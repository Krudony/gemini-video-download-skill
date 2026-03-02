# Flow Video Generation - Supervisor Protocol

## Role Definition

### Supervisor Agent (sompro)
- **Responsibility**: Orchestrate worker subagent, monitor progress, validate results, create audit trail
- **Cannot**: Skip verification, claim success without evidence, retry > 2 times without changing strategy

### Worker Agent (subagent with gemini-video-download skill)
- **Responsibility**: Execute video generation, report heartbeat every 30 seconds, save artifacts
- **Cannot**: Exit without RESULT signal, delete artifacts, claim success without file verification

## Mandatory Workflow

### Phase 1: Preflight (Supervisor)
```
1. Check CDP availability (krudon profile port 18801)
2. Check Flow login status (open Flow, verify project list visible)
3. Check disk space (D:\Gemini-Downloads has > 100MB free)
4. Check credential files exist (oauth tokens)
5. Create audit directory (D:\Gemini-Downloads\artifacts\YYYY-MM-DD\)
```

**Exit criteria**: All checks pass → spawn worker | Any fail → abort + alert user

### Phase 2: Execution (Worker + Supervisor monitoring)
```
Worker:
1. Send ACK immediately on start
2. Send HEARTBEAT every 30 seconds (stage, detail, elapsed_ms)
3. Save screenshot + HTML on any error
4. Send RESULT (success/fail) on completion

Supervisor:
1. Poll heartbeat.json every 30 seconds
2. Alert if no heartbeat for > 60 seconds
3. Log all progress updates to audit log
4. Kill worker if timeout > 15 minutes
```

### Phase 3: Verification (Supervisor)
```
1. Check output file exists (path from RESULT)
2. Verify file size > 1MB (reject fake/empty files)
3. Verify MP4 header (ftyp at bytes 4-7)
4. Check duration > 3 seconds (reject failed generations)
5. Verify audio stream exists (if required by prompt)
```

**Exit criteria**: All checks pass → deliver | Any fail → retry (max 2) or alert user

### Phase 4: Delivery (Supervisor)
```
1. Send video file via Telegram (or Drive link if > 16MB)
2. Send audit report (JSON summary + key artifacts)
3. Update GitHub Issue with run result
4. Archive heartbeat logs + screenshots
5. Clean up temporary files (keep 7 days of artifacts)
```

## Heartbeat Schema

```json
{
  "timestamp": "2026-03-02T11:30:00+07:00",
  "stage": "generate|download|verify|deliver",
  "detail": "human-readable status",
  "elapsed_ms": 45000,
  "attempt": 1,
  "artifacts": ["screenshot.png", "console.log"],
  "error_code": null
}
```

## Error Contract

| Code | Meaning | Recovery |
|------|---------|----------|
| `E_PREFLIGHT_CDP` | CDP not reachable | Restart gateway, retry 1x |
| `E_PREFLIGHT_LOGIN` | Not logged in to Flow | Alert user, abort |
| `E_COMPOSER_NOT_READY` | UI not in composer mode | Click edit button, retry 1x |
| `E_DOWNLOAD_failed` | Download event not fired | Use signed URL fallback |
| `E_VERIFY_SIZE` | File < 1MB | Retry generation |
| `E_VERIFY_HEADER` | Not valid MP4 | Retry generation |
| `E_TIMEOUT` | No heartbeat > 60s | Kill worker, retry 1x |
| `E_MAX_RETRIES` | Failed 3 times | Alert user with full audit |

## Audit Trail Requirements

### Must Save (per run)
- `run-report-{timestamp}.json` — Full execution log
- `heartbeat-{timestamp}.json` — All heartbeat updates
- `screenshot-{stage}-{timestamp}.png` — UI state at errors
- `html-{stage}-{timestamp}.html` — DOM state at errors
- `console-{timestamp}.log` — Browser console logs
- `video-{timestamp}.mp4` — Output file (or link if Drive)

### Retention Policy
- Keep all artifacts for 7 days
- Keep run reports for 30 days
- Keep successful videos for 14 days (then archive to Drive)

## User Alert Policy

### Alert Immediately
- Preflight failure (cannot start)
- Max retries exceeded (failed 3 times)
- Verification failure (fake/corrupt file)
- Timeout > 15 minutes

### Batch Report (Morning Summary)
- All successful runs (count + total size)
- Total execution time
- Any warnings (retries needed, slow generation)

## Implementation Checklist

- [ ] Create `supervisor_flow_video.py` — Main supervisor agent script
- [ ] Create `worker_flow_video.py` — Worker subagent entry point
- [ ] Create `heartbeat_monitor.py` — Real-time heartbeat watcher
- [ ] Create `verify_video.py` — Post-run verification script
- [ ] Create `audit_report.py` — Generate audit report JSON
- [ ] Update `SKILL.md` — Add supervisor protocol section
- [ ] Create `run_flow_supervised.cmd` — One-command launcher
- [ ] Test end-to-end with "ตะปูพูดได้" prompt
- [ ] Document in GitHub Issue
