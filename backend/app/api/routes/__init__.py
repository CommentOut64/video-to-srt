"""
API路由模块初始化
"""
from .file_routes import create_file_router
from .transcription_routes import create_transcription_router

__all__ = ['create_file_router', 'create_transcription_router']