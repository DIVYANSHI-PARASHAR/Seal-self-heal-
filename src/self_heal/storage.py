"""Compact, queryable supervisor history in the Atlas database.

Detailed model and tool payloads stay in LangSmith. This store keeps only the
identities and measurements needed to reproduce, evaluate, and evolve the
harness in later phases.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError


class HistoryError(RuntimeError):
    pass


class AtlasHistoryStore:
    def __init__(self, database: Database) -> None:
        self.runs = database["runs"]
        self.eval_cases = database["eval_cases"]
        self.candidates = database["candidates"]
        self.evaluations = database["evaluations"]
        self.versions = database["versions"]

    def ensure_indexes(self) -> None:
        """Create the Phase 3 query paths without a duplicate event collection."""

        self.runs.create_index([("run_id", ASCENDING)], unique=True)
        self.runs.create_index([("outcome", ASCENDING), ("limitation_kind", ASCENDING), ("created_at", DESCENDING)])
        self.runs.create_index([("invocation.task_family", ASCENDING), ("created_at", DESCENDING)])
        self.runs.create_index([("invocation.task_id", ASCENDING), ("created_at", DESCENDING)])
        self.runs.create_index([("dataset.id", ASCENDING), ("dataset.content_hash", ASCENDING)])
        self.runs.create_index([("execution.source.commit", ASCENDING), ("created_at", DESCENDING)])
        self.runs.create_index([("trace.root_id", ASCENDING)], unique=True, sparse=True)

        self.eval_cases.create_index([("case_id", ASCENDING)], unique=True)
        self.eval_cases.create_index([("task_family", ASCENDING), ("created_at", DESCENDING)])
        self.eval_cases.create_index([("dataset.id", ASCENDING), ("dataset.content_hash", ASCENDING)])
        self.eval_cases.create_index([("scenario_id", ASCENDING), ("created_at", DESCENDING)])

        self.candidates.create_index([("candidate_id", ASCENDING)], unique=True)
        self.candidates.create_index([("candidate_commit", ASCENDING)], unique=True, sparse=True)
        self.candidates.create_index(
            [("task_family", ASCENDING), ("changed_mechanism", ASCENDING), ("created_at", DESCENDING)]
        )

        self.evaluations.create_index([("evaluation_id", ASCENDING)], unique=True)
        self.evaluations.create_index([("trial_id", ASCENDING)], unique=True, sparse=True)
        self.evaluations.create_index([("run_id", ASCENDING), ("case_id", ASCENDING)], unique=True)
        self.evaluations.create_index([("case_id", ASCENDING), ("passed", ASCENDING), ("created_at", DESCENDING)])
        self.evaluations.create_index([("candidate.commit", ASCENDING), ("created_at", DESCENDING)])

        self.versions.create_index([("version_id", ASCENDING)], unique=True)
        self.versions.create_index([("identity_hash", ASCENDING)], unique=True, sparse=True)
        self.versions.create_index([("status", ASCENDING), ("created_at", DESCENDING)])

    def start_run(self, record: dict[str, Any]) -> None:
        self._require(record, "run_id", "_id")
        if record.get("status") != "running":
            raise HistoryError("Run must start in the running state")
        self._insert(self.runs, record, "run")

    def finish_run(self, run_id: str, completion: dict[str, Any]) -> None:
        completion = dict(completion)
        self._require(completion, "status", "completed_at", "trace", "resources")
        lifecycle_entry = completion.pop("lifecycle_entry", None)
        try:
            result = self.runs.update_one(
                {"_id": run_id, "status": "running"},
                {
                    "$set": completion,
                    "$push": {"lifecycle": lifecycle_entry},
                },
            )
        except PyMongoError as exc:
            raise HistoryError("Could not finalize run history") from exc
        if result.matched_count != 1:
            raise HistoryError("Run history record is missing or already finalized")

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self.runs.find_one({"_id": run_id})

    def recent_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        """Return compact run history ordered newest-first for the local UI."""

        if not 1 <= limit <= 100:
            raise ValueError("History limit must be between 1 and 100")
        return list(self.runs.find({"status": "completed"}).sort("created_at", DESCENDING).limit(limit))

    def capability_gaps(self, *, task_family: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        if not 1 <= limit <= 100:
            raise ValueError("History limit must be between 1 and 100")
        query: dict[str, Any] = {"outcome": "unsupported", "limitation_kind": "capability_gap"}
        if task_family:
            query["invocation.task_family"] = task_family
        return list(self.runs.find(query).sort("created_at", DESCENDING).limit(limit))

    def record_eval_case(self, record: dict[str, Any]) -> None:
        record = dict(record)
        self._require(record, "case_id", "_id", "task_family", "dataset", "oracle", "exposure")
        exposure = record.pop("exposure")
        try:
            existing = self.eval_cases.find_one({"_id": record["_id"]}, {"_id": 1})
            if existing:
                self.eval_cases.update_one({"_id": record["_id"]}, {"$push": {"exposures": exposure}})
            else:
                record["exposures"] = [exposure]
                self.eval_cases.insert_one(record)
        except DuplicateKeyError:
            # A concurrent materialization keeps the frozen case and records
            # this additional exposure instead of silently replacing it.
            self.eval_cases.update_one({"_id": record["_id"]}, {"$push": {"exposures": exposure}})
        except PyMongoError as exc:
            raise HistoryError("Could not record evaluation case") from exc

    def record_evaluation(self, record: dict[str, Any]) -> None:
        self._require(record, "evaluation_id", "trial_id", "_id", "run_id", "case_id", "created_at")
        self._insert(self.evaluations, record, "evaluation")

    def record_candidate(self, record: dict[str, Any]) -> None:
        record = dict(record)
        self._require(record, "candidate_id", "_id", "task_family", "changed_mechanism", "created_at")
        record.setdefault("status", "proposed")
        record.setdefault("lifecycle", [{"state": record["status"], "at": record["created_at"]}])
        self._insert(self.candidates, record, "candidate")

    def record_version(self, record: dict[str, Any]) -> None:
        record = dict(record)
        self._require(record, "version_id", "_id", "status", "created_at")
        record.setdefault("lifecycle", [{"state": record["status"], "at": record["created_at"]}])
        self._insert(self.versions, record, "version")

    def append_candidate_transition(
        self, candidate_id: str, *, status: str, at: datetime, reason: str | None = None
    ) -> None:
        self._append_transition(self.candidates, candidate_id, status=status, at=at, reason=reason)

    def append_version_transition(
        self, version_id: str, *, status: str, at: datetime, reason: str | None = None
    ) -> None:
        self._append_transition(self.versions, version_id, status=status, at=at, reason=reason)

    def candidates_for(
        self, *, task_family: str, changed_mechanism: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 100:
            raise ValueError("History limit must be between 1 and 100")
        query: dict[str, Any] = {"task_family": task_family}
        if changed_mechanism:
            query["changed_mechanism"] = changed_mechanism
        return list(self.candidates.find(query).sort("created_at", DESCENDING).limit(limit))

    @staticmethod
    def _require(record: dict[str, Any], *keys: str) -> None:
        missing = [key for key in keys if key not in record or record[key] is None]
        if missing:
            raise HistoryError("History record is missing required fields: " + ", ".join(missing))

    @staticmethod
    def _insert(collection: Any, record: dict[str, Any], kind: str) -> None:
        try:
            collection.insert_one(record)
        except DuplicateKeyError as exc:
            raise HistoryError(f"Duplicate immutable {kind} record") from exc
        except PyMongoError as exc:
            raise HistoryError(f"Could not record {kind} history") from exc

    @staticmethod
    def _append_transition(
        collection: Any, record_id: str, *, status: str, at: datetime, reason: str | None
    ) -> None:
        if not status:
            raise ValueError("History transition status is required")
        entry: dict[str, Any] = {"state": status, "at": at}
        if reason:
            entry["reason"] = reason
        try:
            result = collection.update_one({"_id": record_id}, {"$set": {"status": status}, "$push": {"lifecycle": entry}})
        except PyMongoError as exc:
            raise HistoryError("Could not append history transition") from exc
        if result.matched_count != 1:
            raise HistoryError("History record is unavailable for transition")
