"""Protected Phase 2 evaluator for fixed analyst scenarios."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Callable, Iterable

from evals.analyst.generator import MaterializedCase, PreparedCase, materialize_case
from harness.agent import AnalystAgent, RunResult
from harness.tools import AnalystTools
from self_heal.contracts import (
    build_eval_case_record,
    build_evaluation_record,
    new_trial_id,
    stable_case_id,
    utc_now,
)
from self_heal.execution import RunExecutor
from self_heal.model import ChatModel
from self_heal.settings import AnalystConfig
from self_heal.storage import AtlasHistoryStore, HistoryError
from self_heal.table_store import AtlasTableStore


@dataclass(frozen=True)
class EvaluationTrial:
    scenario_id: str
    dataset_id: str
    dataset_hash: str
    dataset_row_count: int
    scenario_seed: int | None
    task: dict[str, Any]
    expected_answer: dict[str, Any]
    answer: dict[str, Any] | None
    outcome: str
    error: str | None
    passed: bool
    violation: str | None
    model_calls: int
    tool_calls: int
    total_tokens: int
    elapsed_seconds: float
    table_pages: int
    table_bytes: int
    run_id: str = ""
    case_id: str | None = None
    trace_id: str | None = None
    trace_url: str | None = None
    trace_status: str = "not_traced"
    history_status: str = "not_recorded"
    trial_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvaluationRunner:
    """Runs fixed cases through a fresh scoped Atlas table session and retains every trial."""

    def __init__(
        self,
        store: AtlasTableStore,
        config: AnalystConfig,
        *,
        executor: RunExecutor | None = None,
        history: AtlasHistoryStore | None = None,
    ) -> None:
        self.store = store
        self.config = config
        self.executor = executor
        self.history = history
        self.trials: list[EvaluationTrial] = []

    def run_case(self, case: PreparedCase, model: ChatModel) -> EvaluationTrial:
        materialized = materialize_case(self.store, case)
        case_id = stable_case_id(
            scenario_id=case.scenario.scenario_id,
            dataset=materialized.dataset,
            task=case.scenario.task,
            oracle_version=self.config.evaluation.oracle_version,
        )
        history_status = "not_recorded"
        if self.history is not None:
            try:
                self.history.record_eval_case(
                    build_eval_case_record(
                        case_id=case_id,
                        scenario_id=case.scenario.scenario_id,
                        dataset=materialized.dataset,
                        task=case.scenario.task,
                        expected_answer=case.expected_answer,
                        oracle_version=self.config.evaluation.oracle_version,
                        config=self.config,
                        exposure_role="baseline",
                        created_at=utc_now(),
                    )
                )
                history_status = "recording"
            except (HistoryError, OSError):
                history_status = "incomplete"
        table = self.store.open_session(materialized.dataset.dataset_id)
        tools = AnalystTools(table, self.config)
        invocation: dict[str, Any] | str = case.scenario.question or case.scenario.task
        trace = None
        if self.executor is not None:
            execution = self.executor.run(
                model=model,
                tools=tools,
                dataset=materialized.dataset,
                invocation=invocation,
                case_id=case_id,
                case_exposure="baseline",
            )
            result = execution.result
            trace = execution.trace
            history_status = execution.history_status if history_status != "incomplete" else "incomplete"
        else:
            result = AnalystAgent(model, tools, self.config).run(invocation)
        trial_id = new_trial_id()
        trial = assess_run(
            materialized,
            result,
            self.config,
            case_id=case_id,
            trace_id=trace.trace_id if trace is not None else None,
            trace_url=trace.url if trace is not None else None,
            trace_status=trace.status if trace is not None else "not_traced",
            history_status=history_status,
            trial_id=trial_id,
        )
        if self.history is not None:
            try:
                self.history.record_evaluation(
                    build_evaluation_record(
                        evaluation_id=trial_id,
                        case_id=case_id,
                        result=result,
                        passed=trial.passed,
                        violation=trial.violation,
                        dataset=materialized.dataset,
                        trace=trace,
                        config=self.config,
                        created_at=utc_now(),
                    )
                )
                if history_status == "recording":
                    trial = replace(trial, history_status="recorded")
            except (HistoryError, OSError):
                trial = replace(trial, history_status="incomplete")
        self.trials.append(trial)
        return trial

    def run_cases(
        self,
        cases: Iterable[PreparedCase],
        model_factory: Callable[[], ChatModel],
    ) -> tuple[EvaluationTrial, ...]:
        return tuple(self.run_case(case, model_factory()) for case in cases)


def assess_run(
    materialized: MaterializedCase,
    result: RunResult,
    config: AnalystConfig,
    *,
    case_id: str | None = None,
    trace_id: str | None = None,
    trace_url: str | None = None,
    trace_status: str = "not_traced",
    history_status: str = "not_recorded",
    trial_id: str | None = None,
) -> EvaluationTrial:
    """Grade a harness result outside the editable harness boundary."""
    violation = _resource_violation(result, config)
    if violation is None:
        if result.outcome == "unsupported":
            violation = "capability_refusal_for_answerable_case"
        elif result.outcome == "error":
            violation = _error_violation(result.error)
        elif result.answer is None:
            violation = "missing_answer"
        elif result.answer != materialized.case.expected_answer:
            violation = "wrong_answer"
    return EvaluationTrial(
        scenario_id=materialized.case.scenario.scenario_id,
        dataset_id=materialized.dataset.dataset_id,
        dataset_hash=materialized.dataset.content_hash,
        dataset_row_count=materialized.dataset.row_count,
        scenario_seed=materialized.case.scenario.seed,
        task=dict(materialized.case.scenario.task),
        expected_answer=dict(materialized.case.expected_answer),
        answer=dict(result.answer) if result.answer is not None else None,
        outcome=result.outcome,
        error=result.error,
        passed=violation is None,
        violation=violation,
        model_calls=result.model_calls,
        tool_calls=result.tool_calls,
        total_tokens=result.total_tokens,
        elapsed_seconds=result.elapsed_seconds,
        table_pages=result.table_pages,
        table_bytes=result.table_bytes,
        run_id=result.run_id,
        case_id=case_id,
        trace_id=trace_id,
        trace_url=trace_url,
        trace_status=trace_status,
        history_status=history_status,
        trial_id=trial_id,
    )


def baseline_expectation_matches(trial: EvaluationTrial, expectation: str) -> bool:
    if expectation == "pass":
        return trial.passed
    if expectation == "fails_model_call_budget":
        return trial.violation == "model_call_budget_exhausted"
    raise ValueError("Scenario does not describe an answerable baseline expectation")


def _resource_violation(result: RunResult, config: AnalystConfig) -> str | None:
    limits = config.limits
    if result.model_calls > limits.max_model_calls:
        return "model_call_limit_exceeded"
    if result.tool_calls > limits.max_tool_calls:
        return "tool_call_limit_exceeded"
    if result.total_tokens > limits.max_total_tokens:
        return "token_limit_exceeded"
    if result.elapsed_seconds > limits.max_elapsed_seconds:
        return "time_limit_exceeded"
    if result.table_pages > limits.max_pages:
        return "table_page_limit_exceeded"
    if result.table_bytes > limits.max_bytes:
        return "table_byte_limit_exceeded"
    return None


def _error_violation(error: str | None) -> str:
    if not error:
        return "agent_error"
    normalized = error.lower()
    if "model-call budget" in normalized:
        return "model_call_budget_exhausted"
    if "tool-call budget" in normalized:
        return "tool_call_budget_exhausted"
    if "token budget" in normalized:
        return "token_budget_exhausted"
    if "time budget" in normalized:
        return "time_budget_exhausted"
    if "table page budget" in normalized:
        return "table_page_budget_exhausted"
    if "table byte budget" in normalized:
        return "table_byte_budget_exhausted"
    if "required table rows" in normalized:
        return "incomplete_table_read"
    return "agent_error"
