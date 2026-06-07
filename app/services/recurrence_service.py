from typing import List, Dict, Any, Optional

from app.db.database import (
    DefectRecurrenceRepository, DefectRepository, RECURRENCE_TYPES
)
from app.logic.collaboration_analytics import detect_defect_recurrences


class RecurrenceService:
    @staticmethod
    def get_all_recurrences() -> List[Dict[str, Any]]:
        return DefectRecurrenceRepository.get_analysis().get("recurrences", [])

    @staticmethod
    def get_analysis(building_id: Optional[int] = None,
                     component_id: Optional[int] = None) -> Dict[str, Any]:
        return DefectRecurrenceRepository.get_analysis(
            building_id=building_id, component_id=component_id
        )

    @staticmethod
    def detect_potential_recurrences(component_id: Optional[int] = None,
                                     building_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return detect_defect_recurrences(
            component_id=component_id, building_id=building_id
        )

    @staticmethod
    def create_recurrence(original_defect_id: int,
                          recurrence_defect_id: int,
                          recurrence_type: str,
                          days_between: Optional[int] = None,
                          root_cause: str = "",
                          remark: str = "") -> int:
        return DefectRecurrenceRepository.create(
            original_defect_id=original_defect_id,
            recurrence_defect_id=recurrence_defect_id,
            recurrence_type=recurrence_type,
            days_between=days_between,
            root_cause=root_cause,
            remark=remark
        )

    @staticmethod
    def get_by_defect(defect_id: int) -> List[Dict[str, Any]]:
        return DefectRecurrenceRepository.get_by_defect(defect_id)
