import os
from datetime import datetime
from typing import Dict, Any, List
from app.db.database import (
    BuildingRepository, ComponentRepository, RecordRepository, SettingsRepository
)
from app.logic.validator import analyze_component_risk, calculate_statistics


def generate_html_report(building_id: int = None, component_id: int = None,
                     output_path: str = None) -> str:
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

            if records:
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
