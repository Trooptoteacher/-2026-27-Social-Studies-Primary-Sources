# How to Download the Public-Domain Videos

Step-by-step for each source in `WORLD_VIDEO_DOWNLOADS.md` (and the other course
manifests). The goal: get the actual video **file** so you can **self-host it in your own
player** — never embed YouTube or a third-party player.

---

## 1. Internet Archive (archive.org) — most of the links
1. Click the item link (e.g. the D-Day 1944 page).
2. On the right side, find the **"DOWNLOAD OPTIONS"** panel.
3. Click the format you want — usually **h.264 MP4** (best for a web player) or **MPEG4**.
   (The original may be very large; the h.264 derivative is fine for classroom use.)
4. The file downloads to your computer. That's your self-host source.

**Whole collection?** On a collection page (e.g. *Universal Newsreels*), open each item and
download it the same way, or use the archive.org CLI for bulk:
```
pip install internetarchive
ia download <identifier>        # e.g. ia download DDay1944
```

## 2. Wikimedia Commons (`.webm`) — discovery only, then transcode
1. Open the **File:** page.
2. Click **"Original file"** (or a resolution) to download the **.webm**.
3. **Trace provenance first:** read the file's "Source"/"Author" — follow it back to the
   holding institution (NARA/LoC/etc.) and cite **that**, not "Wikimedia Commons."
4. Transcode WebM → MP4 for your player (one-time):
```
ffmpeg -i input.webm -c:v libx264 -crf 20 -c:a aac output.mp4
```

## 3. Library of Congress — National Screening Room
1. Open the item at loc.gov/collections/national-screening-room.
2. Use the **download** control — most titles offer **MP4 (small)** and **ProRes .mov** (high quality).

## 4. National Archives (NARA) catalog
1. Search catalog.archives.gov (filter materials type → Video).
2. On the record, use the **download** option for the video file (often mirrored on archive.org too).

## 5. C-SPAN (congressional floor — Government/US)
1. Open the clip at c-span.org, sign in with a **free MyC-SPAN** account.
2. Trim the clip to **≤ 5 minutes**, then **Download** the **MP4**.
   (Unlimited free clips from Congressional Sessions; floor footage is public domain.)

---

## Before you host anything (the guardrail)
- **Rights:** only ship items marked **✅ PD (US federal work)** or otherwise confirmed
  public domain / CC0 / CC BY (commercial-cleared). For **⚠️ verify** items, open the item's
  rights statement and confirm before hosting; if unclear, **skip it** — there's plenty of
  guaranteed-PD content.
- **Provenance:** record the **originating institution** (NARA, LoC, U.S. Army, etc.), not
  the aggregator. Aggregators (Wikimedia, Internet Archive, DPLA) are where you *download*,
  not who you *cite*.
- **Self-host, no YouTube:** put the MP4/HLS on your own storage/CDN and play it in your own
  player. This keeps video ad-free, click-out-proof, and district-safe.
- **Log it:** add each cleared clip to the video registry
  (`manifests/video/*.video.json`) with `originating_institution`, `rights_basis`,
  `hosting: "self-hosted-pd"`, and the standard it serves — then run the validator.

## Suggested folder for downloaded files
```
media/<course>/<STANDARD>_<slug>.mp4      e.g. media/world/W12_flashes-of-action-wwi.mp4
```
