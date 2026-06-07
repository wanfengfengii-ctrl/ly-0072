from typing import List, Dict, Any, Optional

from app.db.database import (
    DefectRepository, WorkOrderRepository,
    RectificationTrackingRepository, AcceptanceRecordRepository,
    EffectivenessEvaluationRepository
)


class DefectService:
    @staticmethod
    def get_defects(status: Optional[str] = None,
                    building_id: Optional[int] = None,
                    component_id: Optional[int] = None,
                    defect_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return DefectRepository.get_all(
            status=status, building_id=building_id,
            component_id=component_id, defect_type=defect_type
        )

    @staticmethod
    def get_defect_by_id(defect_id: int) -> Optional[Dict[str, Any]]:
        return DefectRepository.get_by_id(defect_id)

    @staticmethod
    def get_statistics(building_id: Optional[int] = None) -> Dict[str, Any]:
        return DefectRepository.get_statistics(building_id=building_id)

    @staticmethod
    def create_defect(**kwargs) -> int:
        return DefectRepository.create(**kwargs)

    @staticmethod
    def update_defect(defect_id: int, **kwargs) -> bool:
        return DefectRepository.update(defect_id, **kwargs)

    @staticmethod
    def delete_defect(defect_id: int) -> bool:
        return DefectRepository.delete(defect_id)

    @staticmethod
    def create_work_order(defect_id: int, **kwargs) -> int:
        return WorkOrderRepository.create(defect_id=defect_id, **kwargs)

    @staticmethod
    def get_work_orders(status: Optional[str] = None,
                        building_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return WorkOrderRepository.get_all(status=status, building_id=building_id)

    @staticmethod
    def update_work_order_status(wo_id: int, new_status: str,
                                 operator: str = "",
                                 change_note: str = "") -> bool:
        return WorkOrderRepository.update_status(
            wo_id, new_status, operator=operator, change_note=change_note
        )

    @staticmethod
    def add_rectification_tracking(wo_id: int, **kwargs) -> int:
        return RectificationTrackingRepository.create(
            work_order_id=wo_id, **kwargs
        )

    @staticmethod
    def create_acceptance(wo_id: int, **kwargs) -> int:
        return AcceptanceRecordRepository.create(
            work_order_id=wo_id, **kwargs
        )

    @staticmethod
    def create_evaluation(defect_id: int, **kwargs) -> int:
        return EffectivenessEvaluationRepository.create(
            defect_id=defect_id, **kwargs
        )

    @staticmethod
    def get_overdue_reminders() -> List[Dict[str, Any]]:
        return DefectRepository.get_overdue_reminders()
