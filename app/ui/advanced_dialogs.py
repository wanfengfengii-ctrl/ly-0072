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
    AnomalyReviewRepository, SettingsRepository, ReportArchiveRepository,
    DefectRepository, WorkOrderRepository, RectificationTrackingRepository,
    AcceptanceRecordRepository, EffectivenessEvaluationRepository,
    DefectStatusLogRepository, UserRepository, RoleRepository,
    MaintenanceResourceRepository, DefectRecurrenceRepository,
    DEFECT_TYPES, DEFECT_SEVERITIES, DEFECT_STATUSES,
    WORK_ORDER_STATUSES, PRIORITIES, ACCEPT_RESULTS, EFFECT_LEVELS,
    USER_ROLES, PERMISSIONS, RESOURCE_TYPES, RECURRENCE_TYPES
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


class DefectDialog(QDialog):
    def __init__(self, parent=None, defect: Optional[Dict[str, Any]] = None,
                 default_component_id: int = None,
                 anomaly_review_id: int = None):
        super().__init__(parent)
        self.defect = defect
        self.default_component_id = default_component_id
        self.anomaly_review_id = anomaly_review_id
        self.setWindowTitle("编辑病害登记" if defect else "新增病害登记")
        self.resize(600, 650)
        self._init_ui()
        if defect:
            self._load_data(defect)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        form_group = QGroupBox("病害基本信息")
        form = QFormLayout(form_group)

        self.building_combo = QComboBox()
        self.building_combo.addItem("请选择...", None)
        for b in BuildingRepository.get_all():
            self.building_combo.addItem(b["name"], b["id"])
        self.building_combo.currentIndexChanged.connect(self._on_building_changed)
        form.addRow("所属建筑 *:", self.building_combo)

        self.component_combo = QComboBox()
        self.component_combo.addItem("请先选择建筑", None)
        form.addRow("所属构件 *:", self.component_combo)

        self.defect_type_combo = QComboBox()
        self.defect_type_combo.addItems(DEFECT_TYPES)
        form.addRow("病害类型 *:", self.defect_type_combo)

        self.severity_combo = QComboBox()
        self.severity_combo.addItems(DEFECT_SEVERITIES)
        self.severity_combo.setCurrentText("一般")
        form.addRow("严重程度 *:", self.severity_combo)

        self.discovery_date = QDateEdit()
        self.discovery_date.setCalendarPopup(True)
        self.discovery_date.setDate(QDate.currentDate())
        self.discovery_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("发现日期 *:", self.discovery_date)

        self.discoverer_edit = QLineEdit()
        self.discoverer_edit.setPlaceholderText("发现人姓名")
        form.addRow("发现人:", self.discoverer_edit)

        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("如：梁端东侧、柱脚北侧等")
        form.addRow("具体位置:", self.location_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("请详细描述病害情况...")
        self.desc_edit.setMinimumHeight(100)
        form.addRow("病害描述 *:", self.desc_edit)

        self.remark_edit = QTextEdit()
        self.remark_edit.setPlaceholderText("其他备注信息...")
        self.remark_edit.setMinimumHeight(60)
        form.addRow("备注:", self.remark_edit)

        if self.default_component_id:
            comp = ComponentRepository.get_by_id(self.default_component_id)
            if comp:
                for i in range(self.building_combo.count()):
                    if self.building_combo.itemData(i) == comp["building_id"]:
                        self.building_combo.setCurrentIndex(i)
                        self._on_building_changed()
                        break
                for i in range(self.component_combo.count()):
                    if self.component_combo.itemData(i) == self.default_component_id:
                        self.component_combo.setCurrentIndex(i)
                        break

        layout.addWidget(form_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_building_changed(self):
        building_id = self.building_combo.currentData()
        self.component_combo.clear()
        if building_id:
            components = ComponentRepository.get_by_building(building_id)
            if not components:
                self.component_combo.addItem("该建筑下暂无构件", None)
            for c in components:
                self.component_combo.addItem(
                    f"{c['code']} - {c['name']} ({c['component_type']})", c["id"]
                )
        else:
            self.component_combo.addItem("请先选择建筑", None)

    def _load_data(self, defect: Dict[str, Any]):
        building_id = defect.get("building_id")
        for i in range(self.building_combo.count()):
            if self.building_combo.itemData(i) == building_id:
                self.building_combo.setCurrentIndex(i)
                self._on_building_changed()
                break
        component_id = defect.get("component_id")
        for i in range(self.component_combo.count()):
            if self.component_combo.itemData(i) == component_id:
                self.component_combo.setCurrentIndex(i)
                break
        dtype = defect.get("defect_type", "")
        idx = self.defect_type_combo.findText(dtype)
        if idx >= 0:
            self.defect_type_combo.setCurrentIndex(idx)
        severity = defect.get("severity", "一般")
        idx = self.severity_combo.findText(severity)
        if idx >= 0:
            self.severity_combo.setCurrentIndex(idx)
        discovery_date = defect.get("discovery_date", "")
        if discovery_date:
            try:
                dt = datetime.fromisoformat(discovery_date.split(" ")[0])
                self.discovery_date.setDate(QDate(dt.year, dt.month, dt.day))
            except Exception:
                pass
        self.discoverer_edit.setText(defect.get("discoverer", "") or "")
        self.location_edit.setText(defect.get("location_detail", "") or "")
        self.desc_edit.setPlainText(defect.get("description", "") or "")
        self.remark_edit.setPlainText(defect.get("remark", "") or "")

    def _on_accept(self):
        if not self.component_combo.currentData():
            QMessageBox.warning(self, "提示", "请选择所属构件")
            return
        if not self.desc_edit.toPlainText().strip():
            QMessageBox.warning(self, "提示", "请填写病害描述")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_combo.currentData(),
            "defect_type": self.defect_type_combo.currentText(),
            "severity": self.severity_combo.currentText(),
            "description": self.desc_edit.toPlainText().strip(),
            "location_detail": self.location_edit.text().strip(),
            "discovery_date": self.discovery_date.date().toString("yyyy-MM-dd"),
            "discoverer": self.discoverer_edit.text().strip(),
            "remark": self.remark_edit.toPlainText().strip(),
            "anomaly_review_id": self.anomaly_review_id
        }


class WorkOrderDialog(QDialog):
    def __init__(self, parent=None, work_order: Optional[Dict[str, Any]] = None,
                 default_defect_id: int = None):
        super().__init__(parent)
        self.work_order = work_order
        self.default_defect_id = default_defect_id
        self.setWindowTitle("编辑维修工单" if work_order else "新增维修工单")
        self.resize(600, 700)
        self._init_ui()
        if work_order:
            self._load_data(work_order)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        info_group = QGroupBox("关联病害")
        info_form = QFormLayout(info_group)
        self.defect_combo = QComboBox()
        self.defect_combo.addItem("请选择病害", None)
        defects = DefectRepository.get_all()
        for d in defects:
            if d["status"] in ("待处置", "处置中") and not DefectRepository.has_open_work_order(d["id"]):
                self.defect_combo.addItem(
                    f"[{d['id']}] {d['defect_type']} - {d['component_code']} {d['component_name']}: {d['description'][:30]}",
                    d["id"]
                )
            elif self.work_order and d["id"] == self.work_order.get("defect_id"):
                self.defect_combo.addItem(
                    f"[{d['id']}] {d['defect_type']} - {d['component_code']} {d['component_name']}: {d['description'][:30]}",
                    d["id"]
                )
        info_form.addRow("关联病害 *:", self.defect_combo)
        if self.default_defect_id:
            for i in range(self.defect_combo.count()):
                if self.defect_combo.itemData(i) == self.default_defect_id:
                    self.defect_combo.setCurrentIndex(i)
                    break
        layout.addWidget(info_group)

        form_group = QGroupBox("工单信息")
        form = QFormLayout(form_group)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("如：大梁腐朽加固维修")
        form.addRow("工单标题 *:", self.title_edit)

        self.status_combo = QComboBox()
        self.status_combo.addItems(WORK_ORDER_STATUSES)
        form.addRow("工单状态:", self.status_combo)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(PRIORITIES)
        self.priority_combo.setCurrentText("中")
        form.addRow("优先级 *:", self.priority_combo)

        self.assignee_edit = QLineEdit()
        self.assignee_edit.setPlaceholderText("负责维修的人员或班组")
        form.addRow("负责人:", self.assignee_edit)

        self.assign_date = QDateEdit()
        self.assign_date.setCalendarPopup(True)
        self.assign_date.setDate(QDate.currentDate())
        self.assign_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("派工日期 *:", self.assign_date)

        self.deadline = QDateEdit()
        self.deadline.setCalendarPopup(True)
        self.deadline.setDate(QDate.currentDate().addDays(14))
        self.deadline.setDisplayFormat("yyyy-MM-dd")
        self.deadline.setSpecialValueText("")
        form.addRow("截止日期:", self.deadline)

        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("详细描述维修内容、工艺要求、技术标准等...")
        self.content_edit.setMinimumHeight(100)
        form.addRow("维修内容 *:", self.content_edit)

        self.materials_edit = QTextEdit()
        self.materials_edit.setPlaceholderText("所需材料清单，如：楠木 0.5m³、环氧树脂 5kg 等...")
        self.materials_edit.setMinimumHeight(60)
        form.addRow("所需材料:", self.materials_edit)

        self.operator_edit = QLineEdit()
        self.operator_edit.setPlaceholderText("创建人/操作人")
        form.addRow("操作人:", self.operator_edit)

        layout.addWidget(form_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_data(self, wo: Dict[str, Any]):
        defect_id = wo.get("defect_id")
        for i in range(self.defect_combo.count()):
            if self.defect_combo.itemData(i) == defect_id:
                self.defect_combo.setCurrentIndex(i)
                break
        self.defect_combo.setEnabled(False)
        self.title_edit.setText(wo.get("title", "") or "")
        status = wo.get("status", "")
        idx = self.status_combo.findText(status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        priority = wo.get("priority", "中")
        idx = self.priority_combo.findText(priority)
        if idx >= 0:
            self.priority_combo.setCurrentIndex(idx)
        self.assignee_edit.setText(wo.get("assignee", "") or "")
        assign_date = wo.get("assign_date", "")
        if assign_date:
            try:
                dt = datetime.fromisoformat(assign_date.split(" ")[0])
                self.assign_date.setDate(QDate(dt.year, dt.month, dt.day))
            except Exception:
                pass
        deadline = wo.get("deadline", "")
        if deadline:
            try:
                dt = datetime.fromisoformat(deadline.split(" ")[0])
                self.deadline.setDate(QDate(dt.year, dt.month, dt.day))
            except Exception:
                pass
        self.content_edit.setPlainText(wo.get("work_content", "") or "")
        self.materials_edit.setPlainText(wo.get("required_materials", "") or "")
        self.operator_edit.setText(wo.get("operator", "") or "")

    def _on_accept(self):
        if not self.defect_combo.currentData():
            QMessageBox.warning(self, "提示", "请选择关联病害")
            return
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "提示", "请填写工单标题")
            return
        if not self.content_edit.toPlainText().strip():
            QMessageBox.warning(self, "提示", "请填写维修内容")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "defect_id": self.defect_combo.currentData(),
            "title": self.title_edit.text().strip(),
            "status": self.status_combo.currentText(),
            "priority": self.priority_combo.currentText(),
            "assignee": self.assignee_edit.text().strip(),
            "assign_date": self.assign_date.date().toString("yyyy-MM-dd"),
            "deadline": self.deadline.date().toString("yyyy-MM-dd"),
            "work_content": self.content_edit.toPlainText().strip(),
            "required_materials": self.materials_edit.toPlainText().strip(),
            "operator": self.operator_edit.text().strip()
        }


class RectificationTrackDialog(QDialog):
    def __init__(self, parent=None, work_order_id: int = None):
        super().__init__(parent)
        self.work_order_id = work_order_id
        self.setWindowTitle("整改跟踪记录")
        self.resize(550, 500)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        if self.work_order_id:
            wo = WorkOrderRepository.get_by_id(self.work_order_id)
            if wo:
                info_label = QLabel(
                    f"工单: {wo.get('order_no', '')} - {wo.get('title', '')}"
                )
                info_label.setStyleSheet("font-weight: bold; padding: 8px; background: #ecf0f1; border-radius: 4px;")
                layout.addWidget(info_label)

        form = QFormLayout()

        self.track_date = QDateEdit()
        self.track_date.setCalendarPopup(True)
        self.track_date.setDate(QDate.currentDate())
        self.track_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("跟踪日期 *:", self.track_date)

        self.tracker_edit = QLineEdit()
        self.tracker_edit.setPlaceholderText("跟踪人员姓名")
        form.addRow("跟踪人:", self.tracker_edit)

        self.progress_edit = QTextEdit()
        self.progress_edit.setPlaceholderText("当前整改进展、已完成工作等...")
        self.progress_edit.setMinimumHeight(100)
        form.addRow("进展情况 *:", self.progress_edit)

        self.problems_edit = QTextEdit()
        self.problems_edit.setPlaceholderText("遇到的问题和困难...")
        self.problems_edit.setMinimumHeight(60)
        form.addRow("存在问题:", self.problems_edit)

        self.next_steps_edit = QTextEdit()
        self.next_steps_edit.setPlaceholderText("下一步工作计划...")
        self.next_steps_edit.setMinimumHeight(60)
        form.addRow("下一步计划:", self.next_steps_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        if not self.progress_edit.toPlainText().strip():
            QMessageBox.warning(self, "提示", "请填写进展情况")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "work_order_id": self.work_order_id,
            "track_date": self.track_date.date().toString("yyyy-MM-dd"),
            "tracker": self.tracker_edit.text().strip(),
            "progress": self.progress_edit.toPlainText().strip(),
            "problems": self.problems_edit.toPlainText().strip(),
            "next_steps": self.next_steps_edit.toPlainText().strip()
        }


class AcceptanceDialog(QDialog):
    def __init__(self, parent=None, work_order_id: int = None):
        super().__init__(parent)
        self.work_order_id = work_order_id
        self.setWindowTitle("验收记录")
        self.resize(550, 550)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        if self.work_order_id:
            wo = WorkOrderRepository.get_by_id(self.work_order_id)
            if wo:
                info_label = QLabel(
                    f"工单: {wo.get('order_no', '')} - {wo.get('title', '')}\n"
                    f"构件: {wo.get('component_code', '')} {wo.get('component_name', '')}"
                )
                info_label.setStyleSheet("font-weight: bold; padding: 8px; background: #ecf0f1; border-radius: 4px;")
                info_label.setWordWrap(True)
                layout.addWidget(info_label)

        form = QFormLayout()

        self.accept_date = QDateEdit()
        self.accept_date.setCalendarPopup(True)
        self.accept_date.setDate(QDate.currentDate())
        self.accept_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("验收日期 *:", self.accept_date)

        self.result_combo = QComboBox()
        self.result_combo.addItems(ACCEPT_RESULTS)
        form.addRow("验收结果 *:", self.result_combo)

        self.person_edit = QLineEdit()
        self.person_edit.setPlaceholderText("验收人员姓名")
        form.addRow("验收人:", self.person_edit)

        self.items_edit = QTextEdit()
        self.items_edit.setPlaceholderText("检查项目清单及检查结果...")
        self.items_edit.setMinimumHeight(80)
        form.addRow("检查项目:", self.items_edit)

        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("验收意见、说明等...")
        self.note_edit.setMinimumHeight(80)
        form.addRow("验收备注:", self.note_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        if not self.person_edit.text().strip():
            QMessageBox.warning(self, "提示", "请填写验收人")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "work_order_id": self.work_order_id,
            "accept_date": self.accept_date.date().toString("yyyy-MM-dd"),
            "accept_result": self.result_combo.currentText(),
            "accept_person": self.person_edit.text().strip(),
            "inspection_items": self.items_edit.toPlainText().strip(),
            "accept_note": self.note_edit.toPlainText().strip()
        }


class EffectivenessEvalDialog(QDialog):
    def __init__(self, parent=None, defect_id: int = None):
        super().__init__(parent)
        self.defect_id = defect_id
        self.setWindowTitle("效果评估")
        self.resize(600, 650)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        if self.defect_id:
            defect = DefectRepository.get_by_id(self.defect_id)
            if defect:
                info_label = QLabel(
                    f"病害: [{defect.get('id', '')}] {defect.get('defect_type', '')} - "
                    f"{defect.get('component_code', '')} {defect.get('component_name', '')}\n"
                    f"描述: {defect.get('description', '')[:60]}"
                )
                info_label.setStyleSheet("font-weight: bold; padding: 8px; background: #ecf0f1; border-radius: 4px;")
                info_label.setWordWrap(True)
                layout.addWidget(info_label)

        form_group = QGroupBox("评估信息")
        form = QFormLayout(form_group)

        self.eval_date = QDateEdit()
        self.eval_date.setCalendarPopup(True)
        self.eval_date.setDate(QDate.currentDate())
        self.eval_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("评估日期 *:", self.eval_date)

        self.effect_combo = QComboBox()
        self.effect_combo.addItems(EFFECT_LEVELS)
        self.effect_combo.setCurrentText("良好")
        form.addRow("总体效果 *:", self.effect_combo)

        self.evaluator_edit = QLineEdit()
        self.evaluator_edit.setPlaceholderText("评估人员姓名")
        form.addRow("评估人:", self.evaluator_edit)

        layout.addWidget(form_group)

        moisture_group = QGroupBox("含水率对比（维修前后）")
        moisture_form = QFormLayout(moisture_group)

        self.moisture_before = QDoubleSpinBox()
        self.moisture_before.setRange(0, 100)
        self.moisture_before.setDecimals(1)
        self.moisture_before.setSingleStep(0.5)
        self.moisture_before.setSuffix(" %")
        self.moisture_before.setSpecialValueText("未填写")
        moisture_form.addRow("维修前含水率:", self.moisture_before)

        self.moisture_after = QDoubleSpinBox()
        self.moisture_after.setRange(0, 100)
        self.moisture_after.setDecimals(1)
        self.moisture_after.setSingleStep(0.5)
        self.moisture_after.setSuffix(" %")
        self.moisture_after.setSpecialValueText("未填写")
        moisture_form.addRow("维修后含水率:", self.moisture_after)

        layout.addWidget(moisture_group)

        risk_group = QGroupBox("风险等级对比")
        risk_form = QFormLayout(risk_group)

        self.risk_before_combo = QComboBox()
        self.risk_before_combo.addItems(["", "高风险", "中风险", "正常"])
        risk_form.addRow("维修前风险:", self.risk_before_combo)

        self.risk_after_combo = QComboBox()
        self.risk_after_combo.addItems(["", "高风险", "中风险", "正常"])
        risk_form.addRow("维修后风险:", self.risk_after_combo)

        layout.addWidget(risk_group)

        quality_group = QGroupBox("质量评价")
        quality_form = QFormLayout(quality_group)

        self.durability_combo = QComboBox()
        self.durability_combo.addItems([""] + EFFECT_LEVELS)
        quality_form.addRow("耐久性:", self.durability_combo)

        self.aesthetic_combo = QComboBox()
        self.aesthetic_combo.addItems([""] + EFFECT_LEVELS)
        quality_form.addRow("美观度:", self.aesthetic_combo)

        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("综合评价说明、建议后续跟踪措施等...")
        self.note_edit.setMinimumHeight(80)
        quality_form.addRow("评估备注:", self.note_edit)

        layout.addWidget(quality_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        if not self.evaluator_edit.text().strip():
            QMessageBox.warning(self, "提示", "请填写评估人")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        moisture_before = self.moisture_before.value()
        moisture_after = self.moisture_after.value()
        return {
            "defect_id": self.defect_id,
            "eval_date": self.eval_date.date().toString("yyyy-MM-dd"),
            "overall_effect": self.effect_combo.currentText(),
            "evaluator": self.evaluator_edit.text().strip(),
            "moisture_before": moisture_before if moisture_before > 0 else None,
            "moisture_after": moisture_after if moisture_after > 0 else None,
            "risk_level_before": self.risk_before_combo.currentText() or None,
            "risk_level_after": self.risk_after_combo.currentText() or None,
            "durability": self.durability_combo.currentText() or None,
            "aesthetic": self.aesthetic_combo.currentText() or None,
            "eval_note": self.note_edit.toPlainText().strip()
        }


class DefectDetailDialog(QDialog):
    def __init__(self, parent=None, defect_id: int = None):
        super().__init__(parent)
        self.defect_id = defect_id
        self.setWindowTitle("病害详情 - 闭环管理全流程")
        self.resize(800, 700)
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.detail_tabs = QTabWidget()

        self.info_tab = QWidget()
        self._init_info_tab()
        self.detail_tabs.addTab(self.info_tab, "📋 基本信息")

        self.work_order_tab = QWidget()
        self._init_work_order_tab()
        self.detail_tabs.addTab(self.work_order_tab, "🔧 维修工单")

        self.tracking_tab = QWidget()
        self._init_tracking_tab()
        self.detail_tabs.addTab(self.tracking_tab, "📝 整改跟踪")

        self.acceptance_tab = QWidget()
        self._init_acceptance_tab()
        self.detail_tabs.addTab(self.acceptance_tab, "✅ 验收记录")

        self.eval_tab = QWidget()
        self._init_eval_tab()
        self.detail_tabs.addTab(self.eval_tab, "📊 效果评估")

        self.log_tab = QWidget()
        self._init_log_tab()
        self.detail_tabs.addTab(self.log_tab, "📜 状态流转日志")

        layout.addWidget(self.detail_tabs)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _init_info_tab(self):
        layout = QVBoxLayout(self.info_tab)
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        layout.addWidget(self.info_text)

    def _init_work_order_tab(self):
        layout = QVBoxLayout(self.work_order_tab)
        self.wo_text = QTextEdit()
        self.wo_text.setReadOnly(True)
        layout.addWidget(self.wo_text)

    def _init_tracking_tab(self):
        layout = QVBoxLayout(self.work_order_tab)
        layout = QVBoxLayout(self.tracking_tab)
        self.tracking_table = QTableWidget()
        self.tracking_table.setAlternatingRowColors(True)
        self.tracking_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tracking_table.verticalHeader().setVisible(False)
        self.tracking_table.setColumnCount(5)
        self.tracking_table.setHorizontalHeaderLabels(
            ["跟踪日期", "跟踪人", "进展", "存在问题", "下一步计划"]
        )
        self.tracking_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.tracking_table)

    def _init_acceptance_tab(self):
        layout = QVBoxLayout(self.acceptance_tab)
        self.accept_text = QTextEdit()
        self.accept_text.setReadOnly(True)
        layout.addWidget(self.accept_text)

    def _init_eval_tab(self):
        layout = QVBoxLayout(self.eval_tab)
        self.eval_text = QTextEdit()
        self.eval_text.setReadOnly(True)
        layout.addWidget(self.eval_text)

    def _init_log_tab(self):
        layout = QVBoxLayout(self.log_tab)
        self.log_table = QTableWidget()
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setColumnCount(5)
        self.log_table.setHorizontalHeaderLabels(
            ["时间", "原状态", "新状态", "操作人", "变更说明"]
        )
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.log_table)

    def _load_data(self):
        if not self.defect_id:
            return
        defect = DefectRepository.get_by_id(self.defect_id)
        if not defect:
            return

        sev_colors = {"轻微": "#27ae60", "一般": "#f39c12", "严重": "#e67e22", "危急": "#e74c3c"}
        sev_color = sev_colors.get(defect.get("severity", "一般"), "#333")

        info_html = f"""
        <h3 style="color: #2c3e50;">病害基本信息</h3>
        <table style="width:100%; border-collapse: collapse;">
            <tr><td style="padding:8px; background:#f8f9fa; width:120px;"><b>病害ID</b></td>
                <td style="padding:8px;">{defect.get('id', '')}</td></tr>
            <tr><td style="padding:8px; background:#f8f9fa;"><b>病害类型</b></td>
                <td style="padding:8px;">{defect.get('defect_type', '')}</td></tr>
            <tr><td style="padding:8px; background:#f8f9fa;"><b>严重程度</b></td>
                <td style="padding:8px; color:{sev_color}; font-weight:bold;">{defect.get('severity', '')}</td></tr>
            <tr><td style="padding:8px; background:#f8f9fa;"><b>当前状态</b></td>
                <td style="padding:8px; font-weight:bold;">{defect.get('status', '')}</td></tr>
            <tr><td style="padding:8px; background:#f8f9fa;"><b>所属建筑</b></td>
                <td style="padding:8px;">{defect.get('building_name', '')}</td></tr>
            <tr><td style="padding:8px; background:#f8f9fa;"><b>所属构件</b></td>
                <td style="padding:8px;">{defect.get('component_code', '')} - {defect.get('component_name', '')} ({defect.get('component_type', '')})</td></tr>
            <tr><td style="padding:8px; background:#f8f9fa;"><b>发现日期</b></td>
                <td style="padding:8px;">{defect.get('discovery_date', '')}</td></tr>
            <tr><td style="padding:8px; background:#f8f9fa;"><b>发现人</b></td>
                <td style="padding:8px;">{defect.get('discoverer', '') or '-'}</td></tr>
            <tr><td style="padding:8px; background:#f8f9fa;"><b>具体位置</b></td>
                <td style="padding:8px;">{defect.get('location_detail', '') or '-'}</td></tr>
            <tr><td style="padding:8px; background:#f8f9fa;"><b>病害描述</b></td>
                <td style="padding:8px;">{defect.get('description', '')}</td></tr>
            <tr><td style="padding:8px; background:#f8f9fa;"><b>备注</b></td>
                <td style="padding:8px;">{defect.get('remark', '') or '-'}</td></tr>
            <tr><td style="padding:8px; background:#f8f9fa;"><b>创建时间</b></td>
                <td style="padding:8px;">{defect.get('created_at', '')[:19]}</td></tr>
        </table>
        """
        self.info_text.setHtml(info_html)

        work_orders = WorkOrderRepository.get_all(defect_id=self.defect_id)
        if work_orders:
            wo = work_orders[0]
            wo_html = f"""
            <h3 style="color: #2c3e50;">维修工单信息</h3>
            <table style="width:100%; border-collapse: collapse;">
                <tr><td style="padding:8px; background:#f8f9fa; width:120px;"><b>工单编号</b></td>
                    <td style="padding:8px;">{wo.get('order_no', '')}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>工单标题</b></td>
                    <td style="padding:8px;">{wo.get('title', '')}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>工单状态</b></td>
                    <td style="padding:8px; font-weight:bold;">{wo.get('status', '')}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>优先级</b></td>
                    <td style="padding:8px;">{wo.get('priority', '')}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>负责人</b></td>
                    <td style="padding:8px;">{wo.get('assignee', '') or '-'}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>派工日期</b></td>
                    <td style="padding:8px;">{wo.get('assign_date', '')}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>截止日期</b></td>
                    <td style="padding:8px;">{wo.get('deadline', '') or '-'}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>维修内容</b></td>
                    <td style="padding:8px;">{wo.get('work_content', '')}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>所需材料</b></td>
                    <td style="padding:8px;">{wo.get('required_materials', '') or '-'}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>完成时间</b></td>
                    <td style="padding:8px;">{wo.get('completed_at', '')[:19] if wo.get('completed_at') else '-'}</td></tr>
            </table>
            """
            self.wo_text.setHtml(wo_html)

            tracks = RectificationTrackingRepository.get_by_work_order(wo["id"])
            self.tracking_table.setRowCount(len(tracks))
            for row, t in enumerate(tracks):
                self.tracking_table.setItem(row, 0, QTableWidgetItem(t.get("track_date", "")[:10]))
                self.tracking_table.setItem(row, 1, QTableWidgetItem(t.get("tracker", "") or "-"))
                self.tracking_table.setItem(row, 2, QTableWidgetItem(t.get("progress", "") or ""))
                self.tracking_table.setItem(row, 3, QTableWidgetItem(t.get("problems", "") or "-"))
                self.tracking_table.setItem(row, 4, QTableWidgetItem(t.get("next_steps", "") or "-"))
        else:
            self.wo_text.setHtml("<p style='color:#888; text-align:center; padding:40px;'>暂无关联维修工单</p>")

        accept = AcceptanceRecordRepository.get_by_defect(self.defect_id)
        if accept:
            accept_html = f"""
            <h3 style="color: #2c3e50;">验收记录</h3>
            <table style="width:100%; border-collapse: collapse;">
                <tr><td style="padding:8px; background:#f8f9fa; width:120px;"><b>工单编号</b></td>
                    <td style="padding:8px;">{accept.get('order_no', '')}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>验收日期</b></td>
                    <td style="padding:8px;">{accept.get('accept_date', '')}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>验收结果</b></td>
                    <td style="padding:8px; font-weight:bold; color:{'#27ae60' if accept.get('accept_result') in ('合格', '基本合格') else '#e74c3c'};">
                        {accept.get('accept_result', '')}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>验收人</b></td>
                    <td style="padding:8px;">{accept.get('accept_person', '')}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>检查项目</b></td>
                    <td style="padding:8px;">{accept.get('inspection_items', '') or '-'}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>验收备注</b></td>
                    <td style="padding:8px;">{accept.get('accept_note', '') or '-'}</td></tr>
            </table>
            """
            self.accept_text.setHtml(accept_html)
        else:
            self.accept_text.setHtml("<p style='color:#888; text-align:center; padding:40px;'>暂无验收记录</p>")

        eval_data = EffectivenessEvaluationRepository.get_by_defect(self.defect_id)
        if eval_data:
            imp_color = "#27ae60" if (eval_data.get("moisture_improvement") or 0) > 0 else "#e74c3c"
            eval_html = f"""
            <h3 style="color: #2c3e50;">效果评估</h3>
            <table style="width:100%; border-collapse: collapse;">
                <tr><td style="padding:8px; background:#f8f9fa; width:140px;"><b>评估日期</b></td>
                    <td style="padding:8px;">{eval_data.get('eval_date', '')}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>总体效果</b></td>
                    <td style="padding:8px; font-weight:bold;">{eval_data.get('overall_effect', '')}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>评估人</b></td>
                    <td style="padding:8px;">{eval_data.get('evaluator', '')}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>维修前含水率</b></td>
                    <td style="padding:8px;">{eval_data.get('moisture_before', '') or '-'} %</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>维修后含水率</b></td>
                    <td style="padding:8px;">{eval_data.get('moisture_after', '') or '-'} %</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>含水率改善率</b></td>
                    <td style="padding:8px; color:{imp_color}; font-weight:bold;">
                        {eval_data.get('moisture_improvement', '') or '-'} %</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>维修前风险</b></td>
                    <td style="padding:8px;">{eval_data.get('risk_level_before', '') or '-'}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>维修后风险</b></td>
                    <td style="padding:8px;">{eval_data.get('risk_level_after', '') or '-'}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>耐久性</b></td>
                    <td style="padding:8px;">{eval_data.get('durability', '') or '-'}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>美观度</b></td>
                    <td style="padding:8px;">{eval_data.get('aesthetic', '') or '-'}</td></tr>
                <tr><td style="padding:8px; background:#f8f9fa;"><b>评估备注</b></td>
                    <td style="padding:8px;">{eval_data.get('eval_note', '') or '-'}</td></tr>
            </table>
            """
            self.eval_text.setHtml(eval_html)
        else:
            self.eval_text.setHtml("<p style='color:#888; text-align:center; padding:40px;'>暂无效果评估记录</p>")

        logs = DefectStatusLogRepository.get_by_defect(self.defect_id)
        self.log_table.setRowCount(len(logs))
        for row, log in enumerate(logs):
            self.log_table.setItem(row, 0, QTableWidgetItem(log.get("created_at", "")[:19]))
            self.log_table.setItem(row, 1, QTableWidgetItem(log.get("from_status", "") or "-"))
            to_item = QTableWidgetItem(log.get("to_status", ""))
            to_item.setFont(QFont("", 10, QFont.Bold))
            self.log_table.setItem(row, 2, to_item)
            self.log_table.setItem(row, 3, QTableWidgetItem(log.get("operator", "") or "-"))
            self.log_table.setItem(row, 4, QTableWidgetItem(log.get("change_note", "") or "-"))


class UserDialog(QDialog):
    def __init__(self, parent=None, user: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle("编辑用户" if user else "新增用户")
        self.resize(480, 400)
        self._init_ui()
        if user:
            self._load_data(user)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("登录用户名，唯一")
        form.addRow("用户名 *:", self.username_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("至少6位")
        form.addRow("密码 *:", self.password_edit)

        self.realname_edit = QLineEdit()
        form.addRow("真实姓名 *:", self.realname_edit)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("可选")
        form.addRow("邮箱:", self.email_edit)

        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("可选")
        form.addRow("电话:", self.phone_edit)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["active", "inactive"])
        form.addRow("状态:", self.status_combo)

        layout.addLayout(form)

        role_group = QGroupBox("分配角色")
        role_layout = QVBoxLayout(role_group)
        self.role_list = QListWidget()
        self.role_list.setSelectionMode(QAbstractItemView.MultiSelection)
        for role in RoleRepository.get_all():
            item = QListWidgetItem(f"{role['name']} - {role.get('description', '')}")
            item.setData(Qt.UserRole, role["id"])
            self.role_list.addItem(item)
        role_layout.addWidget(self.role_list)
        layout.addWidget(role_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_data(self, user: Dict[str, Any]):
        self.username_edit.setText(user.get("username", ""))
        self.username_edit.setReadOnly(True)
        self.realname_edit.setText(user.get("real_name", ""))
        self.email_edit.setText(user.get("email", "") or "")
        self.phone_edit.setText(user.get("phone", "") or "")
        status = user.get("status", "active")
        idx = self.status_combo.findText(status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)

        user_roles = UserRepository.get_roles(user["id"])
        role_ids = [r["id"] for r in user_roles]
        for i in range(self.role_list.count()):
            item = self.role_list.item(i)
            if item.data(Qt.UserRole) in role_ids:
                item.setSelected(True)

    def _on_accept(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        real_name = self.realname_edit.text().strip()
        if not username:
            QMessageBox.warning(self, "提示", "请输入用户名")
            return
        if not self.user and not password:
            QMessageBox.warning(self, "提示", "请输入密码")
            return
        if not real_name:
            QMessageBox.warning(self, "提示", "请输入真实姓名")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        selected_roles = []
        for item in self.role_list.selectedItems():
            selected_roles.append(item.data(Qt.UserRole))
        return {
            "username": self.username_edit.text().strip(),
            "password_hash": self.password_edit.text().strip(),
            "real_name": self.realname_edit.text().strip(),
            "email": self.email_edit.text().strip(),
            "phone": self.phone_edit.text().strip(),
            "status": self.status_combo.currentText(),
            "role_ids": selected_roles
        }


class ResourceDialog(QDialog):
    def __init__(self, parent=None, work_order_id: int = None,
                 resource: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.work_order_id = work_order_id
        self.resource = resource
        self.setWindowTitle("编辑维修资源" if resource else "新增维修资源")
        self.resize(450, 380)
        self._init_ui()
        if resource:
            self._load_data(resource)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.type_combo = QComboBox()
        self.type_combo.addItems(RESOURCE_TYPES)
        form.addRow("资源类型 *:", self.type_combo)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("如：防腐木材、人工工时、烘干设备等")
        form.addRow("资源名称 *:", self.name_edit)

        self.quantity_spin = QDoubleSpinBox()
        self.quantity_spin.setRange(0, 100000)
        self.quantity_spin.setDecimals(2)
        self.quantity_spin.setSingleStep(1)
        form.addRow("数量:", self.quantity_spin)

        self.unit_edit = QLineEdit()
        self.unit_edit.setPlaceholderText("如：kg、m、小时、台等")
        form.addRow("单位:", self.unit_edit)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0, 1000000)
        self.price_spin.setDecimals(2)
        self.price_spin.setPrefix("¥ ")
        self.price_spin.setSingleStep(10)
        form.addRow("单价:", self.price_spin)

        self.usage_date = QDateEdit()
        self.usage_date.setCalendarPopup(True)
        self.usage_date.setDate(QDate.currentDate())
        self.usage_date.setDisplayFormat("yyyy-MM-dd")
        form.addRow("使用日期:", self.usage_date)

        self.remark_edit = QTextEdit()
        self.remark_edit.setPlaceholderText("备注说明...")
        self.remark_edit.setMaximumHeight(60)
        form.addRow("备注:", self.remark_edit)

        layout.addLayout(form)

        self.cost_label = QLabel("预估费用: ¥ 0.00")
        self.cost_label.setFont(QFont("", 11, QFont.Bold))
        self.cost_label.setStyleSheet("color: #e74c3c; padding: 8px; background: #fef5e7; border-radius: 4px;")
        layout.addWidget(self.cost_label)

        self.quantity_spin.valueChanged.connect(self._update_cost)
        self.price_spin.valueChanged.connect(self._update_cost)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_cost(self):
        cost = self.quantity_spin.value() * self.price_spin.value()
        self.cost_label.setText(f"预估费用: ¥ {cost:,.2f}")

    def _load_data(self, resource: Dict[str, Any]):
        idx = self.type_combo.findText(resource.get("resource_type", ""))
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.name_edit.setText(resource.get("resource_name", ""))
        self.quantity_spin.setValue(float(resource.get("quantity", 0) or 0))
        self.unit_edit.setText(resource.get("unit", "") or "")
        self.price_spin.setValue(float(resource.get("unit_price", 0) or 0))
        if resource.get("usage_date"):
            try:
                dt = QDate.fromString(resource["usage_date"][:10], "yyyy-MM-dd")
                if dt.isValid():
                    self.usage_date.setDate(dt)
            except Exception:
                pass
        self.remark_edit.setPlainText(resource.get("remark", "") or "")
        self._update_cost()

    def _on_accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入资源名称")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "work_order_id": self.work_order_id,
            "resource_type": self.type_combo.currentText(),
            "resource_name": self.name_edit.text().strip(),
            "quantity": self.quantity_spin.value(),
            "unit": self.unit_edit.text().strip(),
            "unit_price": self.price_spin.value(),
            "usage_date": self.usage_date.date().toString("yyyy-MM-dd"),
            "remark": self.remark_edit.toPlainText().strip()
        }


class DefectRecurrenceDialog(QDialog):
    def __init__(self, parent=None, original_defect: Dict[str, Any] = None,
                 recurrence_defect: Dict[str, Any] = None):
        super().__init__(parent)
        self.original_defect = original_defect
        self.recurrence_defect = recurrence_defect
        self.setWindowTitle("标记病害复发关联")
        self.resize(520, 450)
        self._init_ui()
        self._load_defaults()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        info_group = QGroupBox("病害信息")
        info_layout = QFormLayout(info_group)
        self.original_label = QLabel("-")
        self.original_label.setWordWrap(True)
        info_layout.addRow("原发病害:", self.original_label)
        self.recurrence_label = QLabel("-")
        self.recurrence_label.setWordWrap(True)
        info_layout.addRow("复发病害:", self.recurrence_label)
        layout.addWidget(info_group)

        form_group = QGroupBox("关联信息")
        form = QFormLayout(form_group)

        self.type_combo = QComboBox()
        self.type_combo.addItems(RECURRENCE_TYPES)
        form.addRow("复发类型 *:", self.type_combo)

        self.days_spin = QSpinBox()
        self.days_spin.setRange(0, 3650)
        self.days_spin.setSuffix(" 天")
        form.addRow("间隔天数:", self.days_spin)

        self.cause_edit = QTextEdit()
        self.cause_edit.setPlaceholderText("分析复发的根本原因...")
        self.cause_edit.setMaximumHeight(80)
        form.addRow("根本原因:", self.cause_edit)

        self.remark_edit = QTextEdit()
        self.remark_edit.setPlaceholderText("备注说明...")
        self.remark_edit.setMaximumHeight(60)
        form.addRow("备注:", self.remark_edit)

        layout.addWidget(form_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_defaults(self):
        if self.original_defect:
            self.original_label.setText(
                f"[{self.original_defect.get('defect_type', '')}] "
                f"{self.original_defect.get('description', '')[:50]}"
            )
        if self.recurrence_defect:
            self.recurrence_label.setText(
                f"[{self.recurrence_defect.get('defect_type', '')}] "
                f"{self.recurrence_defect.get('description', '')[:50]}"
            )
            try:
                if self.original_defect and self.recurrence_defect:
                    d1 = datetime.fromisoformat(self.original_defect["discovery_date"][:10])
                    d2 = datetime.fromisoformat(self.recurrence_defect["discovery_date"][:10])
                    days = (d2 - d1).days
                    if days > 0:
                        self.days_spin.setValue(days)
                    loc1 = self.original_defect.get("location_detail", "")
                    loc2 = self.recurrence_defect.get("location_detail", "")
                    if loc1 and loc2 and loc1 == loc2:
                        idx = self.type_combo.findText("同一位置复发")
                        if idx >= 0:
                            self.type_combo.setCurrentIndex(idx)
                    elif self.original_defect.get("defect_type") == self.recurrence_defect.get("defect_type"):
                        idx = self.type_combo.findText("同类病害")
                        if idx >= 0:
                            self.type_combo.setCurrentIndex(idx)
            except Exception:
                pass

    def _on_accept(self):
        if not self.original_defect or not self.recurrence_defect:
            QMessageBox.warning(self, "提示", "缺少病害信息")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "original_defect_id": self.original_defect["id"] if self.original_defect else None,
            "recurrence_defect_id": self.recurrence_defect["id"] if self.recurrence_defect else None,
            "recurrence_type": self.type_combo.currentText(),
            "days_between": self.days_spin.value(),
            "root_cause": self.cause_edit.toPlainText().strip(),
            "remark": self.remark_edit.toPlainText().strip()
        }


class RolePermissionDialog(QDialog):
    def __init__(self, parent=None, role: Dict[str, Any] = None):
        super().__init__(parent)
        self.role = role
        self.setWindowTitle(f"角色权限管理 - {role.get('name', '')}" if role else "角色权限管理")
        self.resize(600, 500)
        self._init_ui()
        if role:
            self._load_permissions()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(f"请勾选角色「{self.role.get('name', '') if self.role else ''}」的权限：")
        info.setFont(QFont("", 11))
        layout.addWidget(info)

        self.perm_list = QListWidget()
        self.perm_list.setSelectionMode(QAbstractItemView.NoSelection)
        categories = {
            "建筑管理": ["building:create", "building:edit", "building:delete", "building:view"],
            "构件管理": ["component:create", "component:edit", "component:delete", "component:view"],
            "检测记录": ["record:create", "record:edit", "record:delete", "record:view"],
            "病害管理": ["defect:create", "defect:edit", "defect:delete", "defect:view"],
            "工单管理": ["workorder:create", "workorder:edit", "workorder:delete", "workorder:view"],
            "验收评估": ["acceptance:create", "acceptance:view", "evaluation:create", "evaluation:view"],
            "报告归档": ["report:export", "report:view"],
            "系统管理": ["user:manage", "role:manage", "settings:manage"]
        }
        perm_names = {
            "building:create": "新增建筑", "building:edit": "编辑建筑",
            "building:delete": "删除建筑", "building:view": "查看建筑",
            "component:create": "新增构件", "component:edit": "编辑构件",
            "component:delete": "删除构件", "component:view": "查看构件",
            "record:create": "录入记录", "record:edit": "编辑记录",
            "record:delete": "删除记录", "record:view": "查看记录",
            "defect:create": "登记病害", "defect:edit": "编辑病害",
            "defect:delete": "删除病害", "defect:view": "查看病害",
            "workorder:create": "创建工单", "workorder:edit": "编辑工单",
            "workorder:delete": "删除工单", "workorder:view": "查看工单",
            "acceptance:create": "验收记录", "acceptance:view": "查看验收",
            "evaluation:create": "效果评估", "evaluation:view": "查看评估",
            "report:export": "导出报告", "report:view": "查看报告",
            "user:manage": "用户管理", "role:manage": "角色管理",
            "settings:manage": "系统设置"
        }
        for cat, perms in categories.items():
            cat_item = QListWidgetItem(f"=== {cat} ===")
            cat_item.setFlags(Qt.NoItemFlags)
            cat_item.setFont(QFont("", 10, QFont.Bold))
            self.perm_list.addItem(cat_item)
            for p in perms:
                item = QListWidgetItem(f"  {perm_names.get(p, p)}")
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                item.setData(Qt.UserRole, p)
                self.perm_list.addItem(item)
        layout.addWidget(self.perm_list)

        btn_row = QHBoxLayout()
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.clicked.connect(lambda: self._set_all(True))
        btn_row.addWidget(self.btn_select_all)
        self.btn_clear_all = QPushButton("全不选")
        self.btn_clear_all.clicked.connect(lambda: self._set_all(False))
        btn_row.addWidget(self.btn_clear_all)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_all(self, checked: bool):
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self.perm_list.count()):
            item = self.perm_list.item(i)
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(state)

    def _load_permissions(self):
        if not self.role:
            return
        perms = RoleRepository.get_permissions(self.role["id"])
        for i in range(self.perm_list.count()):
            item = self.perm_list.item(i)
            if item.flags() & Qt.ItemIsUserCheckable:
                if item.data(Qt.UserRole) in perms:
                    item.setCheckState(Qt.Checked)

    def get_selected_permissions(self) -> List[str]:
        result = []
        for i in range(self.perm_list.count()):
            item = self.perm_list.item(i)
            if (item.flags() & Qt.ItemIsUserCheckable) and item.checkState() == Qt.Checked:
                result.append(item.data(Qt.UserRole))
        return result
