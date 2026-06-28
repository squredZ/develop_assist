"""CLI entry point using Click."""

from __future__ import annotations

import logging
import sys
from datetime import datetime

import click

from hilog_agent.commands.add_module import add_module
from hilog_agent.commands.analyze_log import analyze_log
from hilog_agent.commands.ask import ask
from hilog_agent.config import load_config
from hilog_agent.logging import setup_logging
from hilog_agent.renderers.json_renderer import render_json
from hilog_agent.renderers.text import render_text
from hilog_agent.store import FeatureStore

logger = logging.getLogger(__name__)


@click.group()
@click.option("--config", "-c", "config_path", default="agent.yaml", help="Path to agent.yaml")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx, config_path, verbose):
    """Hilog Agent — feature Q&A, log analysis, and module knowledge generation."""
    setup_logging(verbose=verbose)
    ctx.ensure_object(dict)
    logger.info("loading config from %s", config_path)
    cfg = load_config(config_path)
    if verbose:
        cfg.output.verbose = True
    ctx.obj["config"] = cfg
    ctx.obj["store"] = FeatureStore(cfg)
    logger.info("CLI ready — %d features available", len(ctx.obj["store"].list_features()))


@cli.command()
@click.option(
    "--feature", "-f", default=None, help="Feature name (optional, auto-matched if omitted)"
)
@click.option("--question", "-q", required=True, help="Question to ask")
@click.option("--no-llm", is_flag=True, help="Deterministic mode — no LLM call")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def ask_cmd(ctx, feature, question, no_llm, json_output):
    """Answer a feature question."""
    cfg = ctx.obj["config"]
    store = ctx.obj["store"]
    logger.info("ask command: feature=%s question='%s'", feature, question[:80])
    result = ask(feature=feature, question=question, store=store, config=cfg, no_llm=no_llm)

    if json_output:
        click.echo(render_json(result))
    else:
        click.echo(render_text(result, verbose=cfg.output.verbose))

    if result.warnings and "feature_auto_match_ambiguous" in result.warnings:
        sys.exit(2)


@cli.command()
@click.option(
    "--log",
    "-l",
    "log_paths",
    multiple=True,
    required=True,
    help="Log file path(s) or glob pattern(s)",
)
@click.option(
    "--time", "-t", "center_time", required=True, help="Center timestamp (YYYY-MM-DD HH:MM)"
)
@click.option("--window", "-w", type=int, default=None, help="Symmetric window in seconds")
@click.option("--window-before", type=int, default=None, help="Seconds before center time")
@click.option("--window-after", type=int, default=None, help="Seconds after center time")
@click.option("--feature", "-f", default=None, help="Feature name (optional)")
@click.option("--chain", default=None, help="Force a specific call chain")
@click.option("--top-n-chains", type=int, default=1, help="Expand top N chains")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def analyze_log_cmd(
    ctx,
    log_paths,
    center_time,
    window,
    window_before,
    window_after,
    feature,
    chain,
    top_n_chains,
    json_output,
):
    """Analyze hilog evidence with feature knowledge."""
    cfg = ctx.obj["config"]
    store = ctx.obj["store"]

    # Resolve window
    if window is not None:
        wb = window
        wa = window
    else:
        wb = window_before or cfg.analysis.default_window_before_seconds
        wa = window_after or cfg.analysis.default_window_after_seconds

    try:
        ct = datetime.strptime(center_time, "%Y-%m-%d %H:%M")
    except ValueError:
        logger.error("invalid --time format: '%s'", center_time)
        click.echo("Error: --time must be 'YYYY-MM-DD HH:MM'", err=True)
        sys.exit(1)

    logger.info(
        "analyze-log: %d log path(s), time=%s, window=%d/%d", len(log_paths), center_time, wb, wa
    )
    result = analyze_log(
        log_paths=list(log_paths),
        time=ct,
        window_before=wb,
        window_after=wa,
        feature=feature,
        store=store,
        config=cfg,
        chain=chain,
        top_n_chains=top_n_chains,
    )

    if json_output:
        click.echo(render_json(result))
    else:
        click.echo(render_text(result, verbose=cfg.output.verbose))


@cli.command()
@click.option("--feature", "-f", required=True, help="Feature name")
@click.option("--module", "-m", required=True, help="Module name")
@click.option("--path", "-p", "code_path", required=True, help="Module code path under repo_root")
@click.option("--force", is_flag=True, help="Overwrite existing module YAML")
@click.option("--backup", is_flag=True, help="Create backups before writing")
@click.option("--dry-run", is_flag=True, help="Validate but do not write")
@click.option("--review", is_flag=True, help="Write with pending-review markers")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def add_module_cmd(ctx, feature, module, code_path, force, backup, dry_run, review, json_output):
    """Generate module knowledge and update feature YAML."""
    cfg = ctx.obj["config"]
    store = ctx.obj["store"]
    logger.info(
        "add-module: feature=%s module=%s force=%s dry_run=%s", feature, module, force, dry_run
    )

    result = add_module(
        feature=feature,
        module=module,
        code_path=code_path,
        store=store,
        config=cfg,
        force=force,
        backup=backup,
        dry_run=dry_run,
        review=review,
    )

    if json_output:
        click.echo(render_json(result))
    else:
        click.echo(render_text(result))


def main():
    """Entry point for the `agent` console script."""
    cli()
