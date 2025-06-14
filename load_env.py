"""
加载 .env 环境变量
"""
import os
from pathlib import Path


def load_dotenv():
    """加载 .env 文件中的环境变量"""
    env_path = Path(__file__).parent / '.env'
    
    if not env_path.exists():
        print(f"❌ .env 文件不存在: {env_path}")
        return False
    
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
    
    print(f"✅ 已加载环境变量: {env_path}")
    return True


if __name__ == "__main__":
    load_dotenv()
    
    # 显示关键环境变量
    print("\n🔑 环境变量状态:")
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        print(f"   OPENROUTER_API_KEY: {api_key[:8]}...{api_key[-4:]}")
    else:
        print("   OPENROUTER_API_KEY: 未设置")
    
    print(f"   OPENROUTER_MODEL: {os.getenv('OPENROUTER_MODEL', '未设置')}")
    print(f"   HTTP_REFERER: {os.getenv('HTTP_REFERER', '未设置')}")
    print(f"   X_TITLE: {os.getenv('X_TITLE', '未设置')}")