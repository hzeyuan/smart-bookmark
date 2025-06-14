"""
智能网页自动化提示词系统 - 参考 browser-use 设计
"""
from typing import Dict, List, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SystemPrompt:
    """系统级提示词 - 定义智能体的能力和行为规范"""
    
    def __init__(self):
        self.system_template = """
你是一个专业的网页自动化智能体，具备以下核心能力：

🎯 **核心使命**
通过观察网页状态、推理分析、执行操作的循环，精确完成用户指定的网页任务。

🧠 **工作模式：ReAct (Reasoning + Acting)**
每一步都要：
1. Thought: 分析当前状态，推理下一步行动
2. Action: 执行具体的网页操作
3. Observation: 观察操作结果和页面变化

⚡ **可用操作**
- navigate: 导航到指定URL
- click: 点击页面元素（按钮、链接等）
- type: 在输入框中输入文本
- wait: 等待页面加载或动画完成
- extract: 从页面提取指定数据
- scroll: 滚动页面查看更多内容

🎯 **成功标准**
- 准确理解用户意图
- 高效完成目标任务
- 避免重复无效操作
- 提取完整准确的数据

⚠️ **重要约束**
- 每次只执行一个操作
- 操作前必须先分析推理
- 失败时要调整策略
- 避免陷入循环
"""

    def get_system_message(self) -> SystemMessage:
        return SystemMessage(content=self.system_template)


class AgentStatePrompt:
    """动态状态提示词 - 描述当前页面和执行状态"""
    
    def __init__(self, context):
        self.context = context
    
    def build_state_description(self) -> str:
        """构建详细的状态描述"""
        sections = []
        
        # 任务信息
        sections.append(f"""
📋 **当前任务**
{self.context.instruction}
""")
        
        # 执行进度
        sections.append(f"""
📊 **执行进度**
步骤: {self.context.step_count}/{self.context.max_steps}
状态: {'🎯 目标已达成' if self.context.goal_achieved else '🔄 进行中'}
""")
        
        # 页面状态
        if self.context.current_page_state:
            state = self.context.current_page_state
            sections.append(f"""
🌐 **当前页面状态**
URL: {state.get('url', '未知')}
标题: {state.get('title', '未知')}
搜索框: {'✅ 存在' if state.get('has_search', False) else '❌ 不存在'}
视频数量: {state.get('video_count', 0)}
时间戳: {datetime.now().strftime('%H:%M:%S')}
""")
        
        # 最近操作历史
        if self.context.execution_log:
            recent_logs = self.context.execution_log[-3:]
            sections.append(f"""
📝 **最近操作**
{chr(10).join(f'  • {log}' for log in recent_logs)}
""")
        
        # 上一步操作结果
        if self.context.last_action and self.context.last_result:
            action = self.context.last_action
            result = self.context.last_result
            success = "✅ 成功" if result.get('success', True) else "❌ 失败"
            sections.append(f"""
🔄 **上一步操作**
操作: {action['type']} {action.get('target', '')}
结果: {success}
""")
        
        # 已提取数据
        if self.context.extracted_data:
            data_count = len(self.context.extracted_data)
            sections.append(f"""
📦 **已提取数据**
数量: {data_count} 条
最新: {self.context.extracted_data[-1].get('title', '') if data_count > 0 else '无'}
""")
        
        # 特殊提示
        warnings = []
        if self.context.step_count > 5:
            warnings.append("⚠️ 已执行多步，请检查是否需要调整策略")
        if self.context.step_count > 2 and not any('click' in log for log in self.context.execution_log[-3:]):
            warnings.append("💡 提示：可能需要点击搜索按钮或其他交互元素")
        
        if warnings:
            sections.append(f"""
⚠️ **注意事项**
{chr(10).join(f'  • {warning}' for warning in warnings)}
""")
        
        return "\n".join(sections)
    
    def get_user_message(self) -> HumanMessage:
        """生成用户消息，包含完整状态信息"""
        state_description = self.build_state_description()
        
        # 添加ReAct格式要求
        react_instruction = """

🤖 **请按ReAct格式回应**

Thought: [你的分析推理 - 分析当前状态，思考下一步最佳行动]
Action: {"type": "操作类型", "target": "目标元素", "value": "输入值(可选)"}

请现在开始分析并决定下一步行动：
"""
        
        full_content = state_description + react_instruction
        return HumanMessage(content=full_content)


class PlannerPrompt:
    """规划器专用提示词"""
    
    @staticmethod
    def get_react_instruction() -> str:
        """获取ReAct模式的详细指导"""
        return """
🧠 **ReAct推理模式**

每次回应必须包含：

1. **Thought** (分析推理)
   - 观察当前页面状态
   - 分析已完成的操作
   - 识别下一步的最佳策略
   - 考虑可能的风险和替代方案

2. **Action** (具体行动)
   - 选择最合适的操作类型
   - 指定精确的目标元素
   - 提供必要的参数值

**示例格式:**
```
Thought: 我看到我们已经在B站主页，现在需要在搜索框中输入关键词。页面显示有21个视频，说明页面已加载完成。下一步应该定位搜索框并输入"Python教程"。

Action: {"type": "click", "target": "搜索框"}
```

**操作类型详解:**
- navigate: 打开新页面 {"type": "navigate", "target": "https://example.com"}
- click: 点击元素 {"type": "click", "target": "搜索框/按钮/链接"}
- type: 输入文本 {"type": "type", "target": "输入框", "value": "要输入的内容"}
- wait: 等待加载 {"type": "wait", "ms": 2000}
- extract: 提取数据 {"type": "extract", "target": "数据区域"}
- scroll: 滚动页面 {"type": "scroll", "direction": "down"}
"""


class ErrorRecoveryPrompt:
    """错误恢复提示词"""
    
    @staticmethod
    def get_recovery_instruction(error_info: str, step_count: int) -> str:
        """生成错误恢复指导"""
        return f"""
🚨 **错误恢复模式**

检测到操作失败或异常：
{error_info}

当前已执行 {step_count} 步，请分析失败原因并调整策略：

💡 **恢复策略建议:**
- 检查页面是否发生了预期外的变化
- 尝试不同的元素选择器或操作方式
- 考虑是否需要等待页面加载
- 评估是否需要回退到前一步重新开始

请用 ReAct 格式重新分析并提出解决方案。
"""


class DataExtractionPrompt:
    """数据提取专用提示词"""
    
    @staticmethod
    def get_extraction_instruction(task: str, raw_data: List[Dict]) -> str:
        """生成数据提取指导"""
        return f"""
📊 **数据提取与优化**

原始任务: {task}
提取到 {len(raw_data)} 条原始数据

请将原始数据清洗和结构化为用户友好的格式：

🎯 **输出要求:**
```json
[
  {
    "title": "标题",
    "url": "链接", 
    "description": "描述"
  }
]
```

原始数据:
{raw_data}

请提取并优化数据格式。
"""