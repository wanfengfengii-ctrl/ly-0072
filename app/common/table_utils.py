from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PySide6.QtGui import QBrush, QColor
from PySide6.QtCore import Qt
from typing import List, Any, Dict, Optional
import csv


def populate_table(table: QTableWidget, headers: List[str], data: List[List[Any]], color_rules: Dict = None) -> None:
    table.clear()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(data))
    for row_idx, row_data in enumerate(data):
        for col_idx, cell_data in enumerate(row_data):
            item = QTableWidgetItem(str(cell_data) if cell_data is not None else "")
            item.setTextAlignment(Qt.AlignCenter)
            if color_rules and col_idx in color_rules:
                rule = color_rules[col_idx]
                if callable(rule):
                    color = rule(cell_data)
                    if color:
                        item.setForeground(QBrush(color))
                elif isinstance(rule, dict) and cell_data in rule:
                    item.setForeground(QBrush(rule[cell_data]))
            table.setItem(row_idx, col_idx, item)


def setup_table_style(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.verticalHeader().setVisible(False)


def get_selected_row_id(table: QTableWidget, id_col: int = 0) -> Optional[int]:
    row = table.currentRow()
    if row < 0:
        return None
    item = table.item(row, id_col)
    if not item:
        return None
    try:
        return int(item.text())
    except (ValueError, TypeError):
        return None


def get_selected_row_ids(table: QTableWidget, id_col: int = 0) -> List[int]:
    ids: List[int] = []
    for item in table.selectedItems():
        row = item.row()
        cell = table.item(row, id_col)
        if cell:
            try:
                val = int(cell.text())
                if val not in ids:
                    ids.append(val)
            except (ValueError, TypeError):
                continue
    return ids


def resize_table_columns(table: QTableWidget, mode: str = 'resize_to_contents') -> None:
    if mode == 'stretch':
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    elif mode == 'resize_to_contents':
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    elif mode == 'interactive':
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)


def export_table_to_csv(table: QTableWidget, file_path: str) -> None:
    with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        headers = []
        for col in range(table.columnCount()):
            item = table.horizontalHeaderItem(col)
            headers.append(item.text() if item else "")
        writer.writerow(headers)
        for row in range(table.rowCount()):
            row_data = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                row_data.append(item.text() if item else "")
            writer.writerow(row_data)
