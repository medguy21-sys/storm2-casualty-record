# Vital Lab

Neutral training simulator with a compact instructor UI, simulated patient displays and a read-only VIP room.

## Start

- **Standalone:** download/open `index.html` in current Edge or Chrome. It is self-contained. Use simulated data only.
- **VIP room / native display inventory:** run `python host.py` (Python 3.12+ for camera support), keep the host window and instructor browser open, and use the printed observer links. The relay needs no extra packages; install `av==19.0.2` for live video (`python -m pip install av==19.0.2`).
- **Windows EXE:** use `build-windows.cmd` on Windows with Python installed. It packages the same public demo; no private course files are required.

## Instructor UI

- **Setup / Run** tabs; phases and observations on the left, vital controls on the right.
- Sticky scenario clock, Start/Pause/Resume and **Mark Intervention**.
- **Tools:** student display, ventilator, display setup, Log & CSV, AAR/reports and panel arrangement.
- **Camera:** GoPro, Patient, Clinic 1, Clinic 2. The collapsible bottom strip previews visible cameras; tap to enlarge and collapse to pause thumbnails. Configure local RTSP cameras in Camera → Set up / add cameras. Add, rename or remove camera entries (up to 12); all appear in instructor/VIP choices. Tapo uses its separate Camera Account and stream1/stream2. Video only, no audio or recording. One decoder per actively viewed camera is shared across viewers and stops when unused. Preview is limited to 10 fps and 960 px width; performance depends on the host and number of active feeds. Passwords never go to viewers or reports. Optional saved passwords use Windows user encryption; otherwise re-enter them after restarting the host. Do not publish the host data folder.
- **VIP View:** choose a 2/4/8-bed overview, a selected patient view or a camera for VIP Screens 1–3 independently, or for all screens together. Open each observer link on the corresponding room display. This changes presentation only, never patient physiology or the students' destination.

Connect compatible wireless receivers in Windows and choose **Extend** first. The browser can select connected displays with permission; it cannot pair an unconnected receiver. Fullscreen can require a click/F11. No unattended receiver power-on workflow or camera compatibility is claimed.

## Data and scope

This public edition includes **one generic demo casualty and eleven illustrative observation items**. Real course handouts, instructor assessment scripts, saved sessions, camera credentials and tokens are excluded. Private course libraries remain separate.

The documentation application in the repository root is preserved. Sharing a repository does not automatically synchronize its records with this simulator. This mobile display edition is also separate from the private shared-course charting pilot.

The instructor browser owns physiology and timing. The local host relays sanitized read-only data and saves the observer audit. If the VIP network drops, the mobile instructor continues. Closing the instructor browser stops simulation. Use the explicit paused recovery and export backups before moving files or clearing browser data. Clinical-form documentation has its own backup.

## Development

`src/` contains editable display policy, display template, journey controller and operator UI. After changing those modules, run `python rebuild.py` to regenerate the inline operator bundle in `index.html`. The rest of `index.html` contains the simulator and offline form-export engines. `host.py` and `inventory.ps1` provide the local relay and optional Windows display inventory.

Run `python -m unittest discover -s tests` and `node tests/policy.cjs`. Browser acceptance was additionally checked in isolated Edge sessions; see `TESTED.txt`. Physical Surface/receiver/camera testing remains necessary.

The repository license applies to original code. Embedded third-party libraries/fonts and documentation assets retain their licenses; see `Third-Party-Notices.txt`.
