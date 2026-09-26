"""Protected configuration and environment loading."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG = Path("config/analyst.yaml")


@dataclass(frozen=True)
class Limits:
    max_model_calls: int
    max_tool_calls: int
    max_elapsed_seconds: int
    max_total_tokens: int
    max_page_size: int
    max_pages: int
    max_bytes: int
    max_calculator_operands: int
    context_rounds: int


@dataclass(frozen=True)
class EvaluationConfig:
    oracle_version: str
    scenarios_path: Path
    max_generated_rows: int
    required_baseline_scenarios: tuple[str, ...]


@dataclass(frozen=True)
class AnalystConfig:
    metrics: tuple[str, ...]
    filter_fields: tuple[str, ...]
    group_fields: tuple[str, ...]
    table_schema: dict[str, str]
    limits: Limits
    evaluation: EvaluationConfig


def load_config(path: Path = DEFAULT_CONFIG) -> AnalystConfig:
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    limits = Limits(**raw["limits"])
    if any(value <= 0 for value in vars(limits).values()):
        raise ValueError("All analyst limits must be positive")
    schema = dict(raw["table_schema"])
    if not schema or any(kind not in {"string", "integer"} for kind in schema.values()):
        raise ValueError("Unsupported table schema")
    contract = raw["task_contract"]
    filters = tuple(contract["filter_fields"])
    groups = tuple(contract["group_fields"])
    if not set(filters + groups).issubset(schema):
        raise ValueError("Filter and grouping fields must exist in the table schema")
    evaluation_raw = raw["evaluation"]
    evaluation = EvaluationConfig(
        oracle_version=evaluation_raw["oracle_version"],
        scenarios_path=Path(evaluation_raw["scenarios_path"]),
        max_generated_rows=evaluation_raw["max_generated_rows"],
        required_baseline_scenarios=tuple(evaluation_raw["required_baseline_scenarios"]),
    )
    if (
        not evaluation.oracle_version
        or evaluation.max_generated_rows <= 0
        or not evaluation.required_baseline_scenarios
        or any(not scenario_id for scenario_id in evaluation.required_baseline_scenarios)
    ):
        raise ValueError("Invalid evaluation configuration")
    return AnalystConfig(
        metrics=tuple(contract["metrics"]),
        filter_fields=filters,
        group_fields=groups,
        table_schema=schema,
        limits=limits,
        evaluation=evaluation,
    )


def atlas_config() -> tuple[str, str]:
    uri = os.environ.get("ATLAS_URI")
    database = os.environ.get("ATLAS_DATABASE")
    if not uri or not database:
        raise ValueError("ATLAS_URI and ATLAS_DATABASE must be set")
    return uri, database


def agent_model_config() -> tuple[str, str]:
    key = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_AGENT_MODEL")
    if not key or not model:
        raise ValueError("OPENROUTER_API_KEY and OPENROUTER_AGENT_MODEL must be set")
    return key, model
