#!/usr/bin/env python3
"""Validate the fixed intake contract for an AI-Coder Draft-PR task."""
from __future__ import annotations

import re
from pathlib import PurePosixPath

RISK_CLASSES = {"GREEN", "YELLOW", "RED"}
REQUIRED_TEXT_FIELDS = (
    "observed_symptom",
    "reproduction",
    "expected_result",
    "performance_baseline",
    "completion_criteria",
)
REQUIRED_LIST_FIELDS = ("allowed_paths", "prohibited_paths", "verification_commands")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or value.startswith(("/", "~")):
        return False
    path = PurePosixPath(value)
    return ".." not in path.parts and "." not in path.parts


def contract_errors(task: dict) -> list[str]:
    errors: list[str] = []
    ticket = task.get("ticket")
    if not isinstance(ticket, dict):
        return ["ticket must be an object"]
    if task.get("risk_class") not in RISK_CLASSES:
        errors.append("risk_class must be GREEN, YELLOW, or RED")
    if not REPOSITORY.fullmatch(str(task.get("repository", ""))):
        errors.append("repository must be owner/name")
    for field in REQUIRED_TEXT_FIELDS:
        if not isinstance(ticket.get(field), str) or not ticket[field].strip():
            errors.append(f"ticket.{field} is required")
    for field in REQUIRED_LIST_FIELDS:
        values = ticket.get(field)
        if not isinstance(values, list) or not values or not all(
            isinstance(value, str) and value.strip() for value in values
        ):
            errors.append(f"ticket.{field} must be a non-empty string list")
    allowed = ticket.get("allowed_paths", [])
    if isinstance(allowed, list) and not all(safe_relative_path(value) for value in allowed):
        errors.append("ticket.allowed_paths must contain safe app-relative paths")
    return errors


def path_is_allowed(path: str, allowed_paths: list[str]) -> bool:
    return any(path == allowed.rstrip("/") or path.startswith(allowed.rstrip("/") + "/") for allowed in allowed_paths)
