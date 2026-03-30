import os
import re
import json
import time
import logging
import concurrent.futures
from typing import Any, Dict, List, Tuple, Optional

import requests

from services import artifacts
from config import Config  # kept for compatibility (even if not used directly here)

logger = logging.getLogger(__name__)


# ----------------------------
# Local Ollama (recommended)
# ----------------------------
OLLAMA_URL_CHAT = os.getenv("OLLAMA_URL_CHAT", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")

# Auto-detect local Ollama models and prefer the smaller `gemma3:1b` when present.
# This helps ensure the backend uses the fast local model if it is installed.
try:
    import subprocess

    try:
        out = subprocess.run(["ollama", "ls"], capture_output=True, text=True, timeout=5)
        txt = (out.stdout or "") + (out.stderr or "")
        if "gemma3:1b" in txt:
            OLLAMA_MODEL = "gemma3:1b"
    except Exception:
        pass
except Exception:
    pass

USE_OLLAMA = os.getenv("USE_OLLAMA", "1") in ("1", "true", "True")  # default ON locally


# ----------------------------
# helpers: safe parsing
# ----------------------------
def _extract_json_from_text(text: str) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r"(\{.*\})", text, re.DOTALL)
    if m:
        sub = m.group(1)
        try:
            return json.loads(sub)
        except Exception:
            try:
                clean = re.sub(r",\s*\}", "}", sub)
                clean = re.sub(r",\s*\]", "]", clean)
                return json.loads(clean)
            except Exception:
                return None
    return None


def _clamp_int(x, lo=0, hi=100, default=0) -> int:
    try:
        return int(max(lo, min(hi, int(x))))
    except Exception:
        return int(default)


def _as_float(x, default=0.0) -> float:
    try:
        v = float(x)
        if not (v == v) or v in (float("inf"), float("-inf")):
            return float(default)
        return v
    except Exception:
        return float(default)


# ----------------------------
# Advanced confidence & evidence quality
# ----------------------------
def _detect_low_evidence(metrics: Dict[str, Any]) -> Tuple[float, Optional[str]]:
    """
    Detect low-evidence cases and return confidence penalty + optional warning.
    Returns (confidence_penalty, note).
    """
    try:
        worst_segs = metrics.get("worst_time_segments") or []
        valid_ratio = _as_float(metrics.get("dtw_valid_ratio"), 1.0)
        collapse_ratio = _as_float(metrics.get("collapse_ratio"), 0.0)
        T_ref = int(metrics.get("T_ref") or 0)
        
        penalties = 0
        reasons = []
        
        # Penalty: No clear worst segments detected
        if len(worst_segs) == 0:
            penalties += 15
            reasons.append("no_clear_segments")
        
        # Penalty: Low alignment validity (high unmatched frames)
        if valid_ratio < 0.6:
            penalties += 10
            reasons.append("low_alignment_validity")
        
        # Penalty: High collapse ratio (many frames collapsed together)
        if collapse_ratio > 0.4:
            penalties += 8
            reasons.append("high_collapse")
        
        # Penalty: Very short video (hard to analyze)
        if T_ref < 60:  # less than 2 seconds at 30fps
            penalties += 5
            reasons.append("very_short_video")
        
        note = None
        if reasons:
            note = f"low_evidence_factors: {', '.join(reasons)}"
        
        penalty = min(float(penalties), 25.0)  # Cap penalty at 25 points
        return penalty, note
    except Exception:
        return 0.0, None


def _calculate_confidence_advanced(metrics: Dict[str, Any]) -> Tuple[int, Optional[str]]:
    """
    Calculate confidence based on multiple factors:
    - Final score (primary)
    - Metric consistency (DTW vs final)
    - Evidence quality (valid_ratio, segment count)
    - low-evidence safeguard
    """
    try:
        fs = _as_float(metrics.get("final_score_0_100"), 0.0)
        dtw = _as_float(metrics.get("dtw_score_0_100"), 0.0)
        valid_ratio = _as_float(metrics.get("dtw_valid_ratio"), 1.0)
        worst_segs = metrics.get("worst_time_segments") or []
        
        # Base confidence from final score
        base_conf = float(fs)
        
        # Consistency bonus/penalty (DTW alignment with final score)
        diff = abs(fs - dtw)
        if diff < 5:
            consistency_bonus = 3
        elif diff < 15:
            consistency_bonus = 0
        else:
            consistency_bonus = -5
        
        # Evidence quality bonus (more worst segments = more confident)
        evidence_bonus = 0
        if len(worst_segs) >= 3:
            evidence_bonus = 5
        elif len(worst_segs) == 2:
            evidence_bonus = 2
        elif len(worst_segs) == 0 and fs < 50:
            evidence_bonus = -8  # Low score with no segments is suspicious
        
        # Alignment validity bonus
        if valid_ratio > 0.9:
            validity_bonus = 4
        elif valid_ratio > 0.75:
            validity_bonus = 2
        elif valid_ratio < 0.5:
            validity_bonus = -8
        else:
            validity_bonus = 0
        
        raw_conf = base_conf + consistency_bonus + evidence_bonus + validity_bonus
        
        # Low-evidence safeguard
        low_ev_penalty, low_ev_note = _detect_low_evidence(metrics)
        final_conf = raw_conf - low_ev_penalty
        
        confidence = _clamp_int(round(final_conf), 0, 100, default=50)
        
        note = low_ev_note
        
        return confidence, note
    except Exception:
        return 50, None


# ----------------------------
# Strength-to-problem validation
# ----------------------------
def _extract_non_contradicting_strengths(
    candidate_strengths: List[str],
    metrics: Dict[str, Any]
) -> List[str]:
    """
    Filter out strengths that contradict detected problem areas.
    E.g., if 'arms' are a top problem, remove claims about arm consistency.
    """
    try:
        problems = metrics.get("top_problem_areas") or []
        problem_parts = set()
        for p in problems:
            if isinstance(p, dict):
                part = str(p.get("part") or "").lower()
                if "arm" in part:
                    problem_parts.add("arm")
                if "leg" in part:
                    problem_parts.add("leg")
                if "torso" in part or "hip" in part:
                    problem_parts.add("torso")
        
        contradiction_patterns = {
            "arm": r"\b(arm|shoulder|hand)\b",
            "leg": r"\b(leg|ankle|foot|knee)\b",
            "torso": r"\b(torso|core|torso|hip|spine)\b",
        }
        
        filtered = []
        for strength in candidate_strengths:
            strength_text = str(strength).lower()
            is_contradicted = False
            
            for part in problem_parts:
                pattern = contradiction_patterns.get(part, "")
                if pattern and re.search(pattern, strength_text, re.I):
                    is_contradicted = True
                    break
            
            if not is_contradicted:
                filtered.append(strength)
        
        return filtered if filtered else candidate_strengths[:1]  # Keep at least one
    except Exception:
        return candidate_strengths


# ----------------------------
# Weakness scaling & timing handling
# ----------------------------
def _scale_weakness_severity(
    base_weaknesses: List[str],
    final_score: float
) -> List[str]:
    """
    Adjust weakness language based on score level.
    High score → subtle, low score → emphatic.
    """
    try:
        if final_score >= 85:
            # High score: subtle weaknesses
            return base_weaknesses
        elif final_score >= 65:
            # Medium score: clear weaknesses
            replacements = {
                r"A few ": "Some ",
                r"Small ": "Noticeable ",
                r"Tiny ": "Several ",
            }
            adjusted = []
            for w in base_weaknesses:
                text = str(w)
                for pattern, replacement in replacements.items():
                    text = re.sub(pattern, replacement, text, flags=re.I)
                adjusted.append(text)
            return adjusted
        else:
            # Low score: emphatic weaknesses
            replacements = {
                r"A few ": "Many ",
                r"Some ": "Frequent ",
                r"often ": "consistently ",
                r"Timing slips": "Timing is frequently off",
                r"Body shape differs": "Body positions don't match",
            }
            adjusted = []
            for w in base_weaknesses:
                text = str(w)
                for pattern, replacement in replacements.items():
                    text = re.sub(pattern, replacement, text, flags=re.I)
                adjusted.append(text)
            return adjusted
    except Exception:
        return base_weaknesses


def _handle_timing_shift_advanced(
    metrics: Dict[str, Any],
    base_weaknesses: List[str],
    base_plan: List[str]
) -> Tuple[List[str], List[str]]:
    """
    Improved timing-shift handling:
    - Scale advise based on shift magnitude
    - Consider relative to video length
    - Adjust urgency in focus_plan
    """
    try:
        shift = abs(int(metrics.get("shift_frames") or 0))
        fps = _as_float(metrics.get("fps"), 30.0)
        T_ref = int(metrics.get("T_ref") or 0)
        
        if shift <= 0:
            return base_weaknesses, base_plan
        
        shift_sec = _sec(shift, fps)
        relative_shift = float(shift) / max(1, T_ref) if T_ref > 0 else 0.0
        
        weaknesses = base_weaknesses.copy()
        plan = base_plan.copy()
        
        if shift > 15:  # Very large shift (>0.5 sec)
            timing_weakness = (
                f"Timing is significantly offset (you're {shift_sec:.1f}s off). "
                f"Start the routine together with the reference."
            )
            if not any("timing" in w.lower() or "offset" in w.lower() for w in weaknesses):
                weaknesses.insert(0, timing_weakness)
            
            # Prioritize timing fix in plan
            if not any("together" in p.lower() or "count" in p.lower() for p in plan):
                plan.insert(0, "Start together with the reference video, then practice with counts.")
        
        elif shift > 8:  # Moderate shift
            timing_weakness = f"Timing is offset (you start {shift_sec:.2f}s {'early' if shift > 0 else 'late'})."
            if not any("timing" in w.lower() or "offset" in w.lower() for w in weaknesses):
                weaknesses.append(timing_weakness)
            
            if not any("together" in p.lower() for p in plan):
                plan.append("Start together, then practice with counts (1–8).")
        
        return weaknesses[:10], plan[:3]
    except Exception:
        return base_weaknesses, base_plan


# ----------------------------
# Handle missing worst segments
# ----------------------------
def _validate_worst_segments_fallback(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    When no worst segments are detected, generate synthetic guidance.
    """
    try:
        worst_segs = metrics.get("worst_time_segments") or []
        problems = metrics.get("top_problem_areas") or []
        fs = _as_float(metrics.get("final_score_0_100"), 0.0)
        
        if len(worst_segs) > 0:
            return {}  # Normal case, return empty (no synthesis needed)
        
        # Synthetic worst segment based on problems & score
        synthetic = {
            "start_frame": 0,
            "end_frame": int(metrics.get("T_ref", 60)),
            "start_sec": 0.0,
            "end_sec": round(_sec(int(metrics.get("T_ref", 60)), _as_float(metrics.get("fps"), 30.0)), 2),
            "focus": _to_human_focus(str(problems[0].get("part", "upper body")) if problems else "upper body"),
            "severity": max(0.5, (100.0 - fs) / 100.0),
        }
        
        return {
            "worst_time_segments": [synthetic],
            "synthetic_segment": True,
        }
    except Exception:
        return {}


# ----------------------------
# Evidence extraction (key upgrade!)
# ----------------------------
def _fps_from_compare(compare_res: Dict[str, Any]) -> float:
    try:
        meta = compare_res.get("meta") or {}
        fps = meta.get("fps") or meta.get("ref_fps") or meta.get("user_fps")
        return float(fps) if fps else 30.0
    except Exception:
        return 30.0


def _sec(frame: int, fps: float) -> float:
    return float(frame) / max(1e-6, float(fps))


def _top_limbs_from_wrongness(wrongness: Dict[str, Any]) -> List[Tuple[str, float]]:
    out = []
    if not isinstance(wrongness, dict):
        return out
    for limb, arr in wrongness.items():
        try:
            a = arr if isinstance(arr, list) else list(arr)
            if len(a) == 0:
                continue
            vals = [float(x) for x in a if _as_float(x, 0.0) > 0.0]
            if not vals:
                m = 0.0
            else:
                m = float(sum(vals) / max(1, len(vals)))
            out.append((str(limb), m))
        except Exception:
            continue
    out.sort(key=lambda x: x[1], reverse=True)
    return out


def _worst_segments(
    wrongness: Dict[str, Any],
    T_ref: int,
    fps: float,
    top_k: int = 6,
    min_len_frames: int = 18,
) -> List[Dict[str, Any]]:
    if not isinstance(wrongness, dict) or T_ref <= 0:
        return []

    limbs = [k for k in wrongness.keys() if isinstance(wrongness.get(k), (list, tuple))]
    if not limbs:
        return []

    comb = [0.0] * T_ref
    for t in range(T_ref):
        vals = []
        for limb in limbs:
            arr = wrongness.get(limb) or []
            if t < len(arr):
                v = _as_float(arr[t], 0.0)
                if v > 0.0:
                    vals.append(v)
        comb[t] = float(sum(vals) / max(1, len(vals))) if vals else 0.0

    idxs = list(range(T_ref))
    idxs.sort(key=lambda i: comb[i], reverse=True)

    used = [False] * T_ref
    segments = []

    for i in idxs:
        if comb[i] <= 0.0:
            break
        if used[i]:
            continue

        peak = comb[i]
        thr = 0.55 * peak

        l = i
        while l > 0 and comb[l] >= thr:
            l -= 1
        r = i
        while r < T_ref - 1 and comb[r] >= thr:
            r += 1

        if (r - l + 1) < min_len_frames:
            half = max(8, min_len_frames // 2)
            l = max(0, i - half)
            r = min(T_ref - 1, i + half)

        for t in range(l, r + 1):
            used[t] = True

        limb_scores = []
        for limb in limbs:
            arr = wrongness.get(limb) or []
            vals = [_as_float(arr[t], 0.0) for t in range(l, min(r + 1, len(arr)))]
            limb_scores.append((limb, float(sum(vals) / max(1, len(vals)))))
        limb_scores.sort(key=lambda x: x[1], reverse=True)
        top_limb = limb_scores[0][0] if limb_scores else "torso"

        segments.append(
            {
                "start_frame": int(l),
                "end_frame": int(r),
                "start_sec": round(_sec(l, fps), 2),
                "end_sec": round(_sec(r, fps), 2),
                "focus": str(top_limb),
                "severity": round(float(peak), 4),
            }
        )
        if len(segments) >= top_k:
            break

    return segments


def _summarize_metrics_full(compare_res: Dict[str, Any]) -> Dict[str, Any]:
    dtw = compare_res.get("dtw_debug", {}) or {}
    stg = compare_res.get("stgcn_embedding", {}) or {}

    fps = _fps_from_compare(compare_res)
    T_ref = int(dtw.get("T_ref") or 0)
    T_usr = int(dtw.get("T_usr") or 0)

    wrongness = compare_res.get("wrongness_limb_timeline") or {}
    top_limbs = _top_limbs_from_wrongness(wrongness)
    worst_segs = _worst_segments(wrongness, T_ref=T_ref, fps=fps, top_k=3)

    worst_windows = []
    try:
        win_scores = list(stg.get("window_scores") or [])
        win_centers = list(stg.get("window_centers_ref") or [])
        pairs = []
        for i, s in enumerate(win_scores):
            c = win_centers[i] if i < len(win_centers) else None
            pairs.append((float(s), int(c) if c is not None else None, i))
        pairs.sort(key=lambda x: x[0])
        for s, c, idx in pairs[:5]:
            worst_windows.append(
                {
                    "score": round(float(s), 4),
                    "center_frame": c,
                    "center_sec": None if c is None else round(_sec(int(c), fps), 2),
                    "index": int(idx),
                }
            )
    except Exception:
        pass

    return {
        "final_score_0_100": round(_as_float(compare_res.get("final_score_0_100"), 0.0), 2),
        "dtw_score_0_100": round(_as_float(compare_res.get("overall_score_0_100"), 0.0), 2),
        "shift_frames": int(compare_res.get("shift_frames") or 0),
        "fps": round(float(fps), 2),
        "T_ref": T_ref,
        "T_usr": T_usr,
        "dtw_valid_ratio": round(_as_float(dtw.get("align_valid_ratio"), 0.0), 4),
        "dtw_unique_ratio": round(_as_float(dtw.get("align_unique_ratio"), 0.0), 4),
        "collapse_ratio": round(_as_float(dtw.get("align_collapse_ratio"), 0.0), 4),
        "stg_enabled": bool(stg.get("enabled")),
        "stg_sim_0_1": round(_as_float(stg.get("sim_0_1"), 0.0), 4),
        "top_problem_areas": [{"part": k, "avg_wrong": round(v, 4)} for (k, v) in top_limbs[:4]],
        "worst_time_segments": worst_segs,
        "worst_stgcn_windows": worst_windows,
    }


# ----------------------------
# Reliability locks (timestamps must be evidence-locked)
# ----------------------------
_TIME_RANGE_RE = re.compile(r"(\d+(?:\.\d+)?)s\s*[–-]\s*(\d+(?:\.\d+)?)s")


def _allowed_time_ranges(metrics: Dict[str, Any]) -> List[str]:
    """Canonical list of allowed time ranges, derived ONLY from worst_time_segments."""
    segs = metrics.get("worst_time_segments") or []
    out: List[str] = []
    for s in segs:
        try:
            start = s.get("start_sec", None)
            end = s.get("end_sec", None)
            if start is None or end is None:
                continue
            tr = f"{start}s–{end}s"
            if tr not in out:
                out.append(tr)
        except Exception:
            continue
    return out


def _is_dtw_perfect(metrics: Dict[str, Any]) -> bool:
    """DTW==100 rule (tolerant to float/rounding)."""
    try:
        return _as_float(metrics.get("dtw_score_0_100"), 0.0) >= 99.99
    except Exception:
        return False


def _is_perfect_case(metrics: Dict[str, Any]) -> bool:
    """Perfect-case gate: DTW>=99 AND ST enabled AND ST sim>=0.99."""
    try:
        dtw = _as_float(metrics.get("dtw_score_0_100"), 0.0)
        stg_enabled = bool(metrics.get("stg_enabled"))
        stg = _as_float(metrics.get("stg_sim_0_1"), 0.0)  # 0..1
        return (dtw >= 99.0) and stg_enabled and (stg >= 0.99)
    except Exception:
        return False


def _strip_unallowed_time_mentions(text: str, allowed: List[str]) -> str:
    """
    Remove any time-range mentions in `text` that are NOT exactly in allowed list.
    Keeps wording but prevents misleading timestamps leaking into UI.
    """
    try:
        s = str(text or "")
        if not s:
            return s
        allowed_set = set([str(x) for x in (allowed or [])])

        def _replace(m: re.Match) -> str:
            a = m.group(1)
            b = m.group(2)
            cand = f"{a}s–{b}s"
            cand2 = f"{a}s-{b}s"
            if cand in allowed_set:
                return cand
            if cand2 in allowed_set:
                return cand2
            return ""

        s2 = _TIME_RANGE_RE.sub(_replace, s)
        s2 = re.sub(r"\s{2,}", " ", s2).strip()
        s2 = re.sub(r"\s*—\s*$", "", s2).strip()
        s2 = re.sub(r"\(\s*\)", "", s2).strip()
        return s2
    except Exception:
        return str(text or "")


def _apply_no_weakness_policy(obj: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    """
    HARD GUARANTEE:
    - If DTW score is 100 (>=99.99), show no weaknesses (and no key moments).
    - If both DTW and ST are perfect (>=99 and ST>=0.99), same policy.
    """
    try:
        if _is_dtw_perfect(metrics) or _is_perfect_case(metrics):
            obj["weaknesses"] = []
            obj["key_moments"] = []
            obj["focus_plan"] = [
                "Do one slow clean run to keep alignment sharp.",
                "Do one normal-speed run focusing on smooth transitions.",
                "Record one take and keep it as your best reference.",
            ]
    except Exception:
        pass


def _apply_low_score_strengths_policy(obj: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    """
    HARD GUARANTEE:
    If scores are low, do NOT show 'significant strengths' that sound misleading.
    Rule:
      - If final_score_0_100 < 45 OR dtw_score_0_100 < 45:
          strengths = []   (or you can keep 1–2 mild neutral lines if you prefer)
    """
    try:
        fs = _as_float(metrics.get("final_score_0_100"), 0.0)
        dtw = _as_float(metrics.get("dtw_score_0_100"), 0.0)

        if fs < 45.0 or dtw < 45.0:
            # Strict version: no strengths at all
            obj["strengths"] = []

            # If you prefer mild neutral items instead, replace the line above with:
            # obj["strengths"] = [
            #     "Good effort to follow the sequence.",
            #     "You stay engaged through the full routine.",
            # ][:2]

            # Optional: force level to needs_work for consistency
            try:
                obj["overall_level"] = "needs_work"
            except Exception:
                pass
    except Exception:
        pass


# ----------------------------
# Prompt: "coach-like" & non-technical + evidence-locked timestamps
# ----------------------------
def _build_prompt(metrics: Dict[str, Any]) -> List[Dict[str, str]]:
    fs = _as_float(metrics.get("final_score_0_100"), 0.0)
    tone = "positive" if fs >= 85 else ("neutral" if fs >= 65 else "negative")

    system = (
        "You are a dance coach assistant. "
        "Write feedback for a dancer in plain, non-technical language. "
        "Never mention DTW, ST-GCN, embeddings, cosine, windows, confidence thresholds, or 'model'. "
        "Be specific and actionable, based ONLY on the evidence provided. "
        "Point out mistakes clearly but respectfully. "
        "If evidence is limited, say so politely."
    )

    schema = (
        "Return ONLY valid JSON with EXACTLY these keys:\n"
        "summary: string (1 sentence)\n"
        "overall_level: one of ['excellent','good','okay','needs_work']\n"
        "strengths: array of 3-10 short strings\n"
        "weaknesses: array of 0-10 short strings\n"
        "focus_plan: array of 3 short steps (what to practice next)\n"
        "key_moments: array of up to 3 items, each item has keys "
        "{time_range: string, focus: string, what_to_fix: string}\n"
        "confidence: integer 0-100\n"
    )

    allowed_ranges = _allowed_time_ranges(metrics)
    lock = (
        "RELIABILITY RULES (must follow exactly):\n"
        "1) You MUST NOT invent timestamps.\n"
        "2) If you output any time_range, it MUST be EXACTLY one of the allowed ranges listed below.\n"
        "3) Do NOT include timestamps inside strengths. Keep strengths general.\n"
        "4) Weakness timestamps are optional; if used, they MUST use an allowed range exactly.\n"
        "5) key_moments must use allowed time_range strings exactly; otherwise omit that key_moment.\n"
        f"ALLOWED TIME RANGES (exact text only): {json.dumps(allowed_ranges, ensure_ascii=False)}\n"
    )

    rules = (
        f"Tone target: {tone}.\n"
        "Weaknesses must be concrete (what is wrong + what to do), not vague.\n"
        "Avoid generic lines like 'good job' without a reason.\n"
        "Focus names must be human-friendly: 'arms', 'legs', 'upper body', 'hips/torso', 'timing'.\n"
        "If shift_frames is large, include a weakness about timing and give a timing practice step.\n"
        "If dtw_score_0_100 is 100 (or effectively 100), weaknesses MUST be an empty array and key_moments MUST be empty.\n"
        "If DTW >= 99 AND ST score >= 99: weaknesses MUST be empty and key_moments can be empty.\n"
        "\n"
        "LOW-SCORE HONESTY RULE (must follow exactly):\n"
        "- If final_score_0_100 < 45 OR dtw_score_0_100 < 45, do NOT list 'significant strengths'.\n"
        "- In that low-score case, strengths MUST be either an empty array [] OR only 1–2 mild/neutral items like:\n"
        "  'Good effort to follow the sequence.' or 'Energy stays consistent.'\n"
        "- Do NOT claim accuracy, control, clean transitions, or 'matches well' when scores are low.\n"
    )

    user = (
        "EVIDENCE (numbers + detected weak parts + weak time segments):\n"
        f"{json.dumps(metrics, ensure_ascii=False)}\n\n"
        "Now write the JSON feedback following the schema."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": schema + "\n" + lock + "\n" + rules + "\n" + user},
    ]


def _overall_level_from_score(fs: float) -> str:
    if fs >= 90:
        return "excellent"
    if fs >= 80:
        return "good"
    if fs >= 65:
        return "okay"
    return "needs_work"


def _to_human_focus(part: str) -> str:
    part = (part or "").lower()
    if "arm" in part:
        return "arms"
    if "leg" in part:
        return "legs"
    if "torso" in part:
        return "hips/torso"
    if "tim" in part:
        return "timing"
    return "upper body"


def _add_specificity_to_sw(v: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    """
    Add minimal, reliable specificity:
    - DO NOT add any timestamps to strengths.
    - Only attach (time_range + part) hints to weaknesses, and only from engine-allowed segments.
    """
    if not isinstance(v, dict):
        return

    # If DTW is perfect, do nothing here (policy will clear weaknesses anyway)
    if _is_dtw_perfect(metrics) or _is_perfect_case(metrics):
        return

    weaknesses = v.get("weaknesses") or []
    if not isinstance(weaknesses, list) or not weaknesses:
        return

    worst = (metrics.get("worst_time_segments") or [])
    problems = (metrics.get("top_problem_areas") or [])

    allowed_ranges = _allowed_time_ranges(metrics)

    parts: List[str] = []
    for p in problems:
        if not isinstance(p, dict):
            continue
        hp = _to_human_focus(str(p.get("part") or "")).strip()
        if hp and hp not in parts:
            parts.append(hp)

    ranges: List[str] = []
    for s in worst:
        if not isinstance(s, dict):
            continue
        start = s.get("start_sec")
        end = s.get("end_sec")
        if start is None or end is None:
            continue
        tr = f"{start}s–{end}s"
        if tr in allowed_ranges and tr not in ranges:
            ranges.append(tr)

    hints: List[Tuple[Optional[str], Optional[str]]] = []
    max_n = max(len(parts), len(ranges), 1)
    for i in range(max_n):
        p = parts[i % len(parts)] if parts else None
        r = ranges[i % len(ranges)] if ranges else None
        hints.append((p, r))

    def already_has_time(text: str) -> bool:
        return bool(_TIME_RANGE_RE.search(str(text or "")))

    def already_has_part(text: str) -> bool:
        return bool(re.search(r"\b(arms|legs|hips/torso|upper body|timing)\b", str(text or ""), re.I))

    def make_hint(part: Optional[str], rng: Optional[str]) -> Optional[str]:
        if rng and part:
            return f"{rng} ({part})"
        if rng:
            return f"{rng}"
        if part:
            return f"({part})"
        return None

    out_w = []
    for i, w in enumerate(weaknesses[:10]):
        text = str(w or "").strip()
        if not text:
            continue

        text = _strip_unallowed_time_mentions(text, allowed_ranges)

        if already_has_time(text) or already_has_part(text):
            out_w.append(text)
            continue

        part, rng = hints[i % len(hints)] if hints else (None, None)
        hint = make_hint(part, rng)
        if hint:
            out_w.append(f"{text} — {hint}")
        else:
            out_w.append(text)

    v["weaknesses"] = out_w[:10]

    # Ensure strengths never get timestamps
    try:
        strengths = v.get("strengths") or []
        if isinstance(strengths, list):
            v["strengths"] = [_strip_unallowed_time_mentions(str(x), []) for x in strengths][:10]
    except Exception:
        pass


def _heuristic_verdict(metrics: Dict[str, Any]) -> Dict[str, Any]:
    fs = _as_float(metrics.get("final_score_0_100"), 0.0)
    level = _overall_level_from_score(fs)
    shift = abs(int(metrics.get("shift_frames") or 0))

    # Handle cases with no worst segments: create synthetic segment for guidance
    fallback_enhance = _validate_worst_segments_fallback(metrics)
    if fallback_enhance:
        metrics = {**metrics, **fallback_enhance}
    
    segs = metrics.get("worst_time_segments") or []
    problems = metrics.get("top_problem_areas") or []

    strengths: List[str] = []
    weaknesses: List[str] = []
    plan: List[str] = []

    if fs >= 85:
        summary = "Very close match with only small details to polish."
        strengths = [
            "Good overall control and consistency.",
            "Most movements follow the reference well.",
            "Transitions stay stable in many parts.",
            "You recover quickly after tiny slips.",
        ]
        weaknesses = [
            "A few short moments drift off-time or off-shape.",
            "Some positions are not held cleanly.",
            "Small inconsistencies in body lines.",
        ]
        plan = [
            "Practice the weakest short section slowly 5 times.",
            "Record a 10–15s clip and compare.",
            "Repeat at normal speed after it feels clean.",
        ]
    elif fs >= 65:
        summary = "Decent match, but a few sections need cleaner timing and shape."
        strengths = [
            "Several parts match well.",
            "You keep the general movement pattern.",
            "Energy is consistent across the routine.",
        ]
        weaknesses = [
            "Some moments are late/early or not shaped the same.",
            "A few transitions look rushed.",
            "Arms/legs don’t always match the same line.",
        ]
        plan = [
            "Practice the weakest section in slow motion.",
            "Count beats out loud to lock timing.",
            "Fix one body part at a time (arms first, then legs).",
        ]
    else:
        summary = "Needs more practice — timing and movement shape often differ."
        strengths = [
            "Good effort to follow the sequence.",
            "You stay engaged through the full routine.",
            "Some short moments look stable.",
        ]
        weaknesses = [
            "Timing slips often.",
            "Body shape differs in key moments.",
            "Positions are not consistent between repeats.",
        ]
        plan = [
            "Work in 5–8 second clips only.",
            "Use a slow tempo and count beats.",
            "Fix big body positions before adding speed.",
        ]

    # Improved timing-shift handling with scaling
    weaknesses, plan = _handle_timing_shift_advanced(metrics, weaknesses, plan)

    # Scale weakness severity based on actual score
    weaknesses = _scale_weakness_severity(weaknesses, fs)

    # key_moments from engine evidence only (will be cleared by policy when DTW is perfect)
    key_moments = []
    for s in segs[:3]:
        tr = f"{s.get('start_sec', 0)}s–{s.get('end_sec', 0)}s"
        focus = _to_human_focus(str(s.get("focus") or "torso"))
        key_moments.append(
            {
                "time_range": tr,
                "focus": focus,
                "what_to_fix": "Match the same shape and direction as the reference in this part.",
            }
        )

    # Add problem-area specific weakness if applicable
    if problems:
        top_part = _to_human_focus(problems[0].get("part", "torso"))
        weakness_text = f"Inconsistent {top_part} position in multiple places."
        if weakness_text not in weaknesses:
            weaknesses = (weaknesses + [weakness_text])[:10]

    # Prevent strengths from contradicting detected problem areas
    strengths = _extract_non_contradicting_strengths(strengths, metrics)

    # Calculate advanced confidence (considers evidence quality, consistency, etc.)
    confidence, confidence_note = _calculate_confidence_advanced(metrics)

    out = {
        "summary": summary,
        "overall_level": level,
        "strengths": strengths[:10],
        "weaknesses": weaknesses[:10],
        "focus_plan": plan[:3],
        "key_moments": key_moments[:3],
        "confidence": confidence,
        "source": "heuristic",
    }

    # Add confidence note if there are low-evidence factors
    if confidence_note:
        out["_confidence_note"] = confidence_note

    # Add specificity ONLY to weaknesses (and only with allowed ranges)
    try:
        _add_specificity_to_sw(out, metrics)
    except Exception:
        pass

    # HARD policies
    _apply_no_weakness_policy(out, metrics)
    _apply_low_score_strengths_policy(out, metrics)

    return out


def _simplify_and_validate(v: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(v, dict):
        return _heuristic_verdict(metrics)

    required = ["summary", "overall_level", "strengths", "weaknesses", "focus_plan", "key_moments", "confidence"]
    for k in required:
        if k not in v:
            return _heuristic_verdict(metrics)

    # strengths/weaknesses up to 10
    if not isinstance(v.get("strengths"), list):
        v["strengths"] = []
    v["strengths"] = [str(x).strip() for x in v["strengths"] if str(x).strip()][:10]

    if not isinstance(v.get("weaknesses"), list):
        v["weaknesses"] = []
    v["weaknesses"] = [str(x).strip() for x in v["weaknesses"] if str(x).strip()][:10]

    # focus_plan fixed 3
    if not isinstance(v.get("focus_plan"), list):
        v["focus_plan"] = []
    v["focus_plan"] = [str(x).strip() for x in v["focus_plan"] if str(x).strip()][:3]
    while len(v["focus_plan"]) < 3:
        v["focus_plan"].append("Practice one short section slowly, then repeat at normal speed.")

    # key moments: keep up to 3 + enforce allowed time ranges strictly
    allowed_ranges = _allowed_time_ranges(metrics)
    allowed_set = set(allowed_ranges)

    km = v.get("key_moments")
    clean_km = []
    if isinstance(km, list):
        for item in km[:3]:
            if not isinstance(item, dict):
                continue
            tr = str(item.get("time_range") or "").strip()
            focus = str(item.get("focus") or "").strip()
            fix = str(item.get("what_to_fix") or "").strip()
            if allowed_set and tr not in allowed_set:
                continue
            if not allowed_set:
                continue
            if tr and focus and fix:
                clean_km.append({"time_range": tr, "focus": focus, "what_to_fix": fix})
    v["key_moments"] = clean_km

    v["confidence"] = _clamp_int(v.get("confidence"), 0, 100, default=50)

    # Re-calculate confidence with advanced logic if not already set optimally
    try:
        adv_conf, adv_note = _calculate_confidence_advanced(metrics)
        # If advanced confidence is notably different, use it (but only if LLM confidence seems low)
        if int(v.get("confidence", 50)) < 40 or adv_conf > int(v.get("confidence", 50)) + 5:
            v["confidence"] = adv_conf
            if adv_note and "_confidence_note" not in v:
                v["_confidence_note"] = adv_note
    except Exception:
        pass

    allowed_levels = {"excellent", "good", "okay", "needs_work"}
    if str(v.get("overall_level")) not in allowed_levels:
        fs = _as_float(metrics.get("final_score_0_100"), 0.0)
        v["overall_level"] = _overall_level_from_score(fs)

    # Strip technical words from summary
    tech = re.compile(r"\b(DTW|ST[-_ ]?GCN|embedding|cosine|window|model|confidence threshold)\b", re.I)
    v["summary"] = tech.sub("", str(v.get("summary") or "")).strip()

    # Reliability: strip any unallowed time mentions from weaknesses (and strengths too, just in case)
    try:
        v["weaknesses"] = [_strip_unallowed_time_mentions(x, allowed_ranges) for x in (v.get("weaknesses") or [])]
        v["strengths"] = [_strip_unallowed_time_mentions(x, []) for x in (v.get("strengths") or [])]  # strengths: no timestamps
        v["weaknesses"] = [x for x in v["weaknesses"] if x]
        v["strengths"] = [x for x in v["strengths"] if x]
    except Exception:
        pass

    # Add specificity ONLY to weaknesses, and only with allowed ranges
    try:
        _add_specificity_to_sw(v, metrics)
    except Exception:
        pass

    # HARD policies
    _apply_no_weakness_policy(v, metrics)
    _apply_low_score_strengths_policy(v, metrics)

    return v


def _fast_consolidate_partials(partials: List[Dict[str, Any]], metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Create a quick interim final verdict by heuristically combining partials."""
    pieces = [str(p.get("summary") or "") for p in partials if p and p.get("summary")]
    summary = " ".join(pieces).strip() or "Partial analysis indicates areas to improve in timing and shape."

    recs = []
    for p in partials:
        for r in (p.get("recommendations") or []):
            s = str(r).strip()
            if s and s not in recs:
                recs.append(s)

    strengths = recs[:6] if recs else ["Some segments match the reference well."]
    weaknesses = recs[6:10] if len(recs) > 6 else ["Timing or shape differences in detected segments."]
    focus_plan = recs[:3] if recs else ["Practice the most problematic short section slowly."]

    key_moments = []
    allowed_ranges = _allowed_time_ranges(metrics)
    worst = metrics.get("worst_time_segments") or []
    for i in range(min(3, len(worst))):
        seg = worst[i]
        tr = f"{seg.get('start_sec', 0)}s–{seg.get('end_sec', 0)}s"
        if tr in set(allowed_ranges):
            key_moments.append(
                {
                    "time_range": tr,
                    "focus": _to_human_focus(str(seg.get("focus") or "upper body")),
                    "what_to_fix": "Clean the shape and timing in this segment.",
                }
            )

    try:
        part_conf = [int(p.get("confidence", 50)) for p in partials if p is not None]
        avg_part = int(sum(part_conf) / max(1, len(part_conf))) if part_conf else 50
    except Exception:
        avg_part = 50
    
    # Use advanced confidence calculation instead of simple average
    adv_conf, adv_note = _calculate_confidence_advanced(metrics)
    confidence = adv_conf  # Prefer advanced calculation over simple blend

    final = {
        "summary": summary[:400],
        "overall_level": _overall_level_from_score(_as_float(metrics.get("final_score_0_100", 0.0))),
        "strengths": strengths[:10],
        "weaknesses": weaknesses[:10],
        "focus_plan": focus_plan[:3],
        "key_moments": key_moments[:3],
        "confidence": _clamp_int(confidence, 0, 100, default=50),
        "source": "interim_partials",
    }

    if adv_note:
        final["_confidence_note"] = adv_note

    try:
        final = _simplify_and_validate(final, metrics)
    except Exception:
        pass

    # HARD policies
    _apply_no_weakness_policy(final, metrics)
    _apply_low_score_strengths_policy(final, metrics)

    return final


# ----------------------------
# Ollama /api/chat call
# ----------------------------
def _call_ollama_chat(
    messages: List[Dict[str, str]],
    timeout: int = 45,
    options_override: Optional[Dict[str, Any]] = None,
):
    opts = {"temperature": 0.2, "num_predict": 450}
    if isinstance(options_override, dict):
        opts.update(options_override)
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": opts,
    }
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(OLLAMA_URL_CHAT, headers=headers, json=payload, timeout=timeout)
    except Exception as e:
        return None, None, str(e)

    if resp is None:
        return None, None, "no response"

    if resp.status_code != 200:
        return None, resp.text, f"status {resp.status_code}"

    try:
        rj = resp.json()
    except Exception:
        return None, resp.text, "invalid json response"

    content = None
    if isinstance(rj, dict):
        msg = rj.get("message") or {}
        if isinstance(msg, dict):
            content = msg.get("content")
    if not isinstance(content, str) or not content.strip():
        return None, rj, "missing content"

    parsed = _extract_json_from_text(content.strip())
    return parsed, content, None


def _safe_call_ollama_chat(
    messages: List[Dict[str, str]],
    timeout: int = 45,
    options_override: Optional[Dict[str, Any]] = None,
    retries: int = 2,
    backoff: float = 1.0,
):
    """Call `_call_ollama_chat` with simple retry/backoff on transient errors."""
    attempt = 0
    last_err = None
    while attempt <= retries:
        parsed, content, err = _call_ollama_chat(messages, timeout=timeout, options_override=options_override)
        if not err and isinstance(parsed, dict):
            return parsed, content, None
        last_err = err
        if isinstance(err, str) and (
            "timed out" in err.lower()
            or "read timeout" in err.lower()
            or "timeout" in err.lower()
            or "connection" in err.lower()
        ):
            attempt += 1
            if attempt > retries:
                return parsed, content, last_err
            try:
                time.sleep(backoff * attempt)
            except Exception:
                pass
            continue
        return parsed, content, err
    return None, None, last_err


# ----------------------------
# Public API
# ----------------------------
def generate_verdict(compare_res: Dict[str, Any], deep: bool = False) -> Dict[str, Any]:
    """
    Main verdict generator.
    - deep=False: faster, smaller generation
    - deep=True : longer, higher-quality generation
    """
    metrics = _summarize_metrics_full(compare_res)

    if not USE_OLLAMA:
        h = _heuristic_verdict(metrics)
        h["note"] = "Ollama disabled — heuristic verdict used"
        out = _simplify_and_validate(h, metrics)
        _apply_no_weakness_policy(out, metrics)
        _apply_low_score_strengths_policy(out, metrics)
        return out

    messages = _build_prompt(metrics)

    if not deep:
        parsed, text, err = _safe_call_ollama_chat(
            messages,
            timeout=30,
            options_override={"num_predict": 350, "temperature": 0.25},
            retries=1,
            backoff=0.5,
        )
    else:
        parsed, text, err = _safe_call_ollama_chat(
            messages,
            timeout=120,
            options_override={"num_predict": 1100, "temperature": 0.12},
            retries=2,
            backoff=1.0,
        )

    if err or not isinstance(parsed, dict):
        try:
            logger.warning("Ollama verdict fallback: %s", str(err))
        except Exception:
            pass
        h = _heuristic_verdict(metrics)
        h["note"] = f"Ollama error/unparsable: {err or 'unparsable'} — heuristic verdict used"
        out = _simplify_and_validate(h, metrics)
        _apply_no_weakness_policy(out, metrics)
        _apply_low_score_strengths_policy(out, metrics)
        return out

    parsed["source"] = "ollama"
    if deep:
        parsed["note"] = parsed.get("note") or "Deep LLM verdict"

    out = _simplify_and_validate(parsed, metrics)
    _apply_no_weakness_policy(out, metrics)
    _apply_low_score_strengths_policy(out, metrics)
    return out


def generate_deep_verdict_stepwise(compare_res: Dict[str, Any], out_dir: str, max_steps: int = 4) -> None:
    """
    Perform deep verdict in multiple steps, writing status updates to
    `verdict_deep_status.json` and final `verdict_deep.json` under out_dir.
    """
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        pass

    deep_status_path = os.path.join(out_dir, "verdict_deep_status.json")
    deep_final_path = os.path.join(out_dir, "verdict_deep.json")

    def _write_status(obj: Dict[str, Any]):
        try:
            artifacts.save_json(deep_status_path, obj)
        except Exception:
            try:
                with open(deep_status_path, "w", encoding="utf-8") as fp:
                    json.dump(obj, fp, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def _write_deep_preview(final_obj: Dict[str, Any], status_obj: Dict[str, Any]):
        try:
            preview = {
                "summary": final_obj.get("summary"),
                "overall_level": final_obj.get("overall_level"),
                "strengths": final_obj.get("strengths"),
                "weaknesses": final_obj.get("weaknesses"),
                "focus_plan": final_obj.get("focus_plan"),
                "key_moments": final_obj.get("key_moments"),
                "confidence": final_obj.get("confidence"),
                "note": final_obj.get("note"),
                "source": final_obj.get("source", "deep"),
            }
            preview_path = os.path.join(out_dir, "verdict_deep_preview.json")
            try:
                artifacts.save_json(preview_path, preview)
            except Exception:
                with open(preview_path, "w", encoding="utf-8") as fp:
                    json.dump(preview, fp, ensure_ascii=False, indent=2)

            try:
                base = os.path.basename(preview_path)
                status_obj["deep_preview_path"] = base
                status_obj["preview_path"] = base
                artifacts.save_json(deep_status_path, status_obj)
            except Exception:
                _write_status(status_obj)
        except Exception:
            pass

    metrics = _summarize_metrics_full(compare_res)

    # Skip expensive stage analysis when policy already enforces no weaknesses/key moments.
    if _is_dtw_perfect(metrics) or _is_perfect_case(metrics):
        final_obj = _heuristic_verdict(metrics)
        final_obj["source"] = "deep_skip_perfect"
        final_obj["note"] = "Stage analysis skipped for perfect/very-close match"
        final_obj = _simplify_and_validate(final_obj, metrics)
        _apply_no_weakness_policy(final_obj, metrics)
        _apply_low_score_strengths_policy(final_obj, metrics)

        try:
            artifacts.save_json(deep_final_path, final_obj)
        except Exception:
            try:
                with open(deep_final_path, "w", encoding="utf-8") as fp:
                    json.dump(final_obj, fp, ensure_ascii=False, indent=2)
            except Exception:
                pass

        status = {
            "status": "done",
            "progress": 100,
            "stages_total": 0,
            "stages_completed": 0,
            "partial": [],
            "note": "Deep stage analysis skipped for perfect/very-close match",
            "final_path": os.path.basename(deep_final_path),
        }
        _write_status(status)
        _write_deep_preview(final_obj, status)
        return

    worst = metrics.get("worst_time_segments") or []
    steps = min(int(max_steps), max(1, len(worst)))
    allowed_ranges = _allowed_time_ranges(metrics)

    status = {
        "status": "running",
        "progress": 1,
        "stages_total": steps + 1,
        "stages_completed": 0,
        "partial": [],
        "note": "Starting deep stepwise analysis",
    }
    _write_status(status)

    partials = []
    for i in range(steps):
        seg = worst[i] if i < len(worst) else None
        # compute a readable interval string for the segment, if available
        interval = None
        if seg is not None:
            try:
                start = seg.get("start_sec")
                end = seg.get("end_sec")
                if start is not None and end is not None:
                    interval = f"{start}s–{end}s"
            except Exception:
                interval = None

        try:
            status["current_stage"] = i
            frac = float(status["stages_completed"]) + 0.2
            status["progress"] = max(1, int(100.0 * frac / float(status["stages_total"])))
            if interval:
                status["note"] = f"Analyzing {interval} ({i+1}/{status['stages_total']})"
            else:
                status["note"] = f"Running stage {i+1}/{status['stages_total']}"
            _write_status(status)
        except Exception:
            pass

        try:
            seg_prompt = (
                "You are analyzing ONE short time segment where the dancer deviates.\n"
                f"Segment evidence: {json.dumps(seg, ensure_ascii=False)}\n\n"
                "Return ONLY JSON with keys:\n"
                "stage_index (int)\n"
                "summary (1 sentence, plain language)\n"
                "recommendations (array of 2-6 short, actionable coaching tips)\n"
                "confidence (0-100)\n\n"
                "Rules:\n"
                "- Do NOT mention any technical terms or metric names.\n"
                "- Do NOT invent timestamps.\n"
                f"- If you mention a time, it MUST be one of these exact ranges: {json.dumps(allowed_ranges, ensure_ascii=False)}\n"
            )
            messages = [
                {"role": "system", "content": "You are an expert dance coach. Be concise, specific, and reliable."},
                {"role": "user", "content": seg_prompt},
            ]
            parsed, text, err = _safe_call_ollama_chat(
                messages,
                timeout=60,
                options_override={"temperature": 0.2, "num_predict": 450},
                retries=2,
                backoff=1.0,
            )
            if err or not isinstance(parsed, dict):
                part = {
                    "stage_index": i,
                    "summary": "No LLM result; heuristic used",
                    "recommendations": [],
                    "confidence": 50,
                    "note": str(err or "no result"),
                }
            else:
                part = parsed
                part.setdefault("stage_index", i)
                part.setdefault("confidence", int(part.get("confidence", 50)))
        except Exception as e:
            part = {
                "stage_index": i,
                "summary": "Error during stage",
                "recommendations": [],
                "confidence": 40,
                "note": str(e),
            }

        # annotate part with the time interval if known
        if interval:
            part["time_range"] = interval
        partials.append(part)
        status["stages_completed"] = len(partials)
        status["progress"] = int(100.0 * status["stages_completed"] / float(status["stages_total"]))
        status["partial"] = partials
        if interval:
            status["note"] = f"Completed {interval} ({status['stages_completed']}/{status['stages_total']})"
        else:
            status["note"] = f"Completed stage {status['stages_completed']}/{status['stages_total']}"
        _write_status(status)

    # Final consolidation
    try:
        try:
            status["note"] = "Consolidating partials into final verdict"
            status["progress"] = max(
                status.get("progress", 1),
                int(100.0 * (status["stages_completed"] + 0.8) / float(status["stages_total"])),
            )
            _write_status(status)
        except Exception:
            pass

        combine_prompt = (
            "Combine the following partial coaching stage analyses into one final JSON following the final schema:\n"
            "{summary, overall_level, strengths, weaknesses, focus_plan, key_moments, confidence}\n\n"
            "RELIABILITY RULES:\n"
            "1) Do NOT invent timestamps.\n"
            "2) If you output any time_range, it MUST be EXACTLY one of these allowed ranges:\n"
            f"{json.dumps(allowed_ranges, ensure_ascii=False)}\n"
            "3) Do NOT include timestamps inside strengths.\n"
            "4) Weakness timestamps are optional; if used, must be an allowed range.\n"
            "5) If dtw_score_0_100 is 100 (or effectively 100), weaknesses MUST be empty and key_moments MUST be empty.\n"
            "\n"
            "LOW-SCORE HONESTY RULE:\n"
            "- If final_score_0_100 < 45 OR dtw_score_0_100 < 45, strengths MUST be [] or only 1–2 mild neutral items.\n"
            "- Do NOT claim strong matching or clean technique in that low-score case.\n\n"
            f"PARTIALS: {json.dumps(partials, ensure_ascii=False)}"
        )
        messages = [
            {"role": "system", "content": "You are an expert dance coach. Produce the final JSON output exactly."},
            {"role": "user", "content": combine_prompt},
        ]

        heuristic_copy = _heuristic_verdict(metrics)

        parsed_final = None
        text_final = None
        err_final = None
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(
                    _safe_call_ollama_chat,
                    messages,
                    150,
                    {"temperature": 0.08, "num_predict": 1400},
                    2,
                    1.0,
                )
                try:
                    parsed_final, text_final, err_final = fut.result(timeout=140)
                except concurrent.futures.TimeoutError:
                    parsed_final, text_final, err_final = None, None, "consolidation timeout"
        except Exception as e:
            parsed_final, text_final, err_final = None, None, str(e)

        if err_final or not isinstance(parsed_final, dict):
            note_final = f"Final consolidation fallback: {err_final or 'unparsable'}"
            final_obj = heuristic_copy
            final_obj["note"] = note_final
            final_obj["llm_raw_text"] = text_final
            final_obj["llm_error"] = str(err_final)

            # HARD policies
            _apply_no_weakness_policy(final_obj, metrics)
            _apply_low_score_strengths_policy(final_obj, metrics)

            try:
                artifacts.save_json(deep_final_path, final_obj)
            except Exception:
                pass
            try:
                _write_deep_preview(final_obj, status)
            except Exception:
                pass
            try:
                status["status"] = "done"
                status["stages_completed"] = int(status.get("stages_total", 1))
                status["progress"] = 100
                status["partial"] = partials
                status["note"] = note_final
                status["final_path"] = os.path.basename(deep_final_path)
                artifacts.save_json(deep_status_path, status)
            except Exception:
                pass
            return

        final_obj = _simplify_and_validate(parsed_final, metrics)
        try:
            final_obj["heuristic_version"] = heuristic_copy
        except Exception:
            pass
        try:
            final_obj["llm_raw_text"] = text_final
            final_obj["llm_parsed_raw"] = parsed_final
        except Exception:
            pass

        # HARD policies
        _apply_no_weakness_policy(final_obj, metrics)
        _apply_low_score_strengths_policy(final_obj, metrics)

    except Exception:
        final_obj = _heuristic_verdict(metrics)
        _apply_no_weakness_policy(final_obj, metrics)
        _apply_low_score_strengths_policy(final_obj, metrics)

    # write final
    try:
        artifacts.save_json(deep_final_path, final_obj)
    except Exception:
        try:
            with open(deep_final_path, "w", encoding="utf-8") as fp:
                json.dump(final_obj, fp, ensure_ascii=False, indent=2)
        except Exception:
            pass

    try:
        _write_deep_preview(final_obj, status)
    except Exception:
        pass

    # final status
    try:
        status["status"] = "done"
        status["stages_completed"] = int(status.get("stages_total", 1))
        status["progress"] = 100
        status["note"] = "Deep analysis complete"
        status["final_path"] = os.path.basename(deep_final_path)
        if "deep_preview_path" not in status and "preview_path" in status:
            status["deep_preview_path"] = status["preview_path"]
        if "preview_path" not in status and "deep_preview_path" in status:
            status["preview_path"] = status["deep_preview_path"]
        try:
            artifacts.save_json(deep_status_path, status)
        except Exception:
            _write_status(status)
    except Exception:
        try:
            _write_status({"status": "done", "progress": 100, "note": "Deep analysis complete (status write failed earlier)"})
        except Exception:
            pass
