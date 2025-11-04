"""Utilities for extracting metadata from G-code files."""

from __future__ import annotations

import os
import re
from typing import Dict

__all__ = ["extract_metadata_from_gcode"]


def _format_duration_from_seconds(seconds: int) -> str:
    seconds = max(int(seconds), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        return "0m"
    return " ".join(parts)


def _normalize_duration_tokens(tokens: list[tuple[int, str]]) -> str:
    hours = minutes = 0
    seconds = 0
    for value, unit in tokens:
        if unit == "h":
            hours += value
        elif unit == "m":
            minutes += value
        elif unit == "s":
            seconds += value
    if seconds and not minutes:
        minutes = max(1, seconds // 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        return "0m"
    return " ".join(parts)


def extract_metadata_from_gcode(path: str, *, max_lines: int | None = None) -> Dict[str, str]:
    """Inspect a G-code file for material/time metadata.

    If ``max_lines`` is provided and greater than zero, scanning stops once the
    limit is reached; otherwise the entire file is streamed until the required
    metadata is collected.
    """
    result: Dict[str, str] = {}
    if not path or not os.path.isfile(path):
        return result

    # Precompile regexes for common slicer annotations.
    material_patterns = [
        re.compile(r"filament_settings_id\s*=\s*\"?([^\";]+)\"?", re.IGNORECASE),
        re.compile(r"filament_spool_name\s*=\s*\"?([^\";]+)\"?", re.IGNORECASE),
        re.compile(r"filament_brand\s*=\s*\"?([^\";]+)\"?", re.IGNORECASE),
        re.compile(r"filament_type\s*=\s*\"?([^\";]+)\"?", re.IGNORECASE),
    ]
    colour_patterns = [
        re.compile(r"filament_colou?r\s*=\s*\"?([^\";]+)\"?", re.IGNORECASE),
    ]
    prusa_time_pattern = re.compile(r"estimated printing time.*=\s*([0-9hms ]+)", re.IGNORECASE)

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            limit = max_lines if (isinstance(max_lines, int) and max_lines > 0) else None
            for line_number, line in enumerate(handle, 1):
                if limit is not None and line_number > limit:
                    break
                stripped = line.strip()
                if not stripped or not stripped.startswith(";"):
                    continue
                body = stripped[1:].strip()
                upper_body = body.upper()

                if "print_time" not in result:
                    if upper_body.startswith("TIME:"):
                        value = body[5:].strip()
                        try:
                            seconds = int(float(value))
                        except ValueError:
                            seconds = None
                        if seconds is not None:
                            result["print_time"] = _format_duration_from_seconds(seconds)
                            continue
                    prusa_match = prusa_time_pattern.search(body)
                    if prusa_match:
                        duration = prusa_match.group(1).strip()
                        matches = re.findall(r"(\d+)\s*([hms])", duration, flags=re.IGNORECASE)
                        if matches:
                            tokens = [(int(amount), unit.lower()) for amount, unit in matches]
                            result["print_time"] = _normalize_duration_tokens(tokens)
                        else:
                            result["print_time"] = duration
                        continue

                if "material" not in result:
                    for pattern in material_patterns:
                        mat_match = pattern.search(body)
                        if not mat_match:
                            continue
                        material = mat_match.group(1).strip().strip('"')
                        if material:
                            result["material"] = material
                            break

                if "colour" not in result:
                    for pattern in colour_patterns:
                        col_match = pattern.search(body)
                        if not col_match:
                            continue
                        colour_value = col_match.group(1).strip().strip('"')
                        if colour_value:
                            result["colour"] = colour_value
                            break

                if result.get("material") and result.get("print_time"):
                    break
    except Exception:
        return result

    fallback_colour = None
    if result.get("material"):
        material_value = result["material"]
        tokens = [token for token in material_value.split() if token]
        if tokens:
            candidate = tokens[-1]
            excluded = {"PLA", "ABS", "PETG", "ASA", "TPU", "PVA", "HIPS", "NYLON", "PET", "PC", "PEI", "PETT"}
            if candidate.isalpha() and len(candidate) > 2 and candidate.upper() not in excluded:
                fallback_colour = candidate

    if fallback_colour:
        existing = result.get("colour")
        if not existing or re.fullmatch(r"#?[0-9a-fA-F]{6}", existing.replace("0x", "").strip("#")):
            result["colour"] = fallback_colour

    chosen_colour = result.get("colour") or ""
    if chosen_colour and result.get("material"):
        stripped_colour = chosen_colour.strip().strip('"')
        lower_colour = stripped_colour.lower()
        material_value = result["material"].strip()
        if stripped_colour and lower_colour in material_value.lower():
            cleaned = material_value
            pattern = re.compile(rf"\s*{re.escape(stripped_colour)}\b", re.IGNORECASE)
            cleaned = pattern.sub("", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if cleaned:
                result["material"] = cleaned

    return result
