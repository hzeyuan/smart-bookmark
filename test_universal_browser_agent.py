#!/usr/bin/env python3
"""
测试通用浏览器代理功能
验证重构后的 BaseBrowserLabelsAgent 是否能作为通用浏览器代理工作
"""
import asyncio
import logging
import json
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


async def test_universal_browser_agent():
    """测试通用浏览器代理在不同网站上的表现"""
    
    test_cases = [
        {
            "name": "Google搜索测试",
            "instruction": "搜索'人工智能发展趋势'",
            "url": "https://www.google.com"
        },
        {
            "name": "知乎测试",
            "instruction": "浏览知乎首页内容",
            "url": "https://www.zhihu.com"
        },
        {
            "name": "GitHub测试",
            "instruction": "浏览GitHub首页",
            "url": "https://github.com"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"🧪 测试 {i}/{len(test_cases)}: {test_case['name']}")
        logger.info(f"📋 任务: {test_case['instruction']}")
        logger.info(f"🌐 网站: {test_case['url']}")
        logger.info(f"{'='*60}")
        
        task_id = f"universal_test_{i}"
        
        try:
            async with AutomationEngine(task_id, headless=False) as engine:
                result = await engine.execute_task(test_case['instruction'], test_case['url'])
                
                # 分析结果
                logger.info(f"\n📊 测试结果:")
                logger.info(f"   成功: {'✅' if result.success else '❌'}")
                logger.info(f"   步骤数: {result.total_steps}")
                logger.info(f"   数据条数: {len(result.final_data)}")
                
                if result.success and result.final_data:
                    logger.info(f"\n📦 提取的数据类型:")
                    for j, data in enumerate(result.final_data[:3], 1):
                        if isinstance(data, dict):
                            logger.info(f"   数据 {j}:")
                            if 'page_info' in data:
                                page_info = data['page_info']
                                logger.info(f"     页面标题: {page_info.get('title', 'N/A')[:50]}...")
                                logger.info(f"     页面URL: {page_info.get('url', 'N/A')}")
                            
                            if 'elements' in data:
                                elements = data['elements']
                                logger.info(f"     可交互元素数量: {len(elements)}")
                                
                                # 分析元素类型
                                element_types = {}
                                for elem in elements[:20]:  # 只分析前20个元素
                                    elem_type = elem.get('type', 'unknown')
                                    element_types[elem_type] = element_types.get(elem_type, 0) + 1
                                
                                logger.info(f"     元素类型分布: {dict(sorted(element_types.items(), key=lambda x: x[1], reverse=True))}")
                            
                            if 'text_content' in data:
                                text_content = data['text_content']
                                logger.info(f"     文本内容长度: {len(text_content)} 字符")
                                if text_content:
                                    logger.info(f"     文本片段: {text_content[:100]}...")
                else:
                    logger.error(f"   错误: {result.error_message}")
                
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 等待一下再进行下一个测试
        await asyncio.sleep(2)
    
    logger.info(f"\n🎉 所有测试完成!")


async def test_element_extraction():
    """专门测试元素提取功能"""
    logger.info(f"\n🔧 专项测试: 元素提取功能")
    
    task_id = "element_extraction_test"
    url = "https://www.baidu.com"  # 使用百度测试，因为页面结构相对简单
    
    try:
        async with AutomationEngine(task_id, headless=False) as engine:
            # 初始化并导航到页面
            await engine.browser_agent.navigate_to(url)
            await engine.browser_agent.sleep(2000)
            
            # 测试获取可交互元素
            logger.info("📋 测试 get_clickable_elements...")
            clickable_data = await engine.browser_agent.get_clickable_elements(with_highlight=False)
            logger.info(f"   找到 {clickable_data.get('count', 0)} 个可交互元素")
            
            # 显示前5个元素的详细信息
            if 'elements' in clickable_data:
                elements = clickable_data['elements']
                logger.info(f"\n📝 前5个元素详情:")
                for i, elem in enumerate(elements[:5], 1):
                    logger.info(f"   元素 {i}:")
                    logger.info(f"     索引: {elem.get('index')}")
                    logger.info(f"     标签: {elem.get('tag')}")
                    logger.info(f"     类型: {elem.get('type')}")
                    logger.info(f"     文本: '{elem.get('text', '')[:30]}...'")
                    if elem.get('placeholder'):
                        logger.info(f"     占位符: {elem.get('placeholder')}")
                    if elem.get('href'):
                        logger.info(f"     链接: {elem.get('href')[:50]}...")
            
            # 测试页面内容提取
            logger.info(f"\n📄 测试 extract_page_content...")
            page_content = await engine.browser_agent.extract_page_content()
            logger.info(f"   页面标题: {page_content.get('title', 'N/A')}")
            logger.info(f"   页面URL: {page_content.get('page_url', 'N/A')}")
            logger.info(f"   内容长度: {len(page_content.get('page_content', ''))} 字符")
            
            # 测试通用数据提取
            logger.info(f"\n📊 测试 extract_page_data...")
            page_data = await engine.browser_agent.extract_page_data()
            logger.info(f"   提取的数据项数: {len(page_data)}")
            
            if page_data:
                data = page_data[0]
                logger.info(f"   数据结构包含: {list(data.keys())}")
            
    except Exception as e:
        logger.error(f"❌ 元素提取测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    async def main():
        # 首先运行专项测试
        await test_element_extraction()
        
        # 然后运行通用测试
        await test_universal_browser_agent()
    
    asyncio.run(main())