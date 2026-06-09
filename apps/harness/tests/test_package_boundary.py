import sipx
import sipx_harness


def test_harness_symbols_live_in_harness_package() -> None:
    assert sipx_harness.Harness is not None
    assert sipx_harness.Timeline is not None
    assert sipx_harness.MockRuntime is not None
    assert sipx_harness.Redactor is not None

    assert not hasattr(sipx, "Harness")
    assert not hasattr(sipx, "Timeline")
    assert not hasattr(sipx, "MockRuntime")
    assert not hasattr(sipx, "Redactor")
    assert not hasattr(sipx, "default_redactor")
