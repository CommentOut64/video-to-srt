"""
统一模型与数据集管理服务
- 下载管理
- 缓存管理
- 自动检测语言并下载
- 版本管理
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from pathlib import Path
import threading
import logging
import os
import shutil

from models.model_models import ModelInfo, AlignModelInfo
from core.config import config


class ModelManagerService:
    """
    模型管理服务
    统一管理Whisper模型和对齐模型的下载、缓存、删除
    """

    # 支持的Whisper模型
    WHISPER_MODELS = {
        "tiny": {"size_mb": 75, "desc": "最快，精度较低"},
        "base": {"size_mb": 145, "desc": "快速，精度一般"},
        "small": {"size_mb": 490, "desc": "平衡速度与精度"},
        "medium": {"size_mb": 1500, "desc": "较慢，精度较高"},
        "large-v2": {"size_mb": 3100, "desc": "最慢，精度最高"},
        "large-v3": {"size_mb": 3100, "desc": "最新版本，精度最高"},
    }

    # 支持的语言（对齐模型）
    SUPPORTED_LANGUAGES = {
        "zh": "中文 (Chinese)",
        "en": "英语 (English)",
        "ja": "日语 (Japanese)",
        "ko": "韩语 (Korean)",
        "es": "西班牙语 (Spanish)",
        "fr": "法语 (French)",
        "de": "德语 (German)",
        "ru": "俄语 (Russian)",
        "pt": "葡萄牙语 (Portuguese)",
        "it": "意大利语 (Italian)",
        "ar": "阿拉伯语 (Arabic)",
        "hi": "印地语 (Hindi)",
    }

    def __init__(self, models_dir: Path = None):
        """
        初始化模型管理服务

        Args:
            models_dir: 模型目录路径，默认使用config中的配置
        """
        self.models_dir = models_dir or config.MODELS_DIR
        self.logger = logging.getLogger(__name__)

        # 模型状态跟踪
        self.whisper_models: Dict[str, ModelInfo] = {}
        self.align_models: Dict[str, AlignModelInfo] = {}

        # 下载队列和锁
        self.download_queue = []
        self.download_lock = threading.Lock()

        # 初始化模型信息
        self._init_model_info()

    def _init_model_info(self):
        """扫描本地已有模型"""
        self.logger.info("🔍 扫描本地已有模型...")

        # 初始化Whisper模型信息
        for model_id, info in self.WHISPER_MODELS.items():
            status, local_path = self._check_whisper_model_exists(model_id)
            self.whisper_models[model_id] = ModelInfo(
                model_id=model_id,
                size_mb=info["size_mb"],
                status=status,
                download_progress=100.0 if status == "ready" else 0.0,
                local_path=str(local_path) if local_path else None,
                description=info["desc"]
            )
            if status == "ready":
                self.logger.info(f"✅ 发现Whisper模型: {model_id}")

        # 初始化对齐模型信息
        for lang, name in self.SUPPORTED_LANGUAGES.items():
            status, local_path = self._check_align_model_exists(lang)
            self.align_models[lang] = AlignModelInfo(
                language=lang,
                language_name=name,
                status=status,
                download_progress=100.0 if status == "ready" else 0.0,
                local_path=str(local_path) if local_path else None
            )
            if status == "ready":
                self.logger.info(f"✅ 发现对齐模型: {lang} ({name})")

    def _check_whisper_model_exists(self, model_id: str) -> tuple[str, Optional[Path]]:
        """
        检查Whisper模型是否存在

        Args:
            model_id: 模型ID

        Returns:
            tuple: (状态, 本地路径)
        """
        # WhisperX模型缓存在HuggingFace缓存目录中
        # 路径格式: models/huggingface/hub/models--guillaumekln--faster-whisper-{model}
        hf_cache = config.HF_CACHE_DIR / "hub"

        # 检查可能的模型缓存路径
        possible_paths = [
            hf_cache / f"models--guillaumekln--faster-whisper-{model_id}",
            hf_cache / f"models--Systran--faster-whisper-{model_id}",
        ]

        for path in possible_paths:
            if path.exists():
                return ("ready", path)

        return ("not_downloaded", None)

    def _check_align_model_exists(self, language: str) -> tuple[str, Optional[Path]]:
        """
        检查对齐模型是否存在

        Args:
            language: 语言代码

        Returns:
            tuple: (状态, 本地路径)
        """
        # 对齐模型也缓存在HuggingFace目录中
        hf_cache = config.HF_CACHE_DIR / "hub"

        # 不同语言的模型名称可能不同，这里列举常见的
        # 实际路径需要根据whisperx实现来确定
        model_patterns = [
            f"models--jonatasgrosman--wav2vec2-large-xlsr-53-{language}",
            f"models--facebook--wav2vec2-large-xlsr-53-{language}",
        ]

        for pattern in model_patterns:
            path = hf_cache / pattern
            if path.exists():
                return ("ready", path)

        return ("not_downloaded", None)

    def list_whisper_models(self) -> List[ModelInfo]:
        """列出所有Whisper模型状态"""
        return list(self.whisper_models.values())

    def list_align_models(self) -> List[AlignModelInfo]:
        """列出所有对齐模型状态"""
        return list(self.align_models.values())

    def download_whisper_model(self, model_id: str) -> bool:
        """
        下载Whisper模型

        Args:
            model_id: 模型ID

        Returns:
            bool: 是否成功加入下载队列
        """
        if model_id not in self.whisper_models:
            self.logger.warning(f"❌ 不支持的模型: {model_id}")
            return False

        model = self.whisper_models[model_id]
        if model.status == "downloading":
            self.logger.info(f"⏳ 模型正在下载中: {model_id}")
            return False  # 已在下载中

        # 标记为下载中
        model.status = "downloading"
        model.download_progress = 0.0

        # 启动下载线程
        threading.Thread(
            target=self._download_whisper_model_task,
            args=(model_id,),
            daemon=True,
            name=f"DownloadWhisper-{model_id}"
        ).start()

        self.logger.info(f"🚀 开始下载Whisper模型: {model_id}")
        return True

    def download_align_model(self, language: str) -> bool:
        """
        下载对齐模型

        Args:
            language: 语言代码

        Returns:
            bool: 是否成功加入下载队列
        """
        if language not in self.align_models:
            self.logger.warning(f"❌ 不支持的语言: {language}")
            return False

        model = self.align_models[language]
        if model.status == "downloading":
            self.logger.info(f"⏳ 对齐模型正在下载中: {language}")
            return False

        # 标记为下载中
        model.status = "downloading"
        model.download_progress = 0.0

        # 启动下载线程
        threading.Thread(
            target=self._download_align_model_task,
            args=(language,),
            daemon=True,
            name=f"DownloadAlign-{language}"
        ).start()

        self.logger.info(f"🚀 开始下载对齐模型: {language}")
        return True

    def auto_download_for_language(self, language: str) -> bool:
        """
        自动下载指定语言所需的对齐模型
        用于断点续传恢复时自动补齐模型

        Args:
            language: 语言代码

        Returns:
            bool: 是否需要下载（True）或已存在（False）
        """
        if language not in self.align_models:
            self.logger.warning(f"⚠️ 不支持的语言: {language}")
            return False

        model = self.align_models[language]

        if model.status == "ready":
            self.logger.info(f"✅ 对齐模型已存在: {language}")
            return False

        self.logger.info(f"🔍 检测到新语言 {language}，开始自动下载对齐模型")
        return self.download_align_model(language)

    def delete_whisper_model(self, model_id: str) -> bool:
        """
        删除Whisper模型

        Args:
            model_id: 模型ID

        Returns:
            bool: 是否删除成功
        """
        if model_id not in self.whisper_models:
            return False

        model = self.whisper_models[model_id]

        if model.status != "ready" or not model.local_path:
            self.logger.warning(f"⚠️ 模型未下载或路径不存在: {model_id}")
            return False

        try:
            # 删除模型目录
            local_path = Path(model.local_path)
            if local_path.exists():
                shutil.rmtree(local_path)
                self.logger.info(f"🗑️ 已删除Whisper模型: {model_id}")

            # 更新状态
            model.status = "not_downloaded"
            model.download_progress = 0.0
            model.local_path = None

            return True

        except Exception as e:
            self.logger.error(f"❌ 删除模型失败: {model_id} - {e}")
            return False

    def delete_align_model(self, language: str) -> bool:
        """
        删除对齐模型

        Args:
            language: 语言代码

        Returns:
            bool: 是否删除成功
        """
        if language not in self.align_models:
            return False

        model = self.align_models[language]

        if model.status != "ready" or not model.local_path:
            self.logger.warning(f"⚠️ 对齐模型未下载或路径不存在: {language}")
            return False

        try:
            # 删除模型目录
            local_path = Path(model.local_path)
            if local_path.exists():
                shutil.rmtree(local_path)
                self.logger.info(f"🗑️ 已删除对齐模型: {language}")

            # 更新状态
            model.status = "not_downloaded"
            model.download_progress = 0.0
            model.local_path = None

            return True

        except Exception as e:
            self.logger.error(f"❌ 删除对齐模型失败: {language} - {e}")
            return False

    def get_download_progress(self) -> Dict:
        """获取所有下载进度"""
        return {
            "whisper": {
                mid: {
                    "status": m.status,
                    "progress": m.download_progress
                }
                for mid, m in self.whisper_models.items()
            },
            "align": {
                lang: {
                    "status": m.status,
                    "progress": m.download_progress
                }
                for lang, m in self.align_models.items()
            }
        }

    def _download_whisper_model_task(self, model_id: str):
        """下载Whisper模型任务（后台线程）"""
        try:
            model = self.whisper_models[model_id]

            # 使用whisperx的下载接口
            import whisperx

            self.logger.info(f"📥 正在下载Whisper模型: {model_id}")

            # 加载模型会自动触发下载
            # device="cpu"表示仅下载，不加载到GPU
            _ = whisperx.load_model(
                model_id,
                device="cpu",
                compute_type="int8",  # 使用较小的精度以节省内存
                download_root=str(config.HF_CACHE_DIR)
            )

            # 下载完成，更新状态
            model.status = "ready"
            model.download_progress = 100.0

            # 重新检查路径
            status, local_path = self._check_whisper_model_exists(model_id)
            if local_path:
                model.local_path = str(local_path)

            self.logger.info(f"✅ Whisper模型下载完成: {model_id}")

        except Exception as e:
            model = self.whisper_models[model_id]
            model.status = "error"
            model.download_progress = 0.0
            self.logger.error(f"❌ Whisper模型下载失败: {model_id} - {e}", exc_info=True)

    def _download_align_model_task(self, language: str):
        """下载对齐模型任务（后台线程）"""
        try:
            model = self.align_models[language]

            import whisperx

            self.logger.info(f"📥 正在下载对齐模型: {language}")

            # 加载对齐模型会自动触发下载
            _, _ = whisperx.load_align_model(
                language_code=language,
                device="cpu",
                model_dir=str(config.HF_CACHE_DIR)
            )

            # 下载完成，更新状态
            model.status = "ready"
            model.download_progress = 100.0

            # 重新检查路径
            status, local_path = self._check_align_model_exists(language)
            if local_path:
                model.local_path = str(local_path)

            self.logger.info(f"✅ 对齐模型下载完成: {language}")

        except Exception as e:
            model = self.align_models[language]
            model.status = "error"
            model.download_progress = 0.0
            self.logger.error(f"❌ 对齐模型下载失败: {language} - {e}", exc_info=True)


# ========== 单例模式 ==========

_model_manager_instance: Optional[ModelManagerService] = None


def get_model_manager() -> ModelManagerService:
    """
    获取模型管理器实例（单例模式）

    Returns:
        ModelManagerService: 模型管理器实例
    """
    global _model_manager_instance
    if _model_manager_instance is None:
        _model_manager_instance = ModelManagerService()
    return _model_manager_instance
