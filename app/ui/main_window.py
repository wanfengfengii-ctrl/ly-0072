from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QTabWidget,
    QComboBox, QGroupBox, QFormLayout, QDoubleSpinBox, QSpinBox,
    QFileDialog, QTextEdit, QSizePolicy, QAbstractItemView
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor, QIcon, QAction
from typing import Optional, Dict, Any

from app.db.database import (
    BuildingRepository, ComponentRepository, RecordRepository,
    SettingsRepository
)
from app.logic.validator import (
    analyze_component_risk, calculate_statistics
)
from app.logic.report_exporter import generate_html_report
from app.ui.dialogs import BuildingDialog, ComponentDialog
from app.ui.csv_import_dialog import CSVImportDialog
from app.ui.chart_widget import ChartWidget


RISK_COLORS = {
    "高风险": QColor(231, 76, 60),
    "中风险": QColor(230, 126, 34),
    "正常": QColor(46, 204, 113),
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("古建筑木构件含水率分析系统")
        self.resize(1280, 800)
        self.current_building_id = None
        self.current_component_id = None
        self._init_ui()
        self._init_menu()
        self.refresh_buildings()

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

        self.tabs.addTab(self._create_detail_tab(), "构件详情")
        self.tabs.addTab(self._create_records_tab(), "检测记录")
        self.tabs.addTab(self._create_charts_tab(), "图表分析")
        self.tabs.addTab(self._create_risk_tab(), "风险分析")
        self.tabs.addTab(self._create_settings_tab(), "系统设置")

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

        self.spin_consecutive = QSpinBox()
        self.spin_consecutive.setRange(2, 20)
        self.spin_consecutive.setValue(SettingsRepository.get_consecutive_count())
        form.addRow("连续超标判定次数:", self.spin_consecutive)

        self.btn_save_settings = QPushButton("保存设置")
        self.btn_save_settings.clicked.connect(self._on_save_settings)
        form.addRow("", self.btn_save_settings)

        layout.addWidget(group)

        tip = QLabel(
            "\n使用说明:\n"
            "1. 首先创建建筑档案\n"
            "2. 在建筑下创建梁、柱、斗拱等构件档案\n"
            "3. 选择构件后通过'导入CSV数据'批量导入检测记录\n"
            "4. 在各标签页查看趋势、对比、风险分析等信息\n"
            "5. CSV格式: 检测时间、检测位置、含水率为必填列\n"
        )
        tip.setStyleSheet("color: #666; padding: 20px;")
        layout.addWidget(tip)
        layout.addStretch()
        return widget

    def _init_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")

        export_act = QAction("导出巡检报告...", self)
        export_act.triggered.connect(self._on_export_report)
        file_menu.addAction(export_act)

        file_menu.addSeparator()

        exit_act = QAction("退出", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

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

    def _on_tree_context_menu(self, pos):
        pass

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
        SettingsRepository.set_consecutive_count(self.spin_consecutive.value())
        QMessageBox.information(self, "成功", "设置已保存")
        if self.current_component_id:
            self._load_component_detail()
            self._refresh_records_table()
            self._refresh_chart()
            self._refresh_risk_analysis()
        self.refresh_buildings()

    def _on_about(self):
        QMessageBox.about(
            self, "关于",
            "古建筑木构件含水率分析系统 v1.0\n\n"
            "用于分析梁、柱、斗拱等木构件的含水率变化，\n"
            "自动识别腐朽风险并生成巡检报告。\n\n"
            "技术栈: Python + PySide6 + SQLite + Matplotlib"
        )
