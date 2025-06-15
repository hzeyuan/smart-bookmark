"""
BaseBrowserLabelsAgent - 复刻 eko 的核心浏览器标签代理
"""
import logging
import time
from typing import Dict, Any, List, Optional
from .browser_agent import BrowserAgent

logger = logging.getLogger(__name__)


class BaseBrowserLabelsAgent(BrowserAgent):
    """基础浏览器标签代理 - 复刻 eko 的完整实现"""
    
    def __init__(self):
        super().__init__()
        self._scripts_injected = False
    
    @property
    def page(self):
        """页面属性 - 兼容性访问器"""
        return self.current_page
        
    async def input_text(self, index: int, text: str, enter: bool = False):
        """输入文本 - 使用 JavaScript 实现"""
        await self.execute_script("""
            (params) => {
                return window.typing(params);
            }
        """, [{"index": index, "text": text, "enter": enter}])
        
        if enter:
            await self.sleep(200)
            
    async def click_element(self, index: int, num_clicks: int = 1, button: str = "left"):
        """点击元素 - 使用 JavaScript 实现"""
        await self.execute_script("""
            (params) => {
                return window.do_click(params);
            }
        """, [{"index": index, "button": button, "num_clicks": num_clicks}])
        
    async def scroll_to_element(self, index: int):
        """滚动到元素"""
        await self.execute_script("""
            (index) => {
                return window.get_highlight_element(index)
                    .scrollIntoView({ behavior: "smooth" });
            }
        """, [index])
        await self.sleep(200)
        
    async def scroll_mouse_wheel(self, amount: int):
        """滚动鼠标滚轮"""
        await self.execute_script("""
            (params) => {
                return window.scroll_by(params);
            }
        """, [{"amount": amount}])
        await self.sleep(200)
        
    async def hover_to_element(self, index: int):
        """悬停到元素"""
        await self.execute_script("""
            (params) => {
                return window.hover_to(params);
            }
        """, [{"index": index}])
        
    async def get_select_options(self, index: int):
        """获取下拉框选项"""
        return await self.execute_script("""
            (params) => {
                return window.get_select_options(params);
            }
        """, [{"index": index}])
        
    async def select_option(self, index: int, option: str):
        """选择下拉框选项"""
        return await self.execute_script("""
            (params) => {
                return window.select_option(params);
            }
        """, [{"index": index, "option": option}])
        
    async def screenshot_and_html(self) -> Dict[str, Any]:
        """
        获取截图和HTML - 复刻 eko 的核心方法
        这是 BaseBrowserLabelsAgent 的核心功能
        """
        try:
            # 确保脚本已注入
            await self._ensure_scripts_injected()
            
            element_result = None
            
            # 尝试5次获取元素（复刻 eko 的重试逻辑）
            for i in range(5):
                await self.sleep(200)
                
                # 执行 DOM 树构建
                await self.execute_script("window.run_build_dom_tree", [])
                await self.sleep(50)
                
                # 获取可点击元素
                element_result = await self.execute_script("""
                    () => {
                        return window.get_clickable_elements(true);
                    }
                """)
                
                if element_result:
                    break
                    
            await self.sleep(100)
            
            # 获取截图
            screenshot = await self.screenshot()
            
            # 提取 pseudoHtml
            pseudo_html = element_result.get('element_str', '') if element_result else ''
            
            return {
                "imageBase64": screenshot["imageBase64"],
                "imageType": screenshot["imageType"],
                "pseudoHtml": pseudo_html,
            }
            
        finally:
            # 清理高亮标记
            try:
                await self.execute_script("""
                    () => {
                        return window.remove_highlight();
                    }
                """)
            except Exception:
                pass
                
    async def get_clickable_elements(self, with_highlight: bool = True) -> Dict[str, Any]:
        """获取可点击元素"""
        # 确保脚本已注入
        await self._ensure_scripts_injected()
        
        return await self.execute_script("""
            (with_highlight) => {
                return window.get_clickable_elements(with_highlight);
            }
        """, [with_highlight])
        
    def get_element_script(self, index: int) -> str:
        """生成获取元素的脚本"""
        return f"window.get_highlight_element({index});"
        
    async def _ensure_scripts_injected(self):
        """确保脚本已注入"""
        if not self._scripts_injected:
            await self.inject_dom_scripts()
            self._scripts_injected = True
        
    async def inject_dom_scripts(self):
        """注入所有必要的DOM脚本"""
        
        # 首先注入 run_build_dom_tree 函数
        await self.inject_build_dom_tree()
        
        # 注入所有交互函数
        await self.inject_interaction_functions()
        
        # 注入主要的DOM工具函数
        await self.inject_main_dom_functions()
        
    async def inject_build_dom_tree(self):
        """注入 run_build_dom_tree 函数"""
        script = """
            window.run_build_dom_tree = function() {
                console.log('🌳 构建DOM树...');
                // 这里应该是构建DOM树的逻辑
                // 目前简化实现，主要确保函数存在
                return true;
            };
        """
        await self.execute_script(script)
        
    async def inject_interaction_functions(self):
        """注入所有交互函数"""
        script = """
            // typing 函数
            window.typing = function(params) {
                let { index, text, enter } = params;
                let element = window.get_highlight_element(index);
                if (!element) {
                    return false;
                }
                
                let input;
                if (element.tagName == "IFRAME") {
                    let iframeDoc = element.contentDocument || element.contentWindow.document;
                    input = iframeDoc.querySelector("textarea") ||
                           iframeDoc.querySelector('*[contenteditable="true"]') ||
                           iframeDoc.querySelector("input");
                } else if (
                    element.tagName == "INPUT" ||
                    element.tagName == "TEXTAREA" ||
                    element.childElementCount == 0
                ) {
                    input = element;
                } else {
                    input = element.querySelector("input") || element.querySelector("textarea");
                    if (!input) {
                        input = element.querySelector('*[contenteditable="true"]') || element;
                        if (input.tagName == "DIV") {
                            input = input.querySelector("span") || input.querySelector("div") || input;
                        }
                    }
                }
                
                input.focus && input.focus();
                
                if (!text && enter) {
                    ["keydown", "keypress", "keyup"].forEach((eventType) => {
                        const event = new KeyboardEvent(eventType, {
                            key: "Enter",
                            code: "Enter", 
                            keyCode: 13,
                            bubbles: true,
                            cancelable: true,
                        });
                        input.dispatchEvent(event);
                    });
                    return true;
                }
                
                if (input.value == undefined) {
                    input.textContent = text;
                } else {
                    input.value = text;
                    if (input.__proto__) {
                        let value_setter = Object.getOwnPropertyDescriptor(
                            input.__proto__,
                            "value"
                        )?.set;
                        value_setter && value_setter.call(input, text);
                    }
                }
                
                input.dispatchEvent(new Event("input", { bubbles: true }));
                
                if (enter) {
                    ["keydown", "keypress", "keyup"].forEach((eventType) => {
                        const event = new KeyboardEvent(eventType, {
                            key: "Enter",
                            code: "Enter",
                            keyCode: 13,
                            bubbles: true,
                            cancelable: true,
                        });
                        input.dispatchEvent(event);
                    });
                }
                
                return true;
            };
            
            // do_click 函数
            window.do_click = function(params) {
                let { index, button, num_clicks } = params;
                
                function simulateMouseEvent(eventTypes, buttonCode) {
                    let element = window.get_highlight_element(index);
                    if (!element) {
                        return false;
                    }
                    
                    for (let n = 0; n < num_clicks; n++) {
                        for (let eventType of eventTypes) {
                            const event = new MouseEvent(eventType, {
                                view: window,
                                bubbles: true,
                                cancelable: true,
                                button: buttonCode,
                            });
                            element.dispatchEvent(event);
                        }
                    }
                    return true;
                }
                
                if (button == "right") {
                    return simulateMouseEvent(["mousedown", "mouseup", "contextmenu"], 2);
                } else if (button == "middle") {
                    return simulateMouseEvent(["mousedown", "mouseup", "click"], 1);
                } else {
                    return simulateMouseEvent(["mousedown", "mouseup", "click"], 0);
                }
            };
            
            // hover_to 函数
            window.hover_to = function(params) {
                let element = window.get_highlight_element(params.index);
                if (!element) {
                    return false;
                }
                
                const event = new MouseEvent("mouseenter", {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                });
                element.dispatchEvent(event);
                
                return true;
            };
            
            // get_select_options 函数
            window.get_select_options = function(params) {
                let element = window.get_highlight_element(params.index);
                if (!element || element.tagName.toUpperCase() !== "SELECT") {
                    return "Error: Not a select element";
                }
                
                return {
                    options: Array.from(element.options).map((opt) => ({
                        index: opt.index,
                        text: opt.text.trim(),
                        value: opt.value,
                    })),
                    name: element.name,
                };
            };
            
            // select_option 函数
            window.select_option = function(params) {
                let element = window.get_highlight_element(params.index);
                if (!element || element.tagName.toUpperCase() !== "SELECT") {
                    return "Error: Not a select element";
                }
                
                let text = params.option.trim();
                let option = Array.from(element.options).find(
                    (opt) => opt.text.trim() === text
                );
                
                if (!option) {
                    option = Array.from(element.options).find(
                        (opt) => opt.value.trim() === text
                    );
                }
                
                if (!option) {
                    return {
                        success: false,
                        error: "Select Option not found",
                        availableOptions: Array.from(element.options).map((o) =>
                            o.text.trim()
                        ),
                    };
                }
                
                element.value = option.value;
                element.dispatchEvent(new Event("change"));
                
                return {
                    success: true,
                    selectedValue: option.value,
                    selectedText: option.text.trim(),
                };
            };
            
            // scroll_by 函数
            window.scroll_by = function(params) {
                if (!params) {
                    console.error('scroll_by: 缺少参数');
                    return false;
                }
                const amount = params.amount;
                const documentElement = document.documentElement || document.body;
                
                if (documentElement.scrollHeight > window.innerHeight * 1.2) {
                    const y = Math.max(
                        20,
                        Math.min((window.innerHeight || documentElement.clientHeight) / 10, 200)
                    );
                    window.scrollBy(0, y * amount);
                    return;
                }
                
                // 复杂的滚动逻辑 - 查找可滚动元素
                function findScrollableElements() {
                    const allElements = Array.from(document.querySelectorAll('*'));
                    return allElements.filter((el) => {
                        const style = window.getComputedStyle(el);
                        const overflowY = style.getPropertyValue("overflow-y");
                        return (
                            (overflowY === "auto" || overflowY === "scroll") &&
                            el.scrollHeight > el.clientHeight
                        );
                    });
                }
                
                const scrollableElements = findScrollableElements();
                if (scrollableElements.length === 0) {
                    const y = Math.max(
                        20,
                        Math.min((window.innerHeight || documentElement.clientHeight) / 10, 200)
                    );
                    window.scrollBy(0, y * amount);
                    return false;
                }
                
                // 选择最佳滚动元素
                const largestElement = scrollableElements[0];
                const viewportHeight = largestElement.clientHeight;
                const y = Math.max(20, Math.min(viewportHeight / 10, 200));
                largestElement.scrollBy(0, y * amount);
                
                return true;
            };
        """
        await self.execute_script(script)
        
    async def inject_main_dom_functions(self):
        """注入主要的DOM函数"""
        script = """
            // 初始化全局变量
            window._interactive_elements = new Map();
            window._highlight_markers = [];
            
            // get_highlight_element 函数
            window.get_highlight_element = function(index) {
                return window._interactive_elements.get(index);
            };
            
            // remove_highlight 函数
            window.remove_highlight = function() {
                window._highlight_markers.forEach(marker => {
                    if (marker && marker.parentNode) {
                        marker.parentNode.removeChild(marker);
                    }
                });
                window._highlight_markers = [];
            };
            
            // get_clickable_elements 函数 - 核心功能
            window.get_clickable_elements = function(withHighlight) {
                console.log('🔍 开始扫描可交互元素...');
                
                // 清理之前的数据
                window._interactive_elements.clear();
                window.remove_highlight();
                
                const elements = [];
                let index = 1;
                
                // 查找常见的可交互元素
                const selectors = [
                    'textarea[name="q"]',
                    'input[name="q"]',
                    'input[type="search"]',
                    '*[role="combobox"]',
                    '*[aria-label*="Search"]',
                    '*[aria-label*="搜索"]',
                    'input:not([type="hidden"])',
                    'textarea',
                    '*[contenteditable="true"]',
                    'button',
                    'input[type="submit"]',
                    'input[type="button"]',
                    '*[role="button"]',
                    'a[href]:not([href="#"])',
                    'select',
                    '[onclick]',
                    '[tabindex]:not([tabindex="-1"])'
                ];
                
                const foundElements = new Set();
                
                selectors.forEach(selector => {
                    try {
                        const nodeList = document.querySelectorAll(selector);
                        nodeList.forEach(el => {
                            if (isElementVisible(el) && !foundElements.has(el)) {
                                foundElements.add(el);
                                
                                const rect = el.getBoundingClientRect();
                                const elementInfo = {
                                    tag: el.tagName.toLowerCase(),
                                    index: index,
                                    text: getElementText(el),
                                    placeholder: el.placeholder || '',
                                    type: el.type || el.tagName.toLowerCase(),
                                    bounds: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                                    role: el.getAttribute('role') || el.tagName.toLowerCase(),
                                    name: el.getAttribute('name') || '',
                                    id: el.getAttribute('id') || '',
                                    'aria-label': el.getAttribute('aria-label') || '',
                                    href: el.href || el.getAttribute('href') || '',
                                    value: el.value || '',
                                    title: el.title || el.getAttribute('title') || '',
                                    className: el.className || '',
                                    disabled: el.disabled || false,
                                    checked: el.checked || false,
                                    selected: el.selected || false
                                };
                                
                                elements.push(elementInfo);
                                window._interactive_elements.set(index, el);
                                
                                // 如果需要高亮显示
                                if (withHighlight) {
                                    highlightElement(el, index, rect);
                                }
                                
                                index++;
                            }
                        });
                    } catch (e) {
                        console.warn('选择器错误:', selector, e);
                    }
                });
                
                // 生成元素字符串
                const elementStr = elements.map(el => {
                    let attrs = '';
                    if (el.type && el.type !== el.tag) attrs += ` type="${el.type}"`;
                    if (el.name) attrs += ` name="${el.name}"`;
                    if (el.placeholder) attrs += ` placeholder="${el.placeholder}"`;
                    if (el.role && el.role !== el.tag) attrs += ` role="${el.role}"`;
                    if (el['aria-label']) attrs += ` aria-label="${el['aria-label']}"`;
                    if (el.href && el.tag === 'a') attrs += ` href="${el.href.substring(0, 100)}"`;
                    if (el.value && (el.tag === 'input' || el.tag === 'textarea')) attrs += ` value="${el.value.substring(0, 50)}"`;
                    if (el.title) attrs += ` title="${el.title.substring(0, 50)}"`;
                    if (el.disabled) attrs += ` disabled="true"`;
                    if (el.checked) attrs += ` checked="true"`;
                    
                    return `[${el.index}]:<${el.tag}${attrs}>${el.text}</${el.tag}>`;
                }).join('\\n');
                
                console.log(`✅ 找到 ${elements.length} 个可交互元素`);
                
                return {
                    element_str: elementStr,
                    elements: elements,
                    count: elements.length
                };
            };
            
            // 辅助函数
            function isElementVisible(el) {
                const rect = el.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) return false;
                
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') return false;
                if (parseFloat(style.opacity) === 0) return false;
                
                return true;
            }
            
            function getElementText(el) {
                if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                    return el.value || el.placeholder || '';
                }
                
                let text = el.innerText || el.textContent || '';
                return text.trim().replace(/\\s+/g, ' ').substring(0, 50);
            }
            
            function highlightElement(el, index, rect) {
                const marker = document.createElement('div');
                marker.className = 'ai-element-marker';
                marker.style.cssText = `
                    position: fixed;
                    left: ${rect.left}px;
                    top: ${rect.top}px;
                    width: ${rect.width}px;
                    height: ${rect.height}px;
                    border: 2px solid #ff6b6b;
                    background: rgba(255, 107, 107, 0.1);
                    pointer-events: none;
                    z-index: 999999;
                `;
                
                const label = document.createElement('div');
                label.textContent = `[${index}]`;
                label.style.cssText = `
                    position: absolute;
                    top: -20px;
                    right: -2px;
                    background: #ff6b6b;
                    color: white;
                    padding: 2px 6px;
                    font-size: 12px;
                    font-weight: bold;
                    border-radius: 3px;
                    line-height: 1;
                    font-family: monospace;
                `;
                
                marker.appendChild(label);
                document.body.appendChild(marker);
                window._highlight_markers.push(marker);
            }
            
            console.log('✅ DOM 工具函数初始化完成');
        """
        await self.execute_script(script)
        
    async def initialize(self):
        """初始化代理"""
        await super().get_browser_context()
        logger.info("✅ BaseBrowserLabelsAgent 初始化完成 - DOM 脚本将在页面加载时注入")
    
    # ====== 新增：统一接口方法 ======
    
    async def execute_action(self, action) -> Dict[str, Any]:
        """
        执行标准化操作 - PlanAgent的统一调用接口
        
        Args:
            action: Action对象，包含type, target, value等
            
        Returns:
            Dict: 包含success, data, error等字段的执行结果
        """
        import time
        from ..types import ActionType, ActionResult
        
        start_time = time.time()
        
        try:
            if action.type == ActionType.NAVIGATE:
                await self.navigate_to(action.target)
                page_state = await self.get_page_state()
                data = {'navigated_to': action.target}
                
            elif action.type == ActionType.CLICK:
                element_index = int(action.target)
                await self.click_element(element_index)
                # 等待页面可能的跳转
                await self.sleep(1500)
                page_state = await self.get_page_state()
                data = {'clicked_element': element_index}
                
            elif action.type == ActionType.INPUT:
                element_index = int(action.target)
                text = action.value
                press_enter = "|ENTER" in text if text else False
                if press_enter and text:
                    text = text.replace("|ENTER", "")
                
                await self.input_text(element_index, text, press_enter)
                if press_enter:
                    # 如果按了回车键，等待页面跳转
                    await self.sleep(2000)
                page_state = await self.get_page_state()
                data = {'input_text': text, 'press_enter': press_enter}
                
            elif action.type == ActionType.EXTRACT:
                extracted_data = await self.extract_page_data()
                page_state = await self.get_page_state()
                data = {'data': extracted_data, 'count': len(extracted_data)}
                
            elif action.type == ActionType.WAIT:
                wait_time = int(action.value) if action.value else 2000
                await self.sleep(wait_time)
                page_state = await self.get_page_state()
                data = {'wait_time': wait_time}
                
            elif action.type == ActionType.SCROLL:
                if action.target:
                    # 滚动到指定元素
                    element_index = int(action.target)
                    await self.scroll_to_element(element_index)
                else:
                    # 滚动页面
                    amount = int(action.value) if action.value else 3
                    await self.scroll_mouse_wheel(amount)
                page_state = await self.get_page_state()
                data = {'scroll_target': action.target or 'page'}
                
            elif action.type == ActionType.HOVER:
                element_index = int(action.target)
                await self.hover_to_element(element_index)
                page_state = await self.get_page_state()
                data = {'hover_element': element_index}
                
            elif action.type == ActionType.CHECK_GOAL:
                # 检查目标是否达成
                page_state = await self.get_page_state()
                goal_achieved = self._check_goal_achievement(page_state, action.value)
                data = {'goal_achieved': goal_achieved, 'criteria': action.value}
                
            else:
                raise ValueError(f"不支持的操作类型: {action.type}")
            
            execution_time = time.time() - start_time
            
            return ActionResult(
                success=True,
                action=action,
                data=data,
                page_state=page_state,
                execution_time=execution_time
            ).to_dict()
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            logger.error(f"❌ 操作执行失败: {error_msg}")
            
            return ActionResult(
                success=False,
                action=action,
                error=error_msg,
                execution_time=execution_time
            ).to_dict()
    
    async def get_page_state(self) -> Dict[str, Any]:
        """获取当前页面状态"""
        try:
            state = {}
            
            if self.page:
                state['url'] = self.page.url
                try:
                    state['title'] = await self.page.title()
                except:
                    state['title'] = ''
                
                # 检查页面基本元素
                try:
                    search_elements = await self.page.query_selector_all("input[type='search'], input[placeholder*='搜索'], textarea[name='q']")
                    state['has_search'] = len(search_elements) > 0
                    
                    links = await self.page.query_selector_all("a[href]:not([href='#'])")
                    state['links_count'] = len(links)
                    
                    # 检查是否在搜索结果页面
                    url_lower = state['url'].lower()
                    state['is_search_results'] = any(keyword in url_lower for keyword in ['search', 'result', 'query'])
                    
                except Exception as e:
                    logger.debug(f"获取页面元素状态失败: {e}")
            
            state['timestamp'] = time.time()
            return state
            
        except Exception as e:
            logger.warning(f"⚠️ 获取页面状态失败: {e}")
            return {'error': str(e), 'timestamp': time.time()}
    
    async def extract_page_data(self) -> List[Dict[str, Any]]:
        """通用页面数据提取 - 不针对特定网站"""
        try:
            if not self.page:
                return []
            
            logger.info(f"📊 开始提取页面数据...")
            
            # 获取页面基本信息
            page_info = {
                'url': self.page.url,
                'title': await self.page.title(),
                'timestamp': time.time()
            }
            
            # 提取所有可交互元素的信息
            elements_data = await self._extract_all_elements()
            
            # 提取页面文本内容
            text_content = await self._extract_text_content()
            
            # 组合返回数据
            result = {
                'page_info': page_info,
                'elements': elements_data,
                'text_content': text_content,
                'element_count': len(elements_data)
            }
            
            logger.info(f"📦 提取完成: {len(elements_data)} 个元素")
            return [result]  # 返回列表格式以保持接口兼容性
            
        except Exception as e:
            logger.error(f"❌ 数据提取失败: {e}")
            return []
    
    async def _extract_all_elements(self) -> List[Dict[str, Any]]:
        """提取页面所有可交互元素的详细信息"""
        elements = []
        try:
            # 使用已有的 get_clickable_elements 功能
            clickable_data = await self.get_clickable_elements(with_highlight=False)
            
            # 从 clickable_data 中提取元素信息
            if isinstance(clickable_data, dict) and 'elements' in clickable_data:
                for elem in clickable_data['elements']:
                    element_info = {
                        'index': elem.get('index'),
                        'tag': elem.get('tag'),
                        'text': elem.get('text', '').strip(),
                        'type': elem.get('type'),
                        'role': elem.get('role'),
                        'name': elem.get('name'),
                        'id': elem.get('id'),
                        'placeholder': elem.get('placeholder'),
                        'aria-label': elem.get('aria-label'),
                        'bounds': elem.get('bounds')
                    }
                    # 移除空值
                    element_info = {k: v for k, v in element_info.items() if v}
                    elements.append(element_info)
            
            # 额外提取链接信息
            all_links = await self.page.query_selector_all("a[href]")
            for link in all_links[:50]:  # 限制数量以避免太多数据
                try:
                    href = await link.get_attribute("href")
                    text = await link.inner_text()
                    
                    if href and text and len(text.strip()) > 0:
                        # 检查是否已在 clickable_elements 中
                        already_exists = any(
                            elem.get('text') == text.strip() 
                            for elem in elements
                        )
                        
                        if not already_exists:
                            elements.append({
                                'tag': 'a',
                                'text': text.strip()[:200],
                                'href': href,
                                'type': 'link'
                            })
                except Exception:
                    continue
            
            return elements
            
        except Exception as e:
            logger.error(f"❌ 元素提取失败: {e}")
            return []
    
    async def _extract_text_content(self) -> str:
        """提取页面的文本内容"""
        try:
            # 使用 JavaScript 提取页面主要文本内容
            text_content = await self.execute_script("""
                () => {
                    // 移除脚本和样式标签
                    const scripts = document.querySelectorAll('script, style, noscript');
                    scripts.forEach(el => el.remove());
                    
                    // 获取主要内容区域
                    const contentSelectors = [
                        'main', 'article', '[role="main"]', 
                        '#content', '.content', '#main', '.main'
                    ];
                    
                    let mainContent = '';
                    for (const selector of contentSelectors) {
                        const element = document.querySelector(selector);
                        if (element) {
                            mainContent = element.innerText || element.textContent || '';
                            if (mainContent.length > 100) break;
                        }
                    }
                    
                    // 如果没有找到主要内容区域，获取body的文本
                    if (!mainContent || mainContent.length < 100) {
                        mainContent = document.body.innerText || document.body.textContent || '';
                    }
                    
                    // 清理文本
                    return mainContent
                        .replace(/\\s+/g, ' ')  // 多个空白合并为一个
                        .replace(/\\n{3,}/g, '\\n\\n')  // 限制连续换行
                        .trim()
                        .substring(0, 5000);  // 限制长度
                }
            """)
            
            return text_content or ''
            
        except Exception as e:
            logger.error(f"❌ 文本内容提取失败: {e}")
            return ''
    
    async def extract_page_content(self, variable_name: Optional[str] = None) -> Dict[str, Any]:
        """
        提取页面内容 - 类似 eko 的 extract_page_content
        返回页面的标题、URL和文本内容
        """
        try:
            page_info = await self.get_page_state()
            text_content = await self._extract_text_content()
            
            result = {
                'title': page_info.get('title', ''),
                'page_url': page_info.get('url', ''),
                'page_content': text_content
            }
            
            # 如果指定了变量名，将结果存储到变量中
            if variable_name:
                # 这里需要上下文管理器的支持
                # 目前先留空，后续可以添加
                pass
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 页面内容提取失败: {e}")
            return {'title': '', 'page_url': '', 'page_content': ''}
    
    # 添加一个新的通用元素描述方法
    async def describe_elements(self, elements: List[Dict[str, Any]]) -> str:
        """
        将元素列表转换为可读的描述
        类似 eko 的 pseudoHtml 格式
        """
        descriptions = []
        for elem in elements:
            index = elem.get('index', '')
            tag = elem.get('tag', '')
            text = elem.get('text', '')
            elem_type = elem.get('type', '')
            
            # 构建元素描述
            attrs = []
            if elem_type:
                attrs.append(f'type="{elem_type}"')
            if elem.get('name'):
                attrs.append(f'name="{elem.get("name")}"')
            if elem.get('placeholder'):
                attrs.append(f'placeholder="{elem.get("placeholder")}"')
            if elem.get('aria-label'):
                attrs.append(f'aria-label="{elem.get("aria-label")}"')
            
            attr_str = ' '.join(attrs)
            if attr_str:
                attr_str = ' ' + attr_str
            
            if index:
                descriptions.append(f'[{index}]:<{tag}{attr_str}>{text}</{tag}>')
            else:
                descriptions.append(f'<{tag}{attr_str}>{text}</{tag}>')
        
        return '\n'.join(descriptions)
    
    def _check_goal_achievement(self, page_state: Dict[str, Any], criteria: Optional[str] = None) -> bool:
        """检查目标是否达成"""
        try:
            # 基本的目标检测逻辑
            url = page_state.get('url', '').lower()
            
            # 如果在搜索结果页面，认为搜索目标达成
            if any(keyword in url for keyword in ['search', 'result', 'query']):
                return True
            
            # 如果页面有链接且不是首页，认为已有内容
            if page_state.get('links_count', 0) > 5 and 'google.com' not in url:
                return True
            
            # 如果有具体的criteria，进行更精确的检查
            if criteria:
                if 'search' in criteria.lower() and page_state.get('is_search_results', False):
                    return True
                if 'extract' in criteria.lower() and page_state.get('links_count', 0) > 0:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ 目标检测失败: {e}")
            return False