"""
Smart Bookmark - 智能网页自动化核心模块
基于Anthropic协调者-执行者模式的简化架构
"""

# 主要组件
from .automation_engine import AutomationEngine, run_automation_task, quick_search, BatchAutomationEngine
from .plan_agent import PlanAgent  
from .browser_agent import BaseBrowserLabelsAgent
from .types import (
    Action, ActionResult, TaskState, TaskResult, ActionTemplates,
    ActionType, TaskStatus, TaskError, BrowserError, PlanningError
)

# 底层支持
from .plan_agent import SystemPrompt

__all__ = [
    # 核心引擎
    "AutomationEngine", "run_automation_task", "quick_search", "BatchAutomationEngine",
    
    # 核心组件  
    "PlanAgent", "BaseBrowserLabelsAgent",
    
    # 数据类型
    "Action", "ActionResult", "TaskState", "TaskResult", "ActionTemplates",
    "ActionType", "TaskStatus", "TaskError", "BrowserError", "PlanningError",
    
    # 底层支持
    "SystemPrompt"
]