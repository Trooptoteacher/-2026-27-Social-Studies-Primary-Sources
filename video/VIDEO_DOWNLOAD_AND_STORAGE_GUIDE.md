# Video Download & Storage — the definitive guide

How to download the public-domain videos, in what format/resolution, and **exactly** where
they go (Azure) vs. what goes in GitHub. Using the "Flashes of Action" archive.org page as the
worked example.

---

## 1. What format — download **H.264 (.mp4)**
On the archive.org **DOWNLOAD OPTIONS** panel you'll see several choices. Pick **H.264**.

| Option on the page | What it is | Use it? |
|---|---|---|
| **H.264** | MPEG-4 / **.mp4** (web-standard video) | ✅ **YES — this is the one.** Plays in every browser + HTML5 `<video>`, hardware-accelerated, best size/quality. |
| OGG VIDEO | `.ogv` (old open format) | ❌ No — poor device/browser support now. |
| QUICKTIME | `.mov` | ❌ No — large, not ideal for web serving. |
| ITEM TILE | a thumbnail **image**, not video | ❌ No. |
| TORRENT | a *download method*, not a format | Optional — only if grabbing many files at once. |
| **SHOW ALL → "7 Original"** | the original uploaded master(s) | ⭐ Optional — grab **one Original as an archival master** if you want the highest-quality source kept; **serve the H.264, not the Original.** |

**Rule:** serve **H.264 .mp4**. Optionally keep one **Original** as a cold-storage master.

## 2. What resolution — take the native derivative; don't upscale
These are historical films (WWI, scanned from 16/35 mm). **The source is the ceiling** — you
can't get more detail than exists.
- The **H.264 derivative** is already web-sized at the film's native resolution (often ~480p or
  less for 1910s–40s footage). **That's correct — use it as-is.**
- **Do NOT upscale** to "1080p" — it just makes bigger files with no new detail.
- If an item offers HD originals, **720p is the practical max** you need for classroom/web; only
  go higher if you have a reason. (For a paid HD master of a specific film, that's where a vendor
  like Periscope sells one — you don't need it; the PD copy is fine.)

## 3. What to do — the steps
**Manual (one file — what's on your screen):**
1. Click **H.264** → the `.mp4` downloads.
2. Rename it by standard + slug: `W30_flashes-of-action-wwi.mp4`.
3. Upload to Azure (§5).

**Bulk (all of them):** run `download_and_upload_videos.sh` in this folder — it uses the
`ia` CLI (`pip install internetarchive`) to pull every archive.org item as MP4, names them by
standard, and pushes to Azure in one `azcopy` call.

**Wikimedia items (`.webm`):** download the "Original file", then transcode:
`ffmpeg -i in.webm -c:v libx264 -crf 20 -c:a aac out.mp4`

## 4. Your options at a glance
| Goal | Do this |
|---|---|
| Serve in the web app | **H.264 .mp4**, self-hosted on Azure Blob |
| Keep a high-quality archival master | also grab **one "Original"** → Azure "archive" tier/container |
| Download 1–2 files | click H.264 on the page |
| Download the whole list | the `ia` CLI script |
| A `.webm` from Wikimedia | download + `ffmpeg` transcode to mp4 |

---

## 5. Where they go — **Azure Blob Storage**, NOT GitHub

**The rule:** **video files → Azure. Metadata/registry → GitHub. Never put the video files in GitHub.**

### Why not GitHub
- GitHub has a **100 MB hard file-size limit** (warns at 50 MB). "Flashes of Action" is **185.7 MB** — it can't go in a normal repo at all.
- Git repos bloat permanently with binaries (every version is kept forever); Git LFS has bandwidth **quotas and costs** and still isn't a media server (no proper streaming/range requests).
- GitHub is for **code, text, and small assets** — not for serving classroom video.

### How to store on Azure (exact structure)
1. **Storage account** → create a **container**, e.g. `videos`.
2. **Blob path = course/standard**, so it's self-documenting:
   ```
   videos/world/W30_flashes-of-action-wwi.mp4
   videos/us-history/US47_dday-1944.mp4
   videos/government/GC12_house-floor-debate.mp4
   ```
   (Optional second container `videos-archive` for the "Original" masters, on the **Cool/Archive** access tier to save cost.)
3. **Set Content-Type `video/mp4` on every blob** — without it browsers download instead of streaming. `azcopy` example:
   ```
   azcopy copy "media/world/*" \
     "https://<acct>.blob.core.windows.net/videos/world/?<SAS>" \
     --content-type video/mp4
   ```
   or per file with the az CLI:
   ```
   az storage blob upload --account-name <acct> --container-name videos \
     --name world/W30_flashes-of-action-wwi.mp4 \
     --file W30_flashes-of-action-wwi.mp4 --content-type video/mp4 --auth-mode login
   ```
4. **Delivery:** put **Azure CDN or Front Door** in front of the container (caching + range
   requests + cheaper egress). Point your player at the CDN/blob URL.
5. **Access:** this is public-domain content, so a **public-read** container is fine and simplest.
   If you prefer private, use **SAS tokens or a CDN with a signed/allowlisted origin**. Either way
   the file is **self-hosted in your own player — no YouTube, no click-out.**

### What DOES go in GitHub
Only the **registry/metadata** — the `*.video.json` record that *points at* the Azure blob and
carries provenance:
```json
{
  "standard": "W.30",
  "also_standards": ["US.23"],
  "title": "Flashes of Action — WWI combat (1928)",
  "originating_institution": "U.S. Army Expeditionary Forces / NARA",
  "access_copy_url": "https://archive.org/details/70752FlashesOfAction",
  "rights_basis": "Public domain — U.S. federal government work",
  "hosting": "self-hosted-pd",
  "blob_url": "https://<acct>.blob.core.windows.net/videos/world/W30_flashes-of-action-wwi.mp4"
}
```
**GitHub holds the pointer + provenance; Azure holds the bytes. The app reads the JSON and streams from Azure.**

---

## TL;DR
Download **H.264 .mp4** at its **native resolution** (don't upscale) → name it by standard →
upload to **Azure Blob** (`videos/<course>/<STD>_<slug>.mp4`, Content-Type `video/mp4`, CDN in
front) → put only the **JSON registry entry (with the blob URL)** in GitHub. Never the video file itself.
