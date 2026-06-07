from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTabWidget,
    QComboBox, QGroupBox, QFormLayout, QWidget
)
from PySide6.QtGui import QFont
from typing import Optional
import os
from datetime import datetime

from app.ui.tabs.base_tab import BaseTab
from app.common import (
    message_utils, ui_utils
)
from app.db.database import (
    BuildingRepository, DefectRepository, WorkOrderRepository,
    MaintenanceResourceRepository, ReportArchiveRepository
)
from app.services import PerformanceService
from app.ui.chart_widget import ChartWidget


PERIOD_OPTIONS = ["最近一周", "最近一月", "最近三月", "最近一年", "全部"]


class ReportTab(BaseTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_summary_tab(), "📊 综合汇总")
        self.tabs.addTab(self._create_performance_tab(), "📈 闭环绩效")
        self.tabs.addTab(self._create_effect_tab(), "🎯 处置效果")
        self.tabs.addTab(self._create_resource_tab(), "💰 资源统计")
        layout.addWidget(self.tabs)

    def _create_summary_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        form_box = QGroupBox("报告参数")
        form = QFormLayout()
        self.report_summary_building = QComboBox()
        self.report_summary_building.addItem("全部建筑", None)
        for b in BuildingRepository.get_all():
            self.report_summary_building.addItem(b["name"], b["id"])
        form.addRow("统计范围:", self.report_summary_building)

        self.report_summary_period = QComboBox()
        self.report_summary_period.addItems(PERIOD_OPTIONS)
        form.addRow("统计周期:", self.report_summary_period)
        form_box.setLayout(form)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        btn_gen_summary = QPushButton("📤 生成综合汇总报告")
        btn_gen_summary.setStyleSheet("background-color: #2980b9; color: white; padding: 8px 20px; font-weight: bold;")
        btn_gen_summary.clicked.connect(self._on_generate_summary_report)
        btn_row.addWidget(btn_gen_summary)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.summary_chart = ChartWidget()
        self.summary_chart.setMinimumHeight(400)
        layout.addWidget(self.summary_chart, stretch=1)

        self.summary_chart.plot_defect_status_pie()
        return w

    def _create_performance_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        form_box = QGroupBox("报告参数")
        form = QFormLayout()
        self.report_perf_building = QComboBox()
        self.report_perf_building.addItem("全部建筑", None)
        for b in BuildingRepository.get_all():
            self.report_perf_building.addItem(b["name"], b["id"])
        form.addRow("统计范围:", self.report_perf_building)
        form_box.setLayout(form)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        btn_gen_perf = QPushButton("📤 生成闭环绩效报告")
        btn_gen_perf.setStyleSheet("background-color: #8e44ad; color: white; padding: 8px 20px; font-weight: bold;")
        btn_gen_perf.clicked.connect(self._on_generate_performance_report)
        btn_row.addWidget(btn_gen_perf)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.perf_chart = ChartWidget()
        self.perf_chart.setMinimumHeight(400)
        layout.addWidget(self.perf_chart, stretch=1)

        self.perf_chart.plot_closed_loop_performance()
        return w

    def _create_effect_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        form_box = QGroupBox("报告参数")
        form = QFormLayout()
        self.report_eff_building = QComboBox()
        self.report_eff_building.addItem("全部建筑", None)
        for b in BuildingRepository.get_all():
            self.report_eff_building.addItem(b["name"], b["id"])
        form.addRow("统计范围:", self.report_eff_building)
        form_box.setLayout(form)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        btn_gen_eff = QPushButton("📤 生成处置效果报告")
        btn_gen_eff.setStyleSheet("background-color: #27ae60; color: white; padding: 8px 20px; font-weight: bold;")
        btn_gen_eff.clicked.connect(self._on_generate_effect_report)
        btn_row.addWidget(btn_gen_eff)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.eff_chart = ChartWidget()
        self.eff_chart.setMinimumHeight(400)
        layout.addWidget(self.eff_chart, stretch=1)

        self.eff_chart.plot_effect_distribution_pie()
        return w

    def _create_resource_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        form_box = QGroupBox("报告参数")
        form = QFormLayout()
        self.report_res_building = QComboBox()
        self.report_res_building.addItem("全部建筑", None)
        for b in BuildingRepository.get_all():
            self.report_res_building.addItem(b["name"], b["id"])
        form.addRow("统计范围:", self.report_res_building)

        self.report_res_period = QComboBox()
        self.report_res_period.addItems(PERIOD_OPTIONS)
        form.addRow("统计周期:", self.report_res_period)
        form_box.setLayout(form)
        layout.addWidget(form_box)

        btn_row = QHBoxLayout()
        btn_gen_res = QPushButton("📤 生成资源统计报告")
        btn_gen_res.setStyleSheet("background-color: #e67e22; color: white; padding: 8px 20px; font-weight: bold;")
        btn_gen_res.clicked.connect(self._on_generate_resource_report)
        btn_row.addWidget(btn_gen_res)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.res_chart = ChartWidget()
        self.res_chart.setMinimumHeight(400)
        layout.addWidget(self.res_chart, stretch=1)

        self.res_chart.plot_resource_cost_pie()
        return w

    def refresh(self) -> None:
        self.summary_chart.plot_defect_status_pie()
        self.perf_chart.plot_closed_loop_performance()
        self.eff_chart.plot_effect_distribution_pie()
        self.res_chart.plot_resource_cost_pie()

    def _save_and_archive(self, content: str, filename: str, report_type: str,
                          building_id: Optional[int], description: str) -> None:
        filepath = os.path.join(os.path.expanduser("~"), "Documents", filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        try:
            ReportArchiveRepository.create(
                report_type=report_type,
                file_name=filename,
                file_path=filepath,
                file_size=os.path.getsize(filepath),
                building_id=building_id,
                description=description
            )
        except Exception:
            pass

        message_utils.show_info(self, "成功", f"报告已导出到:\n{filepath}")
        self.notify_data_changed()

    def _on_generate_summary_report(self) -> None:
        try:
            building_id = self.report_summary_building.currentData()
            period = self.report_summary_period.currentText()
            bldg = BuildingRepository.get_by_id(building_id) if building_id else None
            bldg_name = bldg.get("name", "全部建筑") if bldg else "全部建筑"

            filename = f"综合汇总报告_{bldg_name}_{period}_{datetime.now().strftime('%Y%m%d')}.txt"

            defects = DefectRepository.get_all()
            if building_id:
                defects = [d for d in defects if d.get("building_id") == building_id]
            workorders = WorkOrderRepository.get_all()
            if building_id:
                workorders = [w for w in workorders if w.get("building_id") == building_id]
            resources = MaintenanceResourceRepository.get_all()
            if building_id:
                resources = [r for r in resources if r.get("building_id") == building_id]
            perf = PerformanceService.calculate_closed_loop_performance(building_id)
            eff = PerformanceService.calculate_effectiveness(building_id)

            total_cost = sum((r.get("quantity", 0) or 0) * (r.get("unit_price", 0) or 0) for r in resources)

            report = f"""{'='*60}
古建筑木构件含水率智能预警系统 - 综合汇总报告
{'='*60}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
统计范围: {bldg_name}
统计周期: {period}

一、病害概览
{'-'*40}
  病害总数: {len(defects)}
  已闭环数: {perf.get('closed', 0)}
  闭环率: {perf.get('closed_loop_rate', 0):.1f}%
  平均处理周期: {perf.get('avg_cycle_days', 0):.1f}天
  返工数: {perf.get('rework_count', 0)}

二、风险分布
{'-'*40}
"""
            sev_count = {}
            for d in defects:
                s = d.get("severity", "未知")
                sev_count[s] = sev_count.get(s, 0) + 1
            for s, c in sev_count.items():
                report += f"  {s}: {c}\n"

            report += f"""
三、维修资源消耗
{'-'*40}
  资源记录数: {len(resources)}
  总成本: ¥{total_cost:,.2f}

四、处置效果
{'-'*40}
  已评估数: {eff.get('total_evaluated', 0)}
  平均改善率: {eff.get('avg_improvement_rate', 0):.1f}%

{'='*60}
报告结束
"""
            self._save_and_archive(report, filename, "综合汇总报告", building_id, f"{bldg_name} - {period}综合汇总")
        except Exception as e:
            message_utils.show_error(self, "失败", f"生成失败: {str(e)}")

    def _on_generate_performance_report(self) -> None:
        try:
            from app.db.database import ComponentRepository
            building_id = self.report_perf_building.currentData()
            bldg = BuildingRepository.get_by_id(building_id) if building_id else None
            bldg_name = bldg.get("name", "全部建筑") if bldg else "全部建筑"

            filename = f"闭环绩效报告_{bldg_name}_{datetime.now().strftime('%Y%m%d')}.txt"

            data = PerformanceService.calculate_closed_loop_performance(building_id)

            report = f"""{'='*60}
古建筑木构件含水率智能预警系统 - 闭环绩效报告
{'='*60}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
统计范围: {bldg_name}

总体绩效
{'-'*40}
  病害总数: {data.get('total', 0)}
  已闭环数: {data.get('closed', 0)}
  闭环率: {data.get('closed_loop_rate', 0):.1f}%
  平均处理周期: {data.get('avg_cycle_days', 0):.1f}天
  返工数: {data.get('rework_count', 0)}

按建筑统计
{'-'*40}
"""
            for bid, stats in data.get("by_building", {}).items():
                b = BuildingRepository.get_by_id(bid)
                name = b.get("name", str(bid)) if b else str(bid)
                report += f"  {name}: 闭环率 {stats.get('closed_loop_rate', 0):.1f}%, 平均周期 {stats.get('avg_cycle_days', 0):.1f}天\n"

            report += f"\n按构件类型统计\n{'-'*40}\n"
            for cid, stats in data.get("by_component", {}).items():
                c = ComponentRepository.get_by_id(cid)
                name = c.get("name", str(cid)) if c else str(cid)
                report += f"  {name}: 闭环率 {stats.get('closed_loop_rate', 0):.1f}%, 平均周期 {stats.get('avg_cycle_days', 0):.1f}天\n"

            report += f"\n按病害类型统计\n{'-'*40}\n"
            for dtype, stats in data.get("by_type", {}).items():
                report += f"  {dtype}: 闭环率 {stats.get('closed_loop_rate', 0):.1f}%, 平均周期 {stats.get('avg_cycle_days', 0):.1f}天\n"

            report += f"\n{'='*60}\n报告结束\n"

            self._save_and_archive(report, filename, "闭环绩效报告", building_id, f"{bldg_name} - 闭环绩效分析")
        except Exception as e:
            message_utils.show_error(self, "失败", f"生成失败: {str(e)}")

    def _on_generate_effect_report(self) -> None:
        try:
            building_id = self.report_eff_building.currentData()
            bldg = BuildingRepository.get_by_id(building_id) if building_id else None
            bldg_name = bldg.get("name", "全部建筑") if bldg else "全部建筑"

            filename = f"处置效果报告_{bldg_name}_{datetime.now().strftime('%Y%m%d')}.txt"

            data = PerformanceService.calculate_effectiveness(building_id)

            report = f"""{'='*60}
古建筑木构件含水率智能预警系统 - 处置效果报告
{'='*60}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
统计范围: {bldg_name}

总体效果
{'-'*40}
  已评估数: {data.get('total_evaluated', 0)}
  平均改善率: {data.get('avg_improvement_rate', 0):.1f}%

效果分布
{'-'*40}
"""
            for level, count in data.get("effect_distribution", {}).items():
                report += f"  {level}: {count}\n"

            report += f"\n按病害类型统计\n{'-'*40}\n"
            for dtype, stats in data.get("by_type", {}).items():
                report += f"  {dtype}: 平均改善率 {stats.get('avg_improvement_rate', 0):.1f}%, 样本数 {stats.get('count', 0)}\n"

            report += f"\n改善率最佳 Top 5\n{'-'*40}\n"
            for i, d in enumerate(data.get("top_5", [])[:5], 1):
                b = BuildingRepository.get_by_id(d.get("building_id")) or {}
                report += f"  {i}. {d.get('defect_type', '')} @ {b.get('name', '')} - 改善率 {d.get('improvement_rate', 0):.1f}% (效果: {d.get('effect_level', '')})\n"

            report += f"\n改善率较低 Bottom 5\n{'-'*40}\n"
            for i, d in enumerate(data.get("bottom_5", [])[:5], 1):
                b = BuildingRepository.get_by_id(d.get("building_id")) or {}
                report += f"  {i}. {d.get('defect_type', '')} @ {b.get('name', '')} - 改善率 {d.get('improvement_rate', 0):.1f}% (效果: {d.get('effect_level', '')})\n"

            report += f"\n{'='*60}\n报告结束\n"

            self._save_and_archive(report, filename, "处置效果报告", building_id, f"{bldg_name} - 处置效果分析")
        except Exception as e:
            message_utils.show_error(self, "失败", f"生成失败: {str(e)}")

    def _on_generate_resource_report(self) -> None:
        try:
            building_id = self.report_res_building.currentData()
            period = self.report_res_period.currentText()
            bldg = BuildingRepository.get_by_id(building_id) if building_id else None
            bldg_name = bldg.get("name", "全部建筑") if bldg else "全部建筑"

            filename = f"资源统计报告_{bldg_name}_{period}_{datetime.now().strftime('%Y%m%d')}.txt"

            resources = MaintenanceResourceRepository.get_all()
            if building_id:
                resources = [r for r in resources if r.get("building_id") == building_id]

            stats = MaintenanceResourceRepository.get_statistics()
            by_type = stats.get("by_type", {})
            by_building = stats.get("by_building", {})

            total_cost = sum((r.get("quantity", 0) or 0) * (r.get("unit_price", 0) or 0) for r in resources)

            report = f"""{'='*60}
古建筑木构件含水率智能预警系统 - 资源统计报告
{'='*60}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
统计范围: {bldg_name}
统计周期: {period}

总体资源消耗
{'-'*40}
  资源记录总数: {len(resources)}
  总成本: ¥{total_cost:,.2f}

按资源类型统计
{'-'*40}
"""
            for rtype, s in by_type.items():
                report += f"  {rtype}: {s.get('total_count', 0)}条, 成本 ¥{s.get('total_cost', 0):,.2f}\n"

            report += f"\n按建筑统计\n{'-'*40}\n"
            for bid, s in by_building.items():
                b = BuildingRepository.get_by_id(bid)
                name = b.get("name", str(bid)) if b else str(bid)
                report += f"  {name}: {s.get('total_count', 0)}条, 成本 ¥{s.get('total_cost', 0):,.2f}\n"

            report += f"\n资源明细\n{'-'*40}\n"
            for r in resources[:50]:
                b = BuildingRepository.get_by_id(r.get("building_id")) or {}
                tc = (r.get("quantity", 0) or 0) * (r.get("unit_price", 0) or 0)
                report += f"  [{r.get('resource_type', '')}] {r.get('resource_name', '')} x{r.get('quantity', 0)}{r.get('unit', '')} - ¥{tc:,.2f} @ {b.get('name', '')}\n"

            if len(resources) > 50:
                report += f"  ... (共{len(resources)}条，仅显示前50条)\n"

            report += f"\n{'='*60}\n报告结束\n"

            self._save_and_archive(report, filename, "资源统计报告", building_id, f"{bldg_name} - {period}资源统计")
        except Exception as e:
            message_utils.show_error(self, "失败", f"生成失败: {str(e)}")
