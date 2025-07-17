import asyncio
from openai import AsyncOpenAI  # 导入OpenAI异步客户端，用于与Ollama通信
from agents import Agent, ItemHelpers, Runner, ModelSettings, OpenAIChatCompletionsModel
from openai.types.responses import ResponseTextDeltaEvent 
"""
该示例展示了并行化模式。我们并行运行代理三次，并选择最佳结果。
这种模式可以让模型生成多个翻译版本，然后从中选择最优的一个。
"""

# 配置参数
CONFIG = {
    "model_name_1": "qwen2.5:7b",  # 模型1
    "model_name_2": "qwq:latest",  # 模型2
    "temperature": 0.5,  # 默认温度参数，控制输出的随机性
    "api_base": "http://localhost:11434/v1",  # Ollama API地址，指向本地运行的Ollama服务
    "timeout": 120.0,  # API超时时间，单位为秒
    "max_iterations": 5,  # 最大迭代次数
}

# 设置OpenAI兼容的Ollama客户端
# 创建一个AsyncOpenAI客户端实例，但连接到本地Ollama服务器
qwen_client_1 = AsyncOpenAI(
    api_key="qwen2.5",  # Ollama不需要真实的API密钥，但API要求提供一个值
    base_url=CONFIG["api_base"],  # 使用Ollama的API地址
    timeout=CONFIG["timeout"],  # 设置超时时间
)

qwen_client_2 = AsyncOpenAI(
    api_key="qwq",  # Ollama不需要真实的API密钥，但API要求提供一个值
    base_url=CONFIG["api_base"],  # 使用Ollama的API地址
    timeout=CONFIG["timeout"],  # 设置超时时间
)

# 自定义 OpenAIChatCompletionsModel 类来处理 Ollama 的响应格式
class OllamaOpenAIChatCompletionsModel(OpenAIChatCompletionsModel):
    """
    自定义模型类以处理Ollama API的响应格式与OpenAI API的差异。
    虽然Ollama提供了OpenAI兼容的API，但可能有细微差别，这个类用于处理这些差异。
    """
    
    async def stream_raw_text(self, *args, **kwargs):
        """
        重写流处理方法，处理可能的属性差异。
        这个方法处理模型生成文本时的流式响应。
        """
        async for event in await super().stream_raw_text(*args, **kwargs):
            yield event  # 直接传递事件，如果需要可以在这里对Ollama特有的响应格式进行处理

# 代理: 创建英语翻译代理
# 这个代理的任务是将用户的消息翻译成英语
english_agent = Agent(
    name="english_agent",  # 代理名称
    instructions="请将用户的消息翻译成英语",  
    # 使用自定义Ollama模型而非默认OpenAI模型
    model=OllamaOpenAIChatCompletionsModel(  
        model=CONFIG["model_name_1"],  
        openai_client=qwen_client_1, 
    ),
    model_settings=ModelSettings(temperature=CONFIG["temperature"]),  # 设置模型参数
)

# 代理: 创建翻译选择代理
# 这个代理的任务是从多个翻译结果中选择最佳的一个
translation_picker = Agent(
    name="translation_picker",  # 代理名称
    instructions="请从给出的选项中选择最佳的英语翻译", 
    model=OllamaOpenAIChatCompletionsModel( 
        model=CONFIG["model_name_2"], 
        openai_client=qwen_client_2, 
    ),
    model_settings=ModelSettings(temperature=CONFIG["temperature"]), 
)

async def main():
    """
    主函数，包含程序的主要逻辑流程：
    1. 获取用户输入
    2. 并行运行三个翻译代理
    3. 使用选择代理选出最佳翻译
    4. 输出结果
    """
    # 1. 获取用户输入的消息
    msg = input("你好！请输入一句消息，我们将把它翻译成英语。\n\n")

    # 使用asyncio.gather并行运行三个翻译代理
    # 这样可以同时获得三个不同的翻译版本
    res_1, res_2, res_3 = await asyncio.gather(
        Runner.run(
            english_agent,
            msg,
        ),
        Runner.run(
            english_agent,
            msg,
        ),
        Runner.run(
            english_agent,
            msg,
        ),
    )

    # 从代理结果中提取文本消息输出
    outputs = [
        ItemHelpers.text_message_outputs(res_1.new_items),  # 提取第一个代理的文本输出
        ItemHelpers.text_message_outputs(res_2.new_items),  # 提取第二个代理的文本输出
        ItemHelpers.text_message_outputs(res_3.new_items),  # 提取第三个代理的文本输出
    ]

    # 将所有翻译结果合并成一个字符串，用于展示和选择
    translations = "\n\n".join(outputs)
    print(f"\n\n多个代理的多种翻译结果：\n\n{translations}")

    # 运行翻译选择代理，从多个翻译中选出最佳的一个
    best_translation = Runner.run_streamed(
        translation_picker,  # 使用选择代理
        f"输入文本: {msg}\n\n翻译结果:\n{translations}", 
    )

    # 处理流式输出
    async for event in best_translation.stream_events():
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            print(event.data.delta, end="", flush=True)

    print("\n\n-----")



if __name__ == "__main__":
    asyncio.run(main())  
