"""Hilog evidence analysis command."""

from __future__ import annotations

import glob as glob_mod
import logging
from datetime import datetime
from pathlib import Path

from hilog_agent.config import Config
from hilog_agent.hilog.matcher import filter_by_time_window
from hilog_agent.hilog.parser import HilogEvent, parse_hilog_file
from hilog_agent.models.evidence import AnalysisStats
from hilog_agent.models.result import AnalysisResult, Conclusion, RootCause
from hilog_agent.scoring import build_evidence, infer_chain_statuses, score_chain
from hilog_agent.store import FeatureStore

logger = logging.getLogger(__name__)


def analyze_log(
    *,
    log_paths: list[str],
    time: datetime,
    window_before: int,
    window_after: int,
    feature: str | None,
    store: FeatureStore,
    config: Config,
    chain: str | None = None,
    top_n_chains: int = 1,
) -> AnalysisResult:
    """Run the full analyze-log pipeline."""
    logger.info(
        "analyze-log start — %d path(s), time=%s, window=[%d,%d]",
        len(log_paths),
        time,
        window_before,
        window_after,
    )

    # 1. Collect all log files (expand globs)
    all_files: list[Path] = []
    for lp in log_paths:
        expanded = glob_mod.glob(lp, recursive=True)
        if expanded:
            for p in expanded:
                all_files.append(Path(p))
        else:
            p = Path(lp)
            if p.exists():
                all_files.append(p)

    if not all_files:
        logger.error("no log files found for patterns: %s", log_paths)
        raise ValueError(f"No log files found matching patterns: {log_paths}")

    logger.info("collected %d log file(s): %s", len(all_files), [f.name for f in all_files])

    # 2. Parse all hilog sources
    all_events: list[HilogEvent] = []
    total_lines = 0
    parsed_lines = 0
    unparsed_lines = 0
    for path in all_files:
        result = parse_hilog_file(path)
        all_events.extend(result.events)
        total_lines += result.total_lines
        parsed_lines += result.parsed
        unparsed_lines += result.unparsed

    # 3. Filter by time window
    window_events = filter_by_time_window(all_events, time, window_before, window_after)
    in_window = len(window_events)

    # 4. Match or read feature
    if feature is None:
        names = store.list_features()
        if names:
            feature = names[0]
        else:
            return AnalysisResult(
                feature="",
                conclusion=Conclusion(summary="No features available"),
                stats=AnalysisStats(
                    total_lines=total_lines,
                    parsed_lines=parsed_lines,
                    unparsed_lines=unparsed_lines,
                    in_window_lines=in_window,
                ),
            )

    try:
        f = store.read_feature(feature)
    except ValueError:
        logger.warning("feature '%s' not found", feature)
        return AnalysisResult(
            feature=feature,
            conclusion=Conclusion(summary=f"Feature '{feature}' not found"),
            stats=AnalysisStats(
                total_lines=total_lines,
                parsed_lines=parsed_lines,
                unparsed_lines=unparsed_lines,
                in_window_lines=in_window,
            ),
        )

    logger.info("feature '%s' loaded — %d call chain(s)", f.name, len(f.call_chains))

    # 5. Score all call chains
    chain_scores = [(c, score_chain(c, "", window_events, config.scoring)) for c in f.call_chains]
    chain_scores.sort(key=lambda x: -x[1])
    logger.info("chain scores: %s", [(c.name, s) for c, s in chain_scores])

    # 6. Expand chains
    chains_to_expand: list[str] = []
    if chain is not None:
        chains_to_expand = [chain]
    elif top_n_chains > 0:
        chains_to_expand = [c.name for c, _ in chain_scores[:top_n_chains]]
    else:
        chains_to_expand = [chain_scores[0][0].name] if chain_scores else []

    logger.info("expanding %d chain(s): %s", len(chains_to_expand), chains_to_expand)

    # 7-9. Build evidence, infer statuses, generate root causes
    all_evidence = []
    all_statuses = []
    root_causes: list[RootCause] = []

    for c in f.call_chains:
        if c.name not in chains_to_expand:
            continue
        ev = build_evidence(f, c, window_events)
        all_evidence.extend(ev)
        statuses = infer_chain_statuses(c, ev)
        all_statuses.extend(statuses)

        for st in statuses:
            if st.status == "abnormal":
                root_causes.append(
                    RootCause(
                        description=f"Step '{st.step_id}' in chain '{c.name}' is abnormal",
                        confidence="high",
                        supporting_evidence=st.evidence,
                    )
                )

    # Compute tag distribution
    tag_dist: dict[str, int] = {}
    for evt in window_events:
        tag_dist[evt.tag] = tag_dist.get(evt.tag, 0) + 1

    time_span = 0.0
    if window_events:
        t_min = min(e.timestamp for e in window_events)
        t_max = max(e.timestamp for e in window_events)
        time_span = (t_max - t_min).total_seconds()

    conclusion_text = "Analysis complete"
    if not root_causes:
        conclusion_text = "No abnormal steps detected in the time window"

    logger.info(
        "analyze-log done — %d evidence, %d root cause(s)", len(all_evidence), len(root_causes)
    )

    return AnalysisResult(
        feature=f.name,
        chain=chains_to_expand[0] if chains_to_expand else None,
        expanded_chains=chains_to_expand,
        conclusion=Conclusion(summary=conclusion_text),
        root_causes=root_causes,
        chain_status=all_statuses,
        evidence=all_evidence,
        stats=AnalysisStats(
            total_lines=total_lines,
            parsed_lines=parsed_lines,
            unparsed_lines=unparsed_lines,
            in_window_lines=in_window,
            time_span_seconds=time_span,
            tags_distribution=tag_dist,
        ),
    )
