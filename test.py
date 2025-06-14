#!/usr/bin/env python3
"""
简单测试程序
"""
import asyncio
from core import WebOrchestrator
from load_env import load_dotenv

# 加载环境变量
load_dotenv()


async def test():
    """测试核心功能"""
    orchestrator = WebOrchestrator()
    
    # 测试任务
    result = await orchestrator.run(
        instruction="在B站搜索Python教程，获取前5个视频",
        url="https://www.bilibili.com"
    )
    
    print(f"成功: {result['success']}")
    print(f"数据: {len(result['data'])} 条")
    print(f"日志: {result['execution_log']}")


if __name__ == "__main__":
    asyncio.run(test())