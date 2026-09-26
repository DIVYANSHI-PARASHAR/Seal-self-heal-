"""Browser-facing contract tests for the local Phase 3 operator interface."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import mongomock
import pytest

from self_heal.model import ModelReply, ToolCall
from self_heal.settings import LangSmithConfig, load_config
from self_heal.storage import AtlasHistoryStore
from self_heal.table_store import AtlasTableStore
from self_heal.telemetry import LangSmithTelemetry
from self_heal.web import WebApplication, create_server


FIXTURE = Path(__file__).resolve().parents[1] / "evals" / "analyst" / "data" / "small_inventory.json"


class ScriptedModel:
    def __init__(self, replies: list[ModelReply]) -> None:
        self.replies = iter(replies)

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelReply:
        return next(self.replies)


def supported_model() -> ScriptedModel:
    return ScriptedModel(
        [
            ModelReply('{"metric":"available","filter_field":"warehouse","filter_value":"East"}', (), 10),
            ModelReply(
                None,
                (ToolCall("read-east", "read_rows", '{"limit":4,"filter_field":"warehouse","filter_value":"East"}'),),
                10,
            ),
            ModelReply('{"value":18}', (), 10),
        ]
    )


def unsupported_model() -> ScriptedModel:
    return ScriptedModel([ModelReply('{"error":"Revenue is outside the inventory contract"}', (), 10)])


def make_application(model_factory):
    config = load_config()
    database = mongomock.MongoClient()["test"]
    store = AtlasTableStore(database, config)
    store.ensure_indexes()
    store.materialize("small", json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"])
    history = AtlasHistoryStore(database)
    history.ensure_indexes()
    tracing = LangSmithConfig(enabled=False, api_key=None, project="self-heal-test", workspace_id=None)
    return WebApplication(
        store=store,
        history=history,
        config=config,
        telemetry=LangSmithTelemetry(tracing),
        model_factory=model_factory,
        tracing=tracing,
    )


@pytest.fixture
def local_server():
    server = create_server(make_application(supported_model), port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def request_json(base_url: str, path: str, *, method: str = "GET", body: dict[str, Any] | None = None):
    encoded = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(
        base_url + path,
        data=encoded,
        method=method,
        headers={"Content-Type": "application/json"} if encoded is not None else {},
    )
    with urlopen(request, timeout=2) as response:  # noqa: S310 -- loopback test server
        return response.status, json.loads(response.read())


def test_local_ui_serves_assets_and_only_dataset_metadata(local_server):
    with urlopen(local_server + "/", timeout=2) as response:  # noqa: S310 -- loopback test server
        page = response.read().decode("utf-8")
    assert "What would you like to analyze?" in page
    assert "v1 → v2" not in page

    status, datasets = request_json(local_server, "/api/datasets")
    assert status == 200
    assert datasets["datasets"] == [{"id": "small", "row_count": 6, "content_hash": datasets["datasets"][0]["content_hash"]}]
    assert "A-100" not in repr(datasets)

    with pytest.raises(HTTPError) as error:
        urlopen(local_server + "/%2e%2e/pyproject.toml", timeout=2)  # noqa: S310 -- loopback test server
    assert error.value.code == 404


def test_local_ui_runs_the_phase_three_executor_and_exposes_compact_evidence(local_server):
    status, run = request_json(
        local_server,
        "/api/runs",
        method="POST",
        body={"dataset_id": "small", "question": "How many available units are in the East warehouse?"},
    )
    assert status == 201
    assert run["outcome"] == "answered"
    assert run["answer"] == {"value": 18}
    assert run["dataset"] == {"id": "small", "row_count": 6}
    assert run["resources"]["table_pages"] == 1
    assert run["history"]["status"] == "recorded"
    assert run["trace"]["status"] == "disabled"
    assert "A-100" not in repr(run)

    _, history = request_json(local_server, "/api/runs?limit=20")
    assert [entry["run_id"] for entry in history["runs"]] == [run["run_id"]]
    _, stored = request_json(local_server, "/api/runs/" + run["run_id"])
    assert stored["answer"] == {"value": 18}
    assert stored["trace"]["status"] == "disabled"


def test_local_ui_records_unsupported_questions_as_capability_gaps():
    server = create_server(make_application(unsupported_model), port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    base_url = f"http://{host}:{port}"
    try:
        _, run = request_json(
            base_url,
            "/api/runs",
            method="POST",
            body={"dataset_id": "small", "question": "What is total revenue?"},
        )
        assert run["outcome"] == "unsupported"
        assert run["limitation_kind"] == "capability_gap"
        _, gaps = request_json(base_url, "/api/capability-gaps")
        assert [entry["run_id"] for entry in gaps["runs"]] == [run["run_id"]]
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def test_local_ui_rejects_malformed_run_requests(local_server):
    request = Request(
        local_server + "/api/runs",
        data=b'{"dataset_id":"small"}',
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with pytest.raises(HTTPError) as error:
        urlopen(request, timeout=2)  # noqa: S310 -- loopback test server
    assert error.value.code == 400
    assert json.loads(error.value.read())["error"] == "A run needs exactly dataset_id and question"
