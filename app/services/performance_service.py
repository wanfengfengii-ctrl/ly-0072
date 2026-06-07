from typing import List, Dict, Any, Tuple, Optional

from app.logic.collaboration_analytics import (
    calculate_defect_priority, sort_defects_by_priority,
    check_rectification_deadlines, calculate_effectiveness_comparison,
    calculate_closed_loop_performance
)


class PerformanceService:
    @staticmethod
    def calculate_priority(defect: Dict[str, Any]) -> Tuple[int, str, List[str]]:
        return calculate_defect_priority(defect)

    @staticmethod
    def sort_defects_by_priority(defects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sort_defects_by_priority(defects)

    @staticmethod
    def check_rectification_deadlines() -> Dict[str, Any]:
        return check_rectification_deadlines()

    @staticmethod
    def calculate_effectiveness(building_id: Optional[int] = None) -> Dict[str, Any]:
        return calculate_effectiveness_comparison(building_id=building_id)

    @staticmethod
    def calculate_closed_loop_performance(building_id: Optional[int] = None) -> Dict[str, Any]:
        return calculate_closed_loop_performance(building_id=building_id)
