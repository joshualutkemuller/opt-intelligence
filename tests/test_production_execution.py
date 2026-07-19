"""Tests for production optimizer execution isolation backends."""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest

from decision_intelligence.production_optimizers import (
    ExecutionIsolationSpec,
    InProcessExecutionBackend,
    RestExecutionBackend,
    SubprocessExecutionBackend,
    backend_for_spec,
    execute_isolated,
)


def test_in_process_execution_backend_runs_callable_problem() -> None:
    spec = ExecutionIsolationSpec(mode="in_process")

    result = InProcessExecutionBackend().execute(
        spec,
        {
            "value": 21,
            "callable": lambda problem: {
                "status": "optimal",
                "objective_value": problem["value"] * 2,
            },
        },
    )

    assert result == {"status": "optimal", "objective_value": 42}


def test_subprocess_execution_backend_exchanges_json_over_stdio() -> None:
    spec = ExecutionIsolationSpec(
        mode="subprocess",
        timeout_seconds=5,
        command=[
            sys.executable,
            "-c",
            (
                "import json, sys; "
                "payload=json.load(sys.stdin); "
                "problem=payload['problem']; "
                "print(json.dumps({'status':'optimal', "
                "'objective_value': problem['value'] * 3, "
                "'execution_mode': payload['spec']['mode']}))"
            ),
        ],
    )

    result = SubprocessExecutionBackend().execute(spec, {"value": 14})

    assert result == {
        "status": "optimal",
        "objective_value": 42,
        "execution_mode": "subprocess",
    }


def test_subprocess_execution_backend_rejects_missing_command() -> None:
    spec = ExecutionIsolationSpec(mode="subprocess")

    with pytest.raises(ValueError, match="spec.command"):
        SubprocessExecutionBackend().execute(spec, {"value": 1})


def test_rest_execution_backend_posts_json_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        status = 200

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "status": "optimal",
                    "objective_value": captured["problem"]["value"] + 1,
                }
            ).encode("utf-8")

    def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
        captured["timeout"] = timeout
        captured["url"] = request.full_url
        captured.update(json.loads(request.data.decode("utf-8")))
        return FakeResponse()

    monkeypatch.setattr(
        "decision_intelligence.production_optimizers.execution.urllib_request.urlopen",
        fake_urlopen,
    )
    spec = ExecutionIsolationSpec(
        mode="rest",
        endpoint="http://optimizer.internal/solve",
        timeout_seconds=11,
    )

    result = RestExecutionBackend().execute(spec, {"value": 41})

    assert result == {"status": "optimal", "objective_value": 42}
    assert captured["url"] == "http://optimizer.internal/solve"
    assert captured["timeout"] == 11
    assert captured["spec"]["mode"] == "rest"
    assert captured["problem"]["value"] == 41


def test_execute_isolated_selects_backend_from_spec() -> None:
    spec = ExecutionIsolationSpec(mode="in_process")

    result = execute_isolated(
        spec,
        {"callable": lambda _problem: {"status": "optimal"}},
    )

    assert result == {"status": "optimal"}
    assert isinstance(backend_for_spec(spec), InProcessExecutionBackend)
