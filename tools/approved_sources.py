#!/usr/bin/env python3
"""
Approved-source policy for the Social Studies Hack suite (TDOE Schedule F, C5).

Single source of truth for which repositories may be CITED in adoption-grade
content. Imported by geo_review_audit.py and asset_standards_crosswalk.py so the
same rule is enforced everywhere.

classify(url_or_text) -> one of:
  "approved"        — authoritative government / archival / scholarly repository
  "prefer_original" — acceptable host for a genuinely public-domain work, but a
                      reviewer prefers the ORIGINAL repository (e.g. Wikimedia
                      Commons hosting a LoC/NARA image); allowed, warned
  "blocked"         — tertiary/general encyclopedia; never a cited source
  "unknown"         — not recognized; treat as a failure until vetted
"""

# Authoritative, academically-accepted repositories (domain -> label).
APPROVED = {
    "loc.gov": "Library of Congress",
    "archives.gov": "U.S. National Archives (NARA)",
    "docsteach.org": "NARA DocsTeach",
    "history.state.gov": "U.S. Dept. of State, Office of the Historian",
    "nps.gov": "National Park Service",
    "energy.gov": "U.S. Department of Energy",
    "fhwa.dot.gov": "Federal Highway Administration",
    "history.army.mil": "U.S. Army Center of Military History",
    "history.navy.mil": "U.S. Navy History & Heritage Command",
    "si.edu": "Smithsonian Institution",
    "nmaahc.si.edu": "Smithsonian NMAAHC",
    "census.gov": "U.S. Census Bureau",
    "congress.gov": "U.S. Congress",
    "govinfo.gov": "U.S. Government Publishing Office",
    "supremecourt.gov": "Supreme Court of the United States",
    "uspto.gov": "U.S. Patent and Trademark Office",
    "patents.google.com": "Google Patents (hosts public-domain U.S. patents)",
    "jfklibrary.org": "JFK Presidential Library",
    "hoover.archives.gov": "Hoover Presidential Library (NARA)",
    "911memorial.org": "National September 11 Memorial & Museum",
    "tennesseeencyclopedia.net": "Tennessee Encyclopedia",
    "tn.gov": "State of Tennessee",
    "sos.tn.gov": "Tennessee Secretary of State",
    "teva.contentdm.oclc.org": "Tennessee Virtual Archive (TeVA)",
    "tnmuseum.org": "Tennessee State Museum",
    # Open-access museums & libraries — public-domain / CC0 programs (commercial-use safe).
    # NOTE: repository trust only (Rule 1). Per-item rights are still enforced by Rule 2.
    "metmuseum.org": "The Metropolitan Museum of Art (Open Access, CC0)",
    "clevelandart.org": "Cleveland Museum of Art (Open Access, CC0)",
    "nga.gov": "National Gallery of Art (Open Access, CC0)",
    "getty.edu": "The Getty (Open Content Program)",
    "rijksmuseum.nl": "Rijksmuseum (public domain / CC0)",
    "nypl.org": "New York Public Library Digital Collections",
    "digitalcollections.nypl.org": "NYPL Digital Collections",
    "hathitrust.org": "HathiTrust Digital Library (public-domain works)",
    "fdrlibrary.org": "FDR Presidential Library (NARA)",
    "gilderlehrman.org": "Gilder Lehrman Institute of American History",
    # Authoritative data sources — for charts/graphs built from primary data (Rule 6).
    "bls.gov": "U.S. Bureau of Labor Statistics",
    "bea.gov": "U.S. Bureau of Economic Analysis",
    "data.gov": "U.S. Open Data",
    "usgs.gov": "U.S. Geological Survey",
    "noaa.gov": "NOAA",
    "nasa.gov": "NASA",
    "stlouisfed.org": "Federal Reserve (FRED economic data)",
    "ourworldindata.org": "Our World in Data (CC BY)",
}
# Any *.gov and *.edu host is treated as approved even if not listed above.
APPROVED_TLDS = (".gov", ".edu")

# Acceptable HOST for a public-domain work, but prefer the original repository.
PREFER_ORIGINAL = {
    "commons.wikimedia.org": "Wikimedia Commons (media repository)",
    "dp.la": "Digital Public Library of America",
    "archive.org": "Internet Archive (host for PD works)",
    "flickr.com": "Flickr Commons (verify 'no known copyright')",
    "picryl.com": "PICRYL (public-domain aggregator)",
    "loc.getarchive.net": "GetArchive (PD aggregator)",
}

# Tertiary / study-aid sites — never a cited primary source (fact-check aid only).
BLOCKED = {
    "britannica.com": "Encyclopaedia Britannica",
    "wikipedia.org": "Wikipedia",
    "en.wikipedia.org": "Wikipedia",
    "history.com": "History.com (secondary/tertiary)",
    "study.com": "Study.com",
    "ducksters.com": "Ducksters",
    "quizlet.com": "Quizlet",
    "coursehero.com": "Course Hero",
    "sparknotes.com": "SparkNotes",
    "cliffsnotes.com": "CliffsNotes",
    "ixl.com": "IXL",
}


def _host(s):
    s = str(s or "").lower()
    if "://" in s:
        s = s.split("://", 1)[1]
    # citations often read "... — Library of Congress: https://www.loc.gov/..."
    if " http" in s:
        s = s.split(" http", 1)[1]
    s = s.split("/", 1)[0].split()[-1] if s else s
    return s.lstrip("www.")


# Repository-name fallbacks (when a row gives a name, not a URL).
NAME_APPROVED = ("library of congress", "national archives", "office of the historian",
                 "national park service", "smithsonian", "census", "army center of military",
                 "navy history", "tennessee encyclopedia", "tennessee state museum",
                 "tennessee state library", "presidential library",
                 "department of energy", "federal highway", "supreme court", "9/11 memorial",
                 "september 11 memorial", "metropolitan museum", "cleveland museum",
                 "national gallery of art", "getty", "rijksmuseum", "new york public library",
                 "nypl", "hathitrust", "gilder lehrman", "bureau of labor statistics",
                 "bureau of economic analysis", "geological survey", "noaa", "nasa",
                 "federal reserve", "our world in data", "patent and trademark",
                 "google patents", "uspto")
NAME_PREFER = ("wikimedia commons", "wikimedia", "digital public library", "dpla",
               "internet archive", "flickr commons", "picryl", "getarchive")
NAME_BLOCKED = ("britannica", "wikipedia", "history.com", "study.com", "ducksters",
                "quizlet", "course hero", "sparknotes", "cliffsnotes", "ixl")


def classify(url_or_text):
    h = _host(url_or_text)
    for dom in BLOCKED:
        if h == dom or h.endswith("." + dom):
            return "blocked"
    for dom in PREFER_ORIGINAL:
        if h == dom or h.endswith("." + dom):
            return "prefer_original"
    for dom in APPROVED:
        if h == dom or h.endswith("." + dom):
            return "approved"
    if h.endswith(APPROVED_TLDS):
        return "approved"
    # name-based fallback (repository column may be a label, not a URL).
    # Check Wikimedia (Commons/CDN) BEFORE the "wikipedia" substring so that
    # upload.wikimedia.org storage paths (which contain "/wikipedia/") are not
    # mistaken for the encyclopedia.
    t = str(url_or_text or "").lower()
    if "wikimedia" in h or any(n in t for n in NAME_PREFER):
        return "prefer_original"
    if any(n in t for n in NAME_BLOCKED):
        return "blocked"
    if any(n in t for n in NAME_APPROVED):
        return "approved"
    return "unknown"


if __name__ == "__main__":
    import sys
    for arg in sys.argv[1:]:
        print(f"{classify(arg):15} {arg}")
