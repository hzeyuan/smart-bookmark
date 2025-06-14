"""
核心编排器 - 基于ReAct模式的智能网页自动化系统
"""
import os
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from .browser import BrowserCore
from .prompts import SystemPrompt, AgentStatePrompt, PlannerPrompt, DataExtractionPrompt

logger = logging.getLogger(__name__)


@dataclass
class WebContext:
    """共享的网页上下文 - 单步循环模式"""
    url: str
    instruction: str
    goal_achieved: bool = False
    current_page_state: Dict[str, Any] = None  # 当前页面状态快照
    step_count: int = 0
    max_steps: int = 15
    last_action: Optional[Dict] = None
    last_result: Optional[Dict] = None
    extracted_data: List[Dict[str, Any]] = None
    execution_log: List[str] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.extracted_data is None:
            self.extracted_data = []
        if self.execution_log is None:
            self.execution_log = []
        if self.current_page_state is None:
            self.current_page_state = {}


class CoreAgent:
    """核心智能体 - 所有智能体的基类"""
    
    def __init__(self, role: str, temperature: float = 0):
        self.role = role
        self.llm = ChatOpenAI(
            model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-sonnet-20240229"),
            temperature=temperature,
            openai_api_base="https://openrouter.ai/api/v1",
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            default_headers={
                # "HTTP-Referer": os.getenv("HTTP_REFERER", "https://smart-bookmark.com"),
                # "X-Title": os.getenv("X_TITLE", "Smart Bookmark Crawler")
            }
        )
    
    async def process(self, context: WebContext) -> WebContext:
        """处理上下文，子类实现具体逻辑"""
        raise NotImplementedError


class Planner(CoreAgent):
    """规划者 - 基于专业提示词的单步规划"""
    
    def __init__(self):
        super().__init__("planner")
        self.system_prompt = SystemPrompt()
    
    async def plan_next_step(self, context: WebContext) -> Dict[str, Any]:
        """单步规划 - 使用专业提示词系统"""
        logger.info(f"🎯 Planner: 规划第 {context.step_count + 1} 步")
        
        # 使用新的提示词系统
        state_prompt = AgentStatePrompt(context)
        
        response = await self.llm.ainvoke([
            self.system_prompt.get_system_message(),
            state_prompt.get_user_message()
        ])
        
        # 解析 ReAct 格式的响应
        import json
        import re
        try:
            content = response.content
            logger.info(f"🤖 LLM推理: {content[:200]}...")
            
            # 提取 Thought
            thought_match = re.search(r'Thought:\s*(.*?)(?=Action:|$)', content, re.DOTALL)
            if thought_match:
                thought = thought_match.group(1).strip()
                logger.info(f"💭 Thought: {thought}")
            
            # 提取 Action
            json_match = re.search(r'Action:\s*(\{.*?\})', content, re.DOTALL)
            if json_match:
                action = json.loads(json_match.group(1))
                logger.info(f"📋 Action: {action['type']} {action.get('target', '')}")
                return action
            else:
                # 如果没找到标准格式，尝试直接解析JSON
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    action = json.loads(json_match.group())
                    return action
                else:
                    raise ValueError("无法解析操作")
        except Exception as e:
            logger.error(f"❌ 规划失败: {e}")
            # 根据步数返回合理的默认操作
            if context.step_count == 0:
                return {"type": "navigate", "target": context.url}
            else:
                return {"type": "wait", "ms": 1000}
    
    def _build_context_prompt(self, context: WebContext) -> str:
        """构建上下文提示"""
        info = []
        
        if context.step_count == 0:
            info.append("🆕 任务刚开始，尚未执行任何操作")
        else:
            info.append(f"📊 已执行 {context.step_count} 步操作")
        
        if context.last_action:
            info.append(f"🔄 上一步操作: {context.last_action['type']} {context.last_action.get('target', '')}")
        
        if context.last_result:
            success = context.last_result.get('success', True)
            status = "✅ 成功" if success else "❌ 失败"
            info.append(f"🎯 上一步结果: {status}")
        
        if context.current_page_state:
            url = context.current_page_state.get('url', '未知')
            title = context.current_page_state.get('title', '未知')
            info.append(f"🌐 当前页面: {title}")
            info.append(f"🔗 URL: {url}")
            
            # 重要：检查重复操作
            recent_actions = [log for log in context.execution_log[-3:]]
            if recent_actions:
                info.append(f"📝 最近操作: {', '.join(recent_actions)}")
        
        # 防止重复循环的提示
        if context.step_count > 3:
            info.append("⚠️ 注意：避免重复相同操作，尝试新的策略")
        
        return "\n".join(info)


class Executor(CoreAgent):
    """执行者 - 单步执行模式"""
    
    def __init__(self):
        super().__init__("executor")
        self.browser = BrowserCore()
    
    async def observe_page_state(self, context: WebContext):
        """观察当前页面状态"""
        if not self.browser.page:
            return
        
        try:
            state = {
                "url": self.browser.page.url,
                "title": await self.browser.page.title(),
                "timestamp": __import__("time").time()
            }
            
            # 简单的页面元素扫描
            search_elements = await self.browser.page.query_selector_all("input[type='search'], input[placeholder*='搜索'], .search")
            state["has_search"] = len(search_elements) > 0
            
            video_elements = await self.browser.page.query_selector_all(".video, .bili-video-card, [href*='/video/']")
            state["video_count"] = len(video_elements)
            
            context.current_page_state = state
            logger.info(f"📊 页面状态: {state['title']} | 搜索框: {state['has_search']} | 视频: {state['video_count']}")
            
        except Exception as e:
            logger.warning(f"⚠️ 页面状态观察失败: {e}")
    
    async def execute_single_action(self, action: Dict[str, Any], context: WebContext) -> Dict[str, Any]:
        """执行单个操作并返回结果"""
        logger.info(f"⚡ 执行第 {context.step_count + 1} 步: {action['type']} {action.get('target', '')}")
        
        result = await self._execute_mcp_action(action)
        
        # 执行后立即观察页面状态
        await self.observe_page_state(context)
        
        # 更新上下文
        context.last_action = action
        context.last_result = result
        context.step_count += 1
        
        # 记录日志
        success = result.get('success', True)
        status = "✅" if success else "❌"
        context.execution_log.append(f"{status} 步骤 {context.step_count}: {action['type']}")
        
        return result
    
    async def process(self, context: WebContext) -> WebContext:
        logger.info(f"⚡ Executor: 执行操作计划")
        
        plan = context.current_state.get("plan", [])
        if not plan:
            context.error = "没有执行计划"
            return context
        
        results = []
        for i, action in enumerate(plan):
            logger.info(f"   步骤 {i+1}: {action['type']} {action.get('target', '')}")
            
            try:
                # 模拟MCP执行 - 实际项目中连接真实MCP服务器
                result = await self._execute_mcp_action(action)
                results.append({
                    "step": i + 1,
                    "action": action,
                    "result": result,
                    "success": True
                })
                context.execution_log.append(f"✅ 步骤 {i+1} 成功")
            except Exception as e:
                results.append({
                    "step": i + 1,
                    "action": action,
                    "error": str(e),
                    "success": False
                })
                context.execution_log.append(f"❌ 步骤 {i+1} 失败: {e}")
        
        context.current_state["execution_results"] = results
        success_count = sum(1 for r in results if r["success"])
        context.execution_log.append(f"📊 执行完成: {success_count}/{len(results)} 成功")
        
        return context
    
    async def _execute_mcp_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个MCP操作 - 使用增强的BrowserCore"""
        action_type = action["type"]
        
        # 确保浏览器已启动
        if not self.browser.page:
            await self.browser.start(headless=False)
            logger.info("🌐 浏览器已启动")
        
        try:
            if action_type == "navigate":
                result = await self.browser.navigate_to(action["target"])
                logger.info(f"🔗 已导航到: {result['url']}")
                return {"status": "navigated", **result}
                
            elif action_type == "wait":
                ms = action.get("ms", 2000)
                await self.browser.page.wait_for_timeout(ms)
                logger.info(f"⏳ 等待 {ms}ms")
                return {"status": "waited", "ms": ms}
                
            elif action_type == "click":
                target = action["target"]
                # 智能选择器列表
                selectors = [
                    f".{target}",
                    f"#{target}",
                    f"[class*='{target}']",
                    f"[data-v-*='{target}']",
                    f"[placeholder*='搜索']",
                    "input[class*='search']",
                    ".nav-search-input",
                    ".nav-search-btn"
                ]
                
                success = await self.browser.smart_click(selectors)
                return {"status": "clicked", "element": target, "success": success}
                
            elif action_type == "type":
                target = action["target"] 
                value = action.get("value", "Python教程")
                
                # 智能输入框选择器
                selectors = [
                    f".{target}",
                    f"#{target}",
                    f"[class*='{target}']",
                    "input[class*='search']",
                    "input[placeholder*='搜索']",
                    ".nav-search-input",
                    "#nav-searchform-compl"
                ]
                
                success = await self.browser.smart_input(selectors, value)
                return {"status": "typed", "text": value, "success": success}
                
            elif action_type == "extract":
                # 等待页面加载
                await self.browser.page.wait_for_timeout(3000)
                
                # 尝试提取数据
                videos = await self._extract_videos()
                logger.info(f"📊 成功提取 {len(videos)} 个视频")
                return {"status": "extracted", "data": videos, "success": len(videos) > 0}
                
            elif action_type == "check_goal":
                # 检查目标是否达成
                goal_achieved = await self._check_goal_completion(context)
                return {"status": "goal_check", "goal_achieved": goal_achieved, "success": True}
            
            else:
                return {"status": "completed", "success": True}
                
        except Exception as e:
            logger.error(f"❌ 操作失败 {action_type}: {e}")
            return {"status": "error", "error": str(e), "success": False}
    
    async def _extract_videos(self) -> List[Dict]:
        """提取视频数据"""
        try:
            videos = []
            
            # B站搜索结果选择器
            video_selectors = [
                ".video-item",
                ".bili-video-card", 
                ".card-box",
                ".video-card"
            ]
            
            for selector in video_selectors:
                elements = await self.browser.page.query_selector_all(selector)
                if elements:
                    logger.info(f"📹 找到 {len(elements)} 个视频元素: {selector}")
                    
                    for i, element in enumerate(elements[:5]):  # 限制前5个
                        try:
                            title_elem = await element.query_selector(".title, .video-name, h3, a")
                            title = await title_elem.inner_text() if title_elem else f"视频{i+1}"
                            
                            link_elem = await element.query_selector("a")
                            href = await link_elem.get_attribute("href") if link_elem else ""
                            
                            if href and not href.startswith("http"):
                                href = f"https://www.bilibili.com{href}"
                            
                            videos.append({
                                "title": title.strip(),
                                "url": href,
                                "description": f"B站视频 - {title}"
                            })
                        except:
                            continue
                    break
            
            if not videos:
                # 如果没找到，尝试通用方法
                links = await self.browser.page.query_selector_all("a[href*='/video/']")
                for i, link in enumerate(links[:5]):
                    try:
                        title = await link.inner_text()
                        href = await link.get_attribute("href")
                        if title and href:
                            videos.append({
                                "title": title.strip(),
                                "url": f"https://www.bilibili.com{href}" if not href.startswith("http") else href,
                                "description": f"B站视频 - {title}"
                            })
                    except:
                        continue
            
            return videos
                    
        except Exception as e:
            logger.error(f"❌ 提取失败: {e}")
            return []
    
    async def _check_goal_completion(self, context: WebContext) -> bool:
        """检查目标是否完成"""
        # 简单的目标检测逻辑
        if "搜索" in context.instruction and "视频" in context.instruction:
            # 检查是否在搜索结果页面且有视频
            state = context.current_page_state
            if state and state.get("video_count", 0) > 0:
                url = state.get("url", "")
                if "search" in url.lower() or "搜索" in url:
                    return True
        
        return False


class Extractor(CoreAgent):
    """提取者 - 从执行结果中提取结构化数据"""
    
    def __init__(self):
        super().__init__("extractor")
    
    async def process(self, context: WebContext) -> WebContext:
        logger.info(f"📊 Extractor: 优化提取数据")
        
        # 使用新的context结构
        if not context.extracted_data:
            context.execution_log.append("⚠️ 未找到可提取的数据")
            return context
        
        # 使用LLM优化和结构化数据
        prompt = f"""
        原始任务: {context.instruction}
        
        提取到的原始数据:
        {raw_data}
        
        请将数据优化为用户需要的格式，返回JSON数组：
        [{{"title": "标题", "url": "链接", "description": "描述"}}]
        """
        
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="你是数据结构化专家，将原始数据转换为清晰的JSON格式。"),
                HumanMessage(content=prompt)
            ])
            
            import json
            import re
            json_match = re.search(r'\[.*\]', response.content, re.DOTALL)
            if json_match:
                structured_data = json.loads(json_match.group())
                context.extracted_data.extend(structured_data)
                context.execution_log.append(f"✅ 结构化了 {len(structured_data)} 条数据")
            else:
                # 回退到原始数据
                context.extracted_data.extend(raw_data)
                context.execution_log.append(f"⚠️ 使用原始数据 {len(raw_data)} 条")
                
        except Exception as e:
            context.extracted_data.extend(raw_data)
            context.execution_log.append(f"⚠️ 结构化失败，使用原始数据: {e}")
        
        return context


class WebOrchestrator:
    """Web编排器 - 智能循环重试协调系统"""
    
    def __init__(self):
        self.planner = Planner()
        self.executor = Executor()
        self.extractor = Extractor()
        self.workflow = self._build_workflow()
        # 重试配置
        self.max_iterations = 3
        self.min_success_rate = 0.6  # 至少60%操作成功才继续
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """关闭浏览器"""
        if self.executor.browser:
            await self.executor.browser.close()
    
    def _build_workflow(self) -> StateGraph:
        """构建简洁的工作流"""
        
        def plan_step(context: WebContext) -> WebContext:
            return asyncio.create_task(self.planner.process(context))
        
        def execute_step(context: WebContext) -> WebContext:
            return asyncio.create_task(self.executor.process(context))
        
        def extract_step(context: WebContext) -> WebContext:
            return asyncio.create_task(self.extractor.process(context))
        
        workflow = StateGraph(WebContext)
        
        # 3个核心节点
        workflow.add_node("plan", plan_step)
        workflow.add_node("execute", execute_step)
        workflow.add_node("extract", extract_step)
        
        # 线性流程
        workflow.set_entry_point("plan")
        workflow.add_edge("plan", "execute")
        workflow.add_edge("execute", "extract")
        workflow.add_edge("extract", END)
        
        return workflow
    
    async def run(self, instruction: str, url: str) -> Dict[str, Any]:
        """运行单步循环智能体协作流程"""
        logger.info(f"🚀 开始单步循环执行: {instruction}")
        
        # 初始化上下文
        context = WebContext(
            url=url,
            instruction=instruction
        )
        
        try:
            # 🔄 主循环：单步规划-执行-检查
            while context.step_count < context.max_steps and not context.goal_achieved:
                
                # 1️⃣ 规划下一步
                next_action = await self.planner.plan_next_step(context)
                
                # 2️⃣ 执行单步操作  
                result = await self.executor.execute_single_action(next_action, context)
                
                # 3️⃣ 检查特殊操作结果
                if next_action["type"] == "extract" and result.get("success"):
                    # 提取成功，收集数据
                    extracted_data = result.get("data", [])
                    context.extracted_data.extend(extracted_data)
                    logger.info(f"📦 累计提取 {len(context.extracted_data)} 条数据")
                
                if next_action["type"] == "check_goal":
                    # 目标检查
                    context.goal_achieved = result.get("goal_achieved", False)
                    if context.goal_achieved:
                        logger.info("🎯 目标已达成！")
                        break
                
                # 4️⃣ 错误处理
                if not result.get("success", True):
                    logger.warning(f"⚠️ 第 {context.step_count} 步执行失败，继续尝试...")
                    if context.step_count > 5:  # 防止无限循环
                        logger.error("❌ 连续失败过多，终止执行")
                        break
                
                # 5️⃣ 简单的自动目标检测
                if (context.step_count > 3 and 
                    len(context.extracted_data) >= 5 and 
                    "搜索" in instruction):
                    logger.info("🎯 检测到足够数据，自动完成任务")
                    context.goal_achieved = True
                    break
            
            # 🏁 最终数据优化 (暂时跳过，数据已足够好)
            # if context.extracted_data:
            #     context = await self.extractor.process(context)
            
            # 输出执行总结
            logger.info(f"✅ 循环执行完成:")
            logger.info(f"   📊 总步数: {context.step_count}")
            logger.info(f"   🎯 目标达成: {context.goal_achieved}")
            logger.info(f"   📦 数据条数: {len(context.extracted_data)}")
            
            return {
                "success": True,
                "data": context.extracted_data,
                "execution_log": context.execution_log,
                "steps_taken": context.step_count,
                "goal_achieved": context.goal_achieved,
                "error": context.error
            }
            
        except Exception as e:
            logger.error(f"❌ 循环执行失败: {e}")
            return {
                "success": False,
                "data": context.extracted_data,
                "execution_log": context.execution_log,
                "steps_taken": context.step_count,
                "goal_achieved": False,
                "error": str(e)
            }
        finally:
            # 关闭浏览器
            await self.close()