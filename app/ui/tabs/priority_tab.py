from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from typing import Optional, Dict, Any, List

from app.common.table_utils import populate_table, setup_table_style
from app.common.message_utils import show_info, show_warning, show_error
from app.common.ui_utils import create_stat_card, update_stat_card

from app.services.performance_service import PerformanceService
from app.services.defect_service import DefectService
from app.db.database import BuildingRepository, DefectRepository
from app.ui.chart_widget import ChartWidget
from app.ui.tabs.base_tab import BaseTab


class PriorityTab(BaseTab):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.deadline_alert_banner = QLabel("")
        self.deadline_alert_banner.setStyleSheet("""
            padding: 10px; background: #fff3cd; border: 1px solid #ffeeba;
            border-radius: 4px; color: #856404; font-weight: bold;
        """)
        self.deadline_alert_banner.hide()
        layout.addWidget(self.deadline_alert_banner)

        stat_row = QHBoxLayout()
        self.stat_urgent = create_stat_card("紧急", "0", "#e74c3c")
        self.stat_high = create_stat_card("高", "0", "#e67e22")
        self.stat_medium = create_stat_card("中", "0", "#3498db")
        self.stat_low = create_stat_card("低", "0", "#27ae60")
        self.stat_overdue = create_stat_card("已逾期", "0", "#c0392b")
        stat_row.addWidget(self.stat_urgent)
        stat_row.addWidget(self.stat_high)
        stat_row.addWidget(self.stat_medium)
        stat_row.addWidget(self.stat_low)
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
        btn_row.addWidget(self.btn_auto_priority)

        self.btn_refresh = QPushButton("🔄 刷新排序")
        btn_row.addWidget(self.btn_refresh)

        btn_row.addWidget(QLabel("建筑筛选:"))
        self.building_filter = QComboBox()
        self.building_filter.addItem("全部建筑", None)
        for b in BuildingRepository.get_all():
            self.building_filter.addItem(b["name"], b["id"])
        btn_row.addWidget(self.building_filter)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.priority_table = QTableWidget()
        setup_table_style(self.priority_table)
        layout.addWidget(self.priority_table, stretch=2)

    def _setup_connections(self) -> None:
        self.btn_auto_priority.clicked.connect(self._on_auto_calculate)
        self.btn_refresh.clicked.connect(self.refresh)
        self.building_filter.currentIndexChanged.connect(self.refresh)

    def refresh(self) -> None:
        self._refresh_list()

    def _refresh_list(self) -> None:
        try:
            all_defects = DefectService.get_defects()
            building_id = self.building_filter.currentData()
            if building_id:
                all_defects = [d for d in all_defects if d.get("building_id") == building_id]

            sorted_defects = PerformanceService.sort_defects_by_priority(all_defects)

            counts: Dict[str, int] = {"紧急": 0, "高": 0, "中": 0, "低": 0}
            for d in sorted_defects:
                score, level, _ = PerformanceService.calculate_priority(d)
                if level in counts:
                    counts[level] += 1

            update_stat_card(self.stat_urgent, str(counts["紧急"]))
            update_stat_card(self.stat_high, str(counts["高"]))
            update_stat_card(self.stat_medium, str(counts["中"]))
            update_stat_card(self.stat_low, str(counts["低"]))

            warnings = PerformanceService.check_rectification_deadlines()
            overdue_list = warnings.get("overdue", [])
            update_stat_card(self.stat_overdue, str(len(overdue_list)))

            if overdue_list:
                msg = f"⚠ 有 {len(overdue_list)} 个工单已逾期，请及时处理！"
                self.deadline_alert_banner.setText(msg)
                self.deadline_alert_banner.show()
            else:
                self.deadline_alert_banner.hide()

            headers = ["优先级", "评分", "病害类型", "严重程度", "建筑", "构件",
                       "含水率(%)", "发现日期", "截止日期", "状态", "影响因素"]
            data = []
            color_rules = {
                0: lambda val: {
                    "紧急": QColor(231, 76, 60), "高": QColor(230, 126, 34),
                    "中": QColor(52, 152, 219), "低": QColor(39, 174, 96)
                }.get(val),
            }

            for defect in sorted_defects:
                score, level, factors = PerformanceService.calculate_priority(defect)
                bldg = BuildingRepository.get_by_id(defect.get("building_id")) or {}
                from app.db.database import ComponentRepository
                comp = ComponentRepository.get_by_id(defect.get("component_id")) or {}

                data.append([
                    level, str(score),
                    defect.get("defect_type", ""),
                    defect.get("severity", ""),
                    bldg.get("name", ""),
                    comp.get("name", ""),
                    str(defect.get("moisture_level", "")),
                    (defect.get("discovery_date", "") or "")[:10],
                    (defect.get("deadline_date", "") or "")[:10],
                    defect.get("status", ""),
                    ", ".join(factors[:3])
                ])

            populate_table(self.priority_table, headers, data, color_rules)
            self.priority_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.priority_table.horizontalHeader().setStretchLastSection(True)

            for row in range(self.priority_table.rowCount()):
                item = self.priority_table.item(row, 0)
                if item and item.foreground().color() != QColor(0, 0, 0):
                    item.setFont(self._bold_font())

            self.priority_chart.plot_priority_distribution(sorted_defects)

            deadline_data = {
                "已逾期": len(warnings.get("overdue", [])),
                "即将到期(≤3天)": len(warnings.get("urgent", [])),
                "提醒期(4-7天)": len(warnings.get("warning", [])),
                "正常": max(0, len(all_defects) - len(warnings.get("overdue", []))
                           - len(warnings.get("urgent", [])) - len(warnings.get("warning", [])))
            }
            self._plot_deadline_distribution(deadline_data)
        except Exception as e:
            print(f"刷新优先级列表出错: {e}")

    def _plot_deadline_distribution(self, deadline_data: Dict[str, int]) -> None:
        self.deadline_chart.canvas.clear()
        ax = self.deadline_chart.canvas.fig.add_subplot(111)

        if not deadline_data or sum(deadline_data.values()) == 0:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14)
            self.deadline_chart.canvas.draw()
            return

        colors = {
            "已逾期": "#e74c3c", "即将到期(≤3天)": "#f39c12",
            "提醒期(4-7天)": "#3498db", "正常": "#2ecc71"
        }
        labels = []
        sizes = []
        pie_colors = []
        for k, v in deadline_data.items():
            if v > 0:
                labels.append(f"{k}({v})")
                sizes.append(v)
                pie_colors.append(colors.get(k, "#34495e"))

        explode = [0.03] * len(sizes)
        wedges, texts, autotexts = ax.pie(
            sizes, explode=explode, labels=labels, colors=pie_colors,
            autopct="%1.1f%%", startangle=90, shadow=False
        )
        for t in autotexts:
            t.set_fontsize(10)
            t.set_color("white")
            t.set_fontweight("bold")

        ax.set_title("整改时限状态分布", fontsize=13, fontweight="bold")
        self.deadline_chart.canvas.draw()

    def _on_auto_calculate(self) -> None:
        try:
            all_defects = DefectService.get_defects()
            updated = 0
            for defect in all_defects:
                score, level, _ = PerformanceService.calculate_priority(defect)
                DefectRepository.update(defect["id"], priority_score=score, priority_level=level)
                updated += 1
            show_info(self, "成功", f"已自动计算 {updated} 条病害的优先级")
            self.refresh()
        except Exception as e:
            show_error(self, "失败", f"计算失败: {str(e)}")
