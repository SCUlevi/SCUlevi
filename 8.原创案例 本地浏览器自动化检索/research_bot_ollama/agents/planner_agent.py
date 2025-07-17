from pydantic import BaseModel
from openai import AsyncOpenAI
from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, set_default_openai_client

# 定义要使用的Ollama模型名称
MODEL_NAME = "qwq:latest"  # 使用qwq模型

# 设置OpenAI兼容的Ollama客户端
# 创建一个AsyncOpenAI客户端实例，但连接到本地Ollama服务器
external_client = AsyncOpenAI(
    api_key="qwq", 
    base_url="http://localhost:11434/v1",  # 指向本地Ollama服务的端口
    timeout=120.0,  # 设置合理的超时时间
)

PROMPT = (
    "你是一位有帮助的研究助手。给定一个查询，请提出一系列网络搜索，"
    "以便最好地回答该查询。输出5到20个搜索词条。"
)


class WebSearchItem(BaseModel):
    reason: str
    "解释为什么这个搜索对于查询很重要的理由。"

    query: str
    "用于网络搜索的搜索词。"


class WebSearchPlan(BaseModel):
    searches: list[WebSearchItem]
    """要执行的网络搜索列表，以最好地回答查询。"""


# 创建规划代理实例
planner_agent = Agent(
    name="PlannerAgent",  # 代理名称
    instructions=PROMPT,  # 使用上面定义的提示指令作为代理的指导
    model=OpenAIChatCompletionsModel(  # 使用OpenAI兼容的聊天模型
        model=MODEL_NAME,  # 使用前面定义的模型名称(qwq:latest)
        openai_client=external_client,  # 使用配置好的指向本地Ollama服务的客户端
    ),
    model_settings=ModelSettings(temperature=0.7),  # 设置温度参数为0.7，控制输出的创造性
    output_type=WebSearchPlan,  # 指定输出类型为WebSearchPlan结构体，确保返回格式化的搜索计划
)
