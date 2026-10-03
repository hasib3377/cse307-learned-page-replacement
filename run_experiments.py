"""
CSE-307: Operating Systems - Term Paper (Section B)
Track 1 & Bonus Track - Main Experimentation Pipeline

Runs comprehensive simulations comparing FIFO, LRU, Optimal (Belady),
and Learned-LRU+ under the workload phase shift, logs raw metrics to CSV,
and generates publication-quality figures for the term paper.
"""

import os
import sys
import csv
from typing import List, Dict

# Ensure local source directory is importable
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from src.algorithms import simulate_fifo, simulate_lru, simulate_optimal
from src.workload import WorkloadGenerator
from src.learned_policy import simulate_learned, FeatureExtractor, LightweightClassifier, build_training_dataset
from src.explanation_eval import ExplanationEngine, evaluate_calibration, EvictionExplanation
from src.chart_generator import (
    generate_hit_ratio_svg,
    generate_timeline_svg,
    generate_degradation_svg,
    generate_calibration_svg
)

# Optional matplotlib import
HAS_MATPLOTLIB = False
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def run_all_experiments():
    print("=" * 70)
    print("CSE-307: LEARNING-AUGMENTED OS HEURISTICS (TRACK 1 & BONUS TRACK)")
    print("=" * 70)

    results_dir = os.path.join(CURRENT_DIR, "results")
    os.makedirs(results_dir, exist_ok=True)

    # 1. Generate Synthetic Workload with Deliberate Shift
    total_refs = 10000
    shift_ratio = 0.5
    gen = WorkloadGenerator(total_pages=80, seed=42)
    trace, shift_idx, meta = gen.generate_trace(
        total_references=total_refs,
        shift_ratio=shift_ratio,
        working_set_size=12,
        scan_size=24
    )
    print(f"[*] Generated trace of {len(trace)} accesses. Phase shift at index {shift_idx}.")

    # Save workload trace sample
    trace_sample_path = os.path.join(results_dir, "trace_sample.csv")
    with open(trace_sample_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestep", "page_id", "phase"])
        for t, p in enumerate(trace[:1000]):
            phase = "Phase 1 (Locality)" if t < shift_idx else "Phase 2 (Shift)"
            writer.writerow([t, p, phase])

    # 2. Frame Sweep Experiment (k = 4, 8, 12, 16, 24, 32)
    frame_sizes = [4, 8, 12, 16, 24, 32]
    sweep_records: List[Dict[str, any]] = []

    print("\n[Phase 1] Executing Frame Capacity Sweep across policies...")
    for frames in frame_sizes:
        res_fifo = simulate_fifo(trace, frames)
        res_lru = simulate_lru(trace, frames)
        res_opt = simulate_optimal(trace, frames)
        res_learned = simulate_learned(trace, frames, warmup_steps=1500)

        for res in [res_fifo, res_lru, res_opt, res_learned]:
            metrics = res.compute_phase_metrics(shift_idx)
            sweep_records.append({
                "num_frames": frames,
                "policy": res.policy_name,
                "total_faults": res.faults,
                "overall_hit_ratio": round(res.hit_ratio, 4),
                "pre_hit_ratio": round(metrics["pre_hit_ratio"], 4),
                "post_hit_ratio": round(metrics["post_hit_ratio"], 4),
                "degradation": round(metrics["pre_hit_ratio"] - metrics["post_hit_ratio"], 4)
            })

    # Save Frame Sweep CSV
    sweep_csv_path = os.path.join(results_dir, "frame_sweep_results.csv")
    with open(sweep_csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(sweep_records[0].keys()))
        writer.writeheader()
        writer.writerows(sweep_records)
    print(f"-> Saved frame sweep metrics to: {sweep_csv_path}")

    # Print Summary Table for k = 16
    print("\nSummary for Frame Size k = 16:")
    print("-" * 65)
    print(f"{'Policy':<18} | {'Overall Hit%':<12} | {'Pre-Shift Hit%':<14} | {'Post-Shift Hit%':<14}")
    print("-" * 65)
    for rec in sweep_records:
        if rec["num_frames"] == 16:
            print(f"{rec['policy']:<18} | {rec['overall_hit_ratio']*100:>10.2f}% | {rec['pre_hit_ratio']*100:>12.2f}% | {rec['post_hit_ratio']*100:>12.2f}%")
    print("-" * 65)

    # 3. Timeline Simulation for Detailed Fault Accumulation (k = 16)
    focus_frames = 16
    print(f"\n[Phase 2] Generating Timeline Trajectory for k = {focus_frames}...")
    run_fifo = simulate_fifo(trace, focus_frames)
    run_lru = simulate_lru(trace, focus_frames)
    run_opt = simulate_optimal(trace, focus_frames)
    run_learned = simulate_learned(trace, focus_frames, warmup_steps=1500)

    # 4. Bonus Track: Explanation Generation and Confidence Calibration
    print("\n[Phase 3] Running Bonus Track: Explanation Confidence Calibration...")
    engine = ExplanationEngine()
    explanations: List[EvictionExplanation] = []

    # Re-run learned simulation with explanation hook
    X_train, y_train = build_training_dataset(trace[:1500], focus_frames)
    clf = LightweightClassifier()
    clf.train(X_train, y_train)

    extractor = FeatureExtractor()
    active_frames = set()

    # Pre-index future access for evaluation
    future_lookup: Dict[int, List[int]] = {}
    for idx, p in enumerate(trace):
        if p not in future_lookup:
            future_lookup[p] = []
        future_lookup[p].append(idx)

    for t, page in enumerate(trace):
        extractor.record_access(page, t)
        if page not in active_frames:
            if len(active_frames) < focus_frames:
                active_frames.add(page)
                extractor.record_arrival(page, t)
            else:
                scores = {}
                features_map = {}
                for cand in active_frames:
                    feats = extractor.get_features(cand, t)
                    features_map[cand] = feats
                    scores[cand] = clf.predict_eviction_score(feats)

                victim = max(scores, key=scores.get)
                comp_scores = list(scores.values())

                future_occurrences = [idx for idx in future_lookup[victim] if idx > t]
                next_occ = future_occurrences[0] if future_occurrences else None

                exp = engine.explain_eviction(
                    t=t,
                    evicted_page=victim,
                    incoming_page=page,
                    features=features_map[victim],
                    competitor_scores=comp_scores,
                    next_access_step=next_occ,
                    horizon=focus_frames * 2
                )
                explanations.append(exp)

                active_frames.remove(victim)
                active_frames.add(page)
                extractor.record_arrival(page, t)

    # Compute calibration metrics
    bin_stats, ece = evaluate_calibration(explanations, num_bins=5)
    print(f"-> Total Eviction Decisions Analyzed: {len(explanations)}")
    print(f"-> Expected Calibration Error (ECE): {ece:.4f}")

    # Save Explanation Sample & Calibration CSV
    calib_csv_path = os.path.join(results_dir, "confidence_calibration.csv")
    with open(calib_csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(bin_stats[0].keys()))
        writer.writeheader()
        writer.writerows(bin_stats)

    sample_exp_path = os.path.join(results_dir, "sample_explanations.csv")
    with open(sample_exp_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(explanations[0].to_dict().keys()))
        writer.writeheader()
        for e in explanations[:50]:
            writer.writerow(e.to_dict())
    print(f"-> Saved calibration metrics and sample explanations to results/")

    # 5. Generate Figures (SVG vector charts always + PNG if matplotlib is available)
    print("\n[Phase 4] Generating Publication-Quality Figures...")

    fig1_svg = os.path.join(results_dir, "fig1_hit_ratio_by_frames.svg")
    generate_hit_ratio_svg(sweep_records, fig1_svg)
    print(f"-> Created Vector Chart: {fig1_svg}")

    timelines_dict = {
        "FIFO": run_fifo.fault_timeline,
        "LRU": run_lru.fault_timeline,
        "Optimal (Belady)": run_opt.fault_timeline,
        "Learned-LRU+": run_learned.fault_timeline
    }
    fig2_svg = os.path.join(results_dir, "fig2_cumulative_faults_timeline.svg")
    generate_timeline_svg(timelines_dict, shift_idx, fig2_svg)
    print(f"-> Created Vector Chart: {fig2_svg}")

    k16_records = [r for r in sweep_records if r["num_frames"] == 16]
    fig3_svg = os.path.join(results_dir, "fig3_shift_degradation.svg")
    generate_degradation_svg(k16_records, fig3_svg)
    print(f"-> Created Vector Chart: {fig3_svg}")

    fig4_svg = os.path.join(results_dir, "fig4_confidence_calibration.svg")
    generate_calibration_svg(bin_stats, ece, fig4_svg)
    print(f"-> Created Vector Chart: {fig4_svg}")

    # If matplotlib is present, also render PNGs
    if HAS_MATPLOTLIB:
        import itertools
        # Matplotlib PNG 1
        plt.figure(figsize=(7, 4.5))
        for pol_name in ["FIFO", "LRU", "Optimal (Belady)", "Learned-LRU+"]:
            y_vals = [r["overall_hit_ratio"] * 100 for r in sweep_records if r["policy"] == pol_name]
            plt.plot(frame_sizes, y_vals, marker='o', linewidth=2, label=pol_name)
        plt.title("Overall Hit Ratio vs. Frame Capacity (N=10,000)", fontsize=11, fontweight='bold')
        plt.xlabel("Physical Frame Capacity ($k$)", fontsize=10)
        plt.ylabel("Hit Ratio (%)", fontsize=10)
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.legend(frameon=True)
        plt.tight_layout()
        plt.savefig(os.path.join(results_dir, "fig1_hit_ratio_by_frames.png"), dpi=300)
        plt.close()

        # Matplotlib PNG 2
        plt.figure(figsize=(8, 4.5))
        time_steps = list(range(len(trace)))
        for run in [run_fifo, run_lru, run_learned, run_opt]:
            cum_faults = list(itertools.accumulate(run.fault_timeline))
            plt.plot(time_steps, cum_faults, label=run.policy_name, linewidth=1.8)
        plt.axvline(x=shift_idx, color='red', linestyle='--', linewidth=1.5, label='Phase Shift ($t=5000$)')
        plt.title("Cumulative Page Faults Trajectory ($k=16$)", fontsize=11, fontweight='bold')
        plt.xlabel("Logical Access Step ($t$)", fontsize=10)
        plt.ylabel("Cumulative Page Faults", fontsize=10)
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.legend(loc="upper left", frameon=True)
        plt.tight_layout()
        plt.savefig(os.path.join(results_dir, "fig2_cumulative_faults_timeline.png"), dpi=300)
        plt.close()

        # Matplotlib PNG 3
        plt.figure(figsize=(7, 4.5))
        bar_width = 0.35
        labels = [r["policy"] for r in k16_records]
        pre_hits = [r["pre_hit_ratio"] * 100 for r in k16_records]
        post_hits = [r["post_hit_ratio"] * 100 for r in k16_records]
        indices = list(range(len(labels)))
        plt.bar([i - bar_width/2 for i in indices], pre_hits, width=bar_width, label='Phase 1 (Locality)', color='#2b5c8f')
        plt.bar([i + bar_width/2 for i in indices], post_hits, width=bar_width, label='Phase 2 (Shift)', color='#d95f02')
        plt.xticks(indices, labels, fontsize=9)
        plt.title("Degradation Under Abrupt Workload Shift ($k=16$)", fontsize=11, fontweight='bold')
        plt.ylabel("Hit Ratio (%)", fontsize=10)
        plt.grid(axis='y', linestyle="--", alpha=0.6)
        plt.legend(frameon=True)
        plt.tight_layout()
        plt.savefig(os.path.join(results_dir, "fig3_shift_degradation.png"), dpi=300)
        plt.close()

        # Matplotlib PNG 4
        plt.figure(figsize=(6, 5))
        valid_bins = [b for b in bin_stats if b["count"] > 0]
        bin_confs = [b["avg_confidence"] for b in valid_bins]
        bin_accs = [b["empirical_accuracy"] for b in valid_bins]
        plt.plot([0.5, 1.0], [0.5, 1.0], 'k--', label='Perfect ($y=x$)', linewidth=1.5)
        plt.plot(bin_confs, bin_accs, marker='s', color='#2ca02c', linewidth=2, label=f'Model (ECE = {ece:.3f})')
        plt.title("Reliability Diagram: Eviction Confidence Calibration", fontsize=11, fontweight='bold')
        plt.xlabel("Mean Predicted Confidence", fontsize=10)
        plt.ylabel("Empirical Optimality Ratio", fontsize=10)
        plt.xlim(0.5, 1.0)
        plt.ylim(0.4, 1.0)
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.legend(loc="lower right", frameon=True)
        plt.tight_layout()
        plt.savefig(os.path.join(results_dir, "fig4_confidence_calibration.png"), dpi=300)
        plt.close()

    print("\n[+] All simulation experiments and artifacts successfully produced!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_experiments()
