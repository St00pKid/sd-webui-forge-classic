import os
import requests

CIVITAI_API = "https://civitai.red/api/v1"
TIMEOUT_META = 15   # seconds for API calls
TIMEOUT_IMG  = 30   # seconds for image download

PREVIEW_EXTS = ["png", "jpg", "jpeg", "webp", "gif"]


def _find_existing_preview(base: str) -> str | None:
    for ext in PREVIEW_EXTS:
        for candidate in [f"{base}.{ext}", f"{base}.preview.{ext}"]:
            if os.path.isfile(candidate):
                return candidate
    return None


def get_sha256(filename: str, name: str) -> str | None:
    """Return SHA256 (AddNet format) for a safetensors LoRA, using Forge's cache."""
    from modules import hashes
    cached = hashes.sha256_from_cache(filename, "lora/" + name, use_addnet_hash=True)
    if cached:
        return cached
    # Cache miss — compute (may take a few seconds for large files)
    return hashes.sha256(filename, "lora/" + name, use_addnet_hash=True)


def _fetch_version_by_hash(sha256: str) -> dict | None:
    """GET /model-versions/by-hash/{sha256}. Returns parsed JSON or None on 404."""
    url = f"{CIVITAI_API}/model-versions/by-hash/{sha256}"
    r = requests.get(url, timeout=TIMEOUT_META)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def _parse_version(data: dict) -> dict:
    """Extract description, trigger words, first image URL, and base model."""
    model_obj = data.get("model", {})

    # Prefer the parent model description; fall back to version-level description
    description = (model_obj.get("description") or data.get("description") or "").strip()

    trained_words = data.get("trainedWords") or []
    triggers = ", ".join(w.strip() for w in trained_words if w.strip())

    images = data.get("images") or []
    preview_url = next(
        (img["url"] for img in images if img.get("type", "image") == "image"),
        images[0]["url"] if images else None,
    )

    base_model = data.get("baseModel", "")

    return {
        "description": description,
        "trigger_words": triggers,
        "preview_url": preview_url,
        "base_model": base_model,
    }


def _download_preview(url: str, dest: str) -> bool:
    """Stream-download an image to dest. Returns True on success."""
    try:
        r = requests.get(url, timeout=TIMEOUT_IMG, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        return True
    except Exception:
        return False


def fetch_and_populate(filename: str, name: str, overwrite_preview: bool) -> tuple[bool, str, dict]:
    """
    Fetch metadata for a LoRA from Civitai by its SHA256 hash.

    Returns (success, status_message, result_dict).
    result_dict keys: description (str), trigger_words (str), preview_path (str|None)

    On failure: success=False, result_dict is empty.
    """
    # 1. Get hash
    try:
        sha256 = get_sha256(filename, name)
    except Exception as e:
        return False, f"Hash error: {e}", {}

    if not sha256:
        return False, "Could not compute file hash (hashing disabled?).", {}

    # 2. Call API
    try:
        data = _fetch_version_by_hash(sha256)
    except requests.exceptions.ConnectionError:
        return False, "Network error — check your connection.", {}
    except requests.exceptions.Timeout:
        return False, "Request timed out.", {}
    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {e}", {}

    if data is None:
        return False, "Not found on Civitai.", {}

    parsed = _parse_version(data)

    # 3. Handle preview image
    base = os.path.splitext(filename)[0]
    existing = _find_existing_preview(base)
    preview_path = existing  # default: keep whatever exists

    if parsed["preview_url"]:
        if existing and not overwrite_preview:
            pass  # keep existing, don't download
        else:
            dest = base + ".png"
            if _download_preview(parsed["preview_url"], dest):
                preview_path = dest

    return True, "Fetched from Civitai — review the fields then click Save.", {
        "description": parsed["description"],
        "trigger_words": parsed["trigger_words"],
        "preview_path": preview_path,
    }
