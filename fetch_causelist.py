#!/usr/bin/env python3
"""
Supreme Court of India — per-court BENCH (coram) fetcher for SD-Chamber.

Model (owner's decision, Jul 2026): the office Staff enter each listing on the
day sheet — court no, item no, causelist type, cause title, date, briefing
counsel. This scheduled Action cannot read the app's database, so it does NOT
search for the chamber's matters. Instead it downloads the published SC lists
for a rolling window of upcoming days and extracts, per (date, list-type,
court): the BENCH (coram) and the court's total/fresh counts. The app then
looks up whatever court/item/type/date Staff entered and fills in the
authoritative bench "as per the causelist".

Writes court-updates.json at the repo root; the app reads it same-origin.
Free: pure fetch + PDF text, no API keys. Drafting aid only — the court's
published list is authoritative.

List-type PDF codes (verified against real 13-07-2026 PDFs):
  Miscellaneous  M_J   |  Regular / Final  F_J  |  Chamber  M_C
  Single Judge   M_S   |  Registrar        M_R  |  Curative & Review  M_CC
Each publishes _1 (main) and, some days, _2 (supplementary).
"""

import io
import json
import re
import sys
import time
import datetime
import urllib.request

DAILY_BASE = "https://api.sci.gov.in/jonew/cl/{date}/{suffix}.pdf"

# human list-type -> (suffix, variant) to try, main first then supplementary so
# a later supplementary court entry overrides the main one for the same court.
LIST_TYPES = {
    "Miscellaneous":      [("M_J_1", "main"), ("M_J_2", "supp")],
    "Regular":            [("F_J_1", "main"), ("F_J_2", "supp")],
    "Chamber":            [("M_C_1", "main"), ("M_C_2", "supp")],
    "Single Judge":       [("M_S_1", "main"), ("M_S_2", "supp")],
    "Registrar":          [("M_R_1", "main"), ("M_R_2", "supp")],
    "Curative & Review":  [("M_CC_1", "main")],
}

# Fetch every published list for a full week+ of upcoming sitting days, so a
# matter listed several days out (e.g. a call today for a hearing next Tuesday)
# already resolves its cause title the moment the SC publishes that day's list.
WINDOW_DAYS = 12
OUTPUT_FILE = "court-updates.json"
# Bump whenever parse_courts changes how items/benches are extracted. The size-
# based change-detection reuses a cached parse when the PDF is unchanged; without
# this, a parser FIX never reaches already-cached dates (their PDFs don't change).
# A version mismatch forces a full re-parse of every date in the window.
PARSER_VERSION = 10  # bumped: advocates per side (wrapped names, several per side, caveat/amicus), wrapped serials (39.1+1 = 39.11)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; sd-chamber-causelist-bot/1.0)"}

COURT_RE = re.compile(r"COURT\s*NO\.?\s*[:\-]?\s*([0-9]+)", re.I)
CJ_RE    = re.compile(r"CHIEF\s+JUSTICE'?S\s+COURT", re.I)
REG_RE   = re.compile(r"REGISTRAR\s+COURT\s*NO\.?\s*[:\-]?\s*([0-9]+)", re.I)
# coram lines are a judge ("HON'BLE ...") or a registrar officer ("..., REGISTRAR"
# / "REGISTRAR (TIME..."). The registrar form is kept strict so a PARTY name that
# merely contains "registrar" (e.g. "THE SUB REGISTRAR POOYAPPALLY AND ORS.") is
# NOT mistaken for the bench.
JUDGE_RE = re.compile(r"^HON'?BLE\b", re.I)
REGOFF_RE = re.compile(r",\s*REGISTRAR\b|REGISTRAR\s*(\(|$)", re.I)
TOTAL_RE = re.compile(r"total\s*(?:matters)?\s*[:\-]?\s*([0-9]+)", re.I)
FRESH_RE = re.compile(r"fresh\s*(?:matters)?\s*[:\-]?\s*([0-9]+)", re.I)
ITEM_RE  = re.compile(r"^\s*([0-9]{1,4})\b")
SKIP_CORAM = re.compile(r"NOTE|APPRECIATED|ADJOURNMENT|ASSEMBLE|WILL SIT|NORMAL", re.I)
# Page-header boilerplate repeated at the top of every page. When an item's
# "Versus" sits at the foot of a page, this line is the first thing after it and
# was wrongly captured as the respondent ("… VERSUS DAILY CAUSE LIST FOR DATED …").
# Skip it wholesale so the real respondent (further down the next page) is used.
HEADER_SKIP = re.compile(r"DAILY\s+CAUSE\s+LIST", re.I)


def is_coram(line):
    if SKIP_CORAM.search(line):
        return False
    return bool(JUDGE_RE.match(line) or REGOFF_RE.search(line))


def fetch_pdf(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as resp:
            ct = resp.headers.get("Content-Type", "").lower()
            if resp.status == 200 and ct.startswith("application/pdf"):
                return resp.read()
    except Exception:
        pass
    return None


def probe_size(url):
    """Cheap change-detection: a 1KB ranged GET. Returns the PDF's total size,
    or None if the list isn't published (the server answers 200/HTML for
    missing files). Lets a frequent schedule re-download a multi-MB list ONLY
    when the court actually re-published it."""
    try:
        req = urllib.request.Request(url, headers={**HEADERS, "Range": "bytes=0-1023"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            ct = resp.headers.get("Content-Type", "").lower()
            if not ct.startswith("application/pdf"):
                return None
            m = re.search(r"/(\d+)\s*$", resp.headers.get("Content-Range", ""))
            if m:
                return int(m.group(1))
            cl = resp.headers.get("Content-Length")   # server ignored Range
            return int(cl) if cl else len(resp.read())
    except Exception:
        return None


def pdf_to_text(data):
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception:
        pass
    try:
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
    except Exception as e:
        print("  PDF extraction failed:", e)
        return ""


# The SC list is a two-column table: party text on the left, the ADVOCATE on the
# right (a fixed column starting at x0 ~= 426 on a 595pt page). Plain extract_text
# flattens the columns onto one line, so the advocate name bleeds into the cause
# title ("VIRENDRA SINGH NAGAR RAJ KISHOR CHOUDHARY"). We can't tell party from
# advocate by text alone, but we can by x-position. So for ITEM rows we drop every
# word at/after the advocate column; header/coram rows are kept whole (a right-
# positioned officer line like "ADDITIONAL REGISTRAR" must not be truncated).
ADV_COL_X = 415   # advocate column left edge (words at/after this are the advocate)
SNO_COL_X = 60    # an item row's serial number sits in the far-left margin
# The case number has its OWN column (x ~ 60-180) between the serial number and the parties
# (x >= 185). A long number wraps onto the next row of that column ("SLP(Crl) No." / then
# "18858/2026"), and the registry SECTION code sits under it ("II-E", "XVI-A", "PIL-W").
# Owner, Oct 2026: notes need the exact petition number, so the whole column is gathered
# per item and the section codes dropped.
CASE_COL_X = 180
SECTION_RE = re.compile(r"^(?:[IVXL]{1,5}(?:-[A-Z]{1,2})?|PIL(?:-W)?|[IVXL]{1,5}[A-Z])$")
ITEM_SNO_RE = re.compile(r"^[0-9]{1,4}(?:\.[0-9]{1,3})?[.\)]?$")
ADV_SNO_RE = re.compile(r"^([0-9]{1,4}(?:\.[0-9]{1,3})?)[.\)]?$")  # same, capturing the number


_NUM = r"\d{1,7}(?:\s*-\s*\d{1,7})?\s*[/-]\s*(?:19|20)\d{2}"
_TYPE = r"(?:[A-Za-z][A-Za-z.()&]*\.{0,3}\s?){1,4}?"
CASE_NO_RE = re.compile(
    rf"(?:Connected\s+)?{_TYPE}(?:No(?:s|\(s\))?\.?\s*-?\s*)?{_NUM}"
    rf"(?:\s+in\s+{_TYPE}(?:No(?:s|\(s\))?\.?\s*-?\s*)?{_NUM})*", re.I)


_HAS_NUM = re.compile(r"\d{1,7}(?:-\d{1,7})?\s*[/-]\s*(?:19|20)\d{2}")


def _serial_wraps(prev_sno, prev_case_words, prev_key, key, first_word):
    """The serial column is narrow too: "39.11" can print as "39.1" / "1" (and "102." / "2" in
    Regular lists). A row starting with a bare number right after a "Connected" sub-item row
    that has no case number yet is the rest of THAT serial, not a new item."""
    return (prev_sno is not None and "." in prev_sno and key - prev_key <= 9
            and not _HAS_NUM.search(" ".join(prev_case_words))
            and re.fullmatch(r"[0-9]{1,3}", first_word or "") is not None)


def _case_text(words):
    """Words of the case-number column -> one clean number, e.g. 'SLP(Crl) No. 18858/2026'
    or 'CONMT.PET.(C) No. 21/2026 in C.A. No. 2004/2019'. Section codes, notes ("[FRESH")
    and the digital-signature stamp that can sit in that column are left out."""
    t = " ".join(w for w in words if not SECTION_RE.match(w))
    t = re.sub(r"\s+", " ", t).strip()
    m = CASE_NO_RE.search(t)
    if m:
        num = m.group(0)
        num = re.sub(r"(No(?:s|\(s\))?\.)\s*-?\s*(?=\d)", r"\1 ", num)
        num = re.sub(r"\s*-\s*(?=\d)", "-", num)
        return num.strip()
    # no number at all (rare): keep a leading "Connected" / case type only
    m = re.match(r"(?:Connected\s+)?[A-Za-z][A-Za-z.()&]*(?:\s+No(?:s|\(s\))?\.)?", t)
    return m.group(0) if m else ""


def pdf_to_column_text(data):
    """Rebuild the PDF text, dropping the advocate column from item rows only.
    Returns None if word-level extraction isn't available (caller falls back to
    pdf_to_text). A court header resets to header mode (coram kept whole); the
    first serial-numbered row switches on item mode (advocate column dropped).
    In item mode the CASE-NUMBER column is gathered over all the rows of an item and
    written whole on the item's first line ("6 SLP(Crl) No. 18858/2026 AMIT MITTAL"),
    so a number that wrapped onto the next row is never lost."""
    try:
        import pdfplumber
    except Exception:
        return None
    try:
        out = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                rows = {}
                for w in page.extract_words(use_text_flow=True):
                    rows.setdefault(round(w["top"] / 2), []).append(w)
                in_items = False
                item = None          # {"idx": line index, "sno": str, "case": [words], "party": str}

                def close():
                    if item is not None:
                        num = _case_text(item["case"])
                        out[item["idx"]] = " ".join(x for x in (item["sno"], num, item["party"]) if x)

                for key in sorted(rows):
                    ws = sorted(rows[key], key=lambda w: w["x0"])
                    full = " ".join(w["text"] for w in ws)
                    if REG_RE.search(full) or COURT_RE.search(full) or CJ_RE.search(full):
                        close(); item = None
                        in_items = False           # a court header — coram follows
                    elif HEADER_SKIP.search(full):
                        out.append(full); continue  # page-header boilerplate; the item carries on
                    elif ws[0]["x0"] < SNO_COL_X and ITEM_SNO_RE.match(ws[0]["text"]):
                        in_items = True            # a serial-numbered item row
                        if item is not None and _serial_wraps(item["sno"], item["case"], item["key"], key, ws[0]["text"]):
                            item["sno"] = item["sno"] + ws[0]["text"]          # "39.1"+"1" -> "39.11", "102."+"2" -> "102.2"
                            item["case"] += [w["text"] for w in ws[1:] if w["x0"] < CASE_COL_X]
                            more = " ".join(w["text"] for w in ws[1:] if CASE_COL_X <= w["x0"] < ADV_COL_X)
                            if more: item["party"] = (item["party"] + " " + more).strip()
                            item["key"] = key
                            continue
                        close()
                        item = {"idx": len(out), "sno": ws[0]["text"], "key": key,
                                "case": [w["text"] for w in ws[1:] if w["x0"] < CASE_COL_X],
                                "party": " ".join(w["text"] for w in ws[1:] if CASE_COL_X <= w["x0"] < ADV_COL_X)}
                        out.append("")
                        continue
                    if in_items:
                        if item is not None:
                            item["case"] += [w["text"] for w in ws if SNO_COL_X <= w["x0"] < CASE_COL_X]
                            item["key"] = key
                        out.append(" ".join(w["text"] for w in ws if CASE_COL_X <= w["x0"] < ADV_COL_X))
                    else:
                        out.append(full)
                close()
        return "\n".join(out)
    except Exception as e:
        print("  column extraction failed:", e)
        return None


# an item number, optionally a sub-item ("37" or "37.1"). "37.1 Connected .."
# sub-items are captured as their own keys so the clerk can enter either the
# main item or a specific sub-item.
ITEM_LINE_RE = re.compile(r"^([0-9]{1,4}(?:\.[0-9]{1,3})?)[.\)]?\s+(.+)$")
# Regular (F_J) lists number connected matters differently from Misc: the main
# item is "102 SLP(Crl) No. ..." and each connected matter is written as
# "102. Connected <PARTY>" followed by a line whose leading number is the
# sub-index, e.g. "2 SLP(Crl) No. 8718/2021" -> sub-item 102.2. We must capture
# every one of these so a clerk entering item 102.2 gets its cause title.
CONNECTED_RE = re.compile(r"^([0-9]{1,4})\.\s+Connected\s+(.+)$", re.I)
SUBINDEX_RE = re.compile(r"^([0-9]{1,3})\b\s*(.*)$")


# An advocate's name + code that slipped into the party column at the END of a respondent line
# ("UNION OF INDIA AND ORS. AMRISH KUMAR- 2986 [R-1],"). Up to three name words, never a word
# that belongs to a party ("ORS.", "OF", "INDIA", …), followed by "- 1234".
_ADV_WORD = r"(?!(?:ORS|ANR|ETC|LTD|LIMITED|OF|AND|THE|INDIA|STATE|UNION|GOVT|CO)\b)[A-Z][A-Z']*"
ADV_TAIL_RE = re.compile(rf"\s+(?:{_ADV_WORD}\s+){{0,2}}{_ADV_WORD}-\s?\d{{3,4}}\s*(?:[\[,].*)?$")


def parse_courts(text):
    """Text of one list PDF ->
       {court(str): {coram, total, fresh, items:{item(str): case-line}}}.
    The item line carries the case number + parties, so the app can auto-fill a
    matter's title from just court + item."""
    courts = {}
    cur = None
    in_header = False
    pending = None      # (court, item) awaiting a "Versus" respondent
    await_resp = False
    pending_conn = None # a "N. Connected <party>" awaiting its sub-index next line
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if HEADER_SKIP.search(line):      # page-header boilerplate — never data
            continue
        court = None
        m = REG_RE.search(line) or COURT_RE.search(line)
        if m:
            court = m.group(1)
        elif CJ_RE.search(line):
            court = "1"
        if court is not None:
            cur = court
            courts.setdefault(cur, {"coram": "", "total": "", "fresh": "", "items": {}})
            # collect the bench only until we have it; page headers repeat the
            # court + coram on every page, so re-collecting would duplicate it.
            in_header = not courts[cur]["coram"]
            continue
        if cur is None:
            continue
        tm = TOTAL_RE.search(line)
        if tm and not courts[cur]["total"]:
            courts[cur]["total"] = tm.group(1)
        fm = FRESH_RE.search(line)
        if fm and not courts[cur]["fresh"]:
            courts[cur]["fresh"] = fm.group(1)
        # Regular-list connected matter: "102. Connected <party>" — the sub-index
        # is on the following line; record the party and wait for it.
        cm = CONNECTED_RE.match(line)
        if cm:
            in_header = False
            pending_conn = {"main": cm.group(1), "party": cm.group(2).strip()}
            continue
        if pending_conn is not None:
            sm = SUBINDEX_RE.match(line)
            if sm:
                key = pending_conn["main"] + "." + sm.group(1)
                caseline = (sm.group(2).strip() + " " + pending_conn["party"]).strip()
                if key not in courts[cur]["items"]:
                    courts[cur]["items"][key] = re.sub(r"\s+", " ", caseline).strip()[:70]
                    pending = (cur, key); await_resp = False
                pending_conn = None
                continue
            pending_conn = None   # next line wasn't a sub-index — abandon
        # an item line — record its number -> petitioner side (first occurrence
        # only; page-header repeats won't overwrite). The respondent is captured
        # from the line after "Versus" so the title reads "Petitioner vs Resp".
        im = ITEM_LINE_RE.match(line)
        if im and re.search(r"[A-Za-z]{3}", im.group(2)) \
                and (re.search(r"\bNo(?:s|\(s\))?\.", im.group(2)[:60]) or re.match(r"Connected\b", im.group(2), re.I)):
            in_header = False
            it = im.group(1)
            if it not in courts[cur]["items"]:
                courts[cur]["items"][it] = re.sub(r"\s+", " ", im.group(2)).strip()[:110]
                pending = (cur, it); await_resp = False
            else:
                pending = None
            continue
        if pending is not None:
            if re.match(r"^versus$", line, re.I):
                await_resp = True
                continue
            if await_resp and re.search(r"[A-Za-z]{3}", line) \
                    and not re.match(r"^[\[{(]", line):   # skip [CAVEAT] etc.
                resp = re.sub(r"\s+", " ", line).strip()
                # an advocate that slipped into the party column: "… AND ORS. AMRISH KUMAR- 2986 [R-1],"
                resp = ADV_TAIL_RE.sub("", resp).strip()[:60]
                pc, pit = pending
                courts[pc]["items"][pit] += " VERSUS " + resp
                pending = None; await_resp = False
                continue
        if in_header:
            if is_coram(line):
                piece = re.sub(r"\s+", " ", line).strip()
                courts[cur]["coram"] = (courts[cur]["coram"] + " " + piece).strip()[:200]
            else:
                in_header = False
    for c in courts.values():
        if not c["total"]:
            c["total"] = str(len(c["items"]))   # SC lists have no total line
    return courts


# --- Advocate-on-Record capture -------------------------------------------------
# The AoR sits in the advocate column (x >= ADV_COL_X). Party names, case numbers,
# IA descriptions and the bench are ALL to the LEFT of that column, so by taking
# only x >= ADV_COL_X words nothing "nearby" can leak into the name (owner's hard
# requirement Jul 2026). We then validate every value is a bare name.
VERSUS_ONLY_RE = re.compile(r"^versus$", re.I)
# Words that mean it is NOT an AoR name — a header/officer/party/bench/IA token.
ADV_NAME_BAD = re.compile(
    r"REGISTR|COURT|BENCH|HON'?BLE|JUSTICE|PETITIONER|RESPONDENT|\bADVOCATE\b|"
    r"VERSUS|MATTER|HEARING|\bNOTE\b|SNO|CASE\s*NO|IA\s*NO|DIARY|EMAIL|"
    r"SUBMISSION|JUDGMENT|AMICUS|IN-?PERSON", re.I)


def _clean_adv(s):
    s = re.sub(r"\[[^\]]*\]", " ", s)                       # drop [R-1], [INT], [PET] ...
    s = re.sub(r"\([^)]*\)", " ", s)                        # drop (AMICUS CURIAE), (NP) ...
    s = re.sub(r",?\s*\bADV(?:OCATE|\.)?\b", " ", s, flags=re.I)   # drop the role word
    return re.sub(r"\s+", " ", s).strip(" ,.;-")


def _valid_adv(s):
    """STRICTLY an advocate / firm NAME: letters plus . , & / ' - and spaces only,
    short, no digits, and none of the party/case/bench/officer words."""
    if not s or len(s) > 60 or not re.search(r"[A-Za-z]", s):
        return False
    if re.search(r"[0-9]", s):
        return False
    if ADV_NAME_BAD.search(s):
        return False
    if len(re.sub(r"[A-Za-z .,&/'\-]", "", s)) > 1:        # stray non-name chars -> reject
        return False
    return True


# One advocate entry in the advocate column, as the SC prints it:
#   "MUKESH KUMAR MARORIA- 2324 [R-1], [R-2], [R-3]"   (name - AoR code [parties])
#   "DAKSH KADIAN AC"                                  (amicus curiae)
#   "PETITIONER-IN-PERSON" / "APPLICANT-IN-PERSON"
_NAME = r"[A-Z][A-Z.'&@/() ]*?[A-Z.)]"
ADV_CODED_RE = re.compile(rf"({_NAME})\s*-\s*(\d{{1,5}})\s*((?:\[[^\]]*\][\s,]*)*)")
ADV_AC_RE = re.compile(rf"({_NAME})\s+AC\b\s*((?:\[[^\]]*\][\s,]*)*)")
ADV_INPERSON_RE = re.compile(r"\b(PETITIONER|APPLICANT|RESPONDENT|APPELLANT)-IN-PERSON\b")


def _adv_entries(text):
    """The advocate column of ONE side of ONE case -> [{n: name, p: "R-1, R-2", tag?}].
    Only the NAME is kept — the AoR code, party tags and separators are never part of it."""
    t = re.sub(r"\s+", " ", text or "").strip()
    out, taken = [], []
    def tags(s):
        return ", ".join(x.strip() for x in re.findall(r"\[([^\]]*)\]", s or "") if x.strip())
    for m in ADV_CODED_RE.finditer(t):
        name = re.sub(r"\s+", " ", m.group(1)).strip(" ,.-")
        name = re.sub(r"^(?:AND|&)\s+", "", name)
        if _valid_adv(name):
            e = {"n": name, "p": tags(m.group(3))}
            if "CAVEAT" in e["p"].upper():
                e["tag"] = "caveat"
            out.append(e); taken.append(m.span())
    for m in ADV_AC_RE.finditer(t):
        if any(a <= m.start() < b for a, b in taken):
            continue
        name = re.sub(r"\s+", " ", m.group(1)).strip(" ,.-")
        name = re.sub(r"^.*\]\s*,?\s*", "", name)            # never a tag before it
        if _valid_adv(name):
            out.append({"n": name, "p": tags(m.group(2)), "tag": "amicus"})
    for m in ADV_INPERSON_RE.finditer(t):
        out.append({"n": m.group(1).title() + " in person", "p": "", "tag": "in-person"})
    return out


def parse_advocates(data, real_items):
    """{court: {item: {pet, resp, petAll, respAll}}} — every advocate of each side, read from
    the advocate column only (x >= ADV_COL_X), so nothing from the party/number columns can
    leak in. Petitioner side = the item's rows up to "Versus"; respondent side = the rows
    after it, up to the next item — including names that wrap onto the next row and items
    that run onto the next page. `pet`/`resp` = the first real AoR of that side (the one
    the counsel field is filled with); `petAll`/`respAll` = all of them with their parties."""
    try:
        import pdfplumber
    except Exception:
        return {}
    raw = {}           # court -> item -> {"pet": [text], "resp": [text]}
    st = {"court": None, "item": None, "side": "pet", "pend": None}

    def commit():
        """The serial row seen last becomes the current item (decided one row late, because
        the next row may be the rest of a wrapped serial such as "39.1" / "1" = 39.11)."""
        p = st["pend"]; st["pend"] = None
        if p is None:
            return
        c, sno = st["court"], p["sno"].rstrip(".")
        if c in real_items and sno in real_items[c]:
            st["item"] = sno; st["side"] = "pet"
            raw.setdefault(c, {})[sno] = {"pet": [x for x in p["at"] if x], "resp": []}
        else:
            st["item"] = None

    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                rows = {}
                for w in page.extract_words(use_text_flow=True):
                    rows.setdefault(round(w["top"] / 2), []).append(w)
                for key in sorted(rows):
                    ws = sorted(rows[key], key=lambda w: w["x0"])
                    left = [w for w in ws if w["x0"] < ADV_COL_X]
                    lt = " ".join(w["text"] for w in left).strip()
                    at = " ".join(w["text"] for w in ws if w["x0"] >= ADV_COL_X).strip()
                    if HEADER_SKIP.search(lt):
                        continue                     # page header — the item carries on
                    m = REG_RE.search(lt) or COURT_RE.search(lt)
                    hdr = m.group(1) if m else ("1" if CJ_RE.search(lt) else None)
                    if hdr is not None:
                        if hdr != st["court"]:       # a new court: start afresh
                            commit(); st["court"] = hdr; st["item"] = None
                        continue                     # same court repeated on a new page: carry on
                    if st["court"] is None:
                        continue
                    if left and left[0]["x0"] < SNO_COL_X and ADV_SNO_RE.match(left[0]["text"]):
                        case_w = [w["text"] for w in left[1:] if w["x0"] < CASE_COL_X]
                        p = st["pend"]
                        if p is not None and _serial_wraps(p["sno"], p["case"], p["key"], key, left[0]["text"]):
                            p["sno"] = p["sno"] + left[0]["text"]; p["case"] += case_w; p["at"].append(at); p["key"] = key
                            continue
                        commit()
                        st["pend"] = {"sno": left[0]["text"].rstrip(")"),   # keep a trailing "." ("102." + "2" = 102.2)
                                      "case": case_w, "key": key, "at": [at]}
                        continue
                    if st["pend"] is not None:
                        p = st["pend"]
                        if not VERSUS_ONLY_RE.match(lt) and not _HAS_NUM.search(" ".join(p["case"])):
                            p["case"] += [w["text"] for w in left if SNO_COL_X <= w["x0"] < CASE_COL_X]
                        if VERSUS_ONLY_RE.match(lt) or key - p["key"] > 9 or _HAS_NUM.search(" ".join(p["case"])):
                            commit()
                        else:
                            p["at"].append(at); p["key"] = key
                            continue
                    item = st["item"]
                    if not item:
                        continue
                    if VERSUS_ONLY_RE.match(lt):
                        st["side"] = "resp"
                        if at:
                            raw[st["court"]][item]["resp"].append(at)
                        continue
                    if at:
                        raw[st["court"]][item][st["side"]].append(at)
            commit()
    except Exception as e:
        print("  advocate extraction failed:", e)
    clean = {}
    for c, its in raw.items():
        for it, rec in its.items():
            pe, re_ = _adv_entries(" ".join(rec["pet"])), _adv_entries(" ".join(rec["resp"]))
            d = {}
            first = lambda lst: next((e["n"] for e in lst if e.get("tag") not in ("amicus", "in-person")), "")
            if first(pe): d["pet"] = first(pe)
            if first(re_): d["resp"] = first(re_)
            if pe: d["petAll"] = pe
            if re_: d["respAll"] = re_
            if d:
                clean.setdefault(c, {})[it] = d
    return clean


def upcoming_days(n):
    ist = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    days, d, step = [], ist.date(), 0
    while len(days) < n and step < n * 2 + 4:
        if d.weekday() < 5:
            days.append(d.strftime("%Y-%m-%d"))
        d += datetime.timedelta(days=1)
        step += 1
    return days


def n_matters(items):
    """Count only serially-numbered matters. Connected matters are captured as
    sub-items ("4.1", "102.2") so a clerk can look them up, but the court lists
    them UNDER their main item — they are not separate serial matters, so they
    must NOT inflate a court's total/main/supp counts (Court 5's 30 matters were
    reading 32 because of two connected sub-items)."""
    return sum(1 for k in items if "." not in k)


def build_for_date(date_str, prev_day=None, prev_sizes=None):
    """Returns (lists_found, lists, sizes, reused). Probes every list URL with a
    1KB ranged GET first; if the sizes all match the previous run, the previous
    parse is reused wholesale — no PDF is downloaded."""
    sizes = {}
    for human, variants in LIST_TYPES.items():
        for suffix, variant in variants:
            s = probe_size(DAILY_BASE.format(date=date_str, suffix=suffix))
            if s:
                sizes[suffix] = s
            time.sleep(0.15)
    if prev_day is not None and sizes == (prev_sizes or {}):
        return prev_day.get("lists_found", []), prev_day.get("lists", {}), sizes, True
    lists_found, lists = [], {}
    for human, variants in LIST_TYPES.items():
        merged = {}
        for suffix, variant in variants:
            if suffix not in sizes:
                continue
            data = fetch_pdf(DAILY_BASE.format(date=date_str, suffix=suffix))
            if not data:
                continue
            text = pdf_to_column_text(data) or pdf_to_text(data)  # drop advocate column
            if not text.strip():
                continue
            lists_found.append("{} ({})".format(human, variant))
            parsed = parse_courts(text)
            advs = parse_advocates(data, {c: set(parsed[c]["items"]) for c in parsed})
            for court, info in parsed.items():
                # a supplementary list ADDS matters to the same court — union the
                # items (do NOT replace, or the main list's items are wiped, e.g.
                # court 1's item 30 vanished behind the supp's items 46-51). Keep
                # the main bench; only fill coram/fresh from supp if main lacked it.
                # Track how many of the court's matters came from main vs supp so the
                # printout can show the breakup ("Main 50 · Supp 10").
                ex = merged.setdefault(court, {"coram": "", "total": "", "fresh": "",
                                               "items": {}, "advocates": {}, "main": 0, "supp": 0})
                before = n_matters(ex["items"])
                ex["items"].update(info.get("items", {}))
                # count only the NEW serial matters this list added (not sub-items)
                ex[variant] = ex.get(variant, 0) + (n_matters(ex["items"]) - before)
                # merge the AoR names for this court's items (don't overwrite a name
                # already captured from the main list with an empty from the supp)
                for it, ad in advs.get(court, {}).items():
                    cur = ex["advocates"].setdefault(it, {})
                    if ad.get("pet") and not cur.get("pet"):
                        cur["pet"] = ad["pet"]
                    if ad.get("resp") and not cur.get("resp"):
                        cur["resp"] = ad["resp"]
                    for k in ("petAll", "respAll"):
                        if ad.get(k) and not cur.get(k):
                            cur[k] = ad[k]
                if not ex.get("coram") and info.get("coram"):
                    ex["coram"] = info["coram"]
                if not ex.get("fresh") and info.get("fresh"):
                    ex["fresh"] = info["fresh"]
        # SC lists carry no total line — total is the merged serial-matter count
        for c in merged.values():
            c["total"] = str(n_matters(c["items"]))
        if merged:
            lists[human] = merged
    return lists_found, lists, sizes, False


def main():
    dates = [sys.argv[1]] if len(sys.argv) > 1 else upcoming_days(WINDOW_DAYS)
    print("Checking dates:", ", ".join(dates))
    prev = {}
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:
        pass
    # If the parser was upgraded since this file was written, discard the cached
    # parses so every date is re-parsed with the new logic (otherwise a fixed
    # parser never reaches dates whose PDFs haven't changed size).
    stale_parser = prev.get("parser_version") != PARSER_VERSION
    if stale_parser and prev:
        print("Parser version changed ({} -> {}) — forcing a full re-parse."
              .format(prev.get("parser_version"), PARSER_VERSION))
    prev_by, prev_src = ({}, {}) if stale_parser else (prev.get("by_date", {}), prev.get("sources", {}))
    by_date, sources = {}, {}
    for date_str in dates:
        lists_found, lists, sizes, reused = build_for_date(
            date_str, prev_by.get(date_str), prev_src.get(date_str))
        if sizes:
            sources[date_str] = sizes
        if lists_found or lists:
            by_date[date_str] = {"lists_found": lists_found, "lists": lists}
            ncourts = sum(len(v) for v in lists.values())
            print("  {}: {} list(s), {} courts{}".format(
                date_str, len(lists), ncourts, "  [unchanged — reused]" if reused else "  [FETCHED]"))
    # Nothing new anywhere -> leave the file untouched so the workflow commits
    # nothing and Pages doesn't rebuild. (generated_at = time of last CHANGE.)
    if prev and not stale_parser \
            and json.dumps(by_date, sort_keys=True) == json.dumps(prev_by, sort_keys=True) \
            and json.dumps(sources, sort_keys=True) == json.dumps(prev_src, sort_keys=True):
        print("No change since last run — output left untouched.")
        return
    result = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "parser_version": PARSER_VERSION,
        "window": dates,
        "by_date": by_date,
        "sources": sources,
        "note": "Per-court bench + per-item case line from the SC published lists. "
                "Drafting aid only — the court's published list is authoritative.",
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("Wrote {} — {} day(s) with lists.".format(OUTPUT_FILE, len(by_date)))


if __name__ == "__main__":
    main()
