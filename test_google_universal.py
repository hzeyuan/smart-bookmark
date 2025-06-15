#!/usr/bin/env python3
"""
测试通用浏览器代理在Google搜索上的表现
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


async def test_google_search_universal():
    """使用通用浏览器代理测试Google搜索"""
    
    logger.info("🧪 测试通用浏览器代理 - Google搜索")
    
    task_id = "universal_google_test"
    instruction = "搜索'人工智能发展趋势'"
    url = "https://www.google.com"
    
    try:
        async with AutomationEngine(task_id, headless=False) as engine:
            result = await engine.execute_task(instruction, url)
            
            logger.info(f"\n📊 测试结果:")
            logger.info(f"   成功: {'✅' if result.success else '❌'}")
            logger.info(f"   步骤数: {result.total_steps}")
            logger.info(f"   数据条数: {len(result.final_data)}")
            
            if result.success and result.final_data:
                logger.info(f"\n📦 提取的数据:")
                for i, data in enumerate(result.final_data, 1):
                    logger.info(f"   数据项 {i}:")
                    if isinstance(data, dict):
                        # 显示页面信息
                        if 'page_info' in data:
                            page_info = data['page_info']
                            logger.info(f"     页面: {page_info.get('title', 'N/A')}")
                            logger.info(f"     URL: {page_info.get('url', 'N/A')}")
                        
                        # 显示提取到的元素信息
                        if 'elements' in data:
                            elements = data['elements']
                            logger.info(f"     总元素数: {len(elements)}")
                            
                            # 分析并显示搜索相关的元素
                            search_related = []
                            for elem in elements:
                                text = elem.get('text', '').lower()
                                href = elem.get('href', '').lower()
                                
                                # 如果包含搜索结果特征
                                if (len(elem.get('text', '')) > 10 and 
                                    href and 
                                    'google.com' not in href and
                                    'javascript' not in href and
                                    elem.get('tag') == 'a'):
                                    search_related.append(elem)
                            
                            if search_related:
                                logger.info(f"     潜在搜索结果: {len(search_related)} 个")
                                for j, item in enumerate(search_related[:5], 1):
                                    logger.info(f"       {j}. {item.get('text', '')[:60]}...")
                                    logger.info(f"          URL: {item.get('href', '')[:80]}...")
                            else:
                                logger.info("     未找到明显的搜索结果")
                        
                        # 显示页面文本内容片段
                        if 'text_content' in data:
                            content = data['text_content']
                            logger.info(f"     页面内容长度: {len(content)} 字符")
                            if '人工智能' in content:
                                logger.info("     ✅ 页面内容包含搜索关键词")
                            else:
                                logger.info("     ❌ 页面内容不包含搜索关键词")
            else:
                logger.error(f"   错误: {result.error_message}")
                
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_google_search_universal())