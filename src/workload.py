"""
CSE-307: Operating Systems - Term Paper (Section B)
Synthetic Workload Trace Generator with Deliberate Workload Phase Shift

Generates a memory reference stream characterized by:
- Phase 1 (0 <= t < N/2): High temporal and spatial locality (compact 80/20 working set + localized loops).
- Phase 2 (N/2 <= t < N): Abrupt shift to uniform random accesses and cyclic scanning that exceeds frame capacity (inducing cache thrashing).
"""

import random
from typing import List, Tuple, Dict


class WorkloadGenerator:
    def __init__(self, total_pages: int = 80, seed: int = 42):
        self.total_pages = total_pages
        self.seed = seed
        random.seed(seed)

    def generate_trace(
        self,
        total_references: int = 10000,
        shift_ratio: float = 0.5,
        working_set_size: int = 12,
        scan_size: int = 24
    ) -> Tuple[List[int], int, Dict[str, any]]:
        """
        Generates the reference trace with a deliberate phase transition.

        Parameters:
            total_references: Total length of the trace.
            shift_ratio: Fraction of the trace at which the shift occurs (default: 0.5).
            working_set_size: Size of the compact active set in Phase 1.
            scan_size: Size of the cyclic scan in Phase 2 (designed to exceed typical cache size).

        Returns:
            trace: List of page references.
            shift_index: Exact index where Phase 2 begins.
            metadata: Configuration parameters for documentation and reporting.
        """
        shift_index = int(total_references * shift_ratio)
        trace: List[int] = []

        # Define page partitions
        active_working_set = list(range(0, working_set_size))
        scan_pages = list(range(working_set_size, working_set_size + scan_size))
        background_pages = list(range(working_set_size + scan_size, self.total_pages))

        # ==========================================
        # Phase 1: High Locality (Steps 0 to shift_index)
        # ==========================================
        # 85% of references target the compact working set;
        # 10% follow sequential spatial loops;
        # 5% are sporadic cold/background touches.
        t = 0
        seq_pointer = 0
        while t < shift_index:
            r = random.random()
            if r < 0.75:
                # High temporal locality: Pick from compact working set with Zipf-like bias
                weights = [1.0 / (i + 1) for i in range(len(active_working_set))]
                chosen = random.choices(active_working_set, weights=weights, k=1)[0]
                trace.append(chosen)
            elif r < 0.90:
                # Spatial locality / localized loop
                chosen = active_working_set[seq_pointer % len(active_working_set)]
                seq_pointer += 1
                trace.append(chosen)
            else:
                # Sporadic background noise
                chosen = random.choice(background_pages)
                trace.append(chosen)
            t += 1

        # ==========================================
        # Phase 2: Workload Shift (shift_index to N)
        # ==========================================
        # Switches abruptly to:
        # - Cyclic scan over `scan_size` pages (classic pathological case for LRU)
        # - Uniform random noise across the entire address space
        # Naive recency heuristics fail to retain valuable pages.
        cyclic_idx = 0
        while t < total_references:
            r = random.random()
            if r < 0.60:
                # Cyclic scan over pages larger than frame size
                chosen = scan_pages[cyclic_idx % len(scan_pages)]
                cyclic_idx += 1
                trace.append(chosen)
            else:
                # Broad uniform random access
                chosen = random.randint(0, self.total_pages - 1)
                trace.append(chosen)
            t += 1

        metadata = {
            "total_pages": self.total_pages,
            "total_references": total_references,
            "shift_index": shift_index,
            "phase1_working_set_size": working_set_size,
            "phase2_scan_size": scan_size,
            "random_seed": self.seed
        }

        return trace, shift_index, metadata


if __name__ == "__main__":
    gen = WorkloadGenerator(total_pages=80, seed=42)
    trace, shift_idx, meta = gen.generate_trace(1000)
    print(f"Generated trace of {len(trace)} references. Shift occurs at index {shift_idx}.")
    print(f"Sample Phase 1 references: {trace[:15]}")
    print(f"Sample Phase 2 references: {trace[shift_idx:shift_idx+15]}")
