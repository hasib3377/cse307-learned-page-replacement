"""
CSE-307: Operating Systems - Term Paper (Section B)
Classical Page Replacement Implementations: FIFO, LRU, and Belady's Optimal (MIN)

Author: Md. Hasib Bin Hossain (ID: 202414051, CSE 24 SEC B)
Track: Track 1 - Learned Page Replacement (Memory Management) & Bonus Track
"""

from collections import deque
from typing import List, Dict, Tuple, Optional


class PageReplacementResult:
    """Stores the execution metrics for a page replacement simulation."""
    def __init__(self, policy_name: str, num_frames: int, total_references: int):
        self.policy_name = policy_name
        self.num_frames = num_frames
        self.total_references = total_references
        self.hits = 0
        self.faults = 0
        self.fault_timeline: List[int] = []  # 1 if fault, 0 if hit at time t
        self.evictions: List[Tuple[int, int, int]] = []  # (timestep, evicted_page, incoming_page)

    @property
    def hit_ratio(self) -> float:
        return self.hits / self.total_references if self.total_references > 0 else 0.0

    @property
    def fault_ratio(self) -> float:
        return self.faults / self.total_references if self.total_references > 0 else 0.0

    def compute_phase_metrics(self, shift_index: int) -> Dict[str, float]:
        """Calculates hit ratios before and after the workload shift."""
        pre_hits = sum(1 for i, f in enumerate(self.fault_timeline[:shift_index]) if f == 0)
        pre_faults = sum(1 for i, f in enumerate(self.fault_timeline[:shift_index]) if f == 1)
        pre_total = len(self.fault_timeline[:shift_index])

        post_hits = sum(1 for i, f in enumerate(self.fault_timeline[shift_index:]) if f == 0)
        post_faults = sum(1 for i, f in enumerate(self.fault_timeline[shift_index:]) if f == 1)
        post_total = len(self.fault_timeline[shift_index:])

        return {
            "pre_hits": pre_hits,
            "pre_faults": pre_faults,
            "pre_hit_ratio": (pre_hits / pre_total) if pre_total > 0 else 0.0,
            "post_hits": post_hits,
            "post_faults": post_faults,
            "post_hit_ratio": (post_hits / post_total) if post_total > 0 else 0.0,
            "overall_hit_ratio": self.hit_ratio,
            "overall_faults": self.faults
        }


def simulate_fifo(trace: List[int], num_frames: int) -> PageReplacementResult:
    """
    Simulates First-In, First-Out (FIFO) page replacement.
    Replaces the page that has resided in memory the longest.
    """
    result = PageReplacementResult("FIFO", num_frames, len(trace))
    frames = set()
    queue = deque()  # Preserves arrival order

    for t, page in enumerate(trace):
        if page in frames:
            result.hits += 1
            result.fault_timeline.append(0)
        else:
            result.faults += 1
            result.fault_timeline.append(1)
            if len(frames) < num_frames:
                frames.add(page)
                queue.append(page)
            else:
                evicted = queue.popleft()
                frames.remove(evicted)
                frames.add(page)
                queue.append(page)
                result.evictions.append((t, evicted, page))

    return result


def simulate_lru(trace: List[int], num_frames: int) -> PageReplacementResult:
    """
    Simulates Least Recently Used (LRU) page replacement.
    Evicts the page whose last reference is oldest in the past.
    """
    result = PageReplacementResult("LRU", num_frames, len(trace))
    frames = set()
    last_accessed: Dict[int, int] = {}

    for t, page in enumerate(trace):
        if page in frames:
            result.hits += 1
            result.fault_timeline.append(0)
            last_accessed[page] = t
        else:
            result.faults += 1
            result.fault_timeline.append(1)
            if len(frames) < num_frames:
                frames.add(page)
            else:
                # Find resident page with the minimum last access timestamp
                evicted = min(frames, key=lambda p: last_accessed[p])
                frames.remove(evicted)
                del last_accessed[evicted]
                frames.add(page)
                result.evictions.append((t, evicted, page))
            last_accessed[page] = t

    return result


def simulate_optimal(trace: List[int], num_frames: int) -> PageReplacementResult:
    """
    Simulates Belady's Optimal (MIN) page replacement.
    Looks ahead into future references and evicts the page that will not be accessed
    for the longest duration into the future.
    """
    result = PageReplacementResult("Optimal (Belady)", num_frames, len(trace))
    frames = set()

    # Pre-index future occurrences of each page for O(1) next-use queries
    future_occurrences: Dict[int, deque] = {}
    for idx, page in enumerate(trace):
        if page not in future_occurrences:
            future_occurrences[page] = deque()
        future_occurrences[page].append(idx)

    for t, page in enumerate(trace):
        # Pop the current reference from future list
        future_occurrences[page].popleft()

        if page in frames:
            result.hits += 1
            result.fault_timeline.append(0)
        else:
            result.faults += 1
            result.fault_timeline.append(1)
            if len(frames) < num_frames:
                frames.add(page)
            else:
                # Determine which resident page has the furthest next reference
                furthest_page = None
                furthest_distance = -1

                for resident in frames:
                    occurrences = future_occurrences[resident]
                    if len(occurrences) == 0:
                        # Page is never accessed again; optimal candidate
                        furthest_page = resident
                        furthest_distance = float('inf')
                        break
                    else:
                        next_use = occurrences[0]
                        if next_use > furthest_distance:
                            furthest_distance = next_use
                            furthest_page = resident

                frames.remove(furthest_page)
                frames.add(page)
                result.evictions.append((t, furthest_page, page))

    return result
