import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from datetime import datetime
import numpy as np
from typing import List, Dict, Any
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PySide6.QtGui import QFont

from app.logic.validator import parse_measure_time


class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=True)
        super().__init__(self.fig)
        self.setParent(parent)
        FigureCanvas.setSizePolicy(
            self, QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        FigureCanvas.updateGeometry(self)

    def clear(self):
        self.fig.clear()


class ChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = MplCanvas(self, width=8, height=5, dpi=100)
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout = QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def plot_trend(self, records: List[Dict[str, Any]],
                  position: str = None, threshold: float = 20.0):
        self.canvas.clear()
        ax = self.canvas.fig.add_subplot(111)

        if not records:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14)
            self.canvas.draw()
            return

        position_groups: Dict[str, List[Dict]] = {}
        for r in records:
            pos = r["measure_position"]
            if position and pos != position:
                continue
            if pos not in position_groups:
                position_groups[pos] = []
            position_groups[pos].append(r)

        colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
                  "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]

        for idx, (pos, pos_records) in enumerate(position_groups.items()):
            pos_records.sort(key=lambda x: x["measure_time"])
            times = []
            moistures = []
            for r in pos_records:
                dt = parse_measure_time(r["measure_time"])
                if dt:
                    times.append(dt)
                    moistures.append(r["moisture"])

            if times:
                ax.plot(times, moistures, marker="o", markersize=4,
                       label=pos, color=colors[idx % len(colors)],
                       linewidth=2)
                high_mask = np.array(moistures) > threshold
                if high_mask.any():
                    ax.scatter(np.array(times)[high_mask],
                              np.array(moistures)[high_mask],
                              color="red", s=60, zorder=5, marker="^")

        ax.axhline(y=threshold, color="red", linestyle="--",
                    label=f"阈值 ({threshold}%)", alpha=0.7)

        ax.set_xlabel("检测时间", fontsize=11)
        ax.set_ylabel("含水率 (%)", fontsize=11)
        title = "含水率变化趋势图"
        if position:
            title += f" - {position}"
        ax.set_title(title, fontsize=13, fontweight="bold")
        ax.legend(loc="best", fontsize=9)
        ax.grid(True, alpha=0.3)
        self.canvas.fig.autofmt_xdate()
        self.canvas.draw()

    def plot_position_comparison(self, records: List[Dict[str, Any]]):
        self.canvas.clear()
        ax = self.canvas.fig.add_subplot(111)

        if not records:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14)
            self.canvas.draw()
            return

        position_groups: Dict[str, List[float]] = {}
        for r in records:
            pos = r["measure_position"]
            if pos not in position_groups:
                position_groups[pos] = []
            position_groups[pos].append(r["moisture"])

        if not position_groups:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14)
            self.canvas.draw()
            return

        positions = list(position_groups.keys())
        data = [position_groups[p] for p in positions]

        bp = ax.boxplot(data, labels=positions, patch_artist=True,
                       showmeans=True, meanline=True)

        colors = ["#aec7e8", "#ffbb78", "#98df8a", "#ff9896",
                "#c5b0d5", "#c49c94", "#f7b6d2", "#c7c7c7"]
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_xlabel("检测位置", fontsize=11)
        ax.set_ylabel("含水率 (%)", fontsize=11)
        ax.set_title("不同位置含水率对比", fontsize=13, fontweight="bold")
        ax.grid(True, alpha=0.3, axis="y")
        self.canvas.draw()

    def plot_statistics_bar(self, stats_by_position: Dict[str, Dict[str, Any]],
                          threshold: float = 20.0):
        self.canvas.clear()
        ax = self.canvas.fig.add_subplot(111)

        if not stats_by_position:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14)
            self.canvas.draw()
            return

        positions = list(stats_by_position.keys())
        avgs = [stats_by_position[p]["avg"] for p in positions]
        maxs = [stats_by_position[p]["max"] for p in positions]
        mins = [stats_by_position[p]["min"] for p in positions]

        x = np.arange(len(positions))
        width = 0.25

        bars1 = ax.bar(x - width, mins, width, label="最小值", color="#98df8a")
        bars2 = ax.bar(x, avgs, width, label="平均值", color="#1f77b4")
        bars3 = ax.bar(x + width, maxs, width, label="最大值", color="#ff7f0e")

        ax.axhline(y=threshold, color="red", linestyle="--",
                    label=f"阈值 ({threshold}%)", alpha=0.7)

        ax.set_xlabel("检测位置", fontsize=11)
        ax.set_ylabel("含水率 (%)", fontsize=11)
        ax.set_title("各位置含水率统计", fontsize=13, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(positions, rotation=15)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")
        self.canvas.draw()

    def plot_building_risk_pie(self, overview_data: Dict[str, Any]):
        self.canvas.clear()
        ax = self.canvas.fig.add_subplot(111)

        high = overview_data.get("high_risk_components", 0)
        medium = overview_data.get("medium_risk_components", 0)
        normal = overview_data.get("normal_components", 0)

        if high == 0 and medium == 0 and normal == 0:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14)
            self.canvas.draw()
            return

        sizes = [high, medium, normal]
        labels = [f"高风险({high})", f"中风险({medium})", f"正常({normal})"]
        colors = ["#e74c3c", "#f39c12", "#2ecc71"]
        explode = (0.05, 0.05, 0)

        wedges, texts, autotexts = ax.pie(
            sizes, explode=explode, labels=labels, colors=colors,
            autopct="%1.1f%%", startangle=90, shadow=True
        )
        for t in autotexts:
            t.set_fontsize(10)
            t.set_color("white")
            t.set_fontweight("bold")

        ax.set_title("整体风险分布", fontsize=13, fontweight="bold")
        self.canvas.draw()

    def plot_building_risk_bar(self, overview_data: Dict[str, Any]):
        self.canvas.clear()
        ax = self.canvas.fig.add_subplot(111)

        buildings = overview_data.get("buildings", [])
        if not buildings:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14)
            self.canvas.draw()
            return

        names = [b["name"] for b in buildings]
        high_counts = [b["high_risk"] for b in buildings]
        medium_counts = [b["medium_risk"] for b in buildings]
        normal_counts = [b["normal"] for b in buildings]

        x = np.arange(len(names))
        width = 0.25

        ax.bar(x - width, high_counts, width, label="高风险", color="#e74c3c")
        ax.bar(x, medium_counts, width, label="中风险", color="#f39c12")
        ax.bar(x + width, normal_counts, width, label="正常", color="#2ecc71")

        ax.set_xlabel("建筑名称", fontsize=11)
        ax.set_ylabel("构件数量", fontsize=11)
        ax.set_title("各建筑风险分布对比", fontsize=13, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=15, ha="right")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")
        self.canvas.draw()

    def plot_comparison_bar(self, comparison_data: Dict[str, Any],
                            threshold: float = 20.0):
        self.canvas.clear()
        ax = self.canvas.fig.add_subplot(111)

        groups = comparison_data.get("groups", {})
        if not groups:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14)
            self.canvas.draw()
            return

        keys = list(groups.keys())
        avgs = [groups[k]["avg_moisture"] for k in keys]
        maxs = [groups[k]["max_moisture"] for k in keys]

        x = np.arange(len(keys))
        width = 0.35

        ax.bar(x - width / 2, avgs, width, label="平均含水率", color="#3498db")
        ax.bar(x + width / 2, maxs, width, label="最高含水率", color="#e67e22")
        ax.axhline(y=threshold, color="red", linestyle="--",
                    label=f"阈值 ({threshold}%)", alpha=0.7)

        ax.set_xlabel("分组", fontsize=11)
        ax.set_ylabel("含水率 (%)", fontsize=11)
        ax.set_title("横向对比分析", fontsize=13, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(keys, rotation=15, ha="right")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")
        self.canvas.draw()

    def plot_seasonal_chart(self, seasonal_data: Dict[str, Any],
                            threshold: float = 20.0):
        self.canvas.clear()
        ax = self.canvas.fig.add_subplot(111)

        seasons = ["春季", "夏季", "秋季", "冬季"]
        season_stats = seasonal_data.get("seasons", {})

        if not season_stats:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14)
            self.canvas.draw()
            return

        avgs = [season_stats.get(s, {}).get("avg", 0) for s in seasons]
        maxs = [season_stats.get(s, {}).get("max", 0) for s in seasons]
        mins = [season_stats.get(s, {}).get("min", 0) for s in seasons]

        x = np.arange(len(seasons))
        width = 0.25

        ax.bar(x - width, mins, width, label="最小值", color="#98df8a")
        ax.bar(x, avgs, width, label="平均值", color="#1f77b4")
        ax.bar(x + width, maxs, width, label="最大值", color="#ff7f0e")
        ax.axhline(y=threshold, color="red", linestyle="--",
                    label=f"阈值 ({threshold}%)", alpha=0.7)

        ax.set_xlabel("季节", fontsize=11)
        ax.set_ylabel("含水率 (%)", fontsize=11)
        ax.set_title("季节性波动分析", fontsize=13, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(seasons)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")
        self.canvas.draw()

    def plot_monthly_chart(self, seasonal_data: Dict[str, Any],
                           threshold: float = 20.0):
        self.canvas.clear()
        ax = self.canvas.fig.add_subplot(111)

        month_names = ["1月", "2月", "3月", "4月", "5月", "6月",
                       "7月", "8月", "9月", "10月", "11月", "12月"]
        monthly = seasonal_data.get("monthly_stats", {})

        avgs = [monthly.get(m, {}).get("avg", 0) for m in month_names]

        if all(v == 0 for v in avgs):
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14)
            self.canvas.draw()
            return

        x = np.arange(len(month_names))
        bars = ax.bar(x, avgs, 0.6, label="月平均含水率")

        for bar, val in zip(bars, avgs):
            if val > threshold:
                bar.set_color("#e74c3c")
            elif val > threshold * 0.9:
                bar.set_color("#f39c12")
            else:
                bar.set_color("#3498db")

        ax.axhline(y=threshold, color="red", linestyle="--",
                    label=f"阈值 ({threshold}%)", alpha=0.7)

        ax.set_xlabel("月份", fontsize=11)
        ax.set_ylabel("含水率 (%)", fontsize=11)
        ax.set_title("月度含水率分布", fontsize=13, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels(month_names)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")
        self.canvas.draw()

    def plot_trend_prediction(self, prediction_data: Dict[str, Any],
                              threshold: float = 20.0):
        self.canvas.clear()
        ax = self.canvas.fig.add_subplot(111)

        if not prediction_data.get("has_data", False):
            ax.text(0.5, 0.5, prediction_data.get("recommendation", "数据不足"),
                    ha="center", va="center", transform=ax.transAxes, fontsize=12)
            self.canvas.draw()
            return

        hist = prediction_data.get("historical_points", [])
        forecast = prediction_data.get("forecast_points", [])

        if hist:
            hist_times = [p["time"] for p in hist]
            hist_vals = [p["moisture"] for p in hist]
            ax.plot(hist_times, hist_vals, "bo-", label="历史数据",
                    markersize=5, linewidth=2)

        if forecast:
            fc_times = [p["time"] for p in forecast]
            fc_vals = [p["moisture"] for p in forecast]
            upper_vals = [p["upper"] for p in forecast]
            lower_vals = [p["lower"] for p in forecast]

            ax.plot(fc_times, fc_vals, "r--", label="预测趋势",
                    linewidth=2, alpha=0.8)
            ax.fill_between(fc_times, lower_vals, upper_vals,
                            color="red", alpha=0.15, label="95%置信区间")

        ax.axhline(y=threshold, color="red", linestyle=":",
                    label=f"阈值 ({threshold}%)", alpha=0.7)

        ax.set_xlabel("时间", fontsize=11)
        ax.set_ylabel("含水率 (%)", fontsize=11)
        ax.set_title("风险趋势预测", fontsize=13, fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        self.canvas.fig.autofmt_xdate()
        self.canvas.draw()

    def plot_risk_type_distribution(self, type_data: Dict[str, Any]):
        self.canvas.clear()
        ax = self.canvas.fig.add_subplot(111)

        if not type_data:
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14)
            self.canvas.draw()
            return

        types = list(type_data.keys())
        high_ratios = [type_data[t]["high_risk_ratio"] for t in types]
        colors = ["#e74c3c" if r > 30 else "#f39c12" if r > 10 else "#2ecc71"
                  for r in high_ratios]

        bars = ax.bar(types, high_ratios, color=colors, alpha=0.85)

        for bar, val in zip(bars, high_ratios):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                    f"{val}%", ha="center", va="bottom", fontsize=10, fontweight="bold")

        ax.set_xlabel("构件类型", fontsize=11)
        ax.set_ylabel("高风险占比 (%)", fontsize=11)
        ax.set_title("各构件类型高风险占比", fontsize=13, fontweight="bold")
        ax.axhline(y=30, color="#e74c3c", linestyle="--", alpha=0.5, label="警戒(30%)")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")
        self.canvas.draw()
