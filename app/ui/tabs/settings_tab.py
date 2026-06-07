from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTabWidget,
    QGroupBox, QFormLayout, QDoubleSpinBox, QSpinBox, QLineEdit,
    QFileDialog, QTextEdit, QWidget
)
from PySide6.QtGui import QFont
from typing import Callable, Optional

from app.ui.tabs.base_tab import BaseTab
from app.common import (
    message_utils, ui_utils
)
from app.db.database import SettingsRepository


class SettingsTab(BaseTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._load_settings()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_threshold_tab(), "⚙ 阈值设置")
        self.tabs.addTab(self._create_help_tab(), "ℹ 使用说明")
        layout.addWidget(self.tabs)

    def _create_threshold_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        threshold_box = QGroupBox("📊 预警阈值配置")
        threshold_form = QFormLayout()

        self.moisture_threshold = QDoubleSpinBox()
        self.moisture_threshold.setRange(0, 100)
        self.moisture_threshold.setDecimals(1)
        self.moisture_threshold.setSingleStep(0.5)
        self.moisture_threshold.setSuffix(" %")
        self.moisture_threshold.setToolTip("含水率超过此阈值时标记为高风险并触发异常预警")
        threshold_form.addRow("含水率预警阈值:", self.moisture_threshold)

        self.consecutive_count = QSpinBox()
        self.consecutive_count.setRange(1, 30)
        self.consecutive_count.setSuffix(" 次")
        self.consecutive_count.setToolTip("连续多少次检测超过阈值才判定为异常（减少误报）")
        threshold_form.addRow("连续异常判定次数:", self.consecutive_count)

        self.default_inspection_interval = QSpinBox()
        self.default_inspection_interval.setRange(1, 365)
        self.default_inspection_interval.setSuffix(" 天")
        self.default_inspection_interval.setToolTip("新建巡检计划时的默认巡检周期")
        threshold_form.addRow("默认巡检周期:", self.default_inspection_interval)

        self.default_reminder_days = QSpinBox()
        self.default_reminder_days.setRange(0, 30)
        self.default_reminder_days.setSuffix(" 天")
        self.default_reminder_days.setToolTip("新建巡检计划时默认提前多少天提醒")
        threshold_form.addRow("默认提前提醒天数:", self.default_reminder_days)

        threshold_box.setLayout(threshold_form)
        layout.addWidget(threshold_box)

        archive_box = QGroupBox("📁 报告归档设置")
        archive_form = QFormLayout()

        archive_row = QHBoxLayout()
        self.archive_dir_edit = QLineEdit()
        self.archive_dir_edit.setReadOnly(True)
        archive_row.addWidget(self.archive_dir_edit)
        self.btn_choose_dir = QPushButton("浏览...")
        self.btn_choose_dir.clicked.connect(self._on_choose_archive_dir)
        archive_row.addWidget(self.btn_choose_dir)
        archive_container = QWidget()
        archive_container.setLayout(archive_row)
        archive_form.addRow("归档目录:", archive_container)

        archive_box.setLayout(archive_form)
        layout.addWidget(archive_box)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_save = QPushButton("💾 保存设置")
        self.btn_save.setStyleSheet("background-color: #2980b9; color: white; padding: 8px 24px; font-weight: bold;")
        self.btn_save.clicked.connect(self._on_save_settings)
        btn_row.addWidget(self.btn_save)

        self.btn_reset = QPushButton("↩ 恢复默认")
        self.btn_reset.clicked.connect(self._on_reset_settings)
        btn_row.addWidget(self.btn_reset)
        layout.addLayout(btn_row)

        layout.addStretch()
        return w

    def _create_help_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setStyleSheet("font-size: 13px; padding: 10px;")
        help_text.setHtml("""
        <h2>🏯 古建筑木构件含水率智能预警系统 - 使用说明</h2>

        <h3>📋 模块简介</h3>
        <ul>
            <li><b>建筑档案</b>：管理古建筑及木构件基本信息，支持批量 CSV 导入</li>
            <li><b>含水率检测</b>：录入和查看历次检测数据，自动标记超标记录</li>
            <li><b>病害处置</b>：登记病害、派发工单、跟踪整改、验收评估全流程闭环管理</li>
            <li><b>巡检计划</b>：制定巡检计划，到期自动提醒</li>
            <li><b>异常复核</b>：人工复核系统识别的异常数据，确认或标记为误报</li>
            <li><b>报告归档</b>：查看和管理所有已生成的报告</li>
            <li><b>角色协同</b>：管理系统用户、角色与权限分配</li>
            <li><b>综合报告</b>：生成汇总、绩效、效果、资源四大类报告</li>
            <li><b>系统设置</b>：预警阈值、默认参数等全局配置</li>
        </ul>

        <h3>🔔 工作流程</h3>
        <ol>
            <li>录入/导入<b>建筑与构件</b>基础档案</li>
            <li>定期录入<b>含水率检测</b>数据</li>
            <li>系统自动识别超标记录，可在「异常复核」中通过「自动扫描」批量生成待复核项</li>
            <li>人工复核后，确认为风险的进入<b>病害处置</b>流程</li>
            <li>病害 → 工单 → 整改 → 验收 → 评估，形成闭环</li>
            <li>通过「综合报告」导出各类统计报告，自动归档</li>
        </ol>

        <h3>💡 小技巧</h3>
        <ul>
            <li>表格<b>双击</b>行可快速进入编辑模式</li>
            <li>选中多行后点击批量操作按钮可一次处理多条记录</li>
            <li>所有生成的报告可在「报告归档」中随时查阅和打开</li>
            <li>建议定期在「综合报告」中查看闭环绩效，及时发现处理瓶颈</li>
        </ul>

        <h3>📞 技术支持</h3>
        <p>如遇使用问题，请联系系统管理员。</p>
        """)
        layout.addWidget(help_text)
        return w

    def _load_settings(self) -> None:
        self.moisture_threshold.setValue(SettingsRepository.get_moisture_threshold())
        self.consecutive_count.setValue(SettingsRepository.get_consecutive_count())
        self.default_inspection_interval.setValue(SettingsRepository.get_default_inspection_interval())
        self.default_reminder_days.setValue(SettingsRepository.get_default_reminder_days())
        self.archive_dir_edit.setText(SettingsRepository.get_archive_directory() or "")

    def _on_choose_archive_dir(self) -> None:
        start_dir = self.archive_dir_edit.text() or ""
        directory = QFileDialog.getExistingDirectory(self, "选择归档目录", start_dir)
        if directory:
            self.archive_dir_edit.setText(directory)

    def _on_save_settings(self) -> None:
        try:
            SettingsRepository.set_moisture_threshold(self.moisture_threshold.value())
            SettingsRepository.set_consecutive_count(self.consecutive_count.value())
            SettingsRepository.set_default_inspection_interval(self.default_inspection_interval.value())
            SettingsRepository.set_default_reminder_days(self.default_reminder_days.value())
            if self.archive_dir_edit.text():
                SettingsRepository.set_archive_directory(self.archive_dir_edit.text())

            message_utils.show_info(self, "成功", "系统设置已保存，所有标签页将刷新数据")
            self.notify_data_changed()
        except Exception as e:
            message_utils.show_error(self, "错误", f"保存失败: {str(e)}")

    def _on_reset_settings(self) -> None:
        if not message_utils.confirm_action(self, "确定要将所有设置恢复为默认值吗？", "恢复默认"):
            return
        try:
            SettingsRepository.set("moisture_threshold", "18.0")
            SettingsRepository.set("consecutive_count", "3")
            SettingsRepository.set("default_inspection_interval", "30")
            SettingsRepository.set("default_reminder_days", "7")
            self._load_settings()
            message_utils.show_info(self, "成功", "已恢复默认设置")
            self.notify_data_changed()
        except Exception as e:
            message_utils.show_error(self, "错误", f"恢复失败: {str(e)}")

    def refresh(self) -> None:
        self._load_settings()
