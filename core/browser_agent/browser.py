"""
浏览器核心功能 - 参考EkoAI设计的专业级浏览器控制
"""
import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

logger = logging.getLogger(__name__)


class BrowserCore:
    """浏览器核心 - 专业级反检测浏览器控制"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.cookies_dir = Path("cookies")
        self.cookies_dir.mkdir(exist_ok=True)
        self.headless: bool = False
        self.options: Dict[str, Any] = {}
    
    def set_headless(self, headless: bool):
        """设置无头模式"""
        self.headless = headless
    
    def set_options(self, options: Dict[str, Any]):
        """设置浏览器选项"""
        self.options = options
    
    async def start(self, headless: bool = False) -> Page:
        """启动浏览器 - 增强反检测"""
        if not self.browser:
            playwright = await async_playwright().start()
            
            # 反检测配置
            launch_options = {
                "headless": headless,
                "args": [
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor"
                ],
                **self.options
            }
            
            self.browser = await playwright.chromium.launch(**launch_options)
            self.context = await self.browser.new_context(
                viewport={"width": 1536, "height": 864},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            
            # 注入反检测脚本
            await self.context.add_init_script(self._get_stealth_script())
            
            self.page = await self.context.new_page()
            logger.info("🌐 浏览器已启动(反检测模式)")
        
        return self.page
    
    def _get_stealth_script(self) -> str:
        """反检测脚本 - 参考EkoAI实现"""
        return """
        // 隐藏webdriver特征
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });

        // 伪造语言设置
        Object.defineProperty(navigator, 'languages', {
            get: () => ['zh-CN', 'zh', 'en-US', 'en']
        });

        // 伪造插件
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                {name: "Chrome PDF Plugin"}, 
                {name: "Chrome PDF Viewer"}, 
                {name: "Native Client"}
            ]
        });

        // Chrome运行时
        window.chrome = { runtime: {} };

        // 权限处理
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );

        // Shadow DOM处理
        const originalAttachShadow = Element.prototype.attachShadow;
        Element.prototype.attachShadow = function attachShadow(options) {
            return originalAttachShadow.call(this, { ...options, mode: "open" });
        };
        """
    
    async def close(self):
        """关闭浏览器"""
        if self.browser:
            # await self.browser.close()
            self.browser = None
            self.context = None
            self.page = None
    
    async def get_all_tabs(self) -> List[Dict[str, Any]]:
        """获取所有标签页 - 参考EkoAI实现"""
        if not self.context:
            return []
        
        result = []
        pages = self.context.pages
        for i, page in enumerate(pages):
            result.append({
                "tabId": i,
                "url": page.url,
                "title": await page.title()
            })
        return result
    
    async def switch_tab(self, tab_id: int) -> Dict[str, Any]:
        """切换标签页"""
        if not self.context:
            raise Exception(f"tabId does not exist: {tab_id}")
        
        pages = self.context.pages
        if tab_id >= len(pages):
            raise Exception(f"tabId does not exist: {tab_id}")
        
        self.page = pages[tab_id]
        return {
            "tabId": tab_id,
            "url": self.page.url,
            "title": await self.page.title()
        }
    
    async def navigate_to(self, url: str) -> Dict[str, Any]:
        """安全导航 - 增强稳定性"""
        if not self.page:
            await self.start()
        
        try:
            await self.page.goto(url, 
                wait_until="networkidle", 
                timeout=10000
            )
            await self.page.wait_for_load_state("load", timeout=8000)
        except Exception as e:
            if "Timeout" not in str(e):
                raise e
            logger.warning(f"页面加载超时，继续执行: {url}")
        
        return {
            "url": self.page.url,
            "title": await self.page.title()
        }
    
    async def smart_click(self, selectors: List[str], force: bool = True) -> bool:
        """智能点击 - 多选择器尝试"""
        for selector in selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    await element.click(force=force)
                    logger.info(f"🖱️ 点击成功: {selector}")
                    return True
            except Exception as e:
                logger.debug(f"点击失败 {selector}: {e}")
                continue
        
        logger.warning(f"⚠️ 所有选择器都无法点击: {selectors}")
        return False
    
    async def smart_input(self, selectors: List[str], text: str, enter: bool = False) -> bool:
        """智能输入 - 多选择器尝试"""
        for selector in selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    await element.fill("")  # 先清空
                    await element.fill(text)
                    if enter:
                        await element.press("Enter")
                        await self.page.wait_for_timeout(200)
                    logger.info(f"⌨️ 输入成功 '{text}' 到: {selector}")
                    return True
            except Exception as e:
                logger.debug(f"输入失败 {selector}: {e}")
                continue
        
        logger.warning(f"⚠️ 所有选择器都无法输入: {selectors}")
        return False
    
    async def load_cookies(self, site_name: str) -> bool:
        """加载cookies"""
        cookies_file = self.cookies_dir / f"{site_name}_cookies.json"
        
        if not cookies_file.exists():
            logger.info(f"No cookies found for {site_name}")
            return False
        
        try:
            with open(cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            await self.context.add_cookies(cookies)
            logger.info(f"✅ Loaded cookies for {site_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")
            return False
    
    async def save_cookies(self, site_name: str):
        """保存cookies"""
        try:
            cookies = await self.context.cookies()
            cookies_file = self.cookies_dir / f"{site_name}_cookies.json"
            
            with open(cookies_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Saved cookies for {site_name}")
        except Exception as e:
            logger.error(f"Failed to save cookies: {e}")
    
    async def check_login_status(self, url: str, check_selector: str) -> bool:
        """检查登录状态 - 增强稳定性"""
        try:
            await self.navigate_to(url)
            await self.page.wait_for_timeout(2000)
            
            # 检查登录状态
            is_logged_in = await self.page.evaluate(f"!!document.querySelector('{check_selector}')")
            return is_logged_in
        except Exception as e:
            logger.error(f"Failed to check login status: {e}")
            return False
    
    async def wait_for_manual_login(self, url: str, check_selector: str, timeout: int = 300000):
        """等待手动登录"""
        logger.info("Please login manually in the browser...")
        
        try:
            await self.navigate_to(url)
            
            # 等待登录成功
            await self.page.wait_for_function(
                f"document.querySelector('{check_selector}')",
                timeout=timeout
            )
            
            logger.info("✅ Login detected!")
            return True
            
        except Exception as e:
            logger.error(f"Manual login timeout or failed: {e}")
            return False