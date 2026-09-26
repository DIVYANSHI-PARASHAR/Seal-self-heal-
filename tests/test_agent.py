import json
from dataclasses import replace
from pathlib import Path

import mongomock

from harness.agent import AnalystAgent
from harness.tools import AnalystTools, ToolError
from self_heal.model import ModelReply, ToolCall
from self_heal.settings import load_config
from self_heal.table_store import AtlasTableStore


FIXTURE = Path(__file__).resolve().parents[1] / "evals" / "analyst" / "data" / "small_inventory.json"


class ScriptedModel:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.seen = []

    def complete(self, messages, tools):
        self.seen.append((messages, tools))
        return next(self.replies)


def call(name, arguments, number):
    return ModelReply(None, (ToolCall(f"call-{number}", name, json.dumps(arguments)),), 100)


def make_agent(model, config=None):
    config = config or load_config()
    store = AtlasTableStore(mongomock.MongoClient()["test"], config)
    store.ensure_indexes()
    store.materialize("small", json.loads(FIXTURE.read_text())["rows"])
    table = store.open_session("small")
    tools = AnalystTools(table, config)
    return AnalystAgent(model, tools, config)


def test_scripted_agent_answers_with_only_three_registered_tools():
    model = ScriptedModel(
        [
            call("inspect_table", {}, 1),
            call("read_rows", {"limit": 4, "filter_field": "warehouse", "filter_value": "East"}, 2),
            call("calculate", {"operation": "sum", "values": [8, 5, 5]}, 3),
            ModelReply('{"value":18}', (), 100),
        ]
    )
    agent = make_agent(model)
    result = agent.run({"metric": "available", "filter_field": "warehouse", "filter_value": "East"})
    assert result.error is None
    assert result.answer == {"value": 18}
    assert result.model_calls == 4
    assert result.tool_calls == 3
    assert result.table_pages == 1
    assert {tool["function"]["name"] for tool in model.seen[0][1]} == {"inspect_table", "read_rows", "calculate"}
    assert model.seen[-1][0][-1]["role"] == "tool"


def test_model_call_limit_and_invalid_final_answer_fail_clearly():
    config = load_config()
    limited = replace(config, limits=replace(config.limits, max_model_calls=2))
    model = ScriptedModel([call("inspect_table", {}, 1), call("inspect_table", {}, 2)])
    result = make_agent(model, limited).run({"metric": "on_hand"})
    assert result.error == "Model-call budget exceeded before a final answer"
    assert result.answer is None
    invalid = make_agent(ScriptedModel([ModelReply("not json")])).run({"metric": "on_hand"})
    assert invalid.error == "Model final answer is not JSON"
    guessed = make_agent(ScriptedModel([ModelReply('{"value":18}')])).run({"metric": "available"})
    assert guessed.error == "Required table rows were not fully read"


def test_unregistered_tool_and_invalid_calculation_are_rejected():
    agent = make_agent(ScriptedModel([]))
    assert {tool["function"]["name"] for tool in agent.tools.definitions()} == {
        "inspect_table", "read_rows", "calculate"
    }
    try:
        agent.tools.execute("aggregate_rows", {})
    except ToolError as exc:
        assert "not registered" in str(exc)
    else:
        raise AssertionError("Unregistered tool was accepted")
    try:
        agent.tools.execute("read_rows", {"limit": 1, "dataset_id": "other"})
    except ToolError as exc:
        assert "Unsupported" in str(exc)
    else:
        raise AssertionError("Dataset switching was accepted")
    try:
        agent.tools.execute("calculate", {"operation": "difference", "values": [1, 2, 3]})
    except ToolError:
        pass
    else:
        raise AssertionError("Invalid calculation was accepted")
