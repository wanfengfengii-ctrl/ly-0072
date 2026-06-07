from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QTextEdit,
    QComboBox, QDateEdit, QSpinBox, QPushButton, QDialogButtonBox, QLabel,
    QMessageBox, QCheckBox, QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QGroupBox, QRadioButton,
    QButtonGroup, QSplitter, QWidget, QFileDialog
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor
from typing import Optional, Dict, Any, List
from datetime import datetime
import os

from app.db.database import (
    BuildingRepository, ComponentRepository, InspectionPlanRepository,
    AnomalyReviewRepository, SettingsRepository, ReportArchiveRepository
)
from app.logic.advanced_analytics import get_all_components_for_comparison


PLAN_TYPES = ["常规巡检", "季度巡检", "年度巡检", "专项巡检", "雨后复检", "风险跟踪"]
PLAN_STATUSES = ["待执行", "已提醒", "执行中", "已完成", "已取消"]
REVIEW_STATUSES = ["待复核", "复核通过", "确认为风险", "误报"]


class InspectionPlanDialog(QDialog):
    def __init__(self, parent=None, plan: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.plan = plan
        self.setWindowTitle("编辑巡检计划" if plan else "新增巡检计划")
        self.resize(500, 520)
        self._init_ui()
        if plan:
            self._load_data(plan)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.building_combo = QComboBox()
        self.building_combo.addItem("全部建筑", None)
        for b in BuildingRepository.get_all():
            self.building_combo.addItem(b["name"], b["id"])
        self.building_combo.currentIndexChanged.connect(self._on_building_changed)
        form.addRow("适用建筑:", self.building_combo)

        self.component_combo = QComboBox()
        self.component_combo.addItem("全部构件", None)
        self._on_building_changed()
        form.addRow("适用构件:", self.component_combo)

        self.plan_date = QDateEdit()
        self.plan_date.setCalendarPopup(True)
        self.plan_date.setDate(QDate.currentDate().addDays(7))
        self.plan_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("计划日期 *:", self.plan_date)

        self.plan_type_combo = QComboBox()
        self.plan_type_combo.addItems(PLAN_TYPES)
        form.addRow("计划类型 *:", self.plan_type_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItems(PLAN_STATUSES)
        form.addRow("状态:", self.status_combo)

        self.reminder_spin = QSpinBox()
        self.reminder_spin.setRange(0, 60)
        self.reminder_spin.setSuffix(" 天")
        self.reminder_spin.setValue(SettingsRepository.get_default_reminder_days())
        form.addRow("提前提醒:", self.reminder_spin)

        self.operator_edit = QLineEdit()
        self.operator_edit.setPlaceholderText("负责巡检的人员")
        form.addRow("操作人员:", self.operator_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("巡检内容、注意事项等...")
        self.desc_edit.setMinimumHeight(80)
        form.addRow("描述:", self.desc_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_building_changed(self):
        building_id = self.building_combo.currentData()
        self.component_combo.clear()
        self.component_combo.addItem("全部构件", None)
        if building_id:
            for c in ComponentRepository.get_by_building(building_id):
                self.component_combo.addItem(f"{c['code']} - {c['name']}", c["id"])
        else:
            for c in ComponentRepository.get_all():
                self.component_combo.addItem(f"{c['code']} - {c['name']}", c["id"])

    def _load_data(self, plan: Dict[str, Any]):
        building_id = plan.get("building_id")
        for i in range(self.building_combo.count()):
            if self.building_combo.itemData(i) == building_id:
                self.building_combo.setCurrentIndex(i)
                break

        component_id = plan.get("component_id")
        self._on_building_changed()
        for i in range(self.component_combo.count()):
            if self.component_combo.itemData(i) == component_id:
                self.component_combo.setCurrentIndex(i)
                break

        plan_date = plan.get("plan_date", "")
        if plan_date:
            try:
                dt = datetime.fromisoformat(plan_date.split(" ")[0])
                self.plan_date.setDate(QDate(dt.year, dt.month, dt.day))
            except Exception:
                pass

        plan_type = plan.get("plan_type", "")
        idx = self.plan_type_combo.findText(plan_type)
        if idx >= 0:
            self.plan_type_combo.setCurrentIndex(idx)

        status = plan.get("status", "")
        idx = self.status_combo.findText(status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)

        self.reminder_spin.setValue(plan.get("reminder_days", 7))
        self.operator_edit.setText(plan.get("operator", ""))
        self.desc_edit.setPlainText(plan.get("description", ""))

    def _on_accept(self):
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "building_id": self.building_combo.currentData(),
            "component_id": self.component_combo.currentData(),
            "plan_date": self.plan_date.date().toString("yyyy-MM-dd"),
            "plan_type": self.plan_type_combo.currentText(),
            "status": self.status_combo.currentText(),
            "reminder_days": self.reminder_spin.value(),
            "operator": self.operator_edit.text().strip(),
            "description": self.desc_edit.toPlainText().strip()
        }


class AnomalyReviewDialog(QDialog):
    def __init__(self, parent=None, review: Optional[Dict[str, Any]] = None,
                 record_data: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.review = review
        self.record_data = record_data
        self.setWindowTitle("异常复核")
        self.resize(550, 550)
        self._init_ui()
        if review:
            self._load_data(review)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        if self.record_data:
            info_group = QGroupBox("原始检测记录")
            info_form = QFormLayout(info_group)
            info_form.addRow("检测时间:", QLabel(self.record_data.get("measure_time", "")))
            info_form.addRow("检测位置:", QLabel(self.record_data.get("measure_position", "")))
            moisture = self.record_data.get("moisture", 0)
            moisture_label = QLabel(f"{moisture}%")
            moisture_label.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 14px;")
            info_form.addRow("含水率:", moisture_label)
            temp = self.record_data.get("temperature")
            info_form.addRow("温度:", QLabel(f"{temp}℃" if temp else "-"))
            hum = self.record_data.get("humidity")
            info_form.addRow("环境湿度:", QLabel(f"{hum}%" if hum else "-"))
            info_form.addRow("操作人员:", QLabel(self.record_data.get("operator", "") or "-"))
            info_form.addRow("备注:", QLabel(self.record_data.get("remark", "") or "-"))
            layout.addWidget(info_group)

        form_group = QGroupBox("复核信息")
        form = QFormLayout(form_group)

        self.status_combo = QComboBox()
        self.status_combo.addItems(REVIEW_STATUSES)
        form.addRow("复核结论 *:", self.status_combo)

        self.false_alarm_check = QCheckBox("标记为误报")
        form.addRow("", self.false_alarm_check)

        self.reviewer_edit = QLineEdit()
        self.reviewer_edit.setPlaceholderText("复核人员姓名")
        form.addRow("复核人员:", self.reviewer_edit)

        self.suggestion_edit = QTextEdit()
        self.suggestion_edit.setPlaceholderText("处理建议（如：加强通风、更换木材、持续跟踪等）...")
        self.suggestion_edit.setMinimumHeight(80)
        form.addRow("处理建议:", self.suggestion_edit)

        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("复核说明、现场观察情况等...")
        self.note_edit.setMinimumHeight(80)
        form.addRow("复核备注:", self.note_edit)

        layout.addWidget(form_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_data(self, review: Dict[str, Any]):
        status = review.get("review_status", "待复核")
        idx = self.status_combo.findText(status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        self.false_alarm_check.setChecked(bool(review.get("is_false_alarm", 0)))
        self.reviewer_edit.setText(review.get("reviewer", ""))
        self.suggestion_edit.setPlainText(review.get("handling_suggestion", ""))
        self.note_edit.setPlainText(review.get("review_note", ""))

    def _on_accept(self):
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "review_status": self.status_combo.currentText(),
            "reviewer": self.reviewer_edit.text().strip(),
            "review_note": self.note_edit.toPlainText().strip(),
            "is_false_alarm": 1 if self.false_alarm_check.isChecked() else 0,
            "handling_suggestion": self.suggestion_edit.toPlainText().strip()
        }


class ComponentSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择构件进行对比分析")
        self.resize(700, 500)
        self._init_ui()
        self._load_components()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("建筑筛选:"))
        self.building_filter = QComboBox()
        self.building_filter.addItem("全部", None)
        for b in BuildingRepository.get_all():
            self.building_filter.addItem(b["name"], b["id"])
        self.building_filter.currentIndexChanged.connect(self._load_components)
        filter_layout.addWidget(self.building_filter)

        filter_layout.addWidget(QLabel("类型筛选:"))
        self.type_filter = QComboBox()
        self.type_filter.addItem("全部", None)
        for t in ["梁", "柱", "斗拱", "枋", "檩", "椽", "其他"]:
            self.type_filter.addItem(t, t)
        self.type_filter.currentIndexChanged.connect(self._load_components)
        filter_layout.addWidget(self.type_filter)

        filter_layout.addWidget(QLabel("风险筛选:"))
        self.risk_filter = QComboBox()
        self.risk_filter.addItem("全部", None)
        self.risk_filter.addItem("高风险", "高风险")
        self.risk_filter.addItem("中风险", "中风险")
        self.risk_filter.addItem("正常", "正常")
        self.risk_filter.currentIndexChanged.connect(self._load_components)
        filter_layout.addWidget(self.risk_filter)

        filter_layout.addStretch()
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.clicked.connect(self._select_all)
        filter_layout.addWidget(self.btn_select_all)
        self.btn_clear_all = QPushButton("清空")
        self.btn_clear_all.clicked.connect(self._clear_all)
        filter_layout.addWidget(self.btn_clear_all)
        layout.addLayout(filter_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["选择", "构件编号", "构件名称", "类型", "建筑", "风险等级"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, stretch=1)

        tip = QLabel("提示：勾选需要对比分析的构件，建议选择同一类型或同一建筑的构件进行比较")
        tip.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(tip)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("开始对比分析")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_components(self):
        building_id = self.building_filter.currentData()
        ctype = self.type_filter.currentData()
        risk = self.risk_filter.currentData()

        components = get_all_components_for_comparison()

        if building_id:
            components = [c for c in components if c["building_id"] == building_id]
        if ctype:
            components = [c for c in components if c["component_type"] == ctype]
        if risk:
            components = [c for c in components if c["risk_level"] == risk]

        self.table.setRowCount(len(components))
        self._all_components = components

        risk_colors = {
            "高风险": QColor(231, 76, 60),
            "中风险": QColor(230, 126, 34),
            "正常": QColor(46, 204, 113)
        }

        for row, comp in enumerate(components):
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.Unchecked)
            self.table.setItem(row, 0, checkbox_item)

            self.table.setItem(row, 1, QTableWidgetItem(comp["code"]))
            self.table.setItem(row, 2, QTableWidgetItem(comp["name"]))
            self.table.setItem(row, 3, QTableWidgetItem(comp["component_type"]))
            self.table.setItem(row, 4, QTableWidgetItem(comp.get("building_name", "")))

            risk_item = QTableWidgetItem(comp["risk_level"])
            color = risk_colors.get(comp["risk_level"], QColor(0, 0, 0))
            risk_item.setForeground(color)
            risk_item.setFont(QFont("", 10, QFont.Bold))
            self.table.setItem(row, 5, risk_item)

    def _select_all(self):
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.Checked)

    def _clear_all(self):
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.Unchecked)

    def _on_accept(self):
        selected = self.get_selected_ids()
        if len(selected) < 2:
            QMessageBox.warning(self, "提示", "请至少选择2个构件进行对比分析")
            return
        self.accept()

    def get_selected_ids(self) -> List[int]:
        ids = []
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).checkState() == Qt.Checked:
                ids.append(self._all_components[row]["id"])
        return ids


class BatchExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量导出巡检报告")
        self.resize(500, 400)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        scope_group = QGroupBox("导出范围")
        scope_layout = QVBoxLayout(scope_group)

        self.rb_all = QRadioButton("全部建筑及构件")
        self.rb_all.setChecked(True)
        scope_layout.addWidget(self.rb_all)

        self.rb_building = QRadioButton("指定建筑")
        scope_layout.addWidget(self.rb_building)

        building_row = QHBoxLayout()
        building_row.addSpacing(25)
        self.building_combo = QComboBox()
        self.building_combo.addItem("请选择...", None)
        for b in BuildingRepository.get_all():
            self.building_combo.addItem(b["name"], b["id"])
        self.building_combo.setEnabled(False)
        building_row.addWidget(self.building_combo, stretch=1)
        scope_layout.addLayout(building_row)

        self.scope_group = QButtonGroup(self)
        self.scope_group.addButton(self.rb_all, 1)
        self.scope_group.addButton(self.rb_building, 2)
        self.rb_building.toggled.connect(lambda c: self.building_combo.setEnabled(c))

        layout.addWidget(scope_group)

        option_group = QGroupBox("导出选项")
        option_layout = QFormLayout(option_group)

        self.include_charts = QCheckBox("包含图表(需要浏览器支持)")
        self.include_charts.setChecked(True)
        option_layout.addRow("", self.include_charts)

        self.include_stats = QCheckBox("包含统计汇总")
        self.include_stats.setChecked(True)
        option_layout.addRow("", self.include_stats)

        self.include_risk = QCheckBox("包含风险分析详情")
        self.include_risk.setChecked(True)
        option_layout.addRow("", self.include_risk)

        layout.addWidget(option_group)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("导出目录:"))
        self.path_edit = QLineEdit()
        from app.db.database import get_db_path
        default_path = os.path.dirname(get_db_path())
        self.path_edit.setText(default_path)
        path_row.addWidget(self.path_edit, stretch=1)
        self.btn_browse = QPushButton("浏览...")
        self.btn_browse.clicked.connect(self._browse_path)
        path_row.addWidget(self.btn_browse)
        layout.addLayout(path_row)

        self.archive_check = QCheckBox("同时归档到报告历史")
        self.archive_check.setChecked(True)
        layout.addWidget(self.archive_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("开始批量导出")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择导出目录", self.path_edit.text())
        if path:
            self.path_edit.setText(path)

    def _on_accept(self):
        if self.rb_building.isChecked() and not self.building_combo.currentData():
            QMessageBox.warning(self, "提示", "请选择要导出的建筑")
            return
        if not self.path_edit.text().strip():
            QMessageBox.warning(self, "提示", "请选择导出目录")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "scope": "all" if self.rb_all.isChecked() else "building",
            "building_id": self.building_combo.currentData() if self.rb_building.isChecked() else None,
            "include_charts": self.include_charts.isChecked(),
            "include_stats": self.include_stats.isChecked(),
            "include_risk": self.include_risk.isChecked(),
            "output_dir": self.path_edit.text().strip(),
            "archive": self.archive_check.isChecked()
        }
