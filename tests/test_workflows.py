"""Durable workflow and evolution-job contracts."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import mongomock

from harness.agent import RunResult
from self_heal.evolution_jobs import EvolutionJobService
from self_heal.execution import RunExecution
from self_heal.model import ModelReply, ToolCall
from self_heal.settings import LangSmithConfig, load_config
from self_heal.storage import AtlasHistoryStore
from self_heal.table_store import AtlasTableStore
from self_heal.telemetry import LangSmithTelemetry, TraceEvidence
from self_heal.web import WebApplication
from self_heal.workflow import extract_workflow, workflow_diff


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evals" / "analyst" / "data" / "small_inventory.json"


class Model:
    def __init__(self, replies: list[ModelReply]) -> None:
        self.replies = iter(replies)

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelReply:
        return next(self.replies)


def _history() -> AtlasHistoryStore:
    history = AtlasHistoryStore(mongomock.MongoClient()["workflow"])
    history.ensure_indexes()
    return history


def _application(replies: list[ModelReply]) -> WebApplication:
    config = load_config()
    history = _history()
    store = AtlasTableStore(history.runs.database, config)
    store.ensure_indexes()
    store.materialize("small", json.loads(FIXTURE.read_text())["rows"])
    tracing = LangSmithConfig(enabled=False, api_key=None, project="tests", workspace_id=None)
    return WebApplication(store=store, history=history, config=config,
                          telemetry=LangSmithTelemetry(tracing), model_factory=lambda: Model(list(replies)),
                          tracing=tracing)


def test_workflow_snapshot_is_typed_deduplicated_and_diffable():
    history, config = _history(), load_config()
    snapshot = extract_workflow(source=ROOT, source_commit="base", config=config)
    stored = history.record_workflow(snapshot.record)
    assert history.record_workflow(snapshot.record)["workflow_revision_id"] == stored["workflow_revision_id"]
    nodes = {node["id"]: node for node in stored["graph"]["nodes"]}
    assert nodes["agent:inventory"]["kind"] == "agent"
    assert nodes["tool:read_rows"]["group"] == "agent:inventory"
    assert nodes["data:atlas"]["kind"] == "data_source"
    assert stored["graph"]["metadata"]["runtime_mcp_servers"] == []

    candidate = extract_workflow(source=ROOT, source_commit="candidate", config=config)
    candidate_record = dict(candidate.record)
    candidate_record["graph"] = {**candidate_record["graph"], "nodes": [
        *candidate_record["graph"]["nodes"],
        {"id": "tool:proposed", "kind": "tool", "label": "proposed", "fingerprint": "changed"},
    ]}
    candidate_record["graph_hash"] = "candidate-graph"
    history.record_workflow(candidate_record)
    diff = workflow_diff(stored, candidate_record)
    assert [node["id"] for node in diff["nodes"]["added"]] == ["tool:proposed"]


def test_browser_run_binds_a_saved_workflow_and_queues_one_durable_job():
    app = _application([ModelReply('{"error":"Revenue is outside the inventory contract"}', (), 4)])
    _, run = app.api("POST", "/api/runs", {"dataset_id": "small", "question": "What is total revenue?"})
    assert run["workflow_revision_id"].startswith("workflow_")
    assert run["evolution_job_id"].startswith("evolution_")
    _, workflow = app.api("GET", "/api/harness-workflows/" + run["workflow_revision_id"])
    assert workflow["graph"]["nodes"]
    _, jobs = app.api("GET", "/api/evolution-jobs/" + run["evolution_job_id"] + "/events?after=0")
    assert [event["stage"] for event in jobs["events"]] == ["incident_classified", "workflow_snapshot_ready", "blocked"]
    _, repeated = app.evolution_jobs.queue(incident_run_id=run["run_id"], workflow_revision_id=run["workflow_revision_id"])
    assert repeated is False


def test_background_job_records_replayable_progress_without_a_browser():
    history = _history()
    history.runs.insert_one({"_id": "incident", "run_id": "incident", "status": "completed"})

    def controller_factory(progress):
        class Controller:
            def evolve(self, run_id):
                progress("proposal_received", {"candidate_id": "candidate", "hypothesis": "Add a bounded tool"})
                progress("evaluating", {"candidate_id": "candidate"})
                return {"run_id": run_id, "status": "open", "reason": "Selection rejected"}
        return Controller()

    service = EvolutionJobService(history=history, controller_factory=controller_factory)
    job, created = service.queue(incident_run_id="incident", workflow_revision_id="workflow_base", task_family="inventory-totals")
    assert created
    for _ in range(100):
        current = history.get_evolution_job(job["job_id"])
        if current and current.get("status") == "rejected":
            break
        time.sleep(0.01)
    current = history.get_evolution_job(job["job_id"])
    assert current and current["status"] == "rejected"
    events = history.evolution_events_after(job["job_id"])
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert [event["stage"] for event in events] == ["incident_classified", "workflow_snapshot_ready", "diagnosing", "proposal_received", "evaluating", "rejected"]
