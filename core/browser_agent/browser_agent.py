"""
浏览器代理 - 复刻 eko 的 BrowserAgent 实现
"""
import asyncio
import base64
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from playwright.async_api import Browser, Page, BrowserContext, ElementHandle, Playwright, async_playwright

logger = logging.getLogger(__name__)


class BrowserAgent:
    """浏览器代理 - 复刻 eko 的实现"""
    
    def __init__(self):
        self.cdp_ws_endpoint: Optional[str] = None
        self.user_data_dir: Optional[str] = None
        self.options: Optional[Dict[str, Any]] = None
        self.browser: Optional[Browser] = None
        self.browser_context: Optional[BrowserContext] = None
        self.current_page: Optional[Page] = None
        self.headless: bool = False
        self.playwright: Optional[Playwright] = None
        
    def set_headless(self, headless: bool):
        self.headless = headless
        
    def set_cdp_ws_endpoint(self, cdp_ws_endpoint: str):
        self.cdp_ws_endpoint = cdp_ws_endpoint
        
    def set_options(self, options: Dict[str, Any]):
        self.options = options
        
    async def screenshot(self) -> Dict[str, str]:
        """截图"""
        page = await self.current_page_instance()
        screenshot_buffer = await page.screenshot(
            full_page=False,
            type="jpeg",
            quality=60,
        )
        base64_str = base64.b64encode(screenshot_buffer).decode()
        return {
            "imageType": "image/jpeg",
            "imageBase64": base64_str,
        }
        
    async def navigate_to(self, url: str) -> Dict[str, Any]:
        """导航到指定URL"""
        page = await self.open_url(url)
        await self.sleep(200)
        return {
            "url": page.url,
            "title": await page.title(),
        }
        
    async def get_all_tabs(self) -> List[Dict[str, Any]]:
        """获取所有标签页"""
        if not self.browser_context:
            return []
            
        result = []
        pages = self.browser_context.pages
        for i, page in enumerate(pages):
            result.append({
                "tabId": i,
                "url": page.url,
                "title": await page.title(),
            })
        return result
        
    async def switch_tab(self, tab_id: int) -> Dict[str, Any]:
        """切换标签页"""
        if not self.browser_context:
            raise Exception(f"tabId does not exist: {tab_id}")
            
        pages = self.browser_context.pages
        if tab_id >= len(pages):
            raise Exception(f"tabId does not exist: {tab_id}")
            
        page = pages[tab_id]
        self.current_page = page
        return {
            "tabId": tab_id,
            "url": page.url,
            "title": await page.title(),
        }
        
    async def input_text(self, index: int, text: str, enter: bool = False):
        """输入文本"""
        try:
            element_handle = await self.get_element(index, True)
            await element_handle.fill("")
            await element_handle.fill(text)
            if enter:
                await element_handle.press("Enter")
                await self.sleep(200)
        except Exception as e:
            # 回退到JavaScript实现
            await self.execute_script_input_text(index, text, enter)
            
    async def click_element(self, index: int, num_clicks: int = 1, button: str = "left"):
        """点击元素"""
        try:
            element_handle = await self.get_element(index, True)
            await element_handle.click(
                button=button,
                click_count=num_clicks,
                force=True,
            )
        except Exception as e:
            # 回退到JavaScript实现
            await self.execute_script_click(index, button, num_clicks)
            
    async def hover_to_element(self, index: int):
        """悬停到元素"""
        try:
            element_handle = await self.get_element(index, True)
            await element_handle.hover(force=True)
        except Exception as e:
            # 回退到JavaScript实现
            await self.execute_script_hover(index)
            
    async def execute_script(self, func_code: str, args: List[Any] = None) -> Any:
        """执行JavaScript脚本"""
        page = await self.current_page_instance()
        if args:
            return await page.evaluate(func_code, args)
        else:
            return await page.evaluate(func_code)
            
    async def open_url(self, url: str) -> Page:
        """打开URL"""
        browser_context = await self.get_browser_context()
        page = await browser_context.new_page()
        await page.set_viewport_size({"width": 1536, "height": 864})
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=10000)
            await page.wait_for_load_state("load", timeout=8000)
        except Exception as e:
            if "Timeout" not in str(e):
                raise e
                
        self.current_page = page
        return page
        
    async def current_page_instance(self) -> Page:
        """获取当前页面实例"""
        if self.current_page is None:
            raise Exception("There is no page, please call navigate_to first")
            
        page = self.current_page
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass
        return page
        
    async def get_element(self, index: int, find_input: bool = False) -> ElementHandle:
        """获取元素句柄 - 复刻eko的核心逻辑"""
        page = await self.current_page_instance()
        return await page.evaluate_handle("""
            (params) => {
                let element = window.get_highlight_element(params.index);
                if (element && params.findInput) {
                    if (
                        element.tagName != "INPUT" &&
                        element.tagName != "TEXTAREA" &&
                        element.childElementCount != 0
                    ) {
                        element =
                            element.querySelector("input") ||
                            element.querySelector("textarea") ||
                            element;
                    }
                }
                return element;
            }
        """, {"index": index, "findInput": find_input})
        
    def sleep(self, time_ms: int) -> asyncio.Future:
        """睡眠"""
        return asyncio.sleep(time_ms / 1000.0)
        
    async def get_browser_context(self) -> BrowserContext:
        """获取浏览器上下文"""
        if not self.browser_context:
            self.current_page = None
            self.browser_context = None
            
            if not self.playwright:
                self.playwright = await async_playwright().start()
            
            chromium = self.playwright.chromium
            
            if self.cdp_ws_endpoint:
                self.browser = await chromium.connect_over_cdp(self.cdp_ws_endpoint)
                self.browser_context = await self.browser.new_context()
            elif self.user_data_dir:
                self.browser_context = await chromium.launch_persistent_context(
                    self.user_data_dir,
                    headless=self.headless,
                    **(self.options or {})
                )
            else:
                self.browser = await chromium.launch(
                    headless=self.headless,
                    args=["--no-sandbox"],
                    **(self.options or {})
                )
                self.browser_context = await self.browser.new_context()
                
            # 注入初始化脚本
            init_script = await self.init_script()
            await self.browser_context.add_init_script(script=init_script['content'])
            
        return self.browser_context
        
    async def init_script(self) -> Dict[str, str]:
        """初始化脚本 - 复刻eko的反检测逻辑"""
        return {
            "content": """
                // Webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // Languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US']
                });

                // Plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [{name:"1"}, {name:"2"}, {name:"3"}, {name:"4"}, {name:"5"}]
                });

                // Chrome runtime
                window.chrome = { runtime: {} };

                // Permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // Shadow DOM
                (function () {
                    const originalAttachShadow = Element.prototype.attachShadow;
                    Element.prototype.attachShadow = function attachShadow(options) {
                        return originalAttachShadow.call(this, { ...options, mode: "open" });
                    };
                })();
            """
        }
        
    # 回退的JavaScript实现
    async def execute_script_input_text(self, index: int, text: str, enter: bool):
        """JavaScript输入文本实现"""
        await self.execute_script("""
            (params) => {
                let { index, text, enter } = params;
                let element = window.get_highlight_element(index);
                if (!element) return false;
                
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
            }
        """, [{"index": index, "text": text, "enter": enter}])
        
    async def execute_script_click(self, index: int, button: str, num_clicks: int):
        """JavaScript点击实现"""
        button_map = {"left": 0, "middle": 1, "right": 2}
        button_code = button_map.get(button, 0)
        
        await self.execute_script("""
            (params) => {
                let { index, button, num_clicks } = params;
                let element = window.get_highlight_element(index);
                if (!element) return false;
                
                for (let n = 0; n < num_clicks; n++) {
                    let eventTypes = button == 2 ? 
                        ["mousedown", "mouseup", "contextmenu"] :
                        ["mousedown", "mouseup", "click"];
                        
                    for (let eventType of eventTypes) {
                        const event = new MouseEvent(eventType, {
                            view: window,
                            bubbles: true,
                            cancelable: true,
                            button: button,
                        });
                        element.dispatchEvent(event);
                    }
                }
                
                return true;
            }
        """, [{"index": index, "button": button_code, "num_clicks": num_clicks}])
        
    async def execute_script_hover(self, index: int):
        """JavaScript悬停实现"""
        await self.execute_script("""
            (params) => {
                let element = window.get_highlight_element(params.index);
                if (!element) return false;
                
                const event = new MouseEvent("mouseenter", {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                });
                element.dispatchEvent(event);
                
                return true;
            }
        """, [{"index": index}])
        
    async def close(self):
        """关闭浏览器"""
        if self.browser_context:
            await self.browser_context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    # BaseBrowserLabelsAgent的核心方法 - 等您提供完整代码后再实现
    async def screenshot_and_html(self) -> Dict[str, Any]:
        """获取截图和HTML - 等待BaseBrowserLabelsAgent代码"""
        # 这里需要实现类似BaseBrowserLabelsAgent.screenshot_and_html的逻辑
        # 包括run_build_dom_tree和get_clickable_elements的调用
        pass
        
    async def get_clickable_elements(self, with_highlight: bool = True) -> Dict[str, Any]:
        """获取可点击元素 - 等待BaseBrowserLabelsAgent代码"""
        # 这里需要实现get_clickable_elements的逻辑
        pass