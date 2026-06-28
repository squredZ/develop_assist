"""Diff safety validation — only append-only changes to feature.yaml are allowed."""

from __future__ import annotations

from hilog_agent.models.feature import FeatureYaml


def validate_diff(original: FeatureYaml, updated: FeatureYaml) -> list[str]:
    """Compare original and updated FeatureYaml. Return list of violation messages."""
    errors: list[str] = []

    # Immutable fields
    if updated.name != original.name:
        errors.append(f"name changed: '{original.name}' → '{updated.name}'")
    if updated.display_name != original.display_name:
        errors.append(f"display_name changed")
    if updated.description != original.description:
        errors.append(f"description changed")
    if updated.keywords != original.keywords:
        errors.append("keywords modified")

    # Metadata immutability
    if updated.metadata.owner != original.metadata.owner:
        errors.append("metadata.owner changed")
    if updated.metadata.status != original.metadata.status:
        errors.append("metadata.status changed")
    if updated.metadata.version != original.metadata.version + 1:
        errors.append(
            f"metadata.version should be {original.metadata.version + 1}, "
            f"got {updated.metadata.version}"
        )

    # Modules: only append allowed
    orig_names = {m.name for m in original.modules}
    upd_names = {m.name for m in updated.modules}
    if not orig_names.issubset(upd_names):
        removed = orig_names - upd_names
        errors.append(f"Modules deleted: {sorted(removed)}")
    for m in updated.modules:
        if m.name in orig_names:
            orig_m = next(om for om in original.modules if om.name == m.name)
            if m.yaml_path != orig_m.yaml_path or m.responsibility != orig_m.responsibility:
                errors.append(f"Module '{m.name}' was modified (not append-only)")

    # Call chains: only append allowed
    orig_chain_names = {c.name for c in original.call_chains}
    upd_chain_names = {c.name for c in updated.call_chains}
    if not orig_chain_names.issubset(upd_chain_names):
        removed = orig_chain_names - upd_chain_names
        errors.append(f"Call chains deleted: {sorted(removed)}")

    for oc in original.call_chains:
        uc = next((c for c in updated.call_chains if c.name == oc.name), None)
        if uc is None:
            continue
        orig_step_ids = {s.id for s in oc.steps}
        upd_step_ids = {s.id for s in uc.steps}
        if not orig_step_ids.issubset(upd_step_ids):
            removed_steps = orig_step_ids - upd_step_ids
            errors.append(
                f"Call chain '{oc.name}': steps deleted: {sorted(removed_steps)}"
            )

    # Failure patterns: only append allowed
    for ofp in original.failure_patterns:
        ufp = next(
            (fp for fp in updated.failure_patterns if fp.symptom == ofp.symptom),
            None,
        )
        if ufp is None:
            errors.append(f"Failure pattern '{ofp.symptom}' deleted")
            continue
        if not set(ofp.related_steps).issubset(set(ufp.related_steps)):
            errors.append(f"Failure pattern '{ofp.symptom}': related_steps removed")
        existing_key_log_patterns = {kl.pattern for kl in ofp.key_logs}
        new_key_log_patterns = {kl.pattern for kl in ufp.key_logs}
        if not existing_key_log_patterns.issubset(new_key_log_patterns):
            errors.append(f"Failure pattern '{ofp.symptom}': key_logs removed")
        if not set(ofp.possible_causes).issubset(set(ufp.possible_causes)):
            errors.append(f"Failure pattern '{ofp.symptom}': possible_causes removed")

    return errors
