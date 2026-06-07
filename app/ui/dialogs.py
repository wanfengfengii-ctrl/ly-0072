from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QTextEdit, QDialogButtonBox,
    QComboBox, QLabel, QVBoxLayout, QMessageBox
)
from PySide6.QtCore import Qt
from typing import Optional, Dict, Any

from app.db.database import BuildingRepository, ComponentRepository


COMPONENT_TYPES = ["梁", "柱", "斗拱", "枋", "檩", "椽", "其他"]


class BuildingDialog(QDialog):
    def __init__(self, parent=None, building: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.building = building
        self.setWindowTitle("编辑建筑档案" if building else "新增建筑档案")
        self.resize(450, 350)
        self._init_ui()
        if building:
            self._load_data(building)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("请输入建筑名称")
        form.addRow("建筑名称 *:", self.name_edit)

        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("请输入建筑位置")
        form.addRow("建筑位置:", self.location_edit)

        self.built_year_edit = QLineEdit()
        self.built_year_edit.setPlaceholderText("如: 明永乐年间 或 1420年")
        form.addRow("建造年代:", self.built_year_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("请输入建筑描述信息...")
        self.desc_edit.setMinimumHeight(100)
        form.addRow("描述:", self.desc_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_data(self, building: Dict[str, Any]):
        self.name_edit.setText(building.get("name", ""))
        self.location_edit.setText(building.get("location", ""))
        self.built_year_edit.setText(building.get("built_year", ""))
        self.desc_edit.setPlainText(building.get("description", ""))

    def _on_accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入建筑名称")
            return
        self.accept()

    def get_data(self) -> Dict[str, str]:
        return {
            "name": self.name_edit.text().strip(),
            "location": self.location_edit.text().strip(),
            "built_year": self.built_year_edit.text().strip(),
            "description": self.desc_edit.toPlainText().strip()
        }


class ComponentDialog(QDialog):
    def __init__(self, parent=None, buildings=None,
                 component: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.component = component
        self.buildings = buildings or []
        self.setWindowTitle("编辑构件档案" if component else "新增构件档案")
        self.resize(500, 450)
        self._init_ui()
        if component:
            self._load_data(component)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.building_combo = QComboBox()
        for b in self.buildings:
            self.building_combo.addItem(b["name"], b["id"])
        form.addRow("所属建筑 *:", self.building_combo)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("如: L-001, Z-001")
        form.addRow("构件编号 *:", self.code_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("如: 前檐明间东大梁")
        form.addRow("构件名称 *:", self.name_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(COMPONENT_TYPES)
        form.addRow("构件类型 *:", self.type_combo)

        self.material_edit = QLineEdit()
        self.material_edit.setPlaceholderText("如: 楠木、松木")
        form.addRow("材质:", self.material_edit)

        self.position_edit = QLineEdit()
        self.position_edit.setPlaceholderText("如: 前檐明间东侧")
        form.addRow("所在位置:", self.position_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("请输入构件描述信息...")
        self.desc_edit.setMinimumHeight(80)
        form.addRow("描述:", self.desc_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_data(self, component: Dict[str, Any]):
        building_id = component.get("building_id")
        for i in range(self.building_combo.count()):
            if self.building_combo.itemData(i) == building_id:
                self.building_combo.setCurrentIndex(i)
                break

        self.code_edit.setText(component.get("code", ""))
        self.name_edit.setText(component.get("name", ""))

        comp_type = component.get("component_type", "")
        idx = self.type_combo.findText(comp_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

        self.material_edit.setText(component.get("material", ""))
        self.position_edit.setText(component.get("position", ""))
        self.desc_edit.setPlainText(component.get("description", ""))

    def _on_accept(self):
        if self.building_combo.currentIndex() < 0:
            QMessageBox.warning(self, "提示", "请选择所属建筑")
            return
        if not self.code_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入构件编号")
            return
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "提示", "请输入构件名称")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "building_id": self.building_combo.currentData(),
            "code": self.code_edit.text().strip(),
            "name": self.name_edit.text().strip(),
            "component_type": self.type_combo.currentText(),
            "material": self.material_edit.text().strip(),
            "position": self.position_edit.text().strip(),
            "description": self.desc_edit.toPlainText().strip()
        }
