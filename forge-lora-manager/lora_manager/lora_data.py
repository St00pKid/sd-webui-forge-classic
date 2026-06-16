import os
from typing import Optional

PREVIEW_EXTS = ["png", "jpg", "jpeg", "webp", "gif"]


def _get_networks():
    import networks
    return networks.available_networks


def _resolve_preview(base_path: str) -> Optional[str]:
    for ext in PREVIEW_EXTS:
        for candidate in [f"{base_path}.{ext}", f"{base_path}.preview.{ext}"]:
            if os.path.isfile(candidate):
                return candidate
    return None


def _read_user_metadata(filename: str) -> dict:
    try:
        from modules import extra_networks
        return extra_networks.get_user_metadata(filename) or {}
    except Exception:
        return {}


def _build_lora_dict(name: str, network_on_disk) -> dict:  # type: ignore[no-untyped-def]
    filename = str(network_on_disk.filename)
    base = os.path.splitext(filename)[0]
    mtime = 0
    try:
        mtime = os.path.getmtime(filename)
    except OSError:
        pass

    preview_path = _resolve_preview(base)
    user_meta = _read_user_metadata(filename)

    description = user_meta.get("description", "")
    if not description:
        txt_file = f"{base}.txt"
        if os.path.isfile(txt_file):
            try:
                with open(txt_file, "r", encoding="utf-8", errors="replace") as f:
                    description = f.read()
            except OSError:
                pass

    return {
        "name": name,
        "filename": filename,
        "shorthash": network_on_disk.shorthash or "",
        "alias": network_on_disk.alias or name,
        "preview_path": preview_path,
        "display_name": user_meta.get("display_name", ""),
        "description": description,
        "trigger_words": user_meta.get("activation text", ""),
        "preferred_weight": str(user_meta.get("preferred weight", "")),
        "notes": user_meta.get("notes", ""),
        "sd_version": user_meta.get("sd_version", ""),
        "mtime": mtime,
    }


def list_loras() -> list[dict]:
    try:
        networks = _get_networks()
        loras = [_build_lora_dict(name, nd) for name, nd in networks.items()]
        return sorted(loras, key=lambda x: x["name"].lower())
    except Exception:
        return []


def get_lora_detail(name: str) -> Optional[dict]:
    try:
        networks = _get_networks()
        nd = networks.get(name)
        if nd is None:
            return None
        return _build_lora_dict(name, nd)
    except Exception:
        return None


def refresh_network_list() -> None:
    try:
        import networks
        networks.list_available_networks()
    except Exception:
        pass


def save_user_metadata(filename: str, fields: dict) -> None:
    """
    Merge `fields` into the existing .json sidecar and write atomically.
    Keys with None values are left unchanged (not written).
    """
    import json, tempfile
    basename = os.path.splitext(filename)[0]
    sidecar = basename + ".json"

    existing = {}
    if os.path.isfile(sidecar):
        try:
            with open(sidecar, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass

    for k, v in fields.items():
        if v is not None:
            existing[k] = v

    # Write to a temp file in the same directory, then replace atomically
    dir_ = os.path.dirname(sidecar)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".json.tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, sidecar)
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise
