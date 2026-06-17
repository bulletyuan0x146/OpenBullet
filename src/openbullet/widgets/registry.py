from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

WIDGETS: dict[str, dict[str, Any]] = {}

F = TypeVar("F", bound=Callable[..., Any])


def register_widget(widget_config: dict[str, Any]) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        endpoint = widget_config.get("endpoint")
        if endpoint:
            widget_id = widget_config.setdefault("widgetId", endpoint.replace("/", "_"))
            WIDGETS[widget_id] = widget_config

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await func(*args, **kwargs)

            return cast(F, async_wrapper)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        return cast(F, sync_wrapper)

    return decorator
