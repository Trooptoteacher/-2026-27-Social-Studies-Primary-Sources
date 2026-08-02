#!/usr/bin/env bash
# Download the public-domain World-History videos from the Internet Archive and stage
# them (standard-named) for upload to Azure Blob Storage.
#
# Prereqs (one-time):
#   pip install internetarchive          # the `ia` CLI
#   # Azure: install azcopy  (https://aka.ms/downloadazcopy)  OR the az CLI
#
# Usage:
#   1) edit AZ_* below (or export them)   2) bash download_and_upload_videos.sh
set -euo pipefail

OUT="./media/world"; mkdir -p "$OUT"

# archive.org identifier  ->  standard-based filename (edit/extend freely)
declare -A ITEMS=(
  [70752FlashesOfAction]="W30_flashes-of-action-wwi.mp4"
  [111-adc-138]="W31_wwi-films-nara.mp4"
  [ASC-139]="W32_historical-wwi-films-army.mp4"
  [31434WestfrontWWINewsreelRexfer]="W33_wwi-western-front-newsreel.mp4"
  [DDay1944]="US47_dday-1944.mp4"
  [NewsOfTheDay1937-1943]="US48_news-of-the-day-1937-43.mp4"
  [wwii-nat-archives-videos]="W47_wwii-national-archives.mp4"
  [Newsreels]="W45_wardept-military-intelligence.mp4"
  [55684OfficialFilmNewsthrillPhotoFun]="US45_official-films-1941.mp4"
  [NewsreelClips1940-43]="US49_newsreel-clips-1940-43.mp4"
  [Communis1952]="US59_communism-coldwar-1952.mp4"
)

echo "== Downloading from the Internet Archive =="
for id in "${!ITEMS[@]}"; do
  target="$OUT/${ITEMS[$id]}"
  if [ -s "$target" ]; then echo "  skip (have) $target"; continue; fi
  echo "  $id -> $target"
  # grab the H.264/MP4 derivative only, flatten, then rename the first mp4
  tmp="./_dl/$id"; mkdir -p "$tmp"
  ia download "$id" --glob="*.mp4" --no-directories -d "$tmp" || {
      echo "  !! $id has no .mp4 derivative — open the item page and pick a format manually"; continue; }
  mp4="$(ls -S "$tmp"/*.mp4 2>/dev/null | head -1 || true)"
  [ -n "$mp4" ] && mv -f "$mp4" "$target" && echo "     saved $(du -h "$target" | cut -f1)"
done
rm -rf ./_dl
echo "Downloaded files in: $OUT"
echo "NOTE: Wikimedia (.webm) and the LoC/NARA browse links are not scripted — download those"
echo "      manually; transcode webm:  ffmpeg -i in.webm -c:v libx264 -crf 20 -c:a aac out.mp4"

# -------- Upload to Azure Blob Storage --------
AZ_ACCOUNT="${AZ_ACCOUNT:-YOUR_STORAGE_ACCOUNT}"
AZ_CONTAINER="${AZ_CONTAINER:-videos}"
AZ_SAS="${AZ_SAS:-YOUR_SAS_TOKEN}"     # container SAS with Write/Create (starts with ?sv=...)

if [ "$AZ_ACCOUNT" = "YOUR_STORAGE_ACCOUNT" ]; then
  echo; echo "== Azure upload skipped — set AZ_ACCOUNT / AZ_CONTAINER / AZ_SAS, then re-run =="
  echo "   azcopy example:"
  echo "   azcopy copy \"$OUT/*\" \"https://<acct>.blob.core.windows.net/<container>/world/\$AZ_SAS\" --content-type video/mp4"
  exit 0
fi
echo "== Uploading to Azure ($AZ_ACCOUNT/$AZ_CONTAINER/world) =="
azcopy copy "$OUT/*" "https://${AZ_ACCOUNT}.blob.core.windows.net/${AZ_CONTAINER}/world/${AZ_SAS}" \
  --content-type "video/mp4"
echo "Done. Blob URLs: https://${AZ_ACCOUNT}.blob.core.windows.net/${AZ_CONTAINER}/world/<file>.mp4"
