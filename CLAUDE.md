# SD Chamber — Claude Code handover

Chamber-management PWA for a Supreme Court senior advocate's chamber. Save this
file as `CLAUDE.md` in the repository root — Claude Code reads it automatically.

## What this app is

A work-allocation and cause-list tool **between the clerk and the juniors**.
The senior advocate is deliberately NOT a user (role removed by owner decision).

## Brief files in Dropbox (Oct 2026)

Owner: link Dropbox (his own 2 TB personal plan) for case files, like ASD's OneDrive.
Decided: **App folder** access only (Dropbox/Apps/<app name>/ — nothing else in his
Dropbox is reachable, enforced by Dropbox itself) and **one folder per brief**.

- **Gatekeeper** = Cloudflare Worker `sd-chamber-files` (URL hardcoded in the app as
  `FILES_GATEKEEPER`, account subdomain `sdentertainmentservices`). Source in
  `files-gatekeeper/worker.js` + `SETUP.md` — **gitignored, pasted by hand** (same rule as
  CourtReach's worker: server code is not published). Holds the Dropbox refresh token in
  KV (`dbx_refresh`, `dbx_access`, `dbx_account`, `oauth_state:*`). Secrets
  `DROPBOX_APP_KEY` / `DROPBOX_APP_SECRET`; project, admin email and allowed origin are
  constants at the top of the worker (keep `ADMIN_EMAIL` in step with `CHAMBER.adminEmail`).
- **Who is asking:** every request carries the Firebase ID token (`auth.idToken()`); the
  worker verifies it (Google JWKS, RS256, project `sd-chamber-1aa78`) and reads the
  caller's own `users/{uid}` with THEIR token (rules allow any signed-in read) — so no
  Firebase key in the worker. Roles mirror firestore.rules: admin (email or role) /
  manage (clerk, pa) may upload + delete / active members may list + open. Only admin may
  connect/disconnect. Endpoints POST `/api/{status,connect,disconnect,list,link,upload,delete}`,
  GET `/callback`. Upload streams through (X-Folder / X-File-Name headers, ≤95 MB),
  `mode:add, autorename:true` — never overwrites. Opening/sharing = Dropbox temporary links
  (4 h). Paths are one segment each, `..`/slashes refused.
- **App:** `openBrief` has a **Files** section (`loadBriefFiles`). The folder name is fixed
  once on first upload as `brief.dropboxFolder` (`briefFolderName`: "chamberNo - title", or
  "title (id5)" with no number) so renames never strand files; `_mergeBriefInto` carries it
  to the keeper. Deleting a brief does NOT delete its folder. Status is cached 5 min **per
  uid** (a bug caught in testing: a colleague signing in after Staff inherited Add/Remove).
  `window.open` happens inside the tap, then the link is filled in — or iPhone blocks it.
  DEMO has an in-memory stand-in (`_demoFiles`). No firestore.rules change (Staff already
  have full brief update; the folder name is the only new field).
- **Tested:** 39 gatekeeper checks in the browser with genuinely RS256-signed tokens and a
  fake Dropbox (roles, expired/tampered/wrong-project tokens, inactive/outsider refusal,
  path guards, Unicode names → ASCII-escaped Dropbox-API-Arg, pagination, missing folder,
  CORS incl. preflight, single-use OAuth state); app flows in demo at desktop + 375 px.
- **LIVE since 7 Oct 2026.** Owner completed SETUP A–C: Dropbox app **"SD Master Case
  File"** (so files live in **Dropbox/Apps/SD Master Case File/**), Cloudflare worker
  `sd-chamber-files` with KV + both secrets, and connected from the app. Verified from
  outside: home page, 401 without sign-in, CORS for the app origin, KV-backed callback guard.

## Conference note = the owner's own note format (Oct 2026)

`makeNoteDocx({b, heading, paras})` copies his sample "Alan Chung v. HDFC Bank Dictated Note":
"Supreme Court of India" · the case number written out (`scCaseLine`: SLP(C) → "SLP (Civil)
No.", C.A. → "Civil Appeal No." …; diary only → "Diary No.…") · petitioner ⇥ "...Petitioner(s)"
/ "versus" / respondent ⇥ "...Respondent(s)" (`causeParties`; Appellant for appeals; plural
when "Ors/Anr"; small words lower-cased) · "Note dated DD.MM.YYYY" (Instructions: "Instructions
dated …") bold underlined · Word numbered list (ListParagraph, decimal, 720/360), blank paras.
Garamond 14, A4, margins 851/1134/567/1134, page number top right. NOTHING else (no serial,
no conference line). Notes taken in the app become the first numbered paragraphs.

## Read saving — Firestore free quota ran out (Oct 2026)

The Spark plan allows ~50k reads/day; on 7 Oct it ran out ("Quota exceeded" on every read).
Symptom: Files refused every non-admin as "not an active member" — the gatekeeper's read of
users/{uid} failed (429) and only the admin passes by email. Cuts made:
- **Device copy**: `initializeFirestore(... persistentLocalCache(persistentMultipleTabManager))`
  (falls back to getFirestore). Sign-out = signOut → terminate → clearIndexedDbPersistence →
  reload, so a shared computer keeps nothing.
- `db.watchCollection(path, cb, order, where)` → `cb(rows, {fromCache})`, with
  includeMetadataChanges so the server answer always follows the cached one.
- **Automatic writers act only on server data**: `_briefsLoaded/_dsLoaded` (→ syncRegister,
  selfMigrateMine, mergeDuplicateBriefs, matchAwaitingListings) and `_usersFresh`
  (repairActiveFlags) are set only by non-cache snapshots. NEVER let a background rewrite of
  daysheet `entries` run on cached data (see the Firestore write-hazard memory).
- `notifs` filtered to `uid == me.uid`; `confstatus` to `date == today` (`watchConfToday`,
  re-subscribed when the date changes).
Still advised: Blaze plan (keeps the 50k/day free; ~₹5 per 100k beyond) + a budget alert.

## Registers on phones (Oct 2026)

All phone rules sit in one `@media (max-width:600px)` block ("registers on phones"):
- **Brief register**: page title only (no big heading), admin tools folded into one
  "Register tools" sheet (`#rgToolsBtn`), steps note hidden, filter chips one scrolling line;
  each brief is a compact row (`.rg-card` grid: serial · title/numbers/next listing + "N
  earlier" (`nextLine`) · Files). Tap the row to open. Tablets (601–1100) show the full
  listing dates in the card instead (`.rg-card-lst`).
- **Day sheet**: toolbar = date with ‹ › day steppers (also on desktop) + five icon buttons
  with short labels (`.l-long`/`.l-short`); narrower numbering rail.
- **Leave**: register first, then a one-line-per-person tally. **Chamber workload** islands
  become one line per colleague; Weekly/Monthly/Yearly full width. Credit register table
  padding tightened to fit 375 px.

## Phone bar by role · Files tab (Oct 2026)

- Bottom bar on phones (`mobileTabs()`, applied in `paintChrome`): **Staff (clerk/pa)** —
  Calendar · Day sheet · Files; **colleagues** — Calendar · Day sheet · Briefs · Files;
  admin/Senior unchanged (Calendar · Board · Day · Briefs · More). A phone user on a tab
  outside their set is sent to the Calendar. Desktop sidebar unchanged.
- **Files tab** (`tab-files`, `renderFilesHome`): search any case, or pick from today's day
  sheet / (colleagues) My cases / recently updated. Each row: **Add** (a `<label>` around a
  file input so the phone's picker opens on the tap itself → `openFiles` then
  `addPapersForm`) and **Share** (opens the full-page Files, where each paper has Share).
- Admin "Download case list" (register) exports the register as JSON — used to match the
  owner's OneDrive folders; 37 cases' papers were copied into Dropbox from it (see memory).

## Files as a full page · minimal calendar · start-up safety net (Oct 2026)

- **Files is a page, not a pop-up**: `renderFilesSheet` still uses openSheet but marks the
  overlay `.ov-full` and the sheet `.sheet-full` (fills the screen, safe-area aware), a
  "← Back" at the top, and pushes a history entry `{fv:1}` so the browser/phone Back leaves it.
  `fvLeave()` decides where Back goes: `_fvRet` (set by `wireFilesBtns` — screen underneath
  when opened from a tab, the brief when opened inside the brief sheet; the calendar popup
  sets "Back to <date>"), else the brief.
- **Calendar minimal** (owner: "minimalistic but should convey cases listed and conferences"):
  each date = number (+ holiday / Senior-away label), then two quiet lines — "● 4 cases"
  (dot coloured by load) and "conf icon 2 conf."; phone shows the numbers only. Month line:
  "22 cases listed · 2 conferences · 3 days Senior away". No titles in the cells — the date
  popup (unchanged register) carries the detail.
- **Start-up safety net** (owner's iPhone showed a white page): a plain, non-module script in
  <head> records window errors; if 12 s in neither sign-in nor the app is visible, it shows
  "The app didn't start" with the error + user agent, a **Reset and reload** button
  (`__resetApp`: unregisters the service worker, clears caches, reloads with ?fresh=) and
  "Just try again". Cause of the iPhone white page NOT yet known — get the screenshot.

## Conference Word button · no "likely now" · case folders for all · calendar re-presented (Oct 2026)

- **Conference card**: the Dictation/Instructions bar is gone; ONE blue "W" button sits
  beside Start/Pause/End (also on an ended conference) and opens a small menu — Dictation /
  Instructions (bold) — `_confWordMenu`, closed by any outside click. Files moved to the
  card's who-row. "likely now" (time-inferred highlight) removed. Manual conferences now keep
  their `briefId` and `juniorUids` (they were dropped in `conferencesOn`, so a conference added
  against a case never offered Files/Word). `renderNow` clears the top bar.
- **Create case folders** (register, admin): `allFoldersForm` — mkdir every numbered case's
  folder (4 at a time; existing folders untouched — the gatekeeper's mkdir ignores a conflict);
  unnumbered cases are routed to "Number old cases by date", whose default is now **keep the
  numbers already given** when any exist (never renumber existing folders unasked).
- **Calendar**: month summary (matters listed, conferences, court days, Senior away); each
  date island shows a load bar + count badge, the first 3 matters as `court·item  title`
  (mine bold, next-date-only italic), "+N more", conference and on-leave chips; today is a
  filled circle; past days dimmed. Phone: number + count + chips only. `dayItems(iso)` =
  day-sheet entries + briefs whose nextDate is that day but not yet on the sheet.
- **Day popup** (`dayDetail`) is a register: Ct/Item/time | case (title opens the brief,
  serial/case/diary nos., bench, counsel + colleagues, remarks) | big Files button; then
  "Next date fixed — not yet on the day sheet", conferences (Files when tied to a case), on
  leave, actions, and a collapsible "Day settings" (Senior availability, holiday). Files opened
  from here have "Back to <date>" (`_fvRet`).

## Trimmed: Done buttons, Note for office, both imports · listing dates · video links (Oct 2026)

- **Removed on the owner's word** (code deleted, not flagged off): the day sheet's Done/Undo
  and the "Brief" button beside it (the case title now opens the brief — `.ds-open`), the
  "Note for office" chits from court (calendar + day sheet panels, `notes[]` no longer read;
  old data left alone), the Word-causelist import and the paste-the-cause-list import, and the
  register's "Sync listings" button (the register syncs itself — `maybeSyncRegister`).
  Remaining day-sheet buttons are big: Files (big) / Edit / Remove (`.ds-act`).
- **Brief register — no Status column.** In its place "Dates of listing" (`listingsCell`,
  `briefListings(id)` = every day-sheet date the brief appears on, indexed once per dsAll
  snapshot — NB `listingsOf(uid)` is a different, colleague-side function): upcoming dates
  bold with Ct/Item (plus the brief's own next date), then earlier listings as small chips,
  "+N earlier" expands (`_lstOpen`, `wireListingExp` via bindClicks). Disposed shows as a tag.
- **Conference video link**: confstatus/{key}.video = {url,by,at} (members may already write
  confstatus — no rules change). Whoever runs the conference pastes the Zoom/Meet/Teams link
  (or the whole invite — `videoUrlFrom` keeps just the https link); everyone sees a
  "Join Zoom/Google Meet/Teams" button on the card, even collapsed. Change / Copy / Remove.

## My work rebuilt · Sort by on every register · conference Word files (Oct 2026)

- **My work** (`renderMyWork`, colleagues): navy hero (greeting, date, 4 tiles — need your
  answer / active cases / hearings next 7 days / open directions, roster standing), "Needs your
  answer" (`.act-card`: takeover accept/decline, acknowledge/object, Files), "Coming up — next
  7 days" (`.up-row` date block + Ct/Item + Files; from `activeListings` + live nextDates),
  directions, and **My cases** = the SAME `briefListHTML(list,{edit:false})` as the Brief
  register with search, Live/Concluded/All chips and Sort by (default next hearing).
- **`briefListHTML`** — the register's table + cards extracted so both screens share them.
- **Sort by** (`sortSel(key,options,def)` / `sortVal` / `wireSort`, remembered per person in
  localStorage `sd-sort:<key>`): Brief register + My work (`BRIEF_SORTS`, `sortBriefs`: serial
  ↓/↑, title A–Z/Z–A, next hearing (`nextHearingOf`), date came in ↓/↑), Files screen
  ("papers": by number = grouped/islands; name/newest/oldest/largest = flat list), Saved cause
  lists ("causelists": by the date IN the name, newest/oldest), Leave register ("leave": date
  ↓/↑ by month, or one block per colleague), credit register ("credit": date ↓/↑, matter A–Z,
  credit ↓).
- **Conference → New Word file** (`newConferenceNote(key, kind)`): on a conference tied to a
  case (`c.briefId`) and editable by the person, "Dictation" / "Instructions" create
  `N<serial>[.n] <Short title> - Dictated Note|Instruction Note - DD.MM.YYYY.docx` in the case
  folder (ensureCaseFolder first; ASD .1/.2 rule via planNumber), built in-browser by
  `makeNoteDocx` (stored ZIP with real CRC32; Garamond 14 via styles docDefaults, A4 pgSz,
  heading/serial/numbers/KIND/conference line, numbered paragraphs = the conference's notes so
  far), then `editInWordForm` (Open in Word / Download / Replace with edited version).
- Tested in demo: My work (hero, sections, Files buttons, sort/filters, remembered sort),
  register name/hearing sorts, leave + credit sorts, a listing with a 6 pm conference → the
  card's Dictation → N001 … Dictated Note … in "Wipro Ltd. v ITO (001)", rendered by
  docx-preview with the note carried in.

## Deleting a wrong entry + closing serial gaps (Oct 2026)

Owner: "Make provision for a wrong entry and deletion option … the app should automatically shift
the numbering and also rename the folders accordingly." = his own filing practice (ASD notes:
every vacancy was closed by renumbering the cases after it).
- `removeCaseDialog(b, onRemove)` replaces the plain confirm for deleting a CASE — from the
  brief ("Delete this matter") and from the day sheet when the listing created the case
  (`dsDel` alsoBrief). Shows "edit instead if only details are wrong"; the deleted case's
  folder MOVES to `_to_delete/<folder> - deleted DD.MM.YYYY` (`moveFolderToDelete`, never
  deletes papers; time suffix on a same-day clash); then **Close the gap** (default; needs
  Dropbox reachable) or **Leave NNN unused**. The latest case: nothing moves, its number is
  reused.
- `closeSerialGaps()` / `gapPlan()`: an unbroken run from the LOWEST serial in use (a register
  starting at 101 keeps starting at 101); also separates serials used twice; per move updates
  chamberNo then `applySerialFolder` (folder + numbered papers renamed); up to 3 rounds to
  catch a case numbered meanwhile; finally `config/serial.next = top+1` (rules: the counter
  may go BACK only for canManage). Register shows "Numbering has gaps — close them"
  (`closeGapsForm`, Staff/admin); a duplicates merge that vacates a serial offers it too.
- Tested in demo: 001–004 entered, 002 deleted from the day sheet → 003/004 became 002/003
  with folders + papers renamed, next case 004; "leave unused" → gap chip → Close gaps fixed
  it; deleting the latest → number reused.

## Day sheet: match check, then number the new case (Oct 2026)

Owner: "every time a new case is added by way of day sheet it should be assigned a serial
number and … a serial numbered folder in the dropbox. The app should inform the person … of any
already case matching the cause title or the number or any sort of match. Once that match is
approved the case will not be numbered serially and be linked to the old serial number."
- `caseMatches({title,caseNo,diaryNo})`: same case no. (`_normCase`, ≥5) / same diary no. /
  same normalised title = STRONG; ≥2 shared significant words (`_sigWords`, dup stop-list)
  → "similar cause title" (Jaccard ≥0.5) or "parties in common". Top 6, strong first.
- **Add matter (`dsForm` f_save)**: the old silent `findBriefForListing` auto-link is gone for
  NEW cases. `askCaseMatch` (overlay `#cmOverlay` over the form) lists matches; a strong one is
  pre-chosen, a weak one must be chosen (Continue locked); "Back" returns to the form with
  nothing saved. Same case → listing linked, no number spent. New → brief created, then
  `numberNewCase` = `ensureCaseFolder` (serial via the transaction + Dropbox folder; folder
  deferred to first Files open if Dropbox is unreachable). Toast says "new case NNN, folder
  created" / "linked to case NNN". Editing a listing / "Existing matter" mode skip the check.
- **Word import**: each parsed matter gets `_cands` + `pick` (strong pre-picked, weak = must
  decide, none = new); a select per row; Add is disabled while any is undecided; new ones are
  numbered after the write.
- NOT changed: `syncRegister` (background repair that creates briefs for old unlinked
  listings — no person to ask; they get numbered on first Files open or by "Number old cases
  by date"), and "New brief" from the register (numbered on first Files open). Linking a
  listing to an old case that has no serial yet leaves it unnumbered (the by-date batch or its
  first Files open numbers it).
- Radio inputs in `.cm-opt`/`.dup-m` override the global `input{width:100%}`.
- Tested in demo: exact title match → linked, no number; brand new → 001 + folder; weak match
  → locked until chosen, Back keeps the form, New → 002; case-no + title match shown with
  reasons; Word import with exact/weak/none rows → decide-gate, linked + new 001/002.

## Serials v2 — numbered on first Files tap; old cases by date (Oct 2026, supersedes the Word-list import)

Owner: "Forget about the word files. The app will number a case with serial number only when
someone clicks on files button and there is no linked serial number folder for that case. For
the old cases … assign a serial number as per date. I dont want two cases to be assigned one
serial number so check for duplicates. Also once a serial number is created or assigned the
corresponding serial number folder has to be created in the dropbox."
- The Word serial-list import and "Number the rest" are REMOVED. `addBrief` no longer numbers.
- **`allocateSerial(id)`**: a Firestore TRANSACTION (`db.tx` — runTransaction in prod, a
  sequential emulation in DEMO) reads the brief + `config/serial {next}`, takes
  max(counter, local max+1) skipping any number visible on another brief, writes counter =
  n+1 and the brief's chamberNo + dropboxFolder together. Concurrent taps → Firestore retries
  one → different numbers. Rules: `config/serial` create by any approved member (next int ≥1),
  update only if next strictly increases.
- **`ensureCaseFolder(id)`** (opening Files, saving a paper, "Create its folder now"):
  allocate if no serial, record the folder, gatekeeper mkdir. Opening Files now numbers a case
  (owner's explicit choice — earlier "don't spend a number on a tap" guard reversed).
- **Number old cases by date** (admin, register; `numberByDateForm`/`runNumbering`): blocked
  by the duplicate check until reviewed or "They're all different — continue"; date =
  `caseCameOn(b)` = earliest of createdAt / assignedAt / assignHistory / first listing; mode
  "every case from 001" (default) or "keep numbers already given"; preview table; reserves
  the range first (`bumpSerialCounter(top+1)`) so concurrent taps can't collide; per case
  updates chamberNo then `applySerialFolder` (rename existing folder + the numbered papers in
  it, or mkdir). Admin hand-edit of a serial (brief form; non-admins can't type one) → unique
  check, counter bump, folder/paper rename.
- Tested in demo: new brief unnumbered; dup gate caught a real pair; 53 cases → 001–053 by
  date, unique, no gaps, folders; next taps → 054, 055 with folders; admin 055→060 renamed
  folder + F055→F060, counter 061; duplicate hand serial refused.

## Folders on demand (Oct 2026)

Owner: "If there is no folder for a case and I am clicking on the files button … it should
create a folder for that case with serial number and allow me to save the file in that folder
as colleague or staff." `ensureCaseFolder(id)`: gives the next serial if missing, records
`dropboxFolder`, then gatekeeper **/api/mkdir** (create_folder_v2, existing folder = fine).
Opening Files creates the folder ONLY for a case that already has a serial; a case without
one gets its serial on the first SAVE (addPapersForm) or on "Create its folder now" — merely
browsing must not spend serials before the owner's list is imported. firestore.rules: any
member may set `chamberNo` and `dropboxFolder` only while each is empty (hasOnly those +
updatedAt). Tested: gatekeeper 67/67; demo — Staff opening a numbered case → folder made;
colleague opening an un-numbered case → no number spent; colleague saving → serial + folder
+ correctly named paper; colleague "Create its folder now". Staff always had full paper rights.

## Colleague file rights, preview, Edit in Word, duplicates, cause-list save (Oct 2026)

- **Colleagues manage papers** (owner: "colleague to be able to add, delete, edit files"):
  the gatekeeper now lets every ACTIVE member upload / rename / replace / delete (connect &
  disconnect stay admin; serials and renaming a brief's FOLDER stay canManage). App gate:
  `canEditPapers(st)` (`st.member` from /api/status). A colleague's first paper on a brief
  writes `dropboxFolder` → needs the **firestore.rules** clause "any approved member may set
  `dropboxFolder` (+updatedAt) only while it is unset" (local rules file updated; OWNER MUST
  PASTE it). Until pasted, that first upload shows a clear "ask Staff" message.
- **Preview** = ASD Quick Look (`previewPapers`/`qlShow`, `#qlOverlay`): pdf.js 3.11.174
  with Range requests through **GET /api/content** (gatekeeper streams Dropbox
  /files/download, passes Range, exposes Content-Range/Accept-Ranges; a 60-s per-token user
  cache so range bursts don't re-read Firestore), docx-preview 0.3.5 (+JSZip) for Word,
  images as blobs; prev/next through the papers in shown order; Esc/arrows. Tap a paper's
  name/icon to preview.
- **Edit in Word** (`editInWordForm`): with Dropbox, people without their own Dropbox can't
  have Word save back in place, so: Open in Word (`ms-word:ofe|u|<4-h link>`) or Download →
  edit/save → **Replace with edited version** = upload with `X-Mode: overwrite` (same name &
  number; Dropbox keeps the prior version). Every other upload stays add + autorename.
- **Rename / renumber** (`renamePaperForm`): change "what it is" or the letter (new letter
  → next number of that kind via `planNumber`, .1/.2 rule); numbers "Not yet numbered"
  papers dropped in from Dropbox.
- **Find duplicates** (admin, `duplicatesForm`, register "Find duplicates" + a 3-step banner
  "1 Find duplicates → 2 Import serial list → 3 Number the rest"): union-find over same
  case no. / same diary no. / same normalised title / similar title (≥2 significant shared
  words, Jaccard ≥0.6). Admin ticks the keeper (suggested = most listings → colleagues on
  it → oldest; NOT "has a serial", since new briefs get one automatically); merge = existing
  `_mergeBriefInto` per dup, lowest serial first so it carries to a serial-less keeper; a
  dup's Dropbox folder is MOVED INTO the keeper's folder as an older sub-folder first.
  "Not duplicates" → `config/dupreview.pairs` (admin write, config catch-all).
- **Cause list → Dropbox** (`saveCauselistToDropbox`): day-sheet "Save to Dropbox" builds
  the same jsPDF as Share, uploads to top-level `Causelists/Causelist DD.MM.YYYY
  (Weekday).pdf` with overwrite (re-saving a day replaces it). "Saved" opens the virtual
  folder `@Causelists` (`VIRTUAL_FOLDERS`, `fvTarget()`): list newest first, preview/open/
  share/remove, no add.
- Tested: gatekeeper 64/64 (colleague rights, inactive/outsider still refused, Range
  pass-through, preview path guard/401/403/404, overwrite vs add, user cache); demo: dup
  review (3-way group, correct keeper, serial carry-over + vacancy warning, papers moved),
  colleague add/rename/replace/remove, previews (2-page PDF via pdf.js, PNG, real .docx via
  docx-preview), Edit-in-Word steps + replace, cause-list save ×2 → one file, previewed;
  375 px.

## Serial numbers, ASD-style register + Files screen (Oct 2026)

Owner: "full redone of the brief register… learn from ASD… files button on all the briefs…
all cases numbered serially and carry that serial for the files… presentation of the files
learned from ASD… the day sheet should have a prominent files button against all the cases."

- **Serial = `chamberNo`** (the field the register was already ordered by; no new field, no
  rules change). `serialNum(b)`, `pad3`, `nextSerial()` = highest in use + 1 (plus a session
  counter `_serialIssued` so a batch of creations in one tick can't share a number).
  **Every brief is created through `addBrief(data)`**, which fills the next serial when blank
  — 4 creation sites (syncRegister, dsForm f_save, Word import, briefForm). Legal-aid and
  conference-credit briefs (`isCaseBrief` false) are NOT cases and get no serial.
  `serialClashes()` → red-ish warning chips in the register; `serialTakenBy()` blocks saving
  a brief with a serial already on another; a non-admin can't change a serial once given.
- **Naming = the owner's ASD filing rules** (iCloud "Filing system notes for Claude Code"):
  folder `<Short title> (NNN)` (`caseFolderName`, "vs" → "v", OneDrive/Dropbox-unsafe
  characters stripped, ≤80 chars); papers `<L>NNN[.n] <Short title> - <what>.<ext>`,
  L ∈ N note / L list of dates / S submissions / C compilation / F file received / D draft.
  A lone paper of a letter has no sub-number; when a second arrives the first is RENAMED to
  `.1` (gatekeeper `/api/move`, never overwrites) and the new one is `.2` (`planNumber`).
  `brief.dropboxFolder` fixes the folder name at first upload; if title/serial later differ,
  the Files screen offers **Rename folder** (manage roles). Papers are NOT renamed when a
  title changes (they keep their names; `paperInfo` falls back to the full remainder).
- **Files screen** `openFiles(briefId, sub)` (wide sheet, `.fv-*` CSS ported from ASD):
  path crumbs, search with highlight, kind ISLANDS (count + latest date) + "Latest papers",
  grouped list by letter when a kind is chosen, coloured file-type icons (W/PDF/IMG/X/FILE),
  number badges, Open / Share (4-h link) / Remove (manage), older sub-folders browsable
  (gatekeeper `sub`, ≤3 deep). Add papers → `addPapersForm`: per file a letter (auto F for
  PDF/images, D for Word) + "what it is", live preview of the final name. No serial → notice
  + "Give it serial NNN" (manage). `filesBtn(briefId)` + `wireFilesBtns` (called from
  `bindClicks`) put a Files button on every register row/card, every day-sheet listing
  (rail card first action + a "Papers" column in the desktop table), and the brief detail
  (summary card "N papers · latest …" + big Open files).
- **Register** `renderBriefs` rebuilt: header (files · active · next serial), warning chips
  (N without a serial → filter; serial used twice), search (serial/title/diary/case/AoR),
  filter chips with counts (Active/Listed/Mine/Urgent/Incomplete/No serial/Disposed/All),
  newest serial first; table ≥1100px (Serial · Matter · Next hearing [day-sheet court/item
  via `nextListingOf`] · Colleagues · Status · Papers), cards below (2-up on tablets).
- **Serial list import** (admin, `serialImportForm`): the owner's Word list is SENSITIVE, so
  it is read IN THE BROWSER (`readSerialList`: our own ZIP + WordML reader — every table row
  with a number cell, plus "12. Title" paragraphs; dates/header rows skipped) and never
  uploaded; only approved serials are written. Matching = ASD lesson: only an EXACT
  `_normTitle` match to a single brief is pre-ticked; repeated numbers locked; a brief that
  already has another serial, or a number already on another brief, is flagged unticked;
  the rest picked from a shared datalist. Optional "add entries not in the app as disposed
  files" (`fromSerialList:true`). **Number the rest** (admin) gives remaining briefs the next
  numbers oldest-first — warns to import the list first.
- **Gatekeeper** gained `/api/move` (file or whole-folder rename, manage, `autorename:false`
  so it refuses rather than overwrites) and `sub` paths (`X-Sub` on upload) + `dirs` in list.
  51/51 browser checks with real RS256 tokens. **Needs re-pasting into Cloudflare** — until
  then a second paper of the same letter fails (old worker has no /move).
- Tested in demo (desktop 1024/1440 + 375 px): register, import with a generated test .docx
  (header skipped, table + paragraph entries, exact-match ticks, duplicate lock, clash flags,
  apply + add-missing → next serial 106), Files add/renumber (F101 → F101.1 + F101.2), batch
  of 4, no-serial → give serial, folder rename after a title change, colleague = open/share
  only, day-sheet buttons. test.html NOT regenerated this time (it is publicly served and
  leaks colleagues' names — owner's decision pending).

## Notes from court + Senior's calendar (Sep 2026)

- **Notes from court** (`courtNoteForm` / `courtNotesPanel` / `wireCourtNotes`, block
  `NOTES FROM COURT`): the owner's two Staff split the job — one is in court all day and
  hears which briefs have come in (but never touches a computer), the other sits in the
  office with the computer and time but hears nothing. Cases went unentered. The
  court-side Staff taps **Note for office** (Calendar topbar + Day-sheet topbar, phone-
  first: day defaulting to tomorrow, court, item, counsel, free text — nothing mandatory
  but the day), the office-side Staff sees it at once (Calendar home panel "From court —
  N to enter (all days)", a `cal-chip.note` "N to enter" on the day cell, and that day's
  sheet), and **Enter this matter** opens the ordinary `dsForm(null, preset)` pre-filled;
  the note is struck ONLY when the listing is really saved (`preset.onSaved`), so closing
  the form leaves it waiting. **Done** strikes without entering; delete is author/admin.
  A note may be sent for a Senior-away day (that IS how the office learns a brief came
  in) — the form warns, the panel labels it, and "Enter this matter" is withheld because
  `f_save` would refuse the listing anyway. Stored as `notes[]` on the day's own
  `daysheets/{date}` doc (same canManage() rule — **no rules change**); done notes are
  kept, not deleted. Staff-facing only (`canManage()`); juniors never see them.
  `pushNotif` to the other Staff/admin on send. Both a DEMO-verified end-to-end (send →
  chip → Enter → prefilled → save → struck) and phone-width layout.
- **Senior's calendar** (`seniorCalendarForm` / `seniorAwayRanges` /
  `printSeniorCalendar`, block `SENIOR'S CALENDAR`): Calendar topbar → **Senior's
  calendar** (canManage). A RANGE form — From/To, Reason (`SENIOR_REASONS`: Out of
  station / In another court / Personal / Unwell / Conference-event / Vacation / Other) +
  Details — writes `config/senioravail` for each day as the ONE STRING every reader
  already expects, `"Reason — details"` (same doc, same rule, no rules change; day
  detail, day-sheet notice, calendar cell, `seniorOff()` gate and CourtReach's sync all
  untouched). Below it, upcoming marked days grouped into ranges with a Remove (writes
  null per day, the existing tombstone convention). **Print** opens the same print-window
  pattern as `printCauseList`: A4 portrait, 2-column month grids for the next 3/6/12
  months or a whole calendar year, SC holidays (imported `holidays`) tinted, vacation
  (`isPartial`) tinted, weekends grey, Senior-away days hatched red with the day struck
  and the reason clamped to 3 lines, per-month "N days away", legend + printed-on foot.
  **Sep 2026 redesign (owner: "professional calender printout with proper colour
  presentation")**: `print-color-adjust:exact` so the colours actually print; branded
  head (SD seal, name, "Availability calendar", period, prepared-on); navy/gold weekday
  band; filled colour blocks with a coloured top bar per kind (red away / purple holiday /
  amber vacation / grey weekend), the away day's number in a red disc; a red "N days not
  available" pill per month; layout follows the span (≤3 months → one per page, ≤6 → two,
  a year → 2×2 with the reason category alone in the small cells); a closing **register**
  table of every away range (dates · days · reason · details); confidential foot.
  Verified headlessly (jsc with stubs) + rendered on a service-worker-free port — the
  SD-Chamber SW serves the app shell for ANY path on its origin, so preview files must
  be served elsewhere.
  The per-day toggle in `dayDetail` stays for one-offs. sw.js `chamber-shell-v26→v27`.

## Review-pass changes (Jul 2026, most recent)

- **Roster includes not-yet-signed-in members equally** (`rosterQueue`): a
  colleague added but not logged in is ranked by workload like everyone (owner:
  login doesn't matter for assignment; a "pending:<email>" gets matters that
  migrate on first login). Only on-leave-today sinks. Row shows their load + "not
  yet signed in".
- **Leave register hard-deletes** (`renderLeave`): deleted entries are GONE, not
  struck-through (owner wanted a clean register). Delete → `db.remove`; the list
  filters `!l.deleted` so any existing soft-deleted rows also vanish.
- **Senior-unavailable = no additions** (owner's rule): `seniorOff(iso)` days block
  adding a day-sheet listing (`f_save`, import add) and a brief `nextDate`
  (`b_save`, `ob_next`), with a toast. The Day sheet hides Add/Import + shows a
  notice on those days. Calendar marks senior-away LOUDLY (`.sen-away`: red tint +
  red bar + "Senior away" tag), overriding the neutral day-kind styling.
- **Board nav label is dynamic** (`paintChrome()`): colleagues land on the
  personal `renderMyWork()` home, so their sidebar/mobile board item reads **"My
  work"**; Staff/admin keep **"Work board"**. Label matches the page.
- **New-brief assignment mode** (`briefForm()`): a `.seg` toggle — **Choose
  colleague** (the existing checklist, now with each person's active count) vs
  **Auto-assign** (roster engine, with a live `#autoPickName` preview of who it
  lands on). Save-time auto path reuses `pickNext()` + `advancePointer()` and
  records `assignHistory` mode `auto`/`forced`, identical to the standalone
  `autoAssign()`. `asgnMode` var drives it; `directed` is manual-only.
- **Roster fairness view** (`renderRoster()`): a colleague sees a
  `.roster-standing-banner` ("You're #N in the rotation · next up in K turns ·
  carrying … active … lifetime") and a **You** tag + `.is-me` accent on their
  own row. Banner is colleagues-only (Staff/admin aren't in the rotation).
- **Demo seed** (`make-test.py`): dropped the fake "Sample holiday/Sample
  vacation" clutter; seeds the real SC summer-vacation range via
  `config/vacation` so the preview shows true calm shading.

## Branding & onboarding copy (Jul 2026)

- **SD logo**: gold Fraunces "SD" with a hairline underline (echoes the app
  icon). `.sb-logo` in the sidebar masthead (gold on navy); `.brand-mark` =
  navy rounded tile w/ gold SD on the light auth + pending cards. Colour scheme
  unchanged (navy #101418 / gold #cbb682 institutional).
- **Onboarding relabelled** away from "invite / pre-approve" to just **"Add
  member"** (owner's call — Adith enters real members, no approval step in his
  head). The MECHANISM is unchanged: still `approvals/{emailLower}` claimed on
  first sign-in (the only credential-free way — Firestore users are uid-keyed).
  Button "Add member", panel "Members — awaiting first sign-in", form fields
  name/email/role/phone/joinedOn. Junior signs in with that email + "Set your
  password". Keep the approvals-doc plumbing; only the words changed.
- **Roster shows added-but-not-logged-in members** (`rosterDisplay()` merges
  role=junior approvals into the seniority list, tagged "awaiting first login",
  no loads). effectiveRoster()/assignment still use logged-in `users` only —
  a member with no uid can't be assigned/ack until they activate. The People
  directory (Chamber tab) stays alphabetical-by-role; the Roster is seniority.

## Terminology (Jul 2026 — display only)

The owner renamed the user-facing labels: **Clerk → "Staff"**, **Junior →
"Chamber Colleague"** (plural "Chamber Colleagues", shortened to "Colleagues"
where space is tight). The internal role KEYS are unchanged (`clerk`,
`junior`) — data, comparisons (`me.role==="junior"`), `juniors()`,
`juniorUid(s)`, `heldForClerk`, and the security rules all still use the old
keys. Only `ROLES` labels and rendered copy changed. Keep it that way; a key
rename would touch Firestore data + rules for no benefit.

## Roles & onboarding (Jul 2026 — load-bearing)

Three personas, split by a hard rule: **all TECHNICAL feeding is Adith's; the
clerk only does day-to-day operational input.**
- **admin** (Adith Deshmukh, `adithdeshmukh@gmail.com`): members, their contact
  details + joining dates, email pre-approval, matter weights, holiday calendar.
  Recognised BY EMAIL (`CHAMBER.adminEmail`) as well as by `role:"admin"`, so
  his first-ever login is admin with no chicken-and-egg — **never remove the
  email check**. `isAdmin()` / `canAdmin()` gate every technical surface.
- **clerk/pa**: matters (briefs), conferences, senior availability, day sheet,
  assignment. `canManage()` = admin+clerk+pa. Clerk is NOT technically adept —
  no member management, no weights, no holidays surface at all.
- **junior**: self-onboards. Adith pre-approves their email
  (`approvals/{emailLower}` with role+details) → junior visits the app, uses
  **"Set your password"** (`auth.signUp` = createUserWithEmailAndPassword) →
  `onAuthStateChanged` claims the approval, creates their `users/{uid}` at the
  approved role, deletes the approval. No manual approval step. An un-invited
  sign-in lands as `pending` (the "Not approved yet" screen). Demo has no real
  auth, so the Chamber tab exposes a **"Simulate sign-in"** button on each
  invite to exercise the claim end-to-end.
- **Colleague has LEFT the chamber (`retireColleague`, Jul 2026):** the member
  editor (`roleForm`, admin-only, not on self/admin) has a danger-zone **"Colleague
  has left the chamber"** button. It keeps their RECORD (user doc + name; every
  disposed matter and past day sheet untouched, so their name still shows on the work
  they did) but removes them from everything LIVE: sets `active:false` + `leftOn`
  (the existing `active!==false` filters already drop them from roster, snapshot,
  assignment and all colleague pickers/People), and DETACHES them from every
  NON-disposed brief (assignedTo/ackBy, clears their creditClaim/reassignReq) plus
  today/future day-sheet listings + conferences — so their live credit stops and a
  co-colleague inherits the FULL share (a solo active matter falls back to
  unassigned → reassign from the board). The confirm dialog counts solo-vs-shared
  active matters. A muted **"Former members"** panel on the Workload snapshot lists
  `active===false` members (record kept) and reopens them in `roleForm`, where
  re-checking "Active member" brings them back — so removal is reversible.
  jsc-verified (solo→unassigned, shared→co-colleague inherits, disposed record kept,
  claim cleared) + live demo (removed a colleague: island/People/roster/picker drop,
  Former-members shows them, solo matters freed, no errors). Distinct from the old
  soft "Active member" checkbox, which only hid them and left them attached to live
  matters (stale credit dilution). sw.js `chamber-shell-v24→v25`.
- **Restore-credit PANEL removed (Jul 2026, owner):** the amber "Restore credit —
  N removed identities" panel on the Workload-snapshot view kept nagging for a
  colleague who was deleted and re-added, so it was deleted from `renderSnapshotBody`.
  `remapAssignee(oldId,newUid)` is RETAINED (call it from the console for a one-off
  fix); `orphanAssignees()`/`remapTargets()` are now dead. The board's separate
  "assigned to an inactive member — needs reassignment" notice is unrelated and
  still shows. Original mechanism, for reference:
- **Restore credit for a re-added colleague (Jul 2026):** because members are
  id-keyed, deleting a colleague (e.g. wrong email) and adding them back mints a
  NEW id — their old matters still name the OLD id, so their credit disappears.
  Nothing is destroyed: `orphanAssignees()` finds assignee ids referenced in
  briefs / day sheets / leaves that are neither a current member nor a live invite
  (`currentIdSet()`), and an **admin-only "Restore credit" panel** on the Team →
  Workload snapshot view lets Adith map each orphan onto the right colleague.
  `remapAssignee(oldId,newUid)` rewrites assignedTo / everAssigned / ackBy /
  assignHistory(.uid+.by) / declinedBy / creditClaim across briefs, juniorUids on
  day sheets, and leaves.uid — deduping so a shared matter isn't double-counted.
  Works for a deleted invite (`pending:wrongEmail`) or a removed uid. jsc-verified
  (detect + remap + dedup, no false positives) + live UI test (add invite → assign
  → delete invite → restore onto a colleague). `remapAssignee` updates the local
  `briefs`/`dsAll`/`leaves` optimistically before the Firestore echo, so the panel
  clears at once instead of lingering a round-trip (owner: "still flashing").

## Display board — MOVED to its own repo (Aug 2026)

`board.html` and everything exclusive to it (`board-dev/`, `board-sw.js`,
`board-manifest.json`, `pace-collector.html`, `PUSH-SETUP.md`,
`make-board-test.py`) were split out into their own repo, **`DisplayBoard`**
(owner: "protect the app since it is being distributed on large scale"), with
full git history preserved via `git filter-repo`. See
`../DisplayBoard/CLAUDE.md` for the display-board documentation (Regular-101+
handling, passover logic, chat, full-screen approach flash, closed-phone push,
alerts, the pace collector, etc.) — it is NOT duplicated here anymore, to avoid
the two copies drifting out of sync.

**What's still shared between the two repos:** the Firestore DATA
(`sd-chamber-1aa78`) — board.html reads the SAME `daysheets/{date}` this app
(index.html) writes, which is the whole point of the live sync. The cause-list
fetcher (`fetch_causelist.py` + `.github/workflows/causelist.yml`) and
`court-updates.json` stay HERE too (this app's day-sheet auto-fill still needs
them) — DisplayBoard has its own independent copy, lightly rebranded, not a
dependency on this repo.

## Conference credit + credit register (index.html, Jul 2026)

- **Editing a listing's colleague REPLACES on the brief, not unions (owner fix
  Jul 2026):** `f_save` reconciles the linked brief's `assignedTo` with the
  listing's `juniorUids`. A NEW listing (idx null) ADDS its colleague; EDITING a
  listing removes whoever that listing named before (`jrsOf(e)` swapped out) and
  adds the new pick, so swapping A→B moves the WHOLE credit to B instead of
  crediting `[A,B]` split. Colleagues assigned to the file elsewhere are kept.
  The old code unioned + gated on length only, so a 1→1 swap silently split
  credit. jsc-verified (5 reconcile cases) + live (day-sheet edit A→B → brief
  detail shows B alone). `assignedTo` stays the single source of truth for credit
  (linked listings' juniorUids don't feed credit; only `b.assignedTo` does).
- **Manual duplicate merge (`mergeDuplicateForm`, owner Jul 2026):** the
  auto-merge only collapses briefs that share a case/diary number (≥8 norm chars)
  or an EXACT normalised title — so a real duplicate slips through when one copy
  is missing its number AND the titles differ (a different respondent captured, a
  truncation, a typo). Loosening the auto-merge to partial-title matching was
  REJECTED — it would wrongly merge distinct matters between common parties
  ("Union of India vs A" / "…vs B"). Instead, the brief detail (canManage) has
  **"This is a duplicate — merge into another file"** → a searchable picker of
  every other brief; choosing the keeper runs the SAME `_mergeBriefInto(keep,dup)`
  as the auto-merge (repoints listings + conferences, unions colleagues, carries
  missing details, removes the dup, credit counted once). Live-verified (pick →
  confirm → count −1, dup gone, no errors). Use this for the "listed twice, no
  shared number" cases the auto-merge can't safely infer.
- **A day-sheet conference LINKED to a matter (`c.briefId`) earns NO ½ credit**
  (owner fix Jul 2026): the colleague was already credited when the matter was
  listed, so `conferenceCreditsOf` skips any conference with a `briefId`. Only a
  STANDALONE conference (no linked matter) still earns the split ½.
- **Duplicate-brief prevention + merge (owner Jul 2026):** a matter listed in two
  different weeks must appear ONCE in the register with both listing dates, not as
  two briefs. `findBriefForListing` dedups on input by case number (`_normCase` —
  drops the "No." token so "SLP(C) No. 18036/2026" == "SLP(C) 18036/2026", keeps the
  TYPE so C.A.≠SLP), diary number, then normalised title (`_normTitle` — strips
  vs/versus + "& Ors./Anr." + punctuation). `mergeDuplicateBriefs()` (runs once per
  admin/clerk session in `maybeSyncRegister`) collapses EXISTING duplicates that
  share a case/diary number (>=8 normalised chars = a real unique number, so it can
  never merge two different matters): keeps the oldest, repoints the newer's
  listings + conferences, unions assignees, carries missing details, deletes the
  dup; toasts "Merged N…". jsc-verified (key collapse + full merge mechanics; C.A. vs
  SLP same-number NOT merged).

- A standalone / preliminary / strategy conference (no listed matter, or a matter
  not yet listed) earns **½ credit**, split equally. Modelled as a brief with
  `confCredit:true` (status `disposed`, `nextDate`=conference date). `shareFor`'s
  base is `0.5` for `confCredit` (so solo ½, shared ¼). Added via the **Conference**
  button next to **Legal aid** on the Briefs topbar (`conferenceCreditForm`), and
  it counts in lifetime + the period tally like any matter (worth ½).
- **Ad-hoc conference credit (preferred path):** `confForm` (day sheet → Add
  conference) has a **colleague multi-select** — a conference with colleagues set
  earns ½ credit split, stored on `daysheet.conferences[].juniorUids`.
  `conferenceCreditsOf(uid)` scans ALL day sheets' conferences (any date) so adding
  a colleague to a PAST conference credits it at once; a conference with no colleague
  earns nothing. Wired into `lifetimeCount` + `loadInWindow` + `creditLedger`. (The
  earlier Briefs "Conference" button / `confCredit` brief was removed as a duplicate;
  its credit math stays for backward-compat with any already created.)
- **Credit register is a full SECTION, not a popup** (owner: "I want a proper
  section redirect"): clicking a Workload-snapshot island sets `_regUid` and
  `renderTeam` swaps the whole Team view for `registerSectionHtml` — a **real
  `<table>`** with fixed columns (`.reg-table`: # 38px · Matter/conference flex ·
  Date 112px · Credit 70px, zebra rows, tfoot total), a back-to-Snapshot button, a
  Week/Month/Year toggle (`_regPeriod`), a big period total + a "N matters · N
  conferences" breakdown. `creditLedger(uid,period)` enumerates the SAME
  contributions as `loadInWindow`, so the register total and the island number match
  in display (both via `fmtPts`). jsc-verified (conf 0.5 / shared 0.25 / past dates;
  ledger==loadInWindow at display precision; week ≤ month ≤ year).
Priorities, in the owner's words:

1. **Primary:** work allocation and distribution among ~10 juniors
2. **Secondary:** clerk's ease in preparing the daily chamber cause list
3. **Third:** linking those two functions
4. **Ancillary:** linking assigned matters to their records (Drive links) accessible to all

Human context that shapes every decision: **Adith (the owner) runs the
infrastructure; the clerk is technologically challenged** — he can prepare a
cause list and send files on WhatsApp/email, nothing more. Every clerk-facing
flow must stay at that level: type court+item, click share. Everything is
shared within the chamber — no information walls between members (owner's
explicit instruction; the old senior-notes restriction was removed from both
UI and rules).

## Deployment state (as of handover)

- **Live app:** https://courtreach.github.io/SD-Chamber/
- **Repo:** `SD-Chamber` under GitHub user `courtreach`
- **Firebase project:** `sd-chamber-1aa78` (Auth email/password ON, Firestore
  in `asia-south1`, rules published — current version below)
- **firebaseConfig is baked into index.html** (public by design; security is
  in the rules): apiKey AIzaSyAagQ_-1LLvKtmsfJwSPJvURHWB-FkO-NQ, project
  sd-chamber-1aa78, appId 1:287957629475:web:9c7804acf3060c73abcf96,
  storageBucket sd-chamber-1aa78.firebasestorage.app
- **IMPORTANT divergence risk:** the owner edited `seniorName` directly on
  GitHub with the pencil editor. Any regenerated index.html from this codebase
  has `PASTE_SENIOR_NAME_HERE`. Before pushing a new index.html, read the live
  repo's current seniorName and carry it over, or you will clobber his edit.
- First clerk bootstrap (Firebase Auth user + Firestore role flip to `clerk`)
  was in progress at handover — verify a `users` doc with role `clerk` exists
  before assuming multi-user flows work.

## Files

| File | Purpose |
|---|---|
| `index.html` | Production app. `const DEMO = false;` + real firebaseConfig. |
| `demo.html` / `app.html` | Same code with `DEMO = true` — in-memory mock, seeded sample chamber, amber "View as" role switcher. No login. |
| `sw.js` | Service worker (Jul 2026): the app **HTML is NETWORK-FIRST** so a deployed change is live on the next open (cache is only the offline fallback); the heavy immutable libs — **Firebase SDK + fonts + Tabler icons are CACHE-FIRST** so mobile stays fast. NEVER caches Firestore/Auth/`court-updates.json` (live data). Registered from index.html head. `CACHE` now `chamber-shell-v9`. (`board-sw.js` — same pattern for the war room — now lives in the `DisplayBoard` repo.) NOTE: the previous stale-while-revalidate version made HTML one-open-behind (owner: "change is not live") — hence network-first HTML. |
| `manifest.json` | PWA manifest (navy #101418, maskable icons). Linked from index.html head. |
| `icon-192.png` / `icon-512.png` / `apple-touch-icon.png` | App icon: gold "SD" monogram in Fraunces on the sidebar-navy. Regenerate with `python3 make-icon.py` (Pillow + Fraunces TTF, self-downloading); never hand-transcribe base64. |
| `firestore.rules` | Security rules — **git-ignored by owner's decision (Jul 2026), kept only locally / in the Firebase console**, NOT hosted on GitHub. Recover the last committed copy with `git show f2073ff:firestore.rules`. Still the source of truth for what the console rules must be. |
| `test.html` | Real-chamber test build (owner's juniors + the 13.07.2026 paper list), regenerated by `make-test.py`. Never deploy it. |
| `make-test.py` | Rebuilds test.html from index.html after edits: `python3 make-test.py`. |
| `fetch_causelist.py` + `.github/workflows/causelist.yml` | Scheduled Action: fetch SC lists → per-court benches → commits `court-updates.json` (repo root). See the SC cause-list section + CAUSELIST-SETUP.md. Test the parser OFFLINE against saved PDFs; don't hammer the live site in dev. |

Single-file architecture is deliberate (owner deploys by uploading one file,
edits via GitHub pencil). Do not split into modules without his say-so.

## Architecture

One `<script type="module">`. Two-branch data layer selected by `DEMO`:

```js
db.watchCollection(path, cb, [orderField, dir]) -> unsub   // cb gets [{id,...}]
db.watchDoc(path, cb) -> unsub                              // cb gets {id,...}|null
db.set(path, data, merge) / db.add(path, data) / db.update(path, data) / db.remove(path)
db.now()            // serverTimestamp in prod; {_t: Date.now()} in demo
auth.onChange / signIn / signOut / setUser(demo only)
```

Demo branch: in-memory Map store + synchronous listeners + `seedDemo()`
(50 matters, deliberately skewed distribution, SC index for today, demo
eventualities). Prod branch: Firebase v10.12.2 ESM from gstatic CDN,
top-level await imports.

**Subscription lifecycle (fixed bug — do not regress):** `auth.onChange`
tears down ALL watchers (`unsub[]`, `dsUnsub`, `scUnsub`, `userDocUnsub`) and
re-boots per user via a `booted` flag inside the users/{uid} watchDoc callback.
The old code only booted once, so data went stale after user switches.

Timestamps are dual-format everywhere: demo `{_t: ms}`, prod Firestore
Timestamp. Read with `x?._t ?? x?.toDate?.()` patterns; keep both paths alive.

## Data model (Firestore)

- `users/{uid}`: name, email, phone (for WhatsApp nudges), role
  (`admin|clerk|pa|junior|pending`), active, joinedOn (ISO date — sets chamber
  seniority; juniors sort by it everywhere, roster order derives from it)
- `approvals/{emailLower}`: {email, name, role, phone, joinedOn, by, at} —
  Adith's email pre-approvals. Keyed by the LOWERCASED email so rules can
  recompute the key from `request.auth.token.email.lower()` and verify the
  claimed role. Consumed + deleted on that person's first sign-in.
- `briefs/{id}`: caseTitle, diaryNo ("12345/2026"), caseNo, matterType,
  appearingFor, aor, status (`received|assigned|prep|ready|conf|listed|disposed`),
  priority, directed, detailsAwaited (auto: no diaryNo AND no caseNo),
  nextDate/conferenceAt (ISO), assignedTo[], everAssigned[], ackBy[],
  assignedAt (ms), declinedBy[{uid,ground,note,at}], heldForClerk,
  assignHistory[{uid,at,by?,mode}], createdBy/At, updatedAt
  - subcollections `comments/{id}` + `files/{id}` EXIST in the rules but their
    UI (Files & Discussion in the brief detail) was **removed Jul 2026** (owner:
    file/note upload is a later phase). Rules left in place (harmless); re-add
    the brief-detail sections when that phase resumes. Current app scope: brief
    details, causelist, work distribution + roster only.
- `daysheets/{YYYY-MM-DD}`: {date, entries[], conferences[], updatedAt, updatedBy} —
  entries: {briefId?, caseTitle, courtNo, itemNo (free text — "MM" = mentioning),
  listType (one of CAUSELIST_TYPES: Miscellaneous/Regular/Chamber/Single Judge/
  Registrar/Curative & Review — keys the SC bench lookup), time (default
  "10.30"), bench (auto-filled from the SC causelist by court+type+date), counsel
  (briefing counsel, autofilled from brief.aor), juniorUids[], juniorUid (legacy
  = juniorUids[0]; keep writing both, read via `jrsOf(e)`), remarks, done}. conferences: {time, name, briefId?} —
  the paper's evening "Conferences and meetings" list; clerk board auto-suggests
  briefs whose conferenceAt falls on that date. One doc per day, last-write-wins
  (acceptable: one clerk + one PA). Modelled 1:1 on the clerk's real paper cause
  list (letterhead → matters with bench + "briefing counsel — chamber juniors" →
  conferences by time).
- `scindex/{YYYY-MM-DD}`: {date, entries[], loadedBy, at} — parsed SC list:
  {court, item, diaryNo, caseNo, title, raw}
- `availability/{uid_date}`: {uid, date, status:`available|incourt|half|leave`, note}
- `config/roster`: {pointer:int} — order is no longer stored (owner's Jul 2026
  decision): the roster IS seniority order from users.joinedOn, senior-most
  first; manual reordering was removed. Old docs' `order` field is ignored.
- `config/weights`: {matterType: int 1–9} — live matter weights, editable from
  the Roster tab (clerk/pa). Merged over DEFAULT_WEIGHT in code; absent doc =
  defaults. Covered by existing config/* rules — no rules change needed.
- `config/holidays`: {dateISO: name|null} — SC holidays/vacations, entered by
  the clerk from the Calendar (per-day via day detail, or the "Mark holidays /
  vacation" range tool; null = cleared, checked via `!= null`). Deliberately
  under config/* so existing rules cover it.
- `config/senioravail`: {dateISO: note|null} — days the SENIOR is not
  available (he is not a user; the clerk inputs this). Same null semantics,
  same config/* rules rationale.

## Calendar (home screen — owner's request, Jul 2026)

The default tab for everyone (`curTab="cal"`; sixth mobile tab). Month grid,
Monday-first, Fraunces day numerals. Weekends auto-shaded "Non-sitting";
holidays tinted warn-bg with the name; senior-away days flagged with a
user-off icon; today ringed in accent. Per-day chips: total active matters
with that nextDate (everyone), "N mine" (juniors only — their assignedTo),
"N conf" (from that date's daysheet doc — the whole `daysheets` collection is
watched as `dsAll` for this). Clicking a day opens a detail sheet: the holiday-name input is ADMIN-ONLY
(technical feeding), the senior-availability input is clerk/pa/admin; plus the
day's matters (clickable), conferences, and an "Open day sheet" jump that sets
dsDate and switches tabs. The "Mark holidays / vacation" range tool is admin.
SC holiday data is ENTERED BY THE CLERK (range tool for vacations) — do not
fabricate/hardcode holiday dates; a future autofetch from sci.gov.in could
populate config/holidays the way the cause-list Action populates scindex.

## Assignment engine (the heart — owner's primary purpose)

- `weightOf(brief)` = `Math.max(1, Number(b.weight)||1)`. Weight is an OPTIONAL
  per-brief field the STAFF sets on the brief form (owner's call Jul 2026 —
  the old matter-type weight table + config/weights + Roster-tab editor were
  removed). Blank = 1 (every matter counts equally). `hasWeight(b)` gates the
  "N×" chips so unweighted matters show nothing.
- `isImminent(b)`: nextDate within 0–4 days → that brief counts **double**
  in `activeLoad(uid)`. This is how "junior busy with a matter coming up"
  auto-repels new work.
- `lifetimeCount(uid)`: LIFETIME count — every brief ever assigned
  (everAssigned), disposed included, counted **1 each — NO weightage** (owner's
  decision Jul 2026: weightage is only for immediate distribution, not the
  career clock). `totalLoad` (the old weighted-lifetime fn) was removed.
- `pickNext(brief, exclude)`: eligible = effectiveRoster() (= seniority order)
  minus declinedBy minus on-leave-today. **Fair-distribution cap (Jul 2026,
  owner's rule):** anyone who has taken **≥ CATCHUP_MAX (2)** fresh matters in
  the last **CATCHUP_WINDOW_MIN (90 min)** is held out of the pool (unless that
  empties it), so a batch spreads instead of piling on the lightest person —
  `recentAssigns(uid)` counts non-disposed assigned briefs with `assignedAt`
  inside the window. **Ranking metric = the WORKLOAD SNAPSHOT (owner Jul 2026,
  changed from activeLoad):** the pool is ranked by (`loadInWindow(id, loadPeriod)`
  asc [least credit done this period — exactly the number on the Workload snapshot],
  then recentAssigns asc, then lifetimeCount asc, then turn-distance from
  `roster.pointer` asc) — "snapshot → recent → lifetime → turn". `loadPeriod` is the
  shared week/month/year toggle (default month), so whichever period is selected on
  the snapshot/roster is what assignment uses. The Roster tab is now a **live
  workload queue** (`rosterQueue()` — lightest snapshot first, leave-today + not-yet-
  logged-in sink to the bottom); `nextUpUid()` = `pickNext` for a generic undated
  matter, so the "Next up" marker never disagrees with the engine.
  **Leave-clash skip (Jul 2026, owner's rule):** the matter's hearing date
  (`brief.nextDate`, or the day-sheet listing date passed in) blocks any colleague
  on leave that day OR the day before — prep happens the day before, so leave on
  the 12th bars matters listed on the 12th AND 13th. `leaveClash(uid,hearingDate)`
  = `onLeaveOn(hearingDate) || onLeaveOn(dayBefore(hearingDate))`; with no date on
  the brief it falls back to `isSkippable` (on leave today). Every pickNext call
  site now passes the date (autoAssign/objection via `brief.nextDate`; day sheet
  via the listing date; brief form via `b_next`). jsc-verified + live (Vikram on
  leave 19th → skipped for a 20th matter, still fine for the 18th). **CREDIT vs
  ASSIGNMENT split on the leave window (owner fix Jul 2026 — REVERSED the earlier
  coupling):** ASSIGNMENT still uses the full `leaveClash` (on leave the listing day
  OR the prep day before → don't hand them the matter). But CREDIT follows actual
  PRESENCE ON THE LISTING DAY only — `presentSharers` / `shareForDate` zero a
  colleague's share ONLY if he's on leave THAT day (`onLeaveOn(date)`), NOT the day
  before. Rationale (owner): a colleague marked on a matter who was on leave merely
  the previous day still appeared and did the work, so the credit is his; only leave
  ON the listing day zeroes his share and redistributes it to whoever was present.
  This flows through `shareFor` → `activeLoad` / `lifetimeCount` / `loadInWindow`.
  Live-verified: on-leave-yesterday → credited; on-leave-today → 0, share to the
  present co-assignee.
- **Workload snapshot is a CALENDAR period (Jul 2026 fix), not a rolling ±window.**
  The Chamber-tab week/month/year tally (`loadInWindow`/`casesInWindow` via
  `periodRange`) attributes a matter to the calendar week (Mon–Sun) / month / year
  of its **listing date**, NOT by `assignedAt`. Old bug: a ±30-day "month" window
  from mid-July spanned into August AND counted by assign date, so a matter listed
  4 Aug showed in July's tally. Now: listed 4 Aug → counts only in August's
  week/month (and the current year); a matter with a July listing + an August next
  hearing counts once in each month (per appearance); an undated active matter
  counts in the current period. jsc-verified (10 cases) + live (week ≤ month ≤ year
  monotonic, drill-down works, no errors).
  So standing load decides WHO is next; the cap only limits the RATE of catch-up
  (a returning-light colleague gets ~2 then the rotation moves on, and keeps
  catching up in the next window). Proven with a jsc sim vs the real functions:
  burst 0-vs-5 → gets 2 not 6; 0-vs-20 → still capped at 2; equal loads → clean
  round-robin. If none eligible → **forced** assign to lightest-loaded non-leave
  member, `{forced:true}` (flagged toast). Auto-pick previews now show the pick's
  load ("Name · N active — lightest") for transparency.
- `autoAssign` sets assignedTo=[pick], status=assigned, resets `ackBy=[]`,
  stamps `assignedAt`, appends assignHistory, then `advancePointer()`.
- **Objections:** normal brief → auto-advance to next eligible (objector
  excluded per-brief via declinedBy), pointer advances. **Directed brief**
  (`directed:true`, "on Senior's direction") → NO auto-advance; sets
  `heldForClerk:true`; clerk's board shows a held notice with "Keep as
  assigned" (clears hold) or manual reassign. Directed assignment does NOT
  consume a roster turn but DOES count toward load.
- **Acknowledgment:** every (re)assignment starts unacked. Junior sees banner
  + "Acknowledge assignment" button; clerk sees "unseen · Nd" ageing on the
  board and per-assignee clock icons in the detail; WhatsApp "Nudge" buttons
  (see below).
- Manual assignment via briefForm keeps acks only for still-assigned juniors;
  new assignees need fresh ack; clears heldForClerk if team changed.
- Roster tab: fixed seniority order (joinedOn; no reordering), "Next up"
  marker, per-junior joined date + active load / total load / live / lifetime
  / objection counts, pointer reset, and the matter-weights editor (clerk/pa).

## Word-causelist import (index.html, Jul 2026 — REGRESSIBLE)

Reads the clerk's own daily-causelist **Word (.docx)** and lifts each matter into
the day sheet — court, item, briefing counsel (+ party), chamber colleague(s) and
conference times — so the clerk can keep preparing his familiar Word file and Adith
imports it in one step. **Fully isolated + removable** (owner: "if I don't like it,
regress"): everything lives in ONE block (search `WORD-CAUSELIST IMPORT`) gated by
`const WORD_IMPORT=true;` plus one button in `renderToday`. Set the flag false (button
vanishes) or delete the block to return to the exact prior state — **no schema/data
changes**; imported rows are ordinary day-sheet entries + briefs.

- **Reading .docx with NO external library:** a .docx is a ZIP of WordprocessingML.
  `_zipEntry` walks the ZIP central directory to `word/document.xml`, `_inflateRaw`
  inflates it with the platform `DecompressionStream("deflate-raw")` (Safari 16.4+/
  Chrome 80+ — fine on the clerk/Adith's phones), `_docxTable` parses it with
  `DOMParser` (namespaced `w:tbl/w:tr/w:tc/w:p/w:t`; a cell's paragraphs → `\n`
  lines). Hardened: stray `&` that isn't a valid entity is escaped before parse
  (real Word escapes them, but a macro/paste doc may not).
- **Clerk's layout (ground truth — matched to his real sheet):** table columns
  `Court/Item | Time | Case Name | Judges | Advocates Name | Total matter`.
  `Ct-1#28` → court 1, item 28. The Advocates cell: **line 1 = briefing counsel + a
  party marker** (`(R)`,`(P)`,`-P`,`R-2`,`P`… → `_wiCounsel` sets appearingFor
  Petitioner/Respondent); **the lines below = chamber colleagues**, `/`- or
  `,`-separated (`Adith D/Anshula`), each matched to a uid by `_wiMatchColleague`
  (first-name + initial fuzzy). Conferences (`2.30 - Nishant Patil`) are lifted and
  **linked to the matter whose counsel matches the name** (sets that entry's
  confTime); unmatched conferences become standalone daysheet.conferences rows (no
  colleague → no ½-credit, exactly like a plain counsel meeting).
- **Per-conference DATE (owner Jul 2026):** the clerk's flat conference list has no
  dates but the meetings span the eve-before and the day-of. The preview gives every
  conference a date picker (default = the listing day) plus two bulk buttons ("all →
  eve before", "all → day-of"). A linked conference's chosen date rides onto its
  matter's `confDate` (so the matter's conference lands on the right day); a
  standalone one is stored with that `date`. The day sheet already groups conferences
  by date, so a mixed set shows under separate day headings (e.g. Fri 24th + Sat
  25th). Verified live: moving two of the 13 confs to the day-before regrouped them
  under a 24 Jul heading while the rest stayed on 25 Jul.
- **Editable preview before any write** (`renderWiPreview`): every parsed matter with
  an include checkbox, counsel+party, conf time, matched-colleague chips (removable)
  and a "+ colleague" fixer for anything unrecognised; then "Add N to <date>".
  `applyWordImport` reuses `findBriefForListing` (links an existing register file by
  title, else creates one) — imported matters get credit/registered identically to
  hand-typed ones. Blocked on senior-unavailable days like every other add.
- Verified: jsc unit tests (counsel/party, colleague split, Ct-x#y, conf lines,
  fuzzy name-match — 24 cases) + **full end-to-end in the demo**: a generated .docx
  fed through the real ZIP→inflate→WordML→parse→preview→apply path produced 4 matters
  (correct court/item, multi-line titles, counsel+party, colleagues matched to demo
  users) and 5 conferences (4 auto-linked, 1 standalone), no console errors.
  `sw.js` cache `chamber-shell-v22→v23`.

## Cause list (owner's "nothing would beat this" feature)

Flow: SC list gets indexed once per day → clerk types **Court + Item** →
entry autofills (title/caseNo/diaryNo), matches the register (diaryNo exact
match first, then caseNo substring), pre-tags assignedTo[0] as junior; no
register match → added with remarks "Not in register". Duplicate court+item
refused. Entries auto-sort by court then item.

Index sources, in priority order:
1. `data/scindex-<date>.json` in the repo (committed by the GitHub Action) —
   fetched same-origin on Pages, flagged `fromRepo:true`, wins over Firestore
2. `scindex/{date}` Firestore doc, written by the in-app "Load SC list" paste
   modal (paste PDF text → `parseSCList()` → saves index AND offers
   checkbox-add of chamber matches)

`parseSCList(text)`: tracks `COURT NO.` headers; `^(\d{1,3})[.)]\s` starts an
item; block scanned for diary (`\d{3,6}[/-]\d{4}`), caseNo (prefix regex:
SLP|W.?P|C.?A|CRL.?A|T.?P|R.?P|M.?A|CONMT|CONT|ARB|CUR|DIARY), and
"X Versus Y" title. Best-effort; hardening against real PDFs is pending.

**Share** button (day-sheet toolbar, visible to all members once the sheet has
content) opens an editable plain-text preview in the clerk's own paper format —
`SENIOR NAME / SUPREME COURT (DAY) DD.MM.YYYY`, then per matter
`n) Ct-<court>#<item> — <time>` / title / `Bench: …` / `counsel — junior / junior`
/ `(remarks)`, then `Conferences and meetings:` with `time — name` lines — with
Copy / WhatsApp (`wa.me/?text=` on mobile, `web.whatsapp.com/send?text=` on
desktop, UA-sniffed) / mailto buttons acting on the edited text. This IS the
clerk's delivery mechanism; composer lives in `shareText()`/`shareDaySheet()`.
**Print** button (beside Share) — `printCauseList()` opens a print window in the
clerk's PAPER format: centred `SENIOR NAME` (big caps) + italic "Senior
Advocate", underlined `SUPREME COURT (DAY) DD.MM.YYYY`, then the six-column
table (Court/Item · Time · Case Name · Judges · Advocates Name · Total matter;
Advocates cell = briefing counsel over "/"-joined colleagues), then Conferences.
EB Garamond (Google Fonts) 14px, serif fallback. Print is triggered from the
PARENT after `w.document.fonts.ready` — no inline script in the written HTML.
Admin is a `canManage()` superset, so Adith can add matters + print like Staff.

## SC cause-list auto-fetch (Jul 2026 — owner's "enrich entered listings" model)

Ported+reworked from the ASD app's proven pipeline. Files: `fetch_causelist.py`,
`.github/workflows/causelist.yml` (hourly 08:00–23:00 IST Mon–Sat), output
`court-updates.json` at repo root, `CAUSELIST-SETUP.md`. The fetcher is
change-detecting: `probe_size()` does a 1KB ranged GET per list URL and reuses
the previous parse (stored `sources:{date:{suffix:size}}` in the output) unless
a size changed; identical results leave the file unwritten so the workflow
commits nothing (`generated_at` = time of last CHANGE). App side: a long-open
tab re-fetches court-updates.json on visibilitychange / Day-Calendar tab switch
when older than 10 min (`courtUpdatesAt`/`courtUpdatesStale`). **Model:** the scheduled Action can't read
Firestore, so it does NOT search for the chamber's matters (owner rejected the
ASD watchlist/name-discovery approach). It downloads the 6 SC list PDFs for a
rolling 8-weekday window and extracts, per (date → list-type → court), the
**bench (coram)** + total/fresh. Staff enter court/item/**listType**/date on the
day sheet; the app (`loadCourtUpdates` → `coramFor(date,type,court)` →
`cleanCoram`) auto-fills the authoritative bench and prints it. No watchlist.json.
Jul 2026 UPGRADE: the fetcher also stores `items:{itemNo: case-line}` per court
(case number + parties, ~96KB/day for ~1150 items). The Add-matter form now
takes just **court + item** as the primary inputs; `lookupCauselistItem(date,
court,item)` searches ALL list types (item-number ranges differ so court+item is
unique) and fills case title (`titleFromCauseLine`), list type, and bench.
Everything else on the form is optional.
- Item capture (Jul 2026): parse_courts grabs the petitioner line + the line
  after "Versus" (`caseLine` = "PET .. VERSUS RESP .."). **total/main/supp count
  only SERIAL matters** via `n_matters()` = keys without a "." — connected matters
  are stored as sub-items ("4.1", "102.2") for lookup but the court lists them
  UNDER their main item, so counting them (old `len(items)`) over-reported every
  court (Court 5's 30 read 32). PARSER_VERSION bumped so the Action re-parses all
  cached dates. App `titleFromCauseLine` strips the case-no prefix, splits on
  VERSUS, trims each side at "& Ors./and Anr." (drops the trailing AoR),
  title-cases → "Petitioner vs Respondent". Bug fixed: the entry form tracks
  what IT auto-filled (`auto{title,bench,type}`) so typing item "3"→"30" lands
  on the FINAL item's case, and a value the clerk edits is never overwritten.
- Briefing counsel is an `<input list="lawfirms">` datalist of top Indian firms
  (`LAW_FIRMS`) — pick or type any AoR. Each entry has an optional `confTime`
  (add now or edit later). `conferenceList(date)` builds the Conferences section
  (day sheet + print + share) from entries' confTime: "time — counsel", and
  when a counsel has >1 conference that day, "(FirstWordOfCauseTitle)". Manual
  daysheet.conferences[] merge in.
- `resolveEntry(e,date)` returns title/bench/listType/total from the entry
  falling back to the fetched causelist — used by rail, table, share AND print
  so a court+item-only entry completes once its list is fetched.
- Print heading = "SUPREME COURT (DAY) DATE"; `<title>` (= saved PDF file name)
  = "SD Causelist DATE". Columns: Court/Item (one line) | Time | Case Name |
  Judges | Advocates | Total & Seq. (court total + item seq). EB Garamond 14.
- **Ordering (Jul 2026, owner's rule):** `byCourt(arr, date)` groups by LIST TYPE
  first — every court finishes its Miscellaneous list before its Regular list, so
  ALL Misc matters (court-wise) print before ANY Regular matter, then the rest, in
  `CAUSELIST_TYPES` order (`_typeRank`). Within a type: court, then item. An entry
  carrying a `listType` is used directly; a court+item-only entry resolves its type
  via `resolveEntry(e,date)`. Single sort → day sheet display, print AND share all
  follow it. **Print fits one page for a busy day** (owner's 12-matter 15th + two
  conference days): top margin cut (`@page margin:6mm 11mm 8mm`, `body margin:0`
  — header sits at the top edge). Font sizing balances "one page" against the
  clerk's **"too small / too faint"** feedback: **weight 500 throughout** (EB
  Garamond 400 printed faint; headers 700, and the font link now loads the 500
  weight), case name 13px, judges/advocates 11px (cols widened to 114/120 so names
  don't wrap), court/item 13.5px, line-heights ~1.2. Conferences use a
  DETERMINISTIC two-column flex (`.cfsplit`/`.cfcol`), NOT CSS multicol (which
  balanced unpredictably and fragmented onto page 2): one conference day → its
  rows split left/right; two+ days → each day fills a column (e.g. 8 on the
  14th-evening left, 2 on the 15th-morning right). Measured faithfully against an
  A4 box (REAL print CSS, heavy 12-matter rows): ~1028px vs ~1070px printable →
  ~42px headroom. **Don't enlarge the font without re-measuring the worst-case fit.**
- Jul 2026 (2nd pass): Add-matter form order = **Causelist type FIRST**, then
  court+item (lookup is scoped to the chosen type — `lookupCauselistItem(...,
  preferType)`). Fetcher captures **sub-items** (ITEM_LINE_RE = `N` or `N.M`,
  e.g. 37.1 "Connected .."). Party cleaning: `cleanCauseSide` strips the
  case-TYPE prefix ("SLP(C) No.") even when the number sits on the next PDF
  line, strips a leading "Connected", trims trailing AoR at "& Ors./and Anr.".
  `partiesFromCauseLine`→{pet,resp}; `renderTitle(title,appearingFor,mode)`
  bolds the side we appear for (`<b>` in html, `*..*` in WhatsApp text) — entry
  has `appearingFor`. Time + conference time are `<input list="courttimes">`
  (COURT_TIMES datalist).
- List-type → PDF suffix (verified against real 13-07-2026 PDFs, via an
  authorised one-time probe): Miscellaneous `M_J`, Regular `F_J`, Chamber `M_C`,
  Single Judge `M_S`, Registrar `M_R`, Curative & Review `M_CC`; `_1` main,
  `_2` supplementary. Server returns 200-HTML for missing files, so `fetch_pdf`
  checks Content-Type is application/pdf.
- `parse_courts()` (in the fetcher) collects the coram only on a court's FIRST
  header (page headers repeat → would duplicate). `cleanCoram()` (in the app)
  turns "HON'BLE MR. JUSTICE …" into the clerk's short form; the honorific regex
  needs `\b` (else "MRS" matches "MR" and leaves a stray "S.").
- Validated OFFLINE against real downloaded PDFs (never hammer the live site in
  dev). court-updates.json fetched with `?_=Date.now()` + no-store (Pages CDN).
  A 13-07-2026 seed is committed; the Action overwrites it on first run. Owner
  must enable workflow write permission + run once (see CAUSELIST-SETUP.md).

## SC annual calendar import (Jul 2026)

The SC publishes an annual calendar (image PDF, no text layer — can't auto-parse)
each Nov/Dec. `SC_CALENDAR` encodes it per year: `holidays:[[from,to|null,name]]`
+ `vacation:[[from,to,label]]` (summer partial-court period). Calendar tab →
**Import SC calendar** (admin): one-click `applySCYear(year)` expands the ranges
into `config/holidays` (merge) and writes `config/vacation`; a paste box takes
future years line-by-line ("YYYY-MM-DD Name" / "YYYY-MM-DD to YYYY-MM-DD Name").
`config/vacation` = {ranges:[[from,to,label]]}, watched into `vacation`;
`isPartial(iso)` shades vacation weekdays "Partial court" (holiday > weekend >
partial priority). To add a year: extend `SC_CALENDAR` from the published PDF.

## Lookup note

`lookupCauselistItem(date,court,item,preferType)`: a chosen `preferType` is
AUTHORITATIVE — NO cross-type fallback (picking Miscellaneous can't return a
Registrar matter). Only an empty type searches all lists. The form message
distinguishes "no list fetched for this date" from "not in the <type> list".

## Calendar & brand visuals (Jul 2026 — calmed down)

- Calendar cells are NEUTRAL. The only strong colour is a small workload DOT in
  a pill beside the count: `.ld.lg`<5 green, `.ld.ly`5–10 amber, `.ld.lr`>10 red
  (load = max(register next-dates, day-sheet entries)). Non-working days get one
  faint mute + a thin left accent: `.day-hol` purple, `.day-vac` amber,
  `.day-off` weekend (no accent) + a muted `.cal-tag`. One-line dot legend.
  (Owner found the earlier full-cell tints overwhelming — keep it restrained.)
- **Refresh button** (topbar, `#btnRefresh`/`hardRefresh`): clears caches +
  updates SW + reloads with cache-buster — for installed PWAs holding an old
  shell. sw.js CACHE bumped when the shell changes (currently v3).
- Brand: circular seal emblem `.brand-mark` (navy field, double gold rule, gold
  Fraunces SD) on the login + pending cards; `.sb-logo` is the ring-emblem
  variant in the sidebar. Login = radial navy gradient, gold "CHAMBERS OF",
  Fraunces name + short gold rule. Stay within navy #101418 / gold #cbb682.

## Colleague "My work" home (Jul 2026)

Juniors are phone-first users, so the Work-board tab renders `renderMyWork()`
for `me.role==="junior"` (Staff/admin keep the distribution board). It's a
personal home: 4 metrics (to-acknowledge / my active / coming-up ≤4d / roster
position), a one-tap availability set (Available/In court/Half day/On leave →
`availability/{uid}_{today}`), an "acknowledge / object" card per unacked
assignment, their matters sorted by next date (imminent flame), and roster
standing ("#N · next up in M turns · X active · Y lifetime"). App is responsive
throughout: fixed sidebar ≥860px, dark bottom-nav <860px.

## Out-of-app notification

`waLink(uid, brief)` → WhatsApp deep link with prefilled nudge message;
mobile→wa.me, desktop→web.whatsapp.com (clerk uses WhatsApp Web on his PC,
QR-paired once). Copy-message fallback button beside every nudge. Phone
stored per user (10 digits → auto-prefix 91). True push (FCM + Functions)
is explicitly v2.

## Design system (do not drift)

Modern institutional, spacious. Tokens in `:root`: bg #f5f5f3, ink #141719,
sidebar #101418, single accent #3a5a8c, gold #cbb682 only in sidebar-active/
demo bar. Fonts: Fraunces (serif — masthead, page titles, case titles, metric
numerals ONLY), Inter (UI), IBM Plex Mono (diary/item/court numbers).
Desaturated status chips. Desktop: fixed left sidebar; mobile ≤860px: sidebar
hidden, dark bottom tab bar (5 tabs). **Board defaults are OPEN** (owner's
Jul 2026 reversal of the earlier collapse-by-default): balance panel starts
open, junior cards start expanded (`uiExp.cardsClosed` tracks user collapses).
Day sheet renders as the clerk's paper TABLE on desktop (>860px: Ct/Item ·
Time · Case & Bench · Counsel — Juniors · Remarks) and as the card rail on
mobile — both markups render, CSS switches. Still collapsed: day-sheet clerk
tools behind "⋯" (rail only), detail Files/Discussion, roster explainer.
Unassigned queue is ALWAYS open (it's the action list).
Icons: Tabler webfont via jsdelivr CDN.

## Security rules (`firestore.rules` now IN the repo — reconstructed)

`firestore.rules` was MERGED (Jul 2026) from the owner's actual live console
rules + the new features: admin role (by email AND role, get()-safe against a
missing users doc), `approvals` (read: any signed-in; write: admin; self-delete
of own invite), `config/holidays` (admin), `config/senioravail` (canManage),
constrained self-create of `users/{uid}` (role must be `pending`, or the admin
email, or match a pre-approval keyed by lowercased email). config is enumerated
so the catch-all (admin-only) never widens holidays. Still must be PUBLISHED in
the console by the owner. If `CHAMBER.adminEmail` changes, change it here too.

## Security rules (legacy notes; keep in lockstep with app writes)

Junior may update ONLY these brief fields (rules enforce):
`status, updatedAt, ackBy, declinedBy, heldForClerk, assignedTo, everAssigned,
assignHistory, assignedAt` — i.e. status moves, acknowledge, and the
objection's onward reassignment. Any new junior-writable field MUST be added
to that hasOnly list or production silently permission-fails where demo works.
`config/*`: clerk/pa full; any approved member may change `pointer` only
(objection advances rotation). Files/comments: any approved member reads all,
creates own; clerk/pa delete. daysheets rule still mentions role `senior` —
vestigial, harmless, cleanup candidate. If rules change, the owner must
re-paste in Firebase console (walk him through it; he edits nothing locally).

## Testing conventions (all proven in this project)

- Syntax gate after every edit: extract the module script → `node --check`.
  **The owner's Mac has no Node.** Use JavaScriptCore instead:
  `/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc`
  with a tiny script calling `checkModuleSyntax(readFile("_mod.mjs"))`.
  Behaviour checks: `python3 -m http.server` + the harness's preview tools
  (demo copy = `sed 's/const DEMO = false;/const DEMO = true;/' index.html >
  app.html` — the repo does not actually contain demo.html/app.html).
- Behaviour: Playwright headless Chromium against `file://.../app.html`
  (demo mode), viewport 1320×1000 desktop / 390×844 mobile, collect
  `pageerror`. Role-switch via `#demoRole` select (all seeded users listed)
  or `window.__demoSetUser(uid)`.
- Known harness quirks: clipboard writeText is permission-denied headless
  (not a bug); after modal submits, clear `#modalRoot` between steps;
  select_option fails if the option isn't in #demoRole.
- Engine logic: replicate pickNext in a standalone node script for unit
  tests (lightest-load, leave-skip, objector-exclusion, forced fallback,
  20-round fairness spread ≤3).

## Known wrinkles / cleanup candidates

- Dead code in `seedDemo`: an empty `Object.entries({b23:...}).forEach` block
  (harmless leftover; remove when touching the seed).
- PWA is now fully wired (Jul 2026): manifest linked, apple-touch-icon, iOS
  meta tags, SW registered, "SD" monogram icons. An already-installed shortcut
  keeps its OLD icon until removed and re-added to the device.
- Demo seed titles/numbers are synthetic; `scindex` demo entries mirror seed
  formulas (diary = 27000+i*37, case = 7000+i*13) — keep in sync if reseeding.
- File delivery to the owner via chat downloads is unreliable; he now hosts
  `demo.html` in the repo. Prefer giving him GitHub-pencil-edit instructions
  or small paste-able diffs over new file downloads.

## Pending (rough priority)

1. **Autofetch first SCHEDULED run** — the parser is validated offline against
   real PDFs, but the Action's live scheduled run is its first end-to-end;
   watch the first `causelist-bot` commit. Owner must enable workflow
   write-permission + run once. Possible optimisation: it re-downloads the huge
   M_J list 6×/day per window-day; could skip dates already parsed.
2. FCM push notifications via Firebase Functions (shared backend decision
   with the owner's ASD app — build once, serve both).
4. Native file uploads (needs Blaze; schema already URL-based so it's
   additive).
5. Rules cleanup (drop vestigial `senior`), icons, seed cleanup.

## Working with the owner

Adith is an Advocate on Record — sophisticated, direct, allergic to
over-agreement. Flag weak reasoning proactively; he has corrected fabricated
claims before and expects "tested" to mean actually tested (show the check).
He makes design decisions fast when given crisp options with trade-offs.
Legal-domain terminology must be exact (diary no. vs case no., AoR,
mentioning, pass-over). The clerk-simplicity constraint is load-bearing:
every new clerk-facing feature must survive the question "can a man who only
knows WhatsApp and email use this without training?"
