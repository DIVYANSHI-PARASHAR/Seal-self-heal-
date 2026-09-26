"""Untrusted process entry point. Only line-delimited supervisor RPC crosses stdio."""

import json
import sys
from dataclasses import asdict
from types import SimpleNamespace

from self_heal.model import ModelReply, ToolCall
from self_heal.table_store import TableAccessError


WIRE = sys.stdout
sys.stdout = sys.stderr  # Candidate prints cannot masquerade as protocol messages.


def rpc(message):
    WIRE.write(json.dumps(message, separators=(",", ":")) + "\n")
    WIRE.flush()
    line = sys.stdin.readline()
    if not line:
        raise RuntimeError("Supervisor bridge closed")
    response = json.loads(line)
    if not response.get("ok"):
        raise RuntimeError(response.get("error", "Supervisor rejected request"))
    return response.get("value")


class RemoteModel:
    def complete(self, messages, tools):
        value = rpc({"type": "model", "messages": messages, "tools": tools})
        return ModelReply(
            content=value.get("content"),
            tool_calls=tuple(ToolCall(**call) for call in value.get("tool_calls", [])),
            total_tokens=value.get("total_tokens", 0),
        )


class RemoteTable:
    def __init__(self):
        self.pages_read = 0
        self.bytes_read = 0

    def inspect_table(self):
        return rpc({"type": "table", "operation": "inspect_table", "arguments": {}})

    def read_rows(self, **arguments):
        try:
            value = rpc({"type": "table", "operation": "read_rows", "arguments": arguments})
        except RuntimeError as exc:
            raise TableAccessError(str(exc)) from exc
        self.pages_read += 1
        return value

    def completed_scan(self, filter_field, filter_value):
        return rpc({"type": "table", "operation": "completed_scan", "arguments": {
            "filter_field": filter_field, "filter_value": filter_value,
        }})


class ObservedTools:
    def __init__(self, inner):
        self.inner = inner
        self.table = inner.table

    def definitions(self):
        return self.inner.definitions()

    def execute(self, name, arguments):
        try:
            value = self.inner.execute(name, arguments)
        except Exception as exc:
            rpc({"type": "tool_result", "name": name, "arguments": arguments,
                 "result": {"error_type": type(exc).__name__}})
            raise
        rpc({"type": "tool_result", "name": name, "arguments": arguments, "result": value})
        return value


def namespace(value):
    if isinstance(value, dict):
        return SimpleNamespace(**{key: namespace(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(namespace(item) for item in value)
    return value


def main():
    initial = json.loads(sys.stdin.readline())
    from harness.agent import AnalystAgent
    from harness.tools import AnalystTools

    table = RemoteTable()
    agent = AnalystAgent(RemoteModel(), ObservedTools(AnalystTools(table, namespace(initial["config"]))),
                         namespace(initial["config"]))
    try:
        result = agent.run(initial["invocation"], run_id=initial["run_id"])
        payload = {key: getattr(result, key, None) for key in (
            "answer", "error", "outcome", "interpreted_task", "limitation_kind", "limitation_reason"
        )}
        rpc({"type": "result", "value": payload})
    except BaseException as exc:
        rpc({"type": "result", "value": {"answer": None, "outcome": "error",
             "error": f"Candidate failure: {type(exc).__name__}"}})


if __name__ == "__main__":
    main()
