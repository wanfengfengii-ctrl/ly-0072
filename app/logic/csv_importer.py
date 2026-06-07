import csv
import os
from typing import List, Dict, Any, Tuple, Optional
from io import StringIO
from app.db.database import RecordRepository
from app.logic.validator import (
    validate_csv_row, parse_measure_time, format_measure_time,
    check_duplicate_time
)

REQUIRED_COLUMNS = ["measure_time", "measure_position", "moisture"]
OPTIONAL_COLUMNS = ["temperature", "humidity", "operator", "remark"]

COLUMN_ALIASES = {
    "检测时间": "measure_time",
    "时间": "measure_time",
    "time": "measure_time",
    "检测位置": "measure_position",
    "位置": "measure_position",
    "position": "measure_position",
    "含水率": "moisture",
    "湿度含量": "moisture",
    "moisture_content": "moisture",
    "温度": "temperature",
    "temp": "temperature",
    "环境湿度": "humidity",
    "操作人员": "operator",
    "操作员": "operator",
    "备注": "remark",
    "说明": "remark",
}


def normalize_column_name(col: str) -> str:
    col = col.strip().lower()
    col = col.replace("\ufeff", "").strip()
    if col in COLUMN_ALIASES:
        return COLUMN_ALIASES[col]
    for alias, standard in COLUMN_ALIASES.items():
        if alias.lower() == col:
            return standard
    return col


def detect_encoding(file_path: str) -> str:
    encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312", "gb18030"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                f.read()
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"


def parse_csv_file(file_path: str) -> Tuple[List[str], List[List[str]]]:
    encoding = detect_encoding(file_path)
    with open(file_path, "r", encoding=encoding, newline="") as f:
        content = f.read()

    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(content[:4096])
    except csv.Error:
        dialect = csv.excel

    reader = csv.reader(StringIO(content), dialect=dialect)
    rows = list(reader)
    if not rows:
        return [], []

    headers = [h.strip() for h in rows[0]]
    data_rows = rows[1:]
    return headers, data_rows


def map_columns(headers: List[str]) -> Tuple[Dict[str, int], List[str]]:
    mapping = {}
    missing = []

    normalized_headers = [normalize_column_name(h) for h in headers]

    for req in REQUIRED_COLUMNS:
        if req in normalized_headers:
            mapping[req] = normalized_headers.index(req)
        else:
            missing.append(req)

    for opt in OPTIONAL_COLUMNS:
        if opt in normalized_headers:
            mapping[opt] = normalized_headers.index(opt)

    return mapping, missing


def preview_csv(file_path: str, preview_rows: int = 20) -> Dict[str, Any]:
    result = {
        "file_name": os.path.basename(file_path),
        "file_size": os.path.getsize(file_path),
        "headers": [],
        "normalized_headers": [],
        "preview_data": [],
        "total_rows": 0,
        "column_mapping": {},
        "missing_columns": [],
        "errors": [],
        "warnings": []
    }

    try:
        headers, data_rows = parse_csv_file(file_path)
        result["headers"] = headers
        result["normalized_headers"] = [normalize_column_name(h) for h in headers]
        result["total_rows"] = len(data_rows)
        result["preview_data"] = data_rows[:preview_rows]

        mapping, missing = map_columns(headers)
        result["column_mapping"] = mapping
        result["missing_columns"] = missing

        if missing:
            result["errors"].append(
                f"缺少必要列: {', '.join(missing)}。"
                f"必要列包括: {', '.join(REQUIRED_COLUMNS)}"
            )

    except Exception as e:
        result["errors"].append(f"文件读取失败: {str(e)}")

    return result


def validate_csv_content(file_path: str, component_id: int,
                         skip_errors: bool = True) -> Dict[str, Any]:
    result = {
        "valid_rows": [],
        "error_rows": [],
        "errors": [],
        "total_count": 0,
        "valid_count": 0,
        "error_count": 0,
        "duplicate_count": 0
    }

    try:
        headers, data_rows = parse_csv_file(file_path)
        mapping, missing = map_columns(headers)

        if missing:
            result["errors"].append(f"缺少必要列: {', '.join(missing)}")
            return result

        result["total_count"] = len(data_rows)
        seen_keys = set()

        for idx, row in enumerate(data_rows, start=2):
            if not any(str(cell).strip() for cell in row):
                continue

            row_data = {}
            for col_name, col_idx in mapping.items():
                if col_idx < len(row):
                    row_data[col_name] = row[col_idx]
                else:
                    row_data[col_name] = ""

            is_valid, errors = validate_csv_row(row_data, idx, component_id)

            if not is_valid:
                result["error_rows"].append({
                    "row_num": idx,
                    "row_data": row,
                    "errors": errors
                })
                result["error_count"] += 1
                if not skip_errors:
                    continue

            if is_valid or skip_errors:
                measure_time = parse_measure_time(str(row_data["measure_time"]).strip())
                position = str(row_data["measure_position"]).strip()
                key = (format_measure_time(measure_time), position)

                if key in seen_keys:
                    result["error_rows"].append({
                        "row_num": idx,
                        "row_data": row,
                        "errors": [f"第 {idx} 行: 检测时间和位置在CSV中重复"]
                    })
                    result["duplicate_count"] += 1
                    continue
                seen_keys.add(key)

                if component_id and check_duplicate_time(
                    component_id, format_measure_time(measure_time), position
                ):
                    result["error_rows"].append({
                        "row_num": idx,
                        "row_data": row,
                        "errors": [f"第 {idx} 行: 该检测时间和位置的记录已存在于数据库"]
                    })
                    result["duplicate_count"] += 1
                    continue

            if is_valid:
                result["valid_rows"].append({
                    "row_num": idx,
                    "row_data": row_data,
                    "normalized_time": format_measure_time(
                        parse_measure_time(str(row_data["measure_time"]).strip())
                    )
                })
                result["valid_count"] += 1

    except Exception as e:
        result["errors"].append(f"校验过程出错: {str(e)}")

    return result


def import_valid_records(component_id: int, valid_rows: List[Dict]) -> int:
    records_to_insert = []
    for item in valid_rows:
        rd = item["row_data"]
        temperature = None
        if "temperature" in rd and str(rd["temperature"]).strip() != "":
            try:
                temperature = float(rd["temperature"])
            except (ValueError, TypeError):
                pass

        humidity = None
        if "humidity" in rd and str(rd["humidity"]).strip() != "":
            try:
                humidity = float(rd["humidity"])
            except (ValueError, TypeError):
                pass

        records_to_insert.append((
            component_id,
            item["normalized_time"],
            str(rd["measure_position"]).strip(),
            float(rd["moisture"]),
            temperature,
            humidity,
            str(rd.get("operator", "")).strip(),
            str(rd.get("remark", "")).strip()
        ))

    if records_to_insert:
        return RecordRepository.bulk_create(records_to_insert)
    return 0


def generate_csv_template() -> str:
    headers = ["检测时间", "检测位置", "含水率", "温度", "环境湿度", "操作人员", "备注"]
    sample_rows = [
        ["2024-01-01 10:00:00", "梁端左侧", "18.5", "22.0", "55.0", "张三", "常规检测"],
        ["2024-01-15 10:00:00", "梁端左侧", "19.2", "21.5", "58.0", "张三", ""],
        ["2024-02-01 10:00:00", "梁中端", "21.0", "20.0", "60.0", "李四", "雨后检测"],
    ]
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(sample_rows)
    return output.getvalue()
