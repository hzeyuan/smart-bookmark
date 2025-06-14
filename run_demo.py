#!/usr/bin/env python3
"""
快速演示程序
"""
import asyncio
import logging
from load_env import load_dotenv
load_dotenv()

from core import WebOrchestrator

# 设置详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)


async def quick_demo():
    """快速演示"""
    print("🚀 智能网页爬虫演示")
    print("="*50)
    
    orchestrator = WebOrchestrator()
    
    # 演示任务
    task = "在B站搜索Python教程，获取前5个视频的标题和链接"
    
    print(f"📋 任务: {task}")
    print(f"🌐 网站: https://www.bilibili.com")
    print("-" * 50)
    
    result = await orchestrator.run(task, "https://www.bilibili.com")
    
    print(f"\n📊 执行结果:")
    print(f"✅ 成功: {result['success']}")
    print(f"📦 数据量: {len(result['data'])} 条")
    
    if result['data']:
        print(f"\n📋 提取的数据:")
        for i, item in enumerate(result['data'], 1):
            print(f"   {i}. {item}")
    
    print(f"\n📝 执行日志:")
    for log in result['execution_log']:
        print(f"   • {log}")


if __name__ == "__main__":
    asyncio.run(quick_demo())