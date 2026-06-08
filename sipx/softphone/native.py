from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sipx.backends.native import (
    NativeSipBackend,
    NativeSipCall,
    NativeSipCallState,
    NativeSipLabHooks,
    NativeSipRetransmissionPolicy,
)
from sipx.core.timeline import Timeline
from sipx.sip.register import RegisterClientState
from sipx.sip.transport import UdpAddress
from sipx.sip.uri import SipUri


class NativeSoftphoneError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class NativeSoftphoneAccount:
    aor: SipUri | str
    registrar: SipUri | str
    username: str | None = None
    password: str | None = None
    contact_user: str | None = None
    expires: int = 3600

    def __post_init__(self) -> None:
        object.__setattr__(self, "aor", _sip_uri(self.aor))
        object.__setattr__(self, "registrar", _sip_uri(self.registrar))
        if self.expires <= 0:
            raise ValueError("expires must be positive")

    @property
    def user(self) -> str:
        return self.contact_user or self.aor.user or "softphone"


@dataclass(frozen=True, slots=True)
class NativeSoftphoneConfig:
    account: NativeSoftphoneAccount
    remote: UdpAddress
    mode: str = "strict"
    local_host: str = "127.0.0.1"
    local_port: int = 0
    actor_id: str = "softphone"
    timeout: float = 1.0
    retransmission_policy: NativeSipRetransmissionPolicy | None = None
    lab_hooks: NativeSipLabHooks | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"strict", "lab"}:
            raise ValueError("mode must be strict or lab")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if not self.actor_id:
            raise ValueError("actor_id is required")


class NativeSoftphone:
    def __init__(
        self,
        config: NativeSoftphoneConfig,
        *,
        backend: NativeSipBackend | None = None,
        timeline: Timeline | None = None,
    ) -> None:
        self.config = config
        self.timeline = timeline or Timeline()
        self.backend = backend or NativeSipBackend(
            local_host=config.local_host,
            local_port=config.local_port,
            mode=config.mode,
            timeline=self.timeline,
            actor_id=config.actor_id,
            retransmission_policy=config.retransmission_policy,
            lab_hooks=config.lab_hooks,
        )
        if self.backend.mode != config.mode:
            raise NativeSoftphoneError("backend mode does not match softphone config")
        self._started = False

    @property
    def local_address(self) -> UdpAddress:
        return self.backend.local_address

    @property
    def contact(self) -> SipUri:
        if not self._started:
            raise NativeSoftphoneError(
                "softphone must be started before contact is known"
            )
        host, port = self.local_address
        return SipUri(
            scheme="sip",
            user=self.config.account.user,
            host=host,
            port=port,
        )

    async def start(self) -> NativeSoftphone:
        if self._started:
            return self
        await self.backend.start()
        self._started = True
        self._record(
            "started",
            {"mode": self.config.mode, "aor": str(self.config.account.aor)},
        )
        return self

    async def stop(self) -> None:
        if not self._started:
            return
        await self.backend.stop()
        self._started = False
        self._record("stopped", {"aor": str(self.config.account.aor)})

    async def __aenter__(self) -> NativeSoftphone:
        return await self.start()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        await self.stop()

    async def register(self, *, call_id: str | None = None) -> RegisterClientState:
        self._require_started()
        call_id = call_id or _id("register")
        state = await self.backend.register_account(
            remote=self.config.remote,
            registrar=self.config.account.registrar,
            aor=self.config.account.aor,
            contact=self.contact,
            call_id=call_id,
            branch=_branch("register"),
            from_tag=_tag("from"),
            expires=self.config.account.expires,
            timeout=self.config.timeout,
            username=self.config.account.username,
            password=self.config.account.password,
            auth_branch=_branch("register-auth"),
        )
        self._record("registered", {"call_id": call_id, "state": state.value})
        return state

    async def unregister(self, *, call_id: str | None = None) -> RegisterClientState:
        self._require_started()
        call_id = call_id or _id("unregister")
        state = await self.backend.unregister_account(
            remote=self.config.remote,
            registrar=self.config.account.registrar,
            aor=self.config.account.aor,
            contact=self.contact,
            call_id=call_id,
            branch=_branch("unregister"),
            from_tag=_tag("from"),
            timeout=self.config.timeout,
            username=self.config.account.username,
            password=self.config.account.password,
            auth_branch=_branch("unregister-auth"),
        )
        self._record("unregistered", {"call_id": call_id, "state": state.value})
        return state

    async def call(
        self,
        target: SipUri | str,
        *,
        call_id: str | None = None,
    ) -> NativeSipCall:
        self._require_started()
        target_uri = _sip_uri(target)
        call_id = call_id or _id("call")
        call = await self.backend.initiate_call(
            remote=self.config.remote,
            target=target_uri,
            caller=self.config.account.aor,
            contact=self.contact,
            call_id=call_id,
            branch=_branch("invite"),
            from_tag=_tag("from"),
            ack_branch=_branch("ack"),
            timeout=self.config.timeout,
        )
        self._record(
            "call_confirmed", {"call_id": call.call_id, "target": str(target_uri)}
        )
        return call

    async def answer_inbound(
        self,
        *,
        local_tag: str | None = None,
    ) -> NativeSipCall:
        self._require_started()
        call = await self.backend.accept_call(
            local_tag=local_tag or _tag("local"),
            contact=self.contact,
            timeout=self.config.timeout,
        )
        self._record("inbound_answered", {"call_id": call.call_id})
        return call

    async def hangup(self, call: NativeSipCall) -> None:
        self._require_started()
        if call.state is NativeSipCallState.TERMINATED:
            return
        await self.backend.hangup_call(
            call,
            branch=_branch("bye"),
            timeout=self.config.timeout,
        )
        self._record("call_hungup", {"call_id": call.call_id})

    def _require_started(self) -> None:
        if not self._started:
            raise NativeSoftphoneError("softphone is not started")

    def _record(self, name: str, data: dict[str, object]) -> None:
        self.timeline.record(
            "softphone",
            name,
            actor_id=self.config.actor_id,
            data=data,
        )


def _sip_uri(value: SipUri | str) -> SipUri:
    return value if isinstance(value, SipUri) else SipUri.parse(value)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _branch(prefix: str) -> str:
    return f"z9hG4bK-{prefix}-{uuid4().hex}"


def _tag(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"
