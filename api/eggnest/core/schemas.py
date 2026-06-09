"""Versioned core scenario and result schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from eggnest.citations import Citation

SCENARIO_SCHEMA_VERSION = "eggnest.scenario.v1"
RESULT_SCHEMA_VERSION = "eggnest.result.v1"

EngineId = Literal["us_retirement", "uk_retirement", "us_household_resources"]
EngineJobState = Literal["queued", "running", "succeeded", "failed"]


class EngineScenario(BaseModel):
    """Canonical input envelope for all EggNest calculation engines."""

    schema_version: str = Field(default=SCENARIO_SCHEMA_VERSION)
    engine: EngineId
    country: str = Field(
        min_length=2,
        max_length=3,
        description="ISO country code, preferably alpha-3.",
    )
    inputs: dict[str, Any]
    tags: dict[str, str] = Field(default_factory=dict)


class ModelSource(BaseModel):
    """Human-auditable source used by a calculation engine."""

    name: str
    url: str | None = None
    version: str | None = None
    notes: str | None = None


class Reproducibility(BaseModel):
    """Data needed to reproduce or explain a calculation run."""

    engine_version: str
    model_version: str
    random_seed: int | None = None
    parameter_year: int | None = None
    tax_engine_versions: dict[str, str] = Field(default_factory=dict)


class EngineResult(BaseModel):
    """Canonical output envelope for all EggNest calculation engines."""

    schema_version: str = Field(default=RESULT_SCHEMA_VERSION)
    scenario_schema_version: str
    engine: EngineId
    country: str
    assumptions: dict[str, Any]
    outputs: dict[str, Any]
    citations: list[Citation] = Field(default_factory=list)
    sources: list[ModelSource] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    reproducibility: Reproducibility


class EngineJobStatus(BaseModel):
    """Status snapshot for a background core engine job."""

    job_id: str = Field(..., description="Opaque job identifier")
    status: EngineJobState = Field(..., description="Current job state")
    engine: EngineId = Field(..., description="Core engine being run")
    country: str = Field(..., description="Scenario country")
    progress: float = Field(
        default=0,
        ge=0,
        le=1,
        description="Progress fraction from 0 to 1",
    )
    current_year: float | None = Field(
        default=None,
        ge=0,
        description="Human-readable current simulated year number, when available",
    )
    total_years: int | None = Field(
        default=None,
        ge=0,
        description="Total simulated years, when available",
    )
    message: str | None = Field(
        default=None,
        description="Short human-readable progress message",
    )
    year_summary: dict[str, Any] | None = Field(
        default=None,
        description="Latest completed simulated year preview, when available",
    )
    result: EngineResult | None = Field(
        default=None,
        description="Core result envelope when status is succeeded",
    )
    error: str | None = Field(
        default=None,
        description="Error message when status is failed",
    )
    created_at: str = Field(..., description="ISO timestamp when the job was created")
    updated_at: str = Field(..., description="ISO timestamp for the latest job update")
    completed_at: str | None = Field(
        default=None,
        description="ISO timestamp when the job finished",
    )
