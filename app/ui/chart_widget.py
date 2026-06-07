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
