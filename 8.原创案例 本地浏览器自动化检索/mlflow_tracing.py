""" MLflow追踪模块

本模块提供了使用MLflow追踪代理执行的功能，作为OpenAI Tracing的替代方案。
主要功能：
1. 使用MLflow追踪整个工作流程，包括代理执行、工具调用和代理转交
2. 详细记录每个步骤的输入和输出
3. 捕获代理指令、工具调用参数和结果等信息
4. 可视化代理之间的转交流程

"""

from __future__ import annotations

import json
import contextlib
from typing import Optional, Any, Dict, Callable, Awaitable, List, Union, TypeVar, cast

# 确保导入MLflow
try:
    import mlflow
except ImportError:
    raise ImportError(
        "MLflow未安装。请使用pip install mlflow安装它以使用MLflow追踪功能。"
    )

# 导入agents模块中的相关组件
from agents import Agent, HandoffInputData, Runner, function_tool, handoff

# 类型变量，用于泛型函数
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


def setup_mlflow_tracking(tracking_uri: str = "mlruns", experiment_name: Optional[str] = None):
    """
    设置MLflow追踪环境
    
    Args:
        tracking_uri: MLflow追踪服务器URI，默认为本地的"mlruns"目录
        experiment_name: 实验名称
    """
    mlflow.set_tracking_uri(tracking_uri)
    
    if experiment_name:
        mlflow.set_experiment(experiment_name)


@contextlib.contextmanager
def mlflow_trace(workflow_name: str, 
                trace_id: Optional[str] = None, 
                group_id: Optional[str] = None, 
                metadata: Optional[Dict[str, Any]] = None, 
                disabled: bool = False):
    """
    基于MLflow创建一个追踪上下文
    
    Args:
        workflow_name: 工作流名称
        trace_id: 追踪ID，如果不提供则自动生成
        group_id: 分组ID，可用于关联多个追踪
        metadata: 元数据，附加到追踪的额外信息
        disabled: 是否禁用追踪
    """
    if disabled:
        yield
        return
    
    # 设置MLflow实验，使用workflow_name作为实验名称
    mlflow.set_experiment(workflow_name)
    
    # 开始MLflow的run，相当于一个追踪会话
    with mlflow.start_run(run_name=trace_id or "trace_run") as run:
        # 记录基本信息
        if metadata:
            for key, value in metadata.items():
                mlflow.set_tag(key, str(value))
        
        if group_id:
            mlflow.set_tag("group_id", group_id)
        
        # 创建根span
        with mlflow.start_span(name=workflow_name) as span:
            # 记录工作流名称
            span.set_attribute("workflow_name", workflow_name)
            
            # 记录其他信息
            if trace_id:
                span.set_attribute("trace_id", trace_id)
            if group_id:
                span.set_attribute("group_id", group_id)
            
            try:
                yield
            except Exception as e:
                # 记录异常
                mlflow.set_tag("status", "error")
                mlflow.set_tag("error_message", str(e))
                raise
            finally:
                # 标记完成
                mlflow.set_tag("status", "completed")


@contextlib.contextmanager
def function_span(name: str, input_data: Optional[Any] = None, output_data: Optional[Any] = None):
    """
    为函数调用创建一个追踪span
    
    Args:
        name: 函数名称
        input_data: 输入数据
        output_data: 输出数据
    """
    with mlflow.start_span(name=f"Function:{name}") as span:
        try:
            # 记录输入
            if input_data is not None:
                try:
                    if isinstance(input_data, dict):
                        span.set_inputs(input_data)
                    else:
                        span.set_attribute("input", str(input_data))
                except:
                    pass
            
            yield span
            
            # 记录输出
            if output_data is not None:
                try:
                    if isinstance(output_data, dict):
                        span.set_outputs(output_data)
                    else:
                        span.set_attribute("output", str(output_data))
                except:
                    pass
        except Exception as e:
            # 记录异常
            span.set_attribute("error", str(e))
            raise


@contextlib.contextmanager
def agent_span(name: str, tools: Optional[List[str]] = None, instructions: Optional[str] = None):
    """
    为代理执行创建一个追踪span
    
    Args:
        name: 代理名称
        tools: 可用工具列表
        instructions: 代理指令
    """
    with mlflow.start_span(name=f"Agent:{name}") as span:
        span.set_attribute("agent_name", name)
        
        if tools:
            span.set_attribute("tools", str(tools))
        
        if instructions:
            span.set_attribute("instructions", instructions)
        
        try:
            yield span
        except Exception as e:
            span.set_attribute("error", str(e))
            raise


@contextlib.contextmanager
def handoff_span(from_agent: str, to_agent: str):
    """
    为代理之间的转交创建一个追踪span
    
    Args:
        from_agent: 源代理名称
        to_agent: 目标代理名称
    """
    with mlflow.start_span(name=f"Handoff:{from_agent}->{to_agent}") as span:
        span.set_attribute("from_agent", from_agent)
        span.set_attribute("to_agent", to_agent)
        
        try:
            yield span
        except Exception as e:
            span.set_attribute("error", str(e))
            raise


@contextlib.contextmanager
def step_span(name: str, description: Optional[str] = None):
    """
    为工作流步骤创建一个追踪span
    
    Args:
        name: 步骤名称
        description: 步骤描述
    """
    with mlflow.start_span(name=f"Step:{name}") as span:
        if description:
            span.set_attribute("description", description)
        
        try:
            yield span
        except Exception as e:
            span.set_attribute("error", str(e))
            raise


def traced_function_tool(func: F) -> F:
    """
    装饰器，为function_tool添加MLflow追踪功能
    
    Args:
        func: 要追踪的函数
    
    Returns:
        带追踪功能的function_tool
    """
    # 应用原始的function_tool装饰器
    traced_func = function_tool(func)
    
    # 获取原始的on_invoke_tool方法
    original_invoke = traced_func.on_invoke_tool
    
    # 创建新的带追踪的on_invoke_tool方法
    async def traced_on_invoke_tool(ctx, input_str):
        # 记录工具调用
        with mlflow.start_span(name=f"Tool:{func.__name__}") as span:
            # 尝试记录参数
            try:
                # 尝试解析输入参数
                params = json.loads(input_str) if input_str else {}
                span.set_inputs(params)
            except:
                pass
            
            # 调用原始方法
            result = await original_invoke(ctx, input_str)
            
            # 记录结果
            try:
                span.set_outputs({"result": result})
            except:
                pass
            
            return result
    
    # 替换方法
    traced_func.on_invoke_tool = traced_on_invoke_tool
    
    return cast(F, traced_func)


def traced_handoff(agent: Agent, input_filter: Optional[Callable[[HandoffInputData], HandoffInputData]] = None):
    """
    为handoff添加MLflow追踪功能
    
    Args:
        agent: 目标代理
        input_filter: 输入过滤器
    
    Returns:
        带追踪功能的handoff对象
    """
    handoff_obj = handoff(agent, input_filter=input_filter)
    original_handler = handoff_obj.on_invoke_handoff
    
    # 创建新的带追踪的handler
    async def traced_handler(agent_state, input_message_data):
        from_agent = agent_state.name if hasattr(agent_state, "name") else "未命名代理"
        to_agent = agent.name if hasattr(agent, "name") else "未命名代理"
        
        with handoff_span(from_agent, to_agent):
            with mlflow.start_span(name="Handoff输入") as span:
                try:
                    span.set_attribute("input_data", str(input_message_data))
                except:
                    pass
            
            # 如果存在过滤器，记录过滤过程
            if input_filter:
                with mlflow.start_span(name="消息过滤器"):
                    # 在这里不调用过滤器，因为原始handler会处理
                    pass
            
            # 调用原始handler
            result = await original_handler(agent_state, input_message_data)
            
            with mlflow.start_span(name="Handoff输出") as span:
                try:
                    span.set_attribute("result", str(result))
                except:
                    pass
            
            return result
    
    # 替换handler
    handoff_obj.on_invoke_handoff = traced_handler
    
    return handoff_obj


# 添加对Runner.run方法的追踪装饰器
def traced_runner():
    """
    替换Runner.run方法，添加MLflow追踪功能
    """
    original_run = Runner.run
    
    async def traced_run(agent, *args, **kwargs):
        """添加追踪功能的Runner.run方法"""
        agent_name = agent.name if hasattr(agent, "name") else "未命名代理"
        tools = [t.name for t in agent.tools] if hasattr(agent, "tools") and agent.tools else []
        
        with agent_span(agent_name, tools):
            # 记录代理的指令
            with mlflow.start_span(name="代理指令") as span:
                span.set_attribute("instructions", agent.instructions if hasattr(agent, "instructions") else "")
            
            # 调用原始的run方法
            result = await original_run(agent, *args, **kwargs)
            
            # 记录输出
            with mlflow.start_span(name="代理输出") as span:
                span.set_attribute("output", result.final_output if hasattr(result, "final_output") else "")
            
            return result
    
    # 替换原始Runner.run方法
    Runner.run = traced_run
    
    return original_run


# 恢复原始Runner.run方法的函数
def restore_runner(original_run):
    """
    恢复原始的Runner.run方法
    
    Args:
        original_run: 原始的Runner.run方法
    """
    Runner.run = original_run 