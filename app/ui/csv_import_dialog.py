from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox,
    QGroupBox, QTextEdit, QHeaderView, QSplitter, QComboBox,
    QProgressDialog
)
from PySide6.QtCore import Qt
from typing import Optional, Dict, Any

from app.logic.csv_importer import (
    preview_csv, validate_csv_content, import_valid_records,
    generate_csv_template
)
from app.db.database import ComponentRepository


class CSVImportDialog(QDialog):
    def __init__(self, parent=None, default_component_id: int = None):
        super().__init__(parent)
        self.setWindowTitle("CSV数据导入")
        self.resize(900, 650)
        self.file_path = None
        self.preview_data = None
        self.validation_result = None
        self._init_ui()
        self._load_components(default_component_id)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("目标构件:"))
        self.component_combo = QComboBox()
        self.component_combo.setMinimumWidth(300)
        top_layout.addWidget(self.component_combo)
        top_layout.addStretch()

        self.template_btn = QPushButton("下载CSV模板")
        self.template_btn.clicked.connect(self._on_download_template)
        top_layout.addWidget(self.template_btn)

        self.select_btn = QPushButton("选择CSV文件...")
        self.select_btn.clicked.connect(self._on_select_file)
        top_layout.addWidget(self.select_btn)

        layout.addLayout(top_layout)

        self.file_info_label = QLabel("尚未选择文件")
        self.file_info_label.setStyleSheet("color: #666;")
        layout.addWidget(self.file_info_label)

        splitter = QSplitter(Qt.Vertical)

        preview_group = QGroupBox("数据预览")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_table = QTableWidget()
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        preview_layout.addWidget(self.preview_table)
        splitter.addWidget(preview_group)

        error_group = QGroupBox("错误信息")
        error_layout = QVBoxLayout(error_group)
        self.error_text = QTextEdit()
        self.error_text.setReadOnly(True)
        self.error_text.setStyleSheet("color: #c0392b;")
        error_layout.addWidget(self.error_text)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("font-weight: bold; padding: 5px;")
        error_layout.addWidget(self.summary_label)
        splitter.addWidget(error_group)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        btn_layout = QHBoxLayout()
        self.validate_btn = QPushButton("校验数据")
        self.validate_btn.clicked.connect(self._on_validate)
        self.validate_btn.setEnabled(False)
        btn_layout.addWidget(self.validate_btn)

        btn_layout.addStretch()

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.import_btn = QPushButton("导入有效数据")
        self.import_btn.clicked.connect(self._on_import)
        self.import_btn.setEnabled(False)
        self.import_btn.setStyleSheet(
            "background-color: #27ae60; color: white; padding: 6px 16px;"
        )
        btn_layout.addWidget(self.import_btn)

        layout.addLayout(btn_layout)

    def _load_components(self, default_id: int = None):
        components = ComponentRepository.get_all()
        self.component_combo.clear()
        for c in components:
            label = f"[{c.get('building_name', '')}] {c['code']} - {c['name']}"
            self.component_combo.addItem(label, c["id"])

        if default_id:
            for i in range(self.component_combo.count()):
                if self.component_combo.itemData(i) == default_id:
                    self.component_combo.setCurrentIndex(i)
                    break

    def _on_download_template(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存CSV模板", "检测数据模板.csv", "CSV文件 (*.csv)"
        )
        if file_path:
            try:
                content = generate_csv_template()
                with open(file_path, "w", encoding="utf-8-sig") as f:
                    f.write(content)
                QMessageBox.information(self, "成功", f"模板已保存到:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存模板失败: {str(e)}")

    def _on_select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择CSV文件", "", "CSV文件 (*.csv);;所有文件 (*)"
        )
        if file_path:
            self.file_path = file_path
            self._load_preview()

    def _load_preview(self):
        self.preview_data = preview_csv(self.file_path)
        self.error_text.clear()
        self.import_btn.setEnabled(False)

        info = (f"文件: {self.preview_data['file_name']}  |  "
                f"大小: {self.preview_data['file_size']} 字节  |  "
                f"数据行数: {self.preview_data['total_rows']}")
        self.file_info_label.setText(info)
        self.file_info_label.setStyleSheet("color: #333;")

        headers = self.preview_data["headers"]
        data = self.preview_data["preview_data"]
        self.preview_table.setRowCount(len(data))
        self.preview_table.setColumnCount(len(headers))
        self.preview_table.setHorizontalHeaderLabels(headers)

        for row_idx, row in enumerate(data):
            for col_idx, cell in enumerate(row):
                item = QTableWidgetItem(str(cell))
                self.preview_table.setItem(row_idx, col_idx, item)

        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        if self.preview_data["errors"]:
            self.error_text.append("=== 严重错误 ===")
            for err in self.preview_data["errors"]:
                self.error_text.append(f"• {err}")
            self.validate_btn.setEnabled(False)
        else:
            missing = self.preview_data["missing_columns"]
            if missing:
                self.error_text.append(f"警告: 缺少必要列 {missing}")
                self.validate_btn.setEnabled(False)
            else:
                self.validate_btn.setEnabled(True)
                mapping = self.preview_data["column_mapping"]
                self.error_text.append(f"列映射: {mapping}")

    def _on_validate(self):
        if not self.file_path:
            QMessageBox.warning(self, "提示", "请先选择CSV文件")
            return

        component_id = self.component_combo.currentData()
        if not component_id:
            QMessageBox.warning(self, "提示", "请选择目标构件")
            return

        self.validation_result = validate_csv_content(
            self.file_path, component_id
        )

        self.error_text.clear()
        if self.validation_result["errors"]:
            self.error_text.append("=== 校验错误 ===")
            for err in self.validation_result["errors"]:
                self.error_text.append(f"• {err}")
            self.import_btn.setEnabled(False)
            return

        if self.validation_result["error_rows"]:
            self.error_text.append(f"=== 错误行 ({self.validation_result['error_count']} 行) ===")
            for err_row in self.validation_result["error_rows"]:
                self.error_text.append(
                    f"第 {err_row['row_num']} 行: {'; '.join(err_row['errors'])}"
                )

        summary = (
            f"总行数: {self.validation_result['total_count']}  |  "
            f"<span style='color: #27ae60;'>有效: {self.validation_result['valid_count']}</span>  |  "
            f"<span style='color: #c0392b;'>错误: {self.validation_result['error_count']}</span>  |  "
            f"<span style='color: #f39c12;'>重复: {self.validation_result['duplicate_count']}</span>"
        )
        self.summary_label.setText(summary)

        if self.validation_result["valid_count"] > 0:
            self.import_btn.setEnabled(True)
        else:
            self.import_btn.setEnabled(False)
            QMessageBox.warning(self, "校验结果", "没有可导入的有效数据")

    def _on_import(self):
        if not self.validation_result or not self.validation_result["valid_rows"]:
            QMessageBox.warning(self, "提示", "请先校验数据")
            return

        component_id = self.component_combo.currentData()
        reply = QMessageBox.question(
            self, "确认导入",
            f"确定要导入 {self.validation_result['valid_count']} 条有效数据吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            count = import_valid_records(component_id, self.validation_result["valid_rows"])
            QMessageBox.information(
                self, "导入成功",
                f"成功导入 {count} 条检测记录！\n"
                f"跳过错误/重复数据: {self.validation_result['error_count'] + self.validation_result['duplicate_count']} 条"
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"导入过程出错: {str(e)}")
