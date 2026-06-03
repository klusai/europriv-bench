#!/usr/bin/env python3
"""KLU-53 — the detection/protection dissociation, made visual + significant.

"The anti-correlation IS the paper." This script regenerates, as a reproducible analysis artifact,
the two central exhibits for the EuroPriv-Bench papers from committed inputs:

  1. **Pareto-frontier figure** — detection entity-F1 (x) vs re-identification CNP leak-rate (y)
     across all scored models on the RO real-skeleton track (``ro-realskeleton-v1``). The
     type-accurate detectors (GLiNER, tabularisai) sit on the *bad* frontier (high F1, high leak);
     kp-deid sits OFF it (lower F1, 0% leak). Read live from ``baselines/leaderboard.json`` — never
     hardcoded.

  2. **McNemar significance test** — item-paired per-subject CNP detection (was each gold CNP
     *subject* redacted or leaked) between kp-deid and the most informative contrasts. Uses a fresh
     per-subject prediction dump from ``europriv run --dump-predictions`` (same per-subject
     ``(doc, country, normalized value)`` unit as the re-id leak-rate). Reports the 2x2 discordant
     counts (b, c) and an exact-binomial McNemar p-value.

Reproduce::

    # 1. dump per-subject CNP detection for every model on the RO real-skeleton track
    #    (one config; serial/foreground — heavy model backends required)
    europriv run --suite <single-spec-suite-with-ro-realskeleton> \\
        --adapter kp-model --adapter privacy-filter --adapter openmed \\
        --adapter tabularisai --adapter presidio --adapter gliner \\
        --workers 1 --dump-predictions analysis/predictions_ro_realskeleton.json \\
        --out /tmp/lb.json

    # 2. regenerate the figure + McNemar stats
    python analysis/pareto_dissociation.py \\
        --leaderboard baselines/leaderboard.json \\
        --predictions analysis/predictions_ro_realskeleton.json \\
        --outdir analysis

Needs the ``analysis`` extra (matplotlib; scipy optional for the exact-binomial p-value)::

    pip install -e '.[analysis]'
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

CONFIG = "ro-realskeleton-v1"

# Display names + a stable point colour, keyed by the leaderboard adapter name. Anything scored on
# the track but not listed here still plots (falls back to the adapter name + a neutral colour).
MODEL_DISPLAY: dict[str, dict[str, str]] = {
    "kp-model": {"label": "kp-deid-mdeberta-280m", "color": "#1b9e77"},
    "gliner": {"label": "GLiNER (multi-pii)", "color": "#d95f02"},
    "tabularisai": {"label": "tabularisai eu-pii-safeguard", "color": "#7570b3"},
    "openmed": {"label": "OpenMed privacy-filter-ml", "color": "#e7298a"},
    "privacy-filter": {"label": "openai/privacy-filter", "color": "#66a61e"},
    "presidio": {"label": "Presidio (en_core_web_lg)", "color": "#a6761d"},
}

WILSON_Z_95 = 1.95996


def wilson_interval(successes: int, total: int, z: float = WILSON_Z_95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (matches the harness ``metrics`` impl)."""
    if total <= 0:
        return (0.0, 0.0)
    p = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denom
    half = (z / denom) * math.sqrt(p * (1.0 - p) / total + z2 / (4.0 * total * total))
    return (center - half, center + half)


# --------------------------------------------------------------------------- #
# 1. Pareto frontier from the leaderboard
# --------------------------------------------------------------------------- #
def load_track_points(leaderboard_path: Path) -> list[dict]:
    """Extract one (model, F1, leak-rate, CNP counts, config_status) point per scored model on the
    RO real-skeleton track, straight from the leaderboard JSON. No numbers are hardcoded."""
    lb = json.loads(leaderboard_path.read_text(encoding="utf-8"))
    points: list[dict] = []
    for entries in lb["entries"].values():
        for e in entries:
            if e.get("dataset", {}).get("config") != CONFIG:
                continue
            cnp = e["scores"]["cnp_leakage"]
            adapter = e["adapter"]
            disp = MODEL_DISPLAY.get(adapter, {"label": adapter, "color": "#555555"})
            total = int(cnp["cnp_total"])
            missed = int(cnp["cnp_missed"])
            points.append({
                "adapter": adapter,
                "model_id": e["model_id"],
                "label": disp["label"],
                "color": disp["color"],
                "f1": e["scores"]["entity_f1"]["f1"],
                "leak_rate": cnp["leak_rate"],
                "leak_ci_low": cnp["leak_rate_ci_low"],
                "leak_ci_high": cnp["leak_rate_ci_high"],
                "cnp_total": total,
                "cnp_missed": missed,
                "config_status": e.get("config_status", "dev"),
                "contamination": e.get("contamination", "unknown"),
            })
    if not points:
        raise SystemExit(f"no {CONFIG} entries found in {leaderboard_path}")
    return sorted(points, key=lambda p: p["f1"])


def pareto_bad_frontier(points: list[dict]) -> list[dict]:
    """The "bad" frontier: models that are Pareto-optimal in the *wrong* objective — you cannot get
    higher detection-F1 without also leaking at least as much. A point is on it if no other point
    has both higher F1 AND lower-or-equal leak. kp-deid (0 leak) is dominated on F1 but is the lone
    point that escapes the leak axis entirely — that off-frontier position is the headline."""
    frontier = []
    for p in points:
        dominated = any(
            (q["f1"] > p["f1"] and q["leak_rate"] <= p["leak_rate"]) for q in points if q is not p
        )
        if not dominated:
            frontier.append(p)
    return sorted(frontier, key=lambda p: p["f1"])


def make_figure(points: list[dict], out_svg: Path, out_png: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Wide landscape (2:1) so the figure fills a full-width hero frame at a sensible height and the
    # edge labels have room to breathe.
    fig, ax = plt.subplots(figsize=(12.0, 6.0))

    xs = [p["f1"] for p in points]
    xmin, xmax = (min(xs), max(xs)) if xs else (0.0, 1.0)

    # Trend line through the *leaking* content-NER detectors (sorted by F1): for systems that treat
    # a CNP as just another token, higher detection-F1 does NOT lower the re-id leak — it is the
    # "bad" region. kp-deid (and Presidio) sit OFF it at 0% leak.
    leakers = sorted((p for p in points if p["leak_rate"] > 0), key=lambda p: p["f1"])
    if len(leakers) >= 2:
        ax.plot(
            [p["f1"] for p in leakers],
            [p["leak_rate"] * 100 for p in leakers],
            color="#bbbbbb", linestyle="--", linewidth=1.2, zorder=1,
            label="content-NER detectors (high F1 ⇏ low leak)",
        )

    # Per-adapter label placement (offset in points; ha/va; leader = draw a thin connector for the
    # points in the tight mid-cluster so labels sit in open space). Cosmetic only — every plotted
    # value still comes from the leaderboard above; unlisted adapters fall back to a sane default.
    PLACE = {
        "spacy":          (10, -14, "left",  "top",    False),
        "privacy-filter": (-8,  11, "right", "bottom", False),
        "presidio":       (8,   15, "left",  "bottom", False),
        "openmed":        (-48,  4, "right", "center", True),
        "gliner2":        (4,  -34, "left",  "top",    True),
        "tabularisai":    (-6,  13, "right", "bottom", False),
        "gliner":         (-12, 11, "right", "bottom", False),
        "kp-model":       (12,  13, "left",  "bottom", False),
    }
    for p in points:
        x = p["f1"]
        y = p["leak_rate"] * 100
        yerr = [[(p["leak_rate"] - p["leak_ci_low"]) * 100], [(p["leak_ci_high"] - p["leak_rate"]) * 100]]
        is_kp = p["adapter"] == "kp-model"
        ax.errorbar(
            x, y, yerr=yerr, fmt="o",
            color=p["color"], ecolor=p["color"], elinewidth=1.2, capsize=3,
            markersize=13 if is_kp else 9,
            markeredgecolor="black" if is_kp else "none",
            markeredgewidth=1.6 if is_kp else 0,
            zorder=4 if is_kp else 3,
        )
        dx, dy, ha, va, leader = PLACE.get(p["adapter"], (10, 8, "left", "bottom", False))
        ann_kw = dict(
            textcoords="offset points", xytext=(dx, dy),
            fontsize=9, fontweight="bold" if is_kp else "normal", ha=ha, va=va,
        )
        if leader:
            ann_kw["arrowprops"] = dict(arrowstyle="-", color="#999999", lw=0.7, shrinkA=0, shrinkB=5)
        ax.annotate(f"{p['label']}\nF1={x:.3f}, leak={y:.1f}%", (x, y), **ann_kw)

    ax.set_xlim(xmin - 0.05, xmax + 0.06)
    ax.set_xlabel("Detection entity-F1  (higher = better detection)", fontsize=12)
    ax.set_ylabel("Re-identification CNP leak-rate  (lower = better protection)", fontsize=12)
    ax.set_title(
        "Detection accuracy does NOT buy privacy protection\n"
        "RO real-skeleton track (ro-realskeleton-v1): per-subject CNP leak vs entity-F1",
        fontsize=13.5,
    )
    ax.set_ylim(bottom=-1.5)
    ax.axhline(0, color="#cccccc", linewidth=0.8, zorder=0)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)

    n_total = points[0]["cnp_total"] if points else 0
    statuses = sorted({p["config_status"] for p in points})
    caption = (
        f"Each point is one scored model; y error bars are 95% Wilson CIs on the leak-rate "
        f"(n={n_total} distinct CNP subjects, per-subject (doc, country, value) re-id unit). "
        f"config_status={'/'.join(statuses)} (contamination-controlled, not yet citable-validated). "
        f"kp-deid (ringed) sits OFF the detection-optimal frontier: 0% leak at non-maximal F1. "
        f"Source: EuroPriv-Bench leaderboard (ro-realskeleton-v1)."
    )
    fig.text(0.5, 0.005, caption, ha="center", va="bottom", fontsize=7.3, wrap=True, color="#333333")
    fig.tight_layout(rect=(0, 0.055, 1, 1))
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_svg, format="svg")
    fig.savefig(out_png, format="png", dpi=200)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 2. McNemar on item-paired per-subject CNP detection
# --------------------------------------------------------------------------- #
def _subject_map(dump: dict) -> dict[tuple[int, str, str], bool]:
    """Map (doc, country, value) -> detected, for decode-bearing (CNP) subjects only."""
    return {
        (s["doc"], s["country"], s["value"]): bool(s["detected"])
        for s in dump["subjects"]
        if s.get("decode_bearing", True)
    }


def _exact_binomial_two_sided(b: int, c: int) -> float:
    """Exact two-sided binomial p-value for McNemar with discordant counts (b, c): under H0 each
    discordant pair is a fair coin (p=0.5), n=b+c, k=min(b,c). Used unconditionally (the exact test
    is valid for any n and is what small discordant counts require). Uses scipy when available,
    else a pure-Python binomial computation."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    try:
        from scipy.stats import binomtest

        return float(binomtest(k, n, 0.5, alternative="two-sided").pvalue)
    except Exception:
        # Two-sided exact: 2 * P(X <= k) for the symmetric Binomial(n, 0.5), capped at 1.
        cdf = sum(math.comb(n, i) for i in range(k + 1)) / (2.0 ** n)
        return min(1.0, 2.0 * cdf)


def mcnemar(dump_a: dict, dump_b: dict) -> dict:
    """McNemar test on the per-subject CNP detection of two models over the SAME gold subjects.

    Pairs subjects by (doc, country, value) — the keys are gold-derived, so they align across
    adapters. "Outcome" = was this subject's CNP *detected* (redacted). Discordant pairs:
      b = A detected (protected) but B missed (B leaked it)   -> A protects, B leaks
      c = A missed (A leaked it) but B detected (protected)   -> B protects, A leaks
    Reports the full 2x2, McNemar chi-square (continuity-corrected, informational) and the exact
    two-sided binomial p-value (the one to cite for small discordant counts)."""
    a = _subject_map(dump_a)
    bm = _subject_map(dump_b)
    shared = sorted(set(a) & set(bm))
    n11 = n10 = n01 = n00 = 0  # both-detected, A-only, B-only, neither
    for key in shared:
        da, db = a[key], bm[key]
        if da and db:
            n11 += 1
        elif da and not db:
            n10 += 1
        elif not da and db:
            n01 += 1
        else:
            n00 += 1
    b, c = n10, n01  # discordant
    disc = b + c
    if disc > 0:
        chi2_cc = (abs(b - c) - 1) ** 2 / disc
    else:
        chi2_cc = 0.0
    p_exact = _exact_binomial_two_sided(b, c)
    return {
        "model_a": dump_a["adapter"],
        "model_b": dump_b["adapter"],
        "n_shared_subjects": len(shared),
        "table": {
            "both_detected": n11,
            "a_detected_b_missed_b": n10,   # b: A protects, B leaks
            "a_missed_b_detected_b": n01,   # c: B protects, A leaks
            "neither_detected": n00,
        },
        "discordant_b_A_protects_B_leaks": b,
        "discordant_c_B_protects_A_leaks": c,
        "mcnemar_chi2_cc": chi2_cc,
        "p_value_exact_binomial": p_exact,
        "a_leaked": sum(1 for k in shared if not a[k]),
        "b_leaked": sum(1 for k in shared if not bm[k]),
    }


def _verdict(res: dict, alpha: float = 0.05) -> str:
    a, bn = res["model_a"], res["model_b"]
    b, c = res["discordant_b_A_protects_B_leaks"], res["discordant_c_B_protects_A_leaks"]
    p = res["p_value_exact_binomial"]
    sig = p < alpha
    if not sig:
        return (f"NOT significant (p={p:.3g} >= {alpha}): no detectable difference in per-subject "
                f"CNP protection between {a} and {bn} (b={b}, c={c}).")
    better = a if b > c else bn
    worse = bn if b > c else a
    return (f"SIGNIFICANT (p={p:.3g} < {alpha}): {better} protects per-subject CNPs that {worse} "
            f"leaks far more often than the reverse (b={b}, c={c}). The dissociation is real.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--leaderboard", type=Path, default=Path("baselines/leaderboard.json"))
    ap.add_argument("--predictions", type=Path, default=Path("analysis/predictions_ro_realskeleton.json"))
    ap.add_argument("--outdir", type=Path, default=Path("analysis"))
    ap.add_argument("--alpha", type=float, default=0.05)
    args = ap.parse_args()

    points = load_track_points(args.leaderboard)

    # --- Figure ---
    fig_svg = args.outdir / "pareto_dissociation_ro_realskeleton.svg"
    fig_png = args.outdir / "pareto_dissociation_ro_realskeleton.png"
    make_figure(points, fig_svg, fig_png)
    print(f"wrote figure: {fig_svg} (+ .png)")

    # --- McNemar ---
    pred = json.loads(args.predictions.read_text(encoding="utf-8"))
    dumps_list = [d for d in pred["dumps"] if d["dataset"]["config"] == CONFIG]
    dumps = {d["adapter"]: d for d in dumps_list}
    if "kp-model" not in dumps:
        raise SystemExit(f"kp-model dump missing for {CONFIG}; cannot run the headline contrasts")

    # F1 order from the leaderboard; leak from the leaderboard (per-subject, consistent with dumps).
    by_adapter = {p["adapter"]: p for p in points}
    others = [a for a in dumps if a != "kp-model" and a in by_adapter]

    # Contrast 1: kp-deid vs the F1 leader that ALSO leaks the most (the headline dissociation).
    #   among models that actually leak (>0), the one with the highest F1.
    leakers = [a for a in others if by_adapter[a]["leak_rate"] > 0]
    f1_leader = max(leakers, key=lambda a: by_adapter[a]["f1"]) if leakers else max(others, key=lambda a: by_adapter[a]["f1"])

    # Contrast 2: kp-deid vs the next-best protector — lowest leak-rate among the others (ties
    #   broken by higher F1). On this track another system may also reach 0% leak (a genuine tie,
    #   reported honestly with b=c=0, p=1).
    next_protector = min(others, key=lambda a: (by_adapter[a]["leak_rate"], -by_adapter[a]["f1"]))

    # Contrast 3 (informative): kp-deid vs the next-best protector that ACTUALLY leaks something —
    #   the lowest non-zero leak-rate. Added so the "next protector" comparison is not vacuous when
    #   contrast 2 lands on a second 0%-leak system; skipped if it duplicates an earlier contrast.
    leaking_protectors = [a for a in others if by_adapter[a]["leak_rate"] > 0]
    next_leaking = (min(leaking_protectors, key=lambda a: (by_adapter[a]["leak_rate"], -by_adapter[a]["f1"]))
                    if leaking_protectors else None)

    plan = [("f1_leader_max_leak", f1_leader), ("next_best_protector", next_protector)]
    if next_leaking is not None:
        plan.append(("next_leaking_protector", next_leaking))

    contrasts = []
    seen = set()
    for label, other in plan:
        if other is None or other in seen:
            continue
        seen.add(other)
        res = mcnemar(dumps["kp-model"], dumps[other])
        res["contrast"] = label
        res["verdict"] = _verdict(res, alpha=args.alpha)
        contrasts.append(res)

    # --- Persist results: JSON (machine) + Markdown (human / paper). ---
    out_json = args.outdir / "mcnemar_ro_realskeleton.json"
    out_md = args.outdir / "mcnemar_ro_realskeleton.md"
    payload = {
        "config": CONFIG,
        "predictions_timestamp": pred.get("timestamp"),
        "alpha": args.alpha,
        "pareto_points": [
            {k: p[k] for k in ("adapter", "model_id", "f1", "leak_rate", "leak_ci_low",
                               "leak_ci_high", "cnp_total", "cnp_missed", "config_status")}
            for p in points
        ],
        "contrasts": contrasts,
    }
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# McNemar significance — per-subject CNP detection (`{CONFIG}`)",
        "",
        "Item-paired McNemar on **per-subject CNP detection** (was each distinct gold CNP subject "
        "`(doc, country, normalized value)` redacted or leaked) — the same per-subject unit as the "
        "re-identification leak-rate. Exact two-sided binomial p-value on the discordant pairs "
        "(valid for small discordant counts). Source dump: "
        f"`{args.predictions}` (timestamp {pred.get('timestamp')}).",
        "",
        "Discordant counts: **b** = kp-deid protects / other leaks; **c** = other protects / kp-deid leaks.",
        "",
        "| Contrast | Model A (kp-deid) vs B | shared CNP subjects | A leaked | B leaked | b | c | McNemar p (exact) | Verdict |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in contrasts:
        verdict_short = "**significant**" if r["p_value_exact_binomial"] < args.alpha else "not significant"
        lines.append(
            f"| {r['contrast']} | kp-model vs {r['model_b']} | {r['n_shared_subjects']} | "
            f"{r['a_leaked']} | {r['b_leaked']} | {r['discordant_b_A_protects_B_leaks']} | "
            f"{r['discordant_c_B_protects_A_leaks']} | {r['p_value_exact_binomial']:.3g} | {verdict_short} |"
        )
    lines += ["", "## Verdicts", ""]
    for r in contrasts:
        lines.append(f"- **kp-deid vs {r['model_b']}** ({r['contrast']}): {r['verdict']}")
    lines += ["", f"Figure: `{fig_svg.name}` (+ `.png`). Regenerate with `analysis/pareto_dissociation.py`.", ""]
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"wrote McNemar results: {out_json} and {out_md}")
    for r in contrasts:
        print(f"  [{r['contrast']}] kp-model vs {r['model_b']}: "
              f"b={r['discordant_b_A_protects_B_leaks']} c={r['discordant_c_B_protects_A_leaks']} "
              f"p={r['p_value_exact_binomial']:.3g} -> {r['verdict']}")


if __name__ == "__main__":
    main()
