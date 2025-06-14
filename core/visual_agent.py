"""
视觉智能体 - 多模态页面理解和交互
结合截图和可交互元素信息，实现更可靠的网页自动化
"""
import base64
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from playwright.async_api import Page, ElementHandle
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


@dataclass
class InteractiveElement:
    """可交互元素信息"""
    tag: str
    element_id: str  # 我们分配的唯一ID
    selector: str
    text: str
    placeholder: str
    element_type: str  # input, button, link, etc.
    bounds: Dict[str, float]  # x, y, width, height
    is_visible: bool
    role: str  # 元素的语义角色


class VisualPageAnalyzer:
    """视觉页面分析器 - 提取可见交互元素并生成多模态提示"""
    
    def __init__(self, task_id: str = None):
        self.element_counter = 0
        self.task_id = task_id or f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 创建任务专用目录
        self.base_dir = Path("workflow_logs")
        self.task_dir = self.base_dir / self.task_id
        self.screenshots_dir = self.task_dir / "screenshots"
        self.steps_dir = self.task_dir / "steps"
        
        # 确保目录存在
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.steps_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📁 工作流日志目录: {self.task_dir}")
    
    async def analyze_page(self, page: Page, context: Dict[str, Any] = None) -> Tuple[str, List[InteractiveElement]]:
        """分析页面，返回截图和可交互元素列表"""
        
        try:
            # 1. 等待页面稳定
            await page.wait_for_load_state('networkidle', timeout=5000)
        except:
            logger.warning("页面加载未完全稳定，继续分析")
        
        # 2. 提取所有可交互元素
        interactive_elements = await self._extract_interactive_elements(page)
        
        # 3. 在页面上标记元素（用于视觉识别）
        await self._mark_elements_on_page(page, interactive_elements)
        
        # 4. 获取标记后的截图（降低超时时间）
        marked_screenshot_buffer = None
        marked_screenshot_base64 = ""
        
        try:
            marked_screenshot_buffer = await page.screenshot(
                full_page=False,
                type="png",
                timeout=10000  # 10秒超时
            )
            marked_screenshot_base64 = base64.b64encode(marked_screenshot_buffer).decode()
            
        except Exception as e:
            logger.warning(f"截图失败，使用文本模式: {e}")
        
        # 5. 保存完整的步骤记录
        screenshot_path = await self._save_step_record(
            marked_screenshot_buffer, 
            page, 
            interactive_elements, 
            context
        )
        
        logger.info(f"📊 页面分析完成: 找到 {len(interactive_elements)} 个可见交互元素")
        logger.info(f"💾 步骤记录已保存: {screenshot_path}")
        
        return marked_screenshot_base64, interactive_elements
    
    async def _save_step_record(
        self, 
        screenshot_buffer: bytes, 
        page: Page, 
        elements: List[InteractiveElement], 
        context: Dict[str, Any] = None
    ) -> str:
        """保存完整的步骤记录"""
        try:
            self.element_counter += 1
            step_num = self.element_counter
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 包含毫秒
            domain = page.url.split('//')[1].split('/')[0] if '//' in page.url else 'unknown'
            base_filename = f"step_{step_num:03d}_{timestamp}_{domain}"
            
            # 1. 保存截图
            screenshot_path = None
            if screenshot_buffer:
                screenshot_filename = f"{base_filename}.png"
                screenshot_path = self.screenshots_dir / screenshot_filename
                with open(screenshot_path, 'wb') as f:
                    f.write(screenshot_buffer)
            
            # 2. 保存完整的步骤信息为JSON
            step_data = {
                "step_number": step_num,
                "timestamp": timestamp,
                "task_id": self.task_id,
                "page_info": {
                    "url": page.url,
                    "title": await page.title() if page else "Unknown",
                    "domain": domain
                },
                "context": context or {},
                "screenshot_path": str(screenshot_path.name) if screenshot_path else None,
                "interactive_elements": [
                    {
                        "element_id": elem.element_id,
                        "tag": elem.tag,
                        "role": elem.role,
                        "text": elem.text,
                        "placeholder": elem.placeholder,
                        "bounds": elem.bounds,
                        "selector": elem.selector,
                        "is_visible": elem.is_visible
                    } for elem in elements
                ],
                "elements_count": len(elements)
            }
            
            # 保存JSON记录
            json_filename = f"{base_filename}.json"
            json_path = self.steps_dir / json_filename
            with open(json_path, 'w', encoding='utf-8') as f:
                import json
                json.dump(step_data, f, ensure_ascii=False, indent=2)
            
            # 3. 生成人类可读的总结文件
            summary_filename = f"{base_filename}_summary.md"
            summary_path = self.steps_dir / summary_filename
            await self._generate_step_summary(step_data, summary_path)
            
            logger.info(f"📸 截图保存: {screenshot_path}")
            logger.info(f"📋 步骤记录: {json_path}")
            logger.info(f"📝 总结文件: {summary_path}")
            
            return str(screenshot_path) if screenshot_path else str(json_path)
            
        except Exception as e:
            logger.error(f"保存步骤记录失败: {e}")
            return ""
    
    async def _generate_step_summary(self, step_data: Dict, summary_path: Path):
        """生成步骤总结Markdown文件"""
        try:
            context = step_data.get('context', {})
            elements = step_data.get('interactive_elements', [])
            
            summary_content = f"""# 步骤 {step_data['step_number']} - 工作流记录

## 基本信息
- **时间**: {step_data['timestamp']}
- **任务ID**: {step_data['task_id']}
- **页面标题**: {step_data['page_info']['title']}
- **页面URL**: {step_data['page_info']['url']}
- **截图**: {step_data.get('screenshot_path', '无')}

## 上下文信息
"""
            
            if context.get('step_count'):
                summary_content += f"- **当前步骤**: {context['step_count']}\n"
            if context.get('last_action'):
                action = context['last_action']
                summary_content += f"- **上一步操作**: {action['type']} {action.get('target', '')}\n"
            if context.get('instruction'):
                summary_content += f"- **任务指令**: {context['instruction']}\n"
            
            summary_content += f"\n## 可交互元素 ({len(elements)} 个)\n\n"
            
            for elem in elements:
                summary_content += f"### {elem['element_id']} ({elem['role']})\n"
                summary_content += f"- **标签**: {elem['tag']}\n"
                summary_content += f"- **文本**: {elem['text'] or '无'}\n"
                summary_content += f"- **占位符**: {elem['placeholder'] or '无'}\n"
                summary_content += f"- **位置**: ({elem['bounds']['x']}, {elem['bounds']['y']}) {elem['bounds']['width']}x{elem['bounds']['height']}\n"
                summary_content += f"- **选择器**: {elem['selector']}\n\n"
            
            # 保存Markdown文件
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(summary_content)
                
        except Exception as e:
            logger.warning(f"生成步骤总结失败: {e}")
    
    async def _extract_interactive_elements(self, page: Page) -> List[InteractiveElement]:
        """提取页面中真正可见且可交互的元素"""
        elements = []
        
        # 定义高优先级可交互元素的选择器（减少噪音）
        high_priority_selectors = [
            'input[type="text"]',
            'input[type="search"]', 
            'input[type="email"]',
            'input[type="password"]',
            'input:not([type])',
            'textarea',
            'button:not([style*="display: none"])',
            'a[href]:not([style*="display: none"])',
            '[role="button"]:not([style*="display: none"])',
            'select',
            '[contenteditable="true"]',
            'input[type="submit"]',
            'input[type="button"]'
        ]
        
        # 搜索和导航相关的选择器（B站特定）
        site_specific_selectors = [
            '.search-input-el',
            '.nav-search-input', 
            '.search-input',
            '[placeholder*="搜索"]',
            '[class*="search"][class*="input"]',
            '[class*="search"][class*="btn"]',
            '.bili-header-m .nav-search-content'
        ]
        
        all_selectors = high_priority_selectors + site_specific_selectors
        
        for selector in all_selectors:
            try:
                element_handles = await page.query_selector_all(selector)
                for handle in element_handles:
                    element_info = await self._extract_element_info(handle)
                    # 严格的可见性检查
                    if (element_info and 
                        element_info.is_visible and 
                        self._is_truly_interactive(element_info)):
                        elements.append(element_info)
            except Exception as e:
                logger.debug(f"提取元素失败 {selector}: {e}")
                continue
        
        # 去重并排序（按位置）
        unique_elements = self._deduplicate_elements(elements)
        unique_elements.sort(key=lambda e: (e.bounds['y'], e.bounds['x']))
        
        # 限制元素数量（避免过多噪音）
        if len(unique_elements) > 20:
            logger.info(f"🔍 元素过多({len(unique_elements)})，筛选前20个重要元素")
            unique_elements = self._filter_important_elements(unique_elements)
        
        return unique_elements
    
    def _is_truly_interactive(self, element: InteractiveElement) -> bool:
        """检查元素是否真正可交互"""
        # 检查尺寸（太小的元素可能不是真正的交互元素）
        if element.bounds['width'] < 10 or element.bounds['height'] < 10:
            return False
        
        # 检查位置（在视窗外的元素不考虑）
        if (element.bounds['x'] < 0 or element.bounds['y'] < 0 or 
            element.bounds['x'] > 2000 or element.bounds['y'] > 2000):
            return False
        
        # 优先考虑有明确作用的元素
        priority_roles = ['search_input', 'search_button', 'form_input', 'action_button']
        if element.role in priority_roles:
            return True
        
        # 有文本内容或占位符的元素更可能是有用的
        if element.text.strip() or element.placeholder.strip():
            return True
        
        # 表单元素通常是有用的
        if element.tag in ['input', 'button', 'textarea', 'select']:
            return True
        
        return False
    
    def _filter_important_elements(self, elements: List[InteractiveElement]) -> List[InteractiveElement]:
        """筛选重要的交互元素"""
        important_elements = []
        
        # 优先级排序
        priority_order = {
            'search_input': 1,
            'search_button': 2, 
            'form_input': 3,
            'action_button': 4,
            'navigation_link': 5,
            'form_button': 6,
            'interactive_element': 7
        }
        
        # 按优先级和位置排序
        sorted_elements = sorted(elements, key=lambda e: (
            priority_order.get(e.role, 999),
            e.bounds['y'],
            e.bounds['x']
        ))
        
        return sorted_elements[:20]  # 返回前20个最重要的元素
    
    async def _extract_element_info(self, handle: ElementHandle) -> Optional[InteractiveElement]:
        """提取单个元素的信息"""
        try:
            # 严格的可见性检查
            is_visible = await handle.is_visible()
            if not is_visible:
                return None
            
            # 额外检查：元素是否在视窗中且有有效尺寸
            bounding_box = await handle.bounding_box()
            if not bounding_box or bounding_box['width'] <= 0 or bounding_box['height'] <= 0:
                return None
            
            # 获取元素基本信息
            tag_name = await handle.evaluate('el => el.tagName.toLowerCase()')
            element_type = await handle.evaluate('el => el.type || el.tagName.toLowerCase()')
            text_content = await handle.evaluate('el => el.textContent?.trim() || ""')
            placeholder = await handle.evaluate('el => el.placeholder || ""')
            
            # bounding_box 已经在上面检查过了
            
            # 生成选择器
            element_id = await handle.evaluate('''el => {
                if (el.id) return el.id;
                if (el.className) return el.className.split(' ')[0];
                return el.tagName.toLowerCase();
            }''')
            
            # 生成唯一ID
            self.element_counter += 1
            unique_id = f"elem_{self.element_counter}"
            
            # 确定元素角色
            role = await self._determine_element_role(handle, tag_name, element_type, text_content, placeholder)
            
            return InteractiveElement(
                tag=tag_name,
                element_id=unique_id,
                selector=f"#{element_id}" if element_id else tag_name,
                text=text_content[:50],  # 限制长度
                placeholder=placeholder,
                element_type=element_type,
                bounds={
                    'x': bounding_box['x'],
                    'y': bounding_box['y'], 
                    'width': bounding_box['width'],
                    'height': bounding_box['height']
                },
                is_visible=is_visible,
                role=role
            )
            
        except Exception as e:
            logger.debug(f"提取元素信息失败: {e}")
            return None
    
    async def _determine_element_role(self, handle: ElementHandle, tag: str, element_type: str, text: str, placeholder: str) -> str:
        """确定元素的语义角色"""
        text_lower = text.lower()
        placeholder_lower = placeholder.lower()
        
        # 搜索相关
        if ('search' in placeholder_lower or 'search' in text_lower or 
            '搜索' in placeholder or '搜索' in text):
            return 'search_input' if tag == 'input' else 'search_button'
        
        # 登录相关
        if ('login' in text_lower or 'signin' in text_lower or 
            '登录' in text or '登陆' in text):
            return 'login_button'
        
        # 导航相关
        if tag == 'a':
            return 'navigation_link'
        
        # 表单控件
        if tag == 'input':
            if element_type in ['text', 'email', 'password']:
                return 'form_input'
            elif element_type in ['submit', 'button']:
                return 'form_button'
        
        if tag == 'button':
            return 'action_button'
        
        if tag == 'textarea':
            return 'text_area'
        
        return 'interactive_element'
    
    def _deduplicate_elements(self, elements: List[InteractiveElement]) -> List[InteractiveElement]:
        """去除重复元素"""
        seen_positions = set()
        unique_elements = []
        
        for element in elements:
            # 使用位置作为去重标准
            position_key = (
                round(element.bounds['x']), 
                round(element.bounds['y']),
                element.tag
            )
            
            if position_key not in seen_positions:
                seen_positions.add(position_key)
                unique_elements.append(element)
        
        return unique_elements
    
    async def _mark_elements_on_page(self, page: Page, elements: List[InteractiveElement]):
        """在页面上标记可交互元素"""
        
        # 注入标记脚本
        mark_script = """
        (elements) => {
            // 清除之前的标记
            document.querySelectorAll('.ai-element-marker').forEach(el => el.remove());
            
            elements.forEach((elementInfo, index) => {
                // 创建标记
                const marker = document.createElement('div');
                marker.className = 'ai-element-marker';
                marker.style.cssText = `
                    position: absolute;
                    left: ${elementInfo.bounds.x}px;
                    top: ${elementInfo.bounds.y}px;
                    width: ${elementInfo.bounds.width}px;
                    height: ${elementInfo.bounds.height}px;
                    border: 2px solid #ff6b6b;
                    background: rgba(255, 107, 107, 0.1);
                    pointer-events: none;
                    z-index: 9999;
                    font-size: 12px;
                    color: #fff;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                `;
                marker.textContent = elementInfo.element_id;
                document.body.appendChild(marker);
            });
        }
        """
        
        try:
            await page.evaluate(mark_script, [elem.__dict__ for elem in elements])
            logger.debug(f"已在页面标记 {len(elements)} 个元素")
        except Exception as e:
            logger.warning(f"标记元素失败: {e}")


class MultimodalPromptBuilder:
    """多模态提示构建器"""
    
    @staticmethod
    def build_visual_prompt(
        screenshot_base64: str,
        elements: List[InteractiveElement], 
        instruction: str,
        current_context: Dict[str, Any]
    ) -> HumanMessage:
        """构建包含视觉和文本信息的提示"""
        
        # 构建元素列表文本
        elements_text = MultimodalPromptBuilder._build_elements_description(elements)
        
        # 构建上下文信息
        context_text = MultimodalPromptBuilder._build_context_description(current_context)
        
        # 主提示文本
        prompt_text = f"""
🎯 **任务目标**: {instruction}

📊 **当前状况**:
{context_text}

🔍 **页面可交互元素** (已在截图中用红框标记):
{elements_text}

🤖 **请分析页面并返回严格的JSON格式操作指令**:

**必须返回以下格式的JSON**:
```json
{{
  "reasoning": "分析当前页面状态和下一步策略的思考过程",
  "action": {{
    "type": "click|type|wait|extract|scroll|navigate",
    "target": "元素ID或目标",
    "value": "输入值(仅type操作需要)",
    "description": "操作描述"
  }},
  "expectation": "执行操作后期望看到的结果",
  "confidence": 0.8
}}
```

**重要指南**:
- 仔细观察截图中的页面内容和红框标记的元素
- 选择最合适的元素ID进行操作
- type操作前通常需要先click输入框
- 一次只执行一个操作
- 确保JSON格式完全正确，不要有额外文本
"""

        # 构建多模态消息
        content = [{"type": "text", "text": prompt_text}]
        
        # 只有在有截图时才添加图片
        if screenshot_base64:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{screenshot_base64}",
                    "detail": "high"
                }
            })
        else:
            # 文本模式提示
            content[0]["text"] += "\n\n⚠️ **注意**: 截图不可用，请仅根据元素列表进行操作"
        
        return HumanMessage(content=content)
    
    @staticmethod
    def _build_elements_description(elements: List[InteractiveElement]) -> str:
        """构建元素描述文本"""
        if not elements:
            return "❌ 未发现可交互元素"
        
        descriptions = []
        for elem in elements:
            desc = f"🔹 **{elem.element_id}** ({elem.role})"
            
            if elem.text:
                desc += f" - 文本: '{elem.text}'"
            if elem.placeholder:
                desc += f" - 占位符: '{elem.placeholder}'"
            
            desc += f" - 位置: ({int(elem.bounds['x'])}, {int(elem.bounds['y'])})"
            descriptions.append(desc)
        
        return "\n".join(descriptions)
    
    @staticmethod  
    def _build_context_description(context: Dict[str, Any]) -> str:
        """构建上下文描述"""
        lines = []
        
        if context.get('step_count', 0) > 0:
            lines.append(f"📊 已执行步骤: {context['step_count']}")
        
        if context.get('last_action'):
            action = context['last_action']
            lines.append(f"🔄 上一步操作: {action['type']} {action.get('target', '')}")
        
        if context.get('page_url'):
            lines.append(f"🌐 当前页面: {context['page_url']}")
        
        if context.get('extracted_data'):
            lines.append(f"📦 已提取数据: {len(context['extracted_data'])} 条")
        
        return "\n".join(lines) if lines else "🆕 任务刚开始"