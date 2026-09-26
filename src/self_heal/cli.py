"""Phase 1 commands for seeding Atlas and running the analyst."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from evals.analyst.generator import ScenarioError, load_scenarios, materialize_case, prepare_case
from evals.analyst.oracle import OracleError
from harness.agent import AnalystAgent, RunResult
from harness.tools import AnalystTools
from self_heal.evaluation import EvaluationRunner, baseline_expectation_matches
from self_heal.model import OpenRouterModel
from self_heal.settings import AnalystConfig, agent_model_config, atlas_config, load_config
from self_heal.table_store import AtlasTableStore, DatasetError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="self-heal", description="Atlas-backed structured table analyst")
    subcommands = parser.add_subparsers(dest="command", required=True)
    seed = subcommands.add_parser("seed", help="Materialize an immutable table in Atlas")
    seed.add_argument("--fixture", required=True, type=Path, help="JSON dataset definition")
    run = subcommands.add_parser("run", help="Run an analyst task against an Atlas dataset")
    task_input = run.add_mutually_exclusive_group(required=True)
    task_input.add_argument("--task", help="JSON task object for reproducible runs")
    task_input.add_argument("--question", help="Natural-language question about the assigned table")
    run.add_argument("--dataset", required=True, help="Dataset ID to bind to this run")
    run.add_argument("--json", action="store_true", help="Show the full result as JSON, including for questions")
    evaluation = subcommands.add_parser("eval", help="Materialize or run protected Phase 2 scenarios")
    evaluation_commands = evaluation.add_subparsers(dest="evaluation_command", required=True)
    materialize = evaluation_commands.add_parser("materialize", help="Publish declared valid evaluation datasets to Atlas")
    materialize.add_argument("--scenario", default="all", help="Scenario ID or all")
    evaluate = evaluation_commands.add_parser("run", help="Run the current harness against one declared scenario")
    evaluate.add_argument("--scenario", required=True, help="Answerable scenario ID")
    return parser


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _answer_message(task: dict[str, Any], answer: dict[str, Any]) -> str:
    metric = {"available": "available", "on_hand": "on-hand", "reserved": "reserved"}[task["metric"]]
    field, filter_value = task.get("filter_field"), task.get("filter_value")
    location = {
        "warehouse": f" in the {filter_value} warehouse",
        "category": f" in the {filter_value} category",
        "sku": f" for SKU {filter_value}",
    }.get(field, "")
    if "groups" in answer:
        groups = answer["groups"]
        if not groups:
            return "I found no matching rows to group."
        values = "; ".join(f"{name}: {value}" for name, value in groups.items())
        return f"{metric.capitalize()} units by {task['group_by'].replace('_', ' ')}{location}: {values}."
    value = answer["value"]
    unit = "unit" if value == 1 else "units"
    return f"There are {value} {metric} {unit}{location or ' in this dataset'}."


def _present_run(result: RunResult, *, conversational: bool, json_output: bool) -> int:
    if result.outcome == "unsupported":
        message = "I can't answer that with my current capabilities."
    elif result.outcome == "error":
        message = f"Sorry, I couldn't complete that request: {result.error}."
    else:
        assert result.answer is not None and result.interpreted_task is not None
        message = _answer_message(result.interpreted_task, result.answer)

    if conversational and not json_output:
        print(message)
    else:
        _emit(
            {
                "run_id": result.run_id,
                "answer": result.answer,
                "error": result.error,
                "outcome": result.outcome,
                "message": message,
                "interpreted_task": result.interpreted_task,
                "model_calls": result.model_calls,
                "tool_calls": result.tool_calls,
                "total_tokens": result.total_tokens,
                "elapsed_seconds": result.elapsed_seconds,
                "table_pages": result.table_pages,
                "table_bytes": result.table_bytes,
            }
        )
    return 1 if result.outcome == "error" else 0


def _select_scenarios(scenarios: dict[str, Any], scenario_id: str, *, allow_all: bool) -> list[Any]:
    if scenario_id == "all" and allow_all:
        return list(scenarios.values())
    try:
        return [scenarios[scenario_id]]
    except KeyError as exc:
        raise ValueError("Unknown evaluation scenario") from exc


def _run_evaluation_command(args: argparse.Namespace, store: AtlasTableStore, config: AnalystConfig) -> int:
    scenarios = load_scenarios(config.evaluation.scenarios_path, config)
    if args.evaluation_command == "materialize":
        selected = _select_scenarios(scenarios, args.scenario, allow_all=True)
        published = []
        for scenario in selected:
            if scenario.invalid_row is not None:
                continue
            materialized = materialize_case(store, prepare_case(scenario, config))
            published.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "dataset_id": materialized.dataset.dataset_id,
                    "seed": scenario.seed,
                    "row_count": materialized.dataset.row_count,
                    "content_hash": materialized.dataset.content_hash,
                }
            )
        _emit({"materialized": published, "skipped_invalid_scenarios": [s.scenario_id for s in selected if s.invalid_row]})
        return 0

    scenario = _select_scenarios(scenarios, args.scenario, allow_all=False)[0]
    case = prepare_case(scenario, config)
    api_key, model_id = agent_model_config()
    trial = EvaluationRunner(store, config).run_case(case, OpenRouterModel(api_key, model_id))
    payload = trial.to_dict()
    payload["baseline_expectation"] = scenario.baseline_expectation
    payload["baseline_expectation_matched"] = baseline_expectation_matches(trial, scenario.baseline_expectation)
    _emit(payload)
    return 0 if payload["baseline_expectation_matched"] else 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = load_config()
        uri, database_name = atlas_config()
        with MongoClient(uri, serverSelectionTimeoutMS=10000, connectTimeoutMS=5000) as client:
            client.admin.command("ping")
            store = AtlasTableStore(client[database_name], config)
            store.ensure_indexes()
            if args.command == "seed":
                fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
                info = store.materialize(fixture["dataset_id"], fixture["rows"])
                _emit({"dataset_id": info.dataset_id, "row_count": info.row_count, "content_hash": info.content_hash})
                return 0
            if args.command == "eval":
                return _run_evaluation_command(args, store, config)
            task = json.loads(args.task) if args.task is not None else args.question
            if args.task is not None and not isinstance(task, dict):
                raise ValueError("Task must be a JSON object")
            table = store.open_session(args.dataset)
            api_key, model_id = agent_model_config()
            model = OpenRouterModel(api_key, model_id)
            result = AnalystAgent(model, AnalystTools(table, config), config).run(task)
            return _present_run(result, conversational=args.question is not None, json_output=args.json)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, DatasetError, ScenarioError, OracleError) as exc:
        _emit({"error": str(exc)})
        return 2
    except PyMongoError as exc:
        _emit({"error": f"Atlas operation failed: {type(exc).__name__}"})
        return 3
    except OSError as exc:
        _emit({"error": f"File operation failed: {type(exc).__name__}"})
        return 4


if __name__ == "__main__":
    sys.exit(main())
