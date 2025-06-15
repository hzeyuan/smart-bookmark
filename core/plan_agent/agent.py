"""
PlanAgent - 主导智能体
基于Anthropic协调者-执行者模式的核心规划智能体
负责任务理解、分解和协调BrowserAgent执行操作
"""
import os
import asyncio
import logging
import json
import re
import time
from typing import Dict, List, Any, Optional

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from ..types import (
    Action, ActionResult, TaskState, TaskResult, TaskStatus, ActionType,
    ActionTemplates, TaskError, PlanningError, TimeoutError
)
from .prompts import SystemPrompt

logger = logging.getLogger(__name__)


class PlanAgent:
    """
    主导智能体 - 网页自动化任务的大脑
    
    核心职责：
    1. 任务理解和分解
    2. 调用BrowserAgent执行具体操作  
    3. 状态管理和错误恢复
    4. 决定任务完成条件
    """
    
    def __init__(self, temperature: float = 0):
        self.llm = ChatOpenAI(
            model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-sonnet-20240229"),
            temperature=temperature,
            openai_api_base="https://openrouter.ai/api/v1", 
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            default_headers={}
        )
        self.system_prompt = SystemPrompt()
        
        # 统计信息
        self.total_llm_calls = 0
        self.total_tokens_used = 0
    
    async def execute_task(self, instruction: str, target_url: str, 
                          browser_agent, max_steps: int = 15) -> TaskResult:
        """
        执行完整任务 - 主入口方法
        
        Args:
            instruction: 用户指令
            target_url: 目标URL
            browser_agent: 浏览器代理实例
            max_steps: 最大执行步数
            
        Returns:
            TaskResult: 任务执行结果
        """
        start_time = time.time()
        
        # 初始化任务状态
        task_state = TaskState(
            instruction=instruction,
            target_url=target_url,
            status=TaskStatus.IN_PROGRESS,
            max_steps=max_steps
        )
        
        execution_log = []
        logger.info(f"🎯 开始执行任务: {instruction}")
        logger.info(f"🔗 目标URL: {target_url}")
        
        try:
            # 确保浏览器已初始化
            if not hasattr(browser_agent, 'page') or not browser_agent.page:
                await browser_agent.initialize()
                await browser_agent.navigate_to(target_url)
                execution_log.append("✅ 浏览器初始化并导航到目标页面")
            
            # 主执行循环
            while task_state.should_continue():
                try:
                    # 1. 规划下一步操作
                    action = await self._plan_next_action(task_state, browser_agent)
                    execution_log.append(f"📋 步骤 {task_state.step_count + 1}: {action.description}")
                    
                    # 2. 执行操作
                    result = await self._execute_action(action, browser_agent)
                    
                    # 3. 更新状态
                    task_state.add_action_result(action, result)
                    
                    # 4. 记录结果
                    status_icon = "✅" if result.success else "❌"
                    execution_log.append(f"{status_icon} 结果: {result.error or '执行成功'}")
                    
                    # 5. 检查特殊操作结果
                    if action.type == ActionType.EXTRACT and result.success and result.data:
                        extracted_items = result.data.get('data', [])
                        task_state.extracted_data.extend(extracted_items)
                        execution_log.append(f"📦 提取数据: {len(extracted_items)} 条")
                    
                    if action.type == ActionType.CHECK_GOAL and result.success:
                        task_state.goal_achieved = result.data.get('goal_achieved', False)
                        if task_state.goal_achieved:
                            execution_log.append("🎯 目标已达成!")
                            break
                    
                    # 6. 错误处理
                    if not result.success:
                        task_state.retry_count += 1
                        if task_state.retry_count >= task_state.max_retries:
                            task_state.status = TaskStatus.FAILED
                            task_state.error_context = result.error
                            execution_log.append(f"❌ 任务失败: 重试次数过多")
                            break
                        else:
                            execution_log.append(f"🔄 准备重试 ({task_state.retry_count}/{task_state.max_retries})")
                    else:
                        task_state.retry_count = 0  # 重置重试计数
                    
                    # 7. 简单的自动目标检测
                    if self._should_auto_complete(task_state):
                        task_state.goal_achieved = True
                        execution_log.append("🎯 自动检测到任务完成")
                        break
                        
                except Exception as e:
                    logger.error(f"❌ 执行步骤失败: {e}")
                    execution_log.append(f"❌ 步骤 {task_state.step_count + 1} 失败: {str(e)}")
                    task_state.error_context = str(e)
                    task_state.retry_count += 1
                    
                    if task_state.retry_count >= task_state.max_retries:
                        task_state.status = TaskStatus.FAILED
                        break
            
            # 确定最终状态
            if task_state.goal_achieved:
                task_state.status = TaskStatus.COMPLETED
                execution_log.append("🎉 任务成功完成!")
            elif task_state.step_count >= task_state.max_steps:
                task_state.status = TaskStatus.FAILED
                execution_log.append("⚠️ 达到最大步数限制")
            
            total_time = time.time() - start_time
            
            # 构建最终结果
            task_result = TaskResult(
                success=task_state.status == TaskStatus.COMPLETED,
                task_state=task_state,
                final_data=task_state.extracted_data,
                execution_log=execution_log,
                total_steps=task_state.step_count,
                total_time=total_time,
                error_message=task_state.error_context
            )
            
            logger.info(f"📊 任务执行完成:")
            logger.info(f"   状态: {task_state.status.value}")
            logger.info(f"   步数: {task_state.step_count}/{task_state.max_steps}")
            logger.info(f"   数据: {len(task_state.extracted_data)} 条")
            logger.info(f"   耗时: {total_time:.2f}s")
            
            return task_result
            
        except Exception as e:
            logger.error(f"❌ 任务执行异常: {e}")
            execution_log.append(f"❌ 严重错误: {str(e)}")
            
            return TaskResult(
                success=False,
                task_state=task_state,
                final_data=task_state.extracted_data,
                execution_log=execution_log,
                total_steps=task_state.step_count,
                total_time=time.time() - start_time,
                error_message=str(e)
            )
    
    async def _plan_next_action(self, task_state: TaskState, browser_agent) -> Action:
        """
        规划下一步操作 - 核心决策方法
        基于当前状态和页面信息制定下一步行动计划
        """
        logger.info(f"🎯 规划第 {task_state.step_count + 1} 步操作")
        
        try:
            # 1. 获取当前页面信息
            page_info = await self._get_page_info(browser_agent)
            
            # 2. 构建规划提示
            prompt_content = self._build_planning_prompt(task_state, page_info)
            
            # 3. 调用LLM进行规划
            response = await self._call_llm(prompt_content)
            
            # 4. 解析LLM响应为Action
            action = self._parse_action_response(response, task_state)
            
            logger.info(f"📋 规划结果: {action.type.value} → {action.target or 'N/A'}")
            return action
            
        except Exception as e:
            logger.error(f"❌ 规划失败: {e}")
            # 返回默认的等待操作
            if task_state.step_count == 0:
                return ActionTemplates.navigate(task_state.target_url, "初始导航")
            else:
                return ActionTemplates.wait(2000, "规划失败，等待页面稳定")
    
    async def _get_page_info(self, browser_agent) -> Dict[str, Any]:
        """获取当前页面信息"""
        try:
            # 使用BaseBrowserLabelsAgent获取页面元素信息
            result = await browser_agent.screenshot_and_html()
            pseudo_html = result.get('pseudoHtml', '')
            
            # 获取基本页面状态
            page_state = {
                'url': getattr(browser_agent.page, 'url', '') if hasattr(browser_agent, 'page') else '',
                'title': '',
                'elements_count': len(pseudo_html.split('\n')) if pseudo_html else 0
            }
            
            if hasattr(browser_agent, 'page') and browser_agent.page:
                try:
                    page_state['title'] = await browser_agent.page.title()
                except:
                    pass
            
            return {
                'pseudo_html': pseudo_html,
                'page_state': page_state
            }
            
        except Exception as e:
            logger.warning(f"⚠️ 获取页面信息失败: {e}")
            return {
                'pseudo_html': '无法获取页面元素',
                'page_state': {'url': '', 'title': '', 'elements_count': 0}
            }
    
    def _build_planning_prompt(self, task_state: TaskState, page_info: Dict[str, Any]) -> str:
        """构建规划提示 - 基于Anthropic最佳实践"""
        
        # 基础上下文信息
        context_info = []
        
        if task_state.step_count == 0:
            context_info.append("🆕 任务刚开始，需要分析当前页面并制定策略")
        else:
            context_info.append(f"📊 已执行 {task_state.step_count} 步操作")
            context_info.append(f"📝 最近操作: {task_state.get_recent_summary()}")
        
        if task_state.current_url:
            context_info.append(f"🌐 当前页面: {page_info['page_state'].get('title', '未知')}")
            context_info.append(f"🔗 URL: {task_state.current_url}")
        
        if task_state.extracted_data:
            context_info.append(f"📦 已提取数据: {len(task_state.extracted_data)} 条")
        
        # 防止重复操作的提示
        if task_state.step_count > 3:
            context_info.append("⚠️ 注意：避免重复相同操作，尝试新的策略")
        
        # 页面元素信息
        pseudo_html = page_info.get('pseudo_html', '')
        elements_preview = pseudo_html[:1000] + "..." if len(pseudo_html) > 1000 else pseudo_html
        
        prompt_content = f"""
{chr(10).join(context_info)}

🎯 任务目标: {task_state.instruction}

📄 当前页面可交互元素:
{elements_preview}

📋 操作指南:
- navigate: 导航到新页面 (target=URL)
- click: 点击元素 (target=元素索引如"1")  
- input: 输入文本 (target=元素索引, value=文本内容) 
  * 提示：在搜索框输入后，可在value末尾加"|ENTER"直接按回车键搜索
  * 示例：{{"type": "input", "target": "1", "value": "搜索内容|ENTER"}}
- extract: 提取页面数据
- wait: 等待页面加载 (value=毫秒数)
- check_goal: 检查任务完成情况

💡 策略建议:
1. 如果是搜索任务，先找搜索框输入关键词
2. 如果需要提取数据，确保页面已加载完成
3. 复杂操作可分解为多个简单步骤
4. 根据页面响应调整后续策略

请分析当前情况并决定下一步操作。返回JSON格式:
{{
    "reasoning": "详细的分析推理过程",
    "action": {{
        "type": "操作类型",
        "target": "目标参数", 
        "value": "值参数(可选)",
        "description": "操作描述"
    }},
    "confidence": 0.9
}}
"""
        return prompt_content
    
    async def _call_llm(self, prompt_content: str) -> str:
        """调用LLM获取响应"""
        self.total_llm_calls += 1
        
        try:
            response = await self.llm.ainvoke([
                self.system_prompt.get_system_message(),
                HumanMessage(content=prompt_content)
            ])
            
            content = response.content
            logger.debug(f"🤖 LLM响应长度: {len(content)} 字符")
            
            return content
            
        except Exception as e:
            logger.error(f"❌ LLM调用失败: {e}")
            raise PlanningError(f"LLM调用失败: {e}")
    
    def _parse_action_response(self, response_content: str, task_state: TaskState) -> Action:
        """解析LLM响应为Action对象"""
        try:
            # 尝试提取JSON - 处理代码块格式
            # 先尝试提取```json代码块
            json_block_match = re.search(r'```json\s*\n(.*?)\n```', response_content, re.DOTALL)
            if json_block_match:
                json_str = json_block_match.group(1)
            else:
                # 回退到普通JSON提取
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if not json_match:
                    raise ValueError("未找到JSON格式响应")
                json_str = json_match.group()
            
            response_data = json.loads(json_str)
            
            # 验证必要字段
            if "action" not in response_data:
                raise ValueError("响应缺少action字段")
            
            action_data = response_data["action"]
            if "type" not in action_data:
                raise ValueError("action缺少type字段")
            
            # 构建Action对象
            action_type = ActionType(action_data["type"])
            action = Action(
                type=action_type,
                target=action_data.get("target"),
                value=action_data.get("value"),
                description=action_data.get("description", f"{action_type.value}操作")
            )
            
            # 记录推理过程
            reasoning = response_data.get("reasoning", "无推理信息")
            confidence = response_data.get("confidence", 0.5)
            logger.info(f"💭 推理: {reasoning[:100]}...")
            logger.info(f"📊 置信度: {confidence}")
            
            return action
            
        except Exception as e:
            logger.error(f"❌ 解析LLM响应失败: {e}")
            logger.error(f"原始响应: {response_content[:200]}...")
            
            # 返回默认操作
            if task_state.step_count == 0:
                return ActionTemplates.navigate(task_state.target_url, "解析失败，执行初始导航")
            else:
                return ActionTemplates.wait(2000, "解析失败，等待页面稳定")
    
    async def _execute_action(self, action: Action, browser_agent) -> ActionResult:
        """执行单个操作"""
        start_time = time.time()
        
        try:
            logger.info(f"⚡ 执行操作: {action.description}")
            
            # 直接使用BrowserAgent的execute_action统一接口
            result_dict = await browser_agent.execute_action(action)
            
            # 转换回ActionResult对象
            result = ActionResult(
                success=result_dict['success'],
                action=action,
                data=result_dict.get('data'),
                error=result_dict.get('error'),
                page_state=result_dict.get('page_state'),
                execution_time=result_dict.get('execution_time', time.time() - start_time)
            )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            logger.error(f"❌ 操作执行失败: {error_msg}")
            
            return ActionResult(
                success=False,
                action=action,
                error=error_msg,
                execution_time=execution_time
            )
    
    def _should_auto_complete(self, task_state: TaskState) -> bool:
        """简单的自动完成检测"""
        # 如果提取了足够的数据且是搜索任务
        if (len(task_state.extracted_data) >= 5 and 
            "搜索" in task_state.instruction and
            task_state.step_count > 3):
            return True
        
        # 如果当前在搜索结果页面且已经执行了多个步骤
        if ("search" in task_state.current_url.lower() or 
            "result" in task_state.current_url.lower()) and task_state.step_count > 5:
            return True
        
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_llm_calls": self.total_llm_calls,
            "total_tokens_used": self.total_tokens_used
        }