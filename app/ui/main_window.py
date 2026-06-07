from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QTabWidget,
    QComboBox, QGroupBox, QFormLayout, QDoubleSpinBox,
    QFileDialog, QTextEdit, QSizePolicy, QAbstractItemView, QMenu,
    QSpinBox, QCheckBox, QListWidget, QListWidgetItem, QGridLayout,
    QFrame, QScrollArea, QLineEdit, QDateEdit
)
from PySide6.QtCore import Qt, QSize, QPoint, QDate, QTimer
from PySide6.QtGui import QFont, QColor, QIcon, QAction, QBrush
from typing import Optional, Dict, Any, List
from datetime import datetime
import os

from app.db.database import (
    BuildingRepository, ComponentRepository, RecordRepository,
    SettingsRepository, InspectionPlanRepository, AnomalyReviewRepository,
    ReportArchiveRepository, DefectRepository, WorkOrderRepository,
    RectificationTrackingRepository, AcceptanceRecordRepository,
    EffectivenessEvaluationRepository, DefectStatusLogRepository,
    UserRepository, RoleRepository, MaintenanceResourceRepository,
    DefectRecurrenceRepository, AssignmentRepository,
    DEFECT_TYPES, DEFECT_SEVERITIES, DEFECT_STATUSES,
    WORK_ORDER_STATUSES, PRIORITIES, USER_ROLES,
    RESOURCE_TYPES, RECURRENCE_TYPES
)
from app.logic.validator import (
    analyze_component_risk, calculate_statistics
)
from app.logic.dashboard import get_multi_building_overview, get_risk_distribution_by_type
from app.logic.advanced_analytics import (
    compare_components, get_all_components_for_comparison,
    analyze_seasonal_variation, analyze_seasonal_variation_multi,
    predict_risk_trend
)
from app.logic.collaboration_analytics import (
    calculate_defect_priority, sort_defects_by_priority,
    check_rectification_deadlines, calculate_effectiveness_comparison,
    calculate_closed_loop_performance, detect_defect_recurrences
)
from app.logic.report_exporter import (
    generate_html_report, batch_export_reports, generate_comparison_report,
    generate_defect_disposal_report
)
from app.ui.dialogs import BuildingDialog, ComponentDialog
from app.ui.csv_import_dialog import CSVImportDialog
from app.ui.chart_widget import ChartWidget
from app.ui.advanced_dialogs import (
    InspectionPlanDialog, AnomalyReviewDialog, ComponentSelectionDialog,
    BatchExportDialog, DefectDialog, WorkOrderDialog, RectificationTrackDialog,
    AcceptanceDialog, EffectivenessEvalDialog, DefectDetailDialog,
    UserDialog, ResourceDialog, DefectRecurrenceDialog, RolePermissionDialog
)


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
        self.current_building_id = None
        self.current_component_id = None
        self.selected_comparison_ids: List[int] = []
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

        self.tabs.addTab(self._create_dashboard_tab(), "📊 总览看板")
        self.tabs.addTab(self._create_detail_tab(), "构件详情")
        self.tabs.addTab(self._create_records_tab(), "检测记录")
        self.tabs.addTab(self._create_charts_tab(), "图表分析")
        self.tabs.addTab(self._create_risk_tab(), "风险分析")
        self.tabs.addTab(self._create_comparison_tab(), "🔍 横向对比")
        self.tabs.addTab(self._create_seasonal_tab(), "🌤 季节性分析")
        self.tabs.addTab(self._create_prediction_tab(), "📈 趋势预测")
        self.tabs.addTab(self._create_inspection_tab(), "📋 巡检计划")
        self.tabs.addTab(self._create_review_tab(), "⚠ 异常复核")
        self.tabs.addTab(self._create_defect_tab(), "🔧 病害闭环管理")
        self.tabs.addTab(self._create_priority_tab(), "🎯 优先级排序")
        self.tabs.addTab(self._create_resource_tab(), "📦 维修资源")
        self.tabs.addTab(self._create_recurrence_tab(), "🔄 复发分析")
        self.tabs.addTab(self._create_effectiveness_tab(), "📉 效果对比")
        self.tabs.addTab(self._create_performance_tab(), "🏆 闭环绩效")
        self.tabs.addTab(self._create_collaboration_tab(), "👥 角色协同")
        self.tabs.addTab(self._create_report_center_tab(), "📑 综合报告")
        self.tabs.addTab(self._create_archive_tab(), "📁 报告归档")
        self.tabs.addTab(self._create_settings_tab(), "⚙ 系统设置")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self.tabs)
        return widget

    def _create_detail_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.detail_label = QLabel("请选择构件查看详情")
        self.detail_label.setFont(QFont("", 12))
        self.detail_label.setAlignment(Qt.AlignCenter)
        self.detail_label.setStyleSheet("color: #888;")
        layout.addWidget(self.detail_label)

        self.detail_info = QGroupBox("基本信息")
        self.detail_form = QFormLayout(self.detail_info)
        self.detail_code = QLabel("-")
        self.detail_name = QLabel("-")
        self.detail_type = QLabel("-")
        self.detail_material = QLabel("-")
        self.detail_position = QLabel("-")
        self.detail_desc = QLabel("-")
        self.detail_desc.setWordWrap(True)
        self.detail_form.addRow("构件编号:", self.detail_code)
        self.detail_form.addRow("构件名称:", self.detail_name)
        self.detail_form.addRow("构件类型:", self.detail_type)
        self.detail_form.addRow("材 质:", self.detail_material)
        self.detail_form.addRow("所在位置:", self.detail_position)
        self.detail_form.addRow("描 述:", self.detail_desc)
        self.detail_info.hide()
        layout.addWidget(self.detail_info)

        self.stats_group = QGroupBox("统计概览")
        stats_layout = QFormLayout(self.stats_group)
        self.stat_records = QLabel("-")
        self.stat_avg = QLabel("-")
        self.stat_max = QLabel("-")
        self.stat_min = QLabel("-")
        self.stat_positions = QLabel("-")
        self.stat_risk = QLabel("-")
        self.stat_risk.setFont(QFont("", 11, QFont.Bold))
        stats_layout.addRow("检测次数:", self.stat_records)
        stats_layout.addRow("检测位置:", self.stat_positions)
        stats_layout.addRow("平均含水率:", self.stat_avg)
        stats_layout.addRow("最高含水率:", self.stat_max)
        stats_layout.addRow("最低含水率:", self.stat_min)
        stats_layout.addRow("风险等级:", self.stat_risk)
        self.stats_group.hide()
        layout.addWidget(self.stats_group)

        layout.addStretch()
        return widget

    def _create_records_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        btn_row = QHBoxLayout()
        self.btn_import_csv = QPushButton("导入CSV数据...")
        self.btn_import_csv.clicked.connect(self._on_import_csv)
        self.btn_import_csv.setStyleSheet(
            "background-color: #3498db; color: white; padding: 6px 16px;"
        )
        btn_row.addWidget(self.btn_import_csv)

        self.btn_delete_record = QPushButton("删除记录")
        self.btn_delete_record.clicked.connect(self._on_delete_record)
        btn_row.addWidget(self.btn_delete_record)

        btn_row.addWidget(QLabel("筛选位置:"))
        self.record_position_filter = QComboBox()
        self.record_position_filter.addItem("全部")
        self.record_position_filter.currentIndexChanged.connect(self._refresh_records_table)
        btn_row.addWidget(self.record_position_filter)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.records_table = QTableWidget()
        self.records_table.setAlternatingRowColors(True)
        self.records_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.records_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.records_table.verticalHeader().setVisible(False)
        layout.addWidget(self.records_table)

        return widget

    def _create_charts_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        control_row = QHBoxLayout()
        control_row.addWidget(QLabel("图表类型:"))
        self.chart_type = QComboBox()
        self.chart_type.addItems(["趋势图", "位置对比图", "统计柱状图"])
        self.chart_type.currentIndexChanged.connect(self._refresh_chart)
        control_row.addWidget(self.chart_type)

        control_row.addWidget(QLabel("位置筛选:"))
        self.chart_position_filter = QComboBox()
        self.chart_position_filter.addItem("全部")
        self.chart_position_filter.currentIndexChanged.connect(self._refresh_chart)
        control_row.addWidget(self.chart_position_filter)

        control_row.addStretch()
        layout.addLayout(control_row)

        self.chart_widget = ChartWidget()
        layout.addWidget(self.chart_widget, stretch=1)

        return widget

    def _create_risk_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.risk_summary = QLabel("请选择构件查看风险分析")
        self.risk_summary.setFont(QFont("", 11))
        self.risk_summary.setAlignment(Qt.AlignCenter)
        self.risk_summary.setStyleSheet("color: #888; padding: 20px;")
        layout.addWidget(self.risk_summary)

        self.risk_table = QTableWidget()
        self.risk_table.setAlternatingRowColors(True)
        self.risk_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.risk_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.risk_table.hide()
        layout.addWidget(self.risk_table, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_export_report = QPushButton("导出巡检报告(HTML)")
        self.btn_export_report.clicked.connect(self._on_export_report)
        self.btn_export_report.setStyleSheet(
            "background-color: #27ae60; color: white; padding: 8px 20px;"
        )
        btn_row.addWidget(self.btn_export_report)
        layout.addLayout(btn_row)

        return widget

    def _create_dashboard_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.dashboard_summary = QLabel("正在加载总览数据...")
        self.dashboard_summary.setFont(QFont("", 11))
        self.dashboard_summary.setAlignment(Qt.AlignCenter)
        self.dashboard_summary.setStyleSheet("padding: 10px; background: #ecf0f1; border-radius: 4px;")
        layout.addWidget(self.dashboard_summary)

        stat_grid = QGridLayout()
        self.stat_buildings = self._create_stat_card("🏛 建筑总数", "0", "#3498db")
        self.stat_components = self._create_stat_card("🧱 构件总数", "0", "#2ecc71")
        self.stat_high_risk = self._create_stat_card("🔴 高风险构件", "0", "#e74c3c")
        self.stat_pending_reviews = self._create_stat_card("⚠ 待复核异常", "0", "#f39c12")
        stat_grid.addWidget(self.stat_buildings, 0, 0)
        stat_grid.addWidget(self.stat_components, 0, 1)
        stat_grid.addWidget(self.stat_high_risk, 0, 2)
        stat_grid.addWidget(self.stat_pending_reviews, 0, 3)
        layout.addLayout(stat_grid)

        chart_splitter = QSplitter(Qt.Horizontal)
        self.dashboard_chart1 = ChartWidget()
        self.dashboard_chart2 = ChartWidget()
        chart_splitter.addWidget(self.dashboard_chart1)
        chart_splitter.addWidget(self.dashboard_chart2)
        chart_splitter.setStretchFactor(0, 1)
        chart_splitter.setStretchFactor(1, 1)
        layout.addWidget(chart_splitter, stretch=1)

        self.dashboard_table_label = QLabel("各建筑风险分布:")
        self.dashboard_table_label.setFont(QFont("", 10, QFont.Bold))
        layout.addWidget(self.dashboard_table_label)

        self.dashboard_table = QTableWidget()
        self.dashboard_table.setAlternatingRowColors(True)
        self.dashboard_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.dashboard_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.dashboard_table.verticalHeader().setVisible(False)
        layout.addWidget(self.dashboard_table, stretch=1)

        btn_row = QHBoxLayout()
        self.btn_refresh_dashboard = QPushButton("🔄 刷新数据")
        self.btn_refresh_dashboard.clicked.connect(self._refresh_dashboard)
        btn_row.addWidget(self.btn_refresh_dashboard)
        self.btn_batch_export = QPushButton("📤 批量导出报告")
        self.btn_batch_export.setStyleSheet("background-color: #3498db; color: white; padding: 6px 16px;")
        self.btn_batch_export.clicked.connect(self._on_batch_export)
        btn_row.addWidget(self.btn_batch_export)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return widget

    def _bold_font(self) -> QFont:
        f = QFont()
        f.setBold(True)
        return f

    def _create_stat_card(self, title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setFrameStyle(QFrame.StyledPanel)
        card.setStyleSheet(f"""
            QFrame {{ background: white; border-radius: 8px; padding: 12px;
                     border-left: 4px solid {color}; }}
        """)
        layout = QVBoxLayout(card)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666; font-size: 12px;")
        value_label = QLabel(value)
        value_label.setObjectName("value")
        value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card

    def _create_comparison_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("分组方式:"))
        self.comparison_group_by = QComboBox()
        self.comparison_group_by.addItems(["按构件类型", "按建筑", "按位置"])
        self.comparison_group_by.currentIndexChanged.connect(self._refresh_comparison)
        ctrl_row.addWidget(self.comparison_group_by)

        self.btn_select_components = QPushButton("选择构件...")
        self.btn_select_components.setStyleSheet("background-color: #3498db; color: white; padding: 6px 16px;")
        self.btn_select_components.clicked.connect(self._on_select_components_for_comparison)
        ctrl_row.addWidget(self.btn_select_components)

        self.lbl_comparison_count = QLabel("已选择 0 个构件")
        ctrl_row.addWidget(self.lbl_comparison_count)

        ctrl_row.addStretch()

        self.btn_export_comparison = QPushButton("导出对比报告")
        self.btn_export_comparison.clicked.connect(self._on_export_comparison_report)
        ctrl_row.addWidget(self.btn_export_comparison)
        layout.addLayout(ctrl_row)

        content_splitter = QSplitter(Qt.Vertical)
        self.comparison_chart = ChartWidget()
        content_splitter.addWidget(self.comparison_chart)

        self.comparison_table = QTableWidget()
        self.comparison_table.setAlternatingRowColors(True)
        self.comparison_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.comparison_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.comparison_table.verticalHeader().setVisible(False)
        content_splitter.addWidget(self.comparison_table)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 1)
        layout.addWidget(content_splitter, stretch=1)

        return widget

    def _create_seasonal_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        ctrl_row = QHBoxLayout()
        self.lbl_seasonal_hint = QLabel("请选择左侧构件查看季节性波动分析，或选择多个构件进行对比")
        self.lbl_seasonal_hint.setStyleSheet("color: #666; padding: 5px;")
        ctrl_row.addWidget(self.lbl_seasonal_hint)
        ctrl_row.addStretch()
        self.btn_seasonal_multi = QPushButton("多构件对比分析")
        self.btn_seasonal_multi.clicked.connect(self._on_seasonal_multi_analysis)
        ctrl_row.addWidget(self.btn_seasonal_multi)
        layout.addLayout(ctrl_row)

        self.seasonal_summary = QLabel("")
        self.seasonal_summary.setFont(QFont("", 11))
        self.seasonal_summary.setStyleSheet("padding: 10px; background: #ecf0f1; border-radius: 4px;")
        self.seasonal_summary.setWordWrap(True)
        layout.addWidget(self.seasonal_summary)

        chart_splitter = QSplitter(Qt.Horizontal)
        self.seasonal_chart = ChartWidget()
        self.monthly_chart = ChartWidget()
        chart_splitter.addWidget(self.seasonal_chart)
        chart_splitter.addWidget(self.monthly_chart)
        chart_splitter.setStretchFactor(0, 1)
        chart_splitter.setStretchFactor(1, 1)
        layout.addWidget(chart_splitter, stretch=1)

        self.seasonal_table = QTableWidget()
        self.seasonal_table.setAlternatingRowColors(True)
        self.seasonal_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.seasonal_table.verticalHeader().setVisible(False)
        self.seasonal_table.setMaximumHeight(180)
        layout.addWidget(self.seasonal_table)

        return widget

    def _create_prediction_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("预测天数:"))
        self.prediction_days = QSpinBox()
        self.prediction_days.setRange(30, 365)
        self.prediction_days.setValue(90)
        self.prediction_days.setSuffix(" 天")
        self.prediction_days.valueChanged.connect(self._refresh_prediction)
        ctrl_row.addWidget(self.prediction_days)
        ctrl_row.addStretch()
        self.btn_refresh_prediction = QPushButton("重新预测")
        self.btn_refresh_prediction.clicked.connect(self._refresh_prediction)
        ctrl_row.addWidget(self.btn_refresh_prediction)
        layout.addLayout(ctrl_row)

        self.prediction_summary = QLabel("请选择构件进行风险趋势预测")
        self.prediction_summary.setFont(QFont("", 11))
        self.prediction_summary.setStyleSheet("padding: 10px; background: #ecf0f1; border-radius: 4px;")
        self.prediction_summary.setWordWrap(True)
        layout.addWidget(self.prediction_summary)

        self.prediction_chart = ChartWidget()
        layout.addWidget(self.prediction_chart, stretch=1)

        self.prediction_detail = QLabel("")
        self.prediction_detail.setStyleSheet("padding: 10px; background: white; border-radius: 4px;")
        self.prediction_detail.setWordWrap(True)
        layout.addWidget(self.prediction_detail)

        return widget

    def _create_inspection_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        btn_row = QHBoxLayout()
        self.btn_add_plan = QPushButton("➕ 新增计划")
        self.btn_add_plan.setStyleSheet("background-color: #27ae60; color: white; padding: 6px 16px;")
        self.btn_add_plan.clicked.connect(self._on_add_inspection_plan)
        btn_row.addWidget(self.btn_add_plan)

        self.btn_edit_plan = QPushButton("✏ 编辑")
        self.btn_edit_plan.clicked.connect(self._on_edit_inspection_plan)
        btn_row.addWidget(self.btn_edit_plan)

        self.btn_delete_plan = QPushButton("🗑 删除")
        self.btn_delete_plan.clicked.connect(self._on_delete_inspection_plan)
        btn_row.addWidget(self.btn_delete_plan)

        self.btn_complete_plan = QPushButton("✅ 标记完成")
        self.btn_complete_plan.clicked.connect(self._on_complete_inspection_plan)
        btn_row.addWidget(self.btn_complete_plan)

        btn_row.addWidget(QLabel("状态筛选:"))
        self.plan_status_filter = QComboBox()
        self.plan_status_filter.addItem("全部", None)
        for s in ["待执行", "已提醒", "执行中", "已完成", "已取消"]:
            self.plan_status_filter.addItem(s, s)
        self.plan_status_filter.currentIndexChanged.connect(self._refresh_inspection_plans)
        btn_row.addWidget(self.plan_status_filter)

        btn_row.addStretch()
        self.btn_refresh_plans = QPushButton("🔄 刷新")
        self.btn_refresh_plans.clicked.connect(self._refresh_inspection_plans)
        btn_row.addWidget(self.btn_refresh_plans)
        layout.addLayout(btn_row)

        self.reminder_banner = QLabel("")
        self.reminder_banner.setStyleSheet("""
            padding: 10px; background: #fff3cd; border: 1px solid #ffc107;
            border-radius: 4px; color: #856404; font-weight: bold;
        """)
        self.reminder_banner.hide()
        layout.addWidget(self.reminder_banner)

        self.inspection_table = QTableWidget()
        self.inspection_table.setAlternatingRowColors(True)
        self.inspection_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.inspection_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.inspection_table.verticalHeader().setVisible(False)
        self.inspection_table.doubleClicked.connect(self._on_edit_inspection_plan)
        layout.addWidget(self.inspection_table, stretch=1)

        return widget

    def _create_review_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        btn_row = QHBoxLayout()
        self.btn_add_review = QPushButton("➕ 标记异常")
        self.btn_add_review.clicked.connect(self._on_add_anomaly_review)
        btn_row.addWidget(self.btn_add_review)

        self.btn_review_selected = QPushButton("✏ 复核选中")
        self.btn_review_selected.setStyleSheet("background-color: #f39c12; color: white; padding: 6px 16px;")
        self.btn_review_selected.clicked.connect(self._on_review_selected_anomaly)
        btn_row.addWidget(self.btn_review_selected)

        self.btn_delete_review = QPushButton("🗑 删除")
        self.btn_delete_review.clicked.connect(self._on_delete_anomaly_review)
        btn_row.addWidget(self.btn_delete_review)

        btn_row.addWidget(QLabel("状态筛选:"))
        self.review_status_filter = QComboBox()
        self.review_status_filter.addItem("全部", None)
        for s in ["待复核", "复核通过", "确认为风险", "误报"]:
            self.review_status_filter.addItem(s, s)
        self.review_status_filter.currentIndexChanged.connect(self._refresh_anomaly_reviews)
        btn_row.addWidget(self.review_status_filter)

        btn_row.addStretch()
        self.btn_auto_scan = QPushButton("🔍 自动扫描异常")
        self.btn_auto_scan.setStyleSheet("background-color: #e74c3c; color: white; padding: 6px 16px;")
        self.btn_auto_scan.clicked.connect(self._on_auto_scan_anomalies)
        btn_row.addWidget(self.btn_auto_scan)

        self.btn_refresh_reviews = QPushButton("🔄 刷新")
        self.btn_refresh_reviews.clicked.connect(self._refresh_anomaly_reviews)
        btn_row.addWidget(self.btn_refresh_reviews)
        layout.addLayout(btn_row)

        self.anomaly_table = QTableWidget()
        self.anomaly_table.setAlternatingRowColors(True)
        self.anomaly_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.anomaly_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.anomaly_table.verticalHeader().setVisible(False)
        self.anomaly_table.doubleClicked.connect(self._on_review_selected_anomaly)
        layout.addWidget(self.anomaly_table, stretch=1)

        return widget

    def _create_defect_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.defect_reminder_banner = QLabel("")
        self.defect_reminder_banner.setStyleSheet("""
            padding: 10px; background: #f8d7da; border: 1px solid #f5c6cb;
            border-radius: 4px; color: #721c24; font-weight: bold;
        """)
        self.defect_reminder_banner.hide()
        layout.addWidget(self.defect_reminder_banner)

        stat_row = QHBoxLayout()
        self.defect_stat_total = self._create_stat_card("病害总数", "0", "#3498db")
        self.defect_stat_pending = self._create_stat_card("待处置", "0", "#e74c3c")
        self.defect_stat_processing = self._create_stat_card("处置中", "0", "#f39c12")
        self.defect_stat_completed = self._create_stat_card("已完成", "0", "#27ae60")
        stat_row.addWidget(self.defect_stat_total)
        stat_row.addWidget(self.defect_stat_pending)
        stat_row.addWidget(self.defect_stat_processing)
        stat_row.addWidget(self.defect_stat_completed)
        layout.addLayout(stat_row)

        chart_splitter = QSplitter(Qt.Horizontal)
        self.defect_status_chart = ChartWidget()
        self.defect_type_chart = ChartWidget()
        self.moisture_compare_chart = ChartWidget()
        chart_splitter.addWidget(self.defect_status_chart)
        chart_splitter.addWidget(self.defect_type_chart)
        chart_splitter.addWidget(self.moisture_compare_chart)
        chart_splitter.setStretchFactor(0, 1)
        chart_splitter.setStretchFactor(1, 1)
        chart_splitter.setStretchFactor(2, 1)
        self.defect_chart_splitter = chart_splitter
        layout.addWidget(chart_splitter, stretch=1)

        self.defect_detail_tabs = QTabWidget()

        defect_list_widget = QWidget()
        defect_list_layout = QVBoxLayout(defect_list_widget)

        defect_btn_row = QHBoxLayout()
        self.btn_add_defect = QPushButton("➕ 登记病害")
        self.btn_add_defect.setStyleSheet("background-color: #e74c3c; color: white; padding: 6px 16px;")
        self.btn_add_defect.clicked.connect(self._on_add_defect)
        defect_btn_row.addWidget(self.btn_add_defect)

        self.btn_edit_defect = QPushButton("✏ 编辑")
        self.btn_edit_defect.clicked.connect(self._on_edit_defect)
        defect_btn_row.addWidget(self.btn_edit_defect)

        self.btn_delete_defect = QPushButton("🗑 删除")
        self.btn_delete_defect.clicked.connect(self._on_delete_defect)
        defect_btn_row.addWidget(self.btn_delete_defect)

        self.btn_view_defect_detail = QPushButton("📋 查看详情")
        self.btn_view_defect_detail.clicked.connect(self._on_view_defect_detail)
        defect_btn_row.addWidget(self.btn_view_defect_detail)

        self.btn_create_workorder = QPushButton("🔧 创建工单")
        self.btn_create_workorder.setStyleSheet("background-color: #f39c12; color: white; padding: 6px 16px;")
        self.btn_create_workorder.clicked.connect(self._on_create_workorder)
        defect_btn_row.addWidget(self.btn_create_workorder)

        self.btn_export_defect_report = QPushButton("📄 导出处置报告")
        self.btn_export_defect_report.setStyleSheet("background-color: #3498db; color: white; padding: 6px 16px;")
        self.btn_export_defect_report.clicked.connect(self._on_export_defect_report)
        defect_btn_row.addWidget(self.btn_export_defect_report)

        defect_btn_row.addWidget(QLabel("状态筛选:"))
        self.defect_status_filter = QComboBox()
        self.defect_status_filter.addItem("全部", None)
        for s in DEFECT_STATUSES:
            self.defect_status_filter.addItem(s, s)
        self.defect_status_filter.currentIndexChanged.connect(self._refresh_defects)
        defect_btn_row.addWidget(self.defect_status_filter)

        defect_btn_row.addWidget(QLabel("类型筛选:"))
        self.defect_type_filter = QComboBox()
        self.defect_type_filter.addItem("全部", None)
        for t in DEFECT_TYPES:
            self.defect_type_filter.addItem(t, t)
        self.defect_type_filter.currentIndexChanged.connect(self._refresh_defects)
        defect_btn_row.addWidget(self.defect_type_filter)

        defect_btn_row.addStretch()
        self.btn_refresh_defects = QPushButton("🔄 刷新")
        self.btn_refresh_defects.clicked.connect(self._refresh_defects)
        defect_btn_row.addWidget(self.btn_refresh_defects)

        defect_list_layout.addLayout(defect_btn_row)

        self.defect_table = QTableWidget()
        self.defect_table.setAlternatingRowColors(True)
        self.defect_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.defect_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.defect_table.verticalHeader().setVisible(False)
        self.defect_table.doubleClicked.connect(self._on_view_defect_detail)
        defect_list_layout.addWidget(self.defect_table, stretch=1)

        self.defect_detail_tabs.addTab(defect_list_widget, "📋 病害登记")

        wo_list_widget = QWidget()
        wo_list_layout = QVBoxLayout(wo_list_widget)

        wo_btn_row = QHBoxLayout()
        self.btn_edit_workorder = QPushButton("✏ 编辑工单")
        self.btn_edit_workorder.clicked.connect(self._on_edit_workorder)
        wo_btn_row.addWidget(self.btn_edit_workorder)

        self.btn_delete_workorder = QPushButton("🗑 删除工单")
        self.btn_delete_workorder.clicked.connect(self._on_delete_workorder)
        wo_btn_row.addWidget(self.btn_delete_workorder)

        self.btn_start_workorder = QPushButton("▶ 开始处理")
        self.btn_start_workorder.clicked.connect(lambda: self._on_change_workorder_status("处理中"))
        wo_btn_row.addWidget(self.btn_start_workorder)

        self.btn_add_tracking = QPushButton("📝 记录整改")
        self.btn_add_tracking.setStyleSheet("background-color: #3498db; color: white; padding: 6px 16px;")
        self.btn_add_tracking.clicked.connect(self._on_add_tracking)
        wo_btn_row.addWidget(self.btn_add_tracking)

        self.btn_to_accept = QPushButton("✅ 申请验收")
        self.btn_to_accept.clicked.connect(lambda: self._on_change_workorder_status("待验收"))
        wo_btn_row.addWidget(self.btn_to_accept)

        self.btn_do_acceptance = QPushButton("📝 验收")
        self.btn_do_acceptance.setStyleSheet("background-color: #27ae60; color: white; padding: 6px 16px;")
        self.btn_do_acceptance.clicked.connect(self._on_do_acceptance)
        wo_btn_row.addWidget(self.btn_do_acceptance)

        self.btn_do_eval = QPushButton("📊 效果评估")
        self.btn_do_eval.setStyleSheet("background-color: #9b59b6; color: white; padding: 6px 16px;")
        self.btn_do_eval.clicked.connect(self._on_do_evaluation)
        wo_btn_row.addWidget(self.btn_do_eval)

        wo_btn_row.addWidget(QLabel("状态筛选:"))
        self.wo_status_filter = QComboBox()
        self.wo_status_filter.addItem("全部", None)
        for s in WORK_ORDER_STATUSES:
            self.wo_status_filter.addItem(s, s)
        self.wo_status_filter.currentIndexChanged.connect(self._refresh_workorders)
        wo_btn_row.addWidget(self.wo_status_filter)

        wo_btn_row.addStretch()
        self.btn_refresh_workorders = QPushButton("🔄 刷新")
        self.btn_refresh_workorders.clicked.connect(self._refresh_workorders)
        wo_btn_row.addWidget(self.btn_refresh_workorders)

        wo_list_layout.addLayout(wo_btn_row)

        self.workorder_table = QTableWidget()
        self.workorder_table.setAlternatingRowColors(True)
        self.workorder_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.workorder_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.workorder_table.verticalHeader().setVisible(False)
        self.workorder_table.doubleClicked.connect(self._on_edit_workorder)
        wo_list_layout.addWidget(self.workorder_table, stretch=1)

        self.defect_detail_tabs.addTab(wo_list_widget, "🔧 维修工单")
        self.defect_detail_tabs.currentChanged.connect(self._on_defect_tab_changed)

        layout.addWidget(self.defect_detail_tabs, stretch=2)

        return widget

    def _on_defect_tab_changed(self, index: int):
        if self.defect_detail_tabs.tabText(index).startswith("📋"):
            self._refresh_defects()
        elif self.defect_detail_tabs.tabText(index).startswith("🔧"):
            self._refresh_workorders()

    def _create_archive_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        btn_row = QHBoxLayout()
        self.btn_open_archive = QPushButton("📂 打开文件")
        self.btn_open_archive.clicked.connect(self._on_open_archive_file)
        btn_row.addWidget(self.btn_open_archive)

        self.btn_delete_archive = QPushButton("🗑 删除记录")
        self.btn_delete_archive.clicked.connect(self._on_delete_archive)
        btn_row.addWidget(self.btn_delete_archive)

        btn_row.addWidget(QLabel("类型筛选:"))
        self.archive_type_filter = QComboBox()
        self.archive_type_filter.addItem("全部", None)
        self.archive_type_filter.addItem("建筑巡检报告", "建筑巡检报告")
        self.archive_type_filter.addItem("对比分析报告", "对比分析报告")
        self.archive_type_filter.addItem("病害处置报告", "病害处置报告")
        self.archive_type_filter.currentIndexChanged.connect(self._refresh_archives)
        btn_row.addWidget(self.archive_type_filter)

        btn_row.addStretch()
        self.btn_refresh_archives = QPushButton("🔄 刷新")
        self.btn_refresh_archives.clicked.connect(self._refresh_archives)
        btn_row.addWidget(self.btn_refresh_archives)
        layout.addLayout(btn_row)

        self.archive_table = QTableWidget()
        self.archive_table.setAlternatingRowColors(True)
        self.archive_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.archive_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.archive_table.verticalHeader().setVisible(False)
        self.archive_table.doubleClicked.connect(self._on_open_archive_file)
        layout.addWidget(self.archive_table, stretch=1)

        return widget

    def _create_priority_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.deadline_alert_banner = QLabel("")
        self.deadline_alert_banner.setStyleSheet("""
            padding: 10px; background: #fff3cd; border: 1px solid #ffeeba;
            border-radius: 4px; color: #856404; font-weight: bold;
        """)
        self.deadline_alert_banner.hide()
        layout.addWidget(self.deadline_alert_banner)

        stat_row = QHBoxLayout()
        self.prio_stat_urgent = self._create_stat_card("紧急", "0", "#e74c3c")
        self.prio_stat_high = self._create_stat_card("高", "0", "#e67e22")
        self.prio_stat_medium = self._create_stat_card("中", "0", "#3498db")
        self.prio_stat_low = self._create_stat_card("低", "0", "#27ae60")
        self.stat_overdue = self._create_stat_card("已逾期", "0", "#c0392b")
        stat_row.addWidget(self.prio_stat_urgent)
        stat_row.addWidget(self.prio_stat_high)
        stat_row.addWidget(self.prio_stat_medium)
        stat_row.addWidget(self.prio_stat_low)
        stat_row.addWidget(self.stat_overdue)
        layout.addLayout(stat_row)

        chart_splitter = QSplitter(Qt.Horizontal)
        self.priority_chart = ChartWidget()
        self.deadline_chart = ChartWidget()
        chart_splitter.addWidget(self.priority_chart)
        chart_splitter.addWidget(self.deadline_chart)
        chart_splitter.setStretchFactor(0, 1)
        chart_splitter.setStretchFactor(1, 1)
        layout.addWidget(chart_splitter, stretch=1)

        btn_row = QHBoxLayout()
        self.btn_auto_priority = QPushButton("🎯 自动计算优先级")
        self.btn_auto_priority.setStyleSheet("background-color: #9b59b6; color: white; padding: 6px 16px;")
        self.btn_auto_priority.clicked.connect(self._on_auto_calculate_priority)
        btn_row.addWidget(self.btn_auto_priority)

        self.btn_apply_priority_sort = QPushButton("🔄 刷新排序")
        self.btn_apply_priority_sort.clicked.connect(self._refresh_priority_list)
        btn_row.addWidget(self.btn_apply_priority_sort)

        btn_row.addWidget(QLabel("建筑筛选:"))
        self.priority_building_filter = QComboBox()
        self.priority_building_filter.addItem("全部建筑", None)
        for b in BuildingRepository.get_all():
            self.priority_building_filter.addItem(b["name"], b["id"])
        self.priority_building_filter.currentIndexChanged.connect(self._refresh_priority_list)
        btn_row.addWidget(self.priority_building_filter)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.priority_table = QTableWidget()
        self.priority_table.setAlternatingRowColors(True)
        self.priority_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.priority_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.priority_table.verticalHeader().setVisible(False)
        layout.addWidget(self.priority_table, stretch=2)

        return widget

    def _create_resource_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        stat_row = QHBoxLayout()
        self.res_stat_total = self._create_stat_card("资源记录总数", "0", "#3498db")
        self.res_stat_cost = self._create_stat_card("总成本(¥)", "0", "#e74c3c")
        self.res_stat_material = self._create_stat_card("材料类", "0", "#27ae60")
        self.res_stat_labor = self._create_stat_card("人工类", "0", "#f39c12")
        stat_row.addWidget(self.res_stat_total)
        stat_row.addWidget(self.res_stat_cost)
        stat_row.addWidget(self.res_stat_material)
        stat_row.addWidget(self.res_stat_labor)
        layout.addLayout(stat_row)

        chart_splitter = QSplitter(Qt.Horizontal)
        self.resource_cost_chart = ChartWidget()
        self.resource_building_chart = ChartWidget()
        chart_splitter.addWidget(self.resource_cost_chart)
        chart_splitter.addWidget(self.resource_building_chart)
        chart_splitter.setStretchFactor(0, 1)
        chart_splitter.setStretchFactor(1, 1)
        layout.addWidget(chart_splitter, stretch=1)

        self.resource_detail_tabs = QTabWidget()

        res_list_widget = QWidget()
        res_list_layout = QVBoxLayout(res_list_widget)

        btn_row = QHBoxLayout()
        self.btn_add_resource = QPushButton("➕ 新增资源")
        self.btn_add_resource.setStyleSheet("background-color: #27ae60; color: white; padding: 6px 16px;")
        self.btn_add_resource.clicked.connect(self._on_add_resource)
        btn_row.addWidget(self.btn_add_resource)

        self.btn_delete_resource = QPushButton("🗑 删除")
        self.btn_delete_resource.clicked.connect(self._on_delete_resource)
        btn_row.addWidget(self.btn_delete_resource)

        btn_row.addWidget(QLabel("类型筛选:"))
        self.res_type_filter = QComboBox()
        self.res_type_filter.addItem("全部", None)
        for t in RESOURCE_TYPES:
            self.res_type_filter.addItem(t, t)
        self.res_type_filter.currentIndexChanged.connect(self._refresh_resources)
        btn_row.addWidget(self.res_type_filter)

        btn_row.addWidget(QLabel("建筑筛选:"))
        self.res_building_filter = QComboBox()
        self.res_building_filter.addItem("全部", None)
        for b in BuildingRepository.get_all():
            self.res_building_filter.addItem(b["name"], b["id"])
        self.res_building_filter.currentIndexChanged.connect(self._refresh_resources)
        btn_row.addWidget(self.res_building_filter)

        btn_row.addStretch()
        self.btn_refresh_resources = QPushButton("🔄 刷新")
        self.btn_refresh_resources.clicked.connect(self._refresh_resources)
        btn_row.addWidget(self.btn_refresh_resources)
        res_list_layout.addLayout(btn_row)

        self.resource_table = QTableWidget()
        self.resource_table.setAlternatingRowColors(True)
        self.resource_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.resource_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.resource_table.verticalHeader().setVisible(False)
        self.resource_table.doubleClicked.connect(self._on_edit_resource)
        res_list_layout.addWidget(self.resource_table, stretch=1)

        self.resource_detail_tabs.addTab(res_list_widget, "📋 资源明细")
        layout.addWidget(self.resource_detail_tabs, stretch=2)

        return widget

    def _create_recurrence_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        stat_row = QHBoxLayout()
        self.recur_stat_total = self._create_stat_card("复发总次数", "0", "#e74c3c")
        self.recur_stat_avg_days = self._create_stat_card("平均间隔天数", "0", "#f39c12")
        self.recur_stat_same_loc = self._create_stat_card("同位置复发", "0", "#c0392b")
        self.recur_stat_same_type = self._create_stat_card("同类病害", "0", "#e67e22")
        stat_row.addWidget(self.recur_stat_total)
        stat_row.addWidget(self.recur_stat_avg_days)
        stat_row.addWidget(self.recur_stat_same_loc)
        stat_row.addWidget(self.recur_stat_same_type)
        layout.addLayout(stat_row)

        self.recurrence_chart = ChartWidget()
        layout.addWidget(self.recurrence_chart, stretch=1)

        self.recur_detail_tabs = QTabWidget()

        known_widget = QWidget()
        known_layout = QVBoxLayout(known_widget)
        btn_row1 = QHBoxLayout()
        btn_row1.addWidget(QLabel("已知复发关联:"))
        btn_row1.addStretch()
        self.btn_refresh_recurrence = QPushButton("🔄 刷新")
        self.btn_refresh_recurrence.clicked.connect(self._refresh_recurrence)
        btn_row1.addWidget(self.btn_refresh_recurrence)
        known_layout.addLayout(btn_row1)
        self.recurrence_known_table = QTableWidget()
        self.recurrence_known_table.setAlternatingRowColors(True)
        self.recurrence_known_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.recurrence_known_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.recurrence_known_table.verticalHeader().setVisible(False)
        known_layout.addWidget(self.recurrence_known_table, stretch=1)
        self.recur_detail_tabs.addTab(known_widget, "✅ 已关联复发")

        detect_widget = QWidget()
        detect_layout = QVBoxLayout(detect_widget)
        btn_row2 = QHBoxLayout()
        self.btn_detect_recurrence = QPushButton("🔍 智能检测潜在复发")
        self.btn_detect_recurrence.setStyleSheet("background-color: #e67e22; color: white; padding: 6px 16px;")
        self.btn_detect_recurrence.clicked.connect(self._on_detect_recurrence)
        btn_row2.addWidget(self.btn_detect_recurrence)
        self.btn_mark_recurrence = QPushButton("🔗 标记关联")
        self.btn_mark_recurrence.clicked.connect(self._on_mark_recurrence)
        btn_row2.addWidget(self.btn_mark_recurrence)
        btn_row2.addStretch()
        detect_layout.addLayout(btn_row2)
        self.recurrence_detect_table = QTableWidget()
        self.recurrence_detect_table.setAlternatingRowColors(True)
        self.recurrence_detect_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.recurrence_detect_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.recurrence_detect_table.verticalHeader().setVisible(False)
        detect_layout.addWidget(self.recurrence_detect_table, stretch=1)
        self.recur_detail_tabs.addTab(detect_widget, "🔍 潜在复发检测")
        layout.addWidget(self.recur_detail_tabs, stretch=2)

        return widget

    def _create_effectiveness_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        stat_row = QHBoxLayout()
        self.eff_stat_evaluated = self._create_stat_card("已评估数", "0", "#3498db")
        self.eff_stat_avg_imp = self._create_stat_card("平均改善率(%)", "0", "#27ae60")
        self.eff_stat_excellent = self._create_stat_card("优秀", "0", "#27ae60")
        self.eff_stat_poor = self._create_stat_card("较差", "0", "#e74c3c")
        stat_row.addWidget(self.eff_stat_evaluated)
        stat_row.addWidget(self.eff_stat_avg_imp)
        stat_row.addWidget(self.eff_stat_excellent)
        stat_row.addWidget(self.eff_stat_poor)
        layout.addLayout(stat_row)

        chart_splitter = QSplitter(Qt.Horizontal)
        self.effect_dist_chart = ChartWidget()
        self.effect_type_chart = ChartWidget()
        chart_splitter.addWidget(self.effect_dist_chart)
        chart_splitter.addWidget(self.effect_type_chart)
        chart_splitter.setStretchFactor(0, 1)
        chart_splitter.setStretchFactor(1, 1)
        layout.addWidget(chart_splitter, stretch=1)

        self.eff_detail_tabs = QTabWidget()

        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        label1 = QLabel("🏆 改善效果最佳的病害处置:")
        label1.setFont(QFont("", 11, QFont.Bold))
        top_layout.addWidget(label1)
        self.effect_top_table = QTableWidget()
        self.effect_top_table.setAlternatingRowColors(True)
        self.effect_top_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.effect_top_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.effect_top_table.verticalHeader().setVisible(False)
        top_layout.addWidget(self.effect_top_table, stretch=1)
        self.eff_detail_tabs.addTab(top_widget, "🏆 最佳效果")

        low_widget = QWidget()
        low_layout = QVBoxLayout(low_widget)
        label2 = QLabel("⚠ 改善效果较差的病害处置:")
        label2.setFont(QFont("", 11, QFont.Bold))
        low_layout.addWidget(label2)
        self.effect_low_table = QTableWidget()
        self.effect_low_table.setAlternatingRowColors(True)
        self.effect_low_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.effect_low_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.effect_low_table.verticalHeader().setVisible(False)
        low_layout.addWidget(self.effect_low_table, stretch=1)
        self.eff_detail_tabs.addTab(low_widget, "⚠ 待改进")

        btn_row = QHBoxLayout()
        btn_row.addWidget(QLabel("建筑筛选:"))
        self.eff_building_filter = QComboBox()
        self.eff_building_filter.addItem("全部", None)
        for b in BuildingRepository.get_all():
            self.eff_building_filter.addItem(b["name"], b["id"])
        self.eff_building_filter.currentIndexChanged.connect(self._refresh_effectiveness)
        btn_row.addWidget(self.eff_building_filter)
        btn_row.addStretch()
        self.btn_refresh_effectiveness = QPushButton("🔄 刷新")
        self.btn_refresh_effectiveness.clicked.connect(self._refresh_effectiveness)
        btn_row.addWidget(self.btn_refresh_effectiveness)

        main_bottom = QWidget()
        main_bottom_layout = QVBoxLayout(main_bottom)
        main_bottom_layout.addLayout(btn_row)
        main_bottom_layout.addWidget(self.eff_detail_tabs)
        layout.addWidget(main_bottom, stretch=2)

        return widget

    def _create_performance_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        stat_row = QHBoxLayout()
        self.perf_stat_total = self._create_stat_card("病害总数", "0", "#3498db")
        self.perf_stat_closed = self._create_stat_card("已闭环", "0", "#27ae60")
        self.perf_stat_rate = self._create_stat_card("闭环率(%)", "0", "#9b59b6")
        self.perf_stat_avg_days = self._create_stat_card("平均周期(天)", "0", "#f39c12")
        self.perf_stat_rework = self._create_stat_card("返工数", "0", "#e74c3c")
        stat_row.addWidget(self.perf_stat_total)
        stat_row.addWidget(self.perf_stat_closed)
        stat_row.addWidget(self.perf_stat_rate)
        stat_row.addWidget(self.perf_stat_avg_days)
        stat_row.addWidget(self.perf_stat_rework)
        layout.addLayout(stat_row)

        self.perf_chart = ChartWidget()
        layout.addWidget(self.perf_chart, stretch=1)

        self.perf_detail_tabs = QTabWidget()

        bldg_widget = QWidget()
        bldg_layout = QVBoxLayout(bldg_widget)
        btn_row1 = QHBoxLayout()
        btn_row1.addWidget(QLabel("按建筑统计:"))
        btn_row1.addStretch()
        self.btn_perf_chart_building = QPushButton("📊 建筑绩效图表")
        self.btn_perf_chart_building.clicked.connect(lambda: self._refresh_performance_chart("building"))
        btn_row1.addWidget(self.btn_perf_chart_building)
        bldg_layout.addLayout(btn_row1)
        self.perf_building_table = QTableWidget()
        self.perf_building_table.setAlternatingRowColors(True)
        self.perf_building_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.perf_building_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.perf_building_table.verticalHeader().setVisible(False)
        bldg_layout.addWidget(self.perf_building_table, stretch=1)
        self.perf_detail_tabs.addTab(bldg_widget, "🏛 按建筑")

        comp_widget = QWidget()
        comp_layout = QVBoxLayout(comp_widget)
        btn_row2 = QHBoxLayout()
        btn_row2.addWidget(QLabel("按构件统计:"))
        btn_row2.addStretch()
        self.btn_perf_chart_component = QPushButton("📊 构件绩效图表")
        self.btn_perf_chart_component.clicked.connect(lambda: self._refresh_performance_chart("component"))
        btn_row2.addWidget(self.btn_perf_chart_component)
        comp_layout.addLayout(btn_row2)
        self.perf_component_table = QTableWidget()
        self.perf_component_table.setAlternatingRowColors(True)
        self.perf_component_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.perf_component_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.perf_component_table.verticalHeader().setVisible(False)
        comp_layout.addWidget(self.perf_component_table, stretch=1)
        self.perf_detail_tabs.addTab(comp_widget, "🪵 按构件")

        type_widget = QWidget()
        type_layout = QVBoxLayout(type_widget)
        type_layout.addWidget(QLabel("按病害类型统计:"))
        self.perf_type_table = QTableWidget()
        self.perf_type_table.setAlternatingRowColors(True)
        self.perf_type_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.perf_type_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.perf_type_table.verticalHeader().setVisible(False)
        type_layout.addWidget(self.perf_type_table, stretch=1)
        self.perf_detail_tabs.addTab(type_widget, "🔧 按病害类型")

        btn_row3 = QHBoxLayout()
        btn_row3.addWidget(QLabel("建筑筛选:"))
        self.perf_building_filter = QComboBox()
        self.perf_building_filter.addItem("全部", None)
        for b in BuildingRepository.get_all():
            self.perf_building_filter.addItem(b["name"], b["id"])
        self.perf_building_filter.currentIndexChanged.connect(self._refresh_performance)
        btn_row3.addWidget(self.perf_building_filter)
        btn_row3.addStretch()
        self.btn_refresh_performance = QPushButton("🔄 刷新")
        self.btn_refresh_performance.clicked.connect(self._refresh_performance)
        btn_row3.addWidget(self.btn_refresh_performance)

        main_bottom = QWidget()
        main_bottom_layout = QVBoxLayout(main_bottom)
        main_bottom_layout.addLayout(btn_row3)
        main_bottom_layout.addWidget(self.perf_detail_tabs)
        layout.addWidget(main_bottom, stretch=2)

        return widget

    def _create_collaboration_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.collab_detail_tabs = QTabWidget()

        user_widget = QWidget()
        user_layout = QVBoxLayout(user_widget)
        btn_row1 = QHBoxLayout()
        self.btn_add_user = QPushButton("➕ 新增用户")
        self.btn_add_user.setStyleSheet("background-color: #3498db; color: white; padding: 6px 16px;")
        self.btn_add_user.clicked.connect(self._on_add_user)
        btn_row1.addWidget(self.btn_add_user)
        self.btn_edit_user = QPushButton("✏ 编辑用户")
        self.btn_edit_user.clicked.connect(self._on_edit_user)
        btn_row1.addWidget(self.btn_edit_user)
        self.btn_delete_user = QPushButton("🗑 删除用户")
        self.btn_delete_user.clicked.connect(self._on_delete_user)
        btn_row1.addWidget(self.btn_delete_user)
        btn_row1.addStretch()
        self.btn_refresh_users = QPushButton("🔄 刷新")
        self.btn_refresh_users.clicked.connect(self._refresh_users)
        btn_row1.addWidget(self.btn_refresh_users)
        user_layout.addLayout(btn_row1)
        self.user_table = QTableWidget()
        self.user_table.setAlternatingRowColors(True)
        self.user_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.user_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.user_table.verticalHeader().setVisible(False)
        self.user_table.doubleClicked.connect(self._on_edit_user)
        user_layout.addWidget(self.user_table, stretch=1)
        self.collab_detail_tabs.addTab(user_widget, "👤 用户管理")

        role_widget = QWidget()
        role_layout = QVBoxLayout(role_widget)
        btn_row2 = QHBoxLayout()
        self.btn_edit_role_perm = QPushButton("🔐 编辑角色权限")
        self.btn_edit_role_perm.setStyleSheet("background-color: #9b59b6; color: white; padding: 6px 16px;")
        self.btn_edit_role_perm.clicked.connect(self._on_edit_role_permissions)
        btn_row2.addWidget(self.btn_edit_role_perm)
        btn_row2.addStretch()
        self.btn_refresh_roles = QPushButton("🔄 刷新")
        self.btn_refresh_roles.clicked.connect(self._refresh_roles)
        btn_row2.addWidget(self.btn_refresh_roles)
        role_layout.addLayout(btn_row2)
        self.role_table = QTableWidget()
        self.role_table.setAlternatingRowColors(True)
        self.role_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.role_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.role_table.verticalHeader().setVisible(False)
        role_layout.addWidget(self.role_table, stretch=1)
        self.collab_detail_tabs.addTab(role_widget, "🎭 角色与权限")

        layout.addWidget(self.collab_detail_tabs)
        return widget

    def _create_report_center_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        title = QLabel("📑 综合报告中心")
        title.setFont(QFont("", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        info = QLabel("选择需要的报告类型，一键生成多维度综合分析报告")
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("color: #666;")
        layout.addWidget(info)

        self.report_type_tabs = QTabWidget()

        summary_widget = QWidget()
        summary_layout = QVBoxLayout(summary_widget)
        summary_desc = QLabel("📊 综合汇总报告：包含风险概览、病害统计、资源消耗、处置效果等核心指标")
        summary_desc.setWordWrap(True)
        summary_desc.setStyleSheet("padding: 15px; background: #eaf2f8; border-radius: 6px;")
        summary_layout.addWidget(summary_desc)
        form1 = QFormLayout()
        self.report_summary_building = QComboBox()
        self.report_summary_building.addItem("全部建筑", None)
        for b in BuildingRepository.get_all():
            self.report_summary_building.addItem(b["name"], b["id"])
        form1.addRow("选择建筑:", self.report_summary_building)
        self.report_summary_period = QComboBox()
        self.report_summary_period.addItems(["本月", "本季度", "本年度", "全部"])
        form1.addRow("统计周期:", self.report_summary_period)
        summary_layout.addLayout(form1)
        btn1 = QPushButton("📄 生成综合汇总报告")
        btn1.setStyleSheet("background-color: #3498db; color: white; padding: 10px; font-size: 12px; font-weight: bold;")
        btn1.clicked.connect(self._on_generate_summary_report)
        summary_layout.addWidget(btn1)
        summary_layout.addStretch()
        self.report_type_tabs.addTab(summary_widget, "📊 综合汇总")

        perf_widget = QWidget()
        perf_layout = QVBoxLayout(perf_widget)
        perf_desc = QLabel("🏆 闭环绩效报告：各建筑/构件的病害闭环率、平均处理周期、返工率等绩效分析")
        perf_desc.setWordWrap(True)
        perf_desc.setStyleSheet("padding: 15px; background: #eafaf1; border-radius: 6px;")
        perf_layout.addWidget(perf_desc)
        form2 = QFormLayout()
        self.report_perf_building = QComboBox()
        self.report_perf_building.addItem("全部建筑", None)
        for b in BuildingRepository.get_all():
            self.report_perf_building.addItem(b["name"], b["id"])
        form2.addRow("选择建筑:", self.report_perf_building)
        perf_layout.addLayout(form2)
        btn2 = QPushButton("📄 生成闭环绩效报告")
        btn2.setStyleSheet("background-color: #27ae60; color: white; padding: 10px; font-size: 12px; font-weight: bold;")
        btn2.clicked.connect(self._on_generate_performance_report)
        perf_layout.addWidget(btn2)
        perf_layout.addStretch()
        self.report_type_tabs.addTab(perf_widget, "🏆 闭环绩效")

        effect_widget = QWidget()
        effect_layout = QVBoxLayout(effect_widget)
        effect_desc = QLabel("📉 处置效果报告：维修前后含水率对比、不同病害类型处置效果排名、改善率分析")
        effect_desc.setWordWrap(True)
        effect_desc.setStyleSheet("padding: 15px; background: #fef9e7; border-radius: 6px;")
        effect_layout.addWidget(effect_desc)
        form3 = QFormLayout()
        self.report_eff_building = QComboBox()
        self.report_eff_building.addItem("全部建筑", None)
        for b in BuildingRepository.get_all():
            self.report_eff_building.addItem(b["name"], b["id"])
        form3.addRow("选择建筑:", self.report_eff_building)
        effect_layout.addLayout(form3)
        btn3 = QPushButton("📄 生成处置效果报告")
        btn3.setStyleSheet("background-color: #f39c12; color: white; padding: 10px; font-size: 12px; font-weight: bold;")
        btn3.clicked.connect(self._on_generate_effect_report)
        effect_layout.addWidget(btn3)
        effect_layout.addStretch()
        self.report_type_tabs.addTab(effect_widget, "📉 处置效果")

        resource_widget = QWidget()
        resource_layout = QVBoxLayout(resource_widget)
        resource_desc = QLabel("📦 资源统计报告：维修材料、人工、设备消耗统计，按建筑/病害类型的成本分析")
        resource_desc.setWordWrap(True)
        resource_desc.setStyleSheet("padding: 15px; background: #fdedec; border-radius: 6px;")
        resource_layout.addWidget(resource_desc)
        form4 = QFormLayout()
        self.report_res_building = QComboBox()
        self.report_res_building.addItem("全部建筑", None)
        for b in BuildingRepository.get_all():
            self.report_res_building.addItem(b["name"], b["id"])
        form4.addRow("选择建筑:", self.report_res_building)
        self.report_res_period = QComboBox()
        self.report_res_period.addItems(["本月", "本季度", "本年度", "全部"])
        form4.addRow("统计周期:", self.report_res_period)
        resource_layout.addLayout(form4)
        btn4 = QPushButton("📄 生成资源统计报告")
        btn4.setStyleSheet("background-color: #e74c3c; color: white; padding: 10px; font-size: 12px; font-weight: bold;")
        btn4.clicked.connect(self._on_generate_resource_report)
        resource_layout.addWidget(btn4)
        resource_layout.addStretch()
        self.report_type_tabs.addTab(resource_widget, "📦 资源统计")

        layout.addWidget(self.report_type_tabs, stretch=1)
        return widget

    def _create_settings_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("检测阈值设置")
        form = QFormLayout(group)

        self.spin_threshold = QDoubleSpinBox()
        self.spin_threshold.setRange(0, 100)
        self.spin_threshold.setDecimals(1)
        self.spin_threshold.setSingleStep(0.5)
        self.spin_threshold.setSuffix(" %")
        self.spin_threshold.setValue(SettingsRepository.get_moisture_threshold())
        form.addRow("含水率预警阈值:", self.spin_threshold)

        fixed_label = QLabel("连续 3 次超过阈值判定为高风险（已固定）")
        fixed_label.setStyleSheet("color: #666; font-style: italic;")
        form.addRow("连续超标判定:", fixed_label)

        self.spin_inspection_interval = QSpinBox()
        self.spin_inspection_interval.setRange(7, 180)
        self.spin_inspection_interval.setSuffix(" 天")
        self.spin_inspection_interval.setValue(SettingsRepository.get_default_inspection_interval())
        form.addRow("默认巡检间隔:", self.spin_inspection_interval)

        self.spin_reminder_days = QSpinBox()
        self.spin_reminder_days.setRange(0, 30)
        self.spin_reminder_days.setSuffix(" 天")
        self.spin_reminder_days.setValue(SettingsRepository.get_default_reminder_days())
        form.addRow("计划提前提醒:", self.spin_reminder_days)

        self.btn_save_settings = QPushButton("保存设置")
        self.btn_save_settings.clicked.connect(self._on_save_settings)
        form.addRow("", self.btn_save_settings)

        layout.addWidget(group)

        tip = QLabel(
            "\n📖 系统使用说明:\n\n"
            "【基础功能】\n"
            "1. 首先在左侧创建建筑档案\n"
            "2. 在建筑下创建梁、柱、斗拱、枋、檩、椽等木构件档案\n"
            "3. 选择构件后通过'导入CSV数据'批量导入检测记录\n"
            "4. 在各标签页查看趋势、对比、风险分析等信息\n\n"
            "【新增高级功能】\n"
            "📊 总览看板：多建筑整体风险分布与统计概览\n"
            "🔍 横向对比：按构件类型/建筑/位置的多维对比分析\n"
            "🌤 季节性分析：识别含水率的季节波动规律\n"
            "📈 趋势预测：基于历史数据预测未来风险\n"
            "📋 巡检计划：管理巡检任务并设置提醒\n"
            "⚠ 异常复核：标记异常检测数据并进行人工复核\n"
            "📁 报告归档：批量导出报告并历史归档管理\n\n"
            "【CSV导入格式】\n"
            "必填列: 检测时间、检测位置、含水率\n"
            "可选列: 温度、环境湿度、操作人员、备注\n"
        )
        tip.setStyleSheet("color: #444; padding: 20px; background: #f8f9fa; border-radius: 6px;")
        layout.addWidget(tip)
        layout.addStretch()
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
        compare_act.triggered.connect(lambda: self.tabs.setCurrentIndex(5))
        analyze_menu.addAction(compare_act)

        seasonal_act = QAction("季节性波动分析", self)
        seasonal_act.triggered.connect(lambda: self.tabs.setCurrentIndex(6))
        analyze_menu.addAction(seasonal_act)

        prediction_act = QAction("风险趋势预测", self)
        prediction_act.triggered.connect(lambda: self.tabs.setCurrentIndex(7))
        analyze_menu.addAction(prediction_act)

        plan_menu = menubar.addMenu("巡检")
        plan_act = QAction("巡检计划管理", self)
        plan_act.triggered.connect(lambda: self.tabs.setCurrentIndex(8))
        plan_menu.addAction(plan_act)

        review_act = QAction("异常复核管理", self)
        review_act.triggered.connect(lambda: self.tabs.setCurrentIndex(9))
        plan_menu.addAction(review_act)

        scan_anomaly_act = QAction("自动扫描异常数据", self)
        scan_anomaly_act.triggered.connect(self._on_auto_scan_anomalies)
        plan_menu.addAction(scan_anomaly_act)

        archive_menu = menubar.addMenu("归档")
        archive_list_act = QAction("报告归档历史", self)
        archive_list_act.triggered.connect(lambda: self.tabs.setCurrentIndex(10))
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
            self.detail_label.setText("已选择建筑，请在左侧选择具体构件")
            self.detail_info.hide()
            self.stats_group.hide()
            self.risk_summary.setText("请选择构件查看风险分析")
            self.risk_summary.show()
            self.risk_table.hide()
        elif data["type"] == "component":
            self.current_component_id = data["id"]
            self._load_component_detail()
            self._refresh_records_table()
            self._refresh_chart()
            self._refresh_risk_analysis()

        current_tab = self.tabs.tabText(self.tabs.currentIndex())
        if "病害闭环" in current_tab:
            self._refresh_defects()
            self._refresh_workorders()

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
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
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
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")

    def _on_delete_item(self, data: Dict[str, Any]):
        if data["type"] == "building":
            building = BuildingRepository.get_by_id(data["id"])
            if not building:
                return
            reply = QMessageBox.question(
                self, "确认删除",
                f"确定要删除建筑「{building['name']}」吗？\n"
                f"注意：该建筑下存在构件时将无法删除。",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
            try:
                BuildingRepository.delete(data["id"])
                self.current_building_id = None
                self.current_component_id = None
                self.refresh_buildings()
                QMessageBox.information(self, "成功", "建筑已删除")
            except ValueError as e:
                QMessageBox.warning(self, "无法删除", str(e))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败: {str(e)}")

        elif data["type"] == "component":
            component = ComponentRepository.get_by_id(data["id"])
            if not component:
                return
            has_records = ComponentRepository.has_records(data["id"])
            warn_msg = ""
            if has_records:
                warn_msg = "\n⚠ 该构件存在历史检测记录，将无法删除。"
            reply = QMessageBox.question(
                self, "确认删除",
                f"确定要删除构件「{component['code']} - {component['name']}」吗？{warn_msg}",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
            try:
                ComponentRepository.delete(data["id"])
                self.current_component_id = None
                self.refresh_buildings()
                QMessageBox.information(self, "成功", "构件已删除")
            except ValueError as e:
                QMessageBox.warning(self, "无法删除", str(e))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败: {str(e)}")

    def _on_add_building(self):
        dlg = BuildingDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                BuildingRepository.create(**data)
                self.refresh_buildings()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建失败: {str(e)}")

    def _on_add_component(self):
        buildings = BuildingRepository.get_all()
        if not buildings:
            QMessageBox.warning(self, "提示", "请先创建建筑档案")
            return
        dlg = ComponentDialog(self, buildings=buildings)
        if dlg.exec():
            data = dlg.get_data()
            try:
                ComponentRepository.create(**data)
                self.refresh_buildings()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建失败: {str(e)}")

    def _load_component_detail(self):
        comp = ComponentRepository.get_by_id(self.current_component_id)
        building = BuildingRepository.get_by_id(comp["building_id"]) if comp else None

        if not comp:
            return

        self.detail_label.setText(
            f"{building['name'] if building else ''} - {comp['name']}"
        )
        self.detail_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; padding: 10px; "
            "background: #ecf0f1; border-radius: 4px;"
        )

        self.detail_code.setText(comp["code"])
        self.detail_name.setText(comp["name"])
        self.detail_type.setText(comp["component_type"])
        self.detail_material.setText(comp.get("material") or "-")
        self.detail_position.setText(comp.get("position") or "-")
        self.detail_desc.setText(comp.get("description") or "-")
        self.detail_info.show()

        records = RecordRepository.get_by_component(self.current_component_id)
        stats = calculate_statistics(records)
        risk = analyze_component_risk(self.current_component_id)
        positions = RecordRepository.get_positions(self.current_component_id)

        self.stat_records.setText(str(stats["count"]))
        self.stat_positions.setText(", ".join(positions) if positions else "-")
        self.stat_avg.setText(f"{stats['avg']}%")
        self.stat_max.setText(f"{stats['max']}%")
        self.stat_min.setText(f"{stats['min']}%")
        self.stat_risk.setText(risk["overall_risk_level"])
        color = RISK_COLORS.get(risk["overall_risk_level"], QColor(0, 0, 0))
        self.stat_risk.setStyleSheet(f"color: {color.name()};")
        self.stats_group.show()

        self.record_position_filter.blockSignals(True)
        self.record_position_filter.clear()
        self.record_position_filter.addItem("全部")
        for p in positions:
            self.record_position_filter.addItem(p)
        self.record_position_filter.blockSignals(False)

        self.chart_position_filter.blockSignals(True)
        self.chart_position_filter.clear()
        self.chart_position_filter.addItem("全部")
        for p in positions:
            self.chart_position_filter.addItem(p)
        self.chart_position_filter.blockSignals(False)

    def _refresh_records_table(self):
        if not self.current_component_id:
            self.records_table.setRowCount(0)
            return

        position = self.record_position_filter.currentText()
        if position == "全部":
            position = None

        records = RecordRepository.get_by_component(
            self.current_component_id, position
        )

        headers = ["ID", "检测时间", "检测位置", "含水率(%)", "温度(℃)",
                   "环境湿度(%)", "操作人员", "备注"]
        self.records_table.setColumnCount(len(headers))
        self.records_table.setHorizontalHeaderLabels(headers)
        self.records_table.setRowCount(len(records))

        threshold = SettingsRepository.get_moisture_threshold()

        for row, r in enumerate(records):
            self.records_table.setItem(row, 0, QTableWidgetItem(str(r["id"])))
            self.records_table.setItem(row, 1, QTableWidgetItem(r["measure_time"]))
            self.records_table.setItem(row, 2, QTableWidgetItem(r["measure_position"]))

            moisture_item = QTableWidgetItem(f"{r['moisture']:.1f}")
            if r["moisture"] > threshold:
                moisture_item.setForeground(QColor(231, 76, 60))
                moisture_item.setFont(QFont("", 10, QFont.Bold))
            self.records_table.setItem(row, 3, moisture_item)

            temp_val = f"{r['temperature']:.1f}" if r["temperature"] is not None else "-"
            self.records_table.setItem(row, 4, QTableWidgetItem(temp_val))

            hum_val = f"{r['humidity']:.1f}" if r["humidity"] is not None else "-"
            self.records_table.setItem(row, 5, QTableWidgetItem(hum_val))

            self.records_table.setItem(row, 6, QTableWidgetItem(r.get("operator") or ""))
            self.records_table.setItem(row, 7, QTableWidgetItem(r.get("remark") or ""))

        self.records_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.records_table.horizontalHeader().setStretchLastSection(True)

    def _refresh_chart(self):
        if not self.current_component_id:
            return

        records = RecordRepository.get_by_component(self.current_component_id)
        threshold = SettingsRepository.get_moisture_threshold()

        chart_type = self.chart_type.currentText()
        position = self.chart_position_filter.currentText()
        if position == "全部":
            position = None

        if chart_type == "趋势图":
            self.chart_widget.plot_trend(records, position, threshold)
        elif chart_type == "位置对比图":
            self.chart_widget.plot_position_comparison(records)
        elif chart_type == "统计柱状图":
            positions = RecordRepository.get_positions(self.current_component_id)
            stats = {}
            for p in positions:
                p_records = RecordRepository.get_by_component(
                    self.current_component_id, p
                )
                if p_records:
                    stats[p] = calculate_statistics(p_records)
            self.chart_widget.plot_statistics_bar(stats, threshold)

    def _refresh_risk_analysis(self):
        if not self.current_component_id:
            self.risk_summary.setText("请选择构件查看风险分析")
            self.risk_summary.show()
            self.risk_table.hide()
            return

        result = analyze_component_risk(self.current_component_id)
        threshold = SettingsRepository.get_moisture_threshold()

        all_issues = []
        for item in result["consecutive_high_risk"]:
            all_issues.append({
                "类型": item["type"],
                "位置": item["position"],
                "详情": f"从 {item['start_time']} 到 {item['end_time']}，"
                        f"连续 {item['count']} 次超过阈值 {threshold}%，"
                        f"最高 {item['max_moisture']}%，平均 {item['avg_moisture']}%",
                "级别": "高风险"
            })

        for item in result["long_term_moisture"]:
            all_issues.append({
                "类型": item["type"],
                "位置": item["position"],
                "详情": f"持续 {item['duration_days']} 天，平均含水率 {item['avg_moisture']}%，"
                        f"超标记录占比 {item['high_ratio']}%",
                "级别": "高风险"
            })

        for item in result["sudden_rises"]:
            all_issues.append({
                "类型": item["type"],
                "位置": item["position"],
                "详情": f"{item['prev_time']} 值 {item['prev_moisture']}% → "
                        f"{item['curr_time']} 值 {item['curr_moisture']}%，"
                        f"增幅 {item['rise_ratio']}%",
                "级别": "中风险"
            })

        for item in result["missing_records"]:
            all_issues.append({
                "类型": item["type"],
                "位置": item["position"],
                "详情": f"上次检测 {item['prev_time']}，下次 {item['next_time']}，"
                        f"间隔 {item['gap_days']} 天（预计 {item['expected_days']} 天）",
                "级别": "中风险"
            })

        summary = (
            f"风险等级: <span style='color:{RISK_COLORS[result['overall_risk_level']].name()}; "
            f"font-weight:bold; font-size:16px;'>{result['overall_risk_level']}</span>"
            f"&nbsp;&nbsp;&nbsp;检测记录: {result['total_records']} 条"
            f"&nbsp;&nbsp;&nbsp;检测位置: {len(result['positions'])} 个"
            f"&nbsp;&nbsp;&nbsp;发现问题: <span style='color:#e74c3c; font-weight:bold;'>{len(all_issues)}</span> 项"
        )
        self.risk_summary.setText(summary)
        self.risk_summary.setStyleSheet(
            "font-size: 12px; padding: 12px; background: #ecf0f1; border-radius: 4px;"
        )

        if not all_issues:
            self.risk_table.hide()
            return

        headers = ["风险类型", "检测位置", "详细描述", "风险级别"]
        self.risk_table.setColumnCount(len(headers))
        self.risk_table.setHorizontalHeaderLabels(headers)
        self.risk_table.setRowCount(len(all_issues))

        for row, issue in enumerate(all_issues):
            for col, key in enumerate(["类型", "位置", "详情", "级别"]):
                item = QTableWidgetItem(issue[key])
                if key == "级别":
                    color = RISK_COLORS.get(issue[key], QColor(0, 0, 0))
                    item.setForeground(color)
                    item.setFont(QFont("", 10, QFont.Bold))
                self.risk_table.setItem(row, col, item)

        self.risk_table.show()

    def _on_import_csv(self):
        if not self.current_component_id:
            QMessageBox.warning(self, "提示", "请先选择一个构件")
            return
        dlg = CSVImportDialog(self, default_component_id=self.current_component_id)
        if dlg.exec():
            self.refresh_buildings()
            self._load_component_detail()
            self._refresh_records_table()
            self._refresh_chart()
            self._refresh_risk_analysis()

    def _on_delete_record(self):
        rows = self.records_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "提示", "请选择要删除的记录")
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除选中的 {len(rows)} 条记录吗？此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        deleted = 0
        for row in rows:
            record_id = int(self.records_table.item(row.row(), 0).text())
            if RecordRepository.delete(record_id):
                deleted += 1

        QMessageBox.information(self, "成功", f"已删除 {deleted} 条记录")
        self._load_component_detail()
        self._refresh_records_table()
        self._refresh_chart()
        self._refresh_risk_analysis()
        self.refresh_buildings()

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
            QMessageBox.information(
                self, "导出成功",
                f"报告已成功导出到:\n{output}"
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"生成报告失败: {str(e)}")

    def _on_save_settings(self):
        SettingsRepository.set_moisture_threshold(self.spin_threshold.value())
        SettingsRepository.set_default_inspection_interval(self.spin_inspection_interval.value())
        SettingsRepository.set_default_reminder_days(self.spin_reminder_days.value())
        QMessageBox.information(self, "成功", "设置已保存")
        if self.current_component_id:
            self._load_component_detail()
            self._refresh_records_table()
            self._refresh_chart()
            self._refresh_risk_analysis()
            self._refresh_seasonal()
            self._refresh_prediction()
        self.refresh_buildings()
        self._refresh_dashboard()

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

    def _on_tab_changed(self, index: int):
        tab_name = self.tabs.tabText(index)
        if "总览" in tab_name:
            self._refresh_dashboard()
        elif "横向对比" in tab_name:
            self._refresh_comparison()
        elif "季节性" in tab_name:
            self._refresh_seasonal()
        elif "趋势预测" in tab_name:
            self._refresh_prediction()
        elif "巡检计划" in tab_name:
            self._refresh_inspection_plans()
        elif "异常复核" in tab_name:
            self._refresh_anomaly_reviews()
        elif "病害闭环" in tab_name:
            self._refresh_defects()
            self._refresh_workorders()
        elif "报告归档" in tab_name:
            self._refresh_archives()
        elif "优先级排序" in tab_name:
            self._refresh_priority_list()
        elif "维修资源" in tab_name:
            self._refresh_resources()
        elif "复发分析" in tab_name:
            self._refresh_recurrence()
        elif "效果对比" in tab_name:
            self._refresh_effectiveness()
        elif "闭环绩效" in tab_name:
            self._refresh_performance()
        elif "角色协同" in tab_name:
            self._refresh_users()
            self._refresh_roles()
        elif "综合报告" in tab_name:
            pass

    def _start_reminder_timer(self):
        self._reminder_timer = QTimer(self)
        self._reminder_timer.timeout.connect(self._check_all_reminders)
        self._reminder_timer.start(60000)
        QTimer.singleShot(1000, self._check_all_reminders)

    def _check_all_reminders(self):
        self._check_inspection_reminders()
        self._check_defect_overdue()
        self._check_rectification_deadlines()

    def _check_inspection_reminders(self):
        upcoming = InspectionPlanRepository.get_upcoming()
        now = datetime.now()
        urgent_count = 0
        today_count = 0

        for plan in upcoming:
            try:
                plan_date = datetime.fromisoformat(plan["plan_date"].split(" ")[0])
                days_until = (plan_date - now).days
                reminder_days = plan.get("reminder_days", 7)
                if days_until <= 0:
                    urgent_count += 1
                elif days_until <= reminder_days:
                    today_count += 1
            except Exception:
                continue

        if urgent_count > 0 or today_count > 0:
            msg_parts = []
            if urgent_count > 0:
                msg_parts.append(f"🔴 {urgent_count} 个巡检计划已到期或逾期")
            if today_count > 0:
                msg_parts.append(f"🟡 {today_count} 个巡检计划即将到期")
            self.reminder_banner.setText(" | ".join(msg_parts) + " — 请前往「巡检计划」标签页查看详情")
            self.reminder_banner.show()
        else:
            self.reminder_banner.hide()

    def _refresh_dashboard(self):
        try:
            overview = get_multi_building_overview()
            type_dist = get_risk_distribution_by_type()

            self.dashboard_summary.setText(
                f"系统概览 — 数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            self._update_stat_card(self.stat_buildings, str(overview["total_buildings"]))
            self._update_stat_card(self.stat_components, str(overview["total_components"]))
            self._update_stat_card(self.stat_high_risk, str(overview["high_risk_components"]))
            self._update_stat_card(self.stat_pending_reviews, str(overview["pending_reviews"]))

            self.dashboard_chart1.plot_building_risk_pie(overview)
            self.dashboard_chart2.plot_risk_type_distribution(type_dist)

            buildings = overview.get("buildings", [])
            headers = ["建筑名称", "位置", "构件总数", "高风险", "中风险", "正常",
                       "平均含水率(%)", "最高含水率(%)"]
            self.dashboard_table.setColumnCount(len(headers))
            self.dashboard_table.setHorizontalHeaderLabels(headers)
            self.dashboard_table.setRowCount(len(buildings))

            for row, b in enumerate(buildings):
                self.dashboard_table.setItem(row, 0, QTableWidgetItem(b["name"]))
                self.dashboard_table.setItem(row, 1, QTableWidgetItem(b.get("location", "") or "-"))
                self.dashboard_table.setItem(row, 2, QTableWidgetItem(str(b["total_components"])))
                high_item = QTableWidgetItem(str(b["high_risk"]))
                high_item.setForeground(RISK_COLORS["高风险"])
                high_item.setFont(QFont("", 10, QFont.Bold))
                self.dashboard_table.setItem(row, 3, high_item)
                med_item = QTableWidgetItem(str(b["medium_risk"]))
                med_item.setForeground(RISK_COLORS["中风险"])
                self.dashboard_table.setItem(row, 4, med_item)
                norm_item = QTableWidgetItem(str(b["normal"]))
                norm_item.setForeground(RISK_COLORS["正常"])
                self.dashboard_table.setItem(row, 5, norm_item)
                self.dashboard_table.setItem(row, 6, QTableWidgetItem(str(b["avg_moisture"])))
                max_item = QTableWidgetItem(str(b["max_moisture"]))
                threshold = SettingsRepository.get_moisture_threshold()
                if b["max_moisture"] > threshold:
                    max_item.setForeground(RISK_COLORS["高风险"])
                self.dashboard_table.setItem(row, 7, max_item)

            self.dashboard_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.dashboard_table.horizontalHeader().setStretchLastSection(True)
        except Exception as e:
            self.dashboard_summary.setText(f"加载数据失败: {str(e)}")

    def _update_stat_card(self, card: QFrame, value: str):
        layout = card.layout()
        if layout and layout.count() >= 2:
            value_label = layout.itemAt(1).widget()
            if isinstance(value_label, QLabel):
                value_label.setText(value)

    def _refresh_comparison(self):
        if not self.selected_comparison_ids:
            self.lbl_comparison_count.setText("已选择 0 个构件（请点击「选择构件...」添加)")
            return

        group_map = {"按构件类型": "type", "按建筑": "building", "按位置": "position"}
        group_by = group_map.get(self.comparison_group_by.currentText(), "type")
        threshold = SettingsRepository.get_moisture_threshold()

        self.lbl_comparison_count.setText(f"已选择 {len(self.selected_comparison_ids)} 个构件")

        comparison = compare_components(self.selected_comparison_ids, group_by)
        self.comparison_chart.plot_comparison_bar(comparison, threshold)

        groups = comparison.get("groups", {})
        all_components = []
        for g_data in groups.values():
            all_components.extend(g_data["components"])

        headers = ["构件编号", "构件名称", "类型", "所属建筑/分组", "检测记录",
                   "平均含水率(%)", "最高含水率(%)", "风险等级"]
        self.comparison_table.setColumnCount(len(headers))
        self.comparison_table.setHorizontalHeaderLabels(headers)
        self.comparison_table.setRowCount(len(all_components))

        for row, comp in enumerate(all_components):
            self.comparison_table.setItem(row, 0, QTableWidgetItem(comp["code"]))
            self.comparison_table.setItem(row, 1, QTableWidgetItem(comp["name"]))
            self.comparison_table.setItem(row, 2, QTableWidgetItem(comp["component_type"]))
            if group_by == "building":
                group_value = comp.get("building_name", "") or "未知建筑"
            elif group_by == "type":
                group_value = comp.get("component_type", "") or "其他"
            else:
                group_value = comp.get("position", "") or "-"
            self.comparison_table.setItem(row, 3, QTableWidgetItem(group_value))
            self.comparison_table.setItem(row, 4, QTableWidgetItem(str(comp["record_count"])))
            avg_item = QTableWidgetItem(f"{comp['stats']['avg']}%")
            if comp["stats"]["avg"] > threshold:
                avg_item.setForeground(RISK_COLORS["高风险"])
            self.comparison_table.setItem(row, 5, avg_item)
            max_item = QTableWidgetItem(f"{comp['stats']['max']}%")
            if comp["stats"]["max"] > threshold:
                max_item.setForeground(RISK_COLORS["高风险"])
            self.comparison_table.setItem(row, 6, max_item)
            risk_item = QTableWidgetItem(comp["risk_level"])
            risk_color = RISK_COLORS.get(comp["risk_level"], QColor(0, 0, 0))
            risk_item.setForeground(risk_color)
            risk_item.setFont(QFont("", 10, QFont.Bold))
            self.comparison_table.setItem(row, 7, risk_item)

        self.comparison_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.comparison_table.horizontalHeader().setStretchLastSection(True)

    def _on_select_components_for_comparison(self):
        dlg = ComponentSelectionDialog(self)
        if dlg.exec():
            self.selected_comparison_ids = dlg.get_selected_ids()
            self._refresh_comparison()

    def _on_export_comparison_report(self):
        if not self.selected_comparison_ids:
            QMessageBox.warning(self, "提示", "请先选择要对比的构件")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出对比分析报告",
            f"对比分析报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            "HTML文件 (*.html)"
        )
        if not file_path:
            return
        try:
            group_map = {"按构件类型": "type", "按建筑": "building", "按位置": "position"}
            group_by = group_map.get(self.comparison_group_by.currentText(), "type")
            output = generate_comparison_report(
                self.selected_comparison_ids, output_path=file_path, group_by=group_by
            )
            ReportArchiveRepository.create(
                report_type="对比分析报告",
                file_name=os.path.basename(output),
                file_path=output,
                file_size=os.path.getsize(output),
                generated_by="用户导出",
                description=f"对比分析报告（{len(self.selected_comparison_ids)}个构件）"
            )
            QMessageBox.information(self, "导出成功", f"报告已成功导出到:\n{output}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"生成报告失败: {str(e)}")

    def _refresh_seasonal(self):
        threshold = SettingsRepository.get_moisture_threshold()

        if not self.current_component_id:
            self.seasonal_summary.setText("请在左侧选择构件查看季节性波动分析")
            return

        result = analyze_seasonal_variation(self.current_component_id)

        if not result.get("has_data"):
            self.seasonal_summary.setText("该构件暂无足够的历史数据进行季节性分析")
            return

        pattern = result.get("seasonal_pattern", "")
        high_seasons = result.get("high_risk_seasons", [])
        summary_text = pattern
        if high_seasons:
            summary_text += f"<br><span style='color:#e74c3c; font-weight:bold;'>⚠ 高风险季节: {', '.join(high_seasons)}</span>"
        self.seasonal_summary.setText(summary_text)

        self.seasonal_chart.plot_seasonal_chart(result, threshold)
        self.monthly_chart.plot_monthly_chart(result, threshold)

        seasons = ["春季", "夏季", "秋季", "冬季"]
        season_stats = result.get("seasons", {})
        headers = ["季节", "检测次数", "平均含水率(%)", "最高含水率(%)", "最低含水率(%)", "超标占比(%)"]
        self.seasonal_table.setColumnCount(len(headers))
        self.seasonal_table.setHorizontalHeaderLabels(headers)
        self.seasonal_table.setRowCount(len(seasons))

        for row, s in enumerate(seasons):
            data = season_stats.get(s, {})
            self.seasonal_table.setItem(row, 0, QTableWidgetItem(s))
            self.seasonal_table.setItem(row, 1, QTableWidgetItem(str(data.get("count", 0))))
            avg_item = QTableWidgetItem(str(data.get("avg", 0)))
            if data.get("avg", 0) > threshold:
                avg_item.setForeground(RISK_COLORS["高风险"])
            self.seasonal_table.setItem(row, 2, avg_item)
            max_item = QTableWidgetItem(str(data.get("max", 0)))
            if data.get("max", 0) > threshold:
                max_item.setForeground(RISK_COLORS["高风险"])
            self.seasonal_table.setItem(row, 3, max_item)
            self.seasonal_table.setItem(row, 4, QTableWidgetItem(str(data.get("min", 0))))
            ratio = data.get("high_ratio", 0)
            ratio_item = QTableWidgetItem(f"{ratio}%")
            if ratio > 30:
                ratio_item.setForeground(RISK_COLORS["高风险"])
            elif ratio > 10:
                ratio_item.setForeground(RISK_COLORS["中风险"])
            self.seasonal_table.setItem(row, 5, ratio_item)

        self.seasonal_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def _on_seasonal_multi_analysis(self):
        dlg = ComponentSelectionDialog(self)
        if dlg.exec():
            ids = dlg.get_selected_ids()
            if len(ids) < 2:
                QMessageBox.warning(self, "提示", "请至少选择2个构件")
                return
            threshold = SettingsRepository.get_moisture_threshold()
            result = analyze_seasonal_variation_multi(ids)
            self.seasonal_summary.setText(
                f"多构件季节性对比分析 — 共 {len(ids)} 个构件"
            )
            self.seasonal_chart.plot_seasonal_chart(result, threshold)
            self.monthly_chart.plot_monthly_chart(result, threshold)

            by_comp = result.get("by_component", {})
            seasons = ["春季", "夏季", "秋季", "冬季"]
            headers = ["构件"] + seasons
            self.seasonal_table.setColumnCount(len(headers))
            self.seasonal_table.setHorizontalHeaderLabels(headers)
            self.seasonal_table.setRowCount(len(by_comp))
            for row, (name, data) in enumerate(by_comp.items()):
                self.seasonal_table.setItem(row, 0, QTableWidgetItem(name))
                for col, s in enumerate(seasons, 1):
                    s_data = data.get(s, {})
                    avg = s_data.get("avg", 0)
                    item = QTableWidgetItem(f"{avg}%" if avg else "-")
                    if avg > threshold:
                        item.setForeground(RISK_COLORS["高风险"])
                    self.seasonal_table.setItem(row, col, item)
            self.seasonal_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def _refresh_prediction(self):
        threshold = SettingsRepository.get_moisture_threshold()

        if not self.current_component_id:
            self.prediction_summary.setText("请在左侧选择构件进行风险趋势预测")
            self.prediction_detail.setText("")
            return

        forecast_days = self.prediction_days.value()
        result = predict_risk_trend(self.current_component_id, forecast_days)

        if not result.get("has_data", False):
            self.prediction_summary.setText(result.get("recommendation", "数据不足，无法预测"))
            self.prediction_detail.setText("")
            return

        risk_level = result.get("risk_level_forecast", "正常")
        risk_color = RISK_COLORS.get(risk_level, QColor(0, 0, 0)).name()
        self.prediction_summary.setText(
            f"<b>预测风险等级:</b> <span style='color:{risk_color}; font-size:14px;'>{risk_level}</span>"
            f" &nbsp;&nbsp; <b>预测周期:</b> 未来 {forecast_days} 天"
            f" &nbsp;&nbsp; <b>预测均值:</b> {result.get('forecast_avg', 0)}%"
            f" &nbsp;&nbsp; <b>预测峰值:</b> {result.get('forecast_max', 0)}%"
        )

        self.prediction_chart.plot_trend_prediction(result, threshold)

        regression = result.get("regression", {})
        trend_desc = {
            "rising": "📈 含水率呈上升趋势",
            "falling": "📉 含水率呈下降趋势",
            "stable": "➡ 含水率保持稳定"
        }.get(result.get("trend_direction", "stable"), "趋势未知")

        detail_text = f"""
        <p><b>趋势分析:</b> {trend_desc}</p>
        <p><b>预测建议:</b> {result.get('recommendation', '')}</p>
        <p><b>回归参数:</b> 斜率={regression.get('slope', 0)}/天, 截距={regression.get('intercept', 0)}, 
        标准误差={regression.get('std_error', 0)}</p>
        """
        if result.get("will_exceed_threshold"):
            detail_text += f"""
            <p style='color:#e74c3c; font-weight:bold;'>
            ⚠ 预警：预测有 {result.get('exceed_probability', 0)}% 的概率会超过含水率阈值 {threshold}%
            </p>
            """
        self.prediction_detail.setText(detail_text)

    def _refresh_inspection_plans(self):
        status = self.plan_status_filter.currentData()
        plans = InspectionPlanRepository.get_all(status)

        headers = ["ID", "计划日期", "类型", "状态", "建筑", "构件", "操作人员", "提前提醒", "描述"]
        self.inspection_table.setColumnCount(len(headers))
        self.inspection_table.setHorizontalHeaderLabels(headers)
        self.inspection_table.setRowCount(len(plans))

        status_colors = {
            "待执行": QColor(52, 152, 219),
            "已提醒": QColor(241, 196, 15),
            "执行中": QColor(155, 89, 182),
            "已完成": QColor(46, 204, 113),
            "已取消": QColor(149, 165, 166)
        }

        for row, plan in enumerate(plans):
            self.inspection_table.setItem(row, 0, QTableWidgetItem(str(plan["id"])))
            self.inspection_table.setItem(row, 1, QTableWidgetItem(plan.get("plan_date", "")[:10]))
            self.inspection_table.setItem(row, 2, QTableWidgetItem(plan.get("plan_type", "")))
            status_item = QTableWidgetItem(plan.get("status", ""))
            color = status_colors.get(plan.get("status", ""), QColor(0, 0, 0))
            status_item.setForeground(color)
            status_item.setFont(QFont("", 10, QFont.Bold))
            self.inspection_table.setItem(row, 3, status_item)
            self.inspection_table.setItem(row, 4, QTableWidgetItem(plan.get("building_name", "") or "-"))
            comp_text = f"{plan.get('component_code', '') or ''} {plan.get('component_name', '') or ''}".strip()
            self.inspection_table.setItem(row, 5, QTableWidgetItem(comp_text or "-"))
            self.inspection_table.setItem(row, 6, QTableWidgetItem(plan.get("operator", "") or "-"))
            self.inspection_table.setItem(row, 7, QTableWidgetItem(f"{plan.get('reminder_days', 7)}天"))
            self.inspection_table.setItem(row, 8, QTableWidgetItem(plan.get("description", "") or "-"))

        self.inspection_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.inspection_table.horizontalHeader().setStretchLastSection(True)
        self._check_inspection_reminders()

    def _on_add_inspection_plan(self):
        dlg = InspectionPlanDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                InspectionPlanRepository.create(**data)
                QMessageBox.information(self, "成功", "巡检计划已创建")
                self._refresh_inspection_plans()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建失败: {str(e)}")

    def _on_edit_inspection_plan(self):
        rows = self.inspection_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "提示", "请选择要编辑的巡检计划")
            return
        plan_id = int(self.inspection_table.item(rows[0].row(), 0).text())
        plan = InspectionPlanRepository.get_by_id(plan_id)
        if not plan:
            return
        dlg = InspectionPlanDialog(self, plan=plan)
        if dlg.exec():
            data = dlg.get_data()
            try:
                InspectionPlanRepository.update(plan_id, **data)
                QMessageBox.information(self, "成功", "巡检计划已更新")
                self._refresh_inspection_plans()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"更新失败: {str(e)}")

    def _on_delete_inspection_plan(self):
        rows = self.inspection_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "提示", "请选择要删除的巡检计划")
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除选中的 {len(rows)} 个巡检计划吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        deleted = 0
        for row in rows:
            plan_id = int(self.inspection_table.item(row.row(), 0).text())
            if InspectionPlanRepository.delete(plan_id):
                deleted += 1
        QMessageBox.information(self, "成功", f"已删除 {deleted} 个巡检计划")
        self._refresh_inspection_plans()

    def _on_complete_inspection_plan(self):
        rows = self.inspection_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "提示", "请选择要标记完成的巡检计划")
            return
        updated = 0
        for row in rows:
            plan_id = int(self.inspection_table.item(row.row(), 0).text())
            if InspectionPlanRepository.update(
                plan_id, status="已完成",
                executed_at=datetime.now().isoformat()
            ):
                updated += 1
        QMessageBox.information(self, "成功", f"已标记 {updated} 个计划为完成状态")
        self._refresh_inspection_plans()

    def _refresh_anomaly_reviews(self):
        status = self.review_status_filter.currentData()
        reviews = AnomalyReviewRepository.get_all(status)

        headers = ["ID", "检测时间", "含水率(%)", "检测位置", "建筑", "构件", "复核状态", "复核人员", "是否误报"]
        self.anomaly_table.setColumnCount(len(headers))
        self.anomaly_table.setHorizontalHeaderLabels(headers)
        self.anomaly_table.setRowCount(len(reviews))

        review_colors = {
            "待复核": QColor(231, 76, 60),
            "复核通过": QColor(46, 204, 113),
            "确认为风险": QColor(230, 126, 34),
            "误报": QColor(149, 165, 166)
        }
        threshold = SettingsRepository.get_moisture_threshold()

        for row, r in enumerate(reviews):
            self.anomaly_table.setItem(row, 0, QTableWidgetItem(str(r["id"])))
            self.anomaly_table.setItem(row, 1, QTableWidgetItem(r.get("measure_time", "")[:19]))
            moisture = r.get("moisture", 0)
            moist_item = QTableWidgetItem(f"{moisture:.1f}")
            if moisture > threshold:
                moist_item.setForeground(RISK_COLORS["高风险"])
                moist_item.setFont(QFont("", 10, QFont.Bold))
            self.anomaly_table.setItem(row, 2, moist_item)
            self.anomaly_table.setItem(row, 3, QTableWidgetItem(r.get("measure_position", "") or "-"))
            self.anomaly_table.setItem(row, 4, QTableWidgetItem(r.get("building_name", "") or "-"))
            self.anomaly_table.setItem(row, 5, QTableWidgetItem(
                f"{r.get('component_code', '') or ''} {r.get('component_name', '') or ''}".strip() or "-"
            ))
            status_item = QTableWidgetItem(r.get("review_status", ""))
            color = review_colors.get(r.get("review_status", ""), QColor(0, 0, 0))
            status_item.setForeground(color)
            status_item.setFont(QFont("", 10, QFont.Bold))
            self.anomaly_table.setItem(row, 6, status_item)
            self.anomaly_table.setItem(row, 7, QTableWidgetItem(r.get("reviewer", "") or "-"))
            fa_text = "是" if r.get("is_false_alarm") else "否"
            self.anomaly_table.setItem(row, 8, QTableWidgetItem(fa_text))

        self.anomaly_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.anomaly_table.horizontalHeader().setStretchLastSection(True)

    def _on_add_anomaly_review(self):
        if not self.current_component_id:
            QMessageBox.warning(self, "提示", "请先在左侧选择一个构件")
            return
        records = RecordRepository.get_by_component(self.current_component_id)
        if not records:
            QMessageBox.warning(self, "提示", "该构件暂无检测记录")
            return

        from PySide6.QtWidgets import QInputDialog
        items = [f"{r['measure_time'][:19]} | {r['measure_position']} | {r['moisture']}%" for r in records]
        item, ok = QInputDialog.getItem(self, "选择记录", "选择要标记为异常的检测记录:", items, 0, False)
        if ok and item:
            idx = items.index(item)
            record = records[idx]
            existing = AnomalyReviewRepository.get_by_record(record["id"])
            if existing:
                QMessageBox.warning(self, "提示", "该记录已存在异常复核条目")
                return
            try:
                AnomalyReviewRepository.create(record["id"], self.current_component_id)
                QMessageBox.information(self, "成功", "已标记为异常，待复核")
                self._refresh_anomaly_reviews()
                self._refresh_dashboard()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"操作失败: {str(e)}")

    def _on_review_selected_anomaly(self):
        rows = self.anomaly_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "提示", "请选择要复核的异常记录")
            return
        review_id = int(self.anomaly_table.item(rows[0].row(), 0).text())
        review = AnomalyReviewRepository.get_by_id(review_id)
        if not review:
            return
        dlg = AnomalyReviewDialog(self, review=review)
        if dlg.exec():
            data = dlg.get_data()
            try:
                AnomalyReviewRepository.update(review_id, **data)
                QMessageBox.information(self, "成功", "复核信息已更新")
                self._refresh_anomaly_reviews()
                self._refresh_dashboard()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"更新失败: {str(e)}")

    def _on_delete_anomaly_review(self):
        rows = self.anomaly_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "提示", "请选择要删除的异常复核记录")
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除选中的 {len(rows)} 条复核记录吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        deleted = 0
        for row in rows:
            rid = int(self.anomaly_table.item(row.row(), 0).text())
            if AnomalyReviewRepository.delete(rid):
                deleted += 1
        QMessageBox.information(self, "成功", f"已删除 {deleted} 条复核记录")
        self._refresh_anomaly_reviews()
        self._refresh_dashboard()

    def _on_auto_scan_anomalies(self):
        components = ComponentRepository.get_all()
        threshold = SettingsRepository.get_moisture_threshold()
        scanned = 0
        added = 0

        reply = QMessageBox.question(
            self, "自动扫描异常",
            f"即将扫描全部 {len(components)} 个构件，自动识别含水率超过阈值 {threshold}% 的记录。\n是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        for comp in components:
            records = RecordRepository.get_by_component(comp["id"])
            for r in records:
                scanned += 1
                if r["moisture"] > threshold:
                    existing = AnomalyReviewRepository.get_by_record(r["id"])
                    if not existing:
                        try:
                            AnomalyReviewRepository.create(r["id"], comp["id"])
                            added += 1
                        except Exception:
                            pass

        QMessageBox.information(
            self, "扫描完成",
            f"共扫描 {scanned} 条检测记录\n"
            f"新增异常待复核: {added} 条\n"
            f"请在「异常复核」标签页查看并处理"
        )
        self._refresh_anomaly_reviews()
        self._refresh_dashboard()

    def _refresh_archives(self):
        report_type = self.archive_type_filter.currentData()
        archives = ReportArchiveRepository.get_all(report_type)

        headers = ["ID", "报告类型", "文件名", "建筑", "构件", "文件大小(KB)", "创建时间", "描述"]
        self.archive_table.setColumnCount(len(headers))
        self.archive_table.setHorizontalHeaderLabels(headers)
        self.archive_table.setRowCount(len(archives))

        for row, a in enumerate(archives):
            self.archive_table.setItem(row, 0, QTableWidgetItem(str(a["id"])))
            self.archive_table.setItem(row, 1, QTableWidgetItem(a.get("report_type", "")))
            self.archive_table.setItem(row, 2, QTableWidgetItem(a.get("file_name", "")))
            self.archive_table.setItem(row, 3, QTableWidgetItem(a.get("building_name", "") or "-"))
            self.archive_table.setItem(row, 4, QTableWidgetItem(
                f"{a.get('component_code', '') or ''} {a.get('component_name', '') or ''}".strip() or "-"
            ))
            size_kb = round((a.get("file_size") or 0) / 1024, 1)
            self.archive_table.setItem(row, 5, QTableWidgetItem(f"{size_kb}"))
            self.archive_table.setItem(row, 6, QTableWidgetItem(a.get("created_at", "")[:19]))
            self.archive_table.setItem(row, 7, QTableWidgetItem(a.get("description", "") or "-"))

        self.archive_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.archive_table.horizontalHeader().setStretchLastSection(True)

    def _on_open_archive_file(self):
        rows = self.archive_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "提示", "请选择要打开的归档记录")
            return
        archive_id = int(self.archive_table.item(rows[0].row(), 0).text())
        archive = ReportArchiveRepository.get_by_id(archive_id)
        if not archive:
            return
        file_path = archive.get("file_path", "")
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "提示", "归档文件不存在或已被移动")
            return

        import sys, subprocess
        try:
            if sys.platform.startswith("darwin"):
                subprocess.run(["open", file_path])
            elif os.name == "nt":
                os.startfile(file_path)
            else:
                subprocess.run(["xdg-open", file_path])
        except Exception as e:
            QMessageBox.information(self, "文件位置", f"文件路径:\n{file_path}")

    def _on_delete_archive(self):
        rows = self.archive_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "提示", "请选择要删除的归档记录")
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除选中的 {len(rows)} 条归档记录吗？\n（注意：仅删除数据库记录，不会删除磁盘文件）",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        deleted = 0
        for row in rows:
            aid = int(self.archive_table.item(row.row(), 0).text())
            if ReportArchiveRepository.delete(aid):
                deleted += 1
        QMessageBox.information(self, "成功", f"已删除 {deleted} 条归档记录")
        self._refresh_archives()

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
                QMessageBox.information(self, "导出完成", msg)
                self._refresh_archives()
                self._refresh_dashboard()
            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"批量导出失败: {str(e)}")

    def _refresh_defects(self):
        status_filter = self.defect_status_filter.currentData()
        type_filter = self.defect_type_filter.currentData()
        building_id = getattr(self, "current_building_id", None)
        component_id = getattr(self, "current_component_id", None)

        defects = DefectRepository.get_all(
            building_id=building_id, component_id=component_id,
            status=status_filter, defect_type=type_filter
        )

        headers = ["ID", "建筑", "构件", "病害类型", "严重程度", "状态", "发现日期", "描述"]
        self.defect_table.setColumnCount(len(headers))
        self.defect_table.setHorizontalHeaderLabels(headers)
        self.defect_table.setRowCount(len(defects))

        sev_colors = {
            "轻微": QColor(39, 174, 96), "一般": QColor(243, 156, 18),
            "严重": QColor(230, 126, 34), "危急": QColor(231, 76, 60)
        }
        status_colors = {
            "待处置": QColor(231, 76, 60), "处置中": QColor(243, 156, 18),
            "待验收": QColor(52, 152, 219), "已验收": QColor(155, 89, 182),
            "已完成": QColor(39, 174, 96), "已关闭": QColor(149, 165, 166)
        }

        for row, d in enumerate(defects):
            items = [
                QTableWidgetItem(str(d["id"])),
                QTableWidgetItem(d.get("building_name", "") or "-"),
                QTableWidgetItem(
                    f"{d.get('component_code', '') or ''} {d.get('component_name', '') or ''}".strip() or "-"
                ),
                QTableWidgetItem(d.get("defect_type", "")),
                QTableWidgetItem(d.get("severity", "")),
                QTableWidgetItem(d.get("status", "")),
                QTableWidgetItem((d.get("discovery_date", "") or "")[:10]),
                QTableWidgetItem((d.get("description", "") or "")[:60]),
            ]
            sev_color = sev_colors.get(d.get("severity", ""))
            status_color = status_colors.get(d.get("status", ""))
            if sev_color:
                items[4].setForeground(QBrush(sev_color))
                items[4].setFont(self._bold_font())
            if status_color:
                items[5].setForeground(QBrush(status_color))
                items[5].setFont(self._bold_font())
            for col, it in enumerate(items):
                self.defect_table.setItem(row, col, it)

        self.defect_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.defect_table.horizontalHeader().setStretchLastSection(True)

        self._refresh_defect_stats()
        self._check_defect_overdue()
        self._refresh_defect_charts()

    def _refresh_defect_stats(self):
        building_id = getattr(self, "current_building_id", None)
        stats = DefectRepository.get_statistics(building_id)
        total_label = self.defect_stat_total.findChild(QLabel, "value")
        pending_label = self.defect_stat_pending.findChild(QLabel, "value")
        processing_label = self.defect_stat_processing.findChild(QLabel, "value")
        completed_label = self.defect_stat_completed.findChild(QLabel, "value")
        if total_label:
            total_label.setText(str(stats.get("total", 0)))
        if pending_label:
            pending_label.setText(str(stats.get("待处置", 0)))
        if processing_label:
            processing_label.setText(str(stats.get("处置中", 0)))
        if completed_label:
            completed_label.setText(str(stats.get("已完成", 0)))

    def _check_defect_overdue(self):
        reminders = DefectRepository.get_overdue_reminders()
        if reminders:
            msg = f"⚠ 有 {len(reminders)} 个维修工单已超期，请及时处理！"
            for r in reminders[:3]:
                msg += f"\n  • {r.get('order_no', '')} - {r.get('title', '')} (截止: {str(r.get('deadline', ''))[:10]})"
            if len(reminders) > 3:
                msg += f"\n  ... 还有 {len(reminders) - 3} 个超期工单"
            self.defect_reminder_banner.setText(msg)
            self.defect_reminder_banner.show()
        else:
            self.defect_reminder_banner.hide()

    def _refresh_defect_charts(self):
        building_id = getattr(self, "current_building_id", None)
        stats = DefectRepository.get_statistics(building_id)

        status_data = {}
        for s in DEFECT_STATUSES:
            if stats.get(s, 0) > 0:
                status_data[s] = stats.get(s, 0)
        self.defect_status_chart.plot_defect_status_pie(status_data)

        type_data = stats.get("by_type", {})
        self.defect_type_chart.plot_defect_type_distribution(type_data)

        evals = EffectivenessEvaluationRepository.get_all(building_id=building_id)
        self.moisture_compare_chart.plot_moisture_comparison(
            evals, SettingsRepository.get_moisture_threshold()
        )

    def _refresh_workorders(self):
        status_filter = self.wo_status_filter.currentData()
        building_id = getattr(self, "current_building_id", None)

        workorders = WorkOrderRepository.get_all(
            building_id=building_id, status=status_filter
        )

        headers = ["ID", "工单编号", "标题", "病害类型", "优先级", "状态", "负责人", "派工日期", "截止日期"]
        self.workorder_table.setColumnCount(len(headers))
        self.workorder_table.setHorizontalHeaderLabels(headers)
        self.workorder_table.setRowCount(len(workorders))

        prio_colors = {
            "低": QColor(149, 165, 166), "中": QColor(52, 152, 219),
            "高": QColor(230, 126, 34), "紧急": QColor(231, 76, 60)
        }
        wo_status_colors = {
            "待处理": QColor(231, 76, 60), "处理中": QColor(243, 156, 18),
            "待验收": QColor(52, 152, 219), "已完成": QColor(39, 174, 96),
            "已取消": QColor(149, 165, 166)
        }

        for row, w in enumerate(workorders):
            items = [
                QTableWidgetItem(str(w["id"])),
                QTableWidgetItem(w.get("order_no", "")),
                QTableWidgetItem(w.get("title", "")),
                QTableWidgetItem(w.get("defect_type", "") or ""),
                QTableWidgetItem(w.get("priority", "")),
                QTableWidgetItem(w.get("status", "")),
                QTableWidgetItem(w.get("assignee", "") or "-"),
                QTableWidgetItem((w.get("assign_date", "") or "")[:10]),
                QTableWidgetItem((w.get("deadline", "") or "")[:10]),
            ]
            p_color = prio_colors.get(w.get("priority", ""))
            s_color = wo_status_colors.get(w.get("status", ""))
            if p_color:
                items[4].setForeground(QBrush(p_color))
                items[4].setFont(self._bold_font())
            if s_color:
                items[5].setForeground(QBrush(s_color))
                items[5].setFont(self._bold_font())
            for col, it in enumerate(items):
                self.workorder_table.setItem(row, col, it)

        self.workorder_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.workorder_table.horizontalHeader().setStretchLastSection(True)

    def _get_selected_defect_id(self) -> Optional[int]:
        rows = self.defect_table.selectionModel().selectedRows()
        if not rows:
            return None
        return int(self.defect_table.item(rows[0].row(), 0).text())

    def _get_selected_workorder_id(self) -> Optional[int]:
        rows = self.workorder_table.selectionModel().selectedRows()
        if not rows:
            return None
        return int(self.workorder_table.item(rows[0].row(), 0).text())

    def _on_add_defect(self):
        dlg = DefectDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                DefectRepository.create(**data)
                QMessageBox.information(self, "成功", "病害登记成功")
                self._refresh_defects()
                self._refresh_dashboard()
            except Exception as e:
                QMessageBox.critical(self, "失败", f"登记失败: {str(e)}")

    def _on_edit_defect(self):
        did = self._get_selected_defect_id()
        if not did:
            QMessageBox.warning(self, "提示", "请先选择要编辑的病害")
            return
        defect = DefectRepository.get_by_id(did)
        if not defect:
            return
        dlg = DefectDialog(self, defect=defect)
        if dlg.exec():
            data = dlg.get_data()
            try:
                DefectRepository.update(did, **data)
                QMessageBox.information(self, "成功", "病害信息已更新")
                self._refresh_defects()
                self._refresh_dashboard()
            except Exception as e:
                QMessageBox.critical(self, "失败", f"更新失败: {str(e)}")

    def _on_delete_defect(self):
        did = self._get_selected_defect_id()
        if not did:
            QMessageBox.warning(self, "提示", "请先选择要删除的病害")
            return
        reply = QMessageBox.question(
            self, "确认删除", "确定要删除该病害及其关联的工单、验收、评估记录吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        if DefectRepository.delete(did):
            QMessageBox.information(self, "成功", "删除成功")
            self._refresh_defects()
            self._refresh_workorders()
            self._refresh_dashboard()
        else:
            QMessageBox.warning(self, "失败", "删除失败")

    def _on_view_defect_detail(self):
        did = self._get_selected_defect_id()
        if not did:
            QMessageBox.warning(self, "提示", "请先选择病害")
            return
        dlg = DefectDetailDialog(self, defect_id=did)
        dlg.exec()

    def _on_create_workorder(self):
        did = self._get_selected_defect_id()
        if not did:
            QMessageBox.warning(self, "提示", "请先选择要创建工单的病害")
            return
        if DefectRepository.has_open_work_order(did):
            QMessageBox.warning(self, "提示", "该病害已有未关闭的维修工单，请先处理现有工单")
            return
        dlg = WorkOrderDialog(self, default_defect_id=did)
        if dlg.exec():
            data = dlg.get_data()
            try:
                WorkOrderRepository.create(**data)
                QMessageBox.information(self, "成功", "维修工单创建成功，病害状态已更新为「处置中」")
                self._refresh_defects()
                self._refresh_workorders()
                self._refresh_dashboard()
            except Exception as e:
                QMessageBox.critical(self, "失败", f"创建失败: {str(e)}")

    def _on_edit_workorder(self):
        wid = self._get_selected_workorder_id()
        if not wid:
            QMessageBox.warning(self, "提示", "请先选择要编辑的工单")
            return
        wo = WorkOrderRepository.get_by_id(wid)
        if not wo:
            return
        dlg = WorkOrderDialog(self, work_order=wo)
        if dlg.exec():
            data = dlg.get_data()
            try:
                WorkOrderRepository.update(wid, **data)
                QMessageBox.information(self, "成功", "工单已更新")
                self._refresh_workorders()
                self._refresh_defects()
            except Exception as e:
                QMessageBox.critical(self, "失败", f"更新失败: {str(e)}")

    def _on_delete_workorder(self):
        wid = self._get_selected_workorder_id()
        if not wid:
            QMessageBox.warning(self, "提示", "请先选择要删除的工单")
            return
        reply = QMessageBox.question(self, "确认删除", "确定要删除该维修工单吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        if WorkOrderRepository.delete(wid):
            QMessageBox.information(self, "成功", "删除成功")
            self._refresh_workorders()
            self._refresh_defects()
        else:
            QMessageBox.warning(self, "失败", "删除失败")

    def _on_change_workorder_status(self, new_status: str):
        wid = self._get_selected_workorder_id()
        if not wid:
            QMessageBox.warning(self, "提示", "请先选择工单")
            return
        try:
            WorkOrderRepository.update_status(wid, new_status, operator="系统用户",
                                              change_note=f"状态变更为「{new_status}」")
            QMessageBox.information(self, "成功", f"工单状态已更新为「{new_status}」")
            self._refresh_workorders()
            self._refresh_defects()
        except Exception as e:
            QMessageBox.critical(self, "失败", f"操作失败: {str(e)}")

    def _on_add_tracking(self):
        wid = self._get_selected_workorder_id()
        if not wid:
            QMessageBox.warning(self, "提示", "请先选择要记录整改的工单")
            return
        dlg = RectificationTrackDialog(self, work_order_id=wid)
        if dlg.exec():
            data = dlg.get_data()
            try:
                RectificationTrackingRepository.create(**data)
                QMessageBox.information(self, "成功", "整改记录已保存")
                self._refresh_workorders()
            except Exception as e:
                QMessageBox.critical(self, "失败", f"保存失败: {str(e)}")

    def _on_do_acceptance(self):
        wid = self._get_selected_workorder_id()
        if not wid:
            QMessageBox.warning(self, "提示", "请先选择要验收的工单")
            return
        wo = WorkOrderRepository.get_by_id(wid)
        if not wo:
            return
        if AcceptanceRecordRepository.get_by_work_order(wid):
            reply = QMessageBox.question(
                self, "已存在验收记录", "该工单已有验收记录，是否覆盖？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        dlg = AcceptanceDialog(self, work_order_id=wid, defect_id=wo.get("defect_id"))
        if dlg.exec():
            data = dlg.get_data()
            try:
                AcceptanceRecordRepository.create(**data)
                QMessageBox.information(self, "成功", "验收记录已保存，相关状态已自动更新")
                self._refresh_workorders()
                self._refresh_defects()
                self._refresh_dashboard()
            except Exception as e:
                QMessageBox.critical(self, "失败", f"保存失败: {str(e)}")

    def _on_do_evaluation(self):
        wid = self._get_selected_workorder_id()
        if not wid:
            QMessageBox.warning(self, "提示", "请先选择要评估的工单")
            return
        wo = WorkOrderRepository.get_by_id(wid)
        if not wo:
            return
        defect_id = wo.get("defect_id")
        if EffectivenessEvaluationRepository.get_by_defect(defect_id):
            reply = QMessageBox.question(
                self, "已存在评估记录", "该病害已有效果评估记录，是否覆盖？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        dlg = EffectivenessEvalDialog(self, defect_id=defect_id)
        if dlg.exec():
            data = dlg.get_data()
            try:
                EffectivenessEvaluationRepository.create(**data)
                QMessageBox.information(self, "成功", "效果评估已保存，病害状态已更新为「已完成」")
                self._refresh_defects()
                self._refresh_workorders()
                self._refresh_dashboard()
                self._refresh_defect_charts()
            except Exception as e:
                QMessageBox.critical(self, "失败", f"保存失败: {str(e)}")

    def _on_export_defect_report(self):
        did = self._get_selected_defect_id()
        if not did:
            QMessageBox.warning(self, "提示", "请先选择要导出报告的病害")
            return
        try:
            output_path = generate_defect_disposal_report(did)
            defect = DefectRepository.get_by_id(did)
            try:
                ReportArchiveRepository.create(
                    report_type="病害处置报告",
                    file_name=os.path.basename(output_path),
                    file_path=output_path,
                    file_size=os.path.getsize(output_path),
                    building_id=defect.get("building_id"),
                    component_id=defect.get("component_id"),
                    description=f"{defect.get('defect_type', '')} - {defect.get('severity', '')}处置报告"
                )
            except Exception:
                pass
            QMessageBox.information(self, "成功", f"报告已导出到:\n{output_path}")
            self._refresh_archives()
        except Exception as e:
            QMessageBox.critical(self, "失败", f"导出失败: {str(e)}")

    def _check_rectification_deadlines(self):
        try:
            warnings = check_rectification_deadlines()
            overdue = warnings.get("overdue", [])
            urgent = warnings.get("urgent", [])

            if self.deadline_alert_banner:
                if overdue or urgent:
                    parts = []
                    if overdue:
                        parts.append(f"🔴 {len(overdue)} 个工单已逾期")
                    if urgent:
                        parts.append(f"🟠 {len(urgent)} 个工单即将到期(≤3天)")
                    self.deadline_alert_banner.setText(" | ".join(parts))
                    self.deadline_alert_banner.show()
                else:
                    self.deadline_alert_banner.hide()
        except Exception:
            if self.deadline_alert_banner:
                self.deadline_alert_banner.hide()

    def _refresh_priority_list(self):
        try:
            all_defects = DefectRepository.get_all()
            building_id = self.priority_building_filter.currentData()
            if building_id:
                all_defects = [d for d in all_defects if d.get("building_id") == building_id]

            sorted_defects = sort_defects_by_priority(all_defects)

            counts = {"紧急": 0, "高": 0, "中": 0, "低": 0}
            for d in sorted_defects:
                score, level, _ = calculate_defect_priority(d)
                if level in counts:
                    counts[level] += 1

            self._update_stat_card(self.prio_stat_urgent, str(counts["紧急"]))
            self._update_stat_card(self.prio_stat_high, str(counts["高"]))
            self._update_stat_card(self.prio_stat_medium, str(counts["中"]))
            self._update_stat_card(self.prio_stat_low, str(counts["低"]))

            warnings = check_rectification_deadlines()
            self._update_stat_card(self.stat_overdue, str(len(warnings.get("overdue", []))))

            headers = ["优先级", "评分", "病害类型", "严重程度", "建筑", "构件",
                       "含水率(%)", "发现日期", "截止日期", "状态", "影响因素"]
            self.priority_table.setColumnCount(len(headers))
            self.priority_table.setHorizontalHeaderLabels(headers)
            self.priority_table.setRowCount(len(sorted_defects))

            for row, defect in enumerate(sorted_defects):
                score, level, factors = calculate_defect_priority(defect)
                bldg = BuildingRepository.get_by_id(defect.get("building_id")) or {}
                comp = ComponentRepository.get_by_id(defect.get("component_id")) or {}

                values = [
                    level, str(score),
                    defect.get("defect_type", ""),
                    defect.get("severity", ""),
                    bldg.get("name", ""),
                    comp.get("name", ""),
                    str(defect.get("moisture_level", "")),
                    defect.get("discovery_date", "")[:10] if defect.get("discovery_date") else "",
                    defect.get("deadline_date", "")[:10] if defect.get("deadline_date") else "",
                    defect.get("status", ""),
                    ", ".join(factors[:3])
                ]
                for col, val in enumerate(values):
                    item = QTableWidgetItem(str(val))
                    if col == 0:
                        color_map = {"紧急": "#e74c3c", "高": "#e67e22", "中": "#3498db", "低": "#27ae60"}
                        item.setForeground(QBrush(QColor(color_map.get(level, "#333"))))
                        f = item.font()
                        f.setBold(True)
                        item.setFont(f)
                    self.priority_table.setItem(row, col, item)

            self.priority_table.resizeColumnsToContents()

            self.priority_chart.plot_priority_distribution(counts)
            deadline_data = {
                "已逾期": len(warnings.get("overdue", [])),
                "即将到期(≤3天)": len(warnings.get("urgent", [])),
                "提醒期(4-7天)": len(warnings.get("warning", [])),
                "正常": max(0, len(all_defects) - len(warnings.get("overdue", []))
                           - len(warnings.get("urgent", [])) - len(warnings.get("warning", [])))
            }
            self.deadline_chart.plot_priority_distribution(deadline_data, "整改时限状态分布")
        except Exception as e:
            print(f"刷新优先级列表出错: {e}")

    def _on_auto_calculate_priority(self):
        try:
            all_defects = DefectRepository.get_all()
            updated = 0
            for defect in all_defects:
                score, level, _ = calculate_defect_priority(defect)
                DefectRepository.update(defect["id"], priority_score=score, priority_level=level)
                updated += 1
            QMessageBox.information(self, "成功", f"已自动计算 {updated} 条病害的优先级")
            self._refresh_priority_list()
        except Exception as e:
            QMessageBox.critical(self, "失败", f"计算失败: {str(e)}")

    def _refresh_resources(self):
        try:
            res_type = self.res_type_filter.currentData()
            building_id = self.res_building_filter.currentData()

            resources = MaintenanceResourceRepository.get_all()
            if res_type:
                resources = [r for r in resources if r.get("resource_type") == res_type]
            if building_id:
                resources = [r for r in resources if r.get("building_id") == building_id]

            total_cost = sum((r.get("quantity", 0) or 0) * (r.get("unit_price", 0) or 0) for r in resources)
            mat_count = len([r for r in resources if r.get("resource_type") == "材料"])
            labor_count = len([r for r in resources if r.get("resource_type") == "人工"])

            self._update_stat_card(self.res_stat_total, str(len(resources)))
            self._update_stat_card(self.res_stat_cost, f"{total_cost:,.0f}")
            self._update_stat_card(self.res_stat_material, str(mat_count))
            self._update_stat_card(self.res_stat_labor, str(labor_count))

            headers = ["ID", "类型", "名称", "数量", "单位", "单价(¥)", "总价(¥)",
                       "关联建筑", "关联病害", "使用日期", "备注"]
            self.resource_table.setColumnCount(len(headers))
            self.resource_table.setHorizontalHeaderLabels(headers)
            self.resource_table.setRowCount(len(resources))

            for row, r in enumerate(resources):
                bldg = BuildingRepository.get_by_id(r.get("building_id")) or {}
                total_price = (r.get("quantity", 0) or 0) * (r.get("unit_price", 0) or 0)
                values = [
                    r.get("id", ""),
                    r.get("resource_type", ""),
                    r.get("resource_name", ""),
                    r.get("quantity", ""),
                    r.get("unit", ""),
                    r.get("unit_price", ""),
                    f"{total_price:.2f}",
                    bldg.get("name", ""),
                    r.get("defect_id", "") or "-",
                    r.get("usage_date", "")[:10] if r.get("usage_date") else "",
                    r.get("notes", "") or ""
                ]
                for col, val in enumerate(values):
                    self.resource_table.setItem(row, col, QTableWidgetItem(str(val)))

            self.resource_table.resizeColumnsToContents()

            stats = MaintenanceResourceRepository.get_statistics()
            self.resource_cost_chart.plot_resource_cost_pie(stats.get("by_type", {}))

            building_stats = stats.get("by_building", {})
            building_names = []
            costs = []
            usages = []
            for bid, s in building_stats.items():
                b = BuildingRepository.get_by_id(bid)
                if b:
                    building_names.append(b.get("name", str(bid)))
                    costs.append(s.get("total_cost", 0))
                    usages.append(s.get("total_count", 0))
            self.resource_building_chart.plot_resource_by_building_bar(building_names, costs, usages)
        except Exception as e:
            print(f"刷新维修资源出错: {e}")

    def _on_add_resource(self):
        dlg = ResourceDialog(self)
        if dlg.exec():
            try:
                data = dlg.get_data()
                MaintenanceResourceRepository.create(**data)
                self._refresh_resources()
            except Exception as e:
                QMessageBox.critical(self, "失败", f"保存失败: {str(e)}")

    def _on_edit_resource(self):
        rid = self._get_selected_id(self.resource_table)
        if not rid:
            return
        res = MaintenanceResourceRepository.get_by_id(rid)
        if not res:
            return
        dlg = ResourceDialog(self, resource=res)
        if dlg.exec():
            try:
                data = dlg.get_data()
                MaintenanceResourceRepository.update(rid, **data)
                self._refresh_resources()
            except Exception as e:
                QMessageBox.critical(self, "失败", f"保存失败: {str(e)}")

    def _on_delete_resource(self):
        rid = self._get_selected_id(self.resource_table)
        if not rid:
            return
        reply = QMessageBox.question(self, "确认删除", "确定要删除这条资源记录吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                MaintenanceResourceRepository.delete(rid)
                self._refresh_resources()
            except Exception as e:
                QMessageBox.critical(self, "失败", f"删除失败: {str(e)}")

    def _refresh_recurrence(self):
        try:
            recurrences = DefectRecurrenceRepository.get_all()
            avg_days_list = [r.get("interval_days", 0) or 0 for r in recurrences if r.get("interval_days")]
            avg_days = sum(avg_days_list) / len(avg_days_list) if avg_days_list else 0

            same_loc = len([r for r in recurrences if r.get("recurrence_type") == "同位置复发"])
            same_type = len([r for r in recurrences if r.get("recurrence_type") == "同类病害"])

            self._update_stat_card(self.recur_stat_total, str(len(recurrences)))
            self._update_stat_card(self.recur_stat_avg_days, f"{avg_days:.0f}")
            self._update_stat_card(self.recur_stat_same_loc, str(same_loc))
            self._update_stat_card(self.recur_stat_same_type, str(same_type))

            by_type = {}
            for r in recurrences:
                t = r.get("recurrence_type", "其他")
                by_type[t] = by_type.get(t, 0) + 1
            self.recurrence_chart.plot_recurrence_analysis(by_type)

            headers = ["ID", "原发病害", "复发病害", "复发类型", "间隔天数", "根因分析", "记录时间"]
            self.recurrence_known_table.setColumnCount(len(headers))
            self.recurrence_known_table.setHorizontalHeaderLabels(headers)
            self.recurrence_known_table.setRowCount(len(recurrences))
            for row, r in enumerate(recurrences):
                orig = DefectRepository.get_by_id(r.get("original_defect_id")) or {}
                recur = DefectRepository.get_by_id(r.get("recurrent_defect_id")) or {}
                values = [
                    r.get("id", ""),
                    f"{orig.get('defect_type', '')}@{orig.get('discovery_date', '')[:10]}",
                    f"{recur.get('defect_type', '')}@{recur.get('discovery_date', '')[:10]}",
                    r.get("recurrence_type", ""),
                    r.get("interval_days", ""),
                    (r.get("root_cause", "") or "")[:20],
                    r.get("recorded_at", "")[:10] if r.get("recorded_at") else ""
                ]
                for col, val in enumerate(values):
                    self.recurrence_known_table.setItem(row, col, QTableWidgetItem(str(val)))
            self.recurrence_known_table.resizeColumnsToContents()
        except Exception as e:
            print(f"刷新复发分析出错: {e}")

    def _on_detect_recurrence(self):
        try:
            potentials = detect_defect_recurrences()
            if not potentials:
                QMessageBox.information(self, "检测结果", "未检测到潜在的病害复发关联")
                return

            headers = ["相似度", "原发病害", "复发病害", "位置匹配", "类型匹配", "描述匹配"]
            self.recurrence_detect_table.setColumnCount(len(headers))
            self.recurrence_detect_table.setHorizontalHeaderLabels(headers)
            self.recurrence_detect_table.setRowCount(len(potentials))

            self._detected_recurrences = potentials
            for row, p in enumerate(potentials):
                orig = p.get("original", {})
                recur = p.get("recurrent", {})
                values = [
                    f"{p.get('similarity', 0):.0%}",
                    f"{orig.get('defect_type', '')}@{orig.get('location', '')}",
                    f"{recur.get('defect_type', '')}@{recur.get('location', '')}",
                    "✓" if p.get("location_match") else "✗",
                    "✓" if p.get("type_match") else "✗",
                    f"{p.get('description_similarity', 0):.0%}"
                ]
                for col, val in enumerate(values):
                    self.recurrence_detect_table.setItem(row, col, QTableWidgetItem(str(val)))
            self.recurrence_detect_table.resizeColumnsToContents()
            QMessageBox.information(self, "检测完成", f"检测到 {len(potentials)} 条潜在复发关联，请确认")
        except Exception as e:
            QMessageBox.critical(self, "失败", f"检测失败: {str(e)}")

    def _on_mark_recurrence(self):
        row = self.recurrence_detect_table.currentRow()
        if row < 0 or not hasattr(self, "_detected_recurrences"):
            QMessageBox.warning(self, "提示", "请先在检测结果中选择一条记录")
            return
        p = self._detected_recurrences[row]
        dlg = DefectRecurrenceDialog(self, original=p["original"], recurrent=p["recurrent"])
        if dlg.exec():
            try:
                data = dlg.get_data()
                DefectRecurrenceRepository.create(
                    original_defect_id=p["original"]["id"],
                    recurrent_defect_id=p["recurrent"]["id"],
                    recurrence_type=data.get("recurrence_type", "同位置复发"),
                    interval_days=data.get("interval_days"),
                    root_cause=data.get("root_cause")
                )
                self._refresh_recurrence()
                QMessageBox.information(self, "成功", "已标记复发关联")
            except Exception as e:
                QMessageBox.critical(self, "失败", f"保存失败: {str(e)}")

    def _refresh_effectiveness(self):
        try:
            building_id = self.eff_building_filter.currentData()
            data = calculate_effectiveness_comparison(building_id)

            total_evaluated = data.get("total_evaluated", 0)
            avg_improvement = data.get("avg_improvement_rate", 0)
            effect_dist = data.get("effect_distribution", {})
            top_5 = data.get("top_5", [])
            bottom_5 = data.get("bottom_5", [])

            self._update_stat_card(self.eff_stat_evaluated, str(total_evaluated))
            self._update_stat_card(self.eff_stat_avg_imp, f"{avg_improvement:.1f}")
            self._update_stat_card(self.eff_stat_excellent, str(effect_dist.get("优秀", 0)))
            self._update_stat_card(self.eff_stat_poor, str(effect_dist.get("较差", 0) + effect_dist.get("差", 0)))

            self.effect_dist_chart.plot_effect_distribution_pie(effect_dist)

            by_type = data.get("by_type", {})
            self.effect_type_chart.plot_effectiveness_comparison(
                list(by_type.keys()),
                [v.get("avg_improvement_rate", 0) for v in by_type.values()]
            )

            top_headers = ["病害类型", "建筑", "改善率(%)", "维修前(%)", "维修后(%)", "效果等级"]
            self._populate_effect_table(self.effect_top_table, top_headers, top_5)

            low_headers = ["病害类型", "建筑", "改善率(%)", "维修前(%)", "维修后(%)", "效果等级"]
            self._populate_effect_table(self.effect_low_table, low_headers, bottom_5)
        except Exception as e:
            print(f"刷新效果对比出错: {e}")

    def _populate_effect_table(self, table, headers, rows):
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(rows))
        for row_idx, d in enumerate(rows):
            bldg = BuildingRepository.get_by_id(d.get("building_id")) or {}
            values = [
                d.get("defect_type", ""),
                bldg.get("name", ""),
                f"{d.get('improvement_rate', 0):.1f}",
                d.get("moisture_before", ""),
                d.get("moisture_after", ""),
                d.get("effect_level", "")
            ]
            for col, val in enumerate(values):
                table.setItem(row_idx, col, QTableWidgetItem(str(val)))
        table.resizeColumnsToContents()

    def _refresh_performance(self):
        try:
            building_id = self.perf_building_filter.currentData()
            data = calculate_closed_loop_performance(building_id)

            self._update_stat_card(self.perf_stat_total, str(data.get("total", 0)))
            self._update_stat_card(self.perf_stat_closed, str(data.get("closed", 0)))
            self._update_stat_card(self.perf_stat_rate, f"{data.get('closed_loop_rate', 0):.1f}")
            self._update_stat_card(self.perf_stat_avg_days, f"{data.get('avg_cycle_days', 0):.1f}")
            self._update_stat_card(self.perf_stat_rework, str(data.get("rework_count", 0)))

            self._refresh_performance_chart("building")

            by_building = data.get("by_building", {})
            self._populate_perf_table(self.perf_building_table,
                                      ["建筑", "总数", "闭环数", "闭环率(%)", "平均周期(天)", "返工数"],
                                      list(by_building.items()), key="building")

            by_component = data.get("by_component", {})
            self._populate_perf_table(self.perf_component_table,
                                      ["构件", "总数", "闭环数", "闭环率(%)", "平均周期(天)", "返工数"],
                                      list(by_component.items()), key="component")

            by_type = data.get("by_type", {})
            self._populate_perf_table(self.perf_type_table,
                                      ["病害类型", "总数", "闭环数", "闭环率(%)", "平均周期(天)", "返工数"],
                                      list(by_type.items()), key="type")
        except Exception as e:
            print(f"刷新闭环绩效出错: {e}")

    def _refresh_performance_chart(self, group_by="building"):
        try:
            building_id = self.perf_building_filter.currentData()
            data = calculate_closed_loop_performance(building_id)

            if group_by == "building":
                group_data = data.get("by_building", {})
            elif group_by == "component":
                group_data = data.get("by_component", {})
            else:
                group_data = data.get("by_type", {})

            names = []
            rates = []
            cycles = []
            for key, stats in group_data.items():
                if group_by == "building":
                    b = BuildingRepository.get_by_id(key)
                    names.append(b.get("name", str(key)) if b else str(key))
                elif group_by == "component":
                    c = ComponentRepository.get_by_id(key)
                    names.append(c.get("name", str(key)) if c else str(key))
                else:
                    names.append(key)
                rates.append(stats.get("closed_loop_rate", 0))
                cycles.append(stats.get("avg_cycle_days", 0))

            self.perf_chart.plot_closed_loop_performance(names, rates, cycles)
        except Exception as e:
            print(f"刷新绩效图表出错: {e}")

    def _populate_perf_table(self, table, headers, items, key="building"):
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(items))
        for row_idx, (key_id, stats) in enumerate(items):
            if key == "building":
                b = BuildingRepository.get_by_id(key_id)
                name = b.get("name", str(key_id)) if b else str(key_id)
            elif key == "component":
                c = ComponentRepository.get_by_id(key_id)
                name = c.get("name", str(key_id)) if c else str(key_id)
            else:
                name = key_id
            values = [
                name,
                stats.get("total", 0),
                stats.get("closed", 0),
                f"{stats.get('closed_loop_rate', 0):.1f}",
                f"{stats.get('avg_cycle_days', 0):.1f}",
                stats.get("rework_count", 0)
            ]
            for col, val in enumerate(values):
                table.setItem(row_idx, col, QTableWidgetItem(str(val)))
        table.resizeColumnsToContents()

    def _refresh_users(self):
        try:
            users = UserRepository.get_all()
            headers = ["ID", "用户名", "姓名", "邮箱", "电话", "状态", "角色"]
            self.user_table.setColumnCount(len(headers))
            self.user_table.setHorizontalHeaderLabels(headers)
            self.user_table.setRowCount(len(users))
            for row, u in enumerate(users):
                roles = UserRepository.get_user_roles(u["id"])
                role_names = ", ".join([r.get("name", "") for r in roles])
                values = [
                    u.get("id", ""),
                    u.get("username", ""),
                    u.get("full_name", ""),
                    u.get("email", ""),
                    u.get("phone", ""),
                    u.get("status", ""),
                    role_names
                ]
                for col, val in enumerate(values):
                    self.user_table.setItem(row, col, QTableWidgetItem(str(val)))
            self.user_table.resizeColumnsToContents()
        except Exception as e:
            print(f"刷新用户列表出错: {e}")

    def _on_add_user(self):
        dlg = UserDialog(self)
        if dlg.exec():
            try:
                data = dlg.get_data()
                role_ids = data.pop("role_ids", [])
                uid = UserRepository.create(**data)
                for rid in role_ids:
                    UserRepository.assign_role(uid, rid)
                self._refresh_users()
            except Exception as e:
                QMessageBox.critical(self, "失败", f"保存失败: {str(e)}")

    def _on_edit_user(self):
        uid = self._get_selected_id(self.user_table)
        if not uid:
            return
        user = UserRepository.get_by_id(uid)
        if not user:
            return
        user["role_ids"] = [r["id"] for r in UserRepository.get_user_roles(uid)]
        dlg = UserDialog(self, user=user)
        if dlg.exec():
            try:
                data = dlg.get_data()
                role_ids = data.pop("role_ids", [])
                UserRepository.update(uid, **data)
                UserRepository.clear_roles(uid)
                for rid in role_ids:
                    UserRepository.assign_role(uid, rid)
                self._refresh_users()
            except Exception as e:
                QMessageBox.critical(self, "失败", f"保存失败: {str(e)}")

    def _on_delete_user(self):
        uid = self._get_selected_id(self.user_table)
        if not uid:
            return
        reply = QMessageBox.question(self, "确认删除", "确定要删除该用户吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                UserRepository.delete(uid)
                self._refresh_users()
            except Exception as e:
                QMessageBox.critical(self, "失败", f"删除失败: {str(e)}")

    def _refresh_roles(self):
        try:
            roles = RoleRepository.get_all()
            headers = ["ID", "角色名称", "代码", "描述", "权限数"]
            self.role_table.setColumnCount(len(headers))
            self.role_table.setHorizontalHeaderLabels(headers)
            self.role_table.setRowCount(len(roles))
            for row, r in enumerate(roles):
                perms = RoleRepository.get_role_permissions(r["id"])
                values = [
                    r.get("id", ""),
                    r.get("name", ""),
                    r.get("code", ""),
                    r.get("description", ""),
                    len(perms)
                ]
                for col, val in enumerate(values):
                    self.role_table.setItem(row, col, QTableWidgetItem(str(val)))
            self.role_table.resizeColumnsToContents()
        except Exception as e:
            print(f"刷新角色列表出错: {e}")

    def _on_edit_role_permissions(self):
        row = self.role_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一个角色")
            return
        rid_item = self.role_table.item(row, 0)
        if not rid_item:
            return
        rid = int(rid_item.text())
        role = RoleRepository.get_by_id(rid)
        if not role:
            return
        current_perms = [p["code"] for p in RoleRepository.get_role_permissions(rid)]
        dlg = RolePermissionDialog(self, role=role, current_permissions=current_perms)
        if dlg.exec():
            try:
                perms = dlg.get_selected_permissions()
                RoleRepository.clear_permissions(rid)
                for p in perms:
                    RoleRepository.assign_permission(rid, p)
                self._refresh_roles()
                QMessageBox.information(self, "成功", "角色权限已更新")
            except Exception as e:
                QMessageBox.critical(self, "失败", f"保存失败: {str(e)}")

    def _on_generate_summary_report(self):
        try:
            building_id = self.report_summary_building.currentData()
            period = self.report_summary_period.currentText()
            bldg = BuildingRepository.get_by_id(building_id) if building_id else None
            bldg_name = bldg.get("name", "全部建筑") if bldg else "全部建筑"

            filename = f"综合汇总报告_{bldg_name}_{period}_{datetime.now().strftime('%Y%m%d')}.txt"
            filepath = os.path.join(os.path.expanduser("~"), "Documents", filename)

            defects = DefectRepository.get_all()
            if building_id:
                defects = [d for d in defects if d.get("building_id") == building_id]
            workorders = WorkOrderRepository.get_all()
            if building_id:
                workorders = [w for w in workorders if w.get("building_id") == building_id]
            resources = MaintenanceResourceRepository.get_all()
            if building_id:
                resources = [r for r in resources if r.get("building_id") == building_id]
            perf = calculate_closed_loop_performance(building_id)
            eff = calculate_effectiveness_comparison(building_id)

            total_cost = sum((r.get("quantity", 0) or 0) * (r.get("unit_price", 0) or 0) for r in resources)

            report = f"""{'='*60}
古建筑木构件含水率智能预警系统 - 综合汇总报告
{'='*60}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
统计范围: {bldg_name}
统计周期: {period}

一、病害概览
{'-'*40}
  病害总数: {len(defects)}
  已闭环数: {perf.get('closed', 0)}
  闭环率: {perf.get('closed_loop_rate', 0):.1f}%
  平均处理周期: {perf.get('avg_cycle_days', 0):.1f}天
  返工数: {perf.get('rework_count', 0)}

二、风险分布
{'-'*40}
"""
            sev_count = {}
            for d in defects:
                s = d.get("severity", "未知")
                sev_count[s] = sev_count.get(s, 0) + 1
            for s, c in sev_count.items():
                report += f"  {s}: {c}\n"

            report += f"""
三、维修资源消耗
{'-'*40}
  资源记录数: {len(resources)}
  总成本: ¥{total_cost:,.2f}

四、处置效果
{'-'*40}
  已评估数: {eff.get('total_evaluated', 0)}
  平均改善率: {eff.get('avg_improvement_rate', 0):.1f}%

{'='*60}
报告结束
"""
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(report)

            try:
                ReportArchiveRepository.create(
                    report_type="综合汇总报告",
                    file_name=filename,
                    file_path=filepath,
                    file_size=os.path.getsize(filepath),
                    building_id=building_id,
                    description=f"{bldg_name} - {period}综合汇总"
                )
            except Exception:
                pass

            QMessageBox.information(self, "成功", f"报告已导出到:\n{filepath}")
            self._refresh_archives()
        except Exception as e:
            QMessageBox.critical(self, "失败", f"生成失败: {str(e)}")

    def _on_generate_performance_report(self):
        try:
            building_id = self.report_perf_building.currentData()
            bldg = BuildingRepository.get_by_id(building_id) if building_id else None
            bldg_name = bldg.get("name", "全部建筑") if bldg else "全部建筑"

            filename = f"闭环绩效报告_{bldg_name}_{datetime.now().strftime('%Y%m%d')}.txt"
            filepath = os.path.join(os.path.expanduser("~"), "Documents", filename)

            data = calculate_closed_loop_performance(building_id)

            report = f"""{'='*60}
古建筑木构件含水率智能预警系统 - 闭环绩效报告
{'='*60}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
统计范围: {bldg_name}

总体绩效
{'-'*40}
  病害总数: {data.get('total', 0)}
  已闭环数: {data.get('closed', 0)}
  闭环率: {data.get('closed_loop_rate', 0):.1f}%
  平均处理周期: {data.get('avg_cycle_days', 0):.1f}天
  返工数: {data.get('rework_count', 0)}

按建筑统计
{'-'*40}
"""
            for bid, stats in data.get("by_building", {}).items():
                b = BuildingRepository.get_by_id(bid)
                name = b.get("name", str(bid)) if b else str(bid)
                report += f"  {name}: 闭环率 {stats.get('closed_loop_rate', 0):.1f}%, 平均周期 {stats.get('avg_cycle_days', 0):.1f}天\n"

            report += f"\n按构件类型统计\n{'-'*40}\n"
            for cid, stats in data.get("by_component", {}).items():
                c = ComponentRepository.get_by_id(cid)
                name = c.get("name", str(cid)) if c else str(cid)
                report += f"  {name}: 闭环率 {stats.get('closed_loop_rate', 0):.1f}%, 平均周期 {stats.get('avg_cycle_days', 0):.1f}天\n"

            report += f"\n按病害类型统计\n{'-'*40}\n"
            for dtype, stats in data.get("by_type", {}).items():
                report += f"  {dtype}: 闭环率 {stats.get('closed_loop_rate', 0):.1f}%, 平均周期 {stats.get('avg_cycle_days', 0):.1f}天\n"

            report += f"\n{'='*60}\n报告结束\n"

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(report)

            try:
                ReportArchiveRepository.create(
                    report_type="闭环绩效报告",
                    file_name=filename,
                    file_path=filepath,
                    file_size=os.path.getsize(filepath),
                    building_id=building_id,
                    description=f"{bldg_name} - 闭环绩效分析"
                )
            except Exception:
                pass

            QMessageBox.information(self, "成功", f"报告已导出到:\n{filepath}")
            self._refresh_archives()
        except Exception as e:
            QMessageBox.critical(self, "失败", f"生成失败: {str(e)}")

    def _on_generate_effect_report(self):
        try:
            building_id = self.report_eff_building.currentData()
            bldg = BuildingRepository.get_by_id(building_id) if building_id else None
            bldg_name = bldg.get("name", "全部建筑") if bldg else "全部建筑"

            filename = f"处置效果报告_{bldg_name}_{datetime.now().strftime('%Y%m%d')}.txt"
            filepath = os.path.join(os.path.expanduser("~"), "Documents", filename)

            data = calculate_effectiveness_comparison(building_id)

            report = f"""{'='*60}
古建筑木构件含水率智能预警系统 - 处置效果报告
{'='*60}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
统计范围: {bldg_name}

总体效果
{'-'*40}
  已评估数: {data.get('total_evaluated', 0)}
  平均改善率: {data.get('avg_improvement_rate', 0):.1f}%

效果分布
{'-'*40}
"""
            for level, count in data.get("effect_distribution", {}).items():
                report += f"  {level}: {count}\n"

            report += f"\n按病害类型统计\n{'-'*40}\n"
            for dtype, stats in data.get("by_type", {}).items():
                report += f"  {dtype}: 平均改善率 {stats.get('avg_improvement_rate', 0):.1f}%, 样本数 {stats.get('count', 0)}\n"

            report += f"\n改善率最佳 Top 5\n{'-'*40}\n"
            for i, d in enumerate(data.get("top_5", [])[:5], 1):
                b = BuildingRepository.get_by_id(d.get("building_id")) or {}
                report += f"  {i}. {d.get('defect_type', '')} @ {b.get('name', '')} - 改善率 {d.get('improvement_rate', 0):.1f}% (效果: {d.get('effect_level', '')})\n"

            report += f"\n改善率较低 Bottom 5\n{'-'*40}\n"
            for i, d in enumerate(data.get("bottom_5", [])[:5], 1):
                b = BuildingRepository.get_by_id(d.get("building_id")) or {}
                report += f"  {i}. {d.get('defect_type', '')} @ {b.get('name', '')} - 改善率 {d.get('improvement_rate', 0):.1f}% (效果: {d.get('effect_level', '')})\n"

            report += f"\n{'='*60}\n报告结束\n"

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(report)

            try:
                ReportArchiveRepository.create(
                    report_type="处置效果报告",
                    file_name=filename,
                    file_path=filepath,
                    file_size=os.path.getsize(filepath),
                    building_id=building_id,
                    description=f"{bldg_name} - 处置效果分析"
                )
            except Exception:
                pass

            QMessageBox.information(self, "成功", f"报告已导出到:\n{filepath}")
            self._refresh_archives()
        except Exception as e:
            QMessageBox.critical(self, "失败", f"生成失败: {str(e)}")

    def _on_generate_resource_report(self):
        try:
            building_id = self.report_res_building.currentData()
            period = self.report_res_period.currentText()
            bldg = BuildingRepository.get_by_id(building_id) if building_id else None
            bldg_name = bldg.get("name", "全部建筑") if bldg else "全部建筑"

            filename = f"资源统计报告_{bldg_name}_{period}_{datetime.now().strftime('%Y%m%d')}.txt"
            filepath = os.path.join(os.path.expanduser("~"), "Documents", filename)

            resources = MaintenanceResourceRepository.get_all()
            if building_id:
                resources = [r for r in resources if r.get("building_id") == building_id]

            stats = MaintenanceResourceRepository.get_statistics()
            by_type = stats.get("by_type", {})
            by_building = stats.get("by_building", {})

            total_cost = sum((r.get("quantity", 0) or 0) * (r.get("unit_price", 0) or 0) for r in resources)

            report = f"""{'='*60}
古建筑木构件含水率智能预警系统 - 资源统计报告
{'='*60}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
统计范围: {bldg_name}
统计周期: {period}

总体资源消耗
{'-'*40}
  资源记录总数: {len(resources)}
  总成本: ¥{total_cost:,.2f}

按资源类型统计
{'-'*40}
"""
            for rtype, s in by_type.items():
                report += f"  {rtype}: {s.get('total_count', 0)}条, 成本 ¥{s.get('total_cost', 0):,.2f}\n"

            report += f"\n按建筑统计\n{'-'*40}\n"
            for bid, s in by_building.items():
                b = BuildingRepository.get_by_id(bid)
                name = b.get("name", str(bid)) if b else str(bid)
                report += f"  {name}: {s.get('total_count', 0)}条, 成本 ¥{s.get('total_cost', 0):,.2f}\n"

            report += f"\n资源明细\n{'-'*40}\n"
            for r in resources[:50]:
                b = BuildingRepository.get_by_id(r.get("building_id")) or {}
                tc = (r.get("quantity", 0) or 0) * (r.get("unit_price", 0) or 0)
                report += f"  [{r.get('resource_type', '')}] {r.get('resource_name', '')} x{r.get('quantity', 0)}{r.get('unit', '')} - ¥{tc:,.2f} @ {b.get('name', '')}\n"

            if len(resources) > 50:
                report += f"  ... (共{len(resources)}条，仅显示前50条)\n"

            report += f"\n{'='*60}\n报告结束\n"

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(report)

            try:
                ReportArchiveRepository.create(
                    report_type="资源统计报告",
                    file_name=filename,
                    file_path=filepath,
                    file_size=os.path.getsize(filepath),
                    building_id=building_id,
                    description=f"{bldg_name} - {period}资源统计"
                )
            except Exception:
                pass

            QMessageBox.information(self, "成功", f"报告已导出到:\n{filepath}")
            self._refresh_archives()
        except Exception as e:
            QMessageBox.critical(self, "失败", f"生成失败: {str(e)}")

    def _get_selected_id(self, table):
        row = table.currentRow()
        if row < 0:
            return None
        item = table.item(row, 0)
        if not item:
            return None
        try:
            return int(item.text())
        except (ValueError, TypeError):
            return None
