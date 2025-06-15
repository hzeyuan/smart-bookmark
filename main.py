#!/usr/bin/env python3
"""
智能网页爬虫 - 主程序入口
精简高效的架构，专业级代码结构
"""
import asyncio
import logging
import os
from typing import Dict, Any

# 加载环境变量
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


class SmartCrawler:
    """智能爬虫 - 简洁的接口层"""
    
    def __init__(self):
        # 为每个任务生成唯一ID
        from datetime import datetime
        self.task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info("🚀 智能爬虫初始化完成")
        logger.info(f"📋 任务ID: {self.task_id}")
    
    async def crawl(self, instruction: str, url: str = None) -> Dict[str, Any]:
        """执行爬取任务"""
        # 自动推断URL
        if not url:
            url = self._infer_url(instruction)
        
        logger.info(f"📋 任务: {instruction}")
        logger.info(f"🌐 网站: {url}")
        
        # 使用AutomationEngine执行任务
        async with AutomationEngine(self.task_id, headless=False) as engine:
            task_result = await engine.execute_task(instruction, url)
        
        # 转换为简洁的结果格式
        result = {
            "success": task_result.success,
            "data": task_result.final_data,
            "error": task_result.error_message,
            "steps_taken": task_result.total_steps,
            "goal_achieved": task_result.task_state.goal_achieved if task_result.task_state else False
        }
        
        # 简洁的结果展示
        if result["success"]:
            logger.info(f"✅ 成功提取 {len(result['data'])} 条数据")
        else:
            logger.error(f"❌ 失败: {result['error']}")
        
        return result
    
    def _infer_url(self, instruction: str) -> str:
        """从指令推断目标网站"""
        text = instruction.lower()
        
        url_map = {
            ("bilibili", "b站", "哔哩哔哩"): "https://www.bilibili.com",
            ("google", "谷歌"): "https://www.google.com",
            ("github"): "https://github.com",
            ("zhihu", "知乎"): "https://www.zhihu.com",
            ("baidu", "百度"): "https://www.baidu.com"
        }
        
        for keywords, url in url_map.items():
            if any(keyword in text for keyword in keywords):
                return url
        
        return "https://www.google.com"


async def main():
    """主函数"""
    print("\n🌟 智能网页爬虫")
    print("="*50)
    
    # 检查API配置
    if not os.getenv("OPENROUTER_API_KEY"):
        print("❌ 请配置 OPENROUTER_API_KEY 环境变量")
        return
    
    crawler = SmartCrawler()
    
    # 预定义任务
    tasks = [
        "在B站搜索Python教程，获取前5个视频的标题和链接",
        "在Google搜索人工智能发展趋势，获取前3个结果",
        "在GitHub搜索机器学习项目，按star排序获取前5个"
    ]
    
    print("\n🎯 预定义任务:")
    for i, task in enumerate(tasks, 1):
        print(f"{i}. {task}")
    
    print("\n选择:")
    print("1-3: 执行预定义任务")
    print("c: 自定义任务")
    print("q: 退出")
    
    while True:
        choice = input("\n请选择: ").strip().lower()
        
        if choice == 'q':
            print("👋 再见!")
            break
        
        elif choice in ['1', '2', '3']:
            task_idx = int(choice) - 1
            instruction = tasks[task_idx]
            
            print(f"\n🚀 执行任务 {choice}")
            result = await crawler.crawl(instruction)
            
            if result["success"] and result["data"]:
                print(f"\n📋 提取的数据:")
                for i, item in enumerate(result["data"][:3], 1):
                    print(f"   {i}. {item}")
            
        elif choice == 'c':
            instruction = input("请输入任务描述: ").strip()
            if instruction:
                result = await crawler.crawl(instruction)
                
                if result["success"] and result["data"]:
                    print(f"\n📋 提取的数据:")
                    for i, item in enumerate(result["data"][:3], 1):
                        print(f"   {i}. {item}")
        
        else:
            print("❌ 无效选择")


if __name__ == "__main__":
    asyncio.run(main())