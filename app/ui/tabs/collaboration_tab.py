from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSplitter
)
from PySide6.QtGui import QFont, QColor, QBrush
from PySide6.QtCore import Qt
from typing import List, Dict, Any, Optional

from app.ui.tabs.base_tab import BaseTab
from app.common import (
    table_utils, message_utils, ui_utils
)
from app.db.database import UserRepository, RoleRepository, PERMISSIONS, USER_ROLES
from app.ui.advanced_dialogs import UserDialog, RolePermissionDialog


class CollaborationTab(BaseTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_user_tab(), "👥 用户管理")
        self.tabs.addTab(self._create_role_tab(), "🔐 角色与权限")
        layout.addWidget(self.tabs)

    def _create_user_tab(self):
        w = QTabWidget()
        self.user_tab = QTabWidget()
        user_layout = QVBoxLayout()

        u_btn_row = QHBoxLayout()
        self.btn_add_user = QPushButton("➕ 新增用户")
        self.btn_add_user.setStyleSheet("background-color: #27ae60; color: white; padding: 6px 16px;")
        self.btn_add_user.clicked.connect(self._on_add_user)
        u_btn_row.addWidget(self.btn_add_user)

        self.btn_edit_user = QPushButton("✏ 编辑")
        self.btn_edit_user.clicked.connect(self._on_edit_user)
        u_btn_row.addWidget(self.btn_edit_user)

        self.btn_delete_user = QPushButton("🗑 删除")
        self.btn_delete_user.clicked.connect(self._on_delete_user)
        u_btn_row.addWidget(self.btn_delete_user)

        u_btn_row.addStretch()
        self.btn_refresh_users = QPushButton("🔄 刷新")
        self.btn_refresh_users.clicked.connect(self._refresh_users)
        u_btn_row.addWidget(self.btn_refresh_users)
        user_layout.addLayout(u_btn_row)

        self.user_table = QTableWidget()
        table_utils.setup_table_style(self.user_table)
        self.user_table.doubleClicked.connect(self._on_edit_user)
        user_layout.addWidget(self.user_table, stretch=1)

        user_tab = QTabWidget()
        user_widget = QTabWidget()
        container = QTabWidget()
        real_user_widget = QTabWidget()

        from PySide6.QtWidgets import QWidget as _QWidget
        user_container = _QWidget()
        user_container.setLayout(user_layout)
        return user_container

    def _create_role_tab(self):
        from PySide6.QtWidgets import QWidget as _QWidget
        role_layout = QVBoxLayout()

        r_btn_row = QHBoxLayout()
        r_btn_row.addWidget(QLabel("📋 角色列表（左侧） - 点击查看权限，「编辑权限」修改"))
        r_btn_row.addStretch()
        self.btn_edit_role_perm = QPushButton("🔐 编辑权限")
        self.btn_edit_role_perm.setStyleSheet("background-color: #8e44ad; color: white; padding: 6px 16px;")
        self.btn_edit_role_perm.clicked.connect(self._on_edit_role_permissions)
        r_btn_row.addWidget(self.btn_edit_role_perm)

        self.btn_refresh_roles = QPushButton("🔄 刷新")
        self.btn_refresh_roles.clicked.connect(self._refresh_roles)
        r_btn_row.addWidget(self.btn_refresh_roles)
        role_layout.addLayout(r_btn_row)

        splitter = QSplitter(Qt.Horizontal)

        self.role_table = QTableWidget()
        table_utils.setup_table_style(self.role_table)
        self.role_table.itemSelectionChanged.connect(self._on_role_selected)
        splitter.addWidget(self.role_table)

        perm_group = QTabWidget()
        perm_group_layout = QVBoxLayout()
        self.role_detail_label = QLabel("请选择左侧角色查看权限")
        self.role_detail_label.setFont(QFont("", 12, QFont.Bold))
        perm_group_layout.addWidget(self.role_detail_label)

        self.perm_label = QLabel("-")
        self.perm_label.setWordWrap(True)
        self.perm_label.setStyleSheet("padding: 10px; background: #f8f9fa; border-radius: 4px;")
        perm_group_layout.addWidget(self.perm_label, stretch=1)

        self.role_users_label = QLabel("")
        perm_group_layout.addWidget(self.role_users_label)

        perm_container = _QWidget()
        perm_container.setLayout(perm_group_layout)
        splitter.addWidget(perm_container)
        splitter.setSizes([400, 400])

        role_layout.addWidget(splitter, stretch=1)

        role_container = _QWidget()
        role_container.setLayout(role_layout)
        return role_container

    def refresh(self) -> None:
        self._refresh_users()
        self._refresh_roles()

    def _refresh_users(self) -> None:
        users = UserRepository.get_all()
        headers = ["ID", "用户名", "真实姓名", "角色", "邮箱", "电话", "状态"]
        self.user_table.setColumnCount(len(headers))
        self.user_table.setHorizontalHeaderLabels(headers)
        self.user_table.setRowCount(len(users))

        bold_font = QFont("", 10, QFont.Bold)
        for row, u in enumerate(users):
            self.user_table.setItem(row, 0, QTableWidgetItem(str(u["id"])))
            self.user_table.setItem(row, 1, QTableWidgetItem(u.get("username", "")))
            self.user_table.setItem(row, 2, QTableWidgetItem(u.get("real_name", "")))

            roles = UserRepository.get_roles(u["id"])
            role_names = "、".join([r["name"] for r in roles]) or "-"
            role_item = QTableWidgetItem(role_names)
            role_item.setForeground(QBrush(QColor(142, 68, 173)))
            role_item.setFont(bold_font)
            self.user_table.setItem(row, 3, role_item)

            self.user_table.setItem(row, 4, QTableWidgetItem(u.get("email", "") or "-"))
            self.user_table.setItem(row, 5, QTableWidgetItem(u.get("phone", "") or "-"))

            status = u.get("status", "active")
            status_item = QTableWidgetItem(status)
            if status == "active":
                status_item.setForeground(QBrush(QColor(46, 204, 113)))
            else:
                status_item.setForeground(QBrush(QColor(149, 165, 166)))
            status_item.setFont(bold_font)
            self.user_table.setItem(row, 6, status_item)

        table_utils.resize_table_columns(self.user_table, "resize_to_contents")
        self.user_table.horizontalHeader().setStretchLastSection(True)

    def _refresh_roles(self) -> None:
        roles = RoleRepository.get_all()
        headers = ["ID", "角色名称", "描述", "用户数"]
        self.role_table.setColumnCount(len(headers))
        self.role_table.setHorizontalHeaderLabels(headers)
        self.role_table.setRowCount(len(roles))

        for row, r in enumerate(roles):
            self.role_table.setItem(row, 0, QTableWidgetItem(str(r["id"])))
            self.role_table.setItem(row, 1, QTableWidgetItem(r.get("name", "")))
            self.role_table.setItem(row, 2, QTableWidgetItem(r.get("description", "") or "-"))

            users = RoleRepository.get_users(r["id"])
            self.role_table.setItem(row, 3, QTableWidgetItem(str(len(users))))

        table_utils.resize_table_columns(self.role_table, "resize_to_contents")
        self.role_table.horizontalHeader().setStretchLastSection(True)
        self.perm_label.setText("-")
        self.role_detail_label.setText("请选择左侧角色查看权限")
        self.role_users_label.setText("")

    def _on_role_selected(self) -> None:
        role_id = table_utils.get_selected_row_id(self.role_table)
        if not role_id:
            return
        role = RoleRepository.get_by_id(role_id)
        if not role:
            return

        self.role_detail_label.setText(f"👤 角色：{role.get('name', '')}  -  {role.get('description', '')}")

        perms = RoleRepository.get_permissions(role_id)
        perm_names_map = {
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
        if perms:
            txt_lines = []
            for p in perms:
                txt_lines.append(f"  ✓ {perm_names_map.get(p, p)}")
            self.perm_label.setText(f"当前权限（共 {len(perms)} 项）:\n\n" + "\n".join(txt_lines))
        else:
            self.perm_label.setText("当前角色未分配任何权限")

        users = RoleRepository.get_users(role_id)
        if users:
            user_names = "、".join([f"{u.get('real_name', '')}({u.get('username', '')})" for u in users])
            self.role_users_label.setText(f"👥 拥有此角色的用户（{len(users)} 人）：{user_names}")
        else:
            self.role_users_label.setText("")

    def _get_selected_user_id(self) -> Optional[int]:
        return table_utils.get_selected_row_id(self.user_table)

    def _get_selected_user_ids(self) -> List[int]:
        return table_utils.get_selected_row_ids(self.user_table)

    def _get_selected_role_id(self) -> Optional[int]:
        return table_utils.get_selected_row_id(self.role_table)

    def _on_add_user(self) -> None:
        dlg = UserDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                password = data.pop("password_hash", "")
                role_ids = data.pop("role_ids", [])
                user_id = UserRepository.create(**data, password=password)
                for rid in role_ids:
                    UserRepository.assign_role(user_id, rid)
                message_utils.show_info(self, "成功", "用户已创建")
                self._refresh_users()
                self.notify_data_changed()
            except Exception as e:
                message_utils.show_error(self, "错误", f"创建失败: {str(e)}")

    def _on_edit_user(self) -> None:
        user_id = self._get_selected_user_id()
        if not user_id:
            message_utils.show_warning(self, "提示", "请选择要编辑的用户")
            return
        user = UserRepository.get_by_id(user_id)
        if not user:
            return
        dlg = UserDialog(self, user=user)
        if dlg.exec():
            data = dlg.get_data()
            try:
                password = data.pop("password_hash", None)
                role_ids = data.pop("role_ids", [])
                update_kwargs = {}
                for k, v in data.items():
                    if v is not None and v != "":
                        update_kwargs[k] = v
                if password:
                    update_kwargs["password"] = password
                if update_kwargs:
                    UserRepository.update(user_id, **update_kwargs)

                current_roles = UserRepository.get_roles(user_id)
                current_role_ids = [r["id"] for r in current_roles]
                for rid in role_ids:
                    if rid not in current_role_ids:
                        UserRepository.assign_role(user_id, rid)
                for rid in current_role_ids:
                    if rid not in role_ids:
                        UserRepository.remove_role(user_id, rid)

                message_utils.show_info(self, "成功", "用户已更新")
                self._refresh_users()
                self.notify_data_changed()
            except Exception as e:
                message_utils.show_error(self, "错误", f"更新失败: {str(e)}")

    def _on_delete_user(self) -> None:
        ids = self._get_selected_user_ids()
        if not ids:
            message_utils.show_warning(self, "提示", "请选择要删除的用户")
            return
        if not message_utils.confirm_delete(self, len(ids), "用户"):
            return
        deleted = 0
        for uid in ids:
            if UserRepository.delete(uid):
                deleted += 1
        message_utils.show_info(self, "成功", f"已删除 {deleted} 个用户")
        self._refresh_users()
        self.notify_data_changed()

    def _on_edit_role_permissions(self) -> None:
        role_id = self._get_selected_role_id()
        if not role_id:
            message_utils.show_warning(self, "提示", "请选择要编辑权限的角色")
            return
        role = RoleRepository.get_by_id(role_id)
        if not role:
            return
        dlg = RolePermissionDialog(self, role=role)
        if dlg.exec():
            selected = dlg.get_selected_permissions()
            current = RoleRepository.get_permissions(role_id)
            try:
                for p in selected:
                    if p not in current:
                        RoleRepository.add_permission(role_id, p)
                for p in current:
                    if p not in selected:
                        RoleRepository.remove_permission(role_id, p)
                message_utils.show_info(self, "成功", f"角色「{role.get('name', '')}」的权限已更新")
                self._refresh_roles()
                self.notify_data_changed()
            except Exception as e:
                message_utils.show_error(self, "错误", f"权限更新失败: {str(e)}")
