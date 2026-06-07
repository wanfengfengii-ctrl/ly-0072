from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget,
    QPushButton, QLabel, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView
)
from PySide6.QtGui import QFont
from typing import Optional, Dict, Any, List

from app.common.table_utils import populate_table, setup_table_style
from app.common.message_utils import show_info
from app.common.ui_utils import create_stat_card, update_stat_card

from app.services.performance_service import PerformanceService
from app.db.database import BuildingRepository
from app.ui.chart_widget import ChartWidget
from app.ui.tabs.base_tab import BaseTab


class EffectivenessTab(BaseTab):
    def __init__(self, parent: Optional[QWidget] = None):
        self.current_building_id: Optional[int] = None
        super().__init__(parent)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        stat_row = QHBoxLayout()
        self.stat_evaluated = create_stat_card("已评估数", "0", "#3498db")
        self.stat_avg_imp = create_stat_card("平均改善率(%)", "0", "#27ae60")
        self.stat_excellent = create_stat_card("优秀", "0", "#27ae60")
        self.stat_poor = create_stat_card("较差", "0", "#e74c3c")
        stat_row.addWidget(self.stat_evaluated)
        stat_row.addWidget(self.stat_avg_imp)
        stat_row.addWidget(self.stat_excellent)
        stat_row.addWidget(self.stat_poor)
        layout.addLayout(stat_row)

        chart_splitter = QSplitter(Qt.Horizontal)
        self.dist_chart = ChartWidget()
        self.type_chart = ChartWidget()
        chart_splitter.addWidget(self.dist_chart)
        chart_splitter.addWidget(self.type_chart)
        chart_splitter.setStretchFactor(0, 1)
        chart_splitter.setStretchFactor(1, 1)
        layout.addWidget(chart_splitter, stretch=1)

        self.detail_tabs = QTabWidget()

        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        label1 = QLabel("🏆 改善效果最佳的病害处置:")
        label1.setFont(QFont("", 11, QFont.Bold))
        top_layout.addWidget(label1)
        self.top_table = QTableWidget()
        setup_table_style(self.top_table)
        top_layout.addWidget(self.top_table, stretch=1)
        self.detail_tabs.addTab(top_widget, "🏆 最佳效果")

        low_widget = QWidget()
        low_layout = QVBoxLayout(low_widget)
        label2 = QLabel("⚠ 改善效果较差的病害处置:")
        label2.setFont(QFont("", 11, QFont.Bold))
        low_layout.addWidget(label2)
        self.low_table = QTableWidget()
        setup_table_style(self.low_table)
        low_layout.addWidget(self.low_table, stretch=1)
        self.detail_tabs.addTab(low_widget, "⚠ 待改进")

        btn_row = QHBoxLayout()
        btn_row.addWidget(QLabel("建筑筛选:"))
        self.building_filter = QComboBox()
        self.building_filter.addItem("全部", None)
        for b in BuildingRepository.get_all():
            self.building_filter.addItem(b["name"], b["id"])
        btn_row.addWidget(self.building_filter)
        btn_row.addStretch()
        self.btn_refresh = QPushButton("🔄 刷新")
        btn_row.addWidget(self.btn_refresh)

        main_bottom = QWidget()
        main_bottom_layout = QVBoxLayout(main_bottom)
        main_bottom_layout.addLayout(btn_row)
        main_bottom_layout.addWidget(self.detail_tabs)
        layout.addWidget(main_bottom, stretch=2)

    def _setup_connections(self) -> None:
        self.btn_refresh.clicked.connect(self.refresh)
        self.building_filter.currentIndexChanged.connect(self.refresh)

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
            data = PerformanceService.calculate_effectiveness(building_id=building_id)

            total_evaluated = data.get("total_evaluated", 0)
            avg_improvement = data.get("overall_avg_improvement", 0)
            effect_dist = data.get("effect_distribution", {})
            top_5 = data.get("best_effects", [])
            bottom_5 = data.get("poor_effects", [])

            update_stat_card(self.stat_evaluated, str(total_evaluated))
            update_stat_card(self.stat_avg_imp, f"{avg_improvement:.1f}")
            update_stat_card(self.stat_excellent, str(effect_dist.get("优秀", 0)))
            update_stat_card(self.stat_poor, str(effect_dist.get("较差", 0) + effect_dist.get("差", 0)))

            self.dist_chart.plot_effect_distribution_pie(data)
            self.type_chart.plot_effectiveness_comparison(data)

            top_headers = ["病害类型", "建筑", "改善率(%)", "维修前(%)", "维修后(%)", "效果等级"]
            self._populate_effect_table(self.top_table, top_headers, top_5)

            low_headers = ["病害类型", "建筑", "改善率(%)", "维修前(%)", "维修后(%)", "效果等级"]
            self._populate_effect_table(self.low_table, low_headers, bottom_5)
        except Exception as e:
            print(f"刷新效果对比出错: {e}")

    def _populate_effect_table(self, table: QTableWidget, headers: List[str], rows: List[Dict[str, Any]]) -> None:
        data = []
        for d in rows:
            bldg = BuildingRepository.get_by_id(d.get("building_id")) or {}
            data.append([
                d.get("defect_type", ""),
                bldg.get("name", ""),
                f"{d.get('moisture_improvement', 0):.1f}",
                d.get("moisture_before", ""),
                d.get("moisture_after", ""),
                d.get("overall_effect", "")
            ])
        populate_table(table, headers, data)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
