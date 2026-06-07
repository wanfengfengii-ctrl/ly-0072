from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from app.ui.tabs.base_tab import BaseTab
from app.ui.chart_widget import ChartWidget
from app.common import create_button
from app.db.database import SettingsRepository
from app.logic.advanced_analytics import predict_risk_trend


RISK_COLORS = {
    "高风险": QColor(231, 76, 60),
    "中风险": QColor(230, 126, 34),
    "正常": QColor(46, 204, 113),
}


class PredictionTab(BaseTab):
    def __init__(self, main_window: Optional[QWidget] = None):
        super().__init__(main_window)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("预测天数:"))
        self.prediction_days = QSpinBox()
        self.prediction_days.setRange(30, 365)
        self.prediction_days.setValue(90)
        self.prediction_days.setSuffix(" 天")
        self.prediction_days.valueChanged.connect(self._refresh_prediction)
        ctrl_row.addWidget(self.prediction_days)
        ctrl_row.addStretch()
        self.btn_refresh_prediction = create_button(
            "重新预测",
            self._refresh_prediction
        )
        ctrl_row.addWidget(self.btn_refresh_prediction)
        layout.addLayout(ctrl_row)

        self.prediction_summary = QLabel("请选择构件进行风险趋势预测")
        self.prediction_summary.setFont(QFont("", 11))
        self.prediction_summary.setStyleSheet(
            "padding: 10px; background: #ecf0f1; border-radius: 4px;"
        )
        self.prediction_summary.setWordWrap(True)
        layout.addWidget(self.prediction_summary)

        self.prediction_chart = ChartWidget()
        layout.addWidget(self.prediction_chart, stretch=1)

        self.prediction_detail = QLabel("")
        self.prediction_detail.setStyleSheet(
            "padding: 10px; background: white; border-radius: 4px;"
        )
        self.prediction_detail.setWordWrap(True)
        layout.addWidget(self.prediction_detail)

    def refresh(self) -> None:
        self._refresh_prediction()

    def _refresh_prediction(self) -> None:
        threshold = SettingsRepository.get_moisture_threshold()

        if not self.current_component_id:
            self.prediction_summary.setText("请在左侧选择构件进行风险趋势预测")
            self.prediction_detail.setText("")
            return

        forecast_days = self.prediction_days.value()
        result = predict_risk_trend(self.current_component_id, forecast_days)

        if not result.get("has_data", False):
            self.prediction_summary.setText(
                result.get("recommendation", "数据不足，无法预测")
            )
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

        regression: Dict[str, Any] = result.get("regression", {})
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
