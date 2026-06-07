from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView
)
from typing import Optional, Dict, Any, List

from app.common.table_utils import populate_table, setup_table_style, get_selected_row_id
from app.common.message_utils import show_info, show_warning, show_error
from app.common.ui_utils import create_stat_card, update_stat_card

from app.services.recurrence_service import RecurrenceService
from app.services.defect_service import DefectService
from app.db.database import DefectRepository
from app.ui.chart_widget import ChartWidget
from app.ui.advanced_dialogs import DefectRecurrenceDialog
from app.ui.tabs.base_tab import BaseTab


class RecurrenceTab(BaseTab):
    def __init__(self, parent: Optional[QWidget] = None):
        self._detected_recurrences: List[Dict[str, Any]] = []
        self.current_building_id: Optional[int] = None
        super().__init__(parent)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        stat_row = QHBoxLayout()
        self.stat_total = create_stat_card("复发总次数", "0", "#e74c3c")
        self.stat_avg_days = create_stat_card("平均间隔天数", "0", "#f39c12")
        self.stat_same_loc = create_stat_card("同位置复发", "0", "#c0392b")
        self.stat_same_type = create_stat_card("同类病害", "0", "#e67e22")
        stat_row.addWidget(self.stat_total)
        stat_row.addWidget(self.stat_avg_days)
        stat_row.addWidget(self.stat_same_loc)
        stat_row.addWidget(self.stat_same_type)
        layout.addLayout(stat_row)

        self.recurrence_chart = ChartWidget()
        layout.addWidget(self.recurrence_chart, stretch=1)

        self.detail_tabs = QTabWidget()

        known_widget = QWidget()
        known_layout = QVBoxLayout(known_widget)
        btn_row1 = QHBoxLayout()
        btn_row1.addWidget(QLabel("已知复发关联:"))
        btn_row1.addStretch()
        self.btn_refresh_known = QPushButton("🔄 刷新")
        btn_row1.addWidget(self.btn_refresh_known)
        known_layout.addLayout(btn_row1)
        self.known_table = QTableWidget()
        setup_table_style(self.known_table)
        known_layout.addWidget(self.known_table, stretch=1)
        self.detail_tabs.addTab(known_widget, "✅ 已关联复发")

        detect_widget = QWidget()
        detect_layout = QVBoxLayout(detect_widget)
        btn_row2 = QHBoxLayout()
        self.btn_detect = QPushButton("🔍 智能检测潜在复发")
        self.btn_detect.setStyleSheet("background-color: #e67e22; color: white; padding: 6px 16px;")
        btn_row2.addWidget(self.btn_detect)
        self.btn_mark = QPushButton("🔗 标记关联")
        btn_row2.addWidget(self.btn_mark)
        btn_row2.addStretch()
        detect_layout.addLayout(btn_row2)
        self.detect_table = QTableWidget()
        setup_table_style(self.detect_table)
        detect_layout.addWidget(self.detect_table, stretch=1)
        self.detail_tabs.addTab(detect_widget, "🔍 潜在复发检测")

        layout.addWidget(self.detail_tabs, stretch=2)

    def _setup_connections(self) -> None:
        self.btn_refresh_known.clicked.connect(self._refresh_known)
        self.btn_detect.clicked.connect(self._on_detect)
        self.btn_mark.clicked.connect(self._on_mark)
        self.detail_tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int) -> None:
        if self.detail_tabs.tabText(index).startswith("✅"):
            self._refresh_known()

    def set_building_context(self, building_id: Optional[int] = None) -> None:
        self.current_building_id = building_id
        self.refresh()

    def refresh(self) -> None:
        self._refresh_known()

    def _refresh_known(self) -> None:
        try:
            analysis = RecurrenceService.get_analysis(building_id=self.current_building_id)
            recurrences = analysis.get("recurrences", [])
            avg_days_list = [r.get("days_between", 0) or 0 for r in recurrences if r.get("days_between")]
            avg_days = sum(avg_days_list) / len(avg_days_list) if avg_days_list else 0

            same_loc = len([r for r in recurrences if r.get("recurrence_type") == "同一位置复发"])
            same_type = len([r for r in recurrences if r.get("recurrence_type") == "同类病害"])

            update_stat_card(self.stat_total, str(len(recurrences)))
            update_stat_card(self.stat_avg_days, f"{avg_days:.0f}")
            update_stat_card(self.stat_same_loc, str(same_loc))
            update_stat_card(self.stat_same_type, str(same_type))

            self.recurrence_chart.plot_recurrence_analysis(analysis)

            headers = ["ID", "原发病害", "复发病害", "复发类型", "间隔天数", "根因分析", "记录时间"]
            data = []
            for r in recurrences:
                orig = DefectRepository.get_by_id(r.get("original_defect_id")) or {}
                recur = DefectRepository.get_by_id(r.get("recurrence_defect_id")) or {}
                data.append([
                    r.get("id", ""),
                    f"{orig.get('defect_type', '')}@{(orig.get('discovery_date', '') or '')[:10]}",
                    f"{recur.get('defect_type', '')}@{(recur.get('discovery_date', '') or '')[:10]}",
                    r.get("recurrence_type", ""),
                    r.get("days_between", ""),
                    (r.get("root_cause", "") or "")[:20],
                    (r.get("created_at", "") or "")[:10] if r.get("created_at") else ""
                ])

            populate_table(self.known_table, headers, data)
            self.known_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.known_table.horizontalHeader().setStretchLastSection(True)
        except Exception as e:
            print(f"刷新复发分析出错: {e}")

    def _on_detect(self) -> None:
        try:
            potentials = RecurrenceService.detect_potential_recurrences(
                building_id=self.current_building_id
            )
            if not potentials:
                show_info(self, "检测结果", "未检测到潜在的病害复发关联")
                return

            self._detected_recurrences = potentials

            headers = ["相似度", "原发病害", "复发病害", "位置匹配", "类型匹配", "描述匹配"]
            data = []
            for p in potentials:
                orig = p.get("original", {})
                recur = p.get("recurrent", {})
                data.append([
                    f"{p.get('similarity', 0):.0%}",
                    f"{orig.get('defect_type', '')}@{orig.get('location_detail', '')}",
                    f"{recur.get('defect_type', '')}@{recur.get('location_detail', '')}",
                    "✓" if p.get("location_match") else "✗",
                    "✓" if p.get("type_match") else "✗",
                    f"{p.get('description_similarity', 0):.0%}"
                ])

            populate_table(self.detect_table, headers, data)
            self.detect_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.detect_table.horizontalHeader().setStretchLastSection(True)

            show_info(self, "检测完成", f"检测到 {len(potentials)} 条潜在复发关联，请确认")
        except Exception as e:
            show_error(self, "失败", f"检测失败: {str(e)}")

    def _on_mark(self) -> None:
        row = self.detect_table.currentRow()
        if row < 0 or not self._detected_recurrences:
            show_warning(self, "提示", "请先在检测结果中选择一条记录")
            return
        p = self._detected_recurrences[row]
        dlg = DefectRecurrenceDialog(
            self,
            original_defect=p.get("original"),
            recurrence_defect=p.get("recurrent")
        )
        if dlg.exec():
            try:
                data = dlg.get_data()
                RecurrenceService.create_recurrence(
                    original_defect_id=data.get("original_defect_id"),
                    recurrence_defect_id=data.get("recurrence_defect_id"),
                    recurrence_type=data.get("recurrence_type", "同一位置复发"),
                    days_between=data.get("days_between"),
                    root_cause=data.get("root_cause", ""),
                    remark=data.get("remark", "")
                )
                show_info(self, "成功", "已标记复发关联")
                self._refresh_known()
            except Exception as e:
                show_error(self, "失败", f"保存失败: {str(e)}")
