from typing import Optional, Any, List
from PySide6.QtWidgets import QWidget


class BaseTab(QWidget):
    def __init__(self, main_window: Optional[QWidget] = None):
        super().__init__(main_window)
        self.main_window = main_window
        self._init_ui()

    def _init_ui(self) -> None:
        pass

    def refresh(self) -> None:
        pass

    def on_activated(self) -> None:
        self.refresh()

    @property
    def current_building_id(self) -> Optional[int]:
        if self.main_window:
            return getattr(self.main_window, "current_building_id", None)
        return None

    @property
    def current_component_id(self) -> Optional[int]:
        if self.main_window:
            return getattr(self.main_window, "current_component_id", None)
        return None

    @property
    def selected_comparison_ids(self) -> List[int]:
        if self.main_window:
            return getattr(self.main_window, "selected_comparison_ids", [])
        return []
