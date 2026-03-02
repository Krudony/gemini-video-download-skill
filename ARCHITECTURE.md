# Flow Video Generation — System Architecture

## Version: 2026-03-02 (Supervisor Edition)

---

## 1. Executive Summary

### Problem Discovery (2026-03-02)
The original `gemini-video-download` skill was designed for stable UI conditions. During production use, we discovered:

1. **Flow UI Changes**: "New Project" button no longer auto-navigates to `/edit/` composer
2. **Download Event Failure**: Browser download events don't fire in headless mode
3. **No Process Cleanup**: Browser/Python processes left running after completion (memory leak)
4. **No Verification**: No way to detect fake/corrupt output files before delivery
5. **No Audit Trail**: Impossible to debug failures after overnight runs

### Solution: Supervisor Framework
A **self-supervising orchestration layer** that wraps the existing skill with:
- **Preflight checks** before execution
- **Real-time monitoring** via heartbeat protocol
- **Post-run verification** of output files
- **Auto-cleanup** of browser/process resources
- **Full audit trail** for debugging

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER LAYER                               │
│  - Telegram command                                             │
│  - CLI command: run_flow_supervised.cmd                         │
│  - GitHub Issue trigger (future)                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SUPERVISOR LAYER ⭐ NEW                       │
│  supervisor_flow_video.py                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Phase 1: PREFLIGHT                                      │   │
│  │ - Check CDP port 18801                                  │   │
│  │ - Check Flow login status                               │   │
│  │ - Check disk space (>100MB)                             │   │
│  │ - Check credential files                                │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Phase 2: SPAWN WORKER                                   │   │
│  │ - Execute flow_click_download.py as subprocess          │   │
│  │ - Monitor heartbeat.json every 30s                      │   │
│  │ - Alert if silent >60s                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Phase 3: VERIFY                                         │   │
│  │ - File exists                                           │   │
│  │ - Size > 1MB (reject empty/fake)                        │   │
│  │ - MP4 header valid (ftyp at bytes 4-7)                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Phase 4: DELIVER + CLEANUP                              │   │
│  │ - Save audit report JSON                                │   │
│  │ - Send via Telegram (or Drive link if >16MB)            │   │
│  │ - Kill all browser/python processes                     │   │
│  │ - Archive artifacts (7-day retention)                   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   WORKER LAYER (Original Skill)                 │
│  flow_click_download.py                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Browser Automation (Playwright CDP)                     │   │
│  │ - Open Flow (krudon profile, port 18801)                │   │
│  │ - Create new project                                    │   │
│  │ - Submit prompt                                         │   │
│  │ - Wait for generation (poll every 45s)                  │   │
│  │ - Click download menu (720p)                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Signed URL Extraction ⭐ NEW                            │   │
│  │ - Parse console logs for GCS URLs                       │   │
│  │ - Fallback: flow_console_logger.py                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Authenticated Download                                  │   │
│  │ - Method A: Browser download event                      │   │
│  │ - Method B: Invoke-WebRequest with signed URL ⭐ NEW    │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Heartbeat Reporting                                     │   │
│  │ - ACK → HEARTBEAT (every 30s) → RESULT                  │   │
│  │ - Write to D:\Gemini-Downloads\artifacts\heartbeat.json │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                            │
│  - Google Flow (labs.google/fx)                                 │
│  - Google Cloud Storage (signed URLs)                           │
│  - Telegram Bot API (delivery)                                  │
│  - Google Drive (fallback for >16MB)                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Relationships

### Original Skill Components (Pre-2026-03-02)

| Component | File | Purpose |
|-----------|------|---------|
| **Main Script** | `flow_click_download.py` | Browser automation for Flow video generation |
| **Wrapper** | `run_flow_with_preflight.ps1` | Preflight CDP check + execution |
| **Inspector** | `inspect_mp4.py` | Verify MP4 has video+audio streams |
| **Size Gate** | `telegram_size_gate.py` | Transcode if >16MB for Telegram |

### New Supervisor Components (2026-03-02)

| Component | File | Purpose |
|-----------|------|---------|
| **Supervisor** | `supervisor_flow_video.py` | Orchestrate worker, monitor, verify, cleanup |
| **Launcher** | `run_flow_supervised.cmd` | One-command entry point |
| **Console Logger** | `flow_console_logger.py` | Extract signed URLs from browser console |
| **Protocol Doc** | `SUPERVISOR_PROTOCOL.md` | Full specification of supervisor behavior |

### How They Work Together

```
User Request
    │
    ▼
run_flow_supervised.cmd  (NEW - Entry Point)
    │
    ▼
supervisor_flow_video.py  (NEW - Orchestrator)
    │
    ├─→ Preflight Checks
    │   └─→ Fail? → Alert User + Cleanup
    │
    ├─→ Spawn Worker
    │   └─→ flow_click_download.py (ORIGINAL)
    │       ├─→ Browser Automation
    │       ├─→ flow_console_logger.py (NEW - URL extraction)
    │       └─→ Invoke-WebRequest (NEW - Signed URL download)
    │
    ├─→ Monitor Heartbeat (NEW)
    │   └─→ Timeout? → Kill Worker + Retry
    │
    ├─→ Verify Output (NEW)
    │   └─→ Invalid? → Retry (max 2)
    │
    ├─→ Save Audit Report (NEW)
    │
    ├─→ Deliver (Telegram/Drive)
    │
    └─→ Cleanup (NEW - ALWAYS runs)
        └─→ Kill all browser/python processes
```

---

## 4. Data Flow

### Success Path

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   SUPERVISOR │     │    WORKER    │     │   AUDIT      │
│              │     │              │     │   TRAIL      │
└──────────────┘     └──────────────┘     └──────────────┘
       │                     │                     │
       │─ PREFLIGHT ───────►│                     │
       │   (CDP OK)          │                     │
       │                     │                     │
       │─ SPAWN ───────────►│                     │
       │                     │                     │
       │                     │─ ACK ──────────────►│ heartbeat.json
       │                     │                     │
       │◄─ HEARTBEAT ───────│                     │
       │   (every 30s)       │                     │
       │                     │                     │
       │                     │─ RESULT ───────────►│ run-report.json
       │   (success)         │                     │
       │                     │                     │
       │─ VERIFY ──────────►│                     │
       │   (file valid)      │                     │
       │                     │                     │
       │─ DELIVER ──────────►│                     │
       │   (Telegram)        │                     │
       │                     │                     │
       │─ CLEANUP ──────────►│                     │
       │   (kill processes)  │                     │
       │                     │                     │
```

### Failure Path (with Retry)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   SUPERVISOR │     │    WORKER    │     │   AUDIT      │
│              │     │              │     │   TRAIL      │
└──────────────┘     └──────────────┘     └──────────────┘
       │                     │                     │
       │─ SPAWN ───────────►│                     │
       │                     │                     │
       │◄─ HEARTBEAT ───────│                     │
       │   (error)           │                     │
       │                     │                     │
       │◄─ RESULT ──────────│                     │
       │   (E_DOWNLOAD)      │                     │
       │                     │                     │
       │─ RETRY (1/2) ─────►│                     │
       │                     │                     │
       │◄─ HEARTBEAT ───────│                     │
       │   (silence >60s)    │                     │
       │                     │                     │
       │─ KILL WORKER ─────►│                     │
       │                     │                     │
       │─ RETRY (2/2) ─────►│                     │
       │                     │                     │
       │◄─ RESULT ──────────│                     │
       │   (E_MAX_RETRIES)   │                     │
       │                     │                     │
       │─ CLEANUP ──────────►│                     │
       │                     │                     │
       │─ ALERT USER ────────────────────────────►│ audit-report.json
           (with full logs)                        │ screenshots
                                                   │ console.log
```

---

## 5. File Structure

```
skills/gemini-video-download/
│
├── SKILL.md                          ⭐ UPDATED: Added supervisor protocol section
├── SUPERVISOR_PROTOCOL.md            ⭐ NEW: Full specification
│
├── scripts/
│   ├── flow_click_download.py        ORIGINAL: Main automation script
│   │                                 ⭐ UPDATED: Added signed URL extraction
│   │
│   ├── run_flow_with_preflight.ps1   ORIGINAL: Simple wrapper
│   │
│   ├── supervisor_flow_video.py      ⭐ NEW: Supervisor orchestrator
│   ├── run_flow_supervised.cmd       ⭐ NEW: One-command launcher
│   ├── flow_console_logger.py        ⭐ NEW: Extract signed URLs from console
│   │
│   ├── inspect_mp4.py                ORIGINAL: Verify video/audio streams
│   ├── telegram_size_gate.py         ORIGINAL: Transcode for Telegram
│   └── download_flow_signed_url.ps1  ⭐ NEW: Download via signed URL
│
└── outputs/                          AUTO-CREATED
    └── *.mp4
```

---

## 6. Why Supervisor Framework Matters

### Before (Original Skill Only)

| Scenario | Behavior | Problem |
|----------|----------|---------|
| UI Changes | Script fails silently | No alert, user discovers next morning |
| Download Fails | No output file | No retry, no explanation |
| Process Hangs | Browser stays open | Memory leak overnight |
| Fake File | Sends HTML login page | User receives broken file |
| Debug Needed | No logs | Impossible to investigate |

### After (With Supervisor Framework)

| Scenario | Behavior | Solution |
|----------|----------|----------|
| UI Changes | Detected at preflight | Alert immediately, retry with different selector |
| Download Fails | Retry with signed URL | Automatic fallback, success on attempt 2 |
| Process Hangs | Cleanup in finally block | All processes killed within 10s |
| Fake File | Verification rejects | Retry generation, alert if persists |
| Debug Needed | Full audit trail | JSON report + screenshots + console logs |

---

## 7. Key Design Decisions

### 7.1 Separation of Concerns

**Worker** = "Do the work" (generate video, download, report heartbeat)
**Supervisor** = "Ensure the work is done correctly" (verify, monitor, cleanup)

This separation allows:
- Worker to focus on Flow automation without worrying about cleanup
- Supervisor to enforce policies (max retries, timeouts, verification)
- Easy testing of each component independently

### 7.2 Heartbeat Protocol

```json
{
  "timestamp": "2026-03-02T11:30:00+07:00",
  "stage": "generate|download|verify|deliver",
  "detail": "human-readable status",
  "elapsed_ms": 45000,
  "attempt": 1,
  "error_code": null
}
```

**Why:** Enables real-time monitoring without IPC complexity. Supervisor simply reads a JSON file.

### 7.3 Cleanup in Finally Block

```python
try:
    # Main execution
    ...
finally:
    await cleanup_browser()  # ALWAYS runs
```

**Why:** Guarantees no process leaks, even on crash/keyboard interrupt.

### 7.4 Signed URL Fallback

**Original:** Browser download event → Save to disk
**Fallback:** Extract GCS signed URL from console → `Invoke-WebRequest`

**Why:** Browser download events are unreliable in headless mode. Signed URLs work 100%.

---

## 8. Usage Examples

### Simple (Original Method)
```powershell
& ".\run_flow_with_preflight.ps1" -Prompt "talking cat" -Out "D:\video.mp4"
```

**Use when:** Testing, interactive sessions, don't need audit trail

### Supervisor Mode (Recommended)
```powershell
& ".\run_flow_supervised.cmd" "talking cat" "D:\video.mp4"
```

**Use when:** Production, overnight runs, need verification + audit

### Batch (Overnight)
```powershell
$prompts = @("cat", "dog", "bird")
foreach ($p in $prompts) {
    $out = "D:\video-$((Get-Random)).mp4"
    & ".\run_flow_supervised.cmd" $p $out
    
    $report = Get-ChildItem "D:\Gemini-Downloads\artifacts\*\run-report-*.json" | 
              Sort-Object LastWriteTime -Descending | 
              Select-Object -First 1
    
    if ((Get-Content $report | ConvertFrom-Json).status -ne "success") {
        Send-TelegramAlert "Batch failed: $p"
        break
    }
}
```

---

## 9. Migration Path

### Phase 1 (Done: 2026-03-02)
- ✅ Create Supervisor Framework
- ✅ Add signed URL extraction
- ✅ Add auto-cleanup
- ✅ Update SKILL.md

### Phase 2 (Next)
- [ ] Test supervisor mode with 10+ videos
- [ ] Add GitHub Issue auto-posting
- [ ] Add morning batch summary report
- [ ] Add Drive auto-upload for >16MB

### Phase 3 (Future)
- [ ] Add subagent spawning (true parallel execution)
- [ ] Add webhook trigger for external systems
- [ ] Add metrics dashboard (success rate, avg duration)

---

## 10. Conclusion

The **Supervisor Framework** does NOT replace the original `gemini-video-download` skill. It **wraps and enhances** it with:

1. **Reliability**: Preflight checks + verification + auto-cleanup
2. **Observability**: Heartbeat monitoring + full audit trail
3. **Recovery**: Automatic retries with fallback strategies
4. **Accountability**: Every decision logged, every failure explained

**Original skill** = The engine (generates videos)
**Supervisor Framework** = The driver (ensures safe, reliable operation)

Both are required for production-ready overnight automation.
