# 废弃文件归档

这些文件已被废弃，仅保留作为历史参考。

## 归档文件列表

### 早期主入口文件

- `main_refactored.py` - 早期重构尝试（68行）
  - 曾尝试使用 transcription_service 的简化版本
  - 已被完整版 main.py 替代
  - 归档时间：2025-11-18

- `main_simple.py` - 简化版本（94行）
  - 早期的简化实现
  - 已被完整版 main.py 替代
  - 归档时间：2025-11-18

- `debug_main.py` - 调试用主入口（39行）
  - 含硬编码绝对路径 (F:\video_to_srt_gpu)
  - 简单的调试API接口
  - 已被完整版 main.py 替代
  - 归档时间：2025-11-18

### 核心处理模块

- `processor.py` - 原处理器模块（82行简化版）
  - **原始功能**：转录处理 + 模型管理 + CPU亲和性（533行）
  - **迁移记录**：
    - `TranscriptionProcessor` → `services/transcription_service.py`
    - `CPUAffinityManager` → `services/cpu_affinity_service.py`
    - `initialize_model_manager`等模型管理函数 → `services/model_preload_manager.py`
  - **简化版**：仅保留模型管理门面函数（最终也被替代）
  - 归档时间：2025-11-18

## 当前唯一入口

**backend/app/main.py** - 项目的唯一主入口文件

## 当前架构

### 服务层 (backend/app/services/)
- `transcription_service.py` - 统一转录服务
- `cpu_affinity_service.py` - CPU亲和性管理
- `model_preload_manager.py` - 模型预加载和缓存管理（含全局单例函数）
- `hardware_service.py` - 硬件检测和优化

### 模型层 (backend/app/models/)
- `job_models.py` - 任务数据模型
- `hardware_models.py` - 硬件信息模型

### 配置层 (backend/app/config/)
- `model_config.py` - 模型配置

## 说明

- 这些文件不应再被使用或修改
- 如需参考历史代码，请查看 git 历史记录
- 所有新功能都应在 backend/app/main.py 和对应的服务模块中开发
- 模型管理功能现在完全由 `services/model_preload_manager.py` 提供
