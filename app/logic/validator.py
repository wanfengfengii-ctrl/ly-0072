from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import re
from app.db.database import SettingsRepository, RecordRepository

MOISTURE_MIN = 0.0
MOISTURE_MAX = 100.0
CONSECUTIVE_HIGH_RISK_COUNT = 3

TIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d",
]


def parse_measure_time(time_str: str) -> Optional[datetime]:
    time_str = time_str.strip()
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    return None


def format_measure_time(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def validate_moisture(value: float) -> Tuple[bool, str]:
    if value < MOISTURE_MIN or value > MOISTURE_MAX:
        return False, f"含水率 {value} 超出有效范围 ({MOISTURE_MIN}-{MOISTURE_MAX})"
    return True, ""


def validate_csv_row(row_data: Dict[str, Any], row_num: int,
                     component_id: int = None) -> Tuple[bool, List[str]]:
    errors = []

    required_fields = ["measure_time", "measure_position", "moisture"]
    for field in required_fields:
        if field not in row_data or str(row_data[field]).strip() == "":
            errors.append(f"第 {row_num} 行: 缺少必填字段 '{field}'")

    if errors:
        return False, errors

    measure_time_str = str(row_data["measure_time"]).strip()
    dt = parse_measure_time(measure_time_str)
    if dt is None:
        errors.append(f"第 {row_num} 行: 检测时间格式无效 '{measure_time_str}'，"
                      f"支持格式如: 2024-01-01 12:00:00")

    try:
        moisture = float(row_data["moisture"])
        ok, msg = validate_moisture(moisture)
        if not ok:
            errors.append(f"第 {row_num} 行: {msg}")
    except (ValueError, TypeError):
        errors.append(f"第 {row_num} 行: 含水率值无效 '{row_data['moisture']}'")

    position = str(row_data["measure_position"]).strip()
    if not position:
        errors.append(f"第 {row_num} 行: 检测位置不能为空")

    if "temperature" in row_data and str(row_data["temperature"]).strip() != "":
        try:
            float(row_data["temperature"])
        except (ValueError, TypeError):
            errors.append(f"第 {row_num} 行: 温度值无效 '{row_data['temperature']}'")

    if "humidity" in row_data and str(row_data["humidity"]).strip() != "":
        try:
            float(row_data["humidity"])
        except (ValueError, TypeError):
            errors.append(f"第 {row_num} 行: 湿度值无效 '{row_data['humidity']}'")

    return len(errors) == 0, errors


def check_duplicate_time(component_id: int, measure_time: str,
                         exclude_record_id: int = None) -> bool:
    if RecordRepository.exists(component_id, measure_time):
        if exclude_record_id:
            return False
        return True
    return False


def detect_consecutive_high_risk(records: List[Dict[str, Any]],
                                 position: str = None) -> List[Dict[str, Any]]:
    threshold = SettingsRepository.get_moisture_threshold()
    consecutive_n = CONSECUTIVE_HIGH_RISK_COUNT

    position_groups: Dict[str, List[Dict]] = {}
    for r in records:
        pos = r["measure_position"]
        if position and pos != position:
            continue
        if pos not in position_groups:
            position_groups[pos] = []
        position_groups[pos].append(r)

    high_risk_periods = []

    for pos, pos_records in position_groups.items():
        pos_records.sort(key=lambda x: x["measure_time"])

        streak_start_idx = None
        streak_count = 0

        for i, record in enumerate(pos_records):
            if record["moisture"] > threshold:
                if streak_start_idx is None:
                    streak_start_idx = i
                streak_count += 1
            else:
                if streak_count >= consecutive_n and streak_start_idx is not None:
                    streak_records = pos_records[streak_start_idx:i]
                    period = {
                        "start_time": streak_records[0]["measure_time"],
                        "end_time": streak_records[-1]["measure_time"],
                        "count": len(streak_records),
                        "position": pos,
                        "max_moisture": max(r["moisture"] for r in streak_records),
                        "avg_moisture": round(
                            sum(r["moisture"] for r in streak_records) / len(streak_records), 2
                        ),
                        "type": "连续超标"
                    }
                    high_risk_periods.append(period)
                streak_start_idx = None
                streak_count = 0

        if streak_count >= consecutive_n and streak_start_idx is not None:
            streak_records = pos_records[streak_start_idx:]
            period = {
                "start_time": streak_records[0]["measure_time"],
                "end_time": streak_records[-1]["measure_time"],
                "count": len(streak_records),
                "position": pos,
                "max_moisture": max(r["moisture"] for r in streak_records),
                "avg_moisture": round(
                    sum(r["moisture"] for r in streak_records) / len(streak_records), 2
                ),
                "type": "连续超标"
            }
            high_risk_periods.append(period)

    return high_risk_periods


def detect_long_term_moisture(records: List[Dict[str, Any]],
                              days: int = 30) -> List[Dict[str, Any]]:
    threshold = SettingsRepository.get_moisture_threshold()
    result = []

    position_groups: Dict[str, List[Dict]] = {}
    for r in records:
        pos = r["measure_position"]
        if pos not in position_groups:
            position_groups[pos] = []
        position_groups[pos].append(r)

    for pos, pos_records in position_groups.items():
        pos_records.sort(key=lambda x: x["measure_time"])
        if len(pos_records) < 2:
            continue

        try:
            start_dt = parse_measure_time(pos_records[0]["measure_time"])
            end_dt = parse_measure_time(pos_records[-1]["measure_time"])
            if start_dt and end_dt and (end_dt - start_dt).days >= days:
                avg_moisture = sum(r["moisture"] for r in pos_records) / len(pos_records)
                high_ratio = sum(
                    1 for r in pos_records if r["moisture"] > threshold
                ) / len(pos_records)
                if high_ratio >= 0.5 or avg_moisture > threshold:
                    result.append({
                        "position": pos,
                        "start_time": pos_records[0]["measure_time"],
                        "end_time": pos_records[-1]["measure_time"],
                        "duration_days": (end_dt - start_dt).days,
                        "avg_moisture": round(avg_moisture, 2),
                        "high_ratio": round(high_ratio * 100, 1),
                        "type": "长期潮湿"
                    })
        except Exception:
            continue

    return result


def detect_sudden_rise(records: List[Dict[str, Any]],
                       rise_ratio: float = 0.3) -> List[Dict[str, Any]]:
    result = []
    position_groups: Dict[str, List[Dict]] = {}
    for r in records:
        pos = r["measure_position"]
        if pos not in position_groups:
            position_groups[pos] = []
        position_groups[pos].append(r)

    for pos, pos_records in position_groups.items():
        pos_records.sort(key=lambda x: x["measure_time"])
        for i in range(1, len(pos_records)):
            prev = pos_records[i - 1]["moisture"]
            curr = pos_records[i]["moisture"]
            if prev > 0 and (curr - prev) / prev >= rise_ratio:
                result.append({
                    "position": pos,
                    "prev_time": pos_records[i - 1]["measure_time"],
                    "curr_time": pos_records[i]["measure_time"],
                    "prev_moisture": prev,
                    "curr_moisture": curr,
                    "rise_amount": round(curr - prev, 2),
                    "rise_ratio": round((curr - prev) / prev * 100, 1),
                    "type": "含水率骤升"
                })

    return result


def detect_missing_records(records: List[Dict[str, Any]],
                           expected_interval_days: int = 30) -> List[Dict[str, Any]]:
    result = []
    position_groups: Dict[str, List[Dict]] = {}
    for r in records:
        pos = r["measure_position"]
        if pos not in position_groups:
            position_groups[pos] = []
        position_groups[pos].append(r)

    for pos, pos_records in position_groups.items():
        pos_records.sort(key=lambda x: x["measure_time"])
        for i in range(1, len(pos_records)):
            prev_time = parse_measure_time(pos_records[i - 1]["measure_time"])
            curr_time = parse_measure_time(pos_records[i]["measure_time"])
            if prev_time and curr_time:
                gap_days = (curr_time - prev_time).days
                if gap_days > expected_interval_days * 2:
                    result.append({
                        "position": pos,
                        "prev_time": pos_records[i - 1]["measure_time"],
                        "next_time": pos_records[i]["measure_time"],
                        "gap_days": gap_days,
                        "expected_days": expected_interval_days,
                        "type": "记录缺失"
                    })

    return result


def analyze_component_risk(component_id: int) -> Dict[str, Any]:
    records = RecordRepository.get_by_component(component_id)

    result = {
        "total_records": len(records),
        "positions": RecordRepository.get_positions(component_id),
        "consecutive_high_risk": [],
        "long_term_moisture": [],
        "sudden_rises": [],
        "missing_records": [],
        "overall_risk_level": "正常",
        "risk_count": 0
    }

    if not records:
        return result

    result["consecutive_high_risk"] = detect_consecutive_high_risk(records)
    result["long_term_moisture"] = detect_long_term_moisture(records)
    result["sudden_rises"] = detect_sudden_rise(records)
    result["missing_records"] = detect_missing_records(records)

    total_issues = (
        len(result["consecutive_high_risk"]) +
        len(result["long_term_moisture"]) +
        len(result["sudden_rises"]) +
        len(result["missing_records"])
    )
    result["risk_count"] = total_issues

    if len(result["consecutive_high_risk"]) > 0 or len(result["long_term_moisture"]) > 0:
        result["overall_risk_level"] = "高风险"
    elif len(result["sudden_rises"]) > 0 or len(result["missing_records"]) > 0:
        result["overall_risk_level"] = "中风险"

    return result


def calculate_statistics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not records:
        return {"count": 0, "avg": 0, "max": 0, "min": 0, "std": 0}

    moisture_values = [r["moisture"] for r in records]
    n = len(moisture_values)
    avg = sum(moisture_values) / n
    variance = sum((x - avg) ** 2 for x in moisture_values) / n
    std = variance ** 0.5

    return {
        "count": n,
        "avg": round(avg, 2),
        "max": round(max(moisture_values), 2),
        "min": round(min(moisture_values), 2),
        "std": round(std, 2)
    }
