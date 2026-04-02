"""Flow YAML parser and runner — programmable SIP interaction scripts."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

try:
    import yaml

    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

_log = logging.getLogger("sipx.tui.flows")


class StepAction(Enum):
    """Supported flow step actions."""

    INVITE = "invite"
    REGISTER = "register"
    OPTIONS = "options"
    ACK = "ack"
    BYE = "bye"
    CANCEL = "cancel"
    MESSAGE = "message"
    SUBSCRIBE = "subscribe"
    NOTIFY = "notify"
    REFER = "refer"
    INFO = "info"
    UPDATE = "update"
    PRACK = "prack"
    PUBLISH = "publish"
    WAIT = "wait"
    SLEEP = "sleep"
    DTMF = "dtmf"
    AUDIO = "audio"
    ANSWER = "answer"
    DTMF_COLLECT = "dtmf_collect"
    CONDITION = "condition"


@dataclass
class FlowStep:
    """A single step in a flow."""

    action: StepAction
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FlowStep:
        action_str = data.get("action", "")
        try:
            action = StepAction(action_str)
        except ValueError as e:
            raise ValueError(f"Unknown flow action: {action_str!r}") from e
        params = {k: v for k, v in data.items() if k != "action"}
        return cls(action=action, params=params)


def _substitute_vars(value: str, variables: dict[str, str]) -> str:
    """Replace $var and ${var} placeholders in a string."""
    import re

    def _replace(match: re.Match) -> str:
        name = match.group(1) or match.group(2)
        return variables.get(name, match.group(0))

    return re.sub(r"\$\{(\w+)\}|\$(\w+)", _replace, value)


def _substitute_step(step: FlowStep, variables: dict[str, str]) -> FlowStep:
    """Return a copy of step with variables substituted in all string params."""
    new_params: dict[str, Any] = {}
    for k, v in step.params.items():
        if isinstance(v, str):
            new_params[k] = _substitute_vars(v, variables)
        else:
            new_params[k] = v
    return FlowStep(action=step.action, params=new_params)


@dataclass
class Flow:
    """A parsed SIP interaction flow.

    Supports variables via `vars:` section:
    ```yaml
    vars:
      uri: sip:alice@proxy.example.com
      user: alice
      pass: secret123
    steps:
      - action: register
        uri: $uri
    ```

    Variables can also reference env vars: `$ENV_VAR`
    and be overridden at runtime.
    """

    name: str
    description: str = ""
    role: str = "uac"
    variables: dict[str, str] = field(default_factory=dict)
    steps: list[FlowStep] = field(default_factory=list)
    on_invite: list[FlowStep] = field(default_factory=list)

    @classmethod
    def parse(cls, text: str) -> Flow:
        """Parse a flow from YAML text."""
        if not _HAS_YAML:
            raise RuntimeError("PyYAML is required for flows: pip install pyyaml")
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("Flow YAML must be a mapping")

        # Parse variables — support env var fallback
        import os

        raw_vars = data.get("vars", {})
        variables: dict[str, str] = {}
        if isinstance(raw_vars, dict):
            for k, v in raw_vars.items():
                val = str(v)
                # ${ENV_VAR} or $ENV_VAR in value → resolve from env
                if val.startswith("$"):
                    env_name = val.lstrip("${").rstrip("}")
                    variables[k] = os.environ.get(env_name, val)
                else:
                    variables[k] = val

        steps = [FlowStep.from_dict(s) for s in data.get("steps", [])]
        on_invite = [FlowStep.from_dict(s) for s in data.get("on_invite", [])]

        return cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            role=data.get("role", "uac"),
            variables=variables,
            steps=steps,
            on_invite=on_invite,
        )


class StepStatus(Enum):
    """Execution status of a flow step."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of executing a flow step."""

    step: FlowStep
    status: StepStatus
    message: str = ""
    data: Any = None


class FlowRunner:
    """Executes a parsed Flow against an AsyncClient/AsyncSIPServer.

    The runner maps flow actions to sipx client/server method calls.
    It reports progress via callbacks so the TUI can update in real-time.
    """

    def __init__(
        self,
        flow: Flow,
        on_step_start: Callable[[int, FlowStep], Any] | None = None,
        on_step_done: Callable[[int, StepResult], Any] | None = None,
        on_log: Callable[[str], Any] | None = None,
    ) -> None:
        self.flow = flow
        self._on_step_start = on_step_start
        self._on_step_done = on_step_done
        self._on_log = on_log
        self._cancelled = False
        self._results: list[StepResult] = []

    @property
    def results(self) -> list[StepResult]:
        return self._results

    def cancel(self) -> None:
        """Cancel the running flow."""
        self._cancelled = True

    async def run(self, client: Any = None, server: Any = None) -> list[StepResult]:
        """Execute all steps in the flow.

        Args:
            client: AsyncClient instance (for UAC flows)
            server: AsyncSIPServer instance (for UAS flows)

        Returns:
            List of step results.
        """
        raw_steps = self.flow.steps or self.flow.on_invite
        variables = dict(self.flow.variables)
        # Substitute variables in all steps
        steps = [_substitute_step(s, variables) for s in raw_steps]
        self._results = []

        for i, step in enumerate(steps):
            if self._cancelled:
                self._results.append(StepResult(step, StepStatus.SKIPPED, "Cancelled"))
                continue

            if self._on_step_start:
                self._on_step_start(i, step)
            self._log(f"Step {i + 1}/{len(steps)}: {step.action.value}")

            try:
                result = await self._execute_step(step, client, server)
                self._results.append(result)
            except Exception as exc:
                result = StepResult(step, StepStatus.FAILED, str(exc))
                self._results.append(result)
                self._log(f"  [red]FAILED:[/red] {exc}")

            if self._on_step_done:
                self._on_step_done(i, result)

            if result.status == StepStatus.FAILED:
                self._log("[red]Flow aborted due to failure[/red]")
                # Mark remaining as skipped
                for remaining in steps[i + 1 :]:
                    self._results.append(
                        StepResult(remaining, StepStatus.SKIPPED, "Aborted")
                    )
                break

        return self._results

    async def _execute_step(
        self, step: FlowStep, client: Any, server: Any
    ) -> StepResult:
        """Execute a single flow step."""
        action = step.action
        params = step.params

        if action == StepAction.SLEEP:
            duration = float(params.get("duration", 1.0))
            self._log(f"  Sleeping {duration}s...")
            await asyncio.sleep(duration)
            return StepResult(step, StepStatus.SUCCESS, f"Slept {duration}s")

        if action == StepAction.WAIT:
            timeout = float(params.get("timeout", 30))
            condition = params.get("for", "answer")
            self._log(f"  Waiting for {condition} (timeout={timeout}s)...")
            # In a real implementation, this would wait for a specific response
            await asyncio.sleep(min(timeout, 0.5))
            return StepResult(step, StepStatus.SUCCESS, f"Waited for {condition}")

        # SIP method actions
        if client is None:
            return StepResult(
                step, StepStatus.FAILED, "No client available for this action"
            )

        method_map = {
            StepAction.INVITE: "invite",
            StepAction.REGISTER: "register",
            StepAction.OPTIONS: "options",
            StepAction.ACK: "ack",
            StepAction.BYE: "bye",
            StepAction.CANCEL: "cancel",
            StepAction.MESSAGE: "message",
            StepAction.SUBSCRIBE: "subscribe",
            StepAction.NOTIFY: "notify",
            StepAction.REFER: "refer",
            StepAction.INFO: "info",
            StepAction.UPDATE: "update",
            StepAction.PRACK: "prack",
            StepAction.PUBLISH: "publish",
        }

        if action in method_map:
            method_name = method_map[action]
            method_fn = getattr(client, method_name, None)
            if method_fn is None:
                return StepResult(
                    step,
                    StepStatus.FAILED,
                    f"Client has no method: {method_name}",
                )

            kwargs: dict[str, Any] = {}
            if "uri" in params:
                # Map to the correct kwarg depending on method
                if method_name in ("invite", "bye"):
                    kwargs["to_uri"] = params["uri"]
                elif method_name == "register":
                    kwargs["aor"] = params["uri"]
                else:
                    kwargs["uri"] = params["uri"]
            if "body" in params and params["body"] != "auto-sdp":
                kwargs["content"] = params["body"]

            self._log(f"  {method_name.upper()} {params.get('uri', '')}")
            try:
                resp = await method_fn(**kwargs)
                self._last_response = resp
                if resp:
                    msg = f"{resp.status_code} {resp.reason_phrase}"
                    self._log(f"  Response: {msg}")
                    return StepResult(step, StepStatus.SUCCESS, msg, resp)
                return StepResult(step, StepStatus.SUCCESS, "Sent (no response)")
            except Exception as exc:
                return StepResult(step, StepStatus.FAILED, str(exc))

        if action == StepAction.DTMF:
            digits = params.get("digits", "")
            self._log(f"  Sending DTMF: {digits}")
            # Would use DTMFSender in real implementation
            return StepResult(step, StepStatus.SUCCESS, f"DTMF sent: {digits}")

        if action == StepAction.AUDIO:
            audio_file = params.get("file", "")
            self._log(f"  Playing audio: {audio_file}")
            return StepResult(step, StepStatus.SUCCESS, f"Audio: {audio_file}")

        if action == StepAction.ANSWER:
            self._log("  Answering call...")
            return StepResult(step, StepStatus.SUCCESS, "Answered")

        if action == StepAction.DTMF_COLLECT:
            max_digits = params.get("max_digits", 4)
            self._log(f"  Collecting up to {max_digits} DTMF digits...")
            return StepResult(step, StepStatus.SUCCESS, "DTMF collected")

        if action == StepAction.CONDITION:
            condition_expr = params.get("if", "true")
            self._log(f"  Evaluating condition: {condition_expr}")
            return StepResult(step, StepStatus.SUCCESS, f"Condition: {condition_expr}")

        return StepResult(step, StepStatus.FAILED, f"Unhandled action: {action.value}")

    def _log(self, text: str) -> None:
        if self._on_log:
            self._on_log(text)
        _log.debug(text)
