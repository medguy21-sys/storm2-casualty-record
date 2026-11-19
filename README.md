[README_1.md](https://github.com/user-attachments/files/35100030/README_1.md)
# STORM-2 Unified Casualty Record

A touch-first tablet form that combines the fields of three Ukrainian casualty documentation forms into one record that follows a casualty from point of injury through Role 2 surgery and anesthesia.

- **Form 001/о**: primary medical card (pre-Role 2 and Role 2 parts)
- **Form 002/о**: casualty card (MoD of Ukraine Order No. 253, 18 April 2025)
- **Form 003-3/о**: pre-operative anesthesiologist examination and anesthesia record (MoH of Ukraine Order No. 110, 14 February 2012)

Built for the STORM-2 forward surgical team course by Ragged Edge Solutions.

> **Training prototype. Not an official form.** English labels are training translations. Ukrainian labels need native-speaker review before use.

## Use it

Open `index.html` in Microsoft Edge or Google Chrome. Built and sized for a Surface Pro (landscape or portrait). It also works on a laptop.

No installation, no login, no server. Everything is in the one file.

## What it does

- **One long form** with a frozen top bar. Tap a section tab to jump to it; the active tab follows as you scroll.
- **12 sections:** Patient, Mechanism and injuries (tap body map), Care given (MARCH, tourniquet cards with live timers), Meds/fluids/blood (quick pick, blood unit details, totals), Vital signs and ventilator (with a 003-3/о style chart), Role 2 exam, Diagnostics (serial E-FAST, labs), Operative care, Anesthesia pre-op, Anesthesia record, Disposition and sign-off (Part 1 and Part 2), Timeline and export.
- **Role stamping:** set the current Role (1 to 4) at the top. Every intervention, drug, vital sign and ventilator entry is stamped with the time (HH:MM:SS) and Role.
- **Serial E-FAST:** a negative exam is recorded as "negative now". Each exam starts a repeat timer, and the header shows when the next exam is due or overdue.
- **Touch keypad** for numbers and times (1420 becomes 14:20; quick Now, -1, -5, -15 minute buttons). Turn it off with the ⌨ button to use a keyboard.
- **Ukrainian / English** toggle.
- **Multiple casualties** on one device (Casualties button).
- **Export:** JSON for one casualty, CSV for all casualties, and a text handover summary with timeline.

## Where the data goes

Records are saved **only in the browser on that device**. Nothing is sent anywhere. Notes:

- Data is tied to the page address. If the file is moved, renamed, or opened from a different address, the casualty list starts empty. **Export before moving or updating.**
- Clearing browser data deletes records.
- Do not enter real patient information in this training prototype.

## Voice capture

Tap **Record** (top bar) and speak. Each phrase is saved to a transcript with the time speaking started, and common items are entered into the form automatically, for example:

- "pulse 124, pressure 88 over 50", "пульс 120, тиск 90 на 60"
- "tourniquet right leg on", "турнікет права нога накладено"
- "TXA 1 gram IV", "FAST negative"

Every automatic entry can be undone with one tap in the transcript panel. Choose Ukrainian or English in the panel.

- Works in **Microsoft Edge or Google Chrome**, opened from a web address (for example GitHub Pages). Opened as a file from the tablet's folders, the browser may block the microphone.
- Uses the browser's built-in speech recognition. **Audio is processed by Google (Chrome) or Microsoft (Edge)** and needs an internet connection. GRM and the Ukrainian side should approve this before any real patient use.
- Recognition of Ukrainian medical terms has not been field-tested yet.

## Features only in the claude.ai version

The hosted claude.ai version adds features that need the Claude platform. They do not work from this file or from GitHub Pages:

- "Fill remaining fields with Claude" for phrases the automatic parser could not enter
- Shared course database for trauma registry review

## Updating

Replace `index.html` with the new version. Export records first (see above).

## Known open items

- Abbreviations marked **[confirm]** come from a scanned 001/о and need checking against the paper form: Ц/В/П, triage colors, Б/С and М/С, ММРМ.
- The vital signs chart symbols (∨ systolic, ∧ diastolic, ● pulse) need confirmation from anesthesia staff.
- The E-FAST repeat interval defaults to 30 minutes as a placeholder for faculty to set.
- Needs a connection to open when hosted on GitHub Pages (no offline install yet). Voice capture always needs a connection.
- Not yet tested on a physical Surface Pro.

## Contact

Paul Loos, VP of Special Projects, Ragged Edge Solutions
