from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timedelta
import math

from app.db.database import (
    BuildingRepository, ComponentRepository, RecordRepository,
    DefectRepository, WorkOrderRepository, RectificationTrackingRepository,
    AcceptanceRecordRepository, EffectivenessEvaluationRepository,
    DefectStatusLogRepository, MaintenanceResourceRepository,
    DefectRecurrenceRepository, SettingsRepository,
    DEFECT_SEVERITIES, DEFECT_STATUSES, WORK_ORDER_STATUSES,
    PRIORITIES, DEFECT_TYPES
)


SEVERITY_SCORE = {"轻微": 1, "一般": 2, "严重": 3, "危急": 4}
PRIORITY_SCORE = {"低": 1, "中": 2, "高": 3, "紧急": 4}
SEVERITY_DEFAULT_DEADLINE_DAYS = {"轻微": 30, "一般": 14, "严重": 7, "危急": 3}


def calculate_defect_priority(defect: Dict[str, Any]) -> Tuple[int, str, List[str]]:
    score = 0
    factors = []

    severity = defect.get("severity", "一般")
    sev_score = SEVERITY_SCORE.get(severity, 2)
    score += sev_score * 30
    factors.append(f"严重程度「{severity}」(+{sev_score * 30}分)")

    try:
        disc_date = defect.get("discovery_date", "")
        if disc_date:
            dt = datetime.fromisoformat(disc_date.split(" ")[0])
            days_pending = (datetime.now() - dt).days
            if days_pending > 14:
                score += 30
                factors.append(f"积压时间过长({days_pending}天)(+30分)")
            elif days_pending > 7:
                score += 15
                factors.append(f"积压时间较长({days_pending}天)(+15分)")
    except Exception:
        pass

    defect_type = defect.get("defect_type", "")
    if defect_type in ("木材腐朽", "糟朽软化"):
        score += 20
        factors.append(f"高风险病害类型「{defect_type}」(+20分)")
    elif defect_type in ("虫蛀蚁害", "连接节点损坏"):
        score += 15
        factors.append(f"中风险病害类型「{defect_type}」(+15分)")

    work_order_id = defect.get("work_order_id")
    if work_order_id:
        wo = WorkOrderRepository.get_by_id(work_order_id)
        if wo:
            try:
                deadline = wo.get("deadline", "")
                if deadline:
                    dl_dt = datetime.fromisoformat(deadline.split(" ")[0])
                    days_left = (dl_dt - datetime.now()).days
                    if days_left < 0:
                        score += 25
                        factors.append(f"已逾期({abs(days_left)}天)(+25分)")
                    elif days_left <= 3:
                        score += 20
                        factors.append(f"即将到期(剩余{days_left}天)(+20分)")
                    elif days_left <= 7:
                        score += 10
                        factors.append(f"临近截止(剩余{days_left}天)(+10分)")
            except Exception:
                pass
            pri = wo.get("priority", "中")
            pri_score = PRIORITY_SCORE.get(pri, 2)
            score += pri_score * 5
            factors.append(f"工单优先级「{pri}」(+{pri_score * 5}分)")

    component_id = defect.get("component_id")
    if component_id:
        recs = RecordRepository.get_by_component(component_id)
        if recs:
            recent = sorted(recs, key=lambda x: x["measure_time"], reverse=True)[:3]
            avg_moist = sum(r["moisture"] for r in recent) / len(recent)
            threshold = SettingsRepository.get_moisture_threshold()
            if avg_moist > threshold * 1.3:
                score += 15
                factors.append(f"含水率持续过高(平均{avg_moist:.1f}%)(+15分)")
            elif avg_moist > threshold:
                score += 8
                factors.append(f"含水率超标(平均{avg_moist:.1f}%)(+8分)")

    recurrences = DefectRecurrenceRepository.get_by_defect(defect["id"])
    if recurrences:
        count = len(recurrences)
        if count >= 3:
            score += 20
            factors.append(f"多次复发({count}次)(+20分)")
        elif count >= 1:
            score += 10
            factors.append(f"有复发记录({count}次)(+10分)")

    score = min(score, 100)

    if score >= 80:
        level = "紧急"
    elif score >= 60:
        level = "高"
    elif score >= 40:
        level = "中"
    else:
        level = "低"

    return score, level, factors


def sort_defects_by_priority(defects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched = []
    for d in defects:
        score, level, factors = calculate_defect_priority(d)
        d_copy = dict(d)
        d_copy["priority_score"] = score
        d_copy["priority_level"] = level
        d_copy["priority_factors"] = factors
        enriched.append(d_copy)
    enriched.sort(key=lambda x: x["priority_score"], reverse=True)
    return enriched


def check_rectification_deadlines() -> Dict[str, Any]:
    reminders_days = int(SettingsRepository.get("defect_reminder_days", "7"))
    all_wos = WorkOrderRepository.get_all()

    result = {
        "overdue": [],
        "urgent": [],
        "warning": [],
        "total_active": 0,
        "overdue_count": 0,
        "urgent_count": 0,
        "warning_count": 0
    }

    now = datetime.now()
    for wo in all_wos:
        if wo.get("status") in ("已完成", "已取消"):
            continue
        result["total_active"] += 1

        deadline = wo.get("deadline", "")
        if not deadline:
            continue

        try:
            dl_dt = datetime.fromisoformat(deadline.split(" ")[0])
            days_left = (dl_dt - now).days
        except Exception:
            continue

        item = dict(wo)
        item["days_left"] = days_left

        if days_left < 0:
            item["deadline_status"] = "已逾期"
            item["deadline_days_abs"] = abs(days_left)
            result["overdue"].append(item)
            result["overdue_count"] += 1
        elif days_left <= 3:
            item["deadline_status"] = "紧急"
            result["urgent"].append(item)
            result["urgent_count"] += 1
        elif days_left <= reminders_days:
            item["deadline_status"] = "提醒"
            result["warning"].append(item)
            result["warning_count"] += 1

    result["overdue"].sort(key=lambda x: x["days_left"])
    result["urgent"].sort(key=lambda x: x["days_left"])
    result["warning"].sort(key=lambda x: x["days_left"])

    return result


def calculate_effectiveness_comparison(building_id: int = None) -> Dict[str, Any]:
    all_evals = EffectivenessEvaluationRepository.get_all(building_id)
    all_defects = DefectRepository.get_all(building_id=building_id)

    result = {
        "total_evaluated": len(all_evals),
        "overall_avg_improvement": 0.0,
        "by_defect_type": {},
        "by_severity": {},
        "effect_distribution": {"优秀": 0, "良好": 0, "一般": 0, "较差": 0},
        "moisture_improvement_box": [],
        "top_improvements": [],
        "lowest_improvements": []
    }

    improvements = []
    by_type_imp = defaultdict(list)
    by_sev_imp = defaultdict(list)

    for ev in all_evals:
        overall = ev.get("overall_effect", "一般")
        if overall in result["effect_distribution"]:
            result["effect_distribution"][overall] += 1

        mi = ev.get("moisture_improvement")
        if mi is not None:
            improvements.append(mi)
            result["moisture_improvement_box"].append({
                "defect_id": ev.get("defect_id"),
                "defect_type": ev.get("defect_type", "未知"),
                "improvement": mi,
                "overall": overall
            })

        dtype = ev.get("defect_type", "其他")
        if mi is not None:
            by_type_imp[dtype].append(mi)
            sev = "一般"
            for d in all_defects:
                if d["id"] == ev.get("defect_id"):
                    sev = d.get("severity", "一般")
                    break
            by_sev_imp[sev].append(mi)

    if improvements:
        result["overall_avg_improvement"] = round(sum(improvements) / len(improvements), 1)

    for dtype, imps in by_type_imp.items():
        if imps:
            result["by_defect_type"][dtype] = {
                "count": len(imps),
                "avg_improvement": round(sum(imps) / len(imps), 1),
                "max_improvement": round(max(imps), 1),
                "min_improvement": round(min(imps), 1)
            }

    for sev, imps in by_sev_imp.items():
        if imps:
            result["by_severity"][sev] = {
                "count": len(imps),
                "avg_improvement": round(sum(imps) / len(imps), 1)
            }

    sorted_imps = sorted(result["moisture_improvement_box"], key=lambda x: x["improvement"], reverse=True)
    result["top_improvements"] = sorted_imps[:5]
    result["lowest_improvements"] = sorted_imps[-5:] if len(sorted_imps) >= 5 else sorted_imps

    return result


def calculate_closed_loop_performance(building_id: int = None) -> Dict[str, Any]:
    all_defects = DefectRepository.get_all(building_id=building_id)

    result = {
        "total_defects": len(all_defects),
        "closed_count": 0,
        "pending_count": 0,
        "processing_count": 0,
        "closed_rate": 0.0,
        "avg_cycle_days": 0.0,
        "avg_acceptance_wait_days": 0.0,
        "by_building": {},
        "by_component": {},
        "by_defect_type": {},
        "rework_count": 0,
        "rework_rate": 0.0,
        "buildings_detail": [],
        "components_detail": []
    }

    cycle_days = []
    acceptance_wait_days = []
    by_building = defaultdict(lambda: {"total": 0, "closed": 0, "processing": 0, "pending": 0, "cycle_days": []})
    by_component = defaultdict(lambda: {"total": 0, "closed": 0, "processing": 0, "pending": 0, "cycle_days": []})
    by_type = defaultdict(lambda: {"total": 0, "closed": 0, "processing": 0, "pending": 0, "cycle_days": []})

    for defect in all_defects:
        status = defect.get("status", "待处置")
        bname = defect.get("building_name", "未知")
        ccode = defect.get("component_code", "")
        cname = defect.get("component_name", "")
        ckey = f"{ccode} - {cname}" if ccode else cname
        dtype = defect.get("defect_type", "其他")

        by_building[bname]["total"] += 1
        by_component[ckey]["total"] += 1
        by_type[dtype]["total"] += 1

        if status in ("已完成", "已验收", "已关闭"):
            result["closed_count"] += 1
            by_building[bname]["closed"] += 1
            by_component[ckey]["closed"] += 1
            by_type[dtype]["closed"] += 1

            logs = DefectStatusLogRepository.get_by_defect(defect["id"])
            if logs:
                first = logs[0].get("created_at")
                last = logs[-1].get("created_at")
                try:
                    if first and last:
                        dt1 = datetime.fromisoformat(first.split(" ")[0])
                        dt2 = datetime.fromisoformat(last.split(" ")[0])
                        days = (dt2 - dt1).days
                        if days >= 0:
                            cycle_days.append(days)
                            by_building[bname]["cycle_days"].append(days)
                            by_component[ckey]["cycle_days"].append(days)
                            by_type[dtype]["cycle_days"].append(days)
                except Exception:
                    pass
        elif status in ("处置中", "待验收"):
            result["processing_count"] += 1
            by_building[bname]["processing"] += 1
            by_component[ckey]["processing"] += 1
            by_type[dtype]["processing"] += 1
        else:
            result["pending_count"] += 1
            by_building[bname]["pending"] += 1
            by_component[ckey]["pending"] += 1
            by_type[dtype]["pending"] += 1

        accept_records = AcceptanceRecordRepository.get_by_defect(defect["id"])
        if accept_records:
            result["rework_count"] += 1 if accept_records.get("accept_result") == "需返工" else 0

    if result["total_defects"] > 0:
        result["closed_rate"] = round(result["closed_count"] / result["total_defects"] * 100, 1)
    if cycle_days:
        result["avg_cycle_days"] = round(sum(cycle_days) / len(cycle_days), 1)
    if result["closed_count"] > 0:
        result["rework_rate"] = round(result["rework_count"] / result["closed_count"] * 100, 1)

    for bname, data in by_building.items():
        closed_rate = round(data["closed"] / data["total"] * 100, 1) if data["total"] > 0 else 0
        avg_cycle = round(sum(data["cycle_days"]) / len(data["cycle_days"]), 1) if data["cycle_days"] else 0
        result["by_building"][bname] = {
            "total": data["total"], "closed": data["closed"],
            "processing": data["processing"], "pending": data["pending"],
            "closed_rate": closed_rate, "avg_cycle_days": avg_cycle
        }
        result["buildings_detail"].append({
            "name": bname, **result["by_building"][bname]
        })

    for ckey, data in by_component.items():
        closed_rate = round(data["closed"] / data["total"] * 100, 1) if data["total"] > 0 else 0
        avg_cycle = round(sum(data["cycle_days"]) / len(data["cycle_days"]), 1) if data["cycle_days"] else 0
        result["by_component"][ckey] = {
            "total": data["total"], "closed": data["closed"],
            "processing": data["processing"], "pending": data["pending"],
            "closed_rate": closed_rate, "avg_cycle_days": avg_cycle
        }
        result["components_detail"].append({
            "name": ckey, **result["by_component"][ckey]
        })

    for dtype, data in by_type.items():
        closed_rate = round(data["closed"] / data["total"] * 100, 1) if data["total"] > 0 else 0
        avg_cycle = round(sum(data["cycle_days"]) / len(data["cycle_days"]), 1) if data["cycle_days"] else 0
        result["by_defect_type"][dtype] = {
            "total": data["total"], "closed": data["closed"],
            "processing": data["processing"], "pending": data["pending"],
            "closed_rate": closed_rate, "avg_cycle_days": avg_cycle
        }

    result["buildings_detail"].sort(key=lambda x: x["closed_rate"], reverse=True)
    result["components_detail"].sort(key=lambda x: x["closed_rate"], reverse=True)

    return result


def detect_defect_recurrences(component_id: int = None, building_id: int = None) -> List[Dict[str, Any]]:
    if component_id:
        defects = DefectRepository.get_all(component_id=component_id)
    elif building_id:
        defects = DefectRepository.get_all(building_id=building_id)
    else:
        defects = DefectRepository.get_all()

    by_component = defaultdict(list)
    for d in defects:
        by_component[d["component_id"]].append(d)

    potential_recurrences = []

    for cid, comp_defects in by_component.items():
        comp_defects.sort(key=lambda x: x.get("discovery_date", ""))
        for i in range(len(comp_defects)):
            for j in range(i + 1, len(comp_defects)):
                d1 = comp_defects[i]
                d2 = comp_defects[j]
                if d1["defect_type"] != d2["defect_type"]:
                    continue
                existing = DefectRecurrenceRepository.get_by_defect(d1["id"])
                already_linked = any(r.get("recurrence_defect_id") == d2["id"] for r in existing)
                if already_linked:
                    continue
                try:
                    dt1 = datetime.fromisoformat(d1["discovery_date"].split(" ")[0])
                    dt2 = datetime.fromisoformat(d2["discovery_date"].split(" ")[0])
                    days_between = (dt2 - dt1).days
                except Exception:
                    days_between = None

                loc1 = (d1.get("location_detail", "") or "").strip()
                loc2 = (d2.get("location_detail", "") or "").strip()
                if loc1 and loc2 and loc1 == loc2:
                    rtype = "同一位置复发"
                elif d1["defect_type"] == d2["defect_type"]:
                    rtype = "同类病害"
                else:
                    continue

                desc1 = d1.get("description", "")
                desc2 = d2.get("description", "")
                similarity_score = 0
                if loc1 and loc2 and loc1 == loc2:
                    similarity_score += 50
                if d1["defect_type"] == d2["defect_type"]:
                    similarity_score += 30
                words1 = set(w for w in desc1.replace("，", ",").replace("。", ".").replace(" ", ",").split(",") if w)
                words2 = set(w for w in desc2.replace("，", ",").replace("。", ".").replace(" ", ",").split(",") if w)
                if words1 and words2:
                    overlap = len(words1 & words2) / len(words1 | words2)
                    similarity_score += int(overlap * 20)

                if similarity_score >= 60:
                    potential_recurrences.append({
                        "original_defect_id": d1["id"],
                        "original_defect_type": d1["defect_type"],
                        "original_description": desc1,
                        "original_location": loc1,
                        "original_date": d1.get("discovery_date", ""),
                        "recurrence_defect_id": d2["id"],
                        "recurrence_defect_type": d2["defect_type"],
                        "recurrence_description": desc2,
                        "recurrence_location": loc2,
                        "recurrence_date": d2.get("discovery_date", ""),
                        "component_id": cid,
                        "component_code": d1.get("component_code", ""),
                        "component_name": d1.get("component_name", ""),
                        "building_name": d1.get("building_name", ""),
                        "days_between": days_between,
                        "similarity_score": similarity_score,
                        "suggested_type": rtype
                    })

    potential_recurrences.sort(key=lambda x: x["similarity_score"], reverse=True)
    return potential_recurrences
