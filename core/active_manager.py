"""Helpers for managing the "active" model state and root G-code copies."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from typing import Iterable, List, Tuple


class ActiveModelError(RuntimeError):
    """Raised when an active-model transition fails."""


def set_model_active(model: dict, models_root: str, active: bool) -> Tuple[List[str], dict, datetime]:
    """Flip a model's active state and persist metadata.

    Returns a tuple of (active_gcode_files, updated_metadata, last_modified_dt).
    Raises ActiveModelError (subclass of RuntimeError) on failure.
    """

    if not isinstance(model, dict):
        raise ActiveModelError("Model payload is not a dictionary.")

    models_root = os.path.abspath(models_root or "")
    if not models_root:
        raise ActiveModelError("Storage root path is empty.")

    if active:
        active_files = _copy_model_gcodes_to_root(model, models_root)
    else:
        _remove_active_gcodes(model, models_root)
        active_files = []

    updated_meta, timestamp = _update_model_active_metadata(model, active, active_files)
    return active_files, updated_meta, timestamp


def _copy_model_gcodes_to_root(model: dict, models_root: str) -> List[str]:
    folder = os.path.abspath(model.get("folder") or "")
    if not folder or not os.path.isdir(folder):
        raise ActiveModelError("Model folder could not be found on disk.")

    gcodes = list(model.get("gcodes") or [])
    if not gcodes:
        raise ActiveModelError("This model does not list any G-code entries.")

    os.makedirs(models_root, exist_ok=True)

    folder_leaf = os.path.basename(folder.rstrip(os.sep)) or "model"
    recorded = set(name.lower() for name in _existing_active_names(model))
    used_dest = set(recorded)

    result_names: List[str] = []
    copied_paths: List[str] = []
    missing_sources: List[str] = []
    current_filename = ""

    try:
        for entry in gcodes:
            current_filename = (entry.get("file") or "").strip()
            if not current_filename:
                continue

            source = os.path.join(folder, current_filename)
            if not os.path.isfile(source):
                missing_sources.append(current_filename)
                continue

            dest_name = current_filename
            dest_path = os.path.join(models_root, dest_name)

            if os.path.exists(dest_path):
                if _files_are_same(source, dest_path):
                    if dest_name not in result_names:
                        result_names.append(dest_name)
                    used_dest.add(dest_name.lower())
                    continue

                name_root, name_ext = os.path.splitext(current_filename)
                suffix = 0
                while True:
                    extra = "" if suffix == 0 else f"_{suffix}"
                    candidate = f"{name_root}__{folder_leaf}{extra}{name_ext}"
                    candidate_path = os.path.join(models_root, candidate)
                    if not os.path.exists(candidate_path):
                        dest_name = candidate
                        dest_path = candidate_path
                        break
                    if _files_are_same(source, candidate_path):
                        dest_name = candidate
                        dest_path = candidate_path
                        break
                    suffix += 1

            if dest_name.lower() in used_dest and not _files_are_same(source, os.path.join(models_root, dest_name)):
                name_root, name_ext = os.path.splitext(dest_name)
                suffix = 1
                while True:
                    candidate = f"{name_root}_{suffix}{name_ext}"
                    candidate_path = os.path.join(models_root, candidate)
                    if candidate.lower() not in used_dest and (
                        not os.path.exists(candidate_path) or _files_are_same(source, candidate_path)
                    ):
                        dest_name = candidate
                        dest_path = candidate_path
                        break
                    suffix += 1

            shutil.copy2(source, dest_path)
            copied_paths.append(dest_path)
            used_dest.add(dest_name.lower())
            if dest_name not in result_names:
                result_names.append(dest_name)
    except Exception as exc:  # roll back any partially copied files
        for path in copied_paths:
            if os.path.isfile(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        raise ActiveModelError(f'Failed to copy G-code file "{current_filename}": {exc}') from exc

    if not result_names:
        if missing_sources:
            missing_display = ", ".join(sorted(set(missing_sources)))
            raise ActiveModelError(f"No G-code files were copied. Missing sources: {missing_display}")
        raise ActiveModelError("No G-code files were copied for this model.")

    return result_names


def _remove_active_gcodes(model: dict, models_root: str) -> None:
    for name in _existing_active_names(model):
        target = os.path.join(models_root, name)
        if os.path.isfile(target):
            try:
                os.remove(target)
            except Exception:
                pass


def _existing_active_names(model: dict) -> Iterable[str]:
    meta = model.get("metadata") or {}
    recorded = list(model.get("active_gcode_files") or []) + list(meta.get("active_gcode_files") or [])
    seen: set[str] = set()
    for name in recorded:
        if not name:
            continue
        lowered = name.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        yield name


def _update_model_active_metadata(model: dict, active: bool, active_files: List[str]) -> Tuple[dict, datetime]:
    folder = os.path.abspath(model.get("folder") or "")
    if not folder:
        raise ActiveModelError("Model folder path is not recorded.")

    meta = dict(model.get("metadata") or {})
    meta["active"] = bool(active)
    meta["active_gcode_files"] = list(active_files)

    timestamp = datetime.utcnow()
    meta["last_modified"] = timestamp.isoformat(timespec="seconds") + "Z"

    meta_path = os.path.join(folder, "model.json")
    try:
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)
    except Exception as exc:
        raise ActiveModelError(f"Unable to write model metadata: {exc}") from exc

    return meta, timestamp


def _files_are_same(path_a: str, path_b: str) -> bool:
    if not path_a or not path_b:
        return False
    if not os.path.exists(path_a) or not os.path.exists(path_b):
        return False
    try:
        return os.path.samefile(path_a, path_b)
    except Exception:
        try:
            stat_a = os.stat(path_a)
            stat_b = os.stat(path_b)
        except Exception:
            return False
        return stat_a.st_size == stat_b.st_size and int(stat_a.st_mtime) == int(stat_b.st_mtime)
