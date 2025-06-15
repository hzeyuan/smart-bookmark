#!/usr/bin/env python3
"""
简单测试脚本 - 验证通用浏览器代理的基本功能
"""
import asyncio
import logging
from load_env import load_dotenv
load_dotenv()

from core.browser_agent.base_browser_labels_agent import BaseBrowserLabelsAgent

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


async def test_basic_functions():
    """测试基本的浏览器代理功能"""
    
    logger.info("🧪 开始测试基本的浏览器代理功能")
    
    agent = BaseBrowserLabelsAgent()
    
    try:
        # 初始化代理
        await agent.initialize()
        logger.info("✅ 代理初始化成功")
        
        # 导航到一个简单的页面
        url = "https://www.baidu.com"
        await agent.navigate_to(url)
        logger.info(f"✅ 成功导航到: {url}")
        
        # 等待页面加载
        await agent.sleep(2000)
        
        # 测试获取可交互元素
        logger.info("📋 测试获取可交互元素...")
        elements_data = await agent.get_clickable_elements(with_highlight=False)
        logger.info(f"   找到 {elements_data.get('count', 0)} 个可交互元素")
        
        # 显示前3个元素
        if 'elements' in elements_data:
            elements = elements_data['elements']
            logger.info("   前3个元素:")
            for i, elem in enumerate(elements[:3], 1):
                logger.info(f"     {i}. [{elem.get('index')}] {elem.get('tag')} - '{elem.get('text', '')[:30]}...'")
        
        # 测试页面内容提取
        logger.info("📄 测试页面内容提取...")
        page_content = await agent.extract_page_content()
        logger.info(f"   页面标题: {page_content.get('title', 'N/A')}")
        logger.info(f"   内容长度: {len(page_content.get('page_content', ''))} 字符")
        
        # 测试通用数据提取
        logger.info("📊 测试通用数据提取...")
        page_data = await agent.extract_page_data()
        logger.info(f"   提取数据项数: {len(page_data)}")
        
        if page_data:
            data = page_data[0]
            logger.info(f"   数据结构: {list(data.keys())}")
            if 'elements' in data:
                logger.info(f"   元素数量: {len(data['elements'])}")
        
        logger.info("🎉 所有基本功能测试完成!")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            await agent.close()
            logger.info("✅ 代理已关闭")
        except:
            pass


if __name__ == "__main__":
    asyncio.run(test_basic_functions())