---
name: gemini-video-download
description: Generate and deliver verified AI videos from Gemini/Flow with strict non-interactive execution. Use when user asks to create/download/send video, needs fallback (Gemini limit -> Flow), and requires anti-silence progress, content verification, and Telegram-safe delivery.
---

# Gemini/Flow Video Pipeline (Reliable)

## ⚠️ MANDATORY: Read This Skill FIRST Before Any Video Task
- **DO NOT** start browser automation without reading this file
- **DO NOT** reinvent the wheel — use the scripts and methods documented here
- **DO** follow the exact workflow: `create -> wait -> verify -> download -> verify -> send -> cleanup`
- **DO** use proven fallback: extract GCS URL from `performance.getEntriesByType('resource')` if download fails

## Core principles
1) Deterministic state machine: `create -> wait -> verify-content -> download -> verify-media -> size-gate -> send`.
2) Non-interactive execution: once user approves, do not ask mid-step unless hard-blocked (login/2FA).
3) Evidence before claim: never report "checked" without proof from the correct project/card.
4) Fast recovery: timeout -> recover -> resume same step.
5) Correctness over speed: do not send if content/media gates fail.

## Fixed policy
- Primary route: Gemini
- If Gemini quota/limit is hit: switch to Flow automatically
- Save master files on `D:\Gemini-Downloads\`
- Before Telegram send, place final file in `C:\Users\DELL\.openclaw\media\`

## Mandatory workflow
1) Start browser profile `krudon`.
2) **Hard rule:** create **NEW project for every task** in Flow.
   - Never reuse old project/cards.
   - If current tab is an old project, go back and create `โปรเจ็กต์ใหม่` first.
   - If new-project creation fails, stop with `ORIGINAL_VIDEO_REQUIRED`.
3) Submit prompt in video mode.
4) Wait with anti-silence cadence:
   - Light check every 45-60s (state/progress only)
   - Heavy check every 2-3 min or on transition/error
5) Content gate before download:
   - project title matches task
   - prompt keywords match task
   - active tab URL is the target project/card
   - composer gate: must be inside `/project/...` page and prompt textbox (`คุณต้องการสร้างอะไร`) is present before generation
6) Download gate:
   - open `ดาวน์โหลด` (first when duplicated)
   - choose `720p Original Size`
   - **CRITICAL Fallback (Proven Working):** If browser download event is not emitted:
     1. Wait 3-5 seconds after clicking 720p
     2. Extract GCS signed URL from `performance.getEntriesByType('resource')`:
        ```javascript
        () => {
          const entries = performance.getEntriesByType('resource')
            .filter(e => e.name.includes('storage.googleapis.com'));
          return entries[0]?.name;  // Returns full GCS signed URL
        }
        ```
     3. Download with PowerShell `Invoke-WebRequest -Uri $gcsUrl -OutFile $outPath -UseBasicParsing`
     4. Verify MP4 header (ftyp at bytes 4-7)
   - ⚠️ Do NOT rely on console logs for GCS URLs (often not present)
   - ⚠️ Do NOT try to follow redirect URLs without authenticated session
7) Media gate:
   - run `inspect_mp4.py`
   - must pass: non-HTML, `HAS_VIDEO=True`, `HAS_AUDIO=True`
8) Telegram size gate:
   - run `telegram_size_gate.py` (auto-transcode if >16MB)
9) Send only final gated file.
10) Post-send cleanup (mandatory): close Flow tabs/project pages and stop the `krudon` browser profile to release CPU/RAM.

## Recovery policy
- Timeout #1: reopen tab/profile and resume step
- Timeout #2: restart gateway, reopen profile, resume
- Timeout #3: fail with explicit reason + `ORIGINAL_VIDEO_REQUIRED`
- Script-level retries: `flow_click_download.py` retries menu/open/download before hard fail
- Selector fallback policy: Thai/English labels + role/text/css fallback chain
- CDP endpoint can be overridden via env: `FLOW_CDP_URL`
- CDP auto-fallback in code flow: try `FLOW_CDP_URL`, then `http://127.0.0.1:18801`, then `http://127.0.0.1:18802`
- Failure artifacts: scripts save screenshot+HTML on fail to `D:\Gemini-Downloads\artifacts` (override with `--artifact-dir`)
- Incident report: every run writes `run-report-<timestamp>.json` with status/error_code/error_detail/artifact paths

## Heartbeat policy (code flow)
- `flow_click_download.py` must print progress in pattern: `ACK -> HEARTBEAT -> RESULT`
- While waiting generation, emit heartbeat every ~45 seconds with elapsed time
- On each CDP connect attempt, emit heartbeat (`trying/failed/connected`) before retry/fallback
- Never stay silent during long waits; on fail print explicit `ERROR_CODE` + `ERROR_DETAIL`
- Heartbeat must stop immediately at end-of-run: emit final `RESULT` then no further heartbeat lines
- End-of-run requires explicit close signal: `HEARTBEAT_STOP` + `RESULT` + (if applicable) `CLEANUP_DONE`
- Root fix: wrapper now runs child via shared relay `C:\Users\DELL\.openclaw\workspace\agents\sompro\scripts\heartbeat_relay_runner.py` which emits independent heartbeat every 30s even if child script is quiet

## Scripts
- `scripts/download_gemini_video.py` (Gemini route)
- `scripts/flow_click_download.py` (Flow 720p download with prompt keyword gate)
- `scripts/inspect_mp4.py` (video/audio validity)
- `scripts/telegram_size_gate.py` (<=16MB for Telegram)

## Commands
```powershell
# Mandatory wrapper (preflight gate + flow run). Do not run flow_click_download.py directly.
& "<skill_dir>\scripts\run_flow_with_preflight.ps1" -Prompt "A short cinematic video of an orange cat engineer" -Out "D:\Gemini-Downloads\flow-video-720p.mp4" -Retries 3

# Supervisor mode (recommended for overnight/unattended runs)
& "<skill_dir>\scripts\run_flow_supervised.cmd" "prompt" "output.mp4"
# Example:
& "C:\Users\DELL\.openclaw\workspace\agents\sompro\skills\gemini-video-download\scripts\run_flow_supervised.cmd" "talking nail 8 seconds" "D:\Gemini-Downloads\nail.mp4"

# Media validation
& "C:\Users\DELL\AppData\Local\Programs\Python\Python311\python.exe" "<skill_dir>\scripts\inspect_mp4.py" "D:\Gemini-Downloads\flow-video-720p.mp4"

# Telegram size gate (copy/transcode)
& "C:\Users\DELL\AppData\Local\Programs\Python\Python311\python.exe" "<skill_dir>\scripts\telegram_size_gate.py" --infile "D:\Gemini-Downloads\flow-video-720p.mp4" --outfile "C:\Users\DELL\.openclaw\media\flow-video-telegram.mp4"
```

## Supervisor Protocol (for Unattended/Night Runs)

### Overview
For overnight or unattended execution, use **Supervisor Mode** which spawns a worker subagent and monitors it with:
- Mandatory heartbeat every 30 seconds
- Preflight checks (CDP, login, disk space)
- Post-run verification (file exists, size > 1MB, MP4 header valid)
- Full audit trail (JSON reports, screenshots, console logs)

### Components
- `supervisor_flow_video.py` — Main orchestrator (spawns worker, monitors, verifies)
- `run_flow_supervised.cmd` — One-command launcher
- `SUPERVISOR_PROTOCOL.md` — Full protocol specification

### Workflow
```
1. Preflight: Check CDP (port 18801), disk (>100MB), credentials
2. Spawn worker: Run flow_click_download.py as subprocess
3. Monitor: Poll heartbeat.json every 30s, alert if silent >60s
4. Verify: Check output file (exists, size, MP4 header)
5. Report: Save audit report JSON + deliver to user
6. Cleanup: Archive artifacts (7-day retention)
```

### Audit Trail (per run)
- `run-report-{timestamp}.json` — Full execution summary
- `heartbeat-{timestamp}.json` — All heartbeat updates
- `screenshot-{stage}-{timestamp}.png` — UI state at errors
- `html-{stage}-{timestamp}.html` — DOM state at errors
- `console-{timestamp}.log` — Browser console logs
- `supervisor-audit.log` — Supervisor decision log

### Error Contract
| Code | Meaning | Recovery |
|------|---------|----------|
| `E_PREFLIGHT_CDP` | CDP not reachable | Restart gateway, retry 1x |
| `E_PREFLIGHT_LOGIN` | Not logged in to Flow | Alert user, abort |
| `E_COMPOSER_NOT_READY` | UI not in composer mode | Click edit button, retry 1x |
| `E_DOWNLOAD_FAILED` | Download event not fired | Use signed URL fallback |
| `E_VERIFY_SIZE` | File < 1MB | Retry generation |
| `E_VERIFY_HEADER` | Not valid MP4 | Retry generation |
| `E_TIMEOUT` | No heartbeat > 60s | Kill worker, retry 1x |
| `E_MAX_RETRIES` | Failed 3 times | Alert user with full audit |

## Output contract
- Success: print `OUT=`, `SIZE=`, and media checks (`HAS_VIDEO=True`, `HAS_AUDIO=True`)
- Failure: print explicit reason + `ORIGINAL_VIDEO_REQUIRED`
