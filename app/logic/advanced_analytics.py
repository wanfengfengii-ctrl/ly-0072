from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timedelta
import math
from app.db.database import (
    BuildingRepository, ComponentRepository, RecordRepository,
    SettingsRepository
)
from app.logic.validator import (
    calculate_statistics, parse_measure_time, analyze_component_risk
)


def compare_components(component_ids: List[int],
                       group_by: str = "type") -> Dict[str, Any]:
    threshold = SettingsRepository.get_moisture_threshold()
    result = {
        "component_ids": component_ids,
        "group_by": group_by,
        "groups": {},
        "overall_stats": {"count": 0, "avg": 0, "max": 0, "min": 0}
    }

    all_moistures = []
    group_data = defaultdict(lambda: {"components": [], "moistures": [], "records": []})

    for cid in component_ids:
        comp = ComponentRepository.get_by_id(cid)
        if not comp:
            continue
        records = RecordRepository.get_by_component(cid)
        stats = calculate_statistics(records)
        risk = analyze_component_risk(cid)

        if group_by == "type":
            key = comp["component_type"] or "其他"
        elif group_by == "building":
            building = BuildingRepository.get_by_id(comp["building_id"])
            key = building["name"] if building else "未知建筑"
        elif group_by == "position":
            key = comp.get("position") or "未指定位置"
        else:
            key = "全部"

        comp_data = {
            "id": comp["id"],
            "code": comp["code"],
            "name": comp["name"],
            "building_id": comp["building_id"],
            "building_name": comp.get("building_name", ""),
            "component_type": comp["component_type"],
            "position": comp.get("position", ""),
            "stats": stats,
            "risk_level": risk["overall_risk_level"],
            "record_count": len(records)
        }
        group_data[key]["components"].append(comp_data)
        group_data[key]["records"].extend(records)

        for r in records:
            group_data[key]["moistures"].append(r["moisture"])
            all_moistures.append(r["moisture"])

    for key, data in group_data.items():
        moistures = data["moistures"]
        if moistures:
            result["groups"][key] = {
                "components": data["components"],
                "component_count": len(data["components"]),
                "record_count": len(data["records"]),
                "avg_moisture": round(sum(moistures) / len(moistures), 2),
                "max_moisture": round(max(moistures), 2),
                "min_moisture": round(min(moistures), 2),
                "std_moisture": round(
                    math.sqrt(sum((x - sum(moistures) / len(moistures)) ** 2 for x in moistures) / len(moistures)), 2
                ),
                "high_ratio": round(sum(1 for m in moistures if m > threshold) / len(moistures) * 100, 1)
            }
        else:
            result["groups"][key] = {
                "components": data["components"],
                "component_count": len(data["components"]),
                "record_count": 0,
                "avg_moisture": 0,
                "max_moisture": 0,
                "min_moisture": 0,
                "std_moisture": 0,
                "high_ratio": 0
            }

    if all_moistures:
        n = len(all_moistures)
        avg = sum(all_moistures) / n
        result["overall_stats"] = {
            "count": n,
            "avg": round(avg, 2),
            "max": round(max(all_moistures), 2),
            "min": round(min(all_moistures), 2),
            "std": round(math.sqrt(sum((x - avg) ** 2 for x in all_moistures) / n), 2)
        }

    return result


def get_all_components_for_comparison() -> List[Dict[str, Any]]:
    components = ComponentRepository.get_all()
    result = []
    for comp in components:
        risk = analyze_component_risk(comp["id"])
        records = RecordRepository.get_by_component(comp["id"])
        stats = calculate_statistics(records)
        result.append({
            "id": comp["id"],
            "code": comp["code"],
            "name": comp["name"],
            "component_type": comp["component_type"],
            "position": comp.get("position", ""),
            "building_name": comp.get("building_name", ""),
            "building_id": comp["building_id"],
            "risk_level": risk["overall_risk_level"],
            "avg_moisture": stats["avg"],
            "record_count": len(records)
        })
    return result


def analyze_seasonal_variation(component_id: int) -> Dict[str, Any]:
    records = RecordRepository.get_by_component(component_id)
    threshold = SettingsRepository.get_moisture_threshold()

    result = {
        "component_id": component_id,
        "has_data": False,
        "seasons": {},
        "monthly_stats": {},
        "seasonal_pattern": "",
        "high_risk_seasons": []
    }

    if not records:
        return result

    season_map = {
        12: "冬季", 1: "冬季", 2: "冬季",
        3: "春季", 4: "春季", 5: "春季",
        6: "夏季", 7: "夏季", 8: "夏季",
        9: "秋季", 10: "秋季", 11: "秋季"
    }
    month_names = ["1月", "2月", "3月", "4月", "5月", "6月",
                   "7月", "8月", "9月", "10月", "11月", "12月"]

    season_data = defaultdict(list)
    month_data = defaultdict(list)

    for r in records:
        dt = parse_measure_time(r["measure_time"])
        if not dt:
            continue
        season = season_map[dt.month]
        season_data[season].append(r["moisture"])
        month_data[dt.month].append(r["moisture"])

    for season in ["春季", "夏季", "秋季", "冬季"]:
        moistures = season_data.get(season, [])
        if moistures:
            n = len(moistures)
            avg = sum(moistures) / n
            result["seasons"][season] = {
                "count": n,
                "avg": round(avg, 2),
                "max": round(max(moistures), 2),
                "min": round(min(moistures), 2),
                "high_ratio": round(sum(1 for m in moistures if m > threshold) / n * 100, 1)
            }
            if avg > threshold:
                result["high_risk_seasons"].append(season)

    for m in range(1, 13):
        moistures = month_data.get(m, [])
        if moistures:
            n = len(moistures)
            avg = sum(moistures) / n
            result["monthly_stats"][month_names[m - 1]] = {
                "count": n,
                "avg": round(avg, 2),
                "max": round(max(moistures), 2),
                "min": round(min(moistures), 2)
            }

    if result["seasons"]:
        season_avgs = {s: d["avg"] for s, d in result["seasons"].items()}
        if season_avgs:
            sorted_seasons = sorted(season_avgs.items(), key=lambda x: x[1], reverse=True)
            highest = sorted_seasons[0]
            lowest = sorted_seasons[-1]
            if highest[1] - lowest[1] >= 3:
                result["seasonal_pattern"] = (
                    f"季节性波动明显：{highest[0]}最高(平均{highest[1]}%)，"
                    f"{lowest[0]}最低(平均{lowest[1]}%)，差值{round(highest[1] - lowest[1], 1)}%"
                )
            else:
                result["seasonal_pattern"] = "季节性波动不显著，全年含水率相对稳定"

    result["has_data"] = True
    return result


def analyze_seasonal_variation_multi(component_ids: List[int]) -> Dict[str, Any]:
    season_map = {
        12: "冬季", 1: "冬季", 2: "冬季",
        3: "春季", 4: "春季", 5: "春季",
        6: "夏季", 7: "夏季", 8: "夏季",
        9: "秋季", 10: "秋季", 11: "秋季"
    }
    month_names = ["1月", "2月", "3月", "4月", "5月", "6月",
                   "7月", "8月", "9月", "10月", "11月", "12月"]
    threshold = SettingsRepository.get_moisture_threshold()

    result = {
        "component_count": len(component_ids),
        "seasons": {s: {"count": 0, "moistures": []} for s in ["春季", "夏季", "秋季", "冬季"]},
        "monthly_stats": {m: {"count": 0, "moistures": []} for m in month_names},
        "by_component": {}
    }

    for cid in component_ids:
        comp = ComponentRepository.get_by_id(cid)
        if not comp:
            continue
        records = RecordRepository.get_by_component(cid)
        comp_season_data = defaultdict(list)

        for r in records:
            dt = parse_measure_time(r["measure_time"])
            if not dt:
                continue
            season = season_map[dt.month]
            result["seasons"][season]["moistures"].append(r["moisture"])
            result["seasons"][season]["count"] += 1
            result["monthly_stats"][month_names[dt.month - 1]]["moistures"].append(r["moisture"])
            result["monthly_stats"][month_names[dt.month - 1]]["count"] += 1
            comp_season_data[season].append(r["moisture"])

        comp_season_stats = {}
        for s, moistures in comp_season_data.items():
            if moistures:
                comp_season_stats[s] = {
                    "avg": round(sum(moistures) / len(moistures), 2),
                    "count": len(moistures)
                }
        result["by_component"][f"{comp['code']} - {comp['name']}"] = comp_season_stats

    for s in ["春季", "夏季", "秋季", "冬季"]:
        moistures = result["seasons"][s]["moistures"]
        if moistures:
            n = len(moistures)
            avg = sum(moistures) / n
            result["seasons"][s] = {
                "count": n,
                "avg": round(avg, 2),
                "max": round(max(moistures), 2),
                "min": round(min(moistures), 2),
                "high_ratio": round(sum(1 for m in moistures if m > threshold) / n * 100, 1)
            }

    for m in month_names:
        moistures = result["monthly_stats"][m]["moistures"]
        if moistures:
            n = len(moistures)
            avg = sum(moistures) / n
            result["monthly_stats"][m] = {
                "count": n,
                "avg": round(avg, 2),
                "max": round(max(moistures), 2),
                "min": round(min(moistures), 2)
            }
        else:
            result["monthly_stats"][m] = {
                "count": 0, "avg": 0, "max": 0, "min": 0
            }

    return result


def predict_risk_trend(component_id: int, forecast_days: int = 90) -> Dict[str, Any]:
    records = RecordRepository.get_by_component(component_id)
    threshold = SettingsRepository.get_moisture_threshold()

    result = {
        "component_id": component_id,
        "has_data": False,
        "historical_points": [],
        "forecast_points": [],
        "trend_direction": "stable",
        "forecast_avg": 0.0,
        "forecast_max": 0.0,
        "risk_level_forecast": "正常",
        "will_exceed_threshold": False,
        "exceed_probability": 0.0,
        "recommendation": ""
    }

    if len(records) < 3:
        if records:
            result["recommendation"] = "历史数据不足3个时间点，建议积累更多检测数据后再进行趋势预测"
        return result

    sorted_records = sorted(records, key=lambda x: x["measure_time"])

    historical = []
    for r in sorted_records:
        dt = parse_measure_time(r["measure_time"])
        if dt:
            historical.append({"time": dt, "moisture": r["moisture"]})

    if len(historical) < 3:
        result["recommendation"] = "有效历史数据不足，无法进行可靠预测"
        return result

    result["has_data"] = True

    first_dt = historical[0]["time"]
    x_data = [(h["time"] - first_dt).days for h in historical]
    y_data = [h["moisture"] for h in historical]

    n = len(x_data)
    sum_x = sum(x_data)
    sum_y = sum(y_data)
    sum_xy = sum(x * y for x, y in zip(x_data, y_data))
    sum_x2 = sum(x * x for x in x_data)

    slope = 0
    intercept = 0
    if n * sum_x2 - sum_x * sum_x != 0:
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        intercept = (sum_y - slope * sum_x) / n

    residuals = []
    for i in range(n):
        predicted = slope * x_data[i] + intercept
        residuals.append(abs(y_data[i] - predicted))
    std_error = (sum(r ** 2 for r in residuals) / max(1, n - 2)) ** 0.5 if n > 2 else 0

    last_dt = historical[-1]["time"]
    last_x = x_data[-1]

    forecast_points = []
    step_days = max(1, forecast_days // 10)
    for day_offset in range(0, forecast_days + 1, step_days):
        fx = last_x + day_offset
        fy = slope * fx + intercept
        forecast_dt = last_dt + timedelta(days=day_offset)
        forecast_points.append({
            "time": forecast_dt,
            "moisture": round(fy, 2),
            "upper": round(fy + 1.96 * std_error, 2),
            "lower": round(fy - 1.96 * std_error, 2)
        })

    recent_avg = sum(y_data[-min(5, n):]) / min(5, n)
    forecast_values = [p["moisture"] for p in forecast_points]
    result["forecast_avg"] = round(sum(forecast_values) / len(forecast_values), 2) if forecast_values else 0
    result["forecast_max"] = round(max(forecast_values), 2) if forecast_values else 0

    if abs(slope) < 0.005:
        result["trend_direction"] = "stable"
    elif slope > 0:
        result["trend_direction"] = "rising"
    else:
        result["trend_direction"] = "falling"

    max_forecast = max(forecast_values) if forecast_values else 0
    if max_forecast > threshold:
        result["will_exceed_threshold"] = True
        exceed_vals = [v for v in forecast_values if v > threshold]
        result["exceed_probability"] = round(len(exceed_vals) / len(forecast_values) * 100, 1)

    if result["will_exceed_threshold"] and result["exceed_probability"] > 50:
        result["risk_level_forecast"] = "高风险"
    elif result["forecast_avg"] > threshold * 0.9 or result["trend_direction"] == "rising":
        result["risk_level_forecast"] = "中风险"
    else:
        result["risk_level_forecast"] = "正常"

    if result["trend_direction"] == "rising":
        trend_desc = f"含水率呈上升趋势(每日约+{round(slope * 30, 2)}%/月)"
    elif result["trend_direction"] == "falling":
        trend_desc = f"含水率呈下降趋势(每日约{round(slope * 30, 2)}%/月)"
    else:
        trend_desc = "含水率整体保持稳定"

    if result["will_exceed_threshold"]:
        result["recommendation"] = (
            f"⚠ {trend_desc}。预测未来{forecast_days}天内"
            f"有{result['exceed_probability']}%概率超过阈值{threshold}%，"
            f"建议加强巡检频率，必要时采取防潮除湿措施。"
        )
    else:
        result["recommendation"] = (
            f"✓ {trend_desc}。预测未来{forecast_days}天内含水率将维持在正常范围，"
            f"按常规计划巡检即可。"
        )

    result["historical_points"] = [
        {"time": h["time"], "moisture": h["moisture"]} for h in historical
    ]
    result["forecast_points"] = forecast_points
    result["regression"] = {
        "slope": round(slope, 4),
        "intercept": round(intercept, 2),
        "std_error": round(std_error, 2)
    }

    return result
