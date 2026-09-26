"""Local web surface for the trusted Self-Heal supervisor.

The browser is deliberately thin: every run still travels through the same
execution path used by the CLI, and the only history exposed is the compact
evidence record intended for operator inspection. It is a local
operator interface, not an internet-facing authentication boundary.
"""

from __future__ import annotations

import json
import mimetypes
import os
import sysconfig
from collections.abc import Callable
from datetime import date, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from harness.agent import RunResult
from harness.tools import AnalystTools
from self_heal.execution import RunExecution, RunExecutor
from self_heal.model import ChatModel
from self_heal.settings import AnalystConfig, LangSmithConfig
from self_heal.storage import AtlasHistoryStore
from self_heal.table_store import AtlasTableStore, DatasetError, DatasetInfo
from self_heal.telemetry import LangSmithTelemetry
from self_heal.repository import CandidateRepository
from self_heal.runner import CandidateRunner


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_ASSET_ROOT = PROJECT_ROOT / "ui"
_INSTALLED_ASSET_ROOT = Path(sysconfig.get_path("data")) / "share" / "self-heal" / "ui"
ASSET_ROOT = _SOURCE_ASSET_ROOT if _SOURCE_ASSET_ROOT.is_dir() else _INSTALLED_ASSET_ROOT
MAX_REQUEST_BYTES = 8_192


class WebRequestError(ValueError):
    """An input error that is safe to present to a local operator."""


def _result_message(result: RunResult) -> str:
    if result.outcome == "unsupported":
        return "I can't answer that with my current capabilities."
    if result.outcome == "error":
        return f"Sorry, I couldn't complete that request: {result.error}."
    assert result.answer is not None and result.interpreted_task is not None
    task, answer = result.interpreted_task, result.answer
    metric = {"available": "available", "on_hand": "on-hand", "reserved": "reserved"}[task["metric"]]
    location = {
        "warehouse": f" in the {task.get('filter_value')} warehouse",
        "category": f" in the {task.get('filter_value')} category",
        "sku": f" for SKU {task.get('filter_value')}",
    }.get(task.get("filter_field"), "")
    if "groups" in answer:
        groups = answer["groups"]
        if not groups:
            return "I found no matching rows to group."
        values = "; ".join(f"{name}: {value}" for name, value in groups.items())
        return f"{metric.capitalize()} units by {task['group_by'].replace('_', ' ')}{location}: {values}."
    value = answer["value"]
    return f"There are {value} {metric} {'unit' if value == 1 else 'units'}{location or ' in this dataset'}."


def _run_payload(execution: RunExecution) -> dict[str, Any]:
    result = execution.result
    return {
        "run_id": result.run_id,
        "outcome": result.outcome,
        "message": _result_message(result),
        "answer": result.answer,
        "error": result.error,
        "interpreted_task": result.interpreted_task,
        "limitation_kind": result.limitation_kind,
        "limitation_reason": result.limitation_reason,
        "capability_request": result.capability_request,
        "resources": {
            "model_calls": result.model_calls,
            "tool_calls": result.tool_calls,
            "total_tokens": result.total_tokens,
            "elapsed_seconds": result.elapsed_seconds,
            "table_pages": result.table_pages,
            "table_bytes": result.table_bytes,
        },
        **execution.compact_evidence(),
    }


def _history_summary(record: dict[str, Any]) -> dict[str, Any]:
    invocation = record.get("invocation") or {}
    trace = record.get("trace") or {}
    return {
        "run_id": record.get("run_id"),
        "created_at": record.get("created_at"),
        "outcome": record.get("outcome"),
        "answer": record.get("answer"),
        "error": record.get("error"),
        "question": invocation.get("question"),
        "task": record.get("interpreted_task"),
        "dataset": record.get("dataset"),
        "resources": record.get("resources"),
        "limitation_kind": record.get("limitation_kind"),
        "limitation_reason": record.get("limitation_reason"),
        "capability_request": record.get("capability_request"),
        "trace": {
            "id": trace.get("root_id"),
            "url": trace.get("url"),
            "status": trace.get("status"),
            "project": trace.get("project"),
            "error_type": trace.get("error_type"),
        },
        "history_status": record.get("status"),
    }


class WebApplication:
    """A testable adapter from the local UI's API to trusted supervisor APIs."""

    def __init__(
        self,
        *,
        store: AtlasTableStore,
        history: AtlasHistoryStore,
        config: AnalystConfig,
        telemetry: LangSmithTelemetry,
        model_factory: Callable[[], ChatModel],
        tracing: LangSmithConfig,
    ) -> None:
        self.store = store
        self.history = history
        self.config = config
        self.telemetry = telemetry
        self.model_factory = model_factory
        self.tracing = tracing

    def api(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        """Dispatch a small same-origin API.  This method has no HTTP concerns."""

        route = urlsplit(path)
        query = parse_qs(route.query)
        if method == "GET" and route.path == "/api/health":
            return HTTPStatus.OK, {
                "atlas": "connected",
                "langsmith": "enabled" if self.tracing.enabled else "disabled",
                "task_contract_version": self.config.task_contract_version,
            }
        if method == "GET" and route.path == "/api/datasets":
            return HTTPStatus.OK, {
                "datasets": [
                    {"id": item.dataset_id, "row_count": item.row_count, "content_hash": item.content_hash}
                    for item in self.store.list_dataset_info()
                ]
            }
        if method == "GET" and route.path == "/api/runs":
            return HTTPStatus.OK, {"runs": [_history_summary(item) for item in self.history.recent_runs(limit=_limit(query))]}
        if method == "GET" and route.path == "/api/capability-gaps":
            return HTTPStatus.OK, {
                "runs": [_history_summary(item) for item in self.history.capability_gaps(limit=_limit(query))]
            }
        if method == "GET" and route.path.startswith("/api/runs/"):
            run_id = route.path.removeprefix("/api/runs/")
            if not run_id or "/" in run_id:
                raise WebRequestError("Run ID is invalid")
            record = self.history.get_run(run_id)
            if record is None:
                return HTTPStatus.NOT_FOUND, {"error": "Run history is unavailable"}
            return HTTPStatus.OK, _history_summary(record)
        if method == "POST" and route.path == "/api/runs":
            request = _run_request(body)
            execution, dataset = self._run(request)
            payload = _run_payload(execution)
            payload["question"] = request["question"]
            payload["dataset"] = {
                "id": dataset.dataset_id,
                "row_count": dataset.row_count,
            }
            return HTTPStatus.CREATED, payload
        return HTTPStatus.NOT_FOUND, {"error": "Endpoint not found"}

    def _run(self, request: dict[str, str]) -> tuple[RunExecution, DatasetInfo]:
        dataset_id = request.get("dataset_id")
        dataset = self.store.dataset_info(dataset_id) if dataset_id is not None else self._default_dataset()
        active = self.history.active_version(self.config.task_family)
        if active:
            source = CandidateRepository(PROJECT_ROOT).active_checkout(active["commit"])
            execution = CandidateRunner(
                store=self.store, config=self.config, history=self.history, telemetry=self.telemetry,
                image=os.environ.get("SELF_HEAL_RUNNER_IMAGE", "self-heal-runner:local"),
            ).run(source=source, source_commit=active["commit"], dataset=dataset,
                  invocation=request["question"], model=self.model_factory())
            return execution, dataset
        table = self.store.open_session(dataset.dataset_id)
        execution = RunExecutor(history=self.history, telemetry=self.telemetry, config=self.config).run(
            model=self.model_factory(),
            tools=AnalystTools(table, self.config),
            dataset=dataset,
            invocation=request["question"],
        )
        return execution, dataset

    def _default_dataset(self) -> DatasetInfo:
        """Choose the deterministic operator dataset for a browser run.

        Keep generated evaluation tables out of automatic selection. Explicit
        API requests can still name a dataset. Resolve the chosen dataset again
        to verify its immutable metadata before use.
        """

        datasets = self.store.list_dataset_info()
        if not datasets:
            raise WebRequestError("No ready datasets are available")
        protected_prefixes = ("eval-", "incident-", "private-")
        selected = next((item for item in datasets
                         if not item.dataset_id.casefold().startswith(protected_prefixes)), None)
        if selected is None:
            raise WebRequestError("No operator dataset is available; seed one before running a question")
        return self.store.dataset_info(selected.dataset_id)


def _limit(query: dict[str, list[str]]) -> int:
    value = query.get("limit", ["20"])[0]
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise WebRequestError("History limit must be an integer") from exc


def _run_request(body: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(body, dict) or not {"question"} <= set(body) <= {"dataset_id", "question"}:
        raise WebRequestError("A run needs question and an optional dataset_id")
    question = body["question"]
    if not isinstance(question, str) or not question.strip() or len(question) > 2_000:
        raise WebRequestError("Question must be 1 to 2000 characters")
    request = {"question": question.strip()}
    if "dataset_id" in body:
        dataset_id = body["dataset_id"]
        if not isinstance(dataset_id, str) or not dataset_id.strip() or len(dataset_id) > 100:
            raise WebRequestError("Dataset ID is invalid")
        request["dataset_id"] = dataset_id.strip()
    return request


def create_server(application: WebApplication, host: str = "127.0.0.1", port: int = 4173) -> ThreadingHTTPServer:
    """Create, but do not start, the local server (useful for tests too)."""

    if not 1 <= port <= 65_535 and port != 0:
        raise ValueError("Port must be between 1 and 65535")

    class Handler(_WebRequestHandler):
        app = application

    return ThreadingHTTPServer((host, port), Handler)


class _WebRequestHandler(BaseHTTPRequestHandler):
    app: WebApplication
    server_version = "SelfHealLocalUI/1.0"
    sys_version = ""

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch_api_or_asset()

    def do_POST(self) -> None:  # noqa: N802
        route = urlsplit(self.path)
        if not route.path.startswith("/api/"):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= MAX_REQUEST_BYTES:
                raise WebRequestError("Request body must be between 1 and 8192 bytes")
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
                raise WebRequestError("Request content type must be application/json")
            body = json.loads(self.rfile.read(length))
            status, payload = self.app.api("POST", self.path, body)
            self._send_json(status, payload)
        except (DatasetError, WebRequestError, ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Run could not be completed"})

    def _dispatch_api_or_asset(self) -> None:
        route = urlsplit(self.path)
        if route.path.startswith("/api/"):
            try:
                status, payload = self.app.api("GET", self.path)
                self._send_json(status, payload)
            except (WebRequestError, ValueError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except Exception:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Service is unavailable"})
            return
        self._send_asset(route.path)

    def _send_asset(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else unquote(request_path).lstrip("/")
        candidate = (ASSET_ROOT / relative).resolve()
        if ASSET_ROOT not in candidate.parents and candidate != ASSET_ROOT:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file() or candidate.suffix not in {".css", ".html", ".js", ".svg"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        payload = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, status: int | HTTPStatus, payload: dict[str, Any]) -> None:
        rendered = json.dumps(payload, default=_json_default, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(rendered)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(rendered)

    def log_message(self, format: str, *args: Any) -> None:
        """Keep routine browser requests out of the operator's terminal."""


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)
