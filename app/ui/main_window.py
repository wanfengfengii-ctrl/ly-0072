from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QPushButton, QLabel, QMessageBox,
    QTabWidget, QMenu, QFileDialog
)
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QFont, QColor, QAction
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.db.database import (
    BuildingRepository, ComponentRepository, InspectionPlanRepository,
    DefectRepository, SettingsRepository
)
from app.logic.validator import analyze_component_risk
from app.logic.report_exporter import generate_html_report, batch_export_reports
from app.ui.dialogs import BuildingDialog, ComponentDialog
from app.ui.advanced_dialogs import BatchExportDialog
from app.ui.tabs import (
    DashboardTab, DetailTab, ComparisonTab, SeasonalTab, PredictionTab,
    InspectionTab, ReviewTab, DefectTab, PriorityTab, ResourceTab,
    RecurrenceTab, EffectivenessTab, PerformanceTab, CollaborationTab,
    ReportTab, ArchiveTab, SettingsTab
)
from app.common import show_info, show_warning, show_error, confirm_delete


RISK_COLORS = {
    "高风险": QColor(231, 76, 60),
    "中风险": QColor(230, 126, 34),
    "正常": QColor(46, 204, 113),
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("古建筑木构件含水率智能预警与多维分析系统")
        self.resize(1400, 900)
        self.current_building_id: Optional[int] = None
        self.current_component_id: Optional[int] = None
        self.selected_comparison_ids: List[int] = []
        self._tab_instances: Dict[int, QWidget] = {}
        self._init_ui()
        self._init_menu()
        self.refresh_buildings()
        self._start_reminder_timer()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        main_layout.addWidget(splitter)

    def _create_left_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        title = QLabel("建筑与构件")
        title.setFont(QFont("", 11, QFont.Bold))
        layout.addWidget(title)

        btn_layout = QHBoxLayout()

        self.btn_add_building = QPushButton("新建建筑")
        self.btn_add_building.clicked.connect(self._on_add_building)
        btn_layout.addWidget(self.btn_add_building)

        self.btn_add_component = QPushButton("新建构件")
        self.btn_add_component.clicked.connect(self._on_add_component)
        btn_layout.addWidget(self.btn_add_component)

        layout.addLayout(btn_layout)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["名称 / 编号", "类型"])
        self.tree.setColumnWidth(0, 180)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        layout.addWidget(self.tree, stretch=1)

        return widget

    def _create_right_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        self.tabs = QTabWidget()

        tab_configs = [
            (DashboardTab, "📊 总览看板"),
            (DetailTab, "构件详情"),
            (ComparisonTab, "🔍 横向对比"),
            (SeasonalTab, "🌤 季节性分析"),
            (PredictionTab, "📈 趋势预测"),
            (InspectionTab, "📋 巡检计划"),
            (ReviewTab, "⚠ 异常复核"),
            (DefectTab, "🔧 病害闭环管理"),
            (PriorityTab, "🎯 优先级排序"),
            (ResourceTab, "📦 维修资源"),
            (RecurrenceTab, "🔄 复发分析"),
            (EffectivenessTab, "📉 效果对比"),
            (PerformanceTab, "🏆 闭环绩效"),
            (CollaborationTab, "👥 角色协同"),
            (ReportTab, "📑 综合报告"),
            (ArchiveTab, "📁 报告归档"),
            (SettingsTab, "⚙ 系统设置"),
        ]

        for idx, (tab_cls, tab_name) in enumerate(tab_configs):
            tab_instance = tab_cls(main_window=self)
            self._tab_instances[idx] = tab_instance
            self.tabs.addTab(tab_instance, tab_name)

        self.tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self.tabs)
        return widget

    def _init_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")

        export_act = QAction("导出当前巡检报告...", self)
        export_act.triggered.connect(self._on_export_report)
        file_menu.addAction(export_act)

        batch_export_act = QAction("批量导出多建筑报告...", self)
        batch_export_act.triggered.connect(self._on_batch_export)
        file_menu.addAction(batch_export_act)

        file_menu.addSeparator()

        view_dashboard = QAction("查看总览看板", self)
        view_dashboard.triggered.connect(lambda: self.tabs.setCurrentIndex(0))
        file_menu.addAction(view_dashboard)

        file_menu.addSeparator()

        exit_act = QAction("退出", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        analyze_menu = menubar.addMenu("分析")
        compare_act = QAction("横向对比分析...", self)
        compare_act.triggered.connect(lambda: self.tabs.setCurrentIndex(2))
        analyze_menu.addAction(compare_act)

        seasonal_act = QAction("季节性波动分析", self)
        seasonal_act.triggered.connect(lambda: self.tabs.setCurrentIndex(3))
        analyze_menu.addAction(seasonal_act)

        prediction_act = QAction("风险趋势预测", self)
        prediction_act.triggered.connect(lambda: self.tabs.setCurrentIndex(4))
        analyze_menu.addAction(prediction_act)

        plan_menu = menubar.addMenu("巡检")
        plan_act = QAction("巡检计划管理", self)
        plan_act.triggered.connect(lambda: self.tabs.setCurrentIndex(5))
        plan_menu.addAction(plan_act)

        review_act = QAction("异常复核管理", self)
        review_act.triggered.connect(lambda: self.tabs.setCurrentIndex(6))
        plan_menu.addAction(review_act)

        scan_anomaly_act = QAction("自动扫描异常数据", self)
        scan_anomaly_act.triggered.connect(self._on_auto_scan_anomalies)
        plan_menu.addAction(scan_anomaly_act)

        archive_menu = menubar.addMenu("归档")
        archive_list_act = QAction("报告归档历史", self)
        archive_list_act.triggered.connect(lambda: self.tabs.setCurrentIndex(15))
        archive_menu.addAction(archive_list_act)

        help_menu = menubar.addMenu("帮助")
        about_act = QAction("关于", self)
        about_act.triggered.connect(self._on_about)
        help_menu.addAction(about_act)

    def refresh_buildings(self):
        self.tree.clear()
        buildings = BuildingRepository.get_all()
        for b in buildings:
            b_item = QTreeWidgetItem(["🏛  " + b["name"], "建筑"])
            b_item.setData(0, Qt.UserRole, {"type": "building", "id": b["id"]})
            b_item.setFont(0, QFont("", 10, QFont.Bold))

            components = ComponentRepository.get_by_building(b["id"])
            for c in components:
                risk = analyze_component_risk(c["id"])
                risk_level = risk["overall_risk_level"]
                icon_map = {"梁": "🪵", "柱": "🏛", "斗拱": "🔩", "枋": "📏",
                            "檩": "➖", "椽": "│", "其他": "📦"}
                icon = icon_map.get(c["component_type"], "📦")
                c_item = QTreeWidgetItem(
                    [f"   {icon} {c['code']} - {c['name']}", c["component_type"]]
                )
                c_item.setData(0, Qt.UserRole, {"type": "component", "id": c["id"]})
                color = RISK_COLORS.get(risk_level, QColor(0, 0, 0))
                c_item.setForeground(0, color)
                c_item.setForeground(1, color)
                b_item.addChild(c_item)

            self.tree.addTopLevelItem(b_item)
            b_item.setExpanded(True)

    def _on_tree_selection_changed(self):
        items = self.tree.selectedItems()
        if not items:
            return

        data = items[0].data(0, Qt.UserRole)
        if not data:
            return

        if data["type"] == "building":
            self.current_building_id = data["id"]
            self.current_component_id = None
        elif data["type"] == "component":
            self.current_component_id = data["id"]
            component = ComponentRepository.get_by_id(data["id"])
            if component:
                self.current_building_id = component.get("building_id")

        self._refresh_all_tabs()

    def _on_tree_context_menu(self, pos: QPoint):
        item = self.tree.itemAt(pos)
        if not item:
            return

        data = item.data(0, Qt.UserRole)
        if not data:
            return

        menu = QMenu(self)

        edit_action = menu.addAction("编辑")
        delete_action = menu.addAction("删除")

        action = menu.exec(self.tree.viewport().mapToGlobal(pos))

        if action == edit_action:
            self._on_edit_item(data)
        elif action == delete_action:
            self._on_delete_item(data)

    def _on_edit_item(self, data: Dict[str, Any]):
        if data["type"] == "building":
            building = BuildingRepository.get_by_id(data["id"])
            if not building:
                return
            dlg = BuildingDialog(self, building=building)
            if dlg.exec():
                form_data = dlg.get_data()
                try:
                    BuildingRepository.update(data["id"], **form_data)
                    self.refresh_buildings()
                    self._refresh_all_tabs()
                except Exception as e:
                    show_error(self, f"保存失败: {str(e)}")
        elif data["type"] == "component":
            component = ComponentRepository.get_by_id(data["id"])
            if not component:
                return
            buildings = BuildingRepository.get_all()
            dlg = ComponentDialog(self, buildings=buildings, component=component)
            if dlg.exec():
                form_data = dlg.get_data()
                try:
                    ComponentRepository.update(data["id"], **form_data)
                    self.refresh_buildings()
                    self._refresh_all_tabs()
                except Exception as e:
                    show_error(self, f"保存失败: {str(e)}")

    def _on_delete_item(self, data: Dict[str, Any]):
        if data["type"] == "building":
            building = BuildingRepository.get_by_id(data["id"])
            if not building:
                return
            if not confirm_delete(
                self,
                f"确定要删除建筑「{building['name']}」吗？\n注意：该建筑下存在构件时将无法删除。"
            ):
                return
            try:
                BuildingRepository.delete(data["id"])
                self.current_building_id = None
                self.current_component_id = None
                self.refresh_buildings()
                self._refresh_all_tabs()
                show_info(self, "建筑已删除")
            except ValueError as e:
                show_warning(self, str(e))
            except Exception as e:
                show_error(self, f"删除失败: {str(e)}")

        elif data["type"] == "component":
            component = ComponentRepository.get_by_id(data["id"])
            if not component:
                return
            has_records = ComponentRepository.has_records(data["id"])
            warn_msg = ""
            if has_records:
                warn_msg = "\n⚠ 该构件存在历史检测记录，将无法删除。"
            if not confirm_delete(
                self,
                f"确定要删除构件「{component['code']} - {component['name']}」吗？{warn_msg}"
            ):
                return
            try:
                ComponentRepository.delete(data["id"])
                self.current_component_id = None
                self.refresh_buildings()
                self._refresh_all_tabs()
                show_info(self, "构件已删除")
            except ValueError as e:
                show_warning(self, str(e))
            except Exception as e:
                show_error(self, f"删除失败: {str(e)}")

    def _on_add_building(self):
        dlg = BuildingDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                BuildingRepository.create(**data)
                self.refresh_buildings()
                self._refresh_all_tabs()
            except Exception as e:
                show_error(self, f"创建失败: {str(e)}")

    def _on_add_component(self):
        buildings = BuildingRepository.get_all()
        if not buildings:
            show_warning(self, "请先创建建筑档案")
            return
        dlg = ComponentDialog(self, buildings=buildings)
        if dlg.exec():
            data = dlg.get_data()
            try:
                ComponentRepository.create(**data)
                self.refresh_buildings()
                self._refresh_all_tabs()
            except Exception as e:
                show_error(self, f"创建失败: {str(e)}")

    def _on_tab_changed(self, index: int):
        tab_instance = self._tab_instances.get(index)
        if tab_instance and hasattr(tab_instance, "on_activated"):
            try:
                tab_instance.on_activated()
            except Exception:
                pass

    def _refresh_all_tabs(self):
        for tab in self._tab_instances.values():
            if hasattr(tab, "refresh"):
                try:
                    tab.refresh()
                except Exception:
                    pass

    def _start_reminder_timer(self):
        self._reminder_timer = QTimer(self)
        self._reminder_timer.timeout.connect(self._check_reminders)
        self._reminder_timer.start(60000)
        QTimer.singleShot(1000, self._check_reminders)

    def _check_reminders(self):
        try:
            upcoming = InspectionPlanRepository.get_upcoming()
            now = datetime.now()
            urgent_count = 0
            soon_count = 0

            for plan in upcoming:
                try:
                    plan_date = datetime.fromisoformat(plan["plan_date"].split(" ")[0])
                    days_until = (plan_date - now).days
                    reminder_days = plan.get("reminder_days", 7)
                    if days_until <= 0:
                        urgent_count += 1
                    elif days_until <= reminder_days:
                        soon_count += 1
                except Exception:
                    continue

            overdue_defects = DefectRepository.get_overdue_reminders()

            if urgent_count > 0 or soon_count > 0 or overdue_defects:
                msg_parts = []
                if urgent_count > 0:
                    msg_parts.append(f"🔴 {urgent_count} 个巡检计划已到期或逾期")
                if soon_count > 0:
                    msg_parts.append(f"🟡 {soon_count} 个巡检计划即将到期")
                if overdue_defects:
                    msg_parts.append(f"⚠ {len(overdue_defects)} 个维修工单已超期")
        except Exception:
            pass

    def _on_auto_scan_anomalies(self):
        from app.services import InspectionService

        threshold = SettingsRepository.get_moisture_threshold()
        components = ComponentRepository.get_all()

        reply = QMessageBox.question(
            self, "自动扫描异常",
            f"即将扫描全部 {len(components)} 个构件，自动识别含水率超过阈值 {threshold}% 的记录。\n是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        scanned, added = InspectionService.auto_scan_anomalies()

        show_info(
            self,
            f"共扫描 {scanned} 个构件\n"
            f"新增异常待复核: {added} 条\n"
            f"请在「异常复核」标签页查看并处理"
        )
        self._refresh_all_tabs()

    def _on_export_report(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出巡检报告",
            f"巡检报告_{self.current_component_id or '全部'}.html",
            "HTML文件 (*.html)"
        )
        if not file_path:
            return

        try:
            output = generate_html_report(
                building_id=self.current_building_id if not self.current_component_id else None,
                component_id=self.current_component_id,
                output_path=file_path
            )
            show_info(self, f"报告已成功导出到:\n{output}")
        except Exception as e:
            show_error(self, f"生成报告失败: {str(e)}")

    def _on_batch_export(self):
        dlg = BatchExportDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                results = batch_export_reports(
                    output_dir=data["output_dir"],
                    building_id=data["building_id"],
                    archive=data["archive"],
                    include_charts=data["include_charts"],
                    include_stats=data["include_stats"],
                    include_risk=data["include_risk"]
                )
                success = sum(1 for r in results if r["success"])
                failed = len(results) - success
                msg = f"批量导出完成！\n成功: {success} 个\n"
                if failed > 0:
                    msg += f"失败: {failed} 个\n"
                    for r in results:
                        if not r["success"]:
                            msg += f"  - {r.get('building_name', '')}: {r.get('error', '')}\n"
                msg += f"\n输出目录: {data['output_dir']}"
                show_info(self, msg)
                self._refresh_all_tabs()
            except Exception as e:
                show_error(self, f"批量导出失败: {str(e)}")

    def _on_about(self):
        QMessageBox.about(
            self, "关于",
            "古建筑木构件含水率智能预警与多维分析系统 v2.0\n\n"
            "面向古建筑修缮巡检的专业决策支持平台。\n\n"
            "核心功能:\n"
            "• 多建筑总览看板\n"
            "• 按构件类型/位置横向对比\n"
            "• 季节性波动识别\n"
            "• 风险趋势预测\n"
            "• 巡检计划与提醒\n"
            "• 异常复核标记\n"
            "• 报告批量导出与历史归档\n\n"
            "技术栈: Python + PySide6 + SQLite + Matplotlib"
        )
