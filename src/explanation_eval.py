"""
CSE-307: Operating Systems - Term Paper (Section B)
Optional / Bonus Track: Explanation Confidence & Calibration Evaluator

Generates natural-language explanations of eviction decisions with self-rated
confidence scores, and evaluates whether the confidence is well-calibrated against
ground-truth eviction optimality (absence of immediate re-fault / Belady concordance).
"""

from typing import List, Dict, Tuple, Optional
import math


class EvictionExplanation:
    def __init__(
        self,
        timestep: int,
        evicted_page: int,
        incoming_page: int,
        confidence: float,
        explanation_text: str,
        is_optimal: bool,
        reuse_distance: int
    ):
        self.timestep = timestep
        self.evicted_page = evicted_page
        self.incoming_page = incoming_page
        self.confidence = confidence
        self.explanation_text = explanation_text
        self.is_optimal = is_optimal
        self.reuse_distance = reuse_distance

    def to_dict(self) -> Dict[str, any]:
        return {
            "timestep": self.timestep,
            "evicted_page": self.evicted_page,
            "incoming_page": self.incoming_page,
            "confidence": round(self.confidence, 4),
            "is_optimal": int(self.is_optimal),
            "reuse_distance": self.reuse_distance,
            "explanation": self.explanation_text
        }


class ExplanationEngine:
    """
    Produces deterministic, structured natural-language explanations for eviction decisions
    and computes a self-rated confidence score based on feature margins.
    """
    def __init__(self):
        pass

    def explain_eviction(
        self,
        t: int,
        evicted_page: int,
        incoming_page: int,
        features: List[float],
        competitor_scores: List[float],
        next_access_step: Optional[int],
        horizon: int = 30
    ) -> EvictionExplanation:
        """
        Features: [recency, window_freq, total_freq, avg_interval, residency]
        """
        recency, window_freq, total_freq, avg_interval, residency = features

        # Calculate confidence from the scoring margin over competitors
        if len(competitor_scores) > 1:
            sorted_scores = sorted(competitor_scores, reverse=True)
            top_score = sorted_scores[0]
            runner_up = sorted_scores[1]
            margin = top_score - runner_up
            # Map margin to confidence between 0.52 and 0.98
            confidence = min(0.52 + 0.46 * (1.0 / (1.0 + math.exp(-6.0 * margin))), 0.98)
        else:
            confidence = 0.75

        # Ground truth optimality: Did the evicted page avoid re-reference within horizon?
        reuse_dist = (next_access_step - t) if next_access_step is not None else 999999
        is_optimal = reuse_dist >= horizon

        # Construct concise, domain-specific explanation
        if recency > 80.0 and window_freq <= 1.0:
            rationale = (
                f"Page {evicted_page} was evicted due to high recency latency ({int(recency)} cycles) "
                f"and negligible window frequency ({int(window_freq)} hits), indicating working set departure."
            )
        elif avg_interval > 40.0:
            rationale = (
                f"Page {evicted_page} exhibits an extended inter-arrival interval (avg {avg_interval:.1f} cycles); "
                f"predicted idle duration exceeds competitor frames."
            )
        elif residency > 150.0 and window_freq <= 2.0:
            rationale = (
                f"Page {evicted_page} has stagnated in frame for {int(residency)} cycles without sufficient "
                f"access density to justify retention against incoming Page {incoming_page}."
            )
        else:
            rationale = (
                f"Page {evicted_page} scored highest candidate eviction index based on combined recency-frequency "
                f"scoring margin."
            )

        return EvictionExplanation(
            timestep=t,
            evicted_page=evicted_page,
            incoming_page=incoming_page,
            confidence=confidence,
            explanation_text=rationale,
            is_optimal=is_optimal,
            reuse_distance=min(reuse_dist, 999999)
        )


def evaluate_calibration(
    explanations: List[EvictionExplanation],
    num_bins: int = 5
) -> Tuple[List[Dict[str, float]], float]:
    """
    Computes binned confidence calibration and Expected Calibration Error (ECE).
    """
    bins = [i / num_bins for i in range(num_bins + 1)]
    bin_stats: List[Dict[str, float]] = []
    total_samples = len(explanations)
    ece = 0.0

    for i in range(num_bins):
        low, high = bins[i], bins[i + 1]
        bucket = [e for e in explanations if (low <= e.confidence < high) or (i == num_bins - 1 and low <= e.confidence <= high)]
        count = len(bucket)

        if count > 0:
            avg_conf = sum(e.confidence for e in bucket) / count
            accuracy = sum(1 for e in bucket if e.is_optimal) / count
            bin_ece = (count / total_samples) * abs(accuracy - avg_conf)
            ece += bin_ece

            bin_stats.append({
                "bin_range": f"{low:.1f}-{high:.1f}",
                "count": count,
                "avg_confidence": avg_conf,
                "empirical_accuracy": accuracy,
                "calibration_gap": abs(accuracy - avg_conf)
            })
        else:
            bin_stats.append({
                "bin_range": f"{low:.1f}-{high:.1f}",
                "count": 0,
                "avg_confidence": (low + high) / 2.0,
                "empirical_accuracy": 0.0,
                "calibration_gap": 0.0
            })

    return bin_stats, ece
