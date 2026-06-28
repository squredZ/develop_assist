"""CLI result models and LLM output models."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from hilog_agent.models.evidence import Evidence, ChainStepStatus, AnalysisStats


class Conclusion(BaseModel):
    model_config = ConfigDict(extra="allow")

    summary: str
    confidence: Literal["high", "medium", "low"] = "medium"


class RootCause(BaseModel):
    model_config = ConfigDict(extra="allow")

    description: str
    confidence: Literal["high", "medium", "low"] = "medium"
    supporting_evidence: list[str] = Field(default_factory=list)


class CrossChainCorrelation(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_chain: str
    source_step: str
    target_chain: str
    target_step: str
    relationship: str  # e.g. "upstream_abnormal_blocks_downstream"


class RelatedFeatureSuggestion(BaseModel):
    model_config = ConfigDict(extra="allow")

    feature: str
    reason: str


class AskResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    command: Literal["ask"] = "ask"
    feature: str
    question: str
    answer: str
    sources: list[str] = Field(default_factory=list)
    supplemental_suggestions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    command: Literal["analyze-log"] = "analyze-log"
    feature: str
    chain: Optional[str] = None
    expanded_chains: list[str] = Field(default_factory=list)
    question: Optional[str] = None
    conclusion: Conclusion
    root_causes: list[RootCause] = Field(default_factory=list)
    chain_status: list[ChainStepStatus] = Field(default_factory=list)
    cross_chain_correlation: list[CrossChainCorrelation] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    stats: AnalysisStats = Field(default_factory=AnalysisStats)
    supplemental_suggestions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WrittenFile(BaseModel):
    model_config = ConfigDict(extra="allow")

    path: str
    action: Literal["created", "updated", "backup_created"]


class ModuleGenerationResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    module_yaml: str
    analysis_summary: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class FeatureUpdateResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    updated_feature_yaml: str
    change_summary: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    related_feature_suggestions: list[RelatedFeatureSuggestion] = Field(
        default_factory=list
    )


class AddModuleResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    command: Literal["add-module"] = "add-module"
    feature: str
    module: str
    written_files: list[WrittenFile] = Field(default_factory=list)
    analysis_summary: list[str] = Field(default_factory=list)
    change_summary: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    related_feature_suggestions: list[RelatedFeatureSuggestion] = Field(
        default_factory=list
    )
