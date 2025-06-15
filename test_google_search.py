#!/usr/bin/env python3
"""
测试Google搜索功能
"""
import asyncio
import logging
from load_env import load_dotenv
load_dotenv()

from core import AutomationEngine

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


async def test_google_search():
    """测试Google搜索功能"""
    task_id = "test_google_search"
    instruction = "在Google搜索人工智能发展趋势，获取前3个结果"
    url = "https://www.google.com"
    
    logger.info(f"🚀 开始测试Google搜索功能")
    logger.info(f"📋 任务: {instruction}")
    logger.info(f"🌐 网站: {url}")
    
    try:
        async with AutomationEngine(task_id, headless=False) as engine:
            result = await engine.execute_task(instruction, url)
            
        if result.success:
            logger.info(f"✅ 测试成功！提取到 {len(result.final_data)} 条数据")
            logger.info(f"\n📋 提取的数据:")
            for i, item in enumerate(result.final_data, 1):
                logger.info(f"   {i}. 标题: {item.get('title', 'N/A')}")
                logger.info(f"      URL: {item.get('url', 'N/A')}")
                logger.info(f"      类型: {item.get('type', 'N/A')}")
                logger.info("")
        else:
            logger.error(f"❌ 测试失败: {result.error_message}")
            
    except Exception as e:
        logger.error(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_google_search())