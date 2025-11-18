"""
任务相关的数据模型定义
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, TYPE_CHECKING
import torch

# 使用TYPE_CHECKING避免循环导入
if TYPE_CHECKING:
    from services.cpu_affinity_service import CPUAffinityConfig


@dataclass
class JobSettings:
    """转录任务设置"""
    model: str = "medium"
    compute_type: str = "float16"
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    batch_size: int = 16
    word_timestamps: bool = False
    cpu_affinity: Optional["CPUAffinityConfig"] = None  # 使用字符串形式的类型注解


@dataclass
class JobState:
    """转录任务状态"""
    job_id: str
    filename: str
    dir: str
    input_path: str = ""  # 添加原始输入路径记录
    settings: JobSettings = field(default_factory=JobSettings)
    status: str = "queued"  # queued, processing, finished, failed, canceled
    phase: str = "pending"  # extract, split, transcribe, srt
    progress: float = 0.0
    message: str = "等待开始"
    error: Optional[str] = None
    segments: List[Dict] = field(default_factory=list)
    processed: int = 0
    total: int = 0
    language: Optional[str] = None
    srt_path: Optional[str] = None
    canceled: bool = False

    def to_dict(self):
        """转换为字典格式，用于API响应"""
        d = asdict(self)
        d.pop('segments', None)  # 不透出内部详情
        return d