# Demucs 人声分离集成方案

## 📋 背景与目标

### 问题场景
在有背景音乐的视频中：
- Silero VAD 可能被背景音乐干扰，错误地将音乐段识别为语音段
- Whisper 在背景音乐强的段落可能转录失败或置信度很低
- 字幕时间戳提前/延后，因为 VAD 边界不准确

### 解决方案
集成 **Demucs (Hybrid Transformer Demucs)** 进行人声分离：
- 模型小巧：仅 40-80MB
- 人声保真度高，不会产生"水下音"失真
- 支持 GPU 加速，速度快

### 策略选择

我们采用**"智能检测 + 动态熔断"**的混合策略：

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| **全局预处理** | 整个音频先分离人声，再进行后续处理 | 纯音乐类视频、MV |
| **按需分离** | 只对低置信度段落进行分离重试 | 普通对话视频（偶尔有BGM） |
| **智能模式** | 先检测背景音乐强度，自动选择策略 | 默认推荐 |
| **动态熔断** | 转录过程中检测到持续低置信度，自动升级为全局模式 | 自动兜底 |

### 核心创新：动态熔断机制

即使初始检测判定为"无BGM"，在转录过程中如果发现：
- 连续 3 个 segment 触发低置信度重试
- 或总 segment 的 20% 都需要局部 Demucs 重试

系统会**自动熔断**，停止当前流程，强制升级为**全局分离模式**重新处理。

这解决了"采样漏网"问题——某些视频前中后段都很干净，但中间某处突然出现激烈BGM。

---

## 🏗️ 架构设计

### 整体流程（新版）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         转录主流程 (TranscriptionService)                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. 音频提取                                                             │
│     └─ ffmpeg提取WAV                                                    │
│                                                                         │
│  2. 【新增】背景音乐检测（可选）                                           │
│     └─ DemucsService.detect_background_music_level()                    │
│        ├─ 分位数采样（15%、50%、85%处各取10秒）                            │
│        ├─ 计算 BGM 能量占比                                               │
│        └─ 返回: "none" | "light" | "heavy"                              │
│                                                                         │
│  3. 【新增】全局人声分离（heavy模式下）                                     │
│     └─ DemucsService.separate_vocals()                                  │
│        └─ 返回: vocals.wav（纯人声）                                      │
│                                                                         │
│  4. VAD分段                                                              │
│     └─ 使用原始/分离后的音频进行VAD                                        │
│                                                                         │
│  5. 转录处理（带动态熔断机制）                                              │
│     └─ _transcribe_segment_with_retry()                                 │
│        ├─ 首次转录（使用原始音频）                                         │
│        ├─ 【新增】置信度检测                                              │
│        │   └─ avg_logprob < -0.8 或 no_speech_prob > 0.6                │
│        ├─ 【新增】按需分离重试（light/none模式下）                          │
│        │   └─ DemucsService.separate_vocals_segment()                   │
│        ├─ 【新增】熔断计数器                                              │
│        │   └─ 连续3段或总20%触发重试 → 升级为全局模式                       │
│        └─ 返回最佳结果 或 抛出 BreakToGlobalSeparation 异常               │
│                                                                         │
│  5.5【新增】熔断处理                                                      │
│     └─ 捕获 BreakToGlobalSeparation                                     │
│        ├─ 丢弃已转录内容                                                  │
│        ├─ 全局人声分离                                                    │
│        └─ 从 Step 4 重新开始                                             │
│                                                                         │
│  6. 对齐 & 生成SRT                                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 新增服务：DemucsService

```
backend/app/services/
├── transcription_service.py  (现有，需修改)
├── demucs_service.py         (新增)
└── ...
```

---

## 💻 代码实现

### 1. DemucsService 完整实现

```python
# backend/app/services/demucs_service.py

"""
Demucs 人声分离服务
使用 Hybrid Transformer Demucs (htdemucs) 模型进行高质量人声提取
"""

import os
import gc
import logging
import tempfile
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Literal
from enum import Enum
from dataclasses import dataclass

import torch
import numpy as np
import soundfile as sf


class BGMLevel(Enum):
    """背景音乐强度级别"""
    NONE = "none"      # 无背景音乐
    LIGHT = "light"    # 轻微背景音乐（按需分离）
    HEAVY = "heavy"    # 强背景音乐（全局分离）


@dataclass
class DemucsConfig:
    """Demucs配置"""
    model_name: str = "htdemucs"          # 模型名称
    device: str = "cuda"                   # 设备 (cuda/cpu)
    shifts: int = 1                        # 增强次数（1=快速，5=高质量）
    overlap: float = 0.25                  # 分段重叠率
    segment_length: int = 10               # 每段处理长度（秒）
    
    # 按需分离的缓冲区
    segment_buffer_sec: float = 2.0        # 分离时前后各加的缓冲（秒）
    
    # BGM检测参数（分位数采样策略）
    bgm_sample_duration: float = 10.0      # 每个采样片段的长度（秒）
    bgm_light_threshold: float = 0.2       # 轻微BGM阈值（BGM能量占比）
    bgm_heavy_threshold: float = 0.6       # 强BGM阈值（只要有一处超过此值即为Heavy）


class DemucsService:
    """
    Demucs人声分离服务
    
    支持三种使用模式：
    1. 全局分离：处理整个音频文件，返回纯人声
    2. 按需分离：只处理指定的时间段
    3. BGM检测：快速检测背景音乐强度
    """
    
    _instance = None
    _model = None
    _model_lock = None
    
    def __new__(cls):
        if cls._instance is None:
            import threading
            cls._instance = super().__new__(cls)
            cls._model_lock = threading.Lock()
        return cls._instance
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = DemucsConfig()
        self._cache_dir = Path("models/demucs")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_model(self, device: str = None):
        """
        懒加载Demucs模型
        
        模型首次加载时会自动下载（~80MB）
        """
        if device:
            self.config.device = device
            
        with self._model_lock:
            if self._model is not None:
                return self._model
            
            self.logger.info(f"加载Demucs模型: {self.config.model_name}")
            
            try:
                from demucs.pretrained import get_model
                from demucs.apply import apply_model
                
                # 加载预训练模型
                self._model = get_model(self.config.model_name)
                
                # 移动到指定设备
                if self.config.device == "cuda" and torch.cuda.is_available():
                    self._model.cuda()
                    self.logger.info("Demucs模型已加载到GPU")
                else:
                    self._model.cpu()
                    self.config.device = "cpu"
                    self.logger.info("Demucs模型已加载到CPU")
                
                self._model.eval()
                return self._model
                
            except ImportError:
                raise RuntimeError(
                    "Demucs未安装，请运行: pip install demucs"
                )
    
    def unload_model(self):
        """卸载模型释放显存"""
        with self._model_lock:
            if self._model is not None:
                del self._model
                self._model = None
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                self.logger.info("Demucs模型已卸载")
    
    def separate_vocals(
        self,
        audio_path: str,
        output_path: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> str:
        """
        全局人声分离（处理整个音频文件）
        
        Args:
            audio_path: 输入音频路径
            output_path: 输出路径（可选，默认在同目录生成 xxx_vocals.wav）
            progress_callback: 进度回调 callback(progress: float, message: str)
        
        Returns:
            str: 分离后的人声文件路径
        """
        from demucs.apply import apply_model
        from demucs.audio import AudioFile, save_audio
        
        self.logger.info(f"开始全局人声分离: {audio_path}")
        
        # 生成输出路径
        if output_path is None:
            audio_dir = Path(audio_path).parent
            audio_stem = Path(audio_path).stem
            output_path = str(audio_dir / f"{audio_stem}_vocals.wav")
        
        # 检查缓存
        cache_key = self._get_cache_key(audio_path, "full")
        cached_path = self._cache_dir / f"{cache_key}_vocals.wav"
        if cached_path.exists():
            self.logger.info(f"使用缓存的分离结果: {cached_path}")
            return str(cached_path)
        
        model = self._load_model()
        
        if progress_callback:
            progress_callback(0.1, "加载音频...")
        
        # 加载音频
        wav = AudioFile(audio_path).read(
            streams=0,
            samplerate=model.samplerate,
            channels=model.audio_channels
        )
        
        # 添加batch维度
        ref = wav.mean(0)
        wav = (wav - ref.mean()) / ref.std()
        wav = wav.unsqueeze(0)  # (1, channels, samples)
        
        if self.config.device == "cuda":
            wav = wav.cuda()
        
        if progress_callback:
            progress_callback(0.2, "分离人声中...")
        
        # 执行分离
        with torch.no_grad():
            sources = apply_model(
                model,
                wav,
                shifts=self.config.shifts,
                overlap=self.config.overlap,
                progress=True,
                device=self.config.device
            )
        
        # 提取人声（htdemucs输出顺序：drums, bass, other, vocals）
        # 获取sources名称索引
        source_names = model.sources
        vocals_idx = source_names.index('vocals')
        vocals = sources[0, vocals_idx]  # (channels, samples)
        
        # 恢复原始scale
        vocals = vocals * ref.std() + ref.mean()
        
        if progress_callback:
            progress_callback(0.9, "保存文件...")
        
        # 保存人声
        vocals = vocals.cpu().numpy()
        sf.write(output_path, vocals.T, model.samplerate)
        
        # 保存到缓存
        sf.write(str(cached_path), vocals.T, model.samplerate)
        
        if progress_callback:
            progress_callback(1.0, "人声分离完成")
        
        self.logger.info(f"人声分离完成: {output_path}")
        return output_path
    
    def separate_vocals_segment(
        self,
        audio_array: np.ndarray,
        sr: int,
        start_sec: float,
        end_sec: float,
        buffer_sec: float = None
    ) -> np.ndarray:
        """
        按需分离指定时间段的人声（内存模式）
        
        Args:
            audio_array: 完整音频数组 (samples,) 或 (channels, samples)
            sr: 采样率
            start_sec: 开始时间（秒）
            end_sec: 结束时间（秒）
            buffer_sec: 前后缓冲区（秒），默认使用配置值
        
        Returns:
            np.ndarray: 分离后的人声片段（不含缓冲区）
        """
        from demucs.apply import apply_model
        
        if buffer_sec is None:
            buffer_sec = self.config.segment_buffer_sec
        
        model = self._load_model()
        
        # 计算采样点范围（含缓冲区）
        buffer_samples = int(buffer_sec * sr)
        start_sample = max(0, int(start_sec * sr) - buffer_samples)
        end_sample = min(len(audio_array), int(end_sec * sr) + buffer_samples)
        
        # 提取片段
        if audio_array.ndim == 1:
            segment = audio_array[start_sample:end_sample]
            segment = np.stack([segment, segment])  # 转为立体声
        else:
            segment = audio_array[:, start_sample:end_sample]
        
        # 重采样到模型要求的采样率（如果需要）
        if sr != model.samplerate:
            import librosa
            segment = librosa.resample(segment, orig_sr=sr, target_sr=model.samplerate)
            target_sr = model.samplerate
        else:
            target_sr = sr
        
        # 转为tensor
        wav = torch.from_numpy(segment).float()
        ref = wav.mean(0)
        wav = (wav - ref.mean()) / ref.std()
        wav = wav.unsqueeze(0)
        
        if self.config.device == "cuda":
            wav = wav.cuda()
        
        # 执行分离
        with torch.no_grad():
            sources = apply_model(
                model,
                wav,
                shifts=1,  # 按需分离使用快速模式
                overlap=self.config.overlap,
                progress=False,
                device=self.config.device
            )
        
        # 提取人声
        source_names = model.sources
        vocals_idx = source_names.index('vocals')
        vocals = sources[0, vocals_idx]
        vocals = vocals * ref.std() + ref.mean()
        vocals = vocals.cpu().numpy()
        
        # 重采样回原始采样率
        if target_sr != sr:
            vocals = librosa.resample(vocals, orig_sr=target_sr, target_sr=sr)
        
        # 去除缓冲区，返回原始时间段
        original_start = int(buffer_sec * sr) if start_sec > buffer_sec else int(start_sec * sr)
        original_duration = int((end_sec - start_sec) * sr)
        vocals = vocals[:, original_start:original_start + original_duration]
        
        # 转为单声道（Whisper要求）
        if vocals.ndim > 1:
            vocals = vocals.mean(axis=0)
        
        return vocals
    
    def detect_background_music_level(
        self,
        audio_path: str,
        audio_array: Optional[np.ndarray] = None,
        sr: int = 16000,
        duration_sec: Optional[float] = None
    ) -> Tuple[BGMLevel, List[float]]:
        """
        快速检测背景音乐强度（分位数采样策略）
        
        采样策略：取音频时长的 15%、50%、85% 处各截取 10 秒
        - 15%：捕获 Intro 结束后的主歌背景音
        - 50%：捕获中间部分
        - 85%：捕获结尾前的部分
        
        Args:
            audio_path: 音频文件路径
            audio_array: 音频数组（可选，用于内存模式）
            sr: 采样率
            duration_sec: 音频总时长（可选，如果audio_array提供则自动计算）
        
        Returns:
            Tuple[BGMLevel, List[float]]: (背景音乐强度级别, 各采样点的BGM比例列表)
        """
        self.logger.info("检测背景音乐强度（分位数采样）...")
        
        # 加载音频
        if audio_array is None:
            import librosa
            audio_array, sr = librosa.load(audio_path, sr=sr)
        
        if duration_sec is None:
            duration_sec = len(audio_array) / sr
        
        # 分位数采样位置
        sample_positions = [0.15, 0.50, 0.85]
        sample_duration = self.config.bgm_sample_duration  # 默认10秒
        
        # 检查音频是否足够长
        if duration_sec < sample_duration * 2:
            self.logger.warning(f"音频太短({duration_sec:.1f}s)，无法可靠检测BGM")
            return BGMLevel.LIGHT, []  # 保守起见返回LIGHT
        
        ratios = []
        
        for pos in sample_positions:
            start_time = duration_sec * pos
            
            # 确保不超出边界
            if start_time + sample_duration > duration_sec:
                start_time = duration_sec - sample_duration
            if start_time < 0:
                start_time = 0
            
            try:
                # 分离这一段
                vocals = self.separate_vocals_segment(
                    audio_array, sr,
                    start_sec=start_time,
                    end_sec=start_time + sample_duration,
                    buffer_sec=0.5  # 检测时用较短缓冲
                )
                
                # 获取原始片段
                start_sample = int(start_time * sr)
                end_sample = int((start_time + sample_duration) * sr)
                original = audio_array[start_sample:end_sample]
                
                # 计算BGM能量比（使用改进的算法）
                bgm_ratio = self._calculate_bgm_ratio(original, vocals)
                ratios.append(bgm_ratio)
                
                self.logger.debug(
                    f"采样点 {pos*100:.0f}% ({start_time:.1f}s): BGM比例={bgm_ratio:.2f}"
                )
                    
            except Exception as e:
                self.logger.warning(f"采样点 {pos*100:.0f}% 检测失败: {e}")
                continue
        
        if not ratios:
            return BGMLevel.LIGHT, []  # 默认假设有轻微BGM
        
        # 决策逻辑：使用最大值判断（只要有一处BGM很重，就视为Heavy）
        avg_ratio = np.mean(ratios)
        max_ratio = np.max(ratios)
        
        self.logger.info(
            f"BGM检测完成: 比例={ratios}, 平均={avg_ratio:.2f}, 最大={max_ratio:.2f}"
        )
        
        # 使用max_ratio作为主要判断依据
        if max_ratio > self.config.bgm_heavy_threshold:  # 默认0.6
            return BGMLevel.HEAVY, ratios
        elif max_ratio > self.config.bgm_light_threshold:  # 默认0.2
            return BGMLevel.LIGHT, ratios
        else:
            return BGMLevel.NONE, ratios
    
    def _calculate_bgm_ratio(
        self, 
        original: np.ndarray, 
        vocals: np.ndarray
    ) -> float:
        """
        计算 BGM 能量占比
        
        逻辑：(原音频能量 - 人声能量) / 原音频能量
        
        注意：Demucs分离出的vocals能量可能与原始不完全一致，
        这里使用RMS能量比作为近似估算。
        
        Args:
            original: 原始混合音频
            vocals: 分离后的人声
        
        Returns:
            float: BGM能量占比 (0.0-1.0)，越高表示BGM越强
        """
        # 确保长度一致
        min_len = min(len(original), len(vocals))
        original = original[:min_len]
        vocals = vocals[:min_len]
        
        # 计算均方根能量 (RMS)
        rms_orig = np.sqrt(np.mean(original ** 2))
        rms_voc = np.sqrt(np.mean(vocals ** 2))
        
        # 如果原音就很小（静音片段），返回0
        if rms_orig < 0.01:
            return 0.0
        
        # 计算非人声部分的能量占比（近似背景音）
        # 假设 Energy_Total ≈ Energy_Vocal + Energy_BGM
        # BGM_ratio ≈ 1 - (Vocal_RMS / Total_RMS)
        bgm_ratio = 1.0 - (rms_voc / (rms_orig + 1e-6))
        
        return max(0.0, min(1.0, bgm_ratio))  # 钳制在0-1范围
    
    def _get_cache_key(self, audio_path: str, mode: str) -> str:
        """生成缓存键"""
        path_hash = hashlib.md5(audio_path.encode()).hexdigest()[:16]
        mtime = int(os.path.getmtime(audio_path))
        return f"{path_hash}_{mtime}_{mode}"


# 全局单例
_demucs_service: Optional[DemucsService] = None


def get_demucs_service() -> DemucsService:
    """获取Demucs服务单例"""
    global _demucs_service
    if _demucs_service is None:
        _demucs_service = DemucsService()
    return _demucs_service
```

### 2. TranscriptionService 修改

#### 2.1 新增配置项

```python
# 在 VADConfig 后面添加

class BreakToGlobalSeparation(Exception):
    """
    熔断异常：触发时需要升级为全局人声分离模式
    """
    pass


@dataclass
class DemucsIntegrationConfig:
    """Demucs集成配置"""
    enabled: bool = True                    # 是否启用Demucs
    mode: str = "auto"                      # 模式: "auto" | "always" | "never" | "on_demand"
    
    # 重试阈值
    retry_threshold_logprob: float = -0.8   # 重试阈值（avg_logprob）
    retry_threshold_no_speech: float = 0.6  # 重试阈值（no_speech_prob）
    max_retries: int = 1                    # 每段最大重试次数
    
    # 动态熔断配置
    enable_circuit_breaker: bool = True     # 是否启用动态熔断
    consecutive_retry_threshold: int = 3    # 连续重试触发熔断的阈值
    total_retry_ratio_threshold: float = 0.2  # 总重试比例触发熔断的阈值（20%）


@dataclass
class CircuitBreakerState:
    """
    熔断器状态（用于跟踪转录过程中的重试情况）
    """
    consecutive_retries: int = 0            # 连续重试计数
    total_retries: int = 0                  # 总重试次数
    total_segments: int = 0                 # 总段落数
    processed_segments: int = 0             # 已处理段落数
    
    def record_retry(self):
        """记录一次重试"""
        self.consecutive_retries += 1
        self.total_retries += 1
    
    def record_success(self):
        """记录一次成功（重置连续计数）"""
        self.consecutive_retries = 0
        self.processed_segments += 1
    
    def should_break(self, config: DemucsIntegrationConfig) -> bool:
        """
        判断是否应该触发熔断
        
        熔断条件（满足任一即熔断）：
        1. 连续 N 个 segment 都触发重试（默认N=3）
        2. 总重试比例超过阈值（默认20%）
        """
        if not config.enable_circuit_breaker:
            return False
        
        # 条件1：连续重试次数
        if self.consecutive_retries >= config.consecutive_retry_threshold:
            return True
        
        # 条件2：总重试比例（至少处理5个segment后才检查）
        if self.processed_segments >= 5:
            retry_ratio = self.total_retries / self.processed_segments
            if retry_ratio >= config.total_retry_ratio_threshold:
                return True
        
        return False
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "consecutive_retries": self.consecutive_retries,
            "total_retries": self.total_retries,
            "total_segments": self.total_segments,
            "processed_segments": self.processed_segments,
            "retry_ratio": self.total_retries / max(1, self.processed_segments)
        }
```

#### 2.2 修改转录方法

```python
def _transcribe_segment_with_retry(
    self,
    seg_meta: Dict,
    model,
    job: JobState,
    audio_array: Optional[np.ndarray] = None,
    demucs_config: Optional[DemucsIntegrationConfig] = None,
    circuit_breaker: Optional[CircuitBreakerState] = None
) -> Optional[Dict]:
    """
    带重试的转录方法（支持Demucs人声分离重试 + 动态熔断）
    
    流程：
    1. 首次转录（使用原始音频）
    2. 检查置信度
    3. 如果置信度低，使用Demucs分离人声后重试
    4. 更新熔断器状态
    5. 检查是否触发熔断
    6. 返回置信度更高的结果
    
    Raises:
        BreakToGlobalSeparation: 当触发熔断条件时抛出
    """
    if demucs_config is None:
        demucs_config = DemucsIntegrationConfig()
    
    # 首次转录
    result = self._transcribe_segment(seg_meta, model, job, audio_array)
    
    if not result or not demucs_config.enabled:
        if circuit_breaker:
            circuit_breaker.record_success()
        return result
    
    # 检查是否需要重试
    needs_retry = self._check_transcription_confidence(
        result,
        demucs_config.retry_threshold_logprob,
        demucs_config.retry_threshold_no_speech
    )
    
    if not needs_retry:
        # 不需要重试，记录成功
        if circuit_breaker:
            circuit_breaker.record_success()
        return result
    
    # ========== 需要重试的逻辑 ==========
    self.logger.info(f"段落 {seg_meta['index']} 置信度低，尝试人声分离重试")
    
    # 更新熔断器状态
    if circuit_breaker:
        circuit_breaker.record_retry()
        
        # 检查是否触发熔断
        if circuit_breaker.should_break(demucs_config):
            stats = circuit_breaker.get_stats()
            self.logger.warning(
                f"🚨 触发熔断！连续重试={stats['consecutive_retries']}, "
                f"总重试比例={stats['retry_ratio']:.1%}"
            )
            raise BreakToGlobalSeparation(
                f"连续{stats['consecutive_retries']}段需要Demucs重试，"
                f"建议升级为全局人声分离模式"
            )
    
    try:
        from services.demucs_service import get_demucs_service
        demucs = get_demucs_service()
        
        # 提取该段的人声
        start_sec = seg_meta['start']
        end_sec = seg_meta['end']
        
        if audio_array is not None:
            # 内存模式
            vocals = demucs.separate_vocals_segment(
                audio_array, 
                sr=16000, 
                start_sec=start_sec, 
                end_sec=end_sec
            )
            
            # 构造临时seg_meta
            retry_seg = seg_meta.copy()
            retry_seg['start'] = 0  # 因为vocals已经是切片
            retry_seg['end'] = len(vocals) / 16000
            
            # 重新转录
            retry_result = self._transcribe_segment_in_memory(
                vocals, 
                retry_seg, 
                model, 
                job,
                is_vocals=True  # 标记是人声
            )
        else:
            # 硬盘模式：暂不支持，返回原结果
            self.logger.warning("硬盘模式暂不支持Demucs重试")
            return result
        
        if retry_result:
            # 校正时间偏移（恢复到原始时间轴）
            original_start = seg_meta['start']
            for seg in retry_result.get('segments', []):
                seg['start'] += original_start
                seg['end'] += original_start
            
            # 比较两次结果，返回更好的
            if self._is_better_result(retry_result, result):
                self.logger.info(f"段落 {seg_meta['index']} 重试成功，使用分离后的结果")
                retry_result['used_demucs'] = True
                return retry_result
        
    except Exception as e:
        self.logger.warning(f"Demucs重试失败: {e}")
    
    return result


def _check_transcription_confidence(
    self,
    result: Dict,
    logprob_threshold: float,
    no_speech_threshold: float
) -> bool:
    """
    检查转录结果的置信度
    
    Returns:
        bool: True表示置信度低，需要重试
    """
    segments = result.get('segments', [])
    
    if not segments:
        return True  # 没有识别出内容，需要重试
    
    # 计算平均置信度
    total_logprob = 0
    total_no_speech = 0
    count = 0
    
    for seg in segments:
        if 'avg_logprob' in seg:
            total_logprob += seg['avg_logprob']
            count += 1
        if 'no_speech_prob' in seg:
            total_no_speech += seg['no_speech_prob']
    
    if count == 0:
        return False  # 没有置信度信息，不重试
    
    avg_logprob = total_logprob / count
    avg_no_speech = total_no_speech / count if count > 0 else 0
    
    # 判断是否需要重试
    if avg_logprob < logprob_threshold:
        self.logger.debug(f"avg_logprob={avg_logprob:.2f} < {logprob_threshold}, 需要重试")
        return True
    
    if avg_no_speech > no_speech_threshold:
        self.logger.debug(f"no_speech_prob={avg_no_speech:.2f} > {no_speech_threshold}, 需要重试")
        return True
    
    return False


def _is_better_result(self, new_result: Dict, old_result: Dict) -> bool:
    """
    比较两个转录结果，判断新结果是否更好
    """
    new_segments = new_result.get('segments', [])
    old_segments = old_result.get('segments', [])
    
    # 如果新结果没有内容，旧的更好
    if not new_segments:
        return False
    
    # 如果旧结果没有内容，新的更好
    if not old_segments:
        return True
    
    # 比较平均logprob
    def get_avg_logprob(segments):
        logprobs = [s.get('avg_logprob', -1) for s in segments if 'avg_logprob' in s]
        return np.mean(logprobs) if logprobs else -1
    
    new_logprob = get_avg_logprob(new_segments)
    old_logprob = get_avg_logprob(old_segments)
    
    # 新结果的logprob更高（更接近0）则更好
    return new_logprob > old_logprob
```

#### 2.3 主流程熔断处理

```python
def _process_transcription_with_circuit_breaker(
    self,
    job: JobState,
    segments: List[Dict],
    model,
    audio_array: np.ndarray,
    demucs_config: DemucsIntegrationConfig
) -> List[Dict]:
    """
    带熔断机制的转录主流程
    
    流程：
    1. 初始化熔断器
    2. 逐段转录（带重试）
    3. 如果触发熔断 → 升级为全局分离模式，重新开始
    4. 返回最终结果
    """
    max_global_retries = 1  # 最多触发一次全局升级
    global_retry_count = 0
    
    while global_retry_count <= max_global_retries:
        try:
            # 初始化熔断器
            circuit_breaker = CircuitBreakerState(total_segments=len(segments))
            
            results = []
            for seg in segments:
                result = self._transcribe_segment_with_retry(
                    seg,
                    model,
                    job,
                    audio_array=audio_array,
                    demucs_config=demucs_config,
                    circuit_breaker=circuit_breaker
                )
                if result:
                    results.append(result)
            
            # 正常完成，返回结果
            stats = circuit_breaker.get_stats()
            self.logger.info(
                f"转录完成: {stats['processed_segments']}段, "
                f"重试{stats['total_retries']}次 ({stats['retry_ratio']:.1%})"
            )
            return results
            
        except BreakToGlobalSeparation as e:
            global_retry_count += 1
            self.logger.warning(f"🚨 熔断触发 (第{global_retry_count}次): {e}")
            
            if global_retry_count > max_global_retries:
                self.logger.error("已达到最大全局重试次数，使用当前结果")
                break
            
            # ========== 升级为全局分离模式 ==========
            self.logger.info("📢 升级为全局人声分离模式，重新处理...")
            
            # 1. 丢弃已转录内容（results在异常后丢弃）
            
            # 2. 执行全局人声分离
            from services.demucs_service import get_demucs_service
            demucs = get_demucs_service()
            
            # 保存原始音频到临时文件（全局分离需要文件路径）
            import tempfile
            import soundfile as sf
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                temp_path = f.name
                sf.write(temp_path, audio_array, 16000)
            
            try:
                vocals_path = demucs.separate_vocals(
                    temp_path,
                    progress_callback=lambda p, m: self._update_progress(
                        job, 'demucs', p, f'全局人声分离: {m}'
                    )
                )
                
                # 3. 加载分离后的人声
                import whisperx
                audio_array = whisperx.load_audio(vocals_path)
                
                # 4. 重新VAD分段（使用纯人声）
                segments = self._split_audio_in_memory(audio_array, sr=16000)
                
                self.logger.info(f"全局分离完成，重新分段: {len(segments)}段")
                
                # 5. 禁用后续的按需分离（因为已经是纯人声了）
                demucs_config = DemucsIntegrationConfig(
                    enabled=False,  # 禁用进一步的Demucs处理
                    enable_circuit_breaker=False
                )
                
            finally:
                # 清理临时文件
                import os
                os.unlink(temp_path)
            
            # 继续循环，使用分离后的音频重新转录
            continue
    
    return results  # 返回最后一次尝试的结果
```

#### 2.4 完整流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            转录主流程 (含熔断机制)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. 音频提取 → audio.wav                                                    │
│                                                                             │
│  2. BGM检测（分位数采样: 15%, 50%, 85%）                                     │
│     ├─ HEAVY → 直接全局分离 → 跳到 Step 3                                    │
│     ├─ LIGHT → 启用按需分离 → 跳到 Step 4                                    │
│     └─ NONE  → 禁用分离（仍保留熔断机制）→ 跳到 Step 4                        │
│                                                                             │
│  3. 全局人声分离                                                             │
│     └─ DemucsService.separate_vocals() → vocals.wav                         │
│                                                                             │
│  4. VAD分段                                                                  │
│     └─ segments = [seg1, seg2, ...]                                         │
│                                                                             │
│  5. 转录循环（带熔断器）                                                      │
│     ┌─ for seg in segments:                                                 │
│     │   ├─ 首次转录                                                          │
│     │   ├─ 检查置信度                                                        │
│     │   │   ├─ OK → circuit_breaker.record_success()                        │
│     │   │   └─ 低 → circuit_breaker.record_retry()                          │
│     │   │        ├─ 检查熔断条件                                             │
│     │   │        │   ├─ 连续3段重试? → 🚨 BREAK                              │
│     │   │        │   └─ 总重试>20%?  → 🚨 BREAK                              │
│     │   │        └─ 按需Demucs分离 → 重试转录                                 │
│     │   └─ results.append(result)                                           │
│     └─ 正常完成 → 跳到 Step 6                                                │
│                                                                             │
│  5.5 熔断处理 (catch BreakToGlobalSeparation)                               │
│     ├─ 丢弃已转录内容                                                        │
│     ├─ 全局人声分离                                                          │
│     ├─ 重新VAD分段                                                           │
│     ├─ 禁用后续Demucs（已是纯人声）                                           │
│     └─ 回到 Step 5 重新转录                                                  │
│                                                                             │
│  6. 对齐 & 生成SRT                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 文件变更清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/services/demucs_service.py` | Demucs人声分离服务 |
| `docs/Demucs人声分离集成方案.md` | 本文档 |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `backend/app/services/transcription_service.py` | 添加Demucs集成逻辑 |
| `backend/requirements.txt` | 添加 `demucs>=4.0.0` |

---

## 🔧 配置说明

### requirements.txt 添加

```
demucs>=4.0.0
```

### 前端设置（预留）

```json
{
  "demucs": {
    "enabled": true,
    "mode": "auto",
    "retry_threshold_logprob": -0.8,
    "retry_threshold_no_speech": 0.6,
    "circuit_breaker": {
      "enabled": true,
      "consecutive_threshold": 3,
      "ratio_threshold": 0.2
    },
    "bgm_detection": {
      "light_threshold": 0.2,
      "heavy_threshold": 0.6
    }
  }
}
```

### 模式说明

| 模式 | 说明 | 使用场景 |
|------|------|---------|
| `auto` | 智能检测BGM强度，自动选择策略，启用熔断 | **默认推荐** |
| `always` | 始终进行全局人声分离 | MV、游戏直播等已知重BGM |
| `on_demand` | 仅按需分离低置信度段落，不做初始检测 | 轻量处理 |
| `never` | 完全禁用Demucs | 纯对话、播客等 |

---

## 📊 性能预估

| 场景 | 无Demucs | 有Demucs（按需） | 有Demucs（全局） | 熔断升级 |
|------|----------|-----------------|-----------------|---------|
| 10分钟纯对话 | 2分钟 | 2分钟 | 4分钟 | - |
| 10分钟轻BGM | 2分钟 | 2.5分钟（3段重试） | 4分钟 | - |
| 10分钟重BGM | 2分钟（准确率低） | 3分钟（8段重试） | 4分钟（推荐） | - |
| 10分钟MV | 2分钟（几乎无法用） | 4分钟 | 4分钟（推荐） | - |
| 10分钟突发BGM | 2分钟（部分失败） | ~5分钟（触发熔断） | 4分钟 | 先2分钟尝试，熔断后+2分钟 |

### 熔断机制的性能影响

| 情况 | 行为 | 额外耗时 |
|------|------|---------|
| 采样检测成功 | 初始检测就判定Heavy，直接全局分离 | 仅全局分离时间 |
| 采样检测漏网 | 转录中触发熔断，丢弃结果重来 | 浪费的转录时间 + 全局分离时间 |
| 无BGM | 不触发任何Demucs | 0 |

**建议**：对于已知BGM较重的视频（如游戏实况、MV），建议在设置中直接选择"全局分离"模式，避免熔断带来的额外耗时。

---

## 🧪 测试用例

```python
# 测试1: 基本人声分离
def test_demucs_basic():
    from services.demucs_service import get_demucs_service
    demucs = get_demucs_service()
    
    output = demucs.separate_vocals("test_audio.wav")
    assert os.path.exists(output)
    
# 测试2: BGM检测（分位数采样）
def test_bgm_detection():
    from services.demucs_service import get_demucs_service, BGMLevel
    demucs = get_demucs_service()
    
    # 纯对话视频
    level, ratios = demucs.detect_background_music_level("dialogue.wav")
    assert level == BGMLevel.NONE
    assert len(ratios) == 3  # 15%, 50%, 85% 三个采样点
    
    # MV（应使用max_ratio判断）
    level, ratios = demucs.detect_background_music_level("music_video.wav")
    assert level == BGMLevel.HEAVY
    assert max(ratios) > 0.6

# 测试3: 按需分离
def test_segment_separation():
    from services.demucs_service import get_demucs_service
    import numpy as np
    
    demucs = get_demucs_service()
    
    # 模拟10秒音频
    audio = np.random.randn(160000).astype(np.float32)
    
    vocals = demucs.separate_vocals_segment(
        audio, sr=16000,
        start_sec=2.0, end_sec=5.0
    )
    
    # 应该返回约3秒的音频
    assert abs(len(vocals) - 48000) < 1600  # 允许小误差

# 测试4: 熔断器状态
def test_circuit_breaker():
    from services.transcription_service import (
        CircuitBreakerState, 
        DemucsIntegrationConfig
    )
    
    config = DemucsIntegrationConfig(
        consecutive_retry_threshold=3,
        total_retry_ratio_threshold=0.2
    )
    breaker = CircuitBreakerState(total_segments=20)
    
    # 模拟连续重试
    breaker.record_retry()
    assert not breaker.should_break(config)
    breaker.record_retry()
    assert not breaker.should_break(config)
    breaker.record_retry()  # 第3次
    assert breaker.should_break(config)  # 应该触发熔断

# 测试5: 熔断器比例触发
def test_circuit_breaker_ratio():
    from services.transcription_service import (
        CircuitBreakerState, 
        DemucsIntegrationConfig
    )
    
    config = DemucsIntegrationConfig(
        consecutive_retry_threshold=10,  # 高阈值，不会触发连续熔断
        total_retry_ratio_threshold=0.2
    )
    breaker = CircuitBreakerState(total_segments=10)
    
    # 处理5段，其中2段重试（比例40% > 20%）
    breaker.record_success()  # 1
    breaker.record_retry(); breaker.record_success()  # 2 (重试后成功)
    breaker.record_success()  # 3
    breaker.record_retry(); breaker.record_success()  # 4 (重试后成功)
    breaker.record_success()  # 5
    
    # 此时 retry_ratio = 2/5 = 40% > 20%
    assert breaker.should_break(config)
```

---

## ⚠️ 注意事项

1. **首次使用**会自动下载模型（~80MB），需要网络连接
2. **GPU显存**：Demucs需要约2-4GB显存，与Whisper共享时注意显存管理
3. **CPU模式**：支持纯CPU运行，但速度约为GPU的1/5
4. **音频格式**：支持WAV、MP3、FLAC等常见格式

---

## 🎯 关键设计决策

### 为什么用分位数采样而不是随机/均匀采样？

| 采样方式 | 问题 |
|---------|------|
| 随机采样 | 不可复现，可能全部落在静音段 |
| 均匀采样（0s, 60s, 120s...） | 可能恰好避开所有BGM段 |
| **分位数采样（15%, 50%, 85%）** | ✅ 覆盖Intro后、中段、结尾前，概率最高命中BGM |

### 为什么用 max_ratio 而不是 avg_ratio 判断？

```
场景：视频大部分是纯对话，但有一段30秒的MV插入

avg_ratio = (0.1 + 0.1 + 0.8) / 3 = 0.33 → 判定为 LIGHT ❌
max_ratio = max(0.1, 0.1, 0.8) = 0.8 → 判定为 HEAVY ✅
```

**结论**：只要有一处BGM很重，就应该采用全局分离，否则那一段会严重影响字幕质量。

### 为什么需要动态熔断机制？

即使采样了3个点（15%、50%、85%），仍可能出现：
- 视频第4分钟突然插入30秒的激烈摇滚乐
- 前中后都很干净，但某处有突发BGM

**熔断机制的价值**：
1. 实时监控转录质量
2. 发现持续低置信度时及时止损
3. 自动升级为全局分离，避免"一段段修补"的低效策略

### 熔断阈值的选择依据

| 阈值 | 值 | 原因 |
|------|-----|------|
| 连续重试阈值 | 3 | 连续3段都需要Demucs说明问题持续存在 |
| 总重试比例阈值 | 20% | 超过1/5的段落需要重试，效率已经很低 |
| 最小检查段数 | 5 | 避免前几段偶然低置信度就触发熔断 |

---

## 🚀 下一步

1. 实现 `demucs_service.py`
2. 修改 `transcription_service.py` 集成Demucs
3. 添加前端设置界面
4. 添加SSE进度推送（分离进度）

---

## 📊 断点续传机制修改

### 现有机制回顾

当前 checkpoint.json 结构：
```json
{
  "job_id": "xxx",
  "phase": "transcribe",
  "processing_mode": "memory",
  "total_segments": 20,
  "processed_indices": [0, 1, 2, 3],
  "segments": [...],
  "unaligned_results": [...],
  "timestamp": 1234567890
}
```

### 新增字段设计

```json
{
  "job_id": "xxx",
  "phase": "transcribe",
  "processing_mode": "memory",
  
  // ========== 新增：Demucs相关字段 ==========
  "demucs": {
    "enabled": true,
    "mode": "auto",                    // "auto" | "always" | "on_demand" | "never"
    "bgm_level": "light",              // "none" | "light" | "heavy"
    "bgm_ratios": [0.15, 0.12, 0.18],  // 各采样点的BGM比例
    "global_separation_done": false,   // 全局分离是否已完成
    "vocals_path": null,               // 分离后的人声文件路径
    "circuit_breaker": {               // 熔断器状态（用于恢复）
      "consecutive_retries": 0,
      "total_retries": 2,
      "processed_segments": 10
    },
    "retry_triggered": false           // 是否因熔断触发了全局重试
  },
  
  "total_segments": 20,
  "processed_indices": [0, 1, 2, 3],
  "segments": [...],
  "unaligned_results": [...],
  "timestamp": 1234567890
}
```

### 阶段定义扩展

```python
# 原有阶段
PHASES = ["pending", "extract", "split", "transcribe", "align", "srt", "complete"]

# 新增阶段（插入到流程中）
PHASES_WITH_DEMUCS = [
    "pending",
    "extract",          # 音频提取
    "bgm_detect",       # 【新增】BGM检测
    "demucs_global",    # 【新增】全局人声分离（仅Heavy模式）
    "split",            # VAD分段
    "transcribe",       # 转录（含按需分离重试）
    "align",            # 对齐
    "srt",              # 生成字幕
    "complete"
]
```

### 断点恢复逻辑

```python
def _restore_from_checkpoint(self, checkpoint: Dict, job: JobState) -> Dict:
    """
    从检查点恢复任务状态（支持Demucs）
    
    Returns:
        Dict: 恢复的状态信息，包含应从哪个阶段继续
    """
    phase = checkpoint.get('phase', 'pending')
    demucs_state = checkpoint.get('demucs', {})
    
    restore_info = {
        "resume_phase": phase,
        "skip_extract": False,
        "skip_bgm_detect": False,
        "skip_demucs_global": False,
        "skip_split": False,
        "audio_source": "original",  # "original" | "vocals"
        "processed_indices": set(checkpoint.get('processed_indices', [])),
        "unaligned_results": checkpoint.get('unaligned_results', []),
        "circuit_breaker_state": None
    }
    
    # 根据phase决定从哪里继续
    if phase == 'bgm_detect':
        # BGM检测中断，需要重新检测
        restore_info["skip_extract"] = True
        
    elif phase == 'demucs_global':
        # 全局分离中断
        restore_info["skip_extract"] = True
        restore_info["skip_bgm_detect"] = True
        if demucs_state.get('global_separation_done'):
            # 分离已完成，跳过
            restore_info["skip_demucs_global"] = True
            restore_info["audio_source"] = "vocals"
            
    elif phase == 'split_complete':
        # 分段完成，准备转录
        restore_info["skip_extract"] = True
        restore_info["skip_bgm_detect"] = True
        restore_info["skip_demucs_global"] = demucs_state.get('global_separation_done', False)
        restore_info["skip_split"] = True
        if demucs_state.get('vocals_path'):
            restore_info["audio_source"] = "vocals"
            
    elif phase == 'transcribe':
        # 转录中断，恢复进度
        restore_info["skip_extract"] = True
        restore_info["skip_bgm_detect"] = True
        restore_info["skip_demucs_global"] = True
        restore_info["skip_split"] = True
        
        # 恢复熔断器状态
        cb_state = demucs_state.get('circuit_breaker', {})
        if cb_state:
            restore_info["circuit_breaker_state"] = CircuitBreakerState(
                consecutive_retries=cb_state.get('consecutive_retries', 0),
                total_retries=cb_state.get('total_retries', 0),
                processed_segments=cb_state.get('processed_segments', 0),
                total_segments=checkpoint.get('total_segments', 0)
            )
        
        # 判断使用哪个音频源
        if demucs_state.get('vocals_path') and demucs_state.get('global_separation_done'):
            restore_info["audio_source"] = "vocals"
            
    elif phase == 'align':
        # 对齐中断，需要重新对齐（对齐是原子操作）
        restore_info["skip_extract"] = True
        restore_info["skip_bgm_detect"] = True
        restore_info["skip_demucs_global"] = True
        restore_info["skip_split"] = True
        restore_info["resume_phase"] = "align"
        
    return restore_info
```

### 熔断后的checkpoint处理

```python
def _handle_circuit_breaker_triggered(
    self, 
    job: JobState, 
    job_dir: Path,
    checkpoint: Dict
) -> Dict:
    """
    熔断触发后的checkpoint更新
    
    关键：标记retry_triggered=True，清除已有转录结果，
    但保留BGM检测结果（避免重复检测）
    """
    demucs_state = checkpoint.get('demucs', {})
    
    # 更新checkpoint
    new_checkpoint = {
        "job_id": job.job_id,
        "phase": "demucs_global",  # 回退到全局分离阶段
        "processing_mode": checkpoint.get('processing_mode', 'memory'),
        "demucs": {
            **demucs_state,
            "bgm_level": "heavy",           # 强制升级为Heavy
            "global_separation_done": False, # 需要执行全局分离
            "vocals_path": None,
            "retry_triggered": True,         # 标记是熔断触发的
            "circuit_breaker": None          # 清除熔断器状态
        },
        "total_segments": 0,                 # 清除分段信息
        "processed_indices": [],             # 清除进度
        "segments": [],
        "unaligned_results": [],             # 清除转录结果
        "timestamp": time.time()
    }
    
    self._save_checkpoint(job_dir, new_checkpoint, job)
    self.logger.warning("熔断触发，checkpoint已重置，将执行全局人声分离")
    
    return new_checkpoint
```

### 断点续传状态图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         断点续传状态转换图                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [pending] ──► [extract] ──► [bgm_detect] ──┬──► [demucs_global] ──┐       │
│                                             │                       │       │
│                                             │ (Light/None)          │       │
│                                             ▼                       ▼       │
│                                       [split_complete] ◄───────────┘       │
│                                             │                               │
│                                             ▼                               │
│                                       [transcribe] ──┐                      │
│                                             │        │                      │
│                                             │    熔断触发                   │
│                                             │        │                      │
│                                             │        ▼                      │
│                                             │  [demucs_global] ◄──┘        │
│                                             │   (retry_triggered=true)      │
│                                             ▼                               │
│                                        [align]                              │
│                                             │                               │
│                                             ▼                               │
│                                         [srt]                               │
│                                             │                               │
│                                             ▼                               │
│                                       [complete]                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📈 前端进度条修改

### 现有进度权重配置

```python
# backend/app/core/config.py
PHASE_WEIGHTS = {
    "pending": 0,
    "extract": 5,       # 5%
    "split": 5,         # 5%
    "transcribe": 60,   # 60%
    "align": 20,        # 20%
    "srt": 10,          # 10%
    "complete": 0
}
# TOTAL_WEIGHT = 100
```

### 新增Demucs阶段的权重分配

#### 方案A：动态权重（根据是否需要Demucs调整）

```python
def get_phase_weights(self, demucs_mode: str = "none") -> Dict:
    """
    根据Demucs模式返回不同的权重配置
    
    Args:
        demucs_mode: "none" | "detect_only" | "on_demand" | "global"
    """
    if demucs_mode == "none":
        # 无Demucs，使用原有权重
        return {
            "pending": 0,
            "extract": 5,
            "split": 5,
            "transcribe": 60,
            "align": 20,
            "srt": 10,
            "complete": 0
        }
    
    elif demucs_mode == "detect_only":
        # 仅检测（Light/None模式，按需分离）
        return {
            "pending": 0,
            "extract": 5,
            "bgm_detect": 5,      # 【新增】BGM检测占5%
            "split": 5,
            "transcribe": 55,     # 降低，为检测让出空间
            "align": 20,
            "srt": 10,
            "complete": 0
        }
    
    elif demucs_mode == "global":
        # 全局分离（Heavy模式或熔断后）
        return {
            "pending": 0,
            "extract": 5,
            "bgm_detect": 3,      # BGM检测占3%
            "demucs_global": 12,  # 【新增】全局分离占12%
            "split": 5,
            "transcribe": 50,     # 降低，为分离让出空间
            "align": 15,          # 略微降低
            "srt": 10,
            "complete": 0
        }
    
    else:  # "on_demand" 或其他
        return self.get_phase_weights("detect_only")
```

#### 方案B：固定权重（推荐，更简单）

始终预留Demucs的权重位置，即使不使用也快速跳过：

```python
PHASE_WEIGHTS_WITH_DEMUCS = {
    "pending": 0,
    "extract": 5,           # 音频提取 5%
    "bgm_detect": 3,        # BGM检测 3%（不用时快速跳过）
    "demucs_global": 7,     # 全局分离 7%（不用时快速跳过）
    "split": 5,             # VAD分段 5%
    "transcribe": 50,       # 转录 50%
    "align": 20,            # 对齐 20%
    "srt": 10,              # 生成字幕 10%
    "complete": 0
}
# TOTAL_WEIGHT = 100
```

**优点**：前端进度条逻辑不需要根据模式动态调整

### 前端进度条数据结构

```typescript
// 前端接收的SSE进度数据
interface ProgressData {
  job_id: string;
  phase: string;           // 当前阶段
  percent: number;         // 总进度 (0-100)
  phase_percent: number;   // 阶段内进度 (0-100)
  message: string;         // 进度消息
  status: string;
  processed: number;
  total: number;
  
  // 【新增】Demucs相关
  demucs?: {
    enabled: boolean;
    mode: string;           // "auto" | "always" | "on_demand" | "never"
    bgm_level?: string;     // "none" | "light" | "heavy"（检测后才有）
    is_separating?: boolean; // 是否正在分离
    retry_triggered?: boolean; // 是否触发了熔断重试
  };
}
```

### 前端进度条显示逻辑

```typescript
// 阶段中文名称映射（更新）
const PHASE_NAMES: Record<string, string> = {
  pending: '等待中',
  extract: '提取音频',
  bgm_detect: '检测背景音乐',      // 【新增】
  demucs_global: '分离人声',        // 【新增】
  split: '音频分段',
  transcribe: '转录中',
  align: '对齐时间轴',
  srt: '生成字幕',
  complete: '完成'
};

// 进度条颜色（根据阶段）
const PHASE_COLORS: Record<string, string> = {
  pending: 'gray',
  extract: 'blue',
  bgm_detect: 'purple',            // 【新增】紫色表示检测
  demucs_global: 'violet',         // 【新增】紫罗兰色表示分离
  split: 'cyan',
  transcribe: 'green',
  align: 'teal',
  srt: 'orange',
  complete: 'green'
};

// 渲染进度条
function renderProgress(data: ProgressData) {
  const phaseName = PHASE_NAMES[data.phase] || data.phase;
  const phaseColor = PHASE_COLORS[data.phase] || 'blue';
  
  // 特殊处理：熔断重试提示
  let extraMessage = '';
  if (data.demucs?.retry_triggered) {
    extraMessage = ' ⚠️ 检测到强背景音乐，已自动切换为全局人声分离';
  }
  
  return {
    percent: data.percent,
    label: `${phaseName} ${data.phase_percent.toFixed(1)}%`,
    message: data.message + extraMessage,
    color: phaseColor
  };
}
```

### 进度条视觉效果建议

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 任务进度                                                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 35%                │
│                                                                         │
│  阶段: 转录中 (12/30)                                                   │
│  消息: 正在处理第12段...                                                 │
│                                                                         │
│  ┌─ 阶段明细 ─────────────────────────────────────────────────────┐    │
│  │ ✓ 提取音频     [████████████] 100%                              │    │
│  │ ✓ 检测BGM      [████████████] 100%  → Light                     │    │
│  │ ○ 人声分离     [            ]   -   (按需模式，跳过)              │    │
│  │ ✓ 音频分段     [████████████] 100%  → 30段                      │    │
│  │ ● 转录中       [████████░░░░]  40%  → 12/30                     │    │
│  │ ○ 对齐时间轴   [            ]   0%                              │    │
│  │ ○ 生成字幕     [            ]   0%                              │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 熔断重试时的进度条处理

```typescript
// 当收到熔断重试事件时
function handleCircuitBreakerTriggered(data: ProgressData) {
  // 1. 显示提示Toast
  showToast({
    type: 'warning',
    message: '检测到强背景音乐干扰，正在切换为全局人声分离模式...',
    duration: 5000
  });
  
  // 2. 进度回退（视觉效果）
  // 从当前进度平滑回退到 demucs_global 阶段的起点
  animateProgressTo(15);  // 约15%（extract + bgm_detect完成后）
  
  // 3. 更新阶段显示
  updatePhaseDisplay('demucs_global', '分离人声（自动切换）');
}
```

---

## 🔄 SSE事件类型扩展

### 新增事件类型

```python
# 现有事件
SSE_EVENTS = [
    "connected",      # 连接建立
    "progress",       # 进度更新
    "segment",        # 单段转录完成
    "aligned",        # 对齐完成
    "error",          # 错误
    "job_complete",   # 任务完成
    "job_canceled",   # 任务取消
    "job_paused",     # 任务暂停
]

# 新增Demucs相关事件
SSE_EVENTS_DEMUCS = [
    "bgm_detected",           # BGM检测完成
    "demucs_start",           # 开始人声分离
    "demucs_progress",        # 分离进度
    "demucs_complete",        # 分离完成
    "circuit_breaker_triggered",  # 熔断触发
]
```

### 事件数据结构

```python
# BGM检测完成事件
{
    "type": "bgm_detected",
    "data": {
        "level": "light",           # "none" | "light" | "heavy"
        "ratios": [0.15, 0.12, 0.18],
        "max_ratio": 0.18,
        "recommendation": "on_demand"  # 建议的处理模式
    }
}

# 分离进度事件
{
    "type": "demucs_progress",
    "data": {
        "mode": "global",           # "global" | "segment"
        "progress": 0.45,           # 0-1
        "message": "分离中 45%...",
        "segment_index": null       # 仅segment模式有值
    }
}

# 熔断触发事件
{
    "type": "circuit_breaker_triggered",
    "data": {
        "reason": "consecutive",     # "consecutive" | "ratio"
        "stats": {
            "consecutive_retries": 3,
            "total_retries": 5,
            "retry_ratio": 0.25
        },
        "action": "升级为全局人声分离模式",
        "estimated_extra_time": 120  # 预估额外耗时（秒）
    }
}
```

---

## 📁 文件变更清单（更新）

### 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/services/demucs_service.py` | Demucs人声分离服务 |
| `docs/Demucs人声分离集成方案.md` | 本文档 |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `backend/app/services/transcription_service.py` | 添加Demucs集成逻辑、熔断机制、checkpoint扩展 |
| `backend/app/core/config.py` | 添加新的PHASE_WEIGHTS配置 |
| `backend/requirements.txt` | 添加 `demucs>=4.0.0` |
| `frontend/src/components/TaskProgress.vue` | 更新进度条显示逻辑 |
| `frontend/src/types/progress.ts` | 添加Demucs相关类型定义 |
