# Agent used to synthesize a final report from the individual summaries.
from pydantic import BaseModel
from openai import AsyncOpenAI
from agents import Agent, ModelSettings, OpenAIChatCompletionsModel

# 定义要使用的Ollama模型名称
MODEL_NAME = "qwq:latest" 

# 设置OpenAI兼容的Ollama客户端
# 创建一个AsyncOpenAI客户端实例，但连接到本地Ollama服务器
external_client = AsyncOpenAI(
    api_key="qwq",  
    base_url="http://localhost:11434/v1",  # 指向本地Ollama服务的端口
    timeout=300.0,  # 增加超时时间
    max_retries=3,  # 添加重试机制
)

PROMPT = (
    "你是一位资深研究人员，负责为研究查询撰写一份完整详细的报告。你将获得原始查询和研究助手进行的初步研究结果。"
    "\n\n重要说明：请确保生成实际内容而非占位符。报告每个部分都必须包含具体详细的信息，不要使用'(此处应包含...)'这类占位符文本。"
    "\n\n你的最终输出应该包含三个部分："
    "\n1. short_summary：2-3句话的研究发现简短摘要（100字以内）"
    "\n2. markdown_report：完整的markdown格式研究报告，包含所有细节，至少1000字"
    "\n3. follow_up_questions：3-5个建议进一步研究的问题"
    "\n\n报告结构应包含以下部分，每部分都需要填写实际内容："
    "\n# {查询主题}研究报告"
    "\n## 主要发现"
    "\n{在此处填写实际研究发现，不要使用占位符}"
    "\n## 详细信息"
    "\n{在此处提供详细的研究内容，基于搜索结果}"
    "\n### 相关数据和统计"
    "\n{填写实际数据和统计信息}"
    "\n### 背景和上下文"
    "\n{提供主题相关的背景信息}"
    "\n## 建议和结论"
    "\n{提供具体的建议和明确的结论}"
    "\n\n请确保报告内容具体详尽，不要生成空洞的结构或格式。每个段落应该包含有意义的信息，直接回答研究问题。"
)


class ReportData(BaseModel):
    short_summary: str
    """研究发现的简短摘要(2-3句话)"""

    markdown_report: str
    """完整的研究报告"""

    follow_up_questions: list[str]
    """建议进一步研究的问题列表"""


# 创建写作代理实例
writer_agent = Agent(
    name="WriterAgent",  # 代理名称
    instructions=PROMPT,  # 使用上面定义的提示指令
    model=OpenAIChatCompletionsModel(  # 使用OpenAI兼容的聊天模型
        model=MODEL_NAME,  # 模型名称
        openai_client=external_client,  # 使用配置好的外部客户端
    ),
    model_settings=ModelSettings(temperature=0.7),  # 设置温度参数为0.7
    output_type=ReportData,  # 指定输出类型为ReportData
)
