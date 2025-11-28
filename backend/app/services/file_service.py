"""
文件管理服务
"""
import os
from typing import List, Dict
from datetime import datetime


class FileManagementService:
    """文件管理服务"""
    
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = input_dir
        self.output_dir = output_dir
        # 确保目录存在
        for dir_path in [self.input_dir, self.output_dir]:
            os.makedirs(dir_path, exist_ok=True)

    def is_supported_file(self, filename: str) -> bool:
        """检查是否为支持的视频或音频文件"""
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'}
        ext = os.path.splitext(filename.lower())[1]
        return ext in video_extensions or ext in audio_extensions

    def list_input_files(self) -> List[Dict]:
        """获取输入目录中的所有媒体文件"""
        files = []
        if os.path.exists(self.input_dir):
            for filename in os.listdir(self.input_dir):
                file_path = os.path.join(self.input_dir, filename)
                if os.path.isfile(file_path) and self.is_supported_file(filename):
                    stat = os.stat(file_path)
                    files.append({
                        'name': filename,
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        'modified_timestamp': int(stat.st_mtime * 1000),  # 添加时间戳（毫秒）
                        'created_timestamp': int(stat.st_ctime * 1000),  # 添加创建时间戳（毫秒）
                        'path': file_path
                    })

        # 按修改时间倒序排列
        files.sort(key=lambda x: x['modified_timestamp'], reverse=True)
        return files

    def delete_input_file(self, filename: str) -> bool:
        """删除输入目录中的文件"""
        file_path = os.path.join(self.input_dir, filename)
        if not os.path.exists(file_path):
            return False
        try:
            os.remove(file_path)
            return True
        except Exception:
            return False

    def get_input_file_path(self, filename: str) -> str:
        """获取输入文件的完整路径"""
        return os.path.join(self.input_dir, filename)

    def get_output_file_path(self, filename: str) -> str:
        """获取输出文件的完整路径"""
        return os.path.join(self.output_dir, filename)