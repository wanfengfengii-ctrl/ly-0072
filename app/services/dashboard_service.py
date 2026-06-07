from typing import Dict, Any

from app.logic.dashboard import (
    get_multi_building_overview, get_risk_distribution_by_type
)


class DashboardService:
    @staticmethod
    def get_multi_building_overview() -> Dict[str, Any]:
        return get_multi_building_overview()

    @staticmethod
    def get_risk_distribution_by_type() -> Dict[str, Any]:
        return get_risk_distribution_by_type()
