from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView
)
from PySide6.QtGui import QFont
from typing import Optional, Dict, Any, List, Tuple

from app.common.table_utils import populate_table, setup_table_style
from app.common.ui_utils import create_stat_card, update_stat_card

from app.services.performance_service import PerformanceService
from app.db.database import BuildingRepository, ComponentRepository
from app.ui.chart_widget import ChartWidget
from app.ui.tabs.base_tab import BaseTab


class PerformanceTab(BaseTab):
    def __init__(self, parent: Optional[QWidget] = None):
        self.current_building_id: Optional[int] = None
        self._current_group_by: str = "building"
        super().__init__(parent)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        stat_row = QHBoxLayout()
        self.stat_total = create_stat_card("病害总数", "0", "#3498db")
        self.stat_closed = create_stat_card("已闭环", "0", "#27ae60")
        self.stat_rate = create_stat_card("闭环率(%)", "0", "#9b59b6")
        self.stat_avg_days = create_stat_card("平均周期(天)", "0", "#f39c12")
        self.stat_rework = create_stat_card("返工数", "0", "#e74c3c")
        stat_row.addWidget(self.stat_total)
        stat_row.addWidget(self.stat_closed)
        stat_row.addWidget(self.stat_rate)
        stat_row.addWidget(self.stat_avg_days)
        stat_row.addWidget(self.stat_rework)
        layout.addLayout(stat_row)

        self.perf_chart = ChartWidget()
        layout.addWidget(self.perf_chart, stretch=1)

        self.detail_tabs = QTabWidget()

        bldg_widget = QWidget()
        bldg_layout = QVBoxLayout(bldg_widget)
        btn_row1 = QHBoxLayout()
        label1 = QLabel("按建筑统计:")
        label1.setFont(QFont("", 11, QFont.Bold))
        btn_row1.addWidget(label1)
        btn_row1.addStretch()
        self.btn_chart_building = QPushButton("📊 建筑绩效图表")
        btn_row1.addWidget(self.btn_chart_building)
        bldg_layout.addLayout(btn_row1)
        self.building_table = QTableWidget()
        setup_table_style(self.building_table)
        bldg_layout.addWidget(self.building_table, stretch=1)
        self.detail_tabs.addTab(bldg_widget, "🏢 按建筑")

        comp_widget = QWidget()
        comp_layout = QVBoxLayout(comp_widget)
        btn_row2 = QHBoxLayout()
        label2 = QLabel("按构件统计:")
        label2.setFont(QFont("", 11, QFont.Bold))
        btn_row2.addWidget(label2)
        btn_row2.addStretch()
        self.btn_chart_component = QPushButton("📊 构件绩效图表")
        btn_row2.addWidget(self.btn_chart_component)
        comp_layout.addLayout(btn_row2)
        self.component_table = QTableWidget()
        setup_table_style(self.component_table)
        comp_layout.addWidget(self.component_table, stretch=1)
        self.detail_tabs.addTab(comp_widget, "🔧 按构件")

        type_widget = QWidget()
        type_layout = QVBoxLayout(type_widget)
        btn_row3 = QHBoxLayout()
        label3 = QLabel("按病害类型统计:")
        label3.setFont(QFont("", 11, QFont.Bold))
        btn_row3.addWidget(label3)
        btn_row3.addStretch()
        self.btn_chart_type = QPushButton("📊 类型绩效图表")
        btn_row3.addWidget(self.btn_chart_type)
        type_layout.addLayout(btn_row3)
        self.type_table = QTableWidget()
        setup_table_style(self.type_table)
        type_layout.addWidget(self.type_table, stretch=1)
        self.detail_tabs.addTab(type_widget, "📋 按病害类型")

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("建筑筛选:"))
        self.building_filter = QComboBox()
        self.building_filter.addItem("全部", None)
        for b in BuildingRepository.get_all():
            self.building_filter.addItem(b["name"], b["id"])
        filter_row.addWidget(self.building_filter)
        filter_row.addStretch()
        self.btn_refresh = QPushButton("🔄 刷新")
        filter_row.addWidget(self.btn_refresh)

        main_bottom = QWidget()
        main_bottom_layout = QVBoxLayout(main_bottom)
        main_bottom_layout.addLayout(filter_row)
        main_bottom_layout.addWidget(self.detail_tabs)
        layout.addWidget(main_bottom, stretch=2)

    def _setup_connections(self) -> None:
        self.btn_refresh.clicked.connect(self.refresh)
        self.building_filter.currentIndexChanged.connect(self.refresh)
        self.btn_chart_building.clicked.connect(lambda: self._refresh_chart("building"))
        self.btn_chart_component.clicked.connect(lambda: self._refresh_chart("component"))
        self.btn_chart_type.clicked.connect(lambda: self._refresh_chart("type"))
        self.detail_tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int) -> None:
        tab_name = self.detail_tabs.tabText(index)
        if "建筑" in tab_name:
            self._refresh_chart("building")
        elif "构件" in tab_name:
            self._refresh_chart("component")
        elif "类型" in tab_name:
            self._refresh_chart("type")

    def set_building_context(self, building_id: Optional[int] = None) -> None:
        self.current_building_id = building_id
        if building_id:
            for i in range(self.building_filter.count()):
                if self.building_filter.itemData(i) == building_id:
                    self.building_filter.setCurrentIndex(i)
                    break
        self.refresh()

    def refresh(self) -> None:
        self._refresh_data()

    def _refresh_data(self) -> None:
        try:
            building_id = self.building_filter.currentData()
            data = PerformanceService.calculate_closed_loop_performance(building_id=building_id)

            update_stat_card(self.stat_total, str(data.get("total_defects", 0)))
            update_stat_card(self.stat_closed, str(data.get("closed_count", 0)))
            update_stat_card(self.stat_rate, f"{data.get('closed_rate', 0):.1f}")
            update_stat_card(self.stat_avg_days, f"{data.get('avg_cycle_days', 0):.1f}")
            update_stat_card(self.stat_rework, str(data.get("rework_count", 0)))

            self._refresh_chart(self._current_group_by)

            by_building = data.get("buildings_detail", [])
            self._populate_perf_table(
                self.building_table,
                ["建筑", "总数", "闭环数", "闭环率(%)", "平均周期(天)", "返工数"],
                by_building, key="building"
            )

            by_component = data.get("components_detail", [])
            self._populate_perf_table(
                self.component_table,
                ["构件", "总数", "闭环数", "闭环率(%)", "平均周期(天)", "返工数"],
                by_component, key="component"
            )

            by_type = data.get("by_defect_type", [])
            self._populate_perf_table(
                self.type_table,
                ["病害类型", "总数", "闭环数", "闭环率(%)", "平均周期(天)", "返工数"],
                by_type, key="type"
            )
        except Exception as e:
            print(f"刷新闭环绩效出错: {e}")

    def _refresh_chart(self, group_by: str = "building") -> None:
        self._current_group_by = group_by
        try:
            building_id = self.building_filter.currentData()
            data = PerformanceService.calculate_closed_loop_performance(building_id=building_id)
            self.perf_chart.plot_closed_loop_performance(data, group_by=group_by)
        except Exception as e:
            print(f"刷新绩效图表出错: {e}")

    def _populate_perf_table(self, table: QTableWidget, headers: List[str],
                             detail: List[Dict[str, Any]], key: str = "building") -> None:
        data = []
        for d in detail:
            if key == "building":
                bid = d.get("building_id")
                b = BuildingRepository.get_by_id(bid) if bid else None
                name = b.get("name", str(bid)) if b else d.get("name", "")
            elif key == "component":
                cid = d.get("component_id")
                c = ComponentRepository.get_by_id(cid) if cid else None
                name = c.get("name", str(cid)) if c else d.get("name", "")
            else:
                name = d.get("defect_type", d.get("name", ""))

            data.append([
                name,
                d.get("total", 0),
                d.get("closed", 0),
                f"{d.get('closed_rate', 0):.1f}",
                f"{d.get('avg_cycle_days', 0):.1f}",
                d.get("rework_count", 0)
            ])

        populate_table(table, headers, data)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
