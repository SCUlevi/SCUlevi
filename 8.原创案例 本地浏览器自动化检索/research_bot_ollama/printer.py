from typing import Any

from rich.console import Console, Group
from rich.live import Live
from rich.spinner import Spinner


class Printer:
    def __init__(self, console: Console):
        """
        初始化Printer对象
        
        参数:
            console: Rich库的Console对象，用于控制终端输出
        """
        self.live = Live(console=console)
        self.items: dict[str, tuple[str, bool]] = {}
        self.hide_done_ids: set[str] = set()
        self.live.start()

    def end(self) -> None:
        """停止实时显示"""
        self.live.stop()

    def hide_done_checkmark(self, item_id: str) -> None:
        """
        设置某个项目完成后不显示勾选标记
        
        参数:
            item_id: 项目的唯一标识符
        """
        self.hide_done_ids.add(item_id)

    def update_item(
        self, item_id: str, content: str, is_done: bool = False, hide_checkmark: bool = False
    ) -> None:
        """
        更新项目的内容和状态
        
        参数:
            item_id: 项目的唯一标识符
            content: 项目的文本内容
            is_done: 项目是否已完成，默认为False
            hide_checkmark: 是否隐藏完成标记，默认为False
        """
        self.items[item_id] = (content, is_done)
        if hide_checkmark:
            self.hide_done_ids.add(item_id)
        self.flush()

    def mark_item_done(self, item_id: str) -> None:
        """
        将项目标记为已完成
        
        参数:
            item_id: 项目的唯一标识符
        """
        self.items[item_id] = (self.items[item_id][0], True)
        self.flush()

    def flush(self) -> None:
        """刷新并更新终端显示的内容"""
        renderables: list[Any] = []
        for item_id, (content, is_done) in self.items.items():
            if is_done:
                prefix = "✅ " if item_id not in self.hide_done_ids else ""
                renderables.append(prefix + content)
            else:
                renderables.append(Spinner("dots", text=content))
        self.live.update(Group(*renderables))
