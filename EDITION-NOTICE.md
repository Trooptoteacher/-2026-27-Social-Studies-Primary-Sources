# ⛔ Every standard code in this repo is a **2026-27** code

Tennessee's revised social studies standards take effect in the **2027-28** school year. This
library was built against the **2026-27** standards and is keyed to them throughout — every
`"standard"` field in `manifests/`, every `standard` column in `crosswalk/`, and every filename
under `sources/`.

Those codes are **bare**: `"standard": "GC.01"` carries no year. That is fine while there is one
standards set. There are now two.

## Why this matters

**A standard code is not stable between the two editions.**

| | 2026-27 | 2027-28 |
|---|---|---|
| `US.01` | the Homestead Act and the Transcontinental Railroad | Reconstruction and the Compromise of 1877 |
| `US.04` | Gilded Age politics and economics | the Homestead Act and the Transcontinental Railroad |

**416 codes exist in both editions and mean different things** — including **84 of the 94** U.S.
History codes, **72 of the 74** Grade 8 codes, and **35 of the 47** Government & Civics codes, which
is most of the set this repo has actually populated.

So a source in this repo, matched to a 2027-28 standard by code, will match, will look right, and
will be wrong far more often than not. That is not a hypothetical: it is the majority case.

## What to do instead

**Do not reuse anything here for a 2027-28 build by code.** Go through the crosswalk:

1. `crosswalk/<course>.csv` in **`Trooptoteacher/2027-28-Tn-Social-Studies-Standards`**
2. Read the row's `disposition`:
   - **`unchanged`** — same standard, possibly re-coded. The source carries forward. Re-point it to
     the 2027-28 code and re-verify the citation still fits the standard.
   - **`revised`** — same standard, reworded. Read both texts before reusing. The words after
     "including" are a content checklist; a revision that adds a named person, event or act is not
     covered by a source chosen for the old wording.
   - **`new`** / **`retired`** — no counterpart. Nothing carries.
3. The re-pointed record belongs in the **2027-28** tree, stamped with its year — not edited in
   place here. This repo stays as it is, serving the 2026-27 standards that Tennessee classrooms are
   teaching now.

`crosswalk/collisions.csv` in that repo enumerates all 416 collisions.

## Related

| Repository | Role |
|---|---|
| `Trooptoteacher/2026-27-Tn.-Social-Studies-Standards` | The standards this library is keyed to |
| `Trooptoteacher/2027-28-Tn-Social-Studies-Standards` | The new standards, the crosswalk, and `GOVERNANCE.md` — the two-edition contract |
| `Trooptoteacher/history-hack-web-app` | Where 2027-28 courses are built, under an isolated `2027-28` namespace |
