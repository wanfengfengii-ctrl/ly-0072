from datetime import datetime
from typing import Optional, List, Dict, Any
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from app.ui.tabs.base_tab import BaseTab
from app.ui.chart_widget import ChartWidget
from app.ui.advanced_dialogs import ComponentSelectionDialog
from app.common import (
    create_button, populate_table, setup_table_style,
    resize_table_columns, show_info, show_warning, show_error
)
from app.db.database import SettingsRepository, ReportArchiveRepository
from app.logic.advanced_analytics import compare_components
from app.logic.report_exporter import generate_comparison_report


RISK_COLORS = {
    "高风险": QColor(231, 76, 60),
    "中风险": QColor(230, 126, 34),
    "正常": QColor(46, 204, 113),
}


class ComparisonTab(BaseTab):
    def __init__(self, main_window: Optional[QWidget] = None):
        super().__init__(main_window)
        self._comparison_ids: List[int] = []

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("分组方式:"))
        self.comparison_group_by = QComboBox()
        self.comparison_group_by.addItems(["按构件类型", "按建筑", "按位置"])
        self.comparison_group_by.currentIndexChanged.connect(self._refresh_comparison)
        ctrl_row.addWidget(self.comparison_group_by)

        self.btn_select_components = create_button(
            "选择构件...",
            self._on_select_components_for_comparison,
            "background-color: #3498db; color: white; padding: 6px 16px;"
        )
        ctrl_row.addWidget(self.btn_select_components)

        self.lbl_comparison_count = QLabel("已选择 0 个构件")
        ctrl_row.addWidget(self.lbl_comparison_count)

        ctrl_row.addStretch()

        self.btn_export_comparison = create_button(
            "导出对比报告",
            self._on_export_comparison_report
        )
        ctrl_row.addWidget(self.btn_export_comparison)
        layout.addLayout(ctrl_row)

        content_splitter = QSplitter(Qt.Vertical)
        self.comparison_chart = ChartWidget()
        content_splitter.addWidget(self.comparison_chart)

        self.comparison_table = QTableWidget()
        setup_table_style(self.comparison_table)
        content_splitter.addWidget(self.comparison_table)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 1)
        layout.addWidget(content_splitter, stretch=1)

    @property
    def _selected_ids(self) -> List[int]:
        if self.main_window and hasattr(self.main_window, "selected_comparison_ids"):
            return self.main_window.selected_comparison_ids
        return self._comparison_ids

    @_selected_ids.setter
    def _selected_ids(self, ids: List[int]) -> None:
        self._comparison_ids = ids
        if self.main_window and hasattr(self.main_window, "selected_comparison_ids"):
            self.main_window.selected_comparison_ids = ids

    def refresh(self) -> None:
        self._refresh_comparison()

    def _refresh_comparison(self) -> None:
        if not self._selected_ids:
            self.lbl_comparison_count.setText("已选择 0 个构件（请点击「选择构件...」添加)")
            return

        group_map = {"按构件类型": "type", "按建筑": "building", "按位置": "position"}
        group_by = group_map.get(self.comparison_group_by.currentText(), "type")
        threshold = SettingsRepository.get_moisture_threshold()

        self.lbl_comparison_count.setText(f"已选择 {len(self._selected_ids)} 个构件")

        comparison = compare_components(self._selected_ids, group_by)
        self.comparison_chart.plot_comparison_bar(comparison, threshold)

        groups = comparison.get("groups", {})
        all_components: List[Dict[str, Any]] = []
        for g_data in groups.values():
            all_components.extend(g_data["components"])

        headers = ["构件编号", "构件名称", "类型", "所属建筑/分组", "检测记录",
                   "平均含水率(%)", "最高含水率(%)", "风险等级"]
        data = []

        for comp in all_components:
            if group_by == "building":
                group_value = comp.get("building_name", "") or "未知建筑"
            elif group_by == "type":
                group_value = comp.get("component_type", "") or "其他"
            else:
                group_value = comp.get("position", "") or "-"
            data.append([
                comp["code"],
                comp["name"],
                comp["component_type"],
                group_value,
                str(comp["record_count"]),
                f"{comp['stats']['avg']}%",
                f"{comp['stats']['max']}%",
                comp["risk_level"],
            ])

        color_rules = {
            5: lambda x: RISK_COLORS["高风险"] if float(x.rstrip('%')) > threshold else None,
            6: lambda x: RISK_COLORS["高风险"] if float(x.rstrip('%')) > threshold else None,
            7: lambda x: RISK_COLORS.get(x),
        }

        populate_table(self.comparison_table, headers, data, color_rules)
        resize_table_columns(self.comparison_table, "resize_to_contents")
        self.comparison_table.horizontalHeader().setStretchLastSection(True)

        for row in range(self.comparison_table.rowCount()):
            item = self.comparison_table.item(row, 7)
            if item:
                font = item.font()
                font.setBold(True)
                item.setFont(font)

    def _on_select_components_for_comparison(self) -> None:
        dlg = ComponentSelectionDialog(self)
        if dlg.exec():
            self._selected_ids = dlg.get_selected_ids()
            self._refresh_comparison()

    def _on_export_comparison_report(self) -> None:
        if not self._selected_ids:
            show_warning(self, "提示", "请先选择要对比的构件")
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
                self._selected_ids, output_path=file_path, group_by=group_by
            )
            ReportArchiveRepository.create(
                report_type="对比分析报告",
                file_name=os.path.basename(output),
                file_path=output,
                file_size=os.path.getsize(output),
                generated_by="用户导出",
                description=f"对比分析报告（{len(self._selected_ids)}个构件）"
            )
            show_info(self, "导出成功", f"报告已成功导出到:\n{output}")
        except Exception as e:
            show_error(self, "导出失败", f"生成报告失败: {str(e)}")
