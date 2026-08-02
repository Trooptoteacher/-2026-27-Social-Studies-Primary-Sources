#!/usr/bin/env python3
"""Stage validated World History assets and checkpoint files into the source repo."""

import csv
import json
import os
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PIPE = Path(__file__).resolve().parent.parent
REPO = Path("/home/user/workspace/social-studies-primary-sources")
DB = PIPE / "download_state.sqlite"
MANIFEST_JSON = REPO / "manifests/hs-world-history.json"
SOURCE_ROOT = REPO / "sources/hs-world-history"
RUN_ROOT = REPO / "runs/hs-world-history"

INVALID = {
    25: "Exactness validation failed: resolver selected a modern LOC book record rather than the specified 19th-century Manchester/Leeds view.",
    33: "Exactness validation failed: resolver selected a book page that does not establish the compound Bessemer-converter/electric-telegraph asset.",
    53: "Exactness validation failed: resolver selected a book page rather than the specified contemporary Boxer Rebellion photograph.",
    71: "Content validation failed: downloaded Avalon URL is a navigation menu, not the Treaty of Brest-Litovsk source text.",
    76: "Content validation failed: downloaded Avalon URL is a navigation menu, not the Treaty of Versailles source text.",
}


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def exact_catalog_url(row):
    if row["repository"] != "Library of Congress":
        return row["source_page_url"]
    citation = Path(row["citation_path"]).read_text(encoding="utf-8")
    match = re.search(r"\((https://www\.loc\.gov/item/[^)]+/)\)", citation)
    return match.group(1) if match else row["source_page_url"]


def write_sidecar(destination, row, catalog_url):
    dimensions = (
        f"{row['image_width']} × {row['image_height']} pixels"
        if row["image_width"] and row["image_height"]
        else "N/A (not an image)"
    )
    warning = (
        "HTML transcription or treaty text hosted by the named repository; this is not a scan of an original manuscript."
        if row["original_extension"] == "html"
        else "None"
    )
    lines = [
        f"# {row['title']}",
        "",
        f"- **Title:** {row['title']}",
        f"- **Creator or institution:** {row['creator_or_institution']}",
        f"- **Date:** {row['date']}",
        f"- **Source-page URL:** {catalog_url}",
        f"- **Direct-download URL:** {row['resolved_url']}",
        f"- **License or rights statement:** {row['license']}",
        "- **Required attribution:**",
        f"  {row['attribution']}",
        f"- **Download date:** {row['last_attempt_at'][:10]}",
        f"- **SHA-256 checksum:** {row['sha256']}",
        f"- **Image dimensions:** {dimensions}",
        f"- **Source warning:** {warning}",
        f"- **Course:** {row['course']}",
        f"- **Unit:** {row['unit']}",
        f"- **Standard:** {row['standard']}",
        "",
    ]
    destination.write_text("\n".join(lines), encoding="utf-8")


def append_audit_csv(path, fieldnames, record):
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(record)


def main():
    SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    RUN_ROOT.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    for row_id, message in INVALID.items():
        row = conn.execute("SELECT * FROM assets WHERE row_id=?", (row_id,)).fetchone()
        conn.execute(
            "UPDATE assets SET status='FAILED_VALIDATION', error_message=?, updated_at=? WHERE row_id=?",
            (message, now(), row_id),
        )
        if row["status"] == "FAILED_VALIDATION" and row["error_message"] == message:
            continue
        append_audit_csv(
            PIPE / "download_log.csv",
            ["row_id", "standard", "title", "repository", "status", "message",
             "resolved_url", "local_path", "sha256", "timestamp"],
            {
                "row_id": row_id,
                "standard": row["standard"],
                "title": row["title"],
                "repository": row["repository"],
                "status": "FAILED_VALIDATION",
                "message": message,
                "resolved_url": row["resolved_url"],
                "local_path": row["local_path"],
                "sha256": row["sha256"],
                "timestamp": now(),
            },
        )
        append_audit_csv(
            PIPE / "exception_report.csv",
            ["row_id", "standard", "title", "repository", "status", "error",
             "source_page_url", "timestamp"],
            {
                "row_id": row_id,
                "standard": row["standard"],
                "title": row["title"],
                "repository": row["repository"],
                "status": "FAILED_VALIDATION",
                "error": message,
                "source_page_url": row["source_page_url"],
                "timestamp": now(),
            },
        )

    valid_rows = conn.execute(
        """SELECT * FROM assets
           WHERE status IN ('DOWNLOADED','SUCCESS') AND row_id NOT IN (25,33,53,71,76)
           ORDER BY row_id"""
    ).fetchall()

    records = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    by_key = {(item["standard"], item["title"]): item for item in records}
    staged = []

    for row in valid_rows:
        key = (row["standard"], row["title"])
        if key not in by_key:
            raise RuntimeError(f"Manifest match missing for {key}")
        source = Path(row["local_path"])
        destination_dir = SOURCE_ROOT / row["standard"]
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / source.name
        shutil.copy2(source, destination)
        sidecar = destination.with_name(destination.name + ".citation.md")
        catalog_url = exact_catalog_url(row)
        write_sidecar(sidecar, row, catalog_url)

        item = by_key[key]
        item["catalog_url"] = catalog_url
        item["download_url"] = row["resolved_url"]
        item["verified"] = True

        repo_path = destination.relative_to(REPO).as_posix()
        conn.execute(
            """UPDATE assets
               SET status='SUCCESS', drive_destination_url=?, uploaded_at=?,
                   error_message=NULL, updated_at=?
               WHERE row_id=?""",
            (f"repo:{repo_path}", now(), now(), row["row_id"]),
        )
        staged.append((row, catalog_url, repo_path))

    MANIFEST_JSON.write_text(
        json.dumps(records, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    index_lines = [
        "# World History Primary Sources",
        "",
        "Validated assets are organized by Tennessee standard. Each file has a matching citation sidecar.",
        "",
        "| Standard | Title | Repository path | SHA-256 |",
        "|---|---|---|---|",
    ]
    for row, _, repo_path in staged:
        safe_title = row["title"].replace("|", "\\|")
        index_lines.append(
            f"| {row['standard']} | {safe_title} | `{repo_path}` | `{row['sha256']}` |"
        )
    index_lines.append("")
    (SOURCE_ROOT / "README.md").write_text("\n".join(index_lines), encoding="utf-8")

    conn.commit()
    conn.close()

    for filename in [
        "download_state.sqlite",
        "download_log.csv",
        "exception_report.csv",
        "world_history_normalized_manifest.csv",
        "resume.sh",
        "README.md",
    ]:
        source = PIPE / filename
        if source.exists():
            shutil.copy2(source, RUN_ROOT / filename)
    scripts_out = RUN_ROOT / "scripts"
    scripts_out.mkdir(exist_ok=True)
    for filename in ["pipeline.py", "db.py", "resolvers.py", "downloader.py", "stage_to_repo.py"]:
        shutil.copy2(PIPE / "scripts" / filename, scripts_out / filename)

    print(f"Staged {len(staged)} validated assets and sidecars.")


if __name__ == "__main__":
    main()
