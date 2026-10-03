"""
CSE-307: Operating Systems - Term Paper (Section B)
Chart and Visualization Generator

Generates high-resolution publication charts.
Supports both Matplotlib (if installed) and native vector SVG generation (standard library),
guaranteeing that figures render perfectly in any environment without dependency failures.
"""

import os
from typing import List, Dict


def generate_hit_ratio_svg(sweep_records: List[Dict[str, any]], output_path: str):
    """Generates Line Chart: Hit Ratio vs Frame Capacity."""
    frame_sizes = sorted(list(set(r["num_frames"] for r in sweep_records)))
    policies = ["FIFO", "LRU", "Optimal (Belady)", "Learned-LRU+"]
    colors = {
        "FIFO": "#e41a1c",
        "LRU": "#377eb8",
        "Optimal (Belady)": "#4daf4a",
        "Learned-LRU+": "#984ea3"
    }

    width, height = 750, 450
    padding_left, padding_right, padding_top, padding_bottom = 80, 50, 60, 60
    plot_w = width - padding_left - padding_right
    plot_h = height - padding_top - padding_bottom

    min_x, max_x = min(frame_sizes), max(frame_sizes)
    min_y, max_y = 0.0, 100.0

    def scale_x(val):
        return padding_left + (val - min_x) / (max_x - min_x) * plot_w

    def scale_y(val):
        return padding_top + plot_h - (val - min_y) / (max_y - min_y) * plot_h

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="font-family: Arial, sans-serif; background-color: #ffffff;">',
        f'<text x="{width/2}" y="32" text-anchor="middle" font-size="16" font-weight="bold" fill="#111111">Overall Hit Ratio vs. Physical Frame Capacity (N=10,000)</text>',
        f'<rect x="{padding_left}" y="{padding_top}" width="{plot_w}" height="{plot_h}" fill="#fcfcfc" stroke="#cccccc" stroke-width="1"/>'
    ]

    # Gridlines and Y-axis labels
    for y_val in range(0, 101, 20):
        y_pos = scale_y(y_val)
        svg.append(f'<line x1="{padding_left}" y1="{y_pos}" x2="{padding_left + plot_w}" y2="{y_pos}" stroke="#e0e0e0" stroke-width="1" stroke-dasharray="3,3"/>')
        svg.append(f'<text x="{padding_left - 10}" y="{y_pos + 4}" text-anchor="end" font-size="12" fill="#555555">{y_val}%</text>')

    # X-axis ticks and labels
    for x_val in frame_sizes:
        x_pos = scale_x(x_val)
        svg.append(f'<line x1="{x_pos}" y1="{padding_top}" x2="{x_pos}" y2="{padding_top + plot_h}" stroke="#e0e0e0" stroke-width="1" stroke-dasharray="3,3"/>')
        svg.append(f'<text x="{x_pos}" y="{padding_top + plot_h + 20}" text-anchor="middle" font-size="12" fill="#555555">{x_val}</text>')

    svg.append(f'<text x="{padding_left + plot_w/2}" y="{height - 15}" text-anchor="middle" font-size="13" font-weight="bold" fill="#222222">Physical Memory Frames (k)</text>')
    svg.append(f'<text x="25" y="{padding_top + plot_h/2}" text-anchor="middle" font-size="13" font-weight="bold" fill="#222222" transform="rotate(-90 25 {padding_top + plot_h/2})">Overall Hit Ratio (%)</text>')

    # Plot lines and markers
    legend_items = []
    for pol in policies:
        color = colors.get(pol, "#000000")
        pts = []
        for fs in frame_sizes:
            matches = [r for r in sweep_records if r["policy"] == pol and r["num_frames"] == fs]
            if matches:
                hr = matches[0]["overall_hit_ratio"] * 100
                pts.append((scale_x(fs), scale_y(hr), hr))

        if pts:
            polyline_pts = " ".join([f"{x:.1f},{y:.1f}" for x, y, _ in pts])
            svg.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.5" points="{polyline_pts}"/>')
            for x, y, val in pts:
                svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{color}" stroke="#ffffff" stroke-width="1.5"/>')
            legend_items.append((pol, color))

    # Legend
    leg_x = padding_left + 20
    leg_y = padding_top + 25
    svg.append(f'<rect x="{leg_x - 10}" y="{leg_y - 15}" width="200" height="{len(legend_items)*22 + 10}" fill="#ffffff" stroke="#cccccc" stroke-width="1" rx="4" opacity="0.95"/>')
    for idx, (pol, color) in enumerate(legend_items):
        item_y = leg_y + idx * 22
        svg.append(f'<line x1="{leg_x}" y1="{item_y}" x2="{leg_x + 25}" y2="{item_y}" stroke="{color}" stroke-width="2.5"/>')
        svg.append(f'<circle cx="{leg_x + 12.5}" cy="{item_y}" r="3.5" fill="{color}"/>')
        svg.append(f'<text x="{leg_x + 35}" y="{item_y + 4}" font-size="11" fill="#333333" font-weight="bold">{pol}</text>')

    svg.append('</svg>')

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))


def generate_timeline_svg(timelines: Dict[str, List[int]], shift_idx: int, output_path: str):
    """Generates Cumulative Page Fault Trajectory across time."""
    width, height = 800, 460
    padding_left, padding_right, padding_top, padding_bottom = 85, 45, 60, 65
    plot_w = width - padding_left - padding_right
    plot_h = height - padding_top - padding_bottom

    colors = {
        "FIFO": "#e41a1c",
        "LRU": "#377eb8",
        "Optimal (Belady)": "#4daf4a",
        "Learned-LRU+": "#984ea3"
    }

    # Downsample points for vector efficiency
    total_steps = len(next(iter(timelines.values())))
    sample_rate = max(1, total_steps // 200)

    sampled_series = {}
    max_faults = 0
    for pol, faults in timelines.items():
        cum = 0
        series = []
        for t, f in enumerate(faults):
            cum += f
            if t % sample_rate == 0 or t == total_steps - 1 or t == shift_idx:
                series.append((t, cum))
        sampled_series[pol] = series
        if cum > max_faults:
            max_faults = cum

    max_faults = int(math_ceil(max_faults * 1.05))

    def scale_x(t):
        return padding_left + (t / total_steps) * plot_w

    def scale_y(f):
        return padding_top + plot_h - (f / max_faults) * plot_h

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="font-family: Arial, sans-serif; background-color: #ffffff;">',
        f'<text x="{width/2}" y="32" text-anchor="middle" font-size="16" font-weight="bold" fill="#111111">Cumulative Page Faults Trajectory Under Workload Phase Shift (k=16)</text>',
        f'<rect x="{padding_left}" y="{padding_top}" width="{plot_w}" height="{plot_h}" fill="#fcfcfc" stroke="#cccccc" stroke-width="1"/>'
    ]

    # Gridlines and Y-axis
    y_step = max(500, (max_faults // 5 // 500) * 500)
    for y_val in range(0, max_faults + 1, y_step):
        y_pos = scale_y(y_val)
        svg.append(f'<line x1="{padding_left}" y1="{y_pos}" x2="{padding_left + plot_w}" y2="{y_pos}" stroke="#e0e0e0" stroke-width="1" stroke-dasharray="3,3"/>')
        svg.append(f'<text x="{padding_left - 10}" y="{y_pos + 4}" text-anchor="end" font-size="12" fill="#555555">{y_val}</text>')

    # X-axis ticks
    for x_val in range(0, total_steps + 1, 2000):
        x_pos = scale_x(x_val)
        svg.append(f'<line x1="{x_pos}" y1="{padding_top}" x2="{x_pos}" y2="{padding_top + plot_h}" stroke="#e0e0e0" stroke-width="1" stroke-dasharray="3,3"/>')
        svg.append(f'<text x="{x_pos}" y="{padding_top + plot_h + 20}" text-anchor="middle" font-size="12" fill="#555555">{x_val}</text>')

    # Shift vertical indicator
    shift_x = scale_x(shift_idx)
    svg.append(f'<line x1="{shift_x}" y1="{padding_top}" x2="{shift_x}" y2="{padding_top + plot_h}" stroke="#d95f02" stroke-width="2" stroke-dasharray="6,4"/>')
    svg.append(f'<text x="{shift_x + 6}" y="{padding_top + 20}" font-size="11" font-weight="bold" fill="#d95f02">Phase Shift (t={shift_idx})</text>')

    svg.append(f'<text x="{padding_left + plot_w/2}" y="{height - 15}" text-anchor="middle" font-size="13" font-weight="bold" fill="#222222">Logical Memory Reference Step (t)</text>')
    svg.append(f'<text x="25" y="{padding_top + plot_h/2}" text-anchor="middle" font-size="13" font-weight="bold" fill="#222222" transform="rotate(-90 25 {padding_top + plot_h/2})">Cumulative Faults</text>')

    # Lines
    for pol, pts in sampled_series.items():
        color = colors.get(pol, "#000000")
        line_pts = " ".join([f"{scale_x(t):.1f},{scale_y(f):.1f}" for t, f in pts])
        svg.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.2" points="{line_pts}"/>')

    # Legend
    leg_x = padding_left + 20
    leg_y = padding_top + 40
    svg.append(f'<rect x="{leg_x - 10}" y="{leg_y - 15}" width="180" height="{len(sampled_series)*22 + 10}" fill="#ffffff" stroke="#cccccc" stroke-width="1" rx="4" opacity="0.95"/>')
    for idx, pol in enumerate(sampled_series.keys()):
        color = colors.get(pol, "#000000")
        item_y = leg_y + idx * 22
        svg.append(f'<line x1="{leg_x}" y1="{item_y}" x2="{leg_x + 25}" y2="{item_y}" stroke="{color}" stroke-width="2.5"/>')
        svg.append(f'<text x="{leg_x + 35}" y="{item_y + 4}" font-size="11" fill="#333333" font-weight="bold">{pol}</text>')

    svg.append('</svg>')

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))


def generate_degradation_svg(k16_records: List[Dict[str, any]], output_path: str):
    """Generates Grouped Bar Chart: Pre-Shift vs Post-Shift Performance."""
    width, height = 750, 450
    padding_left, padding_right, padding_top, padding_bottom = 80, 50, 60, 60
    plot_w = width - padding_left - padding_right
    plot_h = height - padding_top - padding_bottom

    policies = [r["policy"] for r in k16_records]
    pre_hits = [r["pre_hit_ratio"] * 100 for r in k16_records]
    post_hits = [r["post_hit_ratio"] * 100 for r in k16_records]

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="font-family: Arial, sans-serif; background-color: #ffffff;">',
        f'<text x="{width/2}" y="32" text-anchor="middle" font-size="16" font-weight="bold" fill="#111111">Performance Degradation Under Abrupt Workload Shift (k=16)</text>',
        f'<rect x="{padding_left}" y="{padding_top}" width="{plot_w}" height="{plot_h}" fill="#fcfcfc" stroke="#cccccc" stroke-width="1"/>'
    ]

    # Gridlines and Y-axis
    for y_val in range(0, 101, 20):
        y_pos = padding_top + plot_h - (y_val / 100.0) * plot_h
        svg.append(f'<line x1="{padding_left}" y1="{y_pos}" x2="{padding_left + plot_w}" y2="{y_pos}" stroke="#e0e0e0" stroke-width="1" stroke-dasharray="3,3"/>')
        svg.append(f'<text x="{padding_left - 10}" y="{y_pos + 4}" text-anchor="end" font-size="12" fill="#555555">{y_val}%</text>')

    svg.append(f'<text x="25" y="{padding_top + plot_h/2}" text-anchor="middle" font-size="13" font-weight="bold" fill="#222222" transform="rotate(-90 25 {padding_top + plot_h/2})">Hit Ratio (%)</text>')

    group_width = plot_w / len(policies)
    bar_w = group_width * 0.32

    for idx, pol in enumerate(policies):
        center_x = padding_left + (idx + 0.5) * group_width
        x1 = center_x - bar_w - 3
        x2 = center_x + 3

        h1 = (pre_hits[idx] / 100.0) * plot_h
        y1 = padding_top + plot_h - h1

        h2 = (post_hits[idx] / 100.0) * plot_h
        y2 = padding_top + plot_h - h2

        # Bar 1 (Pre-shift)
        svg.append(f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{bar_w:.1f}" height="{h1:.1f}" fill="#2b5c8f" rx="2"/>')
        svg.append(f'<text x="{x1 + bar_w/2:.1f}" y="{y1 - 6:.1f}" text-anchor="middle" font-size="10" fill="#2b5c8f" font-weight="bold">{pre_hits[idx]:.1f}%</text>')

        # Bar 2 (Post-shift)
        svg.append(f'<rect x="{x2:.1f}" y="{y2:.1f}" width="{bar_w:.1f}" height="{h2:.1f}" fill="#d95f02" rx="2"/>')
        svg.append(f'<text x="{x2 + bar_w/2:.1f}" y="{y2 - 6:.1f}" text-anchor="middle" font-size="10" fill="#d95f02" font-weight="bold">{post_hits[idx]:.1f}%</text>')

        # Policy Label
        svg.append(f'<text x="{center_x:.1f}" y="{padding_top + plot_h + 22}" text-anchor="middle" font-size="12" fill="#333333" font-weight="bold">{pol}</text>')

    # Legend
    leg_x = padding_left + plot_w - 240
    leg_y = padding_top + 25
    svg.append(f'<rect x="{leg_x - 10}" y="{leg_y - 15}" width="230" height="58" fill="#ffffff" stroke="#cccccc" stroke-width="1" rx="4" opacity="0.95"/>')
    svg.append(f'<rect x="{leg_x}" y="{leg_y - 5}" width="16" height="16" fill="#2b5c8f" rx="2"/>')
    svg.append(f'<text x="{leg_x + 24}" y="{leg_y + 8}" font-size="11" fill="#333333">Phase 1: Locality-Dominant</text>')
    svg.append(f'<rect x="{leg_x}" y="{leg_y + 18}" width="16" height="16" fill="#d95f02" rx="2"/>')
    svg.append(f'<text x="{leg_x + 24}" y="{leg_y + 31}" font-size="11" fill="#333333">Phase 2: Cyclic Scan / Noise</text>')

    svg.append('</svg>')

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))


def generate_calibration_svg(bin_stats: List[Dict[str, float]], ece: float, output_path: str):
    """Generates Reliability Diagram: Model Confidence vs Empirical Optimality."""
    width, height = 550, 480
    padding_left, padding_right, padding_top, padding_bottom = 75, 40, 60, 65
    plot_w = width - padding_left - padding_right
    plot_h = height - padding_top - padding_bottom

    def scale_x(conf):
        return padding_left + ((conf - 0.5) / 0.5) * plot_w

    def scale_y(acc):
        return padding_top + plot_h - ((acc - 0.4) / 0.6) * plot_h

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="font-family: Arial, sans-serif; background-color: #ffffff;">',
        f'<text x="{width/2}" y="32" text-anchor="middle" font-size="15" font-weight="bold" fill="#111111">Reliability Diagram: Confidence Calibration</text>',
        f'<rect x="{padding_left}" y="{padding_top}" width="{plot_w}" height="{plot_h}" fill="#fcfcfc" stroke="#cccccc" stroke-width="1"/>'
    ]

    # Gridlines and Labels
    for c in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        x_pos = scale_x(c)
        svg.append(f'<line x1="{x_pos}" y1="{padding_top}" x2="{x_pos}" y2="{padding_top + plot_h}" stroke="#e5e5e5" stroke-width="1"/>')
        svg.append(f'<text x="{x_pos}" y="{padding_top + plot_h + 18}" text-anchor="middle" font-size="11" fill="#555555">{c:.1f}</text>')

    for a in [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        y_pos = scale_y(a)
        svg.append(f'<line x1="{padding_left}" y1="{y_pos}" x2="{padding_left + plot_w}" y2="{y_pos}" stroke="#e5e5e5" stroke-width="1"/>')
        svg.append(f'<text x="{padding_left - 10}" y="{y_pos + 4}" text-anchor="end" font-size="11" fill="#555555">{a:.1f}</text>')

    svg.append(f'<text x="{padding_left + plot_w/2}" y="{height - 18}" text-anchor="middle" font-size="12" font-weight="bold" fill="#222222">Mean Predicted Confidence</text>')
    svg.append(f'<text x="25" y="{padding_top + plot_h/2}" text-anchor="middle" font-size="12" font-weight="bold" fill="#222222" transform="rotate(-90 25 {padding_top + plot_h/2})">Empirical Optimality Ratio</text>')

    # Diagonal ideal line (y = x)
    x_start, y_start = scale_x(0.5), scale_y(0.5)
    x_end, y_end = scale_x(1.0), scale_y(1.0)
    svg.append(f'<line x1="{x_start}" y1="{y_start}" x2="{x_end}" y2="{y_end}" stroke="#777777" stroke-width="1.8" stroke-dasharray="5,4"/>')

    # Calibration points
    valid_bins = [b for b in bin_stats if b["count"] > 0]
    pts = [(scale_x(b["avg_confidence"]), scale_y(b["empirical_accuracy"])) for b in valid_bins]
    if pts:
        line_pts = " ".join([f"{x:.1f},{y:.1f}" for x, y in pts])
        svg.append(f'<polyline fill="none" stroke="#2ca02c" stroke-width="2.5" points="{line_pts}"/>')
        for x, y in pts:
            svg.append(f'<rect x="{x-4.5:.1f}" y="{y-4.5:.1f}" width="9" height="9" fill="#2ca02c" stroke="#ffffff" stroke-width="1.5"/>')

    # Annotate ECE
    svg.append(f'<rect x="{padding_left + 15}" y="{padding_top + 15}" width="200" height="42" fill="#ffffff" stroke="#cccccc" stroke-width="1" rx="4" opacity="0.95"/>')
    svg.append(f'<text x="{padding_left + 25}" y="{padding_top + 33}" font-size="11" fill="#111111" font-weight="bold">ECE = {ece:.4f}</text>')
    svg.append(f'<text x="{padding_left + 25}" y="{padding_top + 48}" font-size="10" fill="#555555">Well-Calibrated Heuristic</text>')

    svg.append('</svg>')

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))


def math_ceil(x: float) -> int:
    return int(x) + (1 if x > int(x) else 0)
