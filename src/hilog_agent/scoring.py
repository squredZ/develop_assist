"""Evidence builder, feature scoring, chain scoring, chain status inference."""

from __future__ import annotations

from hilog_agent.config import ScoringConfig
from hilog_agent.hilog.parser import HilogEvent
from hilog_agent.hilog.matcher import match_logs
from hilog_agent.models.feature import (
    FeatureYaml,
    CallChain,
    CallChainStep,
    ExpectedLog,
    FailureKeyLog,
)
from hilog_agent.models.evidence import Evidence, ChainStepStatus


def score_feature(
    feature: FeatureYaml,
    question: str,
    log_events: list[HilogEvent],
    sc: ScoringConfig,
) -> int:
    """Score a feature against a question and log events."""
    score = 0
    qt = question.lower()

    for kw in feature.keywords:
        if kw.lower() in qt:
            score += sc.keyword_hit_weight * 3

    for fp in feature.failure_patterns:
        for kl in fp.key_logs:
            hits = match_logs(
                log_events, tag=kl.tag, pattern=kl.pattern,
                match_type=kl.match_type, level=kl.level,
            )
            if hits:
                score += sc.log_pattern_hit_weight * 5

    seen_tags: set[str] = set()
    for evt in log_events:
        if evt.tag in seen_tags:
            continue
        seen_tags.add(evt.tag)
        for fp in feature.failure_patterns:
            for kl in fp.key_logs:
                if kl.tag == evt.tag:
                    score += sc.log_tag_hit_weight * 2
                    break

    return score


def score_chain(
    chain: CallChain,
    question: str,
    events: list[HilogEvent],
    sc: ScoringConfig,
) -> int:
    """Score a single call chain."""
    score = 0
    qt = question.lower()

    for kw in chain.keywords:
        if kw.lower() in qt:
            score += sc.keyword_hit_weight

    for step in chain.steps:
        for elog in step.expected_logs:
            hits = match_logs(
                events, tag=elog.tag, pattern=elog.pattern,
                match_type=elog.match_type, level=elog.level,
            )
            if hits:
                score += elog.weight * sc.log_pattern_hit_weight

    for step in chain.steps:
        if step.optional:
            continue
        for elog in step.expected_logs:
            if not elog.required:
                continue
            hits = match_logs(
                events, tag=elog.tag, pattern=elog.pattern,
                match_type=elog.match_type, level=elog.level,
            )
            if not hits:
                score -= sc.missing_required_step_penalty

    consecutive = _longest_consecutive_normal(chain, events)
    score += consecutive * sc.continuous_step_bonus_per_step

    return score


def _longest_consecutive_normal(chain: CallChain, events: list[HilogEvent]) -> int:
    step_ok: list[bool] = []
    for step in chain.steps:
        required_logs = [el for el in step.expected_logs if el.required]
        if not required_logs:
            step_ok.append(True)
            continue
        ok = False
        for elog in required_logs:
            hits = match_logs(
                events, tag=elog.tag, pattern=elog.pattern,
                match_type=elog.match_type, level=elog.level,
            )
            if hits:
                ok = True
                break
        step_ok.append(ok)

    best = 0
    cur = 0
    for ok in step_ok:
        if ok:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return best


def build_evidence(
    feature: FeatureYaml,
    chain: CallChain,
    events: list[HilogEvent],
) -> list[Evidence]:
    """Build evidence list for a chain against log events."""
    evidence: list[Evidence] = []
    ev_id = 0

    def next_id() -> str:
        nonlocal ev_id
        ev_id += 1
        return f"ev_{ev_id:03d}"

    for step in chain.steps:
        for elog in step.expected_logs:
            hits = match_logs(
                events, tag=elog.tag, pattern=elog.pattern,
                match_type=elog.match_type, level=elog.level,
            )
            if hits:
                for h in hits:
                    evidence.append(Evidence(
                        id=next_id(),
                        source="hilog",
                        type="expected_log_hit",
                        feature=feature.name,
                        chain=chain.name,
                        step=step.id,
                        severity="low",
                        confidence_delta=elog.weight,
                        summary=h.match_text,
                    ))
            elif elog.required:
                penalty = ScoringConfig().missing_required_step_penalty
                evidence.append(Evidence(
                    id=next_id(),
                    source="hilog",
                    type="missing_required_log",
                    feature=feature.name,
                    chain=chain.name,
                    step=step.id,
                    severity="medium",
                    confidence_delta=-penalty,
                    summary=elog.missing_meaning or f"Missing: {elog.pattern}",
                ))

    step_ids = {s.id for s in chain.steps}
    for fp in feature.failure_patterns:
        for kl in fp.key_logs:
            if kl.related_step and kl.related_step in step_ids:
                hits = match_logs(
                    events, tag=kl.tag, pattern=kl.pattern,
                    match_type=kl.match_type, level=kl.level,
                )
                for h in hits:
                    evidence.append(Evidence(
                        id=next_id(),
                        source="hilog",
                        type="failure_log_hit",
                        feature=feature.name,
                        chain=chain.name,
                        step=kl.related_step,
                        severity=kl.severity,
                        confidence_delta=kl.confidence_weight,
                        summary=f"{kl.meaning}: {h.match_text}",
                    ))

    return evidence


def infer_chain_statuses(
    chain: CallChain,
    evidence: list[Evidence],
) -> list[ChainStepStatus]:
    """Infer step statuses from evidence."""
    by_step: dict[str, list[Evidence]] = {}
    for ev in evidence:
        if ev.step:
            by_step.setdefault(ev.step, []).append(ev)

    statuses: list[ChainStepStatus] = []
    upstream_abnormal = False

    for step in chain.steps:
        ev_list = by_step.get(step.id, [])
        ev_ids = [e.id for e in ev_list]

        has_expected = any(e.type == "expected_log_hit" for e in ev_list)
        has_failure = any(
            e.type == "failure_log_hit" and e.severity == "high" for e in ev_list
        )
        has_missing = any(e.type == "missing_required_log" for e in ev_list)

        if upstream_abnormal and not has_expected:
            status = "not_entered"
        elif has_failure:
            status = "abnormal"
            upstream_abnormal = True
        elif has_missing:
            status = "suspected_abnormal"
        elif has_expected:
            status = "normal"
        elif not ev_list:
            status = "not_observed"
        else:
            status = "unknown"

        statuses.append(ChainStepStatus(
            chain=chain.name,
            step_id=step.id,
            status=status,
            evidence=ev_ids,
            detail="",
        ))

    return statuses
