from __future__ import annotations

import os
from contextlib import nullcontext
from typing import Iterable


DEFAULT_LANGSMITH_ENDPOINT = "https://api.smith.langchain.com"


def _normalize_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def configure_langsmith(
    enabled: bool,
    api_key: str = "",
    project: str = "",
    endpoint: str = DEFAULT_LANGSMITH_ENDPOINT,
) -> tuple[bool, str]:
    os.environ["LANGSMITH_TRACING"] = "true" if enabled else "false"

    if api_key.strip():
        os.environ["LANGSMITH_API_KEY"] = api_key.strip()
    elif not enabled:
        os.environ.pop("LANGSMITH_API_KEY", None)

    if project.strip():
        os.environ["LANGSMITH_PROJECT"] = project.strip()
    elif not enabled:
        os.environ.pop("LANGSMITH_PROJECT", None)

    if endpoint.strip():
        os.environ["LANGSMITH_ENDPOINT"] = endpoint.strip()
    elif not enabled:
        os.environ.pop("LANGSMITH_ENDPOINT", None)

    if not enabled:
        return False, "LangSmith 调试已关闭，系统保持当前默认运行模式。"

    try:
        import langsmith  # noqa: F401
    except ImportError:
        return False, "LangSmith 调试未生效：当前环境未安装 `langsmith` 依赖。"

    if not os.getenv("LANGSMITH_API_KEY", "").strip():
        return False, "LangSmith 调试未生效：请先填写 LangSmith API Key。"

    return True, f"LangSmith 调试已开启，当前项目：{os.getenv('LANGSMITH_PROJECT', 'default')}"


def get_langsmith_settings_from_env() -> dict:
    return {
        "enabled": _normalize_bool(os.getenv("LANGSMITH_TRACING") or os.getenv("LANGCHAIN_TRACING_V2", "false")),
        "api_key": os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY", ""),
        "project": os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT", "interview-coach-debug"),
        "endpoint": os.getenv("LANGSMITH_ENDPOINT", DEFAULT_LANGSMITH_ENDPOINT),
    }


def tracing_context_if_enabled(run_name: str = "", tags: Iterable[str] | None = None, metadata: dict | None = None):
    settings = get_langsmith_settings_from_env()
    if not settings["enabled"]:
        return nullcontext()

    try:
        from langsmith import tracing_context
    except ImportError:
        return nullcontext()

    kwargs = {"enabled": True}
    if run_name:
        kwargs["project_name"] = settings["project"]
    if tags:
        kwargs["tags"] = list(tags)
    if metadata:
        kwargs["metadata"] = metadata
    try:
        return tracing_context(**kwargs)
    except TypeError:
        return tracing_context(enabled=True)
