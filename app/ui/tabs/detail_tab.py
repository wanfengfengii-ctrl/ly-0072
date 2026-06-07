from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSplitter, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from app.ui.tabs.base_tab import BaseTab
from app.ui.chart_widget import ChartWidget
from app.ui.csv_import_dialog import CSVImportDialog
from app.common import (
    create_button, create_stat_card, update_stat_card,
    populate_table, setup_table_style, resize_table_columns, get_selected_row_ids,
    show_info, show_warning, show_error, confirm_delete
)
from app.db.database import (
    BuildingRepository, ComponentRepository, RecordRepository,
    SettingsRepository
)
from app.logic.validator import analyze_component_risk, calculate_statistics
from app.logic.report_exporter import generate_html_report


RISK_COLORS = {
    "高风险": QColor(231, 76, 60),
    "中风险": QColor(230, 126, 34),
    "正常": QColor(46, 204, 113),
}


class DetailTab(BaseTab):
    def __init__(self, main_window: Optional[QWidget] = None):
        super().__init__(main_window)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

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

        content_splitter = QSplitter(Qt.Vertical)

        records_widget = self._create_records_widget()
        content_splitter.addWidget(records_widget)

        charts_widget = self._create_charts_widget()
        content_splitter.addWidget(charts_widget)

        risk_widget = self._create_risk_widget()
        content_splitter.addWidget(risk_widget)

        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 1)
        content_splitter.setStretchFactor(2, 1)
        layout.addWidget(content_splitter, stretch=1)

        btn_row = QHBoxLayout()
        self.btn_import_csv = create_button(
            "导入CSV数据...",
            self._on_import_csv,
            "background-color: #3498db; color: white; padding: 6px 16px;"
        )
        btn_row.addWidget(self.btn_import_csv)
        self.btn_delete_record = create_button("删除记录", self._on_delete_record)
        btn_row.addWidget(self.btn_delete_record)
        btn_row.addStretch()
        self.btn_export_report = create_button(
            "导出巡检报告(HTML)",
            self._on_export_report,
            "background-color: #27ae60; color: white; padding: 8px 20px;"
        )
        btn_row.addWidget(self.btn_export_report)
        layout.addLayout(btn_row)

    def _create_records_widget(self) -> QGroupBox:
        widget = QGroupBox("检测记录")
        layout = QVBoxLayout(widget)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("筛选位置:"))
        self.record_position_filter = QComboBox()
        self.record_position_filter.addItem("全部")
        self.record_position_filter.currentIndexChanged.connect(self._refresh_records_table)
        filter_row.addWidget(self.record_position_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self.records_table = QTableWidget()
        setup_table_style(self.records_table)
        layout.addWidget(self.records_table)

        return widget

    def _create_charts_widget(self) -> QGroupBox:
        widget = QGroupBox("图表分析")
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

    def _create_risk_widget(self) -> QGroupBox:
        widget = QGroupBox("风险分析")
        layout = QVBoxLayout(widget)

        self.risk_summary = QLabel("请选择构件查看风险分析")
        self.risk_summary.setFont(QFont("", 11))
        self.risk_summary.setAlignment(Qt.AlignCenter)
        self.risk_summary.setStyleSheet("color: #888; padding: 10px;")
        layout.addWidget(self.risk_summary)

        self.risk_table = QTableWidget()
        setup_table_style(self.risk_table)
        resize_table_columns(self.risk_table, "stretch")
        layout.addWidget(self.risk_table, stretch=1)

        return widget

    def refresh(self) -> None:
        if self.current_component_id:
            self._load_component_detail()
            self._refresh_records_table()
            self._refresh_chart()
            self._refresh_risk_analysis()

    def _load_component_detail(self) -> None:
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

    def _refresh_records_table(self) -> None:
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
        data = []
        threshold = SettingsRepository.get_moisture_threshold()

        for r in records:
            temp_val = f"{r['temperature']:.1f}" if r["temperature"] is not None else "-"
            hum_val = f"{r['humidity']:.1f}" if r["humidity"] is not None else "-"
            data.append([
                str(r["id"]),
                r["measure_time"],
                r["measure_position"],
                f"{r['moisture']:.1f}",
                temp_val,
                hum_val,
                r.get("operator") or "",
                r.get("remark") or "",
            ])

        color_rules = {
            3: lambda x: RISK_COLORS["高风险"] if float(x) > threshold else None,
        }

        populate_table(self.records_table, headers, data, color_rules)
        resize_table_columns(self.records_table, "resize_to_contents")
        self.records_table.horizontalHeader().setStretchLastSection(True)

        for row in range(self.records_table.rowCount()):
            item = self.records_table.item(row, 3)
            if item and item.foreground().color() == RISK_COLORS["高风险"]:
                font = item.font()
                font.setBold(True)
                item.setFont(font)

    def _refresh_chart(self) -> None:
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

    def _refresh_risk_analysis(self) -> None:
        if not self.current_component_id:
            self.risk_summary.setText("请选择构件查看风险分析")
            self.risk_summary.show()
            self.risk_table.hide()
            return

        result = analyze_component_risk(self.current_component_id)
        threshold = SettingsRepository.get_moisture_threshold()

        all_issues: List[Dict[str, str]] = []
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

        risk_color = RISK_COLORS[result["overall_risk_level"]].name()
        summary = (
            f"风险等级: <span style='color:{risk_color}; "
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
        data = [[issue["类型"], issue["位置"], issue["详情"], issue["级别"]] for issue in all_issues]
        color_rules = {
            3: lambda x: RISK_COLORS.get(x),
        }

        populate_table(self.risk_table, headers, data, color_rules)
        resize_table_columns(self.risk_table, "stretch")

        for row in range(self.risk_table.rowCount()):
            item = self.risk_table.item(row, 3)
            if item:
                font = item.font()
                font.setBold(True)
                item.setFont(font)

        self.risk_table.show()

    def _on_import_csv(self) -> None:
        if not self.current_component_id:
            show_warning(self, "提示", "请先选择一个构件")
            return
        dlg = CSVImportDialog(self, default_component_id=self.current_component_id)
        if dlg.exec():
            if self.main_window and hasattr(self.main_window, "refresh_buildings"):
                self.main_window.refresh_buildings()
            self._load_component_detail()
            self._refresh_records_table()
            self._refresh_chart()
            self._refresh_risk_analysis()

    def _on_delete_record(self) -> None:
        ids = get_selected_row_ids(self.records_table, 0)
        if not ids:
            show_warning(self, "提示", "请选择要删除的记录")
            return

        if not confirm_delete(self, len(ids), "记录"):
            return

        deleted = 0
        for rid in ids:
            if RecordRepository.delete(rid):
                deleted += 1

        show_info(self, "成功", f"已删除 {deleted} 条记录")
        self._load_component_detail()
        self._refresh_records_table()
        self._refresh_chart()
        self._refresh_risk_analysis()
        if self.main_window and hasattr(self.main_window, "refresh_buildings"):
            self.main_window.refresh_buildings()

    def _on_export_report(self) -> None:
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
            show_info(self, "导出成功", f"报告已成功导出到:\n{output}")
        except Exception as e:
            show_error(self, "导出失败", f"生成报告失败: {str(e)}")
