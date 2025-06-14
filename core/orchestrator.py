"""
核心编排器 - 基于ReAct模式的智能网页自动化系统
"""
import os
import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from .browser import BrowserCore
from .prompts import SystemPrompt
from .visual_agent import VisualPageAnalyzer, MultimodalPromptBuilder

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
    """规划者 - 基于视觉多模态的单步规划"""
    
    def __init__(self, task_id: str = None):
        super().__init__("planner")
        self.system_prompt = SystemPrompt()
        self.visual_analyzer = VisualPageAnalyzer(task_id)
    
    async def plan_next_step(self, context: WebContext, page) -> Dict[str, Any]:
        """单步规划 - 使用视觉+文本多模态分析"""
        logger.info(f"🎯 Planner: 视觉分析第 {context.step_count + 1} 步")
        
        # 1. 视觉页面分析
        analysis_context = {
            'step_count': context.step_count,
            'last_action': context.last_action,
            'instruction': context.instruction,
            'extracted_data': context.extracted_data
        }
        screenshot_base64, interactive_elements = await self.visual_analyzer.analyze_page(page, analysis_context)
        
        # 2. 构建多模态提示
        context_info = {
            'step_count': context.step_count,
            'last_action': context.last_action,
            'page_url': page.url,
            'extracted_data': context.extracted_data
        }
        
        visual_prompt = MultimodalPromptBuilder.build_visual_prompt(
            screenshot_base64,
            interactive_elements,
            context.instruction,
            context_info
        )
        
        # 3. 发送多模态请求
        response = await self.llm.ainvoke([
            self.system_prompt.get_system_message(),
            visual_prompt
        ])
        
        # 4. 保存元素信息到上下文（供执行器使用）
        context.current_page_state['interactive_elements'] = {
            elem.element_id: {
                'selector': elem.selector,
                'bounds': elem.bounds,
                'role': elem.role,
                'text': elem.text
            } for elem in interactive_elements
        }
        
        # 解析结构化JSON响应
        import json
        import re
        try:
            content = response.content
            logger.info(f"🤖 LLM响应: {content[:100]}...")
            
            # 尝试直接解析JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                structured_response = json.loads(json_match.group())
                
                # 验证必要字段
                if "action" in structured_response and "type" in structured_response["action"]:
                    action = structured_response["action"]
                    reasoning = structured_response.get("reasoning", "无推理信息")
                    confidence = structured_response.get("confidence", 0.5)
                    
                    logger.info(f"💭 推理: {reasoning[:100]}...")
                    logger.info(f"📋 操作: {action['type']} → {action.get('target', '')} (置信度: {confidence})")
                    
                    return action
                else:
                    raise ValueError("响应缺少必要的action字段")
            else:
                raise ValueError("无法找到JSON格式的响应")
                
        except Exception as e:
            logger.error(f"❌ 解析响应失败: {e}")
            logger.error(f"原始响应: {content}")
            
            # 根据步数返回合理的默认操作
            if context.step_count == 0:
                return {"type": "navigate", "target": context.url, "description": "初始导航"}
            else:
                return {"type": "wait", "ms": 2000, "description": "等待页面稳定"}
    
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
        
        result = await self._execute_mcp_action(action, context)
        
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
    
    async def _execute_mcp_action(self, action: Dict[str, Any], context: WebContext = None) -> Dict[str, Any]:
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
                
                # 优先使用视觉分析的元素信息
                interactive_elements = context.current_page_state.get('interactive_elements', {}) if context else {}
                if target in interactive_elements:
                    element_info = interactive_elements[target]
                    # 使用精确的位置点击
                    bounds = element_info['bounds']
                    x = bounds['x'] + bounds['width'] / 2
                    y = bounds['y'] + bounds['height'] / 2
                    
                    await self.browser.page.mouse.click(x, y)
                    logger.info(f"🎯 精确点击元素: {target} at ({x}, {y})")
                    return {"status": "clicked", "element": target, "success": True}
                else:
                    # 回退到传统选择器方式
                    selectors = [
                        f".{target}",
                        f"#{target}",
                        f"[class*='{target}']",
                        "input[class*='search']",
                        ".nav-search-input",
                        ".nav-search-btn"
                    ]
                    success = await self.browser.smart_click(selectors)
                    return {"status": "clicked", "element": target, "success": success}
                
            elif action_type == "type":
                target = action["target"] 
                value = action.get("value", "Python教程")
                
                # 优先使用视觉分析的元素信息
                interactive_elements = context.current_page_state.get('interactive_elements', {}) if context else {}
                if target in interactive_elements:
                    element_info = interactive_elements[target]
                    # 使用精确的位置点击然后输入
                    bounds = element_info['bounds']
                    x = bounds['x'] + bounds['width'] / 2
                    y = bounds['y'] + bounds['height'] / 2
                    
                    await self.browser.page.mouse.click(x, y)
                    await self.browser.page.keyboard.type(value)
                    logger.info(f"🎯 精确输入到元素: {target} - '{value}'")
                    return {"status": "typed", "text": value, "success": True}
                else:
                    # 回退到传统选择器方式
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
                
                # 根据页面类型选择提取方法
                current_url = self.browser.page.url
                if "bilibili.com" in current_url:
                    data = await self._extract_videos()
                    data_type = "视频"
                elif "google.com" in current_url:
                    data = await self._extract_search_results()
                    data_type = "搜索结果"
                elif "github.com" in current_url:
                    data = await self._extract_github_repos()
                    data_type = "代码仓库"
                else:
                    data = await self._extract_generic_links()
                    data_type = "链接"
                
                logger.info(f"📊 成功提取 {len(data)} 个{data_type}")
                return {"status": "extracted", "data": data, "success": len(data) > 0}
                
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
    
    async def _extract_search_results(self) -> List[Dict]:
        """提取Google搜索结果"""
        try:
            results = []
            
            # Google搜索结果选择器
            result_selectors = [
                "[data-sokoban-container] h3",  # 新版Google
                ".g h3",                        # 标准结果
                ".rc h3",                       # 传统结果
                "h3"                           # 通用H3标题
            ]
            
            for selector in result_selectors:
                elements = await self.browser.page.query_selector_all(selector)
                if elements:
                    logger.info(f"🔍 找到 {len(elements)} 个搜索结果: {selector}")
                    
                    for i, element in enumerate(elements[:3]):  # 限制前3个
                        try:
                            # 获取标题
                            title = await element.inner_text()
                            if not title or len(title.strip()) < 5:
                                continue
                                
                            # 查找父级容器中的链接
                            parent = element
                            link_elem = None
                            for _ in range(3):  # 向上查找3级
                                parent = await parent.query_selector("xpath=..")
                                if not parent:
                                    break
                                link_elem = await parent.query_selector("a[href]")
                                if link_elem:
                                    break
                            
                            # 如果在父级没找到，尝试兄弟元素
                            if not link_elem:
                                link_elem = await element.query_selector("xpath=../a") or await element.query_selector("xpath=../../a")
                            
                            href = ""
                            if link_elem:
                                href = await link_elem.get_attribute("href")
                            
                            # 查找描述信息
                            description = ""
                            try:
                                desc_parent = element
                                for _ in range(3):
                                    desc_parent = await desc_parent.query_selector("xpath=..")
                                    if not desc_parent:
                                        break
                                    desc_elem = await desc_parent.query_selector("[data-sncf], .s, .st")
                                    if desc_elem:
                                        description = await desc_elem.inner_text()
                                        break
                            except:
                                pass
                            
                            if title and title.strip():
                                results.append({
                                    "title": title.strip()[:200],  # 限制长度
                                    "url": href if href and href.startswith("http") else "",
                                    "description": description.strip()[:300] if description else title.strip()
                                })
                        except Exception as e:
                            logger.debug(f"提取单个结果失败: {e}")
                            continue
                    
                    if results:  # 找到结果就停止
                        break
            
            # 如果上述方法都没找到，使用更通用的方法
            if not results:
                logger.info("🔍 使用通用方法提取搜索结果")
                links = await self.browser.page.query_selector_all("a[href*='http']:not([href*='google.com'])")
                for i, link in enumerate(links[:3]):
                    try:
                        title = await link.inner_text()
                        href = await link.get_attribute("href")
                        if title and href and len(title.strip()) > 5:
                            results.append({
                                "title": title.strip()[:200],
                                "url": href,
                                "description": f"搜索结果 - {title.strip()}"
                            })
                    except:
                        continue
            
            return results
                    
        except Exception as e:
            logger.error(f"❌ Google搜索结果提取失败: {e}")
            return []
    
    async def _extract_github_repos(self) -> List[Dict]:
        """提取GitHub仓库信息"""
        try:
            repos = []
            
            # GitHub仓库选择器
            repo_selectors = [
                "[data-testid='results-list'] article",
                ".repo-list-item",
                ".Box-row"
            ]
            
            for selector in repo_selectors:
                elements = await self.browser.page.query_selector_all(selector)
                if elements:
                    logger.info(f"📁 找到 {len(elements)} 个仓库: {selector}")
                    
                    for i, element in enumerate(elements[:5]):
                        try:
                            title_elem = await element.query_selector("h3 a, .f4 a")
                            title = await title_elem.inner_text() if title_elem else f"项目{i+1}"
                            
                            link_elem = await element.query_selector("h3 a, .f4 a")
                            href = await link_elem.get_attribute("href") if link_elem else ""
                            
                            if href and not href.startswith("http"):
                                href = f"https://github.com{href}"
                            
                            # 获取描述
                            desc_elem = await element.query_selector("p, .color-fg-muted")
                            description = await desc_elem.inner_text() if desc_elem else ""
                            
                            repos.append({
                                "title": title.strip(),
                                "url": href,
                                "description": description.strip() if description else f"GitHub项目 - {title}"
                            })
                        except:
                            continue
                    break
            
            return repos
                    
        except Exception as e:
            logger.error(f"❌ GitHub仓库提取失败: {e}")
            return []
    
    async def _extract_generic_links(self) -> List[Dict]:
        """提取通用链接"""
        try:
            links = []
            elements = await self.browser.page.query_selector_all("a[href]:not([href*='google.com']):not([href*='javascript'])")
            
            for i, element in enumerate(elements[:5]):
                try:
                    title = await element.inner_text()
                    href = await element.get_attribute("href")
                    
                    if title and href and len(title.strip()) > 3:
                        links.append({
                            "title": title.strip()[:200],
                            "url": href if href.startswith("http") else f"https://{href}",
                            "description": f"链接 - {title.strip()}"
                        })
                except:
                    continue
            
            return links
                    
        except Exception as e:
            logger.error(f"❌ 通用链接提取失败: {e}")
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
        
        # 检查是否有提取的数据
        if not context.extracted_data:
            context.execution_log.append("⚠️ 未找到可提取的数据")
            return context
        
        # 获取原始数据
        raw_data = context.extracted_data
        
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
                context.extracted_data = structured_data  # 替换而不是扩展
                context.execution_log.append(f"✅ 结构化了 {len(structured_data)} 条数据")
            else:
                # 保持原始数据不变
                context.execution_log.append(f"⚠️ 使用原始数据 {len(raw_data)} 条")
                
        except Exception as e:
            # 保持原始数据不变
            context.execution_log.append(f"⚠️ 结构化失败，使用原始数据: {e}")
        
        return context


class WebOrchestrator:
    """Web编排器 - 智能循环重试协调系统"""
    
    def __init__(self, task_id: str = None):
        self.task_id = task_id or f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.planner = Planner(self.task_id)
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
                
                # 确保浏览器已启动
                if not self.executor.browser.page:
                    await self.executor.browser.start(headless=False)
                    await self.executor.browser.navigate_to(context.url)
                
                # 1️⃣ 视觉分析并规划下一步
                next_action = await self.planner.plan_next_step(context, self.executor.browser.page)
                
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