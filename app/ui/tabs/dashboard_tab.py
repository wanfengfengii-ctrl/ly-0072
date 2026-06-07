from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QAbstractItemView, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from app.ui.tabs.base_tab import BaseTab
from app.ui.chart_widget import ChartWidget
from app.ui.advanced_dialogs import BatchExportDialog
from app.services import DashboardService
from app.common import (
    create_stat_card, update_stat_card, create_button,
    populate_table, setup_table_style, resize_table_columns,
    get_risk_color, show_info, show_error
)
from app.db.database import SettingsRepository
from app.logic.report_exporter import batch_export_reports


RISK_COLORS = {
    "高风险": QColor(231, 76, 60),
    "中风险": QColor(230, 126, 34),
    "正常": QColor(46, 204, 113),
}


class DashboardTab(BaseTab):
    def __init__(self, main_window: Optional[QWidget] = None):
        super().__init__(main_window)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.dashboard_summary = QLabel("正在加载总览数据...")
        self.dashboard_summary.setFont(QFont("", 11))
        self.dashboard_summary.setAlignment(Qt.AlignCenter)
        self.dashboard_summary.setStyleSheet(
            "padding: 10px; background: #ecf0f1; border-radius: 4px;"
        )
        layout.addWidget(self.dashboard_summary)

        stat_grid = QGridLayout()
        self.stat_buildings = create_stat_card("🏛 建筑总数", "0", "#3498db")
        self.stat_components = create_stat_card("🧱 构件总数", "0", "#2ecc71")
        self.stat_high_risk = create_stat_card("🔴 高风险构件", "0", "#e74c3c")
        self.stat_pending_reviews = create_stat_card("⚠ 待复核异常", "0", "#f39c12")
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
        setup_table_style(self.dashboard_table)
        layout.addWidget(self.dashboard_table, stretch=1)

        btn_row = QHBoxLayout()
        self.btn_refresh_dashboard = create_button("🔄 刷新数据", self._on_refresh_dashboard)
        btn_row.addWidget(self.btn_refresh_dashboard)
        self.btn_batch_export = create_button(
            "📤 批量导出报告",
            self._on_batch_export,
            "background-color: #3498db; color: white; padding: 6px 16px;"
        )
        btn_row.addWidget(self.btn_batch_export)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def refresh(self) -> None:
        self._refresh_dashboard()

    def _refresh_dashboard(self) -> None:
        try:
            overview = DashboardService.get_multi_building_overview()
            type_dist = DashboardService.get_risk_distribution_by_type()

            self.dashboard_summary.setText(
                f"系统概览 — 数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            update_stat_card(self.stat_buildings, str(overview["total_buildings"]))
            update_stat_card(self.stat_components, str(overview["total_components"]))
            update_stat_card(self.stat_high_risk, str(overview["high_risk_components"]))
            update_stat_card(self.stat_pending_reviews, str(overview["pending_reviews"]))

            self.dashboard_chart1.plot_building_risk_pie(overview)
            self.dashboard_chart2.plot_risk_type_distribution(type_dist)

            buildings = overview.get("buildings", [])
            headers = ["建筑名称", "位置", "构件总数", "高风险", "中风险", "正常",
                       "平均含水率(%)", "最高含水率(%)"]
            data = []
            threshold = SettingsRepository.get_moisture_threshold()

            for b in buildings:
                data.append([
                    b["name"],
                    b.get("location", "") or "-",
                    str(b["total_components"]),
                    str(b["high_risk"]),
                    str(b["medium_risk"]),
                    str(b["normal"]),
                    str(b["avg_moisture"]),
                    str(b["max_moisture"]),
                ])

            color_rules = {
                3: lambda x: RISK_COLORS["高风险"],
                4: lambda x: RISK_COLORS["中风险"],
                5: lambda x: RISK_COLORS["正常"],
                7: lambda x: RISK_COLORS["高风险"] if float(x) > threshold else None,
            }

            populate_table(self.dashboard_table, headers, data, color_rules)
            resize_table_columns(self.dashboard_table, "resize_to_contents")
            self.dashboard_table.horizontalHeader().setStretchLastSection(True)
        except Exception as e:
            self.dashboard_summary.setText(f"加载数据失败: {str(e)}")

    def _on_refresh_dashboard(self) -> None:
        self._refresh_dashboard()
        if self.main_window and hasattr(self.main_window, "refresh_buildings"):
            self.main_window.refresh_buildings()

    def _on_batch_export(self) -> None:
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
                success_count = sum(1 for r in results if r["success"])
                show_info(
                    self, "批量导出完成",
                    f"成功导出 {success_count}/{len(results)} 份报告"
                )
            except Exception as e:
                show_error(self, "导出失败", f"批量导出失败: {str(e)}")
