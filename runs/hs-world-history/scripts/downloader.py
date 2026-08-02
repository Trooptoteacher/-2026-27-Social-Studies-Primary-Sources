"""Download + validate + hash + citation sidecar for a single resolved asset."""
import os
import re
import time
import hashlib
import urllib.request
import urllib.error
import struct
from datetime import datetime, timezone

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

MAGIC_SIGNATURES = {
    b"\xff\xd8\xff": "jpg",
    b"\x89PNG\r\n\x1a\n": "png",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
    b"%PDF": "pdf",
    b"\x25\x50\x44\x46": "pdf",
    b"II*\x00": "tif",
    b"MM\x00*": "tif",
    b"RIFF": "webp",
}

TEMPORARY_HTTP_CODES = {429, 500, 502, 503, 504}
PERMANENT_HTTP_CODES = {401, 403, 404, 410}


def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def detect_signature(data_head):
    for magic, ext in MAGIC_SIGNATURES.items():
        if data_head.startswith(magic):
            return ext
    # HTML detection for text/canonical documents
    head_lower = data_head[:200].lower()
    if b"<!doctype html" in head_lower or b"<html" in head_lower:
        return "html"
    return None


def get_image_dimensions(data, ext):
    """Minimal, dependency-free dimension readers for jpg/png/gif. No AI/visual analysis."""
    try:
        if ext == "png":
            if len(data) >= 24 and data[12:16] == b"IHDR":
                w, h = struct.unpack(">II", data[16:24])
                return w, h
        elif ext == "gif":
            if len(data) >= 10:
                w, h = struct.unpack("<HH", data[6:10])
                return w, h
        elif ext == "jpg":
            idx = 2
            while idx < len(data) - 9:
                if data[idx] != 0xFF:
                    idx += 1
                    continue
                marker = data[idx + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                              0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h = struct.unpack(">H", data[idx + 5:idx + 7])[0]
                    w = struct.unpack(">H", data[idx + 7:idx + 9])[0]
                    return w, h
                if marker in (0xD8, 0xD9, 0x01) or (0xD0 <= marker <= 0xD7):
                    idx += 2
                    continue
                seg_len = struct.unpack(">H", data[idx + 2:idx + 4])[0]
                idx += 2 + seg_len
    except Exception:
        pass
    return None, None


class TemporaryDownloadError(Exception):
    pass


class PermanentDownloadError(Exception):
    def __init__(self, msg, status_hint):
        super().__init__(msg)
        self.status_hint = status_hint  # HOLD_LICENSE-ish mapping done by caller


def fetch_bytes(url, max_retries=3, timeout=60):
    """Fetch bytes with retry only on temporary failures. Raises on permanent failures."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                return data, dict(resp.getheaders()), resp.status
        except urllib.error.HTTPError as e:
            if e.code in PERMANENT_HTTP_CODES:
                raise PermanentDownloadError(f"HTTP {e.code} for {url}", e.code)
            if e.code in TEMPORARY_HTTP_CODES:
                last_exc = e
                time.sleep(min(2 ** attempt, 8))
                continue
            # Unclassified HTTP errors: treat as permanent to avoid infinite retry loops
            raise PermanentDownloadError(f"HTTP {e.code} for {url}", e.code)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_exc = e
            time.sleep(min(2 ** attempt, 8))
            continue
    raise TemporaryDownloadError(f"Exhausted {max_retries} retries fetching {url}: {last_exc}")


def sha256_of(data):
    return hashlib.sha256(data).hexdigest()


def write_citation_sidecar(
    citation_path,
    row,
    resolved,
    sha256_hex,
    local_filename,
    image_width=None,
    image_height=None,
):
    lines = []
    lines.append(f"# {row['title']}")
    lines.append("")
    lines.append(f"- **Creator/Institution:** {row['creator_or_institution']}")
    lines.append(f"- **Date:** {row['date']}")
    lines.append(f"- **Repository:** {row['repository']}")
    lines.append(f"- **License:** {row['license']}")
    lines.append(f"- **Attribution (verbatim, use in student/teacher-facing material):**")
    lines.append(f"  {row['attribution']}")
    lines.append("")
    lines.append(f"- **Source page URL:** {row['source_page_url']}")
    if resolved.get("download_url"):
        lines.append(f"- **Resolved direct download URL:** {resolved['download_url']}")
    lines.append(f"- **Download date:** {datetime.now(timezone.utc).date().isoformat()}")
    lines.append(f"- **SHA-256 checksum:** {sha256_hex}")
    if image_width and image_height:
        lines.append(f"- **Image dimensions:** {image_width} × {image_height} pixels")
    else:
        lines.append("- **Image dimensions:** N/A (not an image)")
    lines.append(f"- **Source warning:** {resolved.get('source_warning', 'None')}")
    lines.append(f"- **Resolution method:** {resolved.get('resolution_note', 'n/a')}")
    lines.append(f"- **Standard:** {row['standard']}")
    lines.append(f"- **Course / Unit:** {row['course']} / {row['unit']}")
    lines.append(f"- **Asset type:** {row['asset_type']}")
    lines.append(f"- **Local filename:** {local_filename}")
    lines.append("")
    lines.append("---")
    lines.append("_Generated automatically by primary_source_pipeline. Do not edit by hand; regenerate via resume command if metadata changes._")
    with open(citation_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
