from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from app.db.database import (
    InspectionPlanRepository, AnomalyReviewRepository,
    RecordRepository, SettingsRepository
)


class InspectionService:
    @staticmethod
    def get_inspection_plans(status: Optional[str] = None) -> List[Dict[str, Any]]:
        return InspectionPlanRepository.get_all(status=status)

    @staticmethod
    def get_upcoming_plans() -> List[Dict[str, Any]]:
        return InspectionPlanRepository.get_upcoming()

    @staticmethod
    def create_plan(**kwargs) -> int:
        return InspectionPlanRepository.create(**kwargs)

    @staticmethod
    def update_plan(plan_id: int, **kwargs) -> bool:
        return InspectionPlanRepository.update(plan_id, **kwargs)

    @staticmethod
    def delete_plan(plan_id: int) -> bool:
        return InspectionPlanRepository.delete(plan_id)

    @staticmethod
    def get_anomaly_reviews(status: Optional[str] = None) -> List[Dict[str, Any]]:
        return AnomalyReviewRepository.get_all(status=status)

    @staticmethod
    def create_anomaly_review(record_id: int, component_id: int, **kwargs) -> int:
        return AnomalyReviewRepository.create(
            record_id=record_id, component_id=component_id, **kwargs
        )

    @staticmethod
    def update_anomaly_review(review_id: int, **kwargs) -> bool:
        return AnomalyReviewRepository.update(review_id, **kwargs)

    @staticmethod
    def auto_scan_anomalies() -> Tuple[int, int]:
        threshold = SettingsRepository.get_moisture_threshold()
        consecutive_count = SettingsRepository.get_consecutive_count()

        scanned = 0
        added = 0

        from app.db.database import ComponentRepository
        components = ComponentRepository.get_all()

        for comp in components:
            records = RecordRepository.get_by_component(comp["id"])
            if not records:
                continue

            scanned += 1
            records_sorted = sorted(records, key=lambda x: x["measure_time"], reverse=True)

            positions = set(r["measure_position"] for r in records_sorted)

            for pos in positions:
                pos_records = [r for r in records_sorted if r["measure_position"] == pos]
                if len(pos_records) < consecutive_count:
                    continue

                recent = pos_records[:consecutive_count]
                all_over = all(r["moisture"] > threshold for r in recent)

                if all_over:
                    latest = recent[0]
                    existing = AnomalyReviewRepository.get_by_record(latest["id"])
                    if not existing:
                        AnomalyReviewRepository.create(
                            record_id=latest["id"],
                            component_id=comp["id"],
                            review_status="待复核",
                            handling_suggestion=f"连续{consecutive_count}次含水率超过阈值{threshold}%"
                        )
                        added += 1

        return scanned, added
