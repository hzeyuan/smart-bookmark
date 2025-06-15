"""
AutomationEngine - 简化的自动化任务入口
替代复杂的WebOrchestrator，提供清晰的任务启动和管理接口
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .plan_agent import PlanAgent
from .browser_agent import BaseBrowserLabelsAgent
from .types import TaskResult

logger = logging.getLogger(__name__)


class AutomationEngine:
    """
    自动化引擎 - 简化的任务协调器
    
    核心职责：
    1. 初始化和管理PlanAgent和BrowserAgent
    2. 提供统一的任务执行接口
    3. 资源管理和清理
    4. 向后兼容性支持
    """
    
    def __init__(self, task_id: Optional[str] = None, headless: bool = False):
        """
        初始化自动化引擎
        
        Args:
            task_id: 任务ID，如果为None则自动生成
            headless: 是否无头模式运行浏览器
        """
        self.task_id = task_id or f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.headless = headless
        
        # 初始化核心组件
        self.plan_agent = PlanAgent()
        self.browser_agent = BaseBrowserLabelsAgent()
        self.browser_agent.set_headless(headless)
        
        # 状态管理
        self._initialized = False
        self._task_running = False
        
        logger.info(f"🚀 AutomationEngine 初始化完成 - 任务ID: {self.task_id}")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def initialize(self):
        """初始化引擎组件"""
        if self._initialized:
            logger.warning("⚠️ AutomationEngine 已经初始化")
            return
        
        try:
            logger.info("🔧 正在初始化浏览器代理...")
            await self.browser_agent.initialize()
            
            self._initialized = True
            logger.info("✅ AutomationEngine 初始化完成")
            
        except Exception as e:
            logger.error(f"❌ AutomationEngine 初始化失败: {e}")
            raise
    
    async def execute_task(self, instruction: str, target_url: str, 
                          max_steps: int = 15) -> TaskResult:
        """
        执行自动化任务 - 主要公共接口
        
        Args:
            instruction: 用户指令描述
            target_url: 目标网页URL
            max_steps: 最大执行步数
            
        Returns:
            TaskResult: 任务执行结果
        """
        if not self._initialized:
            await self.initialize()
        
        if self._task_running:
            raise RuntimeError("已有任务正在运行，请等待完成后再执行新任务")
        
        self._task_running = True
        logger.info(f"🎯 开始执行任务: {instruction}")
        logger.info(f"🔗 目标URL: {target_url}")
        logger.info(f"📊 最大步数: {max_steps}")
        
        try:
            # 委托给PlanAgent执行
            result = await self.plan_agent.execute_task(
                instruction=instruction,
                target_url=target_url,
                browser_agent=self.browser_agent,
                max_steps=max_steps
            )
            
            logger.info(f"🏁 任务执行完成: {'成功' if result.success else '失败'}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 任务执行异常: {e}")
            # 返回失败结果而不是抛出异常
            return TaskResult(
                success=False,
                task_state=None,
                final_data=[],
                execution_log=[f"任务执行异常: {str(e)}"],
                total_steps=0,
                total_time=0.0,
                error_message=str(e)
            )
        finally:
            self._task_running = False
    
    async def close(self):
        """关闭引擎，清理资源"""
        if self._task_running:
            logger.warning("⚠️ 有任务正在运行，强制关闭可能导致数据丢失")
        
        try:
            if hasattr(self.browser_agent, 'close'):
                await self.browser_agent.close()
            
            self._initialized = False
            logger.info("✅ AutomationEngine 已关闭")
            
        except Exception as e:
            logger.error(f"❌ 关闭过程中发生错误: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取引擎状态信息"""
        return {
            "task_id": self.task_id,
            "initialized": self._initialized,
            "task_running": self._task_running,
            "headless": self.headless,
            "plan_agent_stats": self.plan_agent.get_statistics() if self._initialized else {},
            "browser_ready": hasattr(self.browser_agent, 'page') and self.browser_agent.page is not None
        }
    
    # ====== 向后兼容性方法 ======
    
    async def run(self, instruction: str, url: str) -> Dict[str, Any]:
        """
        向后兼容的运行方法 - 兼容旧的WebOrchestrator接口
        
        Args:
            instruction: 任务指令
            url: 目标URL
            
        Returns:
            Dict: 与旧接口兼容的结果格式
        """
        result = await self.execute_task(instruction, url)
        
        # 转换为旧格式
        return {
            "success": result.success,
            "data": result.final_data,
            "execution_log": result.execution_log,
            "steps_taken": result.total_steps,
            "goal_achieved": result.task_state.goal_achieved if result.task_state else False,
            "error": result.error_message
        }


# ====== 便捷函数 ======

async def run_automation_task(instruction: str, target_url: str, 
                             headless: bool = True, max_steps: int = 15) -> TaskResult:
    """
    便捷函数：执行单次自动化任务
    
    Args:
        instruction: 任务指令
        target_url: 目标URL
        headless: 是否无头模式
        max_steps: 最大步数
        
    Returns:
        TaskResult: 任务结果
    """
    async with AutomationEngine(headless=headless) as engine:
        return await engine.execute_task(instruction, target_url, max_steps)


async def quick_search(search_query: str, search_engine: str = "google") -> TaskResult:
    """
    便捷函数：快速搜索
    
    Args:
        search_query: 搜索查询
        search_engine: 搜索引擎 (google, bing等)
        
    Returns:
        TaskResult: 搜索结果
    """
    if search_engine.lower() == "google":
        url = "https://www.google.com"
        instruction = f"在Google搜索'{search_query}'并提取搜索结果"
    elif search_engine.lower() == "bing":
        url = "https://www.bing.com"
        instruction = f"在Bing搜索'{search_query}'并提取搜索结果"
    else:
        raise ValueError(f"不支持的搜索引擎: {search_engine}")
    
    return await run_automation_task(instruction, url)


async def extract_page_links(target_url: str) -> TaskResult:
    """
    便捷函数：提取页面链接
    
    Args:
        target_url: 目标页面URL
        
    Returns:
        TaskResult: 提取的链接数据
    """
    instruction = f"访问页面并提取所有有用的链接信息"
    return await run_automation_task(instruction, target_url)


# ====== 批量任务支持 ======

class BatchAutomationEngine:
    """批量任务引擎 - 支持并发执行多个任务"""
    
    def __init__(self, max_concurrent: int = 3, headless: bool = True):
        """
        初始化批量引擎
        
        Args:
            max_concurrent: 最大并发任务数
            headless: 是否无头模式
        """
        self.max_concurrent = max_concurrent
        self.headless = headless
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def execute_batch(self, tasks: List[Dict[str, str]]) -> List[TaskResult]:
        """
        批量执行任务
        
        Args:
            tasks: 任务列表，每个任务包含instruction和target_url
            
        Returns:
            List[TaskResult]: 所有任务的结果
        """
        async def execute_single_task(task_config: Dict[str, str]) -> TaskResult:
            async with self._semaphore:
                return await run_automation_task(
                    instruction=task_config["instruction"],
                    target_url=task_config["target_url"],
                    headless=self.headless,
                    max_steps=task_config.get("max_steps", 15)
                )
        
        logger.info(f"🚀 开始批量执行 {len(tasks)} 个任务，最大并发: {self.max_concurrent}")
        
        # 创建任务协程
        task_coroutines = [execute_single_task(task) for task in tasks]
        
        # 并发执行
        results = await asyncio.gather(*task_coroutines, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ 任务 {i+1} 执行失败: {result}")
                processed_results.append(TaskResult(
                    success=False,
                    task_state=None,
                    final_data=[],
                    execution_log=[f"任务执行异常: {str(result)}"],
                    total_steps=0,
                    total_time=0.0,
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)
        
        success_count = sum(1 for r in processed_results if r.success)
        logger.info(f"📊 批量任务完成: {success_count}/{len(tasks)} 成功")
        
        return processed_results


# ====== 使用示例（仅在直接运行时执行） ======

async def main():
    """使用示例"""
    
    # 示例1: 使用AutomationEngine执行单个任务
    async with AutomationEngine(headless=False) as engine:
        result = await engine.execute_task(
            instruction="搜索人工智能的最新发展趋势",
            target_url="https://www.google.com",
            max_steps=10
        )
        print(f"任务结果: {'成功' if result.success else '失败'}")
        print(f"提取数据: {len(result.final_data)} 条")
    
    # 示例2: 使用便捷函数
    result = await quick_search("Python教程")
    print(f"搜索结果: {len(result.final_data)} 条")
    
    # 示例3: 批量任务
    batch_engine = BatchAutomationEngine(max_concurrent=2)
    tasks = [
        {"instruction": "搜索机器学习", "target_url": "https://www.google.com"},
        {"instruction": "搜索深度学习", "target_url": "https://www.google.com"}
    ]
    batch_results = await batch_engine.execute_batch(tasks)
    print(f"批量任务完成: {len(batch_results)} 个结果")


if __name__ == "__main__":
    asyncio.run(main())