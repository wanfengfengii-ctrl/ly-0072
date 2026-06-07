from typing import List, Dict, Any
from collections import defaultdict
from datetime import datetime
from app.db.database import (
    BuildingRepository, ComponentRepository, RecordRepository,
    SettingsRepository, AnomalyReviewRepository
)
from app.logic.validator import (
    analyze_component_risk, calculate_statistics, parse_measure_time
)


def get_multi_building_overview() -> Dict[str, Any]:
    buildings = BuildingRepository.get_all()
    threshold = SettingsRepository.get_moisture_threshold()

    result = {
        "total_buildings": len(buildings),
        "total_components": 0,
        "total_records": 0,
        "high_risk_components": 0,
        "medium_risk_components": 0,
        "normal_components": 0,
        "pending_reviews": 0,
        "buildings": []
    }

    for building in buildings:
        building_data = {
            "id": building["id"],
            "name": building["name"],
            "location": building.get("location", ""),
            "components": [],
            "total_components": 0,
            "total_records": 0,
            "high_risk": 0,
            "medium_risk": 0,
            "normal": 0,
            "avg_moisture": 0.0,
            "max_moisture": 0.0
        }

        components = ComponentRepository.get_by_building(building["id"])
        all_moistures = []

        for comp in components:
            risk = analyze_component_risk(comp["id"])
            records = RecordRepository.get_by_component(comp["id"])
            stats = calculate_statistics(records)

            risk_level = risk["overall_risk_level"]
            if risk_level == "高风险":
                building_data["high_risk"] += 1
                result["high_risk_components"] += 1
            elif risk_level == "中风险":
                building_data["medium_risk"] += 1
                result["medium_risk_components"] += 1
            else:
                building_data["normal"] += 1
                result["normal_components"] += 1

            comp_data = {
                "id": comp["id"],
                "code": comp["code"],
                "name": comp["name"],
                "component_type": comp["component_type"],
                "position": comp.get("position", ""),
                "risk_level": risk_level,
                "total_records": risk["total_records"],
                "avg_moisture": stats["avg"],
                "max_moisture": stats["max"],
                "issues_count": risk["risk_count"]
            }
            building_data["components"].append(comp_data)

            if records:
                moistures = [r["moisture"] for r in records]
                all_moistures.extend(moistures)

            building_data["total_components"] += 1
            building_data["total_records"] += len(records)
            result["total_records"] += len(records)

        if all_moistures:
            building_data["avg_moisture"] = round(sum(all_moistures) / len(all_moistures), 2)
            building_data["max_moisture"] = round(max(all_moistures), 2)

        result["buildings"].append(building_data)
        result["total_components"] += building_data["total_components"]

    pending_reviews = AnomalyReviewRepository.get_all("待复核")
    result["pending_reviews"] = len(pending_reviews)

    return result


def get_risk_distribution_by_type() -> Dict[str, Any]:
    components = ComponentRepository.get_all()
    type_stats = defaultdict(lambda: {"total": 0, "high": 0, "medium": 0, "normal": 0, "moistures": []})

    for comp in components:
        ctype = comp["component_type"] or "其他"
        risk = analyze_component_risk(comp["id"])
        records = RecordRepository.get_by_component(comp["id"])

        type_stats[ctype]["total"] += 1
        if risk["overall_risk_level"] == "高风险":
            type_stats[ctype]["high"] += 1
        elif risk["overall_risk_level"] == "中风险":
            type_stats[ctype]["medium"] += 1
        else:
            type_stats[ctype]["normal"] += 1

        for r in records:
            type_stats[ctype]["moistures"].append(r["moisture"])

    result = {}
    for ctype, data in type_stats.items():
        avg_moist = round(sum(data["moistures"]) / len(data["moistures"]), 2) if data["moistures"] else 0
        max_moist = round(max(data["moistures"]), 2) if data["moistures"] else 0
        result[ctype] = {
            "total": data["total"],
            "high_risk": data["high"],
            "medium_risk": data["medium"],
            "normal": data["normal"],
            "avg_moisture": avg_moist,
            "max_moisture": max_moist,
            "high_risk_ratio": round(data["high"] / data["total"] * 100, 1) if data["total"] > 0 else 0
        }

    return result
