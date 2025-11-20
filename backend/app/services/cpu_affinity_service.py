"""
CPU亲和性管理服务
从processor.py提取并整合
"""

import os
import logging
import platform
from dataclasses import dataclass
from typing import List, Optional

try:
    import psutil
except ImportError:
    psutil = None


@dataclass
class CPUAffinityConfig:
    """CPU亲和性配置"""
    enabled: bool = True
    strategy: str = "auto"  # "auto", "half", "custom"
    custom_cores: Optional[List[int]] = None
    exclude_cores: Optional[List[int]] = None


class CPUAffinityManager:
    """
    CPU亲和性管理器
    通过绑定特定CPU核心来优化性能
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.original_affinity = None
        self.is_supported = psutil is not None and hasattr(psutil.Process(), 'cpu_affinity')

        if not self.is_supported:
            self.logger.warning("⚠️ CPU亲和性功能不可用：psutil未安装或系统不支持")

    def get_system_info(self) -> dict:
        """
        获取系统CPU信息

        Returns:
            dict: CPU信息
                - supported: bool, 是否支持CPU亲和性
                - logical_cores: int, 逻辑核心数
                - physical_cores: int, 物理核心数
                - current_affinity: List[int], 当前亲和性设置
                - platform: str, 操作系统平台
        """
        if not self.is_supported:
            return {"supported": False, "reason": "psutil not available"}

        try:
            cpu_count = psutil.cpu_count(logical=True)
            physical_count = psutil.cpu_count(logical=False)
            current_affinity = psutil.Process().cpu_affinity()

            return {
                "supported": True,
                "logical_cores": cpu_count,
                "physical_cores": physical_count,
                "current_affinity": current_affinity,
                "platform": platform.system()
            }
        except Exception as e:
            return {"supported": False, "error": str(e)}

    def calculate_optimal_cores(
        self,
        strategy: str = "auto",
        custom_cores: Optional[List[int]] = None,
        exclude_cores: Optional[List[int]] = None
    ) -> List[int]:
        """
        计算最佳CPU核心分配

        Args:
            strategy: 分配策略
                - "auto": 自动根据核心数智能分配
                - "half": 使用前50%核心
                - "custom": 使用自定义核心列表
            custom_cores: 自定义核心列表 (strategy="custom"时使用)
            exclude_cores: 排除的核心列表

        Returns:
            List[int]: 推荐使用的核心列表
        """
        if not self.is_supported:
            return []

        try:
            cpu_count = psutil.cpu_count(logical=True)
            available_cores = list(range(cpu_count))

            # 排除指定核心
            if exclude_cores:
                available_cores = [c for c in available_cores if c not in exclude_cores]

            if strategy == "custom" and custom_cores:
                # 使用自定义核心列表，但要确保在可用范围内
                return [c for c in custom_cores if c in available_cores]

            elif strategy == "half":
                # 使用前50%的核心
                half_count = max(1, len(available_cores) // 2)
                return available_cores[:half_count]

            else:  # "auto" 默认策略
                # 智能分配：根据CPU核心数采用不同策略
                if cpu_count <= 4:
                    # 低端系统，使用所有核心
                    return available_cores
                elif cpu_count <= 8:
                    # 中端CPU，留一个核心给系统
                    return available_cores[:-1]
                else:
                    # 高端多核CPU，使用前75%的核心
                    use_count = max(1, int(cpu_count * 0.75))
                    return available_cores[:use_count]

        except Exception as e:
            self.logger.error(f"计算最佳核心失败: {e}")
            return []

    def apply_cpu_affinity(self, config: CPUAffinityConfig) -> bool:
        """
        应用CPU亲和性设置

        Args:
            config: CPU亲和性配置

        Returns:
            bool: 是否应用成功
        """
        if not config.enabled or not self.is_supported:
            return False

        try:
            # 保存原始亲和性设置（用于恢复）
            if self.original_affinity is None:
                self.original_affinity = psutil.Process().cpu_affinity()

            # 计算目标核心
            target_cores = self.calculate_optimal_cores(
                strategy=config.strategy,
                custom_cores=config.custom_cores,
                exclude_cores=config.exclude_cores
            )

            if not target_cores:
                self.logger.warning("未找到可用的CPU核心进行绑定")
                return False

            # 应用亲和性设置
            psutil.Process().cpu_affinity(target_cores)

            # 记录成功信息
            sys_info = self.get_system_info()
            self.logger.info(
                f"✅ CPU亲和性设置成功: "
                f"策略={config.strategy}, "
                f"绑定核心={target_cores}, "
                f"系统核心数={sys_info.get('logical_cores', '?')}"
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ CPU亲和性设置失败: {e}")
            return False

    def restore_cpu_affinity(self) -> bool:
        """
        恢复原始CPU亲和性设置

        Returns:
            bool: 是否恢复成功
        """
        if not self.is_supported or self.original_affinity is None:
            return False

        try:
            psutil.Process().cpu_affinity(self.original_affinity)
            self.logger.info(f"🔄 已恢复CPU亲和性设置: {self.original_affinity}")
            return True
        except Exception as e:
            self.logger.error(f"❌ 恢复CPU亲和性失败: {e}")
            return False
