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
from PySide6.QtGui import QFont, QColor, QIcon, QAction
from typing import Optional, Dict, Any, List
from datetime import datetime
import os

from app.db.database import (
    BuildingRepository, ComponentRepository, RecordRepository,
    SettingsRepository, InspectionPlanRepository, AnomalyReviewRepository,
    ReportArchiveRepository
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
from app.logic.report_exporter import generate_html_report, batch_export_reports, generate_comparison_report
from app.ui.dialogs import BuildingDialog, ComponentDialog
from app.ui.csv_import_dialog import CSVImportDialog
from app.ui.chart_widget import ChartWidget
from app.ui.advanced_dialogs import (
    InspectionPlanDialog, AnomalyReviewDialog, ComponentSelectionDialog,
    BatchExportDialog
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
        elif "报告归档" in tab_name:
            self._refresh_archives()

    def _start_reminder_timer(self):
        self._reminder_timer = QTimer(self)
        self._reminder_timer.timeout.connect(self._check_inspection_reminders)
        self._reminder_timer.start(60000)
        QTimer.singleShot(1000, self._check_inspection_reminders)

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
            self.comparison_table.setItem(row, 3, QTableWidgetItem(comp.get("position", "") or "-"))
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
                    archive=data["archive"]
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
