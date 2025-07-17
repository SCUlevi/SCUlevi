from openai import AsyncOpenAI
from agents import Agent, ModelSettings, OpenAIChatCompletionsModel

from .browser_search import browser_search

# 定义要使用的Ollama模型名称
MODEL_NAME = "qwq:latest" 

# 设置OpenAI兼容的Ollama客户端
# 创建一个AsyncOpenAI客户端实例，但连接到本地Ollama服务器
external_client = AsyncOpenAI(
    api_key="qwq", 
    base_url="http://localhost:11434/v1",  # 指向本地Ollama服务的端口
    timeout=300.0,  # 增加超时时间到300秒
    max_retries=3,  # 添加重试机制
)

INSTRUCTIONS = (
    "你是一个研究助手。给定搜索词，你需要使用浏览器搜索工具来搜索该词并生成搜索结果的简明摘要。"
    "摘要必须为2-3段，少于300字。捕捉主要观点。简洁地写作，不需要完整的句子或良好的语法。"
    "这将被用于合成报告，所以捕捉要点并忽略任何无关内容至关重要。"
    "除了摘要本身，不要包含任何额外的评论。"
)

# 创建搜索代理
search_agent = Agent(
    name="Search agent",
    instructions=INSTRUCTIONS,
    tools=[browser_search],  # 使用我们的自定义浏览器搜索工具
    model=OpenAIChatCompletionsModel(
        model=MODEL_NAME,  # 使用本地Ollama模型
        openai_client=external_client,
    ),
    model_settings=ModelSettings(temperature=0.3),
)
