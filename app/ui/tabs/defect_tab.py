from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget,
    QPushButton, QLabel, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from typing import Optional, Dict, Any, List

from app.common.table_utils import populate_table, setup_table_style, get_selected_row_id
from app.common.message_utils import show_info, show_warning, show_error, confirm_delete, confirm_action
from app.common.ui_utils import create_stat_card, update_stat_card

from app.services.defect_service import DefectService
from app.db.database import (
    DEFECT_TYPES, DEFECT_SEVERITIES, DEFECT_STATUSES,
    WORK_ORDER_STATUSES, BuildingRepository, EffectivenessEvaluationRepository,
    SettingsRepository
)
from app.ui.chart_widget import ChartWidget
from app.ui.advanced_dialogs import (
    DefectDialog, WorkOrderDialog, RectificationTrackDialog,
    AcceptanceDialog, EffectivenessEvalDialog, DefectDetailDialog
)
from app.ui.tabs.base_tab import BaseTab


class DefectTab(BaseTab):
    def __init__(self, parent: Optional[QWidget] = None):
        self.current_building_id: Optional[int] = None
        self.current_component_id: Optional[int] = None
        super().__init__(parent)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.reminder_banner = QLabel("")
        self.reminder_banner.setStyleSheet("""
            padding: 10px; background: #f8d7da; border: 1px solid #f5c6cb;
            border-radius: 4px; color: #721c24; font-weight: bold;
        """)
        self.reminder_banner.hide()
        layout.addWidget(self.reminder_banner)

        stat_row = QHBoxLayout()
        self.stat_total = create_stat_card("病害总数", "0", "#3498db")
        self.stat_pending = create_stat_card("待处置", "0", "#e74c3c")
        self.stat_processing = create_stat_card("处置中", "0", "#f39c12")
        self.stat_completed = create_stat_card("已完成", "0", "#27ae60")
        stat_row.addWidget(self.stat_total)
        stat_row.addWidget(self.stat_pending)
        stat_row.addWidget(self.stat_processing)
        stat_row.addWidget(self.stat_completed)
        layout.addLayout(stat_row)

        chart_splitter = QSplitter(Qt.Horizontal)
        self.status_chart = ChartWidget()
        self.type_chart = ChartWidget()
        self.moisture_chart = ChartWidget()
        chart_splitter.addWidget(self.status_chart)
        chart_splitter.addWidget(self.type_chart)
        chart_splitter.addWidget(self.moisture_chart)
        chart_splitter.setStretchFactor(0, 1)
        chart_splitter.setStretchFactor(1, 1)
        chart_splitter.setStretchFactor(2, 1)
        layout.addWidget(chart_splitter, stretch=1)

        self.detail_tabs = QTabWidget()

        defect_list_widget = QWidget()
        defect_list_layout = QVBoxLayout(defect_list_widget)

        defect_btn_row = QHBoxLayout()
        self.btn_add_defect = QPushButton("➕ 登记病害")
        self.btn_add_defect.setStyleSheet("background-color: #e74c3c; color: white; padding: 6px 16px;")
        defect_btn_row.addWidget(self.btn_add_defect)

        self.btn_edit_defect = QPushButton("✏ 编辑")
        defect_btn_row.addWidget(self.btn_edit_defect)

        self.btn_delete_defect = QPushButton("🗑 删除")
        defect_btn_row.addWidget(self.btn_delete_defect)

        self.btn_view_detail = QPushButton("📋 查看详情")
        defect_btn_row.addWidget(self.btn_view_detail)

        self.btn_create_workorder = QPushButton("🔧 创建工单")
        self.btn_create_workorder.setStyleSheet("background-color: #f39c12; color: white; padding: 6px 16px;")
        defect_btn_row.addWidget(self.btn_create_workorder)

        defect_btn_row.addWidget(QLabel("状态筛选:"))
        self.defect_status_filter = QComboBox()
        self.defect_status_filter.addItem("全部", None)
        for s in DEFECT_STATUSES:
            self.defect_status_filter.addItem(s, s)
        defect_btn_row.addWidget(self.defect_status_filter)

        defect_btn_row.addWidget(QLabel("类型筛选:"))
        self.defect_type_filter = QComboBox()
        self.defect_type_filter.addItem("全部", None)
        for t in DEFECT_TYPES:
            self.defect_type_filter.addItem(t, t)
        defect_btn_row.addWidget(self.defect_type_filter)

        defect_btn_row.addStretch()
        self.btn_refresh_defects = QPushButton("🔄 刷新")
        defect_btn_row.addWidget(self.btn_refresh_defects)

        defect_list_layout.addLayout(defect_btn_row)

        self.defect_table = QTableWidget()
        setup_table_style(self.defect_table)
        self.defect_table.doubleClicked.connect(self._on_view_detail)
        defect_list_layout.addWidget(self.defect_table, stretch=1)

        self.detail_tabs.addTab(defect_list_widget, "📋 病害登记")

        wo_list_widget = QWidget()
        wo_list_layout = QVBoxLayout(wo_list_widget)

        wo_btn_row = QHBoxLayout()
        self.btn_edit_workorder = QPushButton("✏ 编辑工单")
        wo_btn_row.addWidget(self.btn_edit_workorder)

        self.btn_delete_workorder = QPushButton("🗑 删除工单")
        wo_btn_row.addWidget(self.btn_delete_workorder)

        self.btn_start_workorder = QPushButton("▶ 开始处理")
        wo_btn_row.addWidget(self.btn_start_workorder)

        self.btn_add_tracking = QPushButton("📝 记录整改")
        self.btn_add_tracking.setStyleSheet("background-color: #3498db; color: white; padding: 6px 16px;")
        wo_btn_row.addWidget(self.btn_add_tracking)

        self.btn_to_accept = QPushButton("✅ 申请验收")
        wo_btn_row.addWidget(self.btn_to_accept)

        self.btn_do_acceptance = QPushButton("📝 验收")
        self.btn_do_acceptance.setStyleSheet("background-color: #27ae60; color: white; padding: 6px 16px;")
        wo_btn_row.addWidget(self.btn_do_acceptance)

        self.btn_do_eval = QPushButton("📊 效果评估")
        self.btn_do_eval.setStyleSheet("background-color: #9b59b6; color: white; padding: 6px 16px;")
        wo_btn_row.addWidget(self.btn_do_eval)

        wo_btn_row.addWidget(QLabel("状态筛选:"))
        self.wo_status_filter = QComboBox()
        self.wo_status_filter.addItem("全部", None)
        for s in WORK_ORDER_STATUSES:
            self.wo_status_filter.addItem(s, s)
        wo_btn_row.addWidget(self.wo_status_filter)

        wo_btn_row.addStretch()
        self.btn_refresh_workorders = QPushButton("🔄 刷新")
        wo_btn_row.addWidget(self.btn_refresh_workorders)

        wo_list_layout.addLayout(wo_btn_row)

        self.workorder_table = QTableWidget()
        setup_table_style(self.workorder_table)
        self.workorder_table.doubleClicked.connect(self._on_edit_workorder)
        wo_list_layout.addWidget(self.workorder_table, stretch=1)

        self.detail_tabs.addTab(wo_list_widget, "🔧 维修工单")

        layout.addWidget(self.detail_tabs, stretch=2)

    def _setup_connections(self) -> None:
        self.btn_add_defect.clicked.connect(self._on_add_defect)
        self.btn_edit_defect.clicked.connect(self._on_edit_defect)
        self.btn_delete_defect.clicked.connect(self._on_delete_defect)
        self.btn_view_detail.clicked.connect(self._on_view_detail)
        self.btn_create_workorder.clicked.connect(self._on_create_workorder)
        self.btn_refresh_defects.clicked.connect(self._refresh_defects)
        self.defect_status_filter.currentIndexChanged.connect(self._refresh_defects)
        self.defect_type_filter.currentIndexChanged.connect(self._refresh_defects)

        self.btn_edit_workorder.clicked.connect(self._on_edit_workorder)
        self.btn_delete_workorder.clicked.connect(self._on_delete_workorder)
        self.btn_start_workorder.clicked.connect(lambda: self._on_change_workorder_status("处理中"))
        self.btn_add_tracking.clicked.connect(self._on_add_tracking)
        self.btn_to_accept.clicked.connect(lambda: self._on_change_workorder_status("待验收"))
        self.btn_do_acceptance.clicked.connect(self._on_do_acceptance)
        self.btn_do_eval.clicked.connect(self._on_do_evaluation)
        self.btn_refresh_workorders.clicked.connect(self._refresh_workorders)
        self.wo_status_filter.currentIndexChanged.connect(self._refresh_workorders)

        self.detail_tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int) -> None:
        if self.detail_tabs.tabText(index).startswith("📋"):
            self._refresh_defects()
        elif self.detail_tabs.tabText(index).startswith("🔧"):
            self._refresh_workorders()

    def set_building_context(self, building_id: Optional[int] = None,
                             component_id: Optional[int] = None) -> None:
        self.current_building_id = building_id
        self.current_component_id = component_id
        self.refresh()

    def refresh(self) -> None:
        self._refresh_defects()
        self._refresh_workorders()

    def _refresh_defects(self) -> None:
        status_filter = self.defect_status_filter.currentData()
        type_filter = self.defect_type_filter.currentData()

        defects = DefectService.get_defects(
            status=status_filter, building_id=self.current_building_id,
            component_id=self.current_component_id, defect_type=type_filter
        )

        headers = ["ID", "建筑", "构件", "病害类型", "严重程度", "状态", "发现日期", "描述"]
        data = []
        sev_colors = {
            "轻微": QColor(39, 174, 96), "一般": QColor(243, 156, 18),
            "严重": QColor(230, 126, 34), "危急": QColor(231, 76, 60)
        }
        status_colors = {
            "待处置": QColor(231, 76, 60), "处置中": QColor(243, 156, 18),
            "待验收": QColor(52, 152, 219), "已验收": QColor(155, 89, 182),
            "已完成": QColor(39, 174, 96), "已关闭": QColor(149, 165, 166)
        }

        color_rules = {
            4: lambda val: sev_colors.get(val),
            5: lambda val: status_colors.get(val),
        }

        for d in defects:
            data.append([
                d["id"],
                d.get("building_name", "") or "-",
                f"{d.get('component_code', '') or ''} {d.get('component_name', '') or ''}".strip() or "-",
                d.get("defect_type", ""),
                d.get("severity", ""),
                d.get("status", ""),
                (d.get("discovery_date", "") or "")[:10],
                (d.get("description", "") or "")[:60],
            ])

        populate_table(self.defect_table, headers, data, color_rules)
        self.defect_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.defect_table.horizontalHeader().setStretchLastSection(True)

        for row in range(self.defect_table.rowCount()):
            for col in [4, 5]:
                item = self.defect_table.item(row, col)
                if item and item.foreground().color() != QColor(0, 0, 0):
                    item.setFont(self._bold_font())

        self._refresh_stats()
        self._check_overdue()
        self._refresh_charts()

    def _refresh_stats(self) -> None:
        stats = DefectService.get_statistics(building_id=self.current_building_id)
        update_stat_card(self.stat_total, str(stats.get("total", 0)))
        update_stat_card(self.stat_pending, str(stats.get("待处置", 0)))
        update_stat_card(self.stat_processing, str(stats.get("处置中", 0)))
        update_stat_card(self.stat_completed, str(stats.get("已完成", 0)))

    def _check_overdue(self) -> None:
        reminders = DefectService.get_overdue_reminders()
        if reminders:
            msg = f"⚠ 有 {len(reminders)} 个维修工单已超期，请及时处理！"
            for r in reminders[:3]:
                msg += f"\n  • {r.get('order_no', '')} - {r.get('title', '')} (截止: {str(r.get('deadline', ''))[:10]})"
            if len(reminders) > 3:
                msg += f"\n  ... 还有 {len(reminders) - 3} 个超期工单"
            self.reminder_banner.setText(msg)
            self.reminder_banner.show()
        else:
            self.reminder_banner.hide()

    def _refresh_charts(self) -> None:
        stats = DefectService.get_statistics(building_id=self.current_building_id)

        status_data: Dict[str, int] = {}
        for s in DEFECT_STATUSES:
            if stats.get(s, 0) > 0:
                status_data[s] = stats.get(s, 0)
        self.status_chart.plot_defect_status_pie(status_data)

        type_data = stats.get("by_type", {})
        self.type_chart.plot_defect_type_distribution(type_data)

        evals = EffectivenessEvaluationRepository.get_all(building_id=self.current_building_id)
        self.moisture_chart.plot_moisture_comparison(
            evals, SettingsRepository.get_moisture_threshold()
        )

    def _refresh_workorders(self) -> None:
        status_filter = self.wo_status_filter.currentData()

        workorders = DefectService.get_work_orders(
            status=status_filter, building_id=self.current_building_id
        )

        headers = ["ID", "工单编号", "标题", "病害类型", "优先级", "状态", "负责人", "派工日期", "截止日期"]
        data = []
        prio_colors = {
            "低": QColor(149, 165, 166), "中": QColor(52, 152, 219),
            "高": QColor(230, 126, 34), "紧急": QColor(231, 76, 60)
        }
        wo_status_colors = {
            "待处理": QColor(231, 76, 60), "处理中": QColor(243, 156, 18),
            "待验收": QColor(52, 152, 219), "已完成": QColor(39, 174, 96),
            "已取消": QColor(149, 165, 166)
        }

        color_rules = {
            4: lambda val: prio_colors.get(val),
            5: lambda val: wo_status_colors.get(val),
        }

        for w in workorders:
            data.append([
                w["id"],
                w.get("order_no", ""),
                w.get("title", ""),
                w.get("defect_type", "") or "",
                w.get("priority", ""),
                w.get("status", ""),
                w.get("assignee", "") or "-",
                (w.get("assign_date", "") or "")[:10],
                (w.get("deadline", "") or "")[:10],
            ])

        populate_table(self.workorder_table, headers, data, color_rules)
        self.workorder_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.workorder_table.horizontalHeader().setStretchLastSection(True)

        for row in range(self.workorder_table.rowCount()):
            for col in [4, 5]:
                item = self.workorder_table.item(row, col)
                if item and item.foreground().color() != QColor(0, 0, 0):
                    item.setFont(self._bold_font())

    def _get_selected_defect_id(self) -> Optional[int]:
        return get_selected_row_id(self.defect_table, 0)

    def _get_selected_workorder_id(self) -> Optional[int]:
        return get_selected_row_id(self.workorder_table, 0)

    def _on_add_defect(self) -> None:
        dlg = DefectDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                DefectService.create_defect(**data)
                show_info(self, "成功", "病害登记成功")
                self._refresh_defects()
            except Exception as e:
                show_error(self, "失败", f"登记失败: {str(e)}")

    def _on_edit_defect(self) -> None:
        did = self._get_selected_defect_id()
        if not did:
            show_warning(self, "提示", "请先选择要编辑的病害")
            return
        defect = DefectService.get_defect_by_id(did)
        if not defect:
            return
        dlg = DefectDialog(self, defect=defect)
        if dlg.exec():
            data = dlg.get_data()
            try:
                DefectService.update_defect(did, **data)
                show_info(self, "成功", "病害信息已更新")
                self._refresh_defects()
            except Exception as e:
                show_error(self, "失败", f"更新失败: {str(e)}")

    def _on_delete_defect(self) -> None:
        did = self._get_selected_defect_id()
        if not did:
            show_warning(self, "提示", "请先选择要删除的病害")
            return
        if confirm_delete(self, item_name="病害"):
            try:
                DefectService.delete_defect(did)
                show_info(self, "成功", "病害已删除")
                self._refresh_defects()
            except Exception as e:
                show_error(self, "失败", f"删除失败: {str(e)}")

    def _on_view_detail(self) -> None:
        did = self._get_selected_defect_id()
        if not did:
            show_warning(self, "提示", "请先选择要查看的病害")
            return
        dlg = DefectDetailDialog(self, defect_id=did)
        dlg.exec()

    def _on_create_workorder(self) -> None:
        did = self._get_selected_defect_id()
        if not did:
            show_warning(self, "提示", "请先选择要创建工单的病害")
            return
        dlg = WorkOrderDialog(self, default_defect_id=did)
        if dlg.exec():
            data = dlg.get_data()
            try:
                DefectService.create_work_order(did, **data)
                show_info(self, "成功", "工单创建成功")
                self._refresh_workorders()
                self._refresh_defects()
            except Exception as e:
                show_error(self, "失败", f"创建失败: {str(e)}")

    def _on_edit_workorder(self) -> None:
        wid = self._get_selected_workorder_id()
        if not wid:
            show_warning(self, "提示", "请先选择要编辑的工单")
            return
        from app.db.database import WorkOrderRepository
        wo = WorkOrderRepository.get_by_id(wid)
        if not wo:
            return
        dlg = WorkOrderDialog(self, work_order=wo)
        if dlg.exec():
            data = dlg.get_data()
            try:
                WorkOrderRepository.update(wid, **data)
                show_info(self, "成功", "工单已更新")
                self._refresh_workorders()
            except Exception as e:
                show_error(self, "失败", f"更新失败: {str(e)}")

    def _on_delete_workorder(self) -> None:
        wid = self._get_selected_workorder_id()
        if not wid:
            show_warning(self, "提示", "请先选择要删除的工单")
            return
        if confirm_delete(self, item_name="工单"):
            try:
                from app.db.database import WorkOrderRepository
                WorkOrderRepository.delete(wid)
                show_info(self, "成功", "工单已删除")
                self._refresh_workorders()
            except Exception as e:
                show_error(self, "失败", f"删除失败: {str(e)}")

    def _on_change_workorder_status(self, new_status: str) -> None:
        wid = self._get_selected_workorder_id()
        if not wid:
            show_warning(self, "提示", "请先选择工单")
            return
        if confirm_action(self, f"确定要将工单状态变更为「{new_status}」吗？"):
            try:
                DefectService.update_work_order_status(wid, new_status)
                show_info(self, "成功", f"状态已变更为「{new_status}」")
                self._refresh_workorders()
                self._refresh_defects()
            except Exception as e:
                show_error(self, "失败", f"状态变更失败: {str(e)}")

    def _on_add_tracking(self) -> None:
        wid = self._get_selected_workorder_id()
        if not wid:
            show_warning(self, "提示", "请先选择要记录整改的工单")
            return
        dlg = RectificationTrackDialog(self, work_order_id=wid)
        if dlg.exec():
            data = dlg.get_data()
            try:
                DefectService.add_rectification_tracking(wid, **data)
                show_info(self, "成功", "整改记录已添加")
            except Exception as e:
                show_error(self, "失败", f"添加失败: {str(e)}")

    def _on_do_acceptance(self) -> None:
        wid = self._get_selected_workorder_id()
        if not wid:
            show_warning(self, "提示", "请先选择要验收的工单")
            return
        dlg = AcceptanceDialog(self, work_order_id=wid)
        if dlg.exec():
            data = dlg.get_data()
            try:
                DefectService.create_acceptance(wid, **data)
                show_info(self, "成功", "验收记录已保存")
                self._refresh_workorders()
                self._refresh_defects()
            except Exception as e:
                show_error(self, "失败", f"保存失败: {str(e)}")

    def _on_do_evaluation(self) -> None:
        did = self._get_selected_defect_id()
        if not did:
            wid = self._get_selected_workorder_id()
            if wid:
                from app.db.database import WorkOrderRepository
                wo = WorkOrderRepository.get_by_id(wid)
                if wo:
                    did = wo.get("defect_id")
        if not did:
            show_warning(self, "提示", "请先选择病害或关联的工单")
            return
        dlg = EffectivenessEvalDialog(self, defect_id=did)
        if dlg.exec():
            data = dlg.get_data()
            try:
                DefectService.create_evaluation(did, **data)
                show_info(self, "成功", "效果评估已保存")
                self._refresh_charts()
            except Exception as e:
                show_error(self, "失败", f"保存失败: {str(e)}")
