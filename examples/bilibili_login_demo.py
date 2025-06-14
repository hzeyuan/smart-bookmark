#!/usr/bin/env python3
"""
B站登录演示 - 作为LLM编排中的一个例子
展示如何处理需要登录的网站
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from load_env import load_dotenv
load_dotenv()

from core import WebOrchestrator
from core.browser import BrowserCore
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BilibiliLoginDemo:
    """B站登录演示"""
    
    def __init__(self):
        self.browser = BrowserCore()
        self.orchestrator = WebOrchestrator()
        self.site_name = "bilibili"
        self.login_url = "https://passport.bilibili.com/login"
        self.check_selector = ".header-avatar-wrap"
    
    async def ensure_login(self) -> bool:
        """确保登录状态"""
        logger.info("🔐 检查B站登录状态...")
        
        page = await self.browser.start(headless=False)  # 非无头模式便于手动登录
        
        # 1. 尝试加载cookies
        await self.browser.load_cookies(self.site_name)
        
        # 2. 检查登录状态
        is_logged_in = await self.browser.check_login_status(
            "https://www.bilibili.com", 
            self.check_selector
        )
        
        if is_logged_in:
            logger.info("✅ 已登录状态")
            return True
        
        # 3. 需要手动登录
        logger.info("⚠️ 未登录，请手动登录...")
        login_success = await self.browser.wait_for_manual_login(
            self.login_url,
            self.check_selector
        )
        
        if login_success:
            # 4. 保存cookies
            await self.browser.save_cookies(self.site_name)
            logger.info("✅ 登录成功，cookies已保存")
            return True
        
        logger.error("❌ 登录失败")
        return False
    
    async def crawl_with_login(self, instruction: str) -> dict:
        """需要登录的爬取任务"""
        # 确保登录
        if not await self.ensure_login():
            return {"success": False, "error": "登录失败"}
        
        # 执行爬取任务
        logger.info(f"🚀 开始执行任务: {instruction}")
        result = await self.orchestrator.run(instruction, "https://www.bilibili.com")
        
        await self.browser.close()
        return result
    
    async def run_demo(self):
        """运行演示"""
        print("\n🎯 B站登录爬取演示")
        print("="*50)
        print("这个演示展示了如何:")
        print("• 智能检测登录状态")
        print("• 自动加载/保存cookies")
        print("• 处理需要登录的任务")
        print("• 集成到LLM编排流程")
        print("="*50)
        
        tasks = [
            "获取我的关注动态，前10条",
            "查看我的收藏夹内容",
            "获取我的观看历史"
        ]
        
        print("\n📋 可执行的任务:")
        for i, task in enumerate(tasks, 1):
            print(f"{i}. {task}")
        
        choice = input("\n选择任务 (1-3) 或输入自定义任务: ").strip()
        
        if choice in ['1', '2', '3']:
            instruction = tasks[int(choice) - 1]
        else:
            instruction = choice
        
        if instruction:
            result = await self.crawl_with_login(instruction)
            
            print(f"\n📊 结果:")
            print(f"成功: {'✅' if result['success'] else '❌'}")
            if result['success']:
                print(f"数据: {len(result.get('data', []))} 条")
                for item in result.get('data', [])[:3]:
                    print(f"  • {item}")
            else:
                print(f"错误: {result.get('error')}")


async def main():
    demo = BilibiliLoginDemo()
    await demo.run_demo()


if __name__ == "__main__":
    asyncio.run(main())