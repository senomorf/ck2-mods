"""GitHub Actions workflow commands, so lint findings show on the pull request's diff.

Under GitHub Actions (GITHUB_ACTIONS=true) annotate() prints `::error file=...,line=...::message`
(or `::warning`); elsewhere it prints nothing. Format and escaping:
https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands
"""
from __future__ import annotations

import os
import re

LINE_IN_MSG = re.compile(r"^line (\d+): |\bon line (\d+)\b")


def _data(s: str) -> str:
    return s.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _prop(s: str) -> str:
    return _data(s).replace(":", "%3A").replace(",", "%2C")


def annotate(kind: str, path: str, msg: str, line: int | None = None) -> None:
    """kind is 'error' or 'warning'; path is relative to the repository root."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    if line is None:
        m = LINE_IN_MSG.search(msg)
        if m:
            line = int(m.group(1) or m.group(2))
    where = f"file={_prop(path)}" + (f",line={line}" if line else "")
    print(f"::{kind} {where}::{_data(msg)}")
