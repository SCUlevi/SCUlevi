from __future__ import annotations

import asyncio
import time
import os
import datetime
import random
from pathlib import Path

from rich.console import Console

from agents import Runner
# 导入MLflow追踪模块
from agents.mlflow_tracing import (
    setup_mlflow_tracking,
    mlflow_trace,
    traced_function_tool,
    traced_handoff,
    traced_runner,
    restore_runner,
    step_span
)
import mlflow

from .agents.planner_agent import WebSearchItem, WebSearchPlan, planner_agent
from .agents.search_agent import search_agent
from .agents.writer_agent import ReportData, writer_agent
from .printer import Printer


class ResearchManager:
    """
    研究管理器类
    
    负责协调整个研究过程，包括搜索规划、执行搜索、报告生成和保存。
    使用异步方法实现并发操作，提高效率和响应速度。
    """
    def __init__(self):
        # 初始化Rich控制台对象，用于美化终端输出
        self.console = Console()
        # 初始化打印工具，用于格式化和管理研究过程中的各种输出信息
        self.printer = Printer(self.console)

    async def run(self, query: str) -> None:
        """
        运行完整的研究流程
        
        参数:
            query: 用户的研究查询字符串
            
        流程:
            1. 初始化MLflow追踪
            2. 规划搜索策略
            3. 执行网络搜索
            4. 生成研究报告
            5. 保存研究结果
        """
        # 初始化MLflow追踪
        setup_mlflow_tracking(tracking_uri="mlruns", experiment_name="研究助手")
        
        # 替换Runner.run为带追踪的版本
        original_run = traced_runner()
        
        try:
            # 将整个运行过程追踪为单个工作流
            with mlflow_trace(workflow_name=f"研究查询: {query}"):
                # 显示研究开始消息
                self.printer.update_item(
                    "starting",
                    "开始研究...",
                    is_done=True,
                    hide_checkmark=True,
                )
                
                try:
                    # 规划搜索 - 使用规划代理生成搜索计划
                    search_plan = await self._plan_searches(query)
                    
                    # 限制搜索数量 - 只选取前5条搜索，避免过多任务导致超时
                    if len(search_plan.searches) > 5:
                        self.printer.update_item(
                            "planning",
                            f"为提高稳定性，将只执行前5条搜索（共计划了{len(search_plan.searches)}条）",
                            is_done=True,
                        )
                        search_plan.searches = search_plan.searches[:5]
                    
                    # 执行搜索 - 并行执行所有搜索任务
                    search_results = await self._perform_searches(search_plan)
                    
                    # 生成报告 - 基于搜索结果生成研究报告
                    report = await self._write_report(query, search_results)

                    # 显示报告摘要
                    final_report = f"报告摘要\n\n{report.short_summary}"
                    self.printer.update_item("final_report", final_report, is_done=True)

                    # 保存报告到output_report目录
                    await self._save_report(query, report)
                    
                    # 结束打印进度
                    self.printer.end()

                    # 输出完整报告内容
                    print("\n\n=====报告=====\n\n")
                    print(f"报告: {report.markdown_report}")
                    print("\n\n=====后续问题=====\n\n")
                    follow_up_questions = "\n".join(report.follow_up_questions)
                    print(f"后续问题: {follow_up_questions}")
                    
                except Exception as e:
                    # 错误处理 - 显示错误信息并结束进度显示
                    self.printer.update_item("error", f"研究过程中出错: {str(e)}", is_done=True)
                    self.printer.end()
                    print(f"\n遇到错误: {str(e)}")
        finally:
            # 恢复原始的Runner.run方法
            restore_runner(original_run)

    async def _plan_searches(self, query: str) -> WebSearchPlan:
        """
        规划搜索策略
        
        参数:
            query: 用户查询字符串
            
        返回:
            WebSearchPlan: 包含多个搜索项的搜索计划
            
        说明:
            使用planner_agent来生成搜索计划，包含最多3次重试机制
        """
        # 添加重试逻辑
        max_attempts = 3
        
        with step_span(name="规划搜索策略"):
            for attempt in range(max_attempts):
                try:
                    # 更新规划状态
                    self.printer.update_item("planning", f"规划搜索中... (尝试 {attempt+1}/{max_attempts})")
                    
                    # 调用规划代理生成搜索计划
                    result = await Runner.run(
                        planner_agent,
                        f"Query: {query}",
                    )
                    
                    # 更新计划完成状态
                    self.printer.update_item(
                        "planning",
                        f"将执行 {len(result.final_output.searches)} 次搜索",
                        is_done=True,
                    )
                    
                    # 返回搜索计划
                    return result.final_output_as(WebSearchPlan)
                except Exception as e:
                    if attempt == max_attempts - 1:  # 最后一次尝试失败
                        raise Exception(f"规划搜索失败: {str(e)}")
                    else:
                        # 显示重试信息
                        self.printer.update_item("planning", f"规划搜索尝试 {attempt+1} 失败: {str(e)}，正在重试...")
                        await asyncio.sleep(2)  # 等待一下再重试

    async def _perform_searches(self, search_plan: WebSearchPlan) -> list[str]:
        """
        执行搜索计划中的所有搜索
        
        参数:
            search_plan: 搜索计划对象，包含多个搜索项
            
        返回:
            list[str]: 搜索结果列表
            
        说明:
            并行执行所有搜索，支持超时控制和错误处理
        """
        with step_span(name="执行网络搜索"):
            # 初始化搜索状态
            self.printer.update_item("searching", "搜索中...")
            num_completed = 0
            
            # 创建并行搜索任务
            tasks = [asyncio.create_task(self._search(item)) for item in search_plan.searches]
            results = []
            
            # 设置超时时间
            search_timeout = 60  # 单位：秒
            
            # 处理完成的任务
            for task in asyncio.as_completed(tasks):
                try:
                    # 添加超时机制
                    result = await asyncio.wait_for(task, timeout=search_timeout)
                    if result is not None and result.strip():  # 确保结果非空
                        # 限制单个搜索结果的长度
                        if len(result) > 1000:
                            result = result[:997] + "..."
                        results.append(result)
                except asyncio.TimeoutError:
                    # 处理搜索超时
                    self.printer.update_item(
                        "searching", f"搜索超时，跳过此项"
                    )
                except Exception as e:
                    # 处理搜索错误
                    self.printer.update_item(
                        "searching", f"搜索出错: {str(e)}，跳过此项"
                    )
                
                # 更新完成状态
                num_completed += 1
                self.printer.update_item(
                    "searching", f"搜索中... {num_completed}/{len(tasks)} 已完成"
                )
            
            # 标记搜索完成
            self.printer.mark_item_done("searching")
            
            # 如果没有获取到任何结果，返回一个默认结果
            if not results:
                return ["未能获取到有效的搜索结果。将基于现有知识生成报告。"]
                
            return results

    async def _search(self, item: WebSearchItem) -> str | None:
        """
        执行单个搜索项
        
        参数:
            item: 搜索项对象，包含查询字符串和搜索原因
            
        返回:
            str | None: 搜索结果文本或None（如果搜索失败）
        """
        input = f"Search term: {item.query}\nReason for searching: {item.reason}"
        try:
            # 记录搜索详情
            with mlflow.start_span(name=f"搜索: {item.query}") as span:
                span.set_attribute("search_query", item.query)
                span.set_attribute("search_reason", item.reason)
                
                # 使用预定义的搜索代理执行搜索
                result = await Runner.run(
                    search_agent,
                    input,
                )
                
                # 记录搜索结果状态
                success = result and str(result.final_output).strip() != ""
                span.set_attribute("search_success", success)
                
                return str(result.final_output)
        except Exception as e:
            # 记录搜索错误
            print(f"搜索出错: {str(e)}")
            return None

    async def _write_report(self, query: str, search_results: list[str]) -> ReportData:
        """
        生成研究报告
        
        参数:
            query: 原始查询字符串
            search_results: 搜索结果列表
            
        返回:
            ReportData: 报告数据对象，包含摘要、正文和后续问题
            
        说明:
            使用writer_agent生成报告，包含重试机制和内容验证
        """
        with step_span(name="生成研究报告"):
            # 添加重试逻辑
            max_attempts = 3
            
            # 准备输入数据，限制大小
            limited_results = []
            total_length = 0
            max_total_length = 4000  # 限制搜索结果总长度
            
            # 记录搜索结果统计
            with mlflow.start_span(name="准备报告输入数据") as span:
                span.set_attribute("total_search_results", len(search_results))
                
                # 限制搜索结果总长度，避免超出模型输入限制
                for result in search_results:
                    # 如果添加这个结果会超出总长度限制，则停止添加
                    if total_length + len(result) > max_total_length:
                        limited_results.append("(更多搜索结果被省略以避免超出长度限制)")
                        break
                    
                    limited_results.append(result)
                    total_length += len(result)
                
                span.set_attribute("used_search_results", len(limited_results))
                span.set_attribute("input_data_length", total_length)
            
            # 准备输入提示
            input = f"Original query: {query}\nSummarized search results: {limited_results}"
            
            # 尝试生成报告，最多重试max_attempts次
            for attempt in range(max_attempts):
                try:
                    # 更新报告生成状态
                    self.printer.update_item("writing", f"思考报告内容中... (尝试 {attempt+1}/{max_attempts})")
                    self.printer.update_item("writing", "生成报告中，请稍等...")
                    
                    # 调用写作代理生成报告
                    with mlflow.start_span(name=f"报告生成尝试 {attempt+1}") as span:
                        result = await Runner.run(
                            writer_agent,
                            input,
                        )
                        
                        # 验证报告内容是否完整
                        report = result.final_output_as(ReportData)
                        
                        # 检查报告内容是否包含占位符或过于简短
                        has_placeholder = ("此处应包含" in report.markdown_report or 
                                           "(在此处填写" in report.markdown_report)
                        is_too_short = len(report.markdown_report) < 200
                        
                        span.set_attribute("has_placeholder", has_placeholder)
                        span.set_attribute("is_too_short", is_too_short)
                        span.set_attribute("report_length", len(report.markdown_report))
                        
                        if has_placeholder or is_too_short:
                            if attempt < max_attempts - 1:  # 如果不是最后一次尝试，重试
                                self.printer.update_item("writing", "检测到报告内容不完整，重新尝试...")
                                await asyncio.sleep(2)
                                span.set_attribute("retry_needed", True)
                                continue
                            else:  # 最后一次尝试，增强提示
                                self.printer.update_item("writing", "尝试增强提示生成完整报告...")
                                span.set_attribute("enhanced_prompt", True)
                                # 增强提示，明确指出不要使用占位符
                                enhanced_input = input + "\n\n重要提示：请生成包含实际内容的完整报告，每个部分都必须有具体内容，不要使用占位符或格式说明文本。"
                                result = await Runner.run(writer_agent, enhanced_input)
                                report = result.final_output_as(ReportData)
                    
                    # 标记报告生成完成
                    self.printer.mark_item_done("writing")
                    return report
                    
                except Exception as e:
                    if attempt == max_attempts - 1:  # 最后一次尝试失败
                        # 创建一个简单的默认报告
                        self.printer.update_item("writing", f"生成报告失败: {str(e)}，创建默认报告", is_done=True)
                        
                        # 记录错误信息
                        with mlflow.start_span(name="创建默认报告") as span:
                            span.set_attribute("error", str(e))
                            
                            # 返回默认报告数据
                            return ReportData(
                                short_summary=f"由于技术原因，无法生成完整报告。查询内容：{query}",
                                markdown_report=f"# 报告生成失败\n\n查询: {query}\n\n由于模型或网络问题，无法生成完整报告。我们收集到了以下搜索结果：\n\n" + 
                                            "\n\n---\n\n".join(limited_results),
                                follow_up_questions=["请重试研究查询", "尝试简化您的搜索主题", "尝试将查询拆分为多个较小的查询"]
                            )
                    else:
                        # 显示重试信息
                        self.printer.update_item("writing", f"生成报告尝试 {attempt+1} 失败: {str(e)}，正在重试...")
                        await asyncio.sleep(3)  # 等待一下再重试

    async def _save_report(self, query: str, report: ReportData) -> None:
        """
        保存报告到文件系统
        
        参数:
            query: 原始查询字符串
            report: 报告数据对象
            
        说明:
            将报告保存为Markdown和纯文本两种格式
        """
        with step_span(name="保存研究报告"):
            # 创建output_report目录（如果不存在）
            output_dir = Path(__file__).parent / "output_report"
            output_dir.mkdir(exist_ok=True)
            
            # 生成文件名（基于查询和时间戳）
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            query_slug = query.lower().replace(" ", "_")[:30]
            base_filename = f"{timestamp}_{query_slug}"
            
            try:
                # 记录报告统计信息
                with mlflow.start_span(name="写入报告文件") as span:
                    # 记录报告元数据
                    span.set_attribute("report_summary_length", len(report.short_summary))
                    span.set_attribute("report_content_length", len(report.markdown_report))
                    span.set_attribute("follow_up_questions_count", len(report.follow_up_questions))
                    
                    # 保存markdown版本
                    md_path = output_dir / f"{base_filename}.md"
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(f"# {query}\n\n")
                        f.write(f"## 摘要\n\n{report.short_summary}\n\n")
                        f.write(f"## 报告\n\n{report.markdown_report}\n\n")
                        f.write("## 后续研究问题\n\n")
                        for question in report.follow_up_questions:
                            f.write(f"- {question}\n")
                    
                    # 保存txt版本
                    txt_path = output_dir / f"{base_filename}.txt"
                    with open(txt_path, "w", encoding="utf-8") as f:
                        f.write(f"查询: {query}\n\n")
                        f.write(f"摘要:\n{report.short_summary}\n\n")
                        f.write(f"报告:\n{report.markdown_report}\n\n")
                        f.write("后续研究问题:\n")
                        for question in report.follow_up_questions:
                            f.write(f"- {question}\n")
                    
                    # 记录文件路径
                    span.set_attribute("markdown_path", str(md_path))
                    span.set_attribute("text_path", str(txt_path))
                
                # 输出保存位置信息
                print(f"\n报告已保存到: \n- {md_path}\n- {txt_path}")
            except Exception as e:
                # 处理保存错误
                print(f"保存报告时出错: {str(e)}")
                # 记录错误
                with mlflow.start_span(name="保存报告错误") as span:
                    span.set_attribute("error", str(e))
