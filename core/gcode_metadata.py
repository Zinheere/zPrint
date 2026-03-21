"""Utilities for extracting metadata from G-code files."""

from __future__ import annotations

import os
import re
from typing import Dict

__all__ = ["extract_metadata_from_gcode", "extract_extended_metadata"]


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


def extract_extended_metadata(path: str, *, max_lines: int | None = 2000) -> Dict[str, str]:
    """Extract extended print parameters from a G-code file.

    Returns a dict that may contain any subset of:
    - ``nozzle_temp``   – hotend temperature in °C (e.g. "215°C")
    - ``bed_temp``      – bed temperature in °C (e.g. "60°C")
    - ``layer_height``  – layer height in mm (e.g. "0.20 mm")
    - ``filament_used`` – estimated filament length or weight (e.g. "4.5 m" or "14.2 g")
    - ``slicer``        – slicer name + version string if present
    """
    result: Dict[str, str] = {}
    if not path or not os.path.isfile(path):
        return result

    nozzle_patterns = [
        re.compile(r"nozzle_temperature\s*=\s*(\d+)", re.IGNORECASE),
        re.compile(r"first_layer_temperature\s*=\s*(\d+)", re.IGNORECASE),
        re.compile(r"temperature\s*=\s*(\d+)", re.IGNORECASE),
    ]
    bed_patterns = [
        re.compile(r"bed_temperature\s*=\s*(\d+)", re.IGNORECASE),
        re.compile(r"first_layer_bed_temperature\s*=\s*(\d+)", re.IGNORECASE),
    ]
    layer_patterns = [
        re.compile(r"layer_height\s*=\s*([0-9]*\.?[0-9]+)", re.IGNORECASE),
    ]
    filament_patterns = [
        # "filament used [mm] = 12500.5" (PrusaSlicer / OrcaSlicer with unit annotation)
        re.compile(r"filament used\s*\[[^\]]*\]\s*=\s*([0-9.,]+)", re.IGNORECASE),
        # "filament used = 4500.5mm" (inline unit)
        re.compile(r"filament used\s*=\s*([0-9.,]+\s*(?:mm|m|g|cm))", re.IGNORECASE),
        re.compile(r"total filament used\s*=\s*([0-9.,]+\s*(?:mm|m|g|cm))", re.IGNORECASE),
        re.compile(r"filament_used\s*=\s*([0-9.,]+)", re.IGNORECASE),
        re.compile(r"filament_weight\s*=\s*([0-9.,]+)", re.IGNORECASE),
    ]
    slicer_patterns = [
        re.compile(r"generated by\s+([^\r\n;]+)", re.IGNORECASE),
        re.compile(r"slicer\s*[:=]\s*([^\r\n;]+)", re.IGNORECASE),
        re.compile(r"prusaslicer\s+([0-9.]+)", re.IGNORECASE),
        re.compile(r"cura\s+([0-9.]+)", re.IGNORECASE),
        re.compile(r"bambu studio\s+([0-9.]+)", re.IGNORECASE),
        re.compile(r"orcaslicer\s+([0-9.]+)", re.IGNORECASE),
        re.compile(r"superslicer\s+([0-9.]+)", re.IGNORECASE),
    ]

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

                if "nozzle_temp" not in result:
                    for pat in nozzle_patterns:
                        m = pat.search(body)
                        if m:
                            try:
                                val = int(m.group(1))
                                if 100 <= val <= 500:
                                    result["nozzle_temp"] = f"{val}°C"
                            except ValueError:
                                pass
                            break

                if "bed_temp" not in result:
                    for pat in bed_patterns:
                        m = pat.search(body)
                        if m:
                            try:
                                val = int(m.group(1))
                                if 0 <= val <= 200:
                                    result["bed_temp"] = f"{val}°C"
                            except ValueError:
                                pass
                            break

                if "layer_height" not in result:
                    for pat in layer_patterns:
                        m = pat.search(body)
                        if m:
                            try:
                                val = float(m.group(1))
                                if 0.01 <= val <= 1.0:
                                    result["layer_height"] = f"{val:.2f} mm"
                            except ValueError:
                                pass
                            break

                if "filament_used" not in result:
                    for pat_idx, pat in enumerate(filament_patterns):
                        m = pat.search(body)
                        if m:
                            raw = m.group(1).strip()
                            if raw:
                                # Normalise long mm values to metres
                                mm_match = re.match(r"([0-9.,]+)\s*mm$", raw, re.IGNORECASE)
                                if mm_match:
                                    try:
                                        mm_val = float(mm_match.group(1).replace(",", "."))
                                        if mm_val >= 1000:
                                            result["filament_used"] = f"{mm_val / 1000:.1f} m"
                                        else:
                                            result["filament_used"] = raw
                                    except ValueError:
                                        result["filament_used"] = raw
                                elif re.match(r"^[0-9.,]+$", raw):
                                    # Bare number from "filament used [mm] = 12500" pattern (pat_idx 0)
                                    # The unit comes from the annotation in brackets, assume mm
                                    try:
                                        num_val = float(raw.replace(",", "."))
                                        if num_val >= 1000:
                                            result["filament_used"] = f"{num_val / 1000:.1f} m"
                                        else:
                                            result["filament_used"] = f"{num_val:.1f} mm"
                                    except ValueError:
                                        result["filament_used"] = raw
                                else:
                                    result["filament_used"] = raw
                            break

                if "slicer" not in result:
                    upper_body = body.upper()
                    if any(kw in upper_body for kw in ("PRUSASLICER", "CURA", "BAMBU", "ORCA", "SUPERSLICER", "GENERATED BY", "SLICER")):
                        for pat in slicer_patterns:
                            m = pat.search(body)
                            if m:
                                slicer_raw = m.group(1).strip().rstrip(";").strip()
                                if slicer_raw:
                                    result["slicer"] = slicer_raw[:64]
                                break

                if len(result) >= 5:
                    break
    except Exception:
        pass

    return result
