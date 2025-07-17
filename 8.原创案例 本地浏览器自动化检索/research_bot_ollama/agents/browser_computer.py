import asyncio 
 # 导入base64库，用于编码/解码
import base64 
from typing import Literal, Union 
# 导入Playwright异步API
from playwright.async_api import Browser, Page, Playwright, async_playwright  
# 从agents模块导入必要的类和类型
from agents import AsyncComputer, Button, Environment  

# 键盘映射，将常用键映射到Playwright支持的键
CUA_KEY_TO_PLAYWRIGHT_KEY = {
    "/": "Divide",
    "\\": "Backslash",
    "alt": "Alt",
    "arrowdown": "ArrowDown",
    "arrowleft": "ArrowLeft",
    "arrowright": "ArrowRight",
    "arrowup": "ArrowUp",
    "backspace": "Backspace",
    "capslock": "CapsLock",
    "cmd": "Meta",
    "ctrl": "Control",
    "delete": "Delete",
    "end": "End",
    "enter": "Enter",
    "esc": "Escape",
    "home": "Home",
    "insert": "Insert",
    "option": "Alt",
    "pagedown": "PageDown",
    "pageup": "PageUp",
    "shift": "Shift",
    "space": " ",
    "super": "Meta",
    "tab": "Tab",
    "win": "Meta",
}


class LocalPlaywrightComputer(AsyncComputer):
    """使用本地Playwright浏览器实现的计算机接口，用于网络搜索"""

    def __init__(self, start_url="https://www.bing.com"):
        """
        初始化LocalPlaywrightComputer对象
        
        参数:
            start_url: 启动浏览器后访问的初始URL，默认为必应搜索引擎
        """
        self._playwright: Union[Playwright, None] = None  # Playwright实例
        self._browser: Union[Browser, None] = None  # 浏览器实例
        self._page: Union[Page, None] = None  # 页面实例
        self._start_url = start_url  # 初始URL

    async def _get_browser_and_page(self) -> tuple[Browser, Page]:
        """
        初始化浏览器和页面的辅助方法
        
        返回:
            tuple: 包含浏览器和页面实例的元组
        """
        width, height = self.dimensions  # 获取浏览器窗口尺寸
        launch_args = [f"--window-size={width},{height}"]  # 设置浏览器窗口尺寸的启动参数
        browser = await self.playwright.chromium.launch(headless=False, args=launch_args)  # 启动有界面的Chrome浏览器
        page = await browser.new_page()  # 创建新页面
        await page.set_viewport_size({"width": width, "height": height})  # 设置视口大小
        await page.goto(self._start_url)  # 导航到初始URL
        return browser, page  # 返回浏览器和页面实例

    async def __aenter__(self):
        """
        异步上下文管理器的进入方法，用于初始化资源
        
        返回:
            self: 返回当前实例自身
        """
        # 启动Playwright并获取浏览器和页面
        self._playwright = await async_playwright().start()  # 启动Playwright
        self._browser, self._page = await self._get_browser_and_page()  # 获取浏览器和页面
        return self  # 返回实例自身

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器的退出方法，用于清理资源
        
        参数:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪信息
        """
        if self._browser:
            await self._browser.close()  # 关闭浏览器
        if self._playwright:
            await self._playwright.stop()  # 停止Playwright

    @property
    def playwright(self) -> Playwright:
        """
        获取Playwright实例的属性
        
        返回:
            Playwright: Playwright实例
        """
        assert self._playwright is not None  # 断言确保实例已初始化
        return self._playwright

    @property
    def browser(self) -> Browser:
        """
        获取浏览器实例的属性
        
        返回:
            Browser: 浏览器实例
        """
        assert self._browser is not None  
        return self._browser

    @property
    def page(self) -> Page:
        """
        获取页面实例的属性
        
        返回:
            Page: 页面实例
        """
        assert self._page is not None  
        return self._page

    @property
    def environment(self) -> Environment:
        """
        获取环境类型的属性
        
        返回:
            Environment: 环境类型为"browser"
        """
        return "browser"

    @property
    def dimensions(self) -> tuple[int, int]:
        """
        获取浏览器窗口尺寸的属性
        
        返回:
            tuple: 包含宽度和高度的元组
        """
        return (1024, 768)  # 返回固定的窗口尺寸

    async def screenshot(self) -> str:
        """
        捕获当前视口的截图
        
        返回:
            str: Base64编码的PNG图像
        """
        png_bytes = await self.page.screenshot(full_page=False)  # 获取当前视口的截图(非整页)
        return base64.b64encode(png_bytes).decode("utf-8")  # 将二进制数据编码为Base64字符串

    async def click(self, x: int, y: int, button: Button = "left") -> None:
        """
        在指定坐标点击鼠标按钮
        
        参数:
            x: 横坐标
            y: 纵坐标
            button: 鼠标按钮，默认为左键
        """
        playwright_button: Literal["left", "middle", "right"] = "left"  # 默认使用左键

        # Playwright只支持left, middle, right按钮
        if button in ("left", "right", "middle"):
            playwright_button = button  # type: ignore

        await self.page.mouse.click(x, y, button=playwright_button)  # 执行点击操作

    async def double_click(self, x: int, y: int) -> None:
        """
        在指定坐标双击鼠标
        
        参数:
            x: 横坐标
            y: 纵坐标
        """
        await self.page.mouse.dblclick(x, y)  # 执行双击操作

    async def scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        """
        在指定位置执行滚动操作
        
        参数:
            x: 鼠标横坐标
            y: 鼠标纵坐标
            scroll_x: 水平滚动距离
            scroll_y: 垂直滚动距离
        """
        await self.page.mouse.move(x, y)  # 将鼠标移到指定位置
        await self.page.evaluate(f"window.scrollBy({scroll_x}, {scroll_y})")  # 执行JavaScript滚动页面

    async def type(self, text: str) -> None:
        """
        在页面中键入文本
        
        参数:
            text: 要键入的文本
        """
        await self.page.keyboard.type(text)  # 使用键盘键入文本

    async def wait(self) -> None:
        """
        等待1秒钟
        """
        await asyncio.sleep(1)  # 暂停1秒钟

    async def move(self, x: int, y: int) -> None:
        """
        移动鼠标到指定坐标
        
        参数:
            x: 横坐标
            y: 纵坐标
        """
        await self.page.mouse.move(x, y)  # 移动鼠标到指定位置

    async def keypress(self, keys: list[str]) -> None:
        """
        按下一系列键
        
        参数:
            keys: 要按下的键列表
        """
        for key in keys:
            mapped_key = CUA_KEY_TO_PLAYWRIGHT_KEY.get(key.lower(), key)  # 将键名映射为Playwright支持的键名
            await self.page.keyboard.press(mapped_key)  # 按下键

    async def drag(self, path: list[tuple[int, int]]) -> None:
        """
        执行拖拽操作
        
        参数:
            path: 包含坐标点的列表，表示拖拽路径
        """
        if not path:
            return  # 如果路径为空，直接返回
        await self.page.mouse.move(path[0][0], path[0][1])  # 移动到起始点
        await self.page.mouse.down()  # 按下鼠标
        for px, py in path[1:]:  # 遍历路径上的其他点
            await self.page.mouse.move(px, py)  # 移动到每个点
        await self.page.mouse.up()  # 释放鼠标 