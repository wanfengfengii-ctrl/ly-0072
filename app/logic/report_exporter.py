import os
from datetime import datetime
from typing import Dict, Any, List, Tuple
from app.db.database import (
    BuildingRepository, ComponentRepository, RecordRepository, SettingsRepository,
    ReportArchiveRepository, DefectRepository, WorkOrderRepository,
    RectificationTrackingRepository, AcceptanceRecordRepository,
    EffectivenessEvaluationRepository, DefectStatusLogRepository
)
from app.logic.validator import analyze_component_risk, calculate_statistics


def generate_html_report(building_id: int = None, component_id: int = None,
                     output_path: str = None, include_charts: bool = True,
                     include_stats: bool = True, include_risk: bool = True) -> str:
    threshold = SettingsRepository.get_moisture_threshold()
    consec_count = SettingsRepository.get_consecutive_count()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if output_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_path = os.path.join(base_dir, f"巡检报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")

    html_parts = []
    html_parts.append(f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
    body {{ font-family: "Microsoft YaHei", sans-serif; margin: 40px; color: #333; }}
    h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
    h2 {{ color: #2980b9; margin-top: 30px; }}
    h3 {{ color: #34495e; }}
    table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
    th {{ background: #3498db; color: white; padding: 10px; text-align: left; border: 1px solid #2980b9; }}
    td {{ padding: 8px 10px; border: 1px solid #ddd; }}
    tr:nth-child(even) {{ background: #f8f9fa; }}
    .risk-high {{ color: #c0392b; font-weight: bold; }}
    .risk-medium {{ color: #e67e22; font-weight: bold; }}
    .risk-low {{ color: #27ae60; font-weight: bold; }}
    .summary-box {{ background: #ecf0f1; padding: 20px; border-radius: 8px; margin: 20px 0; }}
    .stat-card {{ display: inline-block; background: white; padding: 15px 25px; margin: 10px; border-radius: 6px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1); min-width: 120px; text-align: center; }}
    .stat-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
    .stat-label {{ font-size: 12px; color: #7f8c8d; }}
    .footer {{ margin-top: 50px; color: #95a5a6; font-size: 12px; text-align: center; }}
</style>
</head>
<body>
    <h1>古建筑木构件含水率巡检报告</h1>
    <div class="summary-box">
        <div class="stat-card">
            <div class="stat-value">{threshold}%</div>
            <div class="stat-label">含水率阈值</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{consec_count}次</div>
            <div class="stat-label">连续超标判定</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{now}</div>
            <div class="stat-label">报告生成时间</div>
        </div>
    </div>
""")

    buildings = []
    if building_id:
        b = BuildingRepository.get_by_id(building_id)
        if b:
            buildings = [b]
    else:
        buildings = BuildingRepository.get_all()

    total_components = 0
    high_risk_count = 0
    medium_risk_count = 0

    for building in buildings:
        html_parts.append(f"<h2>建筑: {building['name']}</h2>")
        if building.get("location"):
            html_parts.append(f"<p><strong>位置:</strong> {building['location']}")
        if building.get("built_year"):
            html_parts.append(f" | <strong>建造年代:</strong> {building['built_year']}</p>")

        components = ComponentRepository.get_by_building(building["id"])

        if component_id:
            components = [c for c in components if c["id"] == component_id]

        for comp in components:
            total_components += 1
            risk_result = analyze_component_risk(comp["id"])
            records = RecordRepository.get_by_component(comp["id"])

            risk_level = risk_result["overall_risk_level"]
            if risk_level == "高风险":
                risk_class = "risk-high"
                high_risk_count += 1
            elif risk_level == "中风险":
                risk_class = "risk-medium"
                medium_risk_count += 1
            else:
                risk_class = "risk-low"

            html_parts.append(f"""
    <h3>构件: {comp['code']} - {comp['name']}
        <span class="{risk_class}">[{risk_level}]</span></h3>
    <p><strong>类型:</strong> {comp['component_type']}
       <strong>记录数:</strong> {risk_result['total_records']}
       <strong>检测位置:</strong> {', '.join(risk_result['positions']) or '无'}
""")

            if records and include_stats:
                stats = calculate_statistics(records)
                html_parts.append(f"""
    <table>
        <tr><th>统计项</th><th>数值</th></tr>
        <tr><td>检测次数</td><td>{stats['count']}</td></tr>
        <tr><td>平均含水率</td><td>{stats['avg']}%</td></tr>
        <tr><td>最高含水率</td><td>{stats['max']}%</td></tr>
        <tr><td>最低含水率</td><td>{stats['min']}%</td></tr>
        <tr><td>标准差</td><td>{stats['std']}</td></tr>
    </table>
""")

            if include_risk:
                if risk_result["consecutive_high_risk"]:
                    html_parts.append("<h4>连续超标记录</h4><table>")
                    html_parts.append("<tr><th>位置</th><th>开始时间</th><th>结束时间</th><th>连续次数</th><th>最高值</th><th>平均值</th></tr>")
                    for item in risk_result["consecutive_high_risk"]:
                        html_parts.append(
                            f"<tr><td>{item['position']}</td>"
                            f"<td>{item['start_time']}</td>"
                            f"<td>{item['end_time']}</td>"
                            f"<td>{item['count']}次</td>"
                            f"<td>{item['max_moisture']}%</td>"
                            f"<td>{item['avg_moisture']}%</td></tr>"
                        )
                    html_parts.append("</table>")

                if risk_result["long_term_moisture"]:
                    html_parts.append("<h4>长期潮湿记录</h4><table>")
                    html_parts.append("<tr><th>位置</th><th>开始时间</th><th>结束时间</th><th>持续天数</th><th>平均值</th><th>超标比例</th></tr>")
                    for item in risk_result["long_term_moisture"]:
                        html_parts.append(
                            f"<tr><td>{item['position']}</td>"
                            f"<td>{item['start_time']}</td>"
                            f"<td>{item['end_time']}</td>"
                            f"<td>{item['duration_days']}天</td>"
                            f"<td>{item['avg_moisture']}%</td>"
                            f"<td>{item['high_ratio']}%</td></tr>"
                        )
                    html_parts.append("</table>")

                if risk_result["sudden_rises"]:
                    html_parts.append("<h4>含水率骤升记录</h4><table>")
                    html_parts.append("<tr><th>位置</th><th>上次时间</th><th>本次时间</th><th>上次值</th><th>本次值</th><th>增幅</th></tr>")
                    for item in risk_result["sudden_rises"]:
                        html_parts.append(
                            f"<tr><td>{item['position']}</td>"
                            f"<td>{item['prev_time']}</td>"
                            f"<td>{item['curr_time']}</td>"
                            f"<td>{item['prev_moisture']}%</td>"
                            f"<td>{item['curr_moisture']}%</td>"
                            f"<td>+{item['rise_ratio']}%</td></tr>"
                        )
                    html_parts.append("</table>")

                if risk_result["missing_records"]:
                    html_parts.append("<h4>记录缺失</h4><table>")
                    html_parts.append("<tr><th>位置</th><th>上次时间</th><th>下次时间</th><th>间隔天数</th></tr>")
                    for item in risk_result["missing_records"]:
                        html_parts.append(
                            f"<tr><td>{item['position']}</td>"
                            f"<td>{item['prev_time']}</td>"
                            f"<td>{item['next_time']}</td>"
                            f"<td>{item['gap_days']}天</td></tr>"
                        )
                    html_parts.append("</table>")

    html_parts.append(f"""
    <h2>总览</h2>
    <div class="summary-box">
        <div class="stat-card"><div class="stat-value">{total_components}</div><div class="stat-label">总构件数</div></div>
        <div class="stat-card"><div class="stat-value risk-high">{high_risk_count}</div><div class="stat-label">高风险</div></div>
        <div class="stat-card"><div class="stat-value risk-medium">{medium_risk_count}</div><div class="stat-label">中风险</div></div>
        <div class="stat-card"><div class="stat-value risk-low">{total_components - high_risk_count - medium_risk_count}</div><div class="stat-label">正常</div></div>
    </div>
    <div class="footer">
        报告由「古建筑木构件含水率分析系统」自动生成
    </div>
</body>
</html>
""")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("".join(html_parts))

    return output_path


def batch_export_reports(output_dir: str, building_id: int = None,
                         archive: bool = True, include_charts: bool = True,
                         include_stats: bool = True, include_risk: bool = True) -> List[Dict[str, Any]]:
    results = []
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    if building_id:
        buildings = [BuildingRepository.get_by_id(building_id)]
        buildings = [b for b in buildings if b]
    else:
        buildings = BuildingRepository.get_all()

    for building in buildings:
        b_name = "".join(c for c in building["name"] if c.isalnum() or c in (" ", "_", "-")).strip()
        b_name = b_name.replace(" ", "_") or f"building_{building['id']}"
        file_name = f"巡检报告_{b_name}_{timestamp}.html"
        file_path = os.path.join(output_dir, file_name)

        try:
            generate_html_report(
                building_id=building["id"], 
                output_path=file_path,
                include_charts=include_charts,
                include_stats=include_stats,
                include_risk=include_risk
            )
            file_size = os.path.getsize(file_path)

            archive_id = None
            if archive:
                archive_id = ReportArchiveRepository.create(
                    report_type="建筑巡检报告",
                    building_id=building["id"],
                    file_name=file_name,
                    file_path=file_path,
                    file_size=file_size,
                    generated_by="系统批量导出",
                    description=f"{building['name']} - 批量导出巡检报告"
                )

            results.append({
                "success": True,
                "building_id": building["id"],
                "building_name": building["name"],
                "file_name": file_name,
                "file_path": file_path,
                "file_size": file_size,
                "archive_id": archive_id
            })
        except Exception as e:
            results.append({
                "success": False,
                "building_id": building["id"],
                "building_name": building["name"],
                "error": str(e)
            })

    return results


def generate_comparison_report(component_ids: List[int], output_path: str = None,
                                group_by: str = "type") -> str:
    from app.logic.advanced_analytics import compare_components
    from datetime import datetime

    threshold = SettingsRepository.get_moisture_threshold()
    comparison = compare_components(component_ids, group_by)

    if output_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_path = os.path.join(base_dir, "对比分析报告_{}.html".format(datetime.now().strftime('%Y%m%d_%H%M%S')))

    group_by_map = {"type": "按构件类型", "building": "按建筑", "position": "按位置"}
    group_by_label = group_by_map.get(group_by, "自定义")
    gen_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    comp_count = len(component_ids)
    overall_stats = comparison['overall_stats']

    html = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
    body { font-family: "Microsoft YaHei", sans-serif; margin: 40px; color: #333; }
    h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
    h2 { color: #2980b9; margin-top: 30px; }
    h3 { color: #34495e; }
    table { border-collapse: collapse; width: 100%; margin: 15px 0; }
    th { background: #3498db; color: white; padding: 10px; text-align: left; border: 1px solid #2980b9; }
    td { padding: 8px 10px; border: 1px solid #ddd; }
    tr:nth-child(even) { background: #f8f9fa; }
    .risk-high { color: #c0392b; font-weight: bold; }
    .risk-medium { color: #e67e22; font-weight: bold; }
    .risk-low { color: #27ae60; font-weight: bold; }
    .summary-box { background: #ecf0f1; padding: 20px; border-radius: 8px; margin: 20px 0; }
    .footer { margin-top: 50px; color: #95a5a6; font-size: 12px; text-align: center; }
</style>
</head>
<body>
    <h1>构件横向对比分析报告</h1>
    <div class="summary-box">
        <p><strong>生成时间:</strong> %s</p>
        <p><strong>分组方式:</strong> %s</p>
        <p><strong>对比构件数:</strong> %d 个</p>
        <p><strong>检测记录总数:</strong> %d 条</p>
        <p><strong>整体平均含水率:</strong> %s%%</p>
        <p><strong>含水率阈值:</strong> %s%%</p>
    </div>
    <h2>分组统计对比</h2>
    <table>
        <tr><th>分组</th><th>构件数</th><th>记录数</th><th>平均含水率</th><th>最高含水率</th><th>最低含水率</th><th>超标占比</th></tr>
""" % (gen_time, group_by_label, comp_count, overall_stats['count'], overall_stats['avg'], threshold)

    for key, data in comparison["groups"].items():
        avg_class = "risk-high" if data['avg_moisture'] > threshold else "risk-low"
        max_class = "risk-high" if data['max_moisture'] > threshold else ""
        if data['high_ratio'] > 30:
            ratio_class = "risk-high"
        elif data['high_ratio'] > 10:
            ratio_class = "risk-medium"
        else:
            ratio_class = "risk-low"
        html += """
        <tr>
            <td>%s</td>
            <td>%d</td>
            <td>%d</td>
            <td class="%s">%s%%</td>
            <td class="%s">%s%%</td>
            <td>%s%%</td>
            <td class="%s">%s%%</td>
        </tr>
""" % (key, data['component_count'], data['record_count'],
       avg_class, data['avg_moisture'],
       max_class, data['max_moisture'],
       data['min_moisture'],
       ratio_class, data['high_ratio'])

    html += """
    </table>
    <h2>各构件详细数据</h2>
"""

    risk_map = {"高风险": "risk-high", "中风险": "risk-medium", "正常": "risk-low"}

    for key, data in comparison["groups"].items():
        html += "<h3>%s</h3>" % key
        html += """
        <table>
            <tr><th>构件编号</th><th>构件名称</th><th>类型</th><th>记录数</th><th>平均含水率</th><th>最高含水率</th><th>风险等级</th></tr>
"""
        for comp in data["components"]:
            risk_class = risk_map.get(comp["risk_level"], "")
            avg_class = "risk-high" if comp['stats']['avg'] > threshold else ""
            max_class = "risk-high" if comp['stats']['max'] > threshold else ""
            html += """
            <tr>
                <td>%s</td>
                <td>%s</td>
                <td>%s</td>
                <td>%d</td>
                <td class="%s">%s%%</td>
                <td class="%s">%s%%</td>
                <td class="%s">%s</td>
            </tr>
""" % (comp['code'], comp['name'], comp['component_type'],
       comp['record_count'],
       avg_class, comp['stats']['avg'],
       max_class, comp['stats']['max'],
       risk_class, comp['risk_level'])
        html += "</table>"

    html += """
    <div class="footer">
        报告由「古建筑木构件含水率智能预警与多维分析系统」自动生成
    </div>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


def generate_defect_disposal_report(defect_id: int, output_path: str = None) -> str:
    now = datetime.now()
    if output_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_path = os.path.join(
            base_dir,
            f"病害处置报告_{defect_id}_{now.strftime('%Y%m%d_%H%M%S')}.html"
        )

    defect = DefectRepository.get_by_id(defect_id)
    if not defect:
        raise ValueError(f"找不到ID为 {defect_id} 的病害记录")

    work_orders = WorkOrderRepository.get_all(defect_id=defect_id)
    work_order = work_orders[0] if work_orders else None
    wo_id = work_order["id"] if work_order else None

    tracks = RectificationTrackingRepository.get_by_work_order(wo_id) if wo_id else []
    accept = AcceptanceRecordRepository.get_by_defect(defect_id)
    eval_data = EffectivenessEvaluationRepository.get_by_defect(defect_id)
    logs = DefectStatusLogRepository.get_by_defect(defect_id)

    sev_colors = {"轻微": "#27ae60", "一般": "#f39c12", "严重": "#e67e22", "危急": "#e74c3c"}
    sev_color = sev_colors.get(defect.get("severity", "一般"), "#333")
    status_colors = {
        "待处置": "#e74c3c", "处置中": "#f39c12",
        "待验收": "#3498db", "已验收": "#9b59b6",
        "已完成": "#27ae60", "已关闭": "#95a5a6"
    }
    status_color = status_colors.get(defect.get("status", ""), "#333")

    html_parts = []
    html_parts.append(f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
    body {{ font-family: "Microsoft YaHei", sans-serif; margin: 40px; color: #333; }}
    h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
    h2 {{ color: #2980b9; margin-top: 30px; }}
    h3 {{ color: #34495e; }}
    table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
    th {{ background: #3498db; color: white; padding: 10px; text-align: left; border: 1px solid #2980b9; }}
    td {{ padding: 8px 10px; border: 1px solid #ddd; }}
    tr:nth-child(even) {{ background: #f8f9fa; }}
    .summary-box {{ background: #ecf0f1; padding: 20px; border-radius: 8px; margin: 20px 0; }}
    .footer {{ margin-top: 50px; color: #95a5a6; font-size: 12px; text-align: center; }}
    .tag {{ display: inline-block; padding: 4px 12px; border-radius: 4px;
            color: white; font-weight: bold; font-size: 14px; }}
</style>
</head>
<body>
    <h1>古建筑木构件病害处置报告</h1>
    <div class="summary-box">
        <p><strong>报告编号:</strong> DR-{defect['id']}-{now.strftime('%Y%m%d')}</p>
        <p><strong>生成时间:</strong> {now.strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
""")

    html_parts.append(f"""
    <h2>一、病害基本信息</h2>
    <table>
        <tr><th style="width:150px;">病害ID</th><td>{defect.get('id', '')}</td></tr>
        <tr><th>病害类型</th><td>{defect.get('defect_type', '')}</td></tr>
        <tr><th>严重程度</th>
            <td><span class="tag" style="background:{sev_color};">{defect.get('severity', '')}</span></td></tr>
        <tr><th>当前状态</th>
            <td><span class="tag" style="background:{status_color};">{defect.get('status', '')}</span></td></tr>
        <tr><th>所属建筑</th><td>{defect.get('building_name', '')}</td></tr>
        <tr><th>所属构件</th>
            <td>{defect.get('component_code', '')} - {defect.get('component_name', '')}
                ({defect.get('component_type', '')})</td></tr>
        <tr><th>发现日期</th><td>{defect.get('discovery_date', '')}</td></tr>
        <tr><th>发现人</th><td>{defect.get('discoverer', '') or '-'}</td></tr>
        <tr><th>具体位置</th><td>{defect.get('location_detail', '') or '-'}</td></tr>
        <tr><th>病害描述</th><td>{defect.get('description', '')}</td></tr>
        <tr><th>备注</th><td>{defect.get('remark', '') or '-'}</td></tr>
    </table>
""")

    if work_order:
        priority_colors = {"低": "#95a5a6", "中": "#3498db", "高": "#e67e22", "紧急": "#e74c3c"}
        p_color = priority_colors.get(work_order.get("priority", "中"), "#333")
        wo_status_color = status_colors.get(work_order.get("status", ""), "#333")
        html_parts.append(f"""
    <h2>二、维修工单信息</h2>
    <table>
        <tr><th style="width:150px;">工单编号</th><td><strong>{work_order.get('order_no', '')}</strong></td></tr>
        <tr><th>工单标题</th><td>{work_order.get('title', '')}</td></tr>
        <tr><th>工单状态</th>
            <td><span class="tag" style="background:{wo_status_color};">{work_order.get('status', '')}</span></td></tr>
        <tr><th>优先级</th>
            <td><span class="tag" style="background:{p_color};">{work_order.get('priority', '')}</span></td></tr>
        <tr><th>负责人</th><td>{work_order.get('assignee', '') or '-'}</td></tr>
        <tr><th>派工日期</th><td>{work_order.get('assign_date', '')}</td></tr>
        <tr><th>截止日期</th><td>{work_order.get('deadline', '') or '-'}</td></tr>
        <tr><th>完成时间</th>
            <td>{work_order.get('completed_at', '')[:19] if work_order.get('completed_at') else '-'}</td></tr>
        <tr><th>维修内容</th><td style="white-space:pre-wrap;">{work_order.get('work_content', '')}</td></tr>
        <tr><th>所需材料</th>
            <td style="white-space:pre-wrap;">{work_order.get('required_materials', '') or '-'}</td></tr>
    </table>
""")
    else:
        html_parts.append("""
    <h2>二、维修工单信息</h2>
    <p style="color:#888; padding:20px; text-align:center;">暂无关联维修工单</p>
""")

    if tracks:
        html_parts.append("""
    <h2>三、整改跟踪记录</h2>
    <table>
        <tr><th>跟踪日期</th><th>跟踪人</th><th>进展情况</th><th>存在问题</th><th>下一步计划</th></tr>
""")
        for t in tracks:
            html_parts.append(f"""
        <tr>
            <td>{t.get('track_date', '')[:10]}</td>
            <td>{t.get('tracker', '') or '-'}</td>
            <td style="white-space:pre-wrap;">{t.get('progress', '')}</td>
            <td style="white-space:pre-wrap;">{t.get('problems', '') or '-'}</td>
            <td style="white-space:pre-wrap;">{t.get('next_steps', '') or '-'}</td>
        </tr>
""")
        html_parts.append("    </table>")
    else:
        html_parts.append("""
    <h2>三、整改跟踪记录</h2>
    <p style="color:#888; padding:20px; text-align:center;">暂无整改跟踪记录</p>
""")

    if accept:
        result_color = "#27ae60" if accept.get("accept_result") in ("合格", "基本合格") else "#e74c3c"
        html_parts.append(f"""
    <h2>四、验收记录</h2>
    <table>
        <tr><th style="width:150px;">验收日期</th><td>{accept.get('accept_date', '')}</td></tr>
        <tr><th>验收结果</th>
            <td><span class="tag" style="background:{result_color};">{accept.get('accept_result', '')}</span></td></tr>
        <tr><th>验收人</th><td>{accept.get('accept_person', '')}</td></tr>
        <tr><th>检查项目</th>
            <td style="white-space:pre-wrap;">{accept.get('inspection_items', '') or '-'}</td></tr>
        <tr><th>验收备注</th>
            <td style="white-space:pre-wrap;">{accept.get('accept_note', '') or '-'}</td></tr>
    </table>
""")
    else:
        html_parts.append("""
    <h2>四、验收记录</h2>
    <p style="color:#888; padding:20px; text-align:center;">暂无验收记录</p>
""")

    if eval_data:
        imp_color = "#27ae60" if (eval_data.get("moisture_improvement") or 0) > 0 else "#e74c3c"
        effect_colors = {"优秀": "#27ae60", "良好": "#2ecc71", "一般": "#f39c12", "较差": "#e74c3c"}
        e_color = effect_colors.get(eval_data.get("overall_effect", ""), "#333")
        html_parts.append(f"""
    <h2>五、效果评估</h2>
    <table>
        <tr><th style="width:150px;">评估日期</th><td>{eval_data.get('eval_date', '')}</td></tr>
        <tr><th>总体效果</th>
            <td><span class="tag" style="background:{e_color};">{eval_data.get('overall_effect', '')}</span></td></tr>
        <tr><th>评估人</th><td>{eval_data.get('evaluator', '')}</td></tr>
        <tr><th>维修前含水率</th><td>{eval_data.get('moisture_before', '') or '-'} %</td></tr>
        <tr><th>维修后含水率</th><td>{eval_data.get('moisture_after', '') or '-'} %</td></tr>
        <tr><th>含水率改善率</th>
            <td style="color:{imp_color}; font-weight:bold;">
                {eval_data.get('moisture_improvement', '') or '-'} %</td></tr>
        <tr><th>维修前风险等级</th><td>{eval_data.get('risk_level_before', '') or '-'}</td></tr>
        <tr><th>维修后风险等级</th><td>{eval_data.get('risk_level_after', '') or '-'}</td></tr>
        <tr><th>耐久性评价</th><td>{eval_data.get('durability', '') or '-'}</td></tr>
        <tr><th>美观度评价</th><td>{eval_data.get('aesthetic', '') or '-'}</td></tr>
        <tr><th>评估备注</th>
            <td style="white-space:pre-wrap;">{eval_data.get('eval_note', '') or '-'}</td></tr>
    </table>
""")
    else:
        html_parts.append("""
    <h2>五、效果评估</h2>
    <p style="color:#888; padding:20px; text-align:center;">暂无效果评估记录</p>
""")

    if logs:
        html_parts.append("""
    <h2>六、状态流转日志</h2>
    <table>
        <tr><th>时间</th><th>原状态</th><th>新状态</th><th>操作人</th><th>变更说明</th></tr>
""")
        for log in logs:
            html_parts.append(f"""
        <tr>
            <td>{log.get('created_at', '')[:19]}</td>
            <td>{log.get('from_status', '') or '-'}</td>
            <td><strong>{log.get('to_status', '')}</strong></td>
            <td>{log.get('operator', '') or '-'}</td>
            <td>{log.get('change_note', '') or '-'}</td>
        </tr>
""")
        html_parts.append("    </table>")

    html_parts.append(f"""
    <div class="footer">
        报告由「古建筑木构件含水率智能预警与多维分析系统」自动生成
        <br>生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}
    </div>
</body>
</html>
""")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("".join(html_parts))

    return output_path

