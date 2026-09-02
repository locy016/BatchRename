from __future__ import annotations

import json
from pathlib import Path

from batch_rename.history import OperationLog, OperationStatus


FIXTURE_ROOT = Path(__file__).parents[2] / "tests" / "fixtures"


def test_rule_fixtures_cover_public_behaviors() -> None:
    payload = json.loads((FIXTURE_ROOT / "rules-v1.json").read_text(encoding="utf-8"))
    cases = payload["cases"]

    assert payload["schemaVersion"] == 1
    assert len([case for case in cases if case["id"].startswith("template-")]) == 15
    assert any(case["id"] == "plain-text" for case in cases)
    assert any(case["id"] == "protected-extension" for case in cases)
    assert any(case["id"] == "unchanged" for case in cases)
    assert any(case["id"] == "invalid-reference" for case in cases)


def test_operation_fixtures_are_readable_and_cover_recovery_states() -> None:
    expected = {
        "operation-completed-v1.json": OperationStatus.COMPLETED,
        "operation-partial-v1.json": OperationStatus.PARTIAL,
        "operation-interrupted-v1.json": OperationStatus.INTERRUPTED,
        "operation-partially-undone-v1.json": OperationStatus.PARTIALLY_UNDONE,
    }

    for filename, status in expected.items():
        payload = json.loads((FIXTURE_ROOT / "logs" / filename).read_text(encoding="utf-8"))
        operation = OperationLog.from_dict(payload)
        assert operation.schema_version == 1
        assert operation.status is status
        assert operation.items
        assert "loc" not in str(operation.root).casefold()
