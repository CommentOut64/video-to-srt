"""
检查模型预加载状态的脚本
"""

import asyncio
import sys
import os
import json
import requests
import time

# 添加路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'app'))

def check_api_status():
    """通过API检查预加载状态"""
    print("=" * 60)
    print("通过API检查模型预加载状态")
    print("=" * 60)
    
    base_url = "http://127.0.0.1:8000/api"
    
    try:
        # 检查服务是否运行
        print("1. 检查服务状态...")
        response = requests.get(f"{base_url}/files", timeout=5)
        if response.status_code == 200:
            print("✓ 后端服务正在运行")
        else:
            print("✗ 后端服务异常")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ 无法连接到后端服务: {e}")
        print("请确保后端服务已启动: python backend/app/main.py")
        return False
    
    try:
        # 检查预加载状态
        print("\n2. 检查预加载状态...")
        response = requests.get(f"{base_url}/models/preload/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                status = data['data']
                print(f"预加载状态: {'进行中' if status['is_preloading'] else '已完成'}")
                print(f"进度: {status['progress']:.1f}%")
                print(f"当前模型: {status['current_model'] or '无'}")
                print(f"已加载模型: {status['loaded_models']}/{status['total_models']}")
                
                if status['errors']:
                    print("预加载错误:")
                    for error in status['errors']:
                        print(f"  - {error}")
                else:
                    print("✓ 无预加载错误")
            else:
                print(f"✗ 获取预加载状态失败: {data.get('message', 'Unknown error')}")
                return False
        else:
            print(f"✗ API请求失败: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ 请求预加载状态失败: {e}")
        return False
    
    try:
        # 检查缓存状态
        print("\n3. 检查缓存状态...")
        response = requests.get(f"{base_url}/models/cache/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                cache = data['data']
                
                print(f"Whisper模型缓存: {len(cache.get('whisper_models', []))} 个")
                for model in cache.get('whisper_models', []):
                    key = model['key']
                    print(f"  - {key[0]} ({key[1]}, {key[2]}) - {model['memory_mb']}MB")
                
                print(f"对齐模型缓存: {len(cache.get('align_models', []))} 个")
                for lang in cache.get('align_models', []):
                    print(f"  - {lang}")
                
                print(f"总缓存内存: {cache.get('total_memory_mb', 0)}MB")
                
                # 内存信息
                memory = cache.get('memory_info', {})
                if memory:
                    print(f"系统内存: {memory.get('system_memory_used', 0):.1f}GB / {memory.get('system_memory_total', 0):.1f}GB ({memory.get('system_memory_percent', 0):.1f}%)")
                    if memory.get('gpu_memory_total'):
                        print(f"GPU内存: {memory.get('gpu_memory_allocated', 0):.1f}GB / {memory.get('gpu_memory_total', 0):.1f}GB")
            else:
                print(f"✗ 获取缓存状态失败: {data.get('message', 'Unknown error')}")
                return False
        else:
            print(f"✗ API请求失败: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ 请求缓存状态失败: {e}")
        return False
    
    return True

def check_direct_import():
    """直接导入模块检查"""
    print("\n" + "=" * 60)
    print("直接检查模型管理器状态")
    print("=" * 60)
    
    try:
        from processor import get_model_manager, get_preload_status, get_cache_status
        
        print("1. 检查模型管理器...")
        manager = get_model_manager()
        if manager:
            print("✓ 模型管理器已初始化")
            
            print("\n2. 检查预加载状态...")
            status = get_preload_status()
            print(f"预加载状态: {json.dumps(status, indent=2, ensure_ascii=False)}")
            
            print("\n3. 检查缓存状态...")
            cache = get_cache_status()
            print(f"缓存状态: {json.dumps(cache, indent=2, ensure_ascii=False)}")
            
            return True
        else:
            print("✗ 模型管理器未初始化")
            return False
            
    except Exception as e:
        print(f"✗ 直接检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def monitor_preload_progress():
    """监控预加载进度"""
    print("\n" + "=" * 60)
    print("监控预加载进度 (按Ctrl+C停止)")
    print("=" * 60)
    
    base_url = "http://127.0.0.1:8000/api"
    
    try:
        while True:
            try:
                response = requests.get(f"{base_url}/models/preload/status", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data['success']:
                        status = data['data']
                        
                        if status['is_preloading']:
                            print(f"\r预加载进度: {status['progress']:.1f}% - {status['current_model']} ({status['loaded_models']}/{status['total_models']})", end='', flush=True)
                        else:
                            print(f"\n✓ 预加载完成! 已加载 {status['loaded_models']}/{status['total_models']} 个模型")
                            break
                    else:
                        print(f"\n✗ 获取状态失败: {data.get('message', 'Unknown error')}")
                        break
                else:
                    print(f"\n✗ API请求失败: {response.status_code}")
                    break
                    
            except requests.exceptions.RequestException as e:
                print(f"\n✗ 请求失败: {e}")
                break
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n监控已停止")

def start_preload_manually():
    """手动启动预加载"""
    print("\n" + "=" * 60)
    print("手动启动预加载")
    print("=" * 60)
    
    base_url = "http://127.0.0.1:8000/api"
    
    try:
        print("启动预加载...")
        response = requests.post(f"{base_url}/models/preload/start", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                print("✓ 预加载已启动")
                return True
            else:
                print(f"✗ 启动预加载失败: {data.get('message', 'Unknown error')}")
                return False
        else:
            print(f"✗ API请求失败: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ 启动预加载失败: {e}")
        return False

def main():
    """主函数"""
    print("模型预加载状态检查工具")
    print("请选择检查方式:")
    print("1. 通过API检查 (推荐)")
    print("2. 直接导入检查")
    print("3. 监控预加载进度")
    print("4. 手动启动预加载")
    print("5. 全面检查")
    
    choice = input("\n请输入选项 (1-5): ").strip()
    
    if choice == "1":
        check_api_status()
    elif choice == "2":
        check_direct_import()
    elif choice == "3":
        monitor_preload_progress()
    elif choice == "4":
        if start_preload_manually():
            monitor_preload_progress()
    elif choice == "5":
        print("开始全面检查...")
        api_ok = check_api_status()
        if not api_ok:
            print("\nAPI检查失败，尝试直接检查...")
            check_direct_import()
    else:
        print("无效选项")

if __name__ == "__main__":
    main()
