#!/usr/bin/env python3
"""
Deterministic, checkpointed primary-source download pipeline.

Generalized to process any unit named in the manifest, in sequential
batches (default batch size 25), with max 4 concurrent downloads per batch.

Usage:
    python3 pipeline.py --manifest /path/to/manifest.csv --unit "Cold War (1945-1991)" [--batch-size 25] [--only-row N] [--force]
    python3 pipeline.py --manifest /path/to/manifest.csv --all-units [--batch-size 25]

Resume-safe: rows already downloaded or in a terminal exception state are
skipped unless --force is passed.
"""
import argparse
import csv
import concurrent.futures
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(__file__))
import db
import resolvers
import downloader

PIPE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS_DIR = os.path.join(PIPE_DIR, "assets")
LOGS_DIR = os.path.join(PIPE_DIR, "logs")

MAX_CONCURRENCY = 4
MAX_RETRIES = 3
DEFAULT_BATCH_SIZE = 25

TERMINAL_STATUSES = {
    "DOWNLOADED", "UPLOADED", "SUCCESS", "HOLD_LICENSE",
    "BROKEN_LINK", "ACCESS_BLOCKED", "FAILED_VALIDATION",
}

log_lock = threading.Lock()
csv_log_rows = []
exception_rows = []


def load_manifest_rows(manifest_path):
    """Load all manifest rows with their 0-indexed row id (data rows only)."""
    rows = []
    with open(manifest_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            rows.append((idx, row))
    return rows


def load_manifest_unit_rows(manifest_path, unit_name):
    return [(idx, row) for idx, row in load_manifest_rows(manifest_path) if row["unit"] == unit_name]


def list_units_in_order(manifest_path):
    """Return the distinct unit names in the order they first appear in the manifest."""
    seen = []
    for _, row in load_manifest_rows(manifest_path):
        if row["unit"] not in seen:
            seen.append(row["unit"])
    return seen


def chunk(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def append_csv_log(row_id, row, status, message, resolved_url="", local_path="", sha256_hex=""):
    with log_lock:
        csv_log_rows.append({
            "row_id": row_id,
            "standard": row["standard"],
            "title": row["title"],
            "repository": row["repository"],
            "status": status,
            "message": message,
            "resolved_url": resolved_url,
            "local_path": local_path,
            "sha256": sha256_hex,
            "timestamp": db.now(),
        })


def append_exception(row_id, row, status, error):
    with log_lock:
        exception_rows.append({
            "row_id": row_id,
            "standard": row["standard"],
            "title": row["title"],
            "repository": row["repository"],
            "status": status,
            "error": error,
            "source_page_url": row["source_page_url"],
            "timestamp": db.now(),
        })


def flush_logs():
    with log_lock:
        log_csv_path = os.path.join(PIPE_DIR, "download_log.csv")
        write_header = not os.path.exists(log_csv_path) or os.path.getsize(log_csv_path) == 0
        fieldnames = ["row_id", "standard", "title", "repository", "status", "message",
                      "resolved_url", "local_path", "sha256", "timestamp"]
        with open(log_csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            for r in csv_log_rows:
                writer.writerow(r)
        csv_log_rows.clear()

        exc_csv_path = os.path.join(PIPE_DIR, "exception_report.csv")
        write_header2 = not os.path.exists(exc_csv_path) or os.path.getsize(exc_csv_path) == 0
        fieldnames2 = ["row_id", "standard", "title", "repository", "status", "error",
                       "source_page_url", "timestamp"]
        with open(exc_csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames2)
            if write_header2:
                writer.writeheader()
            for r in exception_rows:
                writer.writerow(r)
        exception_rows.clear()


def process_row(row_id, row, force=False):
    conn = db.init_db()
    db.upsert_row_from_manifest(conn, row_id, row)
    existing = db.get_row(conn, row_id)

    if existing["status"] in TERMINAL_STATUSES and not force:
        append_csv_log(row_id, row, existing["status"], "Skipped (already terminal; resume-safe).")
        conn.close()
        return

    db.update_status(conn, row_id, "DOWNLOADING")
    db.increment_attempts(conn, row_id)

    # --- Resolve within named repository ---
    try:
        resolved = resolvers.resolve(row)
    except Exception as e:
        msg = f"Resolver crashed: {e}"
        db.update_status(conn, row_id, "ACCESS_BLOCKED", error_message=msg)
        append_csv_log(row_id, row, "ACCESS_BLOCKED", msg)
        append_exception(row_id, row, "ACCESS_BLOCKED", msg)
        conn.close()
        return

    if not resolved.get("ok"):
        status = resolved.get("status") or "BROKEN_LINK"
        err = resolved.get("error") or "Unresolved (no error detail)."
        db.update_status(conn, row_id, status, error_message=err)
        append_csv_log(row_id, row, status, err)
        append_exception(row_id, row, status, err)
        conn.close()
        return

    download_url = resolved["download_url"]
    ext_hint = resolved.get("extension_hint", "bin")

    # --- Download with bounded retries; permanent errors are not retried ---
    try:
        data, headers, http_status = downloader.fetch_bytes(download_url, max_retries=MAX_RETRIES)
    except downloader.PermanentDownloadError as e:
        code = e.status_hint
        status = "HOLD_LICENSE" if code == 401 else "ACCESS_BLOCKED" if code == 403 else "BROKEN_LINK"
        err = f"Permanent download failure: {e}"
        db.update_status(conn, row_id, status, error_message=err, resolved_url=download_url)
        append_csv_log(row_id, row, status, err, resolved_url=download_url)
        append_exception(row_id, row, status, err)
        conn.close()
        return
    except downloader.TemporaryDownloadError as e:
        err = f"Temporary download failure after {MAX_RETRIES} retries: {e}"
        db.update_status(conn, row_id, "FAILED_VALIDATION", error_message=err, resolved_url=download_url)
        append_csv_log(row_id, row, "FAILED_VALIDATION", err, resolved_url=download_url)
        append_exception(row_id, row, "FAILED_VALIDATION", err)
        conn.close()
        return
    except Exception as e:
        err = f"Unexpected download error: {e}"
        db.update_status(conn, row_id, "FAILED_VALIDATION", error_message=err, resolved_url=download_url)
        append_csv_log(row_id, row, "FAILED_VALIDATION", err, resolved_url=download_url)
        append_exception(row_id, row, "FAILED_VALIDATION", err)
        conn.close()
        return

    db.update_status(conn, row_id, "DOWNLOADED", resolved_url=download_url)

    # --- Validate: magic signature, nonzero size, extension, dimensions ---
    if not data or len(data) == 0:
        err = "Downloaded file is zero bytes."
        db.update_status(conn, row_id, "FAILED_VALIDATION", error_message=err, resolved_url=download_url)
        append_csv_log(row_id, row, "FAILED_VALIDATION", err, resolved_url=download_url)
        append_exception(row_id, row, "FAILED_VALIDATION", err)
        conn.close()
        return

    detected_ext = downloader.detect_signature(data[:64])
    if detected_ext is None:
        err = f"Could not detect a known file signature (magic bytes) for downloaded content from {download_url}."
        db.update_status(conn, row_id, "FAILED_VALIDATION", error_message=err, resolved_url=download_url)
        append_csv_log(row_id, row, "FAILED_VALIDATION", err, resolved_url=download_url)
        append_exception(row_id, row, "FAILED_VALIDATION", err)
        conn.close()
        return

    width, height = (None, None)
    if detected_ext in ("jpg", "png", "gif"):
        width, height = downloader.get_image_dimensions(data, detected_ext)
        if not width or not height or width <= 0 or height <= 0:
            err = f"Image dimension validation failed for detected type {detected_ext}."
            db.update_status(conn, row_id, "FAILED_VALIDATION", error_message=err, resolved_url=download_url)
            append_csv_log(row_id, row, "FAILED_VALIDATION", err, resolved_url=download_url)
            append_exception(row_id, row, "FAILED_VALIDATION", err)
            conn.close()
            return

    # --- Build approved filename: [standard]_[source-title-slug].[original extension] ---
    title_slug = downloader.slugify(row["title"])
    approved_filename = f"{row['standard']}_{title_slug}.{detected_ext}"

    subfolder_rel = row["standard"]
    target_dir = os.path.join(ASSETS_DIR, subfolder_rel)
    os.makedirs(target_dir, exist_ok=True)
    local_path = os.path.join(target_dir, approved_filename)

    with open(local_path, "wb") as f:
        f.write(data)

    sha256_hex = downloader.sha256_of(data)

    citation_path = local_path + ".citation.md"
    downloader.write_citation_sidecar(
        citation_path,
        row,
        resolved,
        sha256_hex,
        approved_filename,
        image_width=width,
        image_height=height,
    )

    db.update_status(
        conn, row_id, "DOWNLOADED",
        resolved_url=download_url,
        local_path=local_path,
        citation_path=citation_path,
        sha256=sha256_hex,
        original_extension=detected_ext,
        file_size_bytes=len(data),
        image_width=width,
        image_height=height,
        error_message=None,
    )
    append_csv_log(row_id, row, "DOWNLOADED",
                    f"Downloaded + validated ({len(data)} bytes, {detected_ext}"
                    + (f", {width}x{height}" if width else "") + ").",
                    resolved_url=download_url, local_path=local_path, sha256_hex=sha256_hex)
    conn.close()


def run_unit(manifest_path, unit_name, batch_size, only_row, force):
    """Process a single unit's rows in sequential batches of `batch_size`,
    with up to MAX_CONCURRENCY concurrent downloads within each batch.
    Returns the unit's post-run status_counts dict (for this unit's rows only)."""
    rows = load_manifest_unit_rows(manifest_path, unit_name)
    if only_row is not None:
        rows = [(idx, r) for idx, r in rows if idx == only_row]

    print(f"\n=== Unit '{unit_name}': {len(rows)} row(s) from {manifest_path} ===")

    os.makedirs(ASSETS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

    conn = db.init_db()
    for row_id, row in rows:
        db.upsert_row_from_manifest(conn, row_id, row)
    conn.close()

    row_ids_this_unit = [row_id for row_id, _ in rows]

    batches = list(chunk(rows, batch_size))
    for b_idx, batch in enumerate(batches, start=1):
        print(f"--- Batch {b_idx}/{len(batches)} ({len(batch)} rows) ---")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as executor:
            futures = [executor.submit(process_row, row_id, row, force) for row_id, row in batch]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    fut.result()
                except Exception as e:
                    print(f"Row processing raised: {e}")
                finally:
                    flush_logs()  # checkpoint after every asset
        flush_logs()

    conn = db.init_db()
    all_rows = db.get_all(conn)
    conn.close()
    status_counts = {}
    for r in all_rows:
        if r["row_id"] in row_ids_this_unit:
            status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    print(f"--- Unit '{unit_name}' complete ---")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")

    return status_counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=os.path.join(PIPE_DIR, "..", "world_history_normalized_manifest.csv"))
    parser.add_argument("--unit", default=None, help="Exact manifest 'unit' value to process. Omit + pass --all-units to process every unit sequentially.")
    parser.add_argument("--all-units", action="store_true", help="Process every unit in the manifest, sequentially, in manifest order.")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help=f"Rows per sequential batch (default {DEFAULT_BATCH_SIZE}). Within a batch, up to {MAX_CONCURRENCY} downloads run concurrently.")
    parser.add_argument("--only-row", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Re-process rows even if in a terminal state.")
    args = parser.parse_args()

    manifest_path = os.path.abspath(args.manifest)

    if not args.unit and not args.all_units:
        parser.error("Must pass either --unit \"<exact unit name>\" or --all-units.")

    if args.all_units:
        units = list_units_in_order(manifest_path)
    else:
        units = [args.unit]

    overall_counts = {}
    for unit_name in units:
        counts = run_unit(manifest_path, unit_name, args.batch_size, args.only_row, args.force)
        for status, c in counts.items():
            overall_counts[status] = overall_counts.get(status, 0) + c

    print("\n=== Pipeline run complete (all requested units) ===")
    for status, count in sorted(overall_counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
