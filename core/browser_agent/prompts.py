"""
BrowserAgent专用提示词
"""
from typing import Dict, List, Any


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