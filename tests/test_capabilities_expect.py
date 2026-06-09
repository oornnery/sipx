import asyncio

import pytest

from sipx import BackendCapability, UnsupportedExpectation, expect
from sipx.backends import MockBackend
from sipx.core.expect import ExpectationFailure


def test_supported_capability_passes() -> None:
    async def run() -> None:
        result = (
            await expect(MockBackend())
            .to_support(BackendCapability.CALL_CONTROL)
            .within()
        )

        assert result.status == "passed"

    asyncio.run(run())


def test_unsupported_capability_fails_loud() -> None:
    async def run() -> None:
        with pytest.raises(UnsupportedExpectation):
            await expect(MockBackend()).to_support(BackendCapability.SIP_WIRE).within()

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
