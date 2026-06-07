from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Qt
from typing import List, Dict, Any, Optional
import sys
import os
import subprocess

from app.ui.tabs.base_tab import BaseTab
from app.common import (
    table_utils, message_utils, ui_utils
)
from app.services import ArchiveService
from app.db.database import ReportArchiveRepository


ARCHIVE_TYPES = ["建筑巡检报告", "对比分析报告", "病害处置报告", "综合汇总报告", "闭环绩效报告", "处置效果报告", "资源统计报告"]


class ArchiveTab(BaseTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.btn_open = QPushButton("📂 打开文件")
        self.btn_open.clicked.connect(self._on_open_file)
        btn_row.addWidget(self.btn_open)

        self.btn_delete = QPushButton("🗑 删除记录")
        self.btn_delete.clicked.connect(self._on_delete)
        btn_row.addWidget(self.btn_delete)

        btn_row.addWidget(QLabel("类型筛选:"))
        self.type_filter = QComboBox()
        self.type_filter.addItem("全部", None)
        for t in ARCHIVE_TYPES:
            self.type_filter.addItem(t, t)
        self.type_filter.currentIndexChanged.connect(self.refresh)
        btn_row.addWidget(self.type_filter)

        btn_row.addStretch()
        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.clicked.connect(self.refresh)
        btn_row.addWidget(self.btn_refresh)
        layout.addLayout(btn_row)

        self.table = QTableWidget()
        table_utils.setup_table_style(self.table)
        self.table.doubleClicked.connect(self._on_open_file)
        layout.addWidget(self.table, stretch=1)

    def refresh(self) -> None:
        report_type = self.type_filter.currentData()
        archives = ArchiveService.get_archives(report_type=report_type)

        headers = ["ID", "报告类型", "文件名", "建筑", "构件", "文件大小(KB)", "创建时间", "描述"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(archives))

        for row, a in enumerate(archives):
            self.table.setItem(row, 0, QTableWidgetItem(str(a["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(a.get("report_type", "")))
            self.table.setItem(row, 2, QTableWidgetItem(a.get("file_name", "")))
            self.table.setItem(row, 3, QTableWidgetItem(a.get("building_name", "") or "-"))
            comp_text = f"{a.get('component_code', '') or ''} {a.get('component_name', '') or ''}".strip()
            self.table.setItem(row, 4, QTableWidgetItem(comp_text or "-"))
            size_kb = round((a.get("file_size") or 0) / 1024, 1)
            self.table.setItem(row, 5, QTableWidgetItem(f"{size_kb}"))
            self.table.setItem(row, 6, QTableWidgetItem(a.get("created_at", "")[:19]))
            self.table.setItem(row, 7, QTableWidgetItem(a.get("description", "") or "-"))

        table_utils.resize_table_columns(self.table, "resize_to_contents")
        self.table.horizontalHeader().setStretchLastSection(True)

    def _get_selected_archive_id(self) -> Optional[int]:
        return table_utils.get_selected_row_id(self.table)

    def _get_selected_archive_ids(self) -> List[int]:
        return table_utils.get_selected_row_ids(self.table)

    def _on_open_file(self) -> None:
        archive_id = self._get_selected_archive_id()
        if not archive_id:
            message_utils.show_warning(self, "提示", "请选择要打开的归档记录")
            return
        archive = ReportArchiveRepository.get_by_id(archive_id)
        if not archive:
            return
        file_path = archive.get("file_path", "")
        if not file_path or not os.path.exists(file_path):
            message_utils.show_warning(self, "提示", "归档文件不存在或已被移动")
            return

        try:
            if sys.platform.startswith("darwin"):
                subprocess.run(["open", file_path])
            elif os.name == "nt":
                os.startfile(file_path)
            else:
                subprocess.run(["xdg-open", file_path])
        except Exception:
            message_utils.show_info(self, "文件位置", f"文件路径:\n{file_path}")

    def _on_delete(self) -> None:
        ids = self._get_selected_archive_ids()
        if not ids:
            message_utils.show_warning(self, "提示", "请选择要删除的归档记录")
            return
        reply = message_utils.confirm_action(
            self,
            f"确定要删除选中的 {len(ids)} 条归档记录吗？\n（注意：仅删除数据库记录，不会删除磁盘文件）",
            "确认删除"
        )
        if not reply:
            return
        deleted = 0
        for aid in ids:
            if ArchiveService.delete_archive(aid):
                deleted += 1
        message_utils.show_info(self, "成功", f"已删除 {deleted} 条归档记录")
        self.refresh()
        self.notify_data_changed()
