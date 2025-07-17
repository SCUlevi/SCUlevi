import asyncio
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Any

from agents import function_tool
from .browser_computer import LocalPlaywrightComputer

class BrowserSearchResult:
    """浏览器搜索结果类，用于存储和处理搜索结果"""
    
    def __init__(self):
        self.title = ""
        self.summary = ""
        self.snippets = []
        self.full_content = ""
    
    def __str__(self):
        if self.summary:
            return self.summary
        elif self.snippets:
            return "\n".join(self.snippets)
        else:
            return "未找到相关内容"

async def extract_search_results(computer: LocalPlaywrightComputer) -> BrowserSearchResult:
    """从搜索结果页面提取信息"""
    result = BrowserSearchResult()
    
    try:
        # 获取页面内容
        html_content = await computer.page.content()
        # 不再存储完整内容，减少内存占用
        # result.full_content = html_content
        
        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 尝试提取搜索结果（适用于多种搜索引擎）
        # Bing搜索结果
        search_results = soup.select('.b_algo, .b_attribution')
        if search_results:
            snippets = []
            for item in search_results:
                text = item.get_text(strip=True)
                if text and len(text) > 20:  # 忽略太短的内容
                    # 限制每个片段的长度
                    snippets.append(text[:200] + "..." if len(text) > 200 else text)
            result.snippets = snippets[:3]  # 减少为前3个结果
        
        # Google搜索结果
        if not result.snippets:
            search_results = soup.select('.g .VwiC3b, .g .GI74Re')
            if search_results:
                snippets = []
                for item in search_results:
                    text = item.get_text(strip=True)
                    if text and len(text) > 20:
                        # 限制每个片段的长度
                        snippets.append(text[:200] + "..." if len(text) > 200 else text)
                result.snippets = snippets[:3]
        
        # 通用提取方法（如果以上方法失败）
        if not result.snippets:
            # 查找所有段落并提取文本
            paragraphs = soup.find_all('p')
            snippets = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 30:  # 忽略太短的段落
                    # 限制每个片段的长度
                    snippets.append(text[:200] + "..." if len(text) > 200 else text)
            result.snippets = snippets[:3]
        
        # 生成摘要，总量控制更严格
        if result.snippets:
            result.summary = "搜索结果摘要:\n" + "\n".join([f"- {s[:100]}..." if len(s) > 100 else f"- {s}" for s in result.snippets])
        else:
            result.summary = "未能提取到有效的搜索结果。"
        
    except Exception as e:
        result.summary = f"提取搜索结果时出错: {str(e)}"
    
    return result

@function_tool
async def browser_search(search_query: str) -> str:
    """
    使用本地浏览器执行网络搜索并返回结果摘要。
    
    Args:
        search_query: 要搜索的查询词。
        
    Returns:
        搜索结果的摘要文本。
    """
    # 最多尝试3次
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # 使用上下文管理器确保资源正确释放
            async with LocalPlaywrightComputer(start_url="https://www.bing.com") as computer:
                try:
                    # 等待搜索框加载
                    await asyncio.sleep(2)
                    
                    # 查找并点击搜索框
                    # 尝试多种可能的选择器，兼容不同搜索引擎
                    try:
                        # Bing搜索框
                        search_box = await computer.page.query_selector('#sb_form_q')
                        if search_box:
                            await search_box.click()
                        else:
                            # 尝试直接点击页面中央位置
                            width, height = computer.dimensions
                            await computer.click(width // 2, height // 3)
                    except Exception:
                        # 如果无法找到特定元素，尝试点击页面中央
                        width, height = computer.dimensions
                        await computer.click(width // 2, height // 3)
                    
                    # 输入搜索词 - 限制长度
                    limited_query = search_query[:50] if len(search_query) > 50 else search_query
                    await computer.type(limited_query)
                    await asyncio.sleep(1)
                    
                    # 按回车键搜索
                    await computer.keypress(["enter"])
                    
                    # 等待搜索结果加载
                    await asyncio.sleep(5)
                    
                    # 提取搜索结果
                    search_result = await extract_search_results(computer)
                    
                    # 滚动页面以加载更多内容
                    await computer.scroll(0, 0, 0, 300)
                    await asyncio.sleep(2)
                    
                    # 再次提取结果（可能会有更多内容）
                    updated_result = await extract_search_results(computer)
                    if len(updated_result.snippets) > len(search_result.snippets):
                        search_result = updated_result
                    
                    return str(search_result)
                    
                except Exception as e:
                    if attempt == max_attempts - 1:  # 最后一次尝试
                        return f"浏览器搜索过程中出错: {str(e)}"
                    else:
                        print(f"搜索尝试 {attempt+1} 失败: {str(e)}，正在重试...")
                        await asyncio.sleep(2)  # 稍等一下再重试
        except Exception as e:
            if attempt == max_attempts - 1:  # 最后一次尝试
                return f"浏览器初始化出错: {str(e)}"
            else:
                print(f"浏览器初始化尝试 {attempt+1} 失败: {str(e)}，正在重试...")
                await asyncio.sleep(2)  # 稍等一下再重试 