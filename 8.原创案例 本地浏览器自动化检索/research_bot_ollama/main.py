import asyncio
import os
from openai import AsyncOpenAI
from agents import set_default_openai_client

from examples.research_bot_ollama.manager import ResearchManager

# # 检查是否设置了OPENAI_API_KEY环境变量
# if "OPENAI_API_KEY" not in os.environ:
#     print("警告: 未设置OPENAI_API_KEY环境变量，这可能会导致computer-use-preview模型无法使用")
#     print("请设置OPENAI_API_KEY环境变量后再运行")

# 设置默认OpenAI客户端
# 注意：对于computer-use-preview模型，需要使用官方OpenAI API
# 以下设置仅用于planner_agent和writer_agent
external_client = AsyncOpenAI(
    api_key="qwq",
    base_url="http://localhost:11434/v1",
    timeout=300.0,  # 增加到300秒
    max_retries=3,  # 添加重试机制
)
# 设置为默认客户端，不用于跟踪
set_default_openai_client(external_client, use_for_tracing=False)

async def main() -> None:
    query = input("\n您想研究什么主题？ ")
    await ResearchManager().run(query)


if __name__ == "__main__":
    asyncio.run(main())
