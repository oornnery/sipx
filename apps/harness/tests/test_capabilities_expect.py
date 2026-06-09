import asyncio

import pytest

from sipx_harness import (
    CallRuntime,
    DtmfRuntime,
    MockRuntime,
    RuntimeCapability,
    UnsupportedExpectation,
    expect,
)
from sipx_harness.expect import ExpectationFailure


def test_mock_runtime_implements_core_runtime_abcs() -> None:
    runtime = MockRuntime()

    assert isinstance(runtime, CallRuntime)
    assert isinstance(runtime, DtmfRuntime)


def test_supported_capability_passes() -> None:
    async def run() -> None:
        result = (
            await expect(MockRuntime())
            .to_support(RuntimeCapability.CALL_CONTROL)
            .within()
        )

        assert result.status == "passed"

    asyncio.run(run())


def test_unsupported_capability_fails_loud() -> None:
    async def run() -> None:
        with pytest.raises(UnsupportedExpectation):
            await expect(MockRuntime()).to_support(RuntimeCapability.SIP_WIRE).within()

    asyncio.run(run())


def test_within_reports_rich_failure() -> None:
    async def run() -> None:
        with pytest.raises(ExpectationFailure) as failure:
            await (
                expect(False)
                .truthy(lambda value: bool(value), name="false check")
                .within()
            )

        assert failure.value.result.name == "false check"
        assert failure.value.result.status == "failed"

    asyncio.run(run())
