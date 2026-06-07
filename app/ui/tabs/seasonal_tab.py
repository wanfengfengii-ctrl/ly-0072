from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from app.ui.tabs.base_tab import BaseTab
from app.ui.chart_widget import ChartWidget
from app.ui.advanced_dialogs import ComponentSelectionDialog
from app.common import (
    create_button, populate_table, setup_table_style,
    resize_table_columns, show_warning
)
from app.db.database import SettingsRepository
from app.logic.advanced_analytics import (
    analyze_seasonal_variation, analyze_seasonal_variation_multi
)


RISK_COLORS = {
    "高风险": QColor(231, 76, 60),
    "中风险": QColor(230, 126, 34),
    "正常": QColor(46, 204, 113),
}


class SeasonalTab(BaseTab):
    def __init__(self, main_window: Optional[QWidget] = None):
        super().__init__(main_window)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        ctrl_row = QHBoxLayout()
        self.lbl_seasonal_hint = QLabel("请选择左侧构件查看季节性波动分析，或选择多个构件进行对比")
        self.lbl_seasonal_hint.setStyleSheet("color: #666; padding: 5px;")
        ctrl_row.addWidget(self.lbl_seasonal_hint)
        ctrl_row.addStretch()
        self.btn_seasonal_multi = create_button(
            "多构件对比分析",
            self._on_seasonal_multi_analysis
        )
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
        setup_table_style(self.seasonal_table)
        self.seasonal_table.setMaximumHeight(180)
        layout.addWidget(self.seasonal_table)

    def refresh(self) -> None:
        self._refresh_seasonal()

    def _refresh_seasonal(self) -> None:
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
        data = []

        for s in seasons:
            d = season_stats.get(s, {})
            ratio = d.get("high_ratio", 0)
            data.append([
                s,
                str(d.get("count", 0)),
                str(d.get("avg", 0)),
                str(d.get("max", 0)),
                str(d.get("min", 0)),
                f"{ratio}%",
            ])

        color_rules = {
            2: lambda x: RISK_COLORS["高风险"] if float(x) > threshold else None,
            3: lambda x: RISK_COLORS["高风险"] if float(x) > threshold else None,
            5: lambda x: (RISK_COLORS["高风险"] if float(x.rstrip('%')) > 30
                          else RISK_COLORS["中风险"] if float(x.rstrip('%')) > 10 else None),
        }

        populate_table(self.seasonal_table, headers, data, color_rules)
        resize_table_columns(self.seasonal_table, "stretch")

    def _on_seasonal_multi_analysis(self) -> None:
        dlg = ComponentSelectionDialog(self)
        if dlg.exec():
            ids = dlg.get_selected_ids()
            if len(ids) < 2:
                show_warning(self, "提示", "请至少选择2个构件")
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
            data = []
            for name, d in by_comp.items():
                row = [name]
                for s in seasons:
                    s_data = d.get(s, {})
                    avg = s_data.get("avg", 0)
                    row.append(f"{avg}%" if avg else "-")
                data.append(row)

            color_rules = {}
            for col in range(1, 5):
                color_rules[col] = lambda x, t=threshold: (
                    RISK_COLORS["高风险"]
                    if x and x != "-" and float(x.rstrip('%')) > t
                    else None
                )

            populate_table(self.seasonal_table, headers, data, color_rules)
            resize_table_columns(self.seasonal_table, "stretch")
