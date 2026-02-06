from contextvars import ContextVar
from typing import Any, Dict, Optional

_policy_ctx: ContextVar[Optional[Dict[str, Any]]] = ContextVar("policy_ctx", default=None)


def set_policy_context(policy: Dict[str, Any]):
    """
    Sets the active policy context for the current request/task.
    Returns a token that must be used to reset the context.
    """
    return _policy_ctx.set(policy)


def reset_policy_context(token) -> None:
    """Resets the policy context to the previous value."""
    _policy_ctx.reset(token)


def get_policy_context() -> Optional[Dict[str, Any]]:
    """Returns the current policy context if set."""
    return _policy_ctx.get()


def policy_value(key: str, default: Any) -> Any:
    """
    Fetches a value from the active policy context, falling back to default.
    """
    policy = _policy_ctx.get()
    if policy and key in policy and policy[key] is not None:
        return policy[key]
    return default


def policy_label(default_label: str) -> str:
    return str(policy_value("policy_version_label", default_label))


def policy_version_id(default_id: str) -> str:
    return str(policy_value("policy_version_id", default_id))
