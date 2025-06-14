# 智能网页爬虫 - 精简专业版

基于 OpenRouter API 和 LangGraph 的智能网页交互系统，采用专业级精简架构。

## 🎯 核心特性

- **3个核心智能体**: Planner → Executor → Extractor
- **共享上下文**: WebContext 贯穿整个流程  
- **Cookies管理**: 自动保存/加载登录状态
- **真实LLM调用**: 直接使用OpenRouter API，无模拟代码
- **精简架构**: <300行核心代码，专业级标准

## 🏗️ 项目结构

```
smart-bookmark/
├── core/                    # 核心模块
│   ├── orchestrator.py     # 主编排器 (3个智能体)
│   └── browser.py          # 浏览器核心 (cookies管理)
├── examples/               # 示例演示
│   └── bilibili_login_demo.py  # 登录演示
├── cookies/               # Cookies存储
├── outputs/               # 输出结果
├── load_env.py           # 环境变量加载
├── main.py               # 主程序入口
├── test.py               # 简单测试
└── requirements.txt      # 依赖包
```

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置API
创建 `.env` 文件：
```bash
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_MODEL=anthropic/claude-3-sonnet-20240229
HTTP_REFERER=https://smart-bookmark.com
X_TITLE=Smart Bookmark Crawler
```

### 3. 运行程序
```bash
# 交互式使用
python main.py

# 简单测试
python test.py

# 登录演示
python examples/bilibili_login_demo.py
```

## 💡 使用示例

### 基本爬取
```python
from core import WebOrchestrator

orchestrator = WebOrchestrator()
result = await orchestrator.run(
    instruction="在B站搜索Python教程，获取前5个视频",
    url="https://www.bilibili.com"
)
```

### 需要登录的爬取
```python
from examples.bilibili_login_demo import BilibiliLoginDemo

demo = BilibiliLoginDemo()
result = await demo.crawl_with_login("获取我的关注动态")
```

## 🧠 智能体架构

### WebContext (共享上下文)
```python
@dataclass
class WebContext:
    url: str                    # 目标网站
    instruction: str            # 用户指令  
    current_state: Dict         # 当前状态
    extracted_data: List        # 提取数据
    execution_log: List         # 执行日志
    error: Optional[str]        # 错误信息
```

### 3个核心智能体

1. **🎯 Planner (规划者)**
   - 将自然语言转换为MCP操作序列
   - 生成具体的浏览器自动化步骤

2. **⚡ Executor (执行者)**
   - 执行MCP操作计划
   - 处理浏览器交互和数据获取

3. **📊 Extractor (提取者)**
   - 从执行结果中提取结构化数据
   - 使用LLM优化数据格式

## 🔐 Cookies管理

系统自动处理登录状态：

- **自动加载**: 启动时加载已保存的cookies
- **智能检测**: 检查当前登录状态
- **手动登录**: 需要时引导手动登录
- **自动保存**: 登录成功后保存cookies

## 📋 支持的任务类型

### 无需登录
- Google/百度搜索结果提取
- GitHub项目信息收集
- 公开网站内容抓取

### 需要登录  
- B站个人动态/收藏
- 知乎关注内容
- 社交媒体个人数据

## 🎮 交互模式

运行 `python main.py` 后可以：

1. **选择预定义任务**
2. **输入自定义指令**
3. **自动推断目标网站**

支持自然语言指令如：
- "在B站搜索机器学习视频，按播放量排序"
- "在GitHub搜索Python爬虫项目，获取前10个"
- "获取我在知乎的关注动态"

## 🔧 技术栈

- **LangGraph**: 智能体编排
- **OpenRouter**: LLM API服务
- **Playwright**: 浏览器自动化
- **Python 3.8+**: 运行环境

## 📊 性能特点

- **精简高效**: 核心代码<300行
- **成本优化**: 智能选择LLM调用时机
- **可扩展**: 易于添加新的智能体
- **专业标准**: 企业级代码质量

## 🤝 开发指南

### 添加新网站支持
1. 在 `main.py` 的 `_infer_url()` 中添加网站映射
2. 在 `examples/` 中创建专门的演示文件

### 扩展智能体
1. 继承 `CoreAgent` 基类
2. 实现 `process(context: WebContext)` 方法
3. 在 `WebOrchestrator` 中集成

这就是一个**专业、精简、高效**的智能网页爬虫系统！