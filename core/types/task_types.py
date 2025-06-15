"""
任务类型定义 - 标准化数据结构用于Agent间通信
基于Anthropic的协调者-执行者模式设计
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Literal
from enum import Enum


class ActionType(str, Enum):
    """操作类型枚举"""
    NAVIGATE = "navigate"
    CLICK = "click"
    INPUT = "input"
    EXTRACT = "extract"
    WAIT = "wait"
    SCROLL = "scroll"
    HOVER = "hover"
    CHECK_GOAL = "check_goal"


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class Action:
    """标准化操作定义 - PlanAgent到BrowserAgent的指令"""
    type: ActionType
    target: Optional[str] = None  # 元素索引、URL或选择器
    value: Optional[str] = None   # 输入值或参数
    description: str = ""         # 操作描述
    timeout: int = 5000          # 超时时间(毫秒)
    retry_count: int = 3         # 重试次数
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "type": self.type.value,
            "target": self.target,
            "value": self.value,
            "description": self.description,
            "timeout": self.timeout,
            "retry_count": self.retry_count
        }


@dataclass
class ActionResult:
    """操作执行结果 - BrowserAgent到PlanAgent的反馈"""
    success: bool
    action: Action
    data: Optional[Dict[str, Any]] = None  # 提取的数据或页面信息
    error: Optional[str] = None            # 错误信息
    page_state: Optional[Dict[str, Any]] = None  # 当前页面状态快照
    execution_time: float = 0.0            # 执行时间(秒)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": self.success,
            "action": self.action.to_dict(),
            "data": self.data,
            "error": self.error,
            "page_state": self.page_state,
            "execution_time": self.execution_time
        }


@dataclass
class TaskState:
    """任务状态 - 替代复杂的WebContext，集中管理状态"""
    instruction: str                        # 用户指令
    target_url: str                        # 目标URL
    current_url: str = ""                  # 当前URL
    status: TaskStatus = TaskStatus.PENDING
    step_count: int = 0                    # 执行步数
    max_steps: int = 15                    # 最大步数
    
    # 执行历史（保持最近5个操作，避免上下文过长）
    recent_actions: List[Action] = field(default_factory=list)
    recent_results: List[ActionResult] = field(default_factory=list)
    
    # 提取的数据
    extracted_data: List[Dict[str, Any]] = field(default_factory=list)
    
    # 错误处理
    error_context: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # 目标检测
    goal_achieved: bool = False
    goal_criteria: Optional[Dict[str, Any]] = None
    
    # 记忆管理（用于避免上下文截断）
    compressed_history: str = ""
    
    def add_action_result(self, action: Action, result: ActionResult):
        """添加操作结果，维护历史记录"""
        self.recent_actions.append(action)
        self.recent_results.append(result)
        self.step_count += 1
        
        # 保持最近5个操作的历史
        if len(self.recent_actions) > 5:
            self.recent_actions.pop(0)
            self.recent_results.pop(0)
        
        # 更新当前URL
        if result.page_state and "url" in result.page_state:
            self.current_url = result.page_state["url"]
    
    def get_recent_summary(self) -> str:
        """获取最近操作的摘要"""
        if not self.recent_actions:
            return "尚未执行任何操作"
        
        summary_parts = []
        for i, (action, result) in enumerate(zip(self.recent_actions, self.recent_results)):
            status = "✅" if result.success else "❌"
            summary_parts.append(f"{status} 步骤{self.step_count-len(self.recent_actions)+i+1}: {action.type.value}")
        
        return " → ".join(summary_parts)
    
    def should_continue(self) -> bool:
        """判断是否应该继续执行"""
        if self.goal_achieved:
            return False
        if self.step_count >= self.max_steps:
            return False
        if self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            return False
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "instruction": self.instruction,
            "target_url": self.target_url,
            "current_url": self.current_url,
            "status": self.status.value,
            "step_count": self.step_count,
            "max_steps": self.max_steps,
            "extracted_data": self.extracted_data,
            "goal_achieved": self.goal_achieved,
            "recent_summary": self.get_recent_summary(),
            "error_context": self.error_context
        }


@dataclass 
class TaskResult:
    """最终任务结果"""
    success: bool
    task_state: TaskState
    final_data: List[Dict[str, Any]] = field(default_factory=list)
    execution_log: List[str] = field(default_factory=list)
    total_steps: int = 0
    total_time: float = 0.0
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": self.success,
            "final_data": self.final_data,
            "execution_log": self.execution_log,
            "total_steps": self.total_steps,
            "total_time": self.total_time,
            "error_message": self.error_message,
            "goal_achieved": self.task_state.goal_achieved,
            "extracted_items": len(self.final_data)
        }


# 常用的操作模板
class ActionTemplates:
    """常用操作的模板"""
    
    @staticmethod
    def navigate(url: str, description: str = "") -> Action:
        """导航操作"""
        return Action(
            type=ActionType.NAVIGATE,
            target=url,
            description=description or f"导航到 {url}"
        )
    
    @staticmethod
    def click(element_index: int, description: str = "") -> Action:
        """点击操作"""
        return Action(
            type=ActionType.CLICK,
            target=str(element_index),
            description=description or f"点击元素 [{element_index}]"
        )
    
    @staticmethod
    def input_text(element_index: int, text: str, press_enter: bool = False) -> Action:
        """输入文本操作"""
        value = f"{text}{'|ENTER' if press_enter else ''}"
        return Action(
            type=ActionType.INPUT,
            target=str(element_index),
            value=value,
            description=f"在元素 [{element_index}] 输入: {text}"
        )
    
    @staticmethod
    def extract_data(description: str = "提取页面数据") -> Action:
        """数据提取操作"""
        return Action(
            type=ActionType.EXTRACT,
            description=description
        )
    
    @staticmethod
    def wait(milliseconds: int = 2000, description: str = "") -> Action:
        """等待操作"""
        return Action(
            type=ActionType.WAIT,
            value=str(milliseconds),
            description=description or f"等待 {milliseconds}ms"
        )
    
    @staticmethod
    def check_goal(criteria: str = "") -> Action:
        """目标检查操作"""
        return Action(
            type=ActionType.CHECK_GOAL,
            value=criteria,
            description="检查任务目标是否完成"
        )


# 错误类型定义
class TaskError(Exception):
    """任务执行错误"""
    def __init__(self, message: str, action: Optional[Action] = None, 
                 recoverable: bool = True):
        super().__init__(message)
        self.action = action
        self.recoverable = recoverable


class BrowserError(TaskError):
    """浏览器操作错误"""
    pass


class PlanningError(TaskError):
    """规划错误"""
    pass


class TimeoutError(TaskError):
    """超时错误"""
    def __init__(self, message: str, action: Optional[Action] = None):
        super().__init__(message, action, recoverable=True)