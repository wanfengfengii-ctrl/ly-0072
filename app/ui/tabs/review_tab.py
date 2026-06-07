from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QInputDialog
)
from PySide6.QtGui import QFont, QColor, QBrush
from PySide6.QtCore import Qt
from typing import List, Dict, Any, Optional

from app.ui.tabs.base_tab import BaseTab
from app.common import (
    table_utils, message_utils, ui_utils
)
from app.services import InspectionService
from app.db.database import (
    AnomalyReviewRepository, SettingsRepository,
    ComponentRepository, RecordRepository
)
from app.ui.advanced_dialogs import AnomalyReviewDialog


REVIEW_STATUSES = ["待复核", "复核通过", "确认为风险", "误报"]


class ReviewTab(BaseTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_component_id: Optional[int] = None
        self._init_ui()
        self.refresh()

    def set_current_component(self, component_id: Optional[int]) -> None:
        self.current_component_id = component_id

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.btn_add_review = QPushButton("➕ 标记异常")
        self.btn_add_review.clicked.connect(self._on_add_review)
        btn_row.addWidget(self.btn_add_review)

        self.btn_review_selected = QPushButton("✏ 复核选中")
        self.btn_review_selected.setStyleSheet("background-color: #f39c12; color: white; padding: 6px 16px;")
        self.btn_review_selected.clicked.connect(self._on_review_selected)
        btn_row.addWidget(self.btn_review_selected)

        self.btn_delete_review = QPushButton("🗑 删除")
        self.btn_delete_review.clicked.connect(self._on_delete_review)
        btn_row.addWidget(self.btn_delete_review)

        btn_row.addWidget(QLabel("状态筛选:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("全部", None)
        for s in REVIEW_STATUSES:
            self.status_filter.addItem(s, s)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        btn_row.addWidget(self.status_filter)

        btn_row.addStretch()
        self.btn_auto_scan = QPushButton("🔍 自动扫描异常")
        self.btn_auto_scan.setStyleSheet("background-color: #e74c3c; color: white; padding: 6px 16px;")
        self.btn_auto_scan.clicked.connect(self._on_auto_scan)
        btn_row.addWidget(self.btn_auto_scan)

        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.clicked.connect(self.refresh)
        btn_row.addWidget(self.btn_refresh)
        layout.addLayout(btn_row)

        self.table = QTableWidget()
        table_utils.setup_table_style(self.table)
        self.table.doubleClicked.connect(self._on_review_selected)
        layout.addWidget(self.table, stretch=1)

    def refresh(self) -> None:
        status = self.status_filter.currentData()
        reviews = InspectionService.get_anomaly_reviews(status=status)

        headers = ["ID", "检测时间", "含水率(%)", "检测位置", "建筑", "构件", "复核状态", "复核人员", "是否误报"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(reviews))

        review_colors = {
            "待复核": QColor(231, 76, 60),
            "复核通过": QColor(46, 204, 113),
            "确认为风险": QColor(230, 126, 34),
            "误报": QColor(149, 165, 166)
        }
        threshold = SettingsRepository.get_moisture_threshold()
        bold_font = QFont("", 10, QFont.Bold)

        for row, r in enumerate(reviews):
            self.table.setItem(row, 0, QTableWidgetItem(str(r["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(r.get("measure_time", "")[:19]))

            moisture = r.get("moisture", 0)
            moist_item = QTableWidgetItem(f"{moisture:.1f}")
            if moisture > threshold:
                moist_item.setForeground(QBrush(ui_utils.RISK_COLORS["高风险"]))
                moist_item.setFont(bold_font)
            self.table.setItem(row, 2, moist_item)

            self.table.setItem(row, 3, QTableWidgetItem(r.get("measure_position", "") or "-"))
            self.table.setItem(row, 4, QTableWidgetItem(r.get("building_name", "") or "-"))
            comp_text = f"{r.get('component_code', '') or ''} {r.get('component_name', '') or ''}".strip()
            self.table.setItem(row, 5, QTableWidgetItem(comp_text or "-"))

            status_item = QTableWidgetItem(r.get("review_status", ""))
            color = review_colors.get(r.get("review_status", ""), QColor(0, 0, 0))
            status_item.setForeground(QBrush(color))
            status_item.setFont(bold_font)
            self.table.setItem(row, 6, status_item)

            self.table.setItem(row, 7, QTableWidgetItem(r.get("reviewer", "") or "-"))
            fa_text = "是" if r.get("is_false_alarm") else "否"
            self.table.setItem(row, 8, QTableWidgetItem(fa_text))

        table_utils.resize_table_columns(self.table, "resize_to_contents")
        self.table.horizontalHeader().setStretchLastSection(True)

    def _get_selected_review_id(self) -> Optional[int]:
        return table_utils.get_selected_row_id(self.table)

    def _get_selected_review_ids(self) -> List[int]:
        return table_utils.get_selected_row_ids(self.table)

    def _on_add_review(self) -> None:
        if not self.current_component_id:
            message_utils.show_warning(self, "提示", "请先在左侧选择一个构件")
            return
        records = RecordRepository.get_by_component(self.current_component_id)
        if not records:
            message_utils.show_warning(self, "提示", "该构件暂无检测记录")
            return

        items = [f"{r['measure_time'][:19]} | {r['measure_position']} | {r['moisture']}%" for r in records]
        item, ok = QInputDialog.getItem(self, "选择记录", "选择要标记为异常的检测记录:", items, 0, False)
        if not (ok and item):
            return
        idx = items.index(item)
        record = records[idx]
        existing = AnomalyReviewRepository.get_by_record(record["id"])
        if existing:
            message_utils.show_warning(self, "提示", "该记录已存在异常复核条目")
            return
        try:
            InspectionService.create_anomaly_review(record["id"], self.current_component_id)
            message_utils.show_info(self, "成功", "已标记为异常，待复核")
            self.refresh()
            self.notify_data_changed()
        except Exception as e:
            message_utils.show_error(self, "错误", f"操作失败: {str(e)}")

    def _on_review_selected(self) -> None:
        review_id = self._get_selected_review_id()
        if not review_id:
            message_utils.show_warning(self, "提示", "请选择要复核的异常记录")
            return
        review = AnomalyReviewRepository.get_by_id(review_id)
        if not review:
            return
        dlg = AnomalyReviewDialog(self, review=review)
        if dlg.exec():
            data = dlg.get_data()
            try:
                InspectionService.update_anomaly_review(review_id, **data)
                message_utils.show_info(self, "成功", "复核信息已更新")
                self.refresh()
                self.notify_data_changed()
            except Exception as e:
                message_utils.show_error(self, "错误", f"更新失败: {str(e)}")

    def _on_delete_review(self) -> None:
        ids = self._get_selected_review_ids()
        if not ids:
            message_utils.show_warning(self, "提示", "请选择要删除的异常复核记录")
            return
        if not message_utils.confirm_delete(self, len(ids), "复核记录"):
            return
        deleted = 0
        for rid in ids:
            if AnomalyReviewRepository.delete(rid):
                deleted += 1
        message_utils.show_info(self, "成功", f"已删除 {deleted} 条复核记录")
        self.refresh()
        self.notify_data_changed()

    def _on_auto_scan(self) -> None:
        components = ComponentRepository.get_all()
        threshold = SettingsRepository.get_moisture_threshold()

        if not message_utils.confirm_action(
            self,
            f"即将扫描全部 {len(components)} 个构件，自动识别含水率超过阈值 {threshold}% 的记录。\n是否继续？",
            "自动扫描异常"
        ):
            return

        scanned, added = InspectionService.auto_scan_anomalies()

        message_utils.show_info(
            self, "扫描完成",
            f"共扫描 {scanned} 条检测记录\n"
            f"新增异常待复核: {added} 条\n"
            f"请在「异常复核」标签页查看并处理"
        )
        self.refresh()
        self.notify_data_changed()
