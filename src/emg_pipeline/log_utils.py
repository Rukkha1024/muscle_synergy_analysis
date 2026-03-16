"""Emit structured pipeline log lines one line at a time."""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable
from typing import Any


_RULE_WIDTH = 58
_KV_INDENT = " " * 8


def _resolve_logger(logger: logging.Logger | None = None) -> logging.Logger:
    return logger or logging.getLogger()


def log_step_banner(step_index: int, total_steps: int, title: str, logger: logging.Logger | None = None) -> None:
    active_logger = _resolve_logger(logger)
    active_logger.info("")
    active_logger.info("%s", "═" * _RULE_WIDTH)
    active_logger.info("  Step %s/%s : %s", step_index, total_steps, title)
    active_logger.info("%s", "═" * _RULE_WIDTH)


def log_kv_section(
    title: str,
    rows: Iterable[tuple[str, Any]],
    logger: logging.Logger | None = None,
) -> None:
    active_logger = _resolve_logger(logger)
    rendered_rows = [(label, _stringify(value)) for label, value in rows]
    active_logger.info("[%s]", title)
    if not rendered_rows:
        return
    label_width = max(len(label) for label, _ in rendered_rows)
    for label, value in rendered_rows:
        active_logger.info("%s%-*s : %s", _KV_INDENT, label_width, label, value)


def compact_list(values: Iterable[Any], *, limit: int = 6) -> str:
    rendered = [str(value) for value in values if str(value)]
    if not rendered:
        return "n/a"
    if len(rendered) <= limit:
        return ", ".join(rendered)
    return ", ".join(rendered[:limit]) + ", ..."


def format_float(value: Any, *, digits: int = 3) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if math.isnan(numeric) or math.isinf(numeric):
        return "n/a"
    return f"{numeric:.{digits}f}"


def _stringify(value: Any) -> str:
    if value is None:
        return "n/a"
    return str(value)
