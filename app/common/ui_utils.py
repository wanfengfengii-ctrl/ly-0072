from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QPushButton, QComboBox
from PySide6.QtGui import QColor
from typing import List, Tuple, Any, Callable, Optional


RISK_COLORS = {
    "高风险": QColor(231, 76, 60),
    "中风险": QColor(230, 126, 34),
    "正常": QColor(46, 204, 113),
}


def get_risk_color(risk_level: str) -> QColor:
    return RISK_COLORS.get(risk_level, QColor(0, 0, 0))


def create_stat_card(title: str, value: str, color: str) -> QFrame:
    card = QFrame()
    card.setFrameStyle(QFrame.StyledPanel)
    card.setStyleSheet(f"""
        QFrame {{ background: white; border-radius: 8px; padding: 12px;
                 border-left: 4px solid {color}; }}
    """)
    layout = QVBoxLayout(card)
    title_label = QLabel(title)
    title_label.setStyleSheet("color: #666; font-size: 12px;")
    value_label = QLabel(value)
    value_label.setObjectName("value")
    value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
    layout.addWidget(title_label)
    layout.addWidget(value_label)
    return card


def update_stat_card(card: QFrame, value: str) -> None:
    value_label = card.findChild(QLabel, "value")
    if value_label:
        value_label.setText(value)


def create_button(text: str, callback: Callable, style_sheet: str = None) -> QPushButton:
    btn = QPushButton(text)
    if callback:
        btn.clicked.connect(callback)
    if style_sheet:
        btn.setStyleSheet(style_sheet)
    return btn


def populate_combo(combo: QComboBox, items: List[Tuple[str, Any]], add_all: bool = True) -> None:
    combo.clear()
    if add_all:
        combo.addItem("全部", None)
    for text, data in items:
        combo.addItem(text, data)
