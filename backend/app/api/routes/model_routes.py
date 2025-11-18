"""
模型管理API路由
"""

from fastapi import APIRouter, HTTPException
from typing import List

from models.model_models import ModelInfo, AlignModelInfo
from services.model_manager_service import get_model_manager

router = APIRouter(prefix="/api/models", tags=["models"])

# 获取模型管理器实例
model_manager = get_model_manager()


@router.get("/whisper", response_model=List[dict])
async def list_whisper_models():
    """
    列出所有Whisper模型

    Returns:
        List[dict]: 模型信息列表
    """
    try:
        models = model_manager.list_whisper_models()
        return [model.to_dict() for model in models]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")


@router.get("/align", response_model=List[dict])
async def list_align_models():
    """
    列出所有对齐模型

    Returns:
        List[dict]: 对齐模型信息列表
    """
    try:
        models = model_manager.list_align_models()
        return [model.to_dict() for model in models]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取对齐模型列表失败: {str(e)}")


@router.post("/whisper/{model_id}/download")
async def download_whisper_model(model_id: str):
    """
    下载指定的Whisper模型

    Args:
        model_id: 模型ID (tiny, base, small, medium, large-v2, large-v3)

    Returns:
        dict: 操作结果
    """
    try:
        success = model_manager.download_whisper_model(model_id)
        if not success:
            raise HTTPException(status_code=400, detail="模型不存在或正在下载中")
        return {"success": True, "message": f"开始下载模型 {model_id}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


@router.post("/align/{language}/download")
async def download_align_model(language: str):
    """
    下载指定语言的对齐模型

    Args:
        language: 语言代码 (zh, en, ja, ko, etc.)

    Returns:
        dict: 操作结果
    """
    try:
        success = model_manager.download_align_model(language)
        if not success:
            raise HTTPException(status_code=400, detail="语言不支持或正在下载中")
        return {"success": True, "message": f"开始下载 {language} 对齐模型"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


@router.delete("/whisper/{model_id}")
async def delete_whisper_model(model_id: str):
    """
    删除指定的Whisper模型

    Args:
        model_id: 模型ID

    Returns:
        dict: 操作结果
    """
    try:
        success = model_manager.delete_whisper_model(model_id)
        if not success:
            raise HTTPException(status_code=400, detail="删除失败：模型不存在或未下载")
        return {"success": True, "message": f"已删除模型 {model_id}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.delete("/align/{language}")
async def delete_align_model(language: str):
    """
    删除指定的对齐模型

    Args:
        language: 语言代码

    Returns:
        dict: 操作结果
    """
    try:
        success = model_manager.delete_align_model(language)
        if not success:
            raise HTTPException(status_code=400, detail="删除失败：模型不存在或未下载")
        return {"success": True, "message": f"已删除对齐模型 {language}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.get("/progress")
async def get_download_progress():
    """
    获取所有下载进度

    Returns:
        dict: 下载进度信息
    """
    try:
        return model_manager.get_download_progress()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取进度失败: {str(e)}")
