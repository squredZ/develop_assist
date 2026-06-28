"""Feature Q&A command."""

from __future__ import annotations

from hilog_agent.config import Config
from hilog_agent.store import FeatureStore
from hilog_agent.scoring import score_feature
from hilog_agent.models.result import AskResult


def ask(
    *,
    feature: str | None,
    question: str,
    store: FeatureStore,
    config: Config,
    no_llm: bool = False,
) -> AskResult:
    """Answer a feature question. If feature is None, auto-match from the question."""
    if feature is not None:
        try:
            f = store.read_feature(feature)
        except ValueError as e:
            return AskResult(
                feature=feature,
                question=question,
                answer=f"Feature '{feature}' not found: {e}",
                warnings=[str(e)],
            )
        return _answer_from_feature(f, question)

    # Auto-match
    names = store.list_features()
    if not names:
        return AskResult(
            feature="",
            question=question,
            answer="No features available.",
        )

    scored = []
    for name in names:
        try:
            f = store.read_feature(name)
        except Exception:
            continue
        s = score_feature(f, question, [], config.scoring)
        scored.append((name, s))

    scored.sort(key=lambda x: -x[1])
    if not scored:
        return AskResult(
            feature="",
            question=question,
            answer="No features could be matched.",
        )

    top = scored[0]
    margin = config.analysis.feature_score_margin
    threshold = config.analysis.min_feature_score

    if top[1] >= threshold:
        if len(scored) == 1 or (scored[1][1] + margin <= top[1]):
            f = store.read_feature(top[0])
            return _answer_from_feature(f, question)

    # Ambiguous — return candidates
    candidates = "\n".join(
        f"  {name} (score: {s})" for name, s in scored[:3]
    )
    return AskResult(
        feature="",
        question=question,
        answer=(
            f"Feature auto-match ambiguous. Top candidates:\n{candidates}\n\n"
            f"Please re-run with --feature <name>."
        ),
        warnings=["feature_auto_match_ambiguous"],
    )


def _answer_from_feature(f, question: str) -> AskResult:
    """Build a deterministic answer from a feature YAML."""
    lines = [f"Feature: {f.display_name}"]
    lines.append(f"Description: {f.description}")

    if f.failure_patterns:
        lines.append("\nKnown Failure Patterns:")
        for fp in f.failure_patterns:
            lines.append(f"  - {fp.symptom}")
            for cause in fp.possible_causes:
                lines.append(f"    Possible cause: {cause}")

    if f.call_chains:
        lines.append("\nCall Chains:")
        for cc in f.call_chains:
            lines.append(f"  {cc.name}: {cc.description}")
            for step in cc.steps:
                lines.append(f"    [{step.id}] {step.description} ({step.symbol})")

    warnings: list[str] = []
    if not f.failure_patterns and not f.call_chains:
        warnings.append("Feature has no failure patterns or call chains")

    return AskResult(
        feature=f.name,
        question=question,
        answer="\n".join(lines),
        sources=[f"features/{f.name}/feature.yaml"],
        warnings=warnings,
    )
