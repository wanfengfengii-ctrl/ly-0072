from typing import List, Dict, Any, Optional
from datetime import datetime

from app.db.database import (
    MaintenanceResourceRepository, RESOURCE_TYPES, get_connection
)


class ResourceService:
    @staticmethod
    def get_resources(resource_type: Optional[str] = None,
                      building_id: Optional[int] = None) -> List[Dict[str, Any]]:
        stats = MaintenanceResourceRepository.get_statistics(building_id=building_id)
        resources = stats.get("resources", [])
        if resource_type:
            resources = [r for r in resources if r.get("resource_type") == resource_type]
        return resources

    @staticmethod
    def get_statistics(building_id: Optional[int] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None) -> Dict[str, Any]:
        return MaintenanceResourceRepository.get_statistics(
            building_id=building_id, start_date=start_date, end_date=end_date
        )

    @staticmethod
    def create_resource(**kwargs) -> int:
        return MaintenanceResourceRepository.create(**kwargs)

    @staticmethod
    def update_resource(resource_id: int, **kwargs) -> bool:
        now = datetime.now().isoformat()
        with get_connection() as conn:
            cursor = conn.cursor()
            fields = []
            values = []
            for k, v in kwargs.items():
                if v is not None:
                    fields.append(f"{k}=?")
                    values.append(v)
            if not fields:
                return False
            if "quantity" in kwargs or "unit_price" in kwargs:
                cursor.execute(
                    "SELECT quantity, unit_price FROM maintenance_resources WHERE id=?",
                    (resource_id,)
                )
                row = cursor.fetchone()
                if row:
                    qty = kwargs.get("quantity", row["quantity"])
                    price = kwargs.get("unit_price", row["unit_price"])
                    if qty is not None and price is not None:
                        total_cost = round(float(qty) * float(price), 2)
                        fields.append("total_cost=?")
                        values.append(total_cost)
            values.append(resource_id)
            cursor.execute(
                f"UPDATE maintenance_resources SET {', '.join(fields)} WHERE id=?",
                values
            )
            return cursor.rowcount > 0

    @staticmethod
    def delete_resource(resource_id: int) -> bool:
        return MaintenanceResourceRepository.delete(resource_id)

    @staticmethod
    def calculate_total_cost(resources: List[Dict[str, Any]]) -> float:
        total = 0.0
        for r in resources:
            if r.get("total_cost") is not None:
                total += r["total_cost"]
        return round(total, 2)
