# Vital Lab integrated session

One local host coordinates the instructor console, student monitors, two student charting devices, camera previews and debrief exports. This public demo contains one generic case. The original standalone documentation app and `vital-lab/` simulator remain available separately.

## Run

Use Python 3.12+ and `python -m pip install -r requirements.txt`, then `python hub.py`. Keep the host running. Open the printed instructor URL on the host Surface; use **Students** to obtain the two classroom links. Students need only a browser on the same private Wi-Fi. The Windows build script packages a single executable. Source can run without PyAV if camera video is not used.

## Observation modes

Under **Session setup**, choose **Manual entry only**, **One-tap capture**, or **Live vitals feed + capture**. Live mode also offers optional automatic charting at a selected interval; it is off by default. Automatic observations use the shared clock, pause with it and retain their own source tag. They merge with manual drafts without replacing student edits. The chart distinguishes original automatic rows, captures, manual entries and edited captures.

The same patient IDs and available readings feed single-patient SYNCO and 2/4/8-patient displays. Unassigned beds stay empty. Students hand over writing ownership explicitly; conflicts retain the local draft. Sensor availability and completed BP measurement time govern capture—unmeasured targets are excluded.

## Cameras and reports

The instructor console has a collapsible bottom camera strip with labels/status and tap-to-enlarge previews. Only visible cards load streams. Camera selection and VIP presentation do not change physiology. Configure your own camera account locally; camera passwords stay in memory or in Windows-user-encrypted host storage, never in student records or exports. Video only; no audio/recording.

**Debrief** provides student AAR, command summary, instructor detail, comparison CSV, all-chart-section CSV, combined event CSV and full session JSON. Stable session/patient/entry/event IDs join the datasets. Clinical chart time, server documentation time, receipt UTC, sample age and BP measurement time are separate fields. Source tags distinguish `student-entered`, `monitor-capture`, `student-edited-capture` and `auto-stream`; `field_source` identifies individually edited captured values. Automatically populated matches are excluded from student-entry comparison counts in the command summary.

The audit stores an initial chart, original captured rows and before/after changed values/entries rather than duplicating the full growing chart on every keystroke. Repeated request IDs cannot duplicate an observation. Routine updates omit unchanged chart bodies and unselected patients' charts.

## Scope and development

Read [READ-ME.txt](READ-ME.txt) and [TESTED.txt](TESTED.txt) for workflow and validation. Clinical sections and language labels derive from the supplied repository documentation app; this is a training prototype. Camera credentials, real course scripts and saved sessions are excluded from this public folder.

`python rebuild.py` regenerates the instructor/student HTML and monitor assets from the sibling standalone simulator, root documentation HTML and local bridge/templates. Run `python -m unittest discover -s tests`. Case replay remains in the standalone simulator; a local replay cannot reset this shared exercise. Restart recovery uses the local SQLite database. Full-session JSON import is not implemented.

The repository license applies to original code. Embedded libraries retain their licenses; see Third-Party-Notices.txt. Original documentation source and attribution remain in the repository root.
