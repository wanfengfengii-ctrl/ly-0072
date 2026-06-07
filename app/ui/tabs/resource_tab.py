from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget,
    QPushButton, QLabel, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView
)
from PySide6.QtCore import Qt
from typing import Optional, Dict, Any, List

from app.common.table_utils import populate_table, setup_table_style, get_selected_row_id
from app.common.message_utils import show_info, show_warning, show_error, confirm_delete
from app.common.ui_utils import create_stat_card, update_stat_card

from app.services.resource_service import ResourceService
from app.db.database import RESOURCE_TYPES, BuildingRepository, MaintenanceResourceRepository
from app.ui.chart_widget import ChartWidget
from app.ui.advanced_dialogs import ResourceDialog
from app.ui.tabs.base_tab import BaseTab


class ResourceTab(BaseTab):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        stat_row = QHBoxLayout()
        self.stat_total = create_stat_card("资源记录总数", "0", "#3498db")
        self.stat_cost = create_stat_card("总成本(¥)", "0", "#e74c3c")
        self.stat_material = create_stat_card("材料类", "0", "#27ae60")
        self.stat_labor = create_stat_card("人工类", "0", "#f39c12")
        stat_row.addWidget(self.stat_total)
        stat_row.addWidget(self.stat_cost)
        stat_row.addWidget(self.stat_material)
        stat_row.addWidget(self.stat_labor)
        layout.addLayout(stat_row)

        chart_splitter = QSplitter(Qt.Horizontal)
        self.cost_chart = ChartWidget()
        self.building_chart = ChartWidget()
        chart_splitter.addWidget(self.cost_chart)
        chart_splitter.addWidget(self.building_chart)
        chart_splitter.setStretchFactor(0, 1)
        chart_splitter.setStretchFactor(1, 1)
        layout.addWidget(chart_splitter, stretch=1)

        self.detail_tabs = QTabWidget()

        res_list_widget = QWidget()
        res_list_layout = QVBoxLayout(res_list_widget)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("➕ 新增资源")
        self.btn_add.setStyleSheet("background-color: #27ae60; color: white; padding: 6px 16px;")
        btn_row.addWidget(self.btn_add)

        self.btn_edit = QPushButton("✏ 编辑")
        btn_row.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("🗑 删除")
        btn_row.addWidget(self.btn_delete)

        btn_row.addWidget(QLabel("类型筛选:"))
        self.type_filter = QComboBox()
        self.type_filter.addItem("全部", None)
        for t in RESOURCE_TYPES:
            self.type_filter.addItem(t, t)
        btn_row.addWidget(self.type_filter)

        btn_row.addWidget(QLabel("建筑筛选:"))
        self.building_filter = QComboBox()
        self.building_filter.addItem("全部", None)
        for b in BuildingRepository.get_all():
            self.building_filter.addItem(b["name"], b["id"])
        btn_row.addWidget(self.building_filter)

        btn_row.addStretch()
        self.btn_refresh = QPushButton("🔄 刷新")
        btn_row.addWidget(self.btn_refresh)

        res_list_layout.addLayout(btn_row)

        self.resource_table = QTableWidget()
        setup_table_style(self.resource_table)
        self.resource_table.doubleClicked.connect(self._on_edit)
        res_list_layout.addWidget(self.resource_table, stretch=1)

        self.detail_tabs.addTab(res_list_widget, "📋 资源明细")
        layout.addWidget(self.detail_tabs, stretch=2)

    def _setup_connections(self) -> None:
        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_refresh.clicked.connect(self.refresh)
        self.type_filter.currentIndexChanged.connect(self.refresh)
        self.building_filter.currentIndexChanged.connect(self.refresh)

    def refresh(self) -> None:
        self._refresh_list()

    def _refresh_list(self) -> None:
        try:
            res_type = self.type_filter.currentData()
            building_id = self.building_filter.currentData()

            resources = ResourceService.get_resources(
                resource_type=res_type, building_id=building_id
            )

            total_cost = ResourceService.calculate_total_cost(resources)
            mat_count = len([r for r in resources if r.get("resource_type") == "材料"])
            labor_count = len([r for r in resources if r.get("resource_type") == "人工"])

            update_stat_card(self.stat_total, str(len(resources)))
            update_stat_card(self.stat_cost, f"{total_cost:,.0f}")
            update_stat_card(self.stat_material, str(mat_count))
            update_stat_card(self.stat_labor, str(labor_count))

            headers = ["ID", "类型", "名称", "数量", "单位", "单价(¥)", "总价(¥)",
                       "关联建筑", "关联病害", "使用日期", "备注"]
            data = []

            for r in resources:
                bldg = BuildingRepository.get_by_id(r.get("building_id")) or {}
                total_price = (r.get("quantity", 0) or 0) * (r.get("unit_price", 0) or 0)
                data.append([
                    r.get("id", ""),
                    r.get("resource_type", ""),
                    r.get("resource_name", ""),
                    r.get("quantity", ""),
                    r.get("unit", ""),
                    r.get("unit_price", ""),
                    f"{total_price:.2f}",
                    bldg.get("name", ""),
                    r.get("defect_id", "") or "-",
                    (r.get("usage_date", "") or "")[:10] if r.get("usage_date") else "",
                    r.get("remark", "") or ""
                ])

            populate_table(self.resource_table, headers, data)
            self.resource_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.resource_table.horizontalHeader().setStretchLastSection(True)

            stats = ResourceService.get_statistics(building_id=building_id)
            self.cost_chart.plot_resource_cost_pie(stats)
            self.building_chart.plot_resource_by_building_bar(stats)
        except Exception as e:
            print(f"刷新维修资源出错: {e}")

    def _get_selected_id(self) -> Optional[int]:
        return get_selected_row_id(self.resource_table, 0)

    def _on_add(self) -> None:
        dlg = ResourceDialog(self)
        if dlg.exec():
            try:
                data = dlg.get_data()
                ResourceService.create_resource(**data)
                show_info(self, "成功", "资源记录已添加")
                self.refresh()
            except Exception as e:
                show_error(self, "失败", f"保存失败: {str(e)}")

    def _on_edit(self) -> None:
        rid = self._get_selected_id()
        if not rid:
            show_warning(self, "提示", "请先选择要编辑的资源记录")
            return
        res = MaintenanceResourceRepository.get_by_id(rid)
        if not res:
            return
        dlg = ResourceDialog(self, resource=res)
        if dlg.exec():
            try:
                data = dlg.get_data()
                ResourceService.update_resource(rid, **data)
                show_info(self, "成功", "资源记录已更新")
                self.refresh()
            except Exception as e:
                show_error(self, "失败", f"保存失败: {str(e)}")

    def _on_delete(self) -> None:
        rid = self._get_selected_id()
        if not rid:
            show_warning(self, "提示", "请先选择要删除的资源记录")
            return
        if confirm_delete(self, item_name="资源记录"):
            try:
                ResourceService.delete_resource(rid)
                show_info(self, "成功", "资源记录已删除")
                self.refresh()
            except Exception as e:
                show_error(self, "失败", f"删除失败: {str(e)}")
