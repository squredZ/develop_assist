"""Text renderer for CLI output."""

from __future__ import annotations

from hilog_agent.models.result import (
    AskResult,
    AnalysisResult,
    AddModuleResult,
)


def render_text(
    result: AskResult | AnalysisResult | AddModuleResult,
    verbose: bool = False,
) -> str:
    """Render a result model to human-readable text."""
    lines: list[str] = []

    if isinstance(result, AskResult):
        lines.append(f"Feature: {result.feature}")
        lines.append(f"Question: {result.question}")
        lines.append(f"\n{result.answer}")
        if result.sources:
            lines.append("\nSources:")
            for src in result.sources:
                lines.append(f"  - {src}")
        if result.supplemental_suggestions:
            lines.append("\nSupplemental Suggestions (无直接证据):")
            for s in result.supplemental_suggestions:
                lines.append(f"  - {s}")
        if result.warnings:
            lines.append("\nWarnings:")
            for w in result.warnings:
                lines.append(f"  ⚠ {w}")

    elif isinstance(result, AnalysisResult):
        lines.append(f"Feature: {result.feature}")
        lines.append(f"Chain: {result.chain or 'N/A'}")
        lines.append(f"Expanded Chains: {', '.join(result.expanded_chains)}")
        lines.append(f"\nConclusion: {result.conclusion.summary} (confidence: {result.conclusion.confidence})")

        if result.root_causes:
            lines.append("\nRoot Causes:")
            for rc in result.root_causes:
                refs = ", ".join(rc.supporting_evidence)
                lines.append(f"  [{rc.confidence}] {rc.description} (evidence: {refs})")

        if result.chain_status:
            lines.append("\nChain Status:")
            for cs in result.chain_status:
                lines.append(f"  [{cs.status}] {cs.chain}/{cs.step_id}")
                if verbose and cs.detail:
                    lines.append(f"    {cs.detail}")

        if verbose and result.evidence:
            lines.append("\nEvidence Breakdown:")
            for ev in result.evidence:
                lines.append(f"  {ev.id}: [{ev.type}] {ev.summary} (Δ{ev.confidence_delta})")

        if result.cross_chain_correlation:
            lines.append("\nCross-Chain Correlation:")
            for cc in result.cross_chain_correlation:
                lines.append(
                    f"  {cc.source_chain}/{cc.source_step} → "
                    f"{cc.target_chain}/{cc.target_step}: {cc.relationship}"
                )

        if result.stats.total_lines:
            lines.append(f"\nLog Stats: {result.stats.parsed_lines}/{result.stats.total_lines} parsed, "
                         f"{result.stats.in_window_lines} in window, "
                         f"span {result.stats.time_span_seconds:.1f}s")

        if result.supplemental_suggestions:
            lines.append("\nSupplemental Suggestions (无直接证据):")
            for s in result.supplemental_suggestions:
                lines.append(f"  - {s}")

        if result.warnings:
            lines.append("\nWarnings:")
            for w in result.warnings:
                lines.append(f"  ⚠ {w}")

    elif isinstance(result, AddModuleResult):
        lines.append(f"Command: add-module")
        lines.append(f"Feature: {result.feature}")
        lines.append(f"Module: {result.module}")
        if result.written_files:
            lines.append("\nWritten Files:")
            for wf in result.written_files:
                lines.append(f"  [{wf.action}] {wf.path}")
        if result.analysis_summary:
            lines.append("\nAnalysis Summary:")
            for s in result.analysis_summary:
                lines.append(f"  - {s}")
        if result.change_summary:
            lines.append("\nChanges:")
            for s in result.change_summary:
                lines.append(f"  - {s}")
        if result.warnings:
            lines.append("\nWarnings:")
            for w in result.warnings:
                lines.append(f"  ⚠ {w}")
        if result.related_feature_suggestions:
            lines.append("\nRelated Feature Suggestions:")
            for rfs in result.related_feature_suggestions:
                lines.append(f"  - {rfs.feature}: {rfs.reason}")

    return "\n".join(lines)
