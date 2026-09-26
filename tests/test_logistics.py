from datetime import datetime, timezone

import mongomock
import pytest

from evals.logistics.generator import public_incident_bundle
from evals.logistics.oracle import reference_answer
from harness.agent import AnalystAgent
from harness.tools import AnalystTools
from self_heal.input_router import InputRouter
from self_heal.logistics_store import LogisticsDatasetStore
from self_heal.settings import load_config
from self_heal.table_store import AtlasTableStore, DatasetError, TableAccessError


def materialized_store():
    database = mongomock.MongoClient()["test"]
    store = LogisticsDatasetStore(database)
    store.ensure_indexes()
    bundle = public_incident_bundle()
    info = store.materialize("logistics-shipment-threshold-public-v1", **bundle)
    return store, database, info, bundle


def test_public_bundle_is_immutable_and_oracle_is_hand_checked():
    store, database, info, bundle = materialized_store()
    task = {"operation": "count_customers_with_shipment_count_gt", "warehouse_number": 3, "relative_day": "yesterday", "threshold": 15}
    assert info.relations["shipments"]["row_count"] == 74
    assert reference_answer(bundle, task) == {"value": 2}
    assert store.materialize(info.dataset_id, **bundle) == info
    changed = {**bundle, "shipments": bundle["shipments"][:-1]}
    with pytest.raises(DatasetError, match="cannot be changed"):
        store.materialize(info.dataset_id, **changed)
    database.logistics_shipments.update_one({"dataset_id": info.dataset_id, "position": 0}, {"$set": {"status": "cancelled"}})
    with pytest.raises(DatasetError, match="content changed"):
        store.dataset_info(info.dataset_id)


def test_bundle_validation_rejects_foreign_keys_timestamps_and_duplicates():
    bundle = public_incident_bundle()
    for mutation, message in [
        (lambda value: value["shipments"][0].update(sender_customer_id="missing"), "orphaned"),
        (lambda value: value["shipments"][0].update(sent_at="2026-09-27T00:00:00Z"), "later"),
        (lambda value: value["shipments"].append(dict(value["shipments"][0])), "Duplicate"),
        (lambda value: value.update(reporting_timezone="Not/AZone"), "timezone"),
    ]:
        candidate = public_incident_bundle()
        mutation(candidate)
        store = LogisticsDatasetStore(mongomock.MongoClient()["test"])
        with pytest.raises(DatasetError, match=message):
            store.materialize("bad", **candidate)


def test_logistics_session_is_filter_bound_and_cursor_bound():
    store, _, info, _ = materialized_store()
    session = store.open_session(info.dataset_id)
    assert session.inspect_catalog()["relations"]["shipments"]["row_count"] == 74
    first = session.read_shipments(warehouse_number=3, relative_day="yesterday", limit=4)
    assert len(first["shipments"]) == 4
    assert first["next_cursor"]
    with pytest.raises(TableAccessError, match="cursor"):
        session.read_shipments(warehouse_number=2, relative_day="yesterday", limit=4, cursor=first["next_cursor"])
    with pytest.raises(TableAccessError, match="Invalid"):
        session.read_shipments(warehouse_number=3, relative_day="today", limit=4)


class NoCallsModel:
    def complete(self, *_args):
        raise AssertionError("The baseline must refuse before any model or data access")


def test_inventory_baseline_records_explicit_logistics_capability_gap_without_reads():
    config = load_config()
    inventory = AtlasTableStore(mongomock.MongoClient()["test"], config)
    inventory.ensure_indexes()
    inventory.materialize("inventory", [{"sku": "A", "warehouse": "East", "category": "Hardware", "on_hand": 1, "reserved": 0}])
    table = inventory.open_session("inventory")
    result = AnalystAgent(NoCallsModel(), AnalystTools(table, config), config).run(
        "How many customers sent more than 15 shipments from warehouse 3 yesterday?"
    )
    assert result.outcome == "unsupported"
    assert result.limitation_kind == "capability_gap"
    assert result.capability_request and result.capability_request["kind"] == "shipment_customer_threshold"
    assert result.model_calls == result.tool_calls == result.table_pages == result.table_bytes == 0


def test_router_requires_an_explicit_input_kind():
    config = load_config()
    database = mongomock.MongoClient()["test"]
    tables = AtlasTableStore(database, config)
    tables.ensure_indexes()
    tables.materialize("inventory", [{"sku": "A", "warehouse": "East", "category": "Hardware", "on_hand": 1, "reserved": 0}])
    logistics = LogisticsDatasetStore(database); logistics.ensure_indexes()
    logistics.materialize("logistics", **public_incident_bundle())
    router = InputRouter(tables, logistics)
    assert router.describe(input_kind="inventory_table", dataset_id="inventory").domain == "inventory"
    assert router.describe(input_kind="logistics_bundle", dataset_id="logistics").relation_counts == {"customers": 8, "warehouses": 3, "shipments": 74}
    with pytest.raises(ValueError, match="input kind"):
        router.describe(input_kind="unknown", dataset_id="inventory")
