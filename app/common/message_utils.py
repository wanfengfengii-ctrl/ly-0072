from PySide6.QtWidgets import QMessageBox
from typing import Optional


def show_info(parent: Optional[object], title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)


def show_warning(parent: Optional[object], title: str, message: str) -> None:
    QMessageBox.warning(parent, title, message)


def show_error(parent: Optional[object], title: str, message: str) -> None:
    QMessageBox.critical(parent, title, message)


def confirm_delete(parent: Optional[object], count: int = 1, item_name: str = "记录") -> bool:
    if count <= 1:
        msg = f"确定要删除该{item_name}吗？此操作不可撤销。"
    else:
        msg = f"确定要删除选中的 {count} 条{item_name}吗？此操作不可撤销。"
    reply = QMessageBox.question(
        parent,
        "确认删除",
        msg,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )
    return reply == QMessageBox.Yes


def confirm_action(parent: Optional[object], message: str, title: str = "确认操作") -> bool:
    reply = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )
    return reply == QMessageBox.Yes
