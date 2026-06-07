from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PySide6.QtGui import QFont, QColor, QBrush
from PySide6.QtCore import Qt
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.ui.tabs.base_tab import BaseTab
from app.common import (
    table_utils, message_utils, ui_utils
)
from app.services import InspectionService
from app.db.database import InspectionPlanRepository
from app.ui.advanced_dialogs import InspectionPlanDialog


PLAN_STATUSES = ["待执行", "已提醒", "执行中", "已完成", "已取消"]


class InspectionTab(BaseTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.btn_add_plan = QPushButton("➕ 新增计划")
        self.btn_add_plan.setStyleSheet("background-color: #27ae60; color: white; padding: 6px 16px;")
        self.btn_add_plan.clicked.connect(self._on_add_plan)
        btn_row.addWidget(self.btn_add_plan)

        self.btn_edit_plan = QPushButton("✏ 编辑")
        self.btn_edit_plan.clicked.connect(self._on_edit_plan)
        btn_row.addWidget(self.btn_edit_plan)

        self.btn_delete_plan = QPushButton("🗑 删除")
        self.btn_delete_plan.clicked.connect(self._on_delete_plan)
        btn_row.addWidget(self.btn_delete_plan)

        self.btn_complete_plan = QPushButton("✅ 标记完成")
        self.btn_complete_plan.clicked.connect(self._on_complete_plan)
        btn_row.addWidget(self.btn_complete_plan)

        btn_row.addWidget(QLabel("状态筛选:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem("全部", None)
        for s in PLAN_STATUSES:
            self.status_filter.addItem(s, s)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        btn_row.addWidget(self.status_filter)

        btn_row.addStretch()
        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.clicked.connect(self.refresh)
        btn_row.addWidget(self.btn_refresh)
        layout.addLayout(btn_row)

        self.reminder_banner = QLabel("")
        self.reminder_banner.setStyleSheet("""
            padding: 10px; background: #fff3cd; border: 1px solid #ffc107;
            border-radius: 4px; color: #856404; font-weight: bold;
        """)
        self.reminder_banner.hide()
        layout.addWidget(self.reminder_banner)

        self.table = QTableWidget()
        table_utils.setup_table_style(self.table)
        self.table.doubleClicked.connect(self._on_edit_plan)
        layout.addWidget(self.table, stretch=1)

    def refresh(self) -> None:
        status = self.status_filter.currentData()
        plans = InspectionService.get_inspection_plans(status=status)

        headers = ["ID", "计划日期", "类型", "状态", "建筑", "构件", "操作人员", "提前提醒", "描述"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(plans))

        status_colors = {
            "待执行": QColor(52, 152, 219),
            "已提醒": QColor(241, 196, 15),
            "执行中": QColor(155, 89, 182),
            "已完成": QColor(46, 204, 113),
            "已取消": QColor(149, 165, 166)
        }
        bold_font = QFont("", 10, QFont.Bold)

        for row, plan in enumerate(plans):
            self.table.setItem(row, 0, QTableWidgetItem(str(plan["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(plan.get("plan_date", "")[:10]))
            self.table.setItem(row, 2, QTableWidgetItem(plan.get("plan_type", "")))

            status_item = QTableWidgetItem(plan.get("status", ""))
            color = status_colors.get(plan.get("status", ""), QColor(0, 0, 0))
            status_item.setForeground(QBrush(color))
            status_item.setFont(bold_font)
            self.table.setItem(row, 3, status_item)

            self.table.setItem(row, 4, QTableWidgetItem(plan.get("building_name", "") or "-"))
            comp_text = f"{plan.get('component_code', '') or ''} {plan.get('component_name', '') or ''}".strip()
            self.table.setItem(row, 5, QTableWidgetItem(comp_text or "-"))
            self.table.setItem(row, 6, QTableWidgetItem(plan.get("operator", "") or "-"))
            self.table.setItem(row, 7, QTableWidgetItem(f"{plan.get('reminder_days', 7)}天"))
            self.table.setItem(row, 8, QTableWidgetItem(plan.get("description", "") or "-"))

        table_utils.resize_table_columns(self.table, "resize_to_contents")
        self.table.horizontalHeader().setStretchLastSection(True)
        self._check_reminders()

    def _check_reminders(self) -> None:
        upcoming = InspectionService.get_upcoming_plans()
        if upcoming:
            msg = f"⚠ 有 {len(upcoming)} 个巡检计划即将到期或待执行！"
            for p in upcoming[:3]:
                msg += f"\n  • {p.get('plan_date', '')[:10]} - {p.get('plan_type', '')}"
            if len(upcoming) > 3:
                msg += f"\n  ... 还有 {len(upcoming) - 3} 个计划"
            self.reminder_banner.setText(msg)
            self.reminder_banner.show()
        else:
            self.reminder_banner.hide()

    def _get_selected_plan_id(self) -> Optional[int]:
        return table_utils.get_selected_row_id(self.table)

    def _get_selected_plan_ids(self) -> List[int]:
        return table_utils.get_selected_row_ids(self.table)

    def _on_add_plan(self) -> None:
        dlg = InspectionPlanDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                InspectionService.create_plan(**data)
                message_utils.show_info(self, "成功", "巡检计划已创建")
                self.refresh()
                self.notify_data_changed()
            except Exception as e:
                message_utils.show_error(self, "错误", f"创建失败: {str(e)}")

    def _on_edit_plan(self) -> None:
        plan_id = self._get_selected_plan_id()
        if not plan_id:
            message_utils.show_warning(self, "提示", "请选择要编辑的巡检计划")
            return
        plan = InspectionPlanRepository.get_by_id(plan_id)
        if not plan:
            return
        dlg = InspectionPlanDialog(self, plan=plan)
        if dlg.exec():
            data = dlg.get_data()
            try:
                InspectionService.update_plan(plan_id, **data)
                message_utils.show_info(self, "成功", "巡检计划已更新")
                self.refresh()
                self.notify_data_changed()
            except Exception as e:
                message_utils.show_error(self, "错误", f"更新失败: {str(e)}")

    def _on_delete_plan(self) -> None:
        ids = self._get_selected_plan_ids()
        if not ids:
            message_utils.show_warning(self, "提示", "请选择要删除的巡检计划")
            return
        if not message_utils.confirm_delete(self, len(ids), "巡检计划"):
            return
        deleted = 0
        for pid in ids:
            if InspectionService.delete_plan(pid):
                deleted += 1
        message_utils.show_info(self, "成功", f"已删除 {deleted} 个巡检计划")
        self.refresh()
        self.notify_data_changed()

    def _on_complete_plan(self) -> None:
        ids = self._get_selected_plan_ids()
        if not ids:
            message_utils.show_warning(self, "提示", "请选择要标记完成的巡检计划")
            return
        updated = 0
        for pid in ids:
            if InspectionService.update_plan(
                pid, status="已完成",
                executed_at=datetime.now().isoformat()
            ):
                updated += 1
        message_utils.show_info(self, "成功", f"已标记 {updated} 个计划为完成状态")
        self.refresh()
        self.notify_data_changed()
