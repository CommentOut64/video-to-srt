"""
模型预加载和缓存管理器
实现模型预加载、LRU缓存、内存监控等功能
"""

import os
import gc
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import psutil
import torch
import whisperx

# 修复导入路径
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.job_models import JobSettings


@dataclass
class ModelCacheInfo:
    """模型缓存信息"""
    model: Any
    key: Tuple[str, str, str]
    load_time: float
    last_used: float
    memory_size: int  # 估算的内存占用(MB)


@dataclass
class PreloadConfig:
    """预加载配置"""
    enabled: bool = True
    default_models: List[str] = None
    max_cache_size: int = 3  # 最大缓存模型数量
    memory_threshold: float = 0.8  # 内存使用阈值(80%)
    preload_timeout: int = 300  # 预加载超时时间(秒)
    warmup_enabled: bool = True  # 是否启用预热

    def __post_init__(self):
        if self.default_models is None:
            self.default_models = ["medium"]


class ModelPreloadManager:
    """模型预加载和缓存管理器"""
    
    def __init__(self, config: PreloadConfig = None):
        self.config = config or PreloadConfig()
        self.logger = logging.getLogger(__name__)
        
        # 模型缓存 (LRU)
        self._whisper_cache: OrderedDict[Tuple[str, str, str], ModelCacheInfo] = OrderedDict()
        self._align_cache: OrderedDict[str, Tuple[Any, Any, float]] = OrderedDict()
        
        # 线程锁
        self._whisper_lock = threading.Lock()
        self._align_lock = threading.Lock()
        self._preload_lock = threading.Lock()
        
        # 预加载状态
        self._preload_status = {
            "is_preloading": False,
            "progress": 0.0,
            "current_model": "",
            "total_models": 0,
            "loaded_models": 0,
            "errors": []
        }
        
        # 内存监控
        self._memory_monitor = MemoryMonitor()
        
    def get_preload_status(self) -> Dict[str, Any]:
        """获取预加载状态"""
        return self._preload_status.copy()
    
    def get_cache_status(self) -> Dict[str, Any]:
        """获取缓存状态"""
        with self._whisper_lock:
            whisper_models = [
                {
                    "key": info.key,
                    "memory_mb": info.memory_size,
                    "last_used": info.last_used,
                    "load_time": info.load_time
                }
                for info in self._whisper_cache.values()
            ]
        
        with self._align_lock:
            align_models = list(self._align_cache.keys())
        
        return {
            "whisper_models": whisper_models,
            "align_models": align_models,
            "total_memory_mb": sum(info.memory_size for info in self._whisper_cache.values()),
            "max_cache_size": self.config.max_cache_size,
            "memory_info": self._memory_monitor.get_memory_info()
        }
    
    async def preload_models(self, progress_callback=None) -> Dict[str, Any]:
        """预加载默认模型"""
        self.logger.info("=== 开始模型预加载流程 ===")
        
        if not self.config.enabled:
            self.logger.warning("模型预加载功能已禁用")
            return {"success": False, "message": "预加载功能已禁用"}
        
        with self._preload_lock:
            if self._preload_status["is_preloading"]:
                self.logger.warning("预加载正在进行中，跳过新的预加载请求")
                return {"success": False, "message": "预加载正在进行中"}
            
            self._preload_status.update({
                "is_preloading": True,
                "progress": 0.0,
                "current_model": "",
                "total_models": len(self.config.default_models),
                "loaded_models": 0,
                "errors": []
            })
        
        self.logger.info(f"预加载配置: 模型={self.config.default_models}, 最大缓存={self.config.max_cache_size}, 预热={self.config.warmup_enabled}")
        
        try:
            for i, model_name in enumerate(self.config.default_models):
                try:
                    self.logger.info(f"开始预加载模型 {i+1}/{len(self.config.default_models)}: {model_name}")
                    
                    # 检查内存
                    memory_info = self._memory_monitor.get_memory_info()
                    self.logger.info(f"当前内存使用: 系统 {memory_info.get('system_memory_percent', 0):.1f}%")
                    
                    if not self._memory_monitor.check_memory_available():
                        error_msg = f"内存不足，跳过模型 {model_name} (系统内存使用: {memory_info.get('system_memory_percent', 0):.1f}%)"
                        self.logger.warning(error_msg)
                        self._preload_status["errors"].append(error_msg)
                        continue
                    
                    # 更新状态
                    self._preload_status.update({
                        "current_model": model_name,
                        "progress": (i / len(self.config.default_models)) * 100
                    })
                    
                    self.logger.info(f"预加载进度: {self._preload_status['progress']:.1f}%")
                    
                    if progress_callback:
                        progress_callback(self._preload_status.copy())
                    
                    # 预加载模型
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                    settings = JobSettings(
                        model=model_name,
                        compute_type="float16",
                        device=device
                    )
                    
                    self.logger.info(f"使用配置加载模型: model={model_name}, device={device}, compute_type=float16")
                    
                    start_time = time.time()
                    model = self._load_whisper_model(settings)
                    load_time = time.time() - start_time
                    
                    # 预热模型
                    if self.config.warmup_enabled:
                        self.logger.info(f"开始预热模型 {model_name}")
                        warmup_start = time.time()
                        self._warmup_model(model)
                        warmup_time = time.time() - warmup_start
                        self.logger.info(f"模型 {model_name} 预热完成 (耗时: {warmup_time:.2f}s)")
                    
                    self._preload_status["loaded_models"] += 1
                    
                    self.logger.info(f"✓ 成功预加载模型 {model_name} (总耗时: {load_time:.2f}s)")
                    
                except Exception as e:
                    error_msg = f"预加载模型 {model_name} 失败: {str(e)}"
                    self.logger.error(error_msg, exc_info=True)
                    self._preload_status["errors"].append(error_msg)
            
            # 完成预加载
            self._preload_status.update({
                "is_preloading": False,
                "progress": 100.0,
                "current_model": ""
            })
            
            success = self._preload_status["loaded_models"] > 0
            result = {
                "success": success,
                "loaded_models": self._preload_status["loaded_models"],
                "total_models": self._preload_status["total_models"],
                "errors": self._preload_status["errors"],
                "cache_status": self.get_cache_status()
            }
            
            if progress_callback:
                progress_callback(self._preload_status.copy())
            
            # 详细的完成日志
            if success:
                self.logger.info(f"=== 模型预加载成功完成 ===")
                self.logger.info(f"成功加载: {result['loaded_models']}/{result['total_models']} 个模型")
                cache_status = self.get_cache_status()
                self.logger.info(f"当前缓存: {len(cache_status['whisper_models'])} 个Whisper模型, {cache_status['total_memory_mb']}MB")
            else:
                self.logger.warning(f"=== 模型预加载完成但无成功加载的模型 ===")
                
            if result['errors']:
                self.logger.warning(f"预加载过程中出现 {len(result['errors'])} 个错误")
                for error in result['errors']:
                    self.logger.warning(f"错误: {error}")
            
            return result
            
        except Exception as e:
            self._preload_status["is_preloading"] = False
            self.logger.error(f"预加载过程异常: {str(e)}", exc_info=True)
            return {"success": False, "message": f"预加载失败: {str(e)}"}
    
    def get_model(self, settings: JobSettings):
        """获取Whisper模型 (带LRU缓存)"""
        key = (settings.model, settings.compute_type, settings.device)
        
        with self._whisper_lock:
            # 命中缓存
            if key in self._whisper_cache:
                info = self._whisper_cache[key]
                info.last_used = time.time()
                # 移到最后 (最近使用)
                self._whisper_cache.move_to_end(key)
                self.logger.debug(f"命中Whisper模型缓存: {key}")
                return info.model
            
            # 缓存未命中，加载新模型
            self.logger.info(f"加载新的Whisper模型: {key}")
            return self._load_whisper_model(settings)
    
    def _load_whisper_model(self, settings: JobSettings):
        """加载Whisper模型"""
        key = (settings.model, settings.compute_type, settings.device)
        
        # 检查内存
        if not self._memory_monitor.check_memory_available():
            self.logger.warning("内存不足，尝试清理缓存")
            self._cleanup_old_models()
        
        # 检查缓存大小
        if len(self._whisper_cache) >= self.config.max_cache_size:
            self._evict_lru_model()
        
        try:
            start_time = time.time()
            model = whisperx.load_model(
                settings.model, 
                settings.device, 
                compute_type=settings.compute_type
            )
            load_time = time.time() - start_time
            
            # 估算内存使用
            memory_size = self._estimate_model_memory(model)
            
            # 添加到缓存
            info = ModelCacheInfo(
                model=model,
                key=key,
                load_time=load_time,
                last_used=time.time(),
                memory_size=memory_size
            )
            
            self._whisper_cache[key] = info
            
            self.logger.info(f"成功加载Whisper模型 {key}, 内存: {memory_size}MB, 耗时: {load_time:.2f}s")
            return model
            
        except Exception as e:
            self.logger.error(f"加载Whisper模型失败 {key}: {str(e)}", exc_info=True)
            raise
    
    def get_align_model(self, lang: str, device: str):
        """获取对齐模型 (带LRU缓存)"""
        with self._align_lock:
            # 命中缓存
            if lang in self._align_cache:
                model, meta, last_used = self._align_cache[lang]
                # 更新使用时间并移到最后
                self._align_cache[lang] = (model, meta, time.time())
                self._align_cache.move_to_end(lang)
                self.logger.debug(f"命中对齐模型缓存: {lang}")
                return model, meta
            
            # 缓存未命中，加载新模型
            self.logger.info(f"加载新的对齐模型: {lang}")
            try:
                model, meta = whisperx.load_align_model(language_code=lang, device=device)
                
                # 添加到缓存 (限制大小)
                if len(self._align_cache) >= 5:  # 对齐模型缓存上限
                    # 移除最旧的
                    oldest = next(iter(self._align_cache))
                    del self._align_cache[oldest]
                
                self._align_cache[lang] = (model, meta, time.time())
                
                self.logger.info(f"成功加载对齐模型: {lang}")
                return model, meta
                
            except Exception as e:
                self.logger.error(f"加载对齐模型失败 {lang}: {str(e)}", exc_info=True)
                raise
    
    def _warmup_model(self, model):
        """预热模型 - 空跑一次确保完全加载"""
        try:
            self.logger.debug("开始模型预热")
            
            # 创建虚拟音频数据 (1秒静音)
            import numpy as np
            dummy_audio = np.zeros(16000, dtype=np.float32)  # 16kHz 1秒
            
            # 空跑一次
            _ = model.transcribe(dummy_audio, batch_size=1, verbose=False)
            
            self.logger.debug("模型预热完成")
            
        except Exception as e:
            self.logger.warning(f"模型预热失败: {str(e)}")
    
    def _evict_lru_model(self):
        """驱逐最久未使用的模型"""
        if not self._whisper_cache:
            return
        
        # 最久未使用的在开头
        oldest_key = next(iter(self._whisper_cache))
        info = self._whisper_cache.pop(oldest_key)
        
        self.logger.info(f"驱逐LRU模型: {oldest_key}, 释放内存: {info.memory_size}MB")
        
        # 释放内存
        del info.model
        del info
        gc.collect()
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    
    def _cleanup_old_models(self):
        """清理旧模型释放内存"""
        current_time = time.time()
        to_remove = []
        
        for key, info in self._whisper_cache.items():
            # 超过10分钟未使用的模型
            if current_time - info.last_used > 600:
                to_remove.append(key)
        
        for key in to_remove:
            info = self._whisper_cache.pop(key)
            self.logger.info(f"清理旧模型: {key}")
            del info.model
            del info
        
        if to_remove:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    
    def _estimate_model_memory(self, model) -> int:
        """估算模型内存使用 (MB)"""
        try:
            # 简单估算，基于模型参数
            if hasattr(model, 'model') and hasattr(model.model, 'parameters'):
                total_params = sum(p.numel() for p in model.model.parameters())
                # 假设每个参数4字节 (float32) 或 2字节 (float16)
                bytes_per_param = 2  # float16
                total_bytes = total_params * bytes_per_param
                return int(total_bytes / (1024 * 1024))  # 转换为MB
        except:
            pass
        
        # 默认估算值
        return 500  # 默认500MB
    
    def clear_cache(self):
        """清空所有缓存"""
        with self._whisper_lock:
            for info in self._whisper_cache.values():
                del info.model
            self._whisper_cache.clear()
        
        with self._align_lock:
            self._align_cache.clear()
        
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        self.logger.info("已清空所有模型缓存")


class MemoryMonitor:
    """内存监控器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_memory_info(self) -> Dict[str, Any]:
        """获取内存信息"""
        try:
            # 系统内存
            memory = psutil.virtual_memory()
            
            # GPU内存 (如果可用)
            gpu_info = {}
            if torch.cuda.is_available():
                gpu_info = {
                    "gpu_memory_total": torch.cuda.get_device_properties(0).total_memory / (1024**3),  # GB
                    "gpu_memory_allocated": torch.cuda.memory_allocated() / (1024**3),  # GB
                    "gpu_memory_cached": torch.cuda.memory_reserved() / (1024**3),  # GB
                }
            
            return {
                "system_memory_total": memory.total / (1024**3),  # GB
                "system_memory_used": memory.used / (1024**3),  # GB
                "system_memory_percent": memory.percent,
                **gpu_info
            }
        except Exception as e:
            self.logger.error(f"获取内存信息失败: {str(e)}")
            return {}
    
    def check_memory_available(self, threshold: float = 0.85) -> bool:
        """检查内存是否充足"""
        try:
            memory = psutil.virtual_memory()
            return memory.percent < (threshold * 100)
        except:
            return True  # 默认认为内存充足
