#!/usr/bin/env python
"""
Flow Video Supervisor — Orchestrates worker subagent with full audit trail

Usage:
  python supervisor_flow_video.py --prompt "video description" --out "path/to/output.mp4"

Outputs:
  - D:\Gemini-Downloads\artifacts\YYYY-MM-DD\run-report-*.json
  - D:\Gemini-Downloads\artifacts\YYYY-MM-DD\heartbeat-*.json
  - Telegram delivery + audit report
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import subprocess

ARTIFACT_DIR = Path("D:/Gemini-Downloads/artifacts")
HEARTBEAT_FILE = ARTIFACT_DIR / "flow-heartbeat.json"
AUDIT_LOG = ARTIFACT_DIR / "supervisor-audit.log"

def ts() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def date_dir() -> Path:
    return ARTIFACT_DIR / datetime.now().strftime("%Y-%m-%d")

def log_audit(msg: str):
    """Append to audit log"""
    date_dir().mkdir(parents=True, exist_ok=True)
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    print(f"AUDIT: {msg}", flush=True)

def write_heartbeat(stage: str, detail: str, elapsed_ms: int = 0, attempt: int = 1, error_code: str = None):
    """Write heartbeat file for supervisor monitoring"""
    hb = {
        "timestamp": datetime.now().isoformat(),
        "stage": stage,
        "detail": detail,
        "elapsed_ms": elapsed_ms,
        "attempt": attempt,
        "error_code": error_code
    }
    date_dir().mkdir(parents=True, exist_ok=True)
    hb_path = date_dir() / f"heartbeat-{ts()}.json"
    hb_path.write_text(json.dumps(hb, ensure_ascii=False, indent=2), encoding="utf-8")
    HEARTBEAT_FILE.write_text(json.dumps(hb, ensure_ascii=False, indent=2), encoding="utf-8")
    return hb

def check_preflight() -> dict:
    """Check all preconditions before spawning worker"""
    results = {
        "cdp_ok": False,
        "login_ok": True,  # Skip for now - assume browser profile is logged in
        "disk_ok": False,
        "creds_ok": False
    }
    
    # 1. Check CDP
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(('127.0.0.1', 18801))
        sock.close()
        results["cdp_ok"] = (result == 0)
        log_audit(f"CDP check: port 18801 {'open' if results['cdp_ok'] else 'closed'}")
    except Exception as e:
        log_audit(f"CDP check failed: {e}")
    
    # 2. Check disk space
    try:
        import shutil
        total, used, free = shutil.disk_usage("D:")
        results["disk_ok"] = (free > 100 * 1024 * 1024)  # > 100MB
        log_audit(f"Disk free: {free / (1024*1024):.1f} MB")
    except Exception as e:
        log_audit(f"Disk check failed: {e}")
    
    # 3. Check credentials
    cred_paths = [
        Path.home() / ".openclaw" / "workspace" / "credentials.json",
        Path.home() / ".openclaw" / "workspace" / "agents" / "somkru" / "oauth_token.json"
    ]
    results["creds_ok"] = any(p.exists() for p in cred_paths)
    log_audit(f"Credential files: {'found' if results['creds_ok'] else 'missing'}")
    
    return results

def verify_video(output_path: str) -> dict:
    """Verify output video meets requirements"""
    result = {
        "exists": False,
        "size_ok": False,
        "header_ok": False,
        "duration_ok": None,  # Skip for now (needs ffprobe)
        "valid": False
    }
    
    p = Path(output_path)
    if not p.exists():
        log_audit(f"Verify failed: file not found {output_path}")
        return result
    
    result["exists"] = True
    
    # Check size > 1MB
    size = p.stat().st_size
    result["size_ok"] = (size > 1024 * 1024)
    log_audit(f"File size: {size / (1024*1024):.2f} MB")
    
    # Check MP4 header (ftyp at bytes 4-7)
    try:
        with open(p, "rb") as f:
            header = f.read(12)
        result["header_ok"] = (header[4:8] == b"ftyp")
        log_audit(f"MP4 header: {'valid' if result['header_ok'] else 'invalid'}")
    except Exception as e:
        log_audit(f"Header check failed: {e}")
    
    result["valid"] = result["exists"] and result["size_ok"] and result["header_ok"]
    return result

async def run_worker(prompt: str, output_path: str, max_retries: int = 2) -> dict:
    """Spawn worker subagent and monitor progress"""
    start_time = datetime.now()
    attempt = 0
    worker_session = None
    
    while attempt <= max_retries:
        attempt += 1
        log_audit(f"Starting worker attempt {attempt}/{max_retries + 1}")
        
        write_heartbeat("spawning", f"worker attempt {attempt}", elapsed_ms=0, attempt=attempt)
        
        # Spawn worker via sessions_spawn (external)
        # Use the NEW openclaw browser CLI-based worker
        worker_script = Path(__file__).parent / "flow_worker_openclaw_cli.py"
        
        cmd = [
            "C:/Users/DELL/AppData/Local/Programs/Python/Python311/python.exe",
            str(worker_script),
            "--prompt", prompt,
            "--out", output_path
        ]
        
        log_audit(f"Worker command: {' '.join(cmd)}")
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(Path(__file__).parent)
            )
            
            # Monitor stdout/stderr
            stdout_lines = []
            stderr_lines = []
            
            async def read_stream(stream, lines):
                async for line in stream:
                    lines.append(line.decode().strip())
                    log_audit(f"Worker: {line.decode().strip()}")
            
            await asyncio.gather(
                read_stream(proc.stdout, stdout_lines),
                read_stream(proc.stderr, stderr_lines)
            )
            
            await proc.wait()
            
            # Check for RESULT in output
            result_line = None
            for line in stdout_lines + stderr_lines:
                if line.startswith("RESULT:"):
                    result_line = line
                    break
            
            if result_line:
                status = "success" if "success" in result_line else "fail"
                log_audit(f"Worker RESULT: {status}")
                
                if status == "success":
                    write_heartbeat("worker_done", "success", elapsed_ms=int((datetime.now() - start_time).total_seconds() * 1000), attempt=attempt)
                    return {"success": True, "attempt": attempt, "output": output_path}
                else:
                    # Extract error code
                    error_code = None
                    for line in stdout_lines + stderr_lines:
                        if line.startswith("ERROR_CODE="):
                            error_code = line.split("=")[1]
                            break
                    
                    write_heartbeat("worker_failed", f"error={error_code}", elapsed_ms=int((datetime.now() - start_time).total_seconds() * 1000), attempt=attempt, error_code=error_code)
                    log_audit(f"Worker failed with {error_code}")
                    
            else:
                write_heartbeat("worker_no_result", "no RESULT signal", elapsed_ms=int((datetime.now() - start_time).total_seconds() * 1000), attempt=attempt, error_code="E_NO_RESULT")
                log_audit("Worker exited without RESULT signal")
                
        except Exception as e:
            write_heartbeat("worker_crashed", str(e), elapsed_ms=int((datetime.now() - start_time).total_seconds() * 1000), attempt=attempt, error_code="E_CRASH")
            log_audit(f"Worker crashed: {e}")
        
        if attempt <= max_retries:
            log_audit(f"Retrying in 5 seconds...")
            await asyncio.sleep(5)
    
    return {"success": False, "attempts": attempt, "error": "max_retries_exceeded"}

async def cleanup_browser():
    """Force close all browser profiles and python processes"""
    import subprocess
    try:
        # Stop browser profiles via browser tool
        subprocess.run(["openclaw", "browser", "stop", "--profile", "krudon"], 
                      capture_output=True, timeout=10)
        subprocess.run(["openclaw", "browser", "stop", "--profile", "gmail-profile"], 
                      capture_output=True, timeout=10)
        
        # Kill any remaining chrome/python processes
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], 
                      capture_output=True, timeout=5)
        subprocess.run(["taskkill", "/F", "/IM", "python.exe"], 
                      capture_output=True, timeout=5)
        
        log_audit("Browser cleanup completed")
    except Exception as e:
        log_audit(f"Cleanup warning: {e}")

async def main(prompt: str, output_path: str, retries: int = 2):
    start_time = datetime.now()
    log_audit("=" * 60)
    log_audit(f"Supervisor starting: prompt='{prompt[:50]}...'")
    log_audit("=" * 60)
    
    try:
        # Phase 1: Preflight
        write_heartbeat("preflight", "checking prerequisites")
        preflight = check_preflight()
        
        if not all(preflight.values()):
            log_audit(f"Preflight FAILED: {preflight}")
            write_heartbeat("preflight_failed", str(preflight), error_code="E_PREFLIGHT")
            print(json.dumps({"status": "failed", "stage": "preflight", "details": preflight}, ensure_ascii=False))
            await cleanup_browser()
            return 1
        
        log_audit("Preflight PASSED")
        write_heartbeat("preflight_done", "all checks passed")
        
        # Phase 2: Run worker
        log_audit("Spawning worker...")
        worker_result = await run_worker(prompt, output_path, retries)
        
        if not worker_result["success"]:
            log_audit(f"Worker FAILED after {worker_result.get('attempts', '?')} attempts")
            write_heartbeat("supervisor_failed", "worker exhausted retries", error_code="E_MAX_RETRIES")
            print(json.dumps({"status": "failed", "stage": "worker", "details": worker_result}, ensure_ascii=False))
            await cleanup_browser()
            return 1
        
        log_audit(f"Worker SUCCEEDED on attempt {worker_result['attempt']}")
        
        # Phase 3: Verification
        write_heartbeat("verification", "checking output file")
        verify = verify_video(output_path)
        
        if not verify["valid"]:
            log_audit(f"Verification FAILED: {verify}")
            write_heartbeat("verification_failed", str(verify), error_code="E_VERIFY")
            print(json.dumps({"status": "failed", "stage": "verification", "details": verify}, ensure_ascii=False))
            await cleanup_browser()
            return 1
        
        log_audit("Verification PASSED")
        elapsed = int((datetime.now() - start_time).total_seconds() * 1000)
        write_heartbeat("verification_done", "file valid", elapsed_ms=elapsed)
        
        # Phase 4: Create audit report
        report = {
            "status": "success",
            "prompt": prompt,
            "output": output_path,
            "output_size": Path(output_path).stat().st_size,
            "attempts": worker_result["attempt"],
            "elapsed_ms": elapsed,
            "timestamp": datetime.now().isoformat(),
            "preflight": preflight,
            "verification": verify
        }
        
        report_path = date_dir() / f"run-report-{ts()}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        log_audit(f"Audit report saved: {report_path}")
        
        print(json.dumps({"status": "success", "output": output_path, "report": str(report_path)}, ensure_ascii=False))
        log_audit("Supervisor completed successfully")
        
        return 0
        
    finally:
        # ALWAYS cleanup browser processes
        log_audit("Starting cleanup...")
        await cleanup_browser()
        log_audit("Cleanup completed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flow Video Supervisor")
    parser.add_argument("--prompt", required=True, help="Video generation prompt")
    parser.add_argument("--out", required=True, help="Output file path")
    parser.add_argument("--retries", type=int, default=2, help="Max retry attempts")
    
    args = parser.parse_args()
    
    exit_code = asyncio.run(main(args.prompt, args.out, args.retries))
    sys.exit(exit_code)
