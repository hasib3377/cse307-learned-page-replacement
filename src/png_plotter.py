"""
CSE-307: Operating Systems - Pure Python PNG Image Generator
Uses only Python Standard Library (zlib, struct) to generate high-resolution
PNG charts without requiring matplotlib, PIL, or any third-party packages.
"""

import zlib
import struct
import os
import csv
from typing import List, Tuple, Dict


class Canvas:
    def __init__(self, width: int, height: int, bg_color: Tuple[int, int, int] = (255, 255, 255)):
        self.width = width
        self.height = height
        self.bg = bg_color
        # Buffer as flat bytearray (R, G, B per pixel)
        self.pixels = bytearray(width * height * 3)
        for i in range(0, len(self.pixels), 3):
            self.pixels[i] = bg_color[0]
            self.pixels[i+1] = bg_color[1]
            self.pixels[i+2] = bg_color[2]

    def set_pixel(self, x: int, y: int, color: Tuple[int, int, int]):
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = (y * self.width + x) * 3
            self.pixels[idx] = color[0]
            self.pixels[idx+1] = color[1]
            self.pixels[idx+2] = color[2]

    def draw_rect(self, x: int, y: int, w: int, h: int, color: Tuple[int, int, int], fill: bool = True):
        for cy in range(max(0, y), min(self.height, y + h)):
            for cx in range(max(0, x), min(self.width, x + w)):
                if fill or cy == y or cy == y + h - 1 or cx == x or cx == x + w - 1:
                    self.set_pixel(cx, cy, color)

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, color: Tuple[int, int, int], width: int = 1, dashed: bool = False):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        step = 0

        while True:
            step += 1
            if not dashed or (step % 10 < 6):
                for wx in range(-width // 2, width // 2 + 1):
                    for wy in range(-width // 2, width // 2 + 1):
                        self.set_pixel(x0 + wx, y0 + wy, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def draw_circle(self, cx: int, cy: int, r: int, color: Tuple[int, int, int], fill: bool = True):
        for y in range(-r, r + 1):
            for x in range(-r, r + 1):
                if fill:
                    if x*x + y*y <= r*r:
                        self.set_pixel(cx + x, cy + y, color)
                else:
                    if abs(x*x + y*y - r*r) <= r:
                        self.set_pixel(cx + x, cy + y, color)

    def save_png(self, filepath: str):
        # 8-byte PNG header
        header = b"\x89PNG\r\n\x1a\n"

        # IHDR chunk: width(4), height(4), bit_depth(1=8), color_type(1=2 RGB), comp(1=0), filter(1=0), interlace(1=0)
        ihdr_data = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
        ihdr_chunk = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

        # IDAT chunk: filter byte (0) preceding each scanline
        raw_scanlines = bytearray()
        stride = self.width * 3
        for y in range(self.height):
            raw_scanlines.append(0)  # Filter type 0 (None)
            start = y * stride
            raw_scanlines.extend(self.pixels[start:start+stride])

        compressed = zlib.compress(raw_scanlines, level=6)
        idat_crc = zlib.crc32(b"IDAT" + compressed)
        idat_chunk = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(">I", idat_crc)

        # IEND chunk
        iend_crc = zlib.crc32(b"IEND")
        iend_chunk = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

        with open(filepath, "wb") as f:
            f.write(header + ihdr_chunk + idat_chunk + iend_chunk)


def render_all_png_figures(results_dir: str):
    print("Rendering native high-resolution PNG figures...")

    # Load sweep data
    sweep_path = os.path.join(results_dir, "frame_sweep_results.csv")
    records = []
    with open(sweep_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append({
                "num_frames": int(row["num_frames"]),
                "policy": row["policy"],
                "overall_hit_ratio": float(row["overall_hit_ratio"]),
                "pre_hit_ratio": float(row["pre_hit_ratio"]),
                "post_hit_ratio": float(row["post_hit_ratio"])
            })

    colors = {
        "FIFO": (228, 26, 28),             # Red
        "LRU": (55, 126, 184),             # Blue
        "Optimal (Belady)": (77, 175, 74),  # Green
        "Learned-LRU+": (152, 78, 163)     # Purple
    }

    # -------------------------------------------------------------
    # Figure 1: Hit Ratio vs Frame Capacity (PNG)
    # -------------------------------------------------------------
    c1 = Canvas(800, 480, (255, 255, 255))
    px, py, pw, ph = 90, 60, 650, 360
    # Background and border
    c1.draw_rect(px, py, pw, ph, (250, 250, 250), fill=True)
    c1.draw_rect(px, py, pw, ph, (180, 180, 180), fill=False)

    # Gridlines
    for y_pct in range(0, 101, 20):
        y_pos = int(py + ph - (y_pct / 100.0) * ph)
        c1.draw_line(px, y_pos, px + pw, y_pos, (220, 220, 220), width=1, dashed=True)

    frame_sizes = [4, 8, 12, 16, 24, 32]
    for fs in frame_sizes:
        x_pos = int(px + ((fs - 4) / (32 - 4)) * pw)
        c1.draw_line(x_pos, py, x_pos, py + ph, (220, 220, 220), width=1, dashed=True)

    # Lines for policies
    for pol, col in colors.items():
        pts = []
        for fs in frame_sizes:
            sub = [r for r in records if r["policy"] == pol and r["num_frames"] == fs]
            if sub:
                hr = sub[0]["overall_hit_ratio"]
                x_pos = int(px + ((fs - 4) / 28.0) * pw)
                y_pos = int(py + ph - hr * ph)
                pts.append((x_pos, y_pos))
        for i in range(len(pts) - 1):
            c1.draw_line(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1], col, width=3)
        for pt in pts:
            c1.draw_circle(pt[0], pt[1], 5, col, fill=True)
            c1.draw_circle(pt[0], pt[1], 5, (255, 255, 255), fill=False)

    # Legend box
    leg_x, leg_y = px + 20, py + 20
    c1.draw_rect(leg_x, leg_y, 180, 100, (255, 255, 255), fill=True)
    c1.draw_rect(leg_x, leg_y, 180, 100, (200, 200, 200), fill=False)
    for idx, (pol, col) in enumerate(colors.items()):
        ly = leg_y + 15 + idx * 22
        c1.draw_line(leg_x + 10, ly, leg_x + 35, ly, col, width=3)
        c1.draw_circle(leg_x + 22, ly, 4, col, fill=True)

    c1.save_png(os.path.join(results_dir, "fig1_hit_ratio_by_frames.png"))

    # -------------------------------------------------------------
    # Figure 3: Performance Degradation Bar Chart (PNG)
    # -------------------------------------------------------------
    c3 = Canvas(800, 480, (255, 255, 255))
    c3.draw_rect(px, py, pw, ph, (250, 250, 250), fill=True)
    c3.draw_rect(px, py, pw, ph, (180, 180, 180), fill=False)

    for y_pct in range(0, 101, 20):
        y_pos = int(py + ph - (y_pct / 100.0) * ph)
        c3.draw_line(px, y_pos, px + pw, y_pos, (220, 220, 220), width=1, dashed=True)

    k16_records = [r for r in records if r["num_frames"] == 16]
    group_w = pw // len(k16_records)
    bar_w = int(group_w * 0.32)

    for idx, rec in enumerate(k16_records):
        cx = int(px + (idx + 0.5) * group_w)
        bx1 = cx - bar_w - 4
        bx2 = cx + 4

        h1 = int(rec["pre_hit_ratio"] * ph)
        h2 = int(rec["post_hit_ratio"] * ph)

        # Pre-shift (Navy)
        c3.draw_rect(bx1, py + ph - h1, bar_w, h1, (43, 92, 143), fill=True)
        # Post-shift (Orange)
        c3.draw_rect(bx2, py + ph - h2, bar_w, h2, (217, 95, 2), fill=True)

    # Legend
    c3.draw_rect(px + pw - 220, py + 20, 200, 60, (255, 255, 255), fill=True)
    c3.draw_rect(px + pw - 220, py + 20, 200, 60, (200, 200, 200), fill=False)
    c3.draw_rect(px + pw - 205, py + 30, 16, 16, (43, 92, 143), fill=True)
    c3.draw_rect(px + pw - 205, py + 52, 16, 16, (217, 95, 2), fill=True)

    c3.save_png(os.path.join(results_dir, "fig3_shift_degradation.png"))

    # -------------------------------------------------------------
    # Figure 4: Confidence Calibration (PNG)
    # -------------------------------------------------------------
    c4 = Canvas(600, 500, (255, 255, 255))
    cx, cy, cw, ch = 80, 50, 470, 390
    c4.draw_rect(cx, cy, cw, ch, (250, 250, 250), fill=True)
    c4.draw_rect(cx, cy, cw, ch, (180, 180, 180), fill=False)

    # Grid
    for g in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        gx = int(cx + ((g - 0.5) / 0.5) * cw)
        gy = int(cy + ch - ((g - 0.4) / 0.6) * ch)
        c4.draw_line(gx, cy, gx, cy + ch, (220, 220, 220), width=1, dashed=True)
        c4.draw_line(cx, gy, cx + cw, gy, (220, 220, 220), width=1, dashed=True)

    # Diagonal ideal line (y=x)
    diag_start_x = int(cx)
    diag_start_y = int(cy + ch - ((0.5 - 0.4) / 0.6) * ch)
    diag_end_x = int(cx + cw)
    diag_end_y = int(cy)
    c4.draw_line(diag_start_x, diag_start_y, diag_end_x, diag_end_y, (100, 100, 100), width=2, dashed=True)

    # Load calibration csv
    calib_path = os.path.join(results_dir, "confidence_calibration.csv")
    calib_pts = []
    with open(calib_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row["count"]) > 0:
                conf = float(row["avg_confidence"])
                acc = float(row["empirical_accuracy"])
                px_val = int(cx + ((conf - 0.5) / 0.5) * cw)
                py_val = int(cy + ch - ((acc - 0.4) / 0.6) * ch)
                calib_pts.append((px_val, py_val))

    for i in range(len(calib_pts) - 1):
        c4.draw_line(calib_pts[i][0], calib_pts[i][1], calib_pts[i+1][0], calib_pts[i+1][1], (44, 160, 44), width=3)
    for pt in calib_pts:
        c4.draw_rect(pt[0] - 4, pt[1] - 4, 8, 8, (44, 160, 44), fill=True)

    c4.save_png(os.path.join(results_dir, "fig4_confidence_calibration.png"))

    # -------------------------------------------------------------
    # Figure 2: Cumulative Faults Timeline (PNG)
    # -------------------------------------------------------------
    c2 = Canvas(800, 480, (255, 255, 255))
    c2.draw_rect(px, py, pw, ph, (250, 250, 250), fill=True)
    c2.draw_rect(px, py, pw, ph, (180, 180, 180), fill=False)

    # Grid
    for y_v in range(0, 9001, 1500):
        y_pos = int(py + ph - (y_v / 8500.0) * ph)
        c2.draw_line(px, y_pos, px + pw, y_pos, (220, 220, 220), width=1, dashed=True)

    # Shift indicator line at t=5000 (halfway)
    shift_px = int(px + pw * 0.5)
    c2.draw_line(shift_px, py, shift_px, py + ph, (217, 95, 2), width=2, dashed=True)

    # Approximate timeline endpoints from results
    # k=16 total faults: FIFO=5344 (1074 pre, 4270 post), LRU=4954 (663 pre, 4291 post), Opt=2730 (376 pre, 2354 post), Learned=4731 (498 pre, 4233 post)
    timeline_milestones = {
        "FIFO": [(px, py + ph), (shift_px, int(py + ph - (1074 / 8500.0) * ph)), (px + pw, int(py + ph - (5344 / 8500.0) * ph))],
        "LRU": [(px, py + ph), (shift_px, int(py + ph - (663 / 8500.0) * ph)), (px + pw, int(py + ph - (4954 / 8500.0) * ph))],
        "Optimal (Belady)": [(px, py + ph), (shift_px, int(py + ph - (376 / 8500.0) * ph)), (px + pw, int(py + ph - (2730 / 8500.0) * ph))],
        "Learned-LRU+": [(px, py + ph), (shift_px, int(py + ph - (498 / 8500.0) * ph)), (px + pw, int(py + ph - (4731 / 8500.0) * ph))]
    }
    for pol, pts in timeline_milestones.items():
        col = colors[pol]
        for i in range(len(pts) - 1):
            c2.draw_line(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1], col, width=3)

    c2.draw_rect(px + 20, py + 20, 180, 100, (255, 255, 255), fill=True)
    c2.draw_rect(px + 20, py + 20, 180, 100, (200, 200, 200), fill=False)
    for idx, (pol, col) in enumerate(colors.items()):
        ly = py + 35 + idx * 22
        c2.draw_line(px + 30, ly, px + 55, ly, col, width=3)

    c2.save_png(os.path.join(results_dir, "fig2_cumulative_faults_timeline.png"))

    print("All PNG raster figures successfully generated!")


if __name__ == "__main__":
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    results_dir = os.path.join(os.path.dirname(CURRENT_DIR), "results") if "src" in CURRENT_DIR else os.path.join(CURRENT_DIR, "results")
    render_all_png_figures(results_dir)
