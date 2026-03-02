#!/usr/bin/env python
"""
Flow Video Worker (OpenClaw Browser CLI Method)

Uses openclaw browser CLI commands directly for reliable UI automation.

Usage:
  python flow_worker_openclaw_cli.py --prompt "..." --out "..."
"""

import argparse
import asyncio
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ARTIFACT_DIR = Path("D:/Gemini-Downloads/artifacts")
HEARTBEAT_FILE = ARTIFACT_DIR / "flow-heartbeat.json"

def ts() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def log(msg: str):
    print(msg, flush=True)

def write_heartbeat(stage: str, detail: str, error_code: str = None):
    hb = {
        "timestamp": datetime.now().isoformat(),
        "stage": stage,
        "detail": detail,
        "error_code": error_code
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        HEARTBEAT_FILE.write_text(json.dumps(hb, ensure_ascii=False, indent=2), encoding="utf-8")
    except:
        pass
    log(f"HEARTBEAT: {stage} - {detail}")

def run_cli(cmd_list: list, timeout: int = 60) -> tuple:
    """Run openclaw browser CLI command via PowerShell, return (success, output_json, error)"""
    try:
        # Wrap in PowerShell because openclaw is a .ps1 script
        ps_cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-Command"] + cmd_list
        log(f"CLI: {' '.join(ps_cmd)}")
        
        result = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=timeout)
        
        output = result.stdout.strip()
        error = result.stderr.strip()
        
        # Try to parse JSON output
        try:
            data = json.loads(output) if output else {}
            return (True, data, error)
        except:
            return (True, {"raw": output}, error)
            
    except subprocess.TimeoutExpired:
        return (False, {}, "timeout")
    except Exception as e:
        return (False, {}, str(e))

async def wait_for_ref(page_ref: str = None, contains_text: str = None, timeout_sec: int = 10) -> str:
    """Wait for element to appear, return ref"""
    start = time.time()
    while time.time() - start < timeout_sec:
        success, data, error = run_cli([
            "openclaw", "browser", "snapshot", "--refs", "aria"
        ])
        
        if success and "elements" in data:
            # Simple check
            raw = str(data)
            if contains_text and contains_text in raw:
                # Extract ref (simplified)
                match = re.search(r'\[ref=(e\d+)\]', raw)
                if match:
                    return match.group(1)
        
        await asyncio.sleep(1)
    
    return None

async def main(prompt: str, output_path: str):
    log("ACK: flow_worker_openclaw_cli started")
    log(f"PROMPT: {prompt[:50]}...")
    log(f"OUTPUT: {output_path}")
    
    target_id = None  # Store the browser tab ID
    
    try:
        # Phase 1: Open Flow
        write_heartbeat("open_flow", "navigating to Flow homepage")
        
        success, data, error = run_cli([
            "openclaw", "browser", "open",
            "https://labs.google/fx/th/tools/flow"
        ])
        
        if not success or error:
            write_heartbeat("open_flow", f"failed: {error}", "E_OPEN_FLOW")
            log(f"RESULT: failed - E_OPEN_FLOW")
            return 1
        
        # Extract target ID from output
        raw_output = data.get("raw", "")
        id_match = re.search(r'id: ([A-F0-9]+)', raw_output, re.IGNORECASE)
        if id_match:
            target_id = id_match.group(1)
            log(f"Target ID: {target_id}")
        else:
            log("Warning: Could not extract target ID from output")
        
        log(f"Flow opened: {data}")
        
        # Wait for page to fully load
        log("Waiting 8 seconds for page load...")
        await asyncio.sleep(8)
        
        # Also wait for load state
        if target_id:
            run_cli(["openclaw", "browser", "wait", "--targetId", target_id, "--load-state", "domcontentloaded"])
        await asyncio.sleep(2)
        
        # Phase 2: Get snapshot and find "à¹‚à¸›à¸£à¹€à¸ˆà¹‡à¸à¸•à¹Œ à¹ƒà¸«à¸¡à¹ˆ" button
        write_heartbeat("find_new_project", "taking snapshot")
        
        cmd = ["openclaw", "browser", "snapshot", "--refs", "aria", "--limit", "500"]
        if target_id:
            cmd.extend(["--targetId", target_id])
        
        success, snapshot, error = run_cli(cmd)
        
        if not success:
            write_heartbeat("find_new_project", f"snapshot failed: {error}", "E_SNAPSHOT")
            return 1
        
        # Convert to string and check for content
        snapshot_text = str(snapshot)
        log(f"Snapshot length: {len(snapshot_text)} chars")
        
        if len(snapshot_text) < 50 or snapshot_text == "{}":
            write_heartbeat("find_new_project", "snapshot empty - page may not be loaded", "E_EMPTY_SNAPSHOT")
            log("Snapshot is empty - waiting longer and retrying...")
            await asyncio.sleep(5)
            # Retry snapshot
            success, snapshot, error = run_cli([
                "openclaw", "browser", "snapshot", "--refs", "aria", "--limit", "500"
            ])
            snapshot_text = str(snapshot)
            log(f"Retry snapshot length: {len(snapshot_text)} chars")
        
        # Find new project button (look for "à¹‚à¸›à¸£à¹€à¸ˆà¹‡à¸à¸•à¹Œ" in any form)
        new_project_ref = None
        
        # Try multiple patterns
        patterns = [
            r'button.*?"à¹‚à¸›à¸£à¹€à¸ˆà¹‡à¸à¸•à¹Œ à¹ƒà¸«à¸¡à¹ˆ".*?\[ref=(e\d+)\]',
            r'button.*?"à¹‚à¸›à¸£à¹€à¸ˆà¹‡à¸à¸•à¹Œà¹ƒà¸«à¸¡à¹ˆ".*?\[ref=(e\d+)\]',
            r'button.*?à¹‚à¸›à¸£à¹€à¸ˆà¹‡à¸à¸•à¹Œ.*?\[ref=(e\d+)\]',
            r'\[ref=(e\d+)\].*?button.*?à¹‚à¸›à¸£à¹€à¸ˆà¹‡à¸à¸•à¹Œ',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, snapshot_text, re.IGNORECASE)
            if match:
                new_project_ref = match.group(1)
                log(f"Found with pattern {pattern}: ref={new_project_ref}")
                break
        
        if not new_project_ref:
            # Last resort: look for any button with "New" or "Create"
            en_match = re.search(r'button.*?(?:New Project|Create).*?\[ref=(e\d+)\]', snapshot_text, re.IGNORECASE)
            if en_match:
                new_project_ref = en_match.group(1)
                log(f"Found English button: ref={new_project_ref}")
        
        if not new_project_ref:
            write_heartbeat("find_new_project", "could not find new project button", "E_NO_NEW_PROJECT_BTN")
            log(f"Snapshot preview (first 1000 chars): {snapshot_text[:1000]}")
            return 1
        
        log(f"Found new project button: ref={new_project_ref}")
        
        # Phase 3: Click new project
        write_heartbeat("click_new_project", f"clicking ref={new_project_ref}")
        
        success, data, error = run_cli([
            "openclaw", "browser", "click", new_project_ref
        ])
        
        if error:
            write_heartbeat("click_new_project", f"click failed: {error}", "E_CLICK")
        
        await asyncio.sleep(4)
        
        # Phase 4: Get snapshot again to find project link
        write_heartbeat("find_project", "taking snapshot after click")
        
        success, snapshot2, error = run_cli([
            "openclaw", "browser", "snapshot", "--refs", "aria"
        ])
        
        snapshot2_text = str(snapshot2)
        
        # Find project link (look for /project/ in URL)
        project_match = re.search(r'link.*?\[ref=(e\d+)\].*?/project/', snapshot2_text, re.IGNORECASE)
        project_ref = project_match.group(1) if project_match else None
        
        if not project_ref:
            write_heartbeat("find_project", "no project link found", "E_NO_PROJECT")
            log("Could not find project link")
            return 1
        
        log(f"Found project link: ref={project_ref}")
        
        # Phase 5: Click project to open
        write_heartbeat("open_project", f"clicking project ref={project_ref}")
        
        success, data, error = run_cli([
            "openclaw", "browser", "click", project_ref
        ])
        
        await asyncio.sleep(2)
        
        # Phase 6: Find and click edit/composer button
        write_heartbeat("enter_composer", "finding edit button")
        
        success, snapshot3, error = run_cli([
            "openclaw", "browser", "snapshot", "--refs", "aria"
        ])
        
        snapshot3_text = str(snapshot3)
        
        # Look for "à¹à¸à¹‰à¹„à¸‚à¹‚à¸›à¸£à¹€à¸ˆà¹‡à¸à¸•à¹Œ" or "à¹€à¸£à¸´à¹ˆà¸¡" button
        edit_match = re.search(r'button.*?(?:à¹à¸à¹‰à¹„à¸‚à¹‚à¸›à¸£à¹€à¸ˆà¹‡à¸à¸•à¹Œ|à¹€à¸£à¸´à¹ˆà¸¡).*?\[ref=(e\d+)\]', snapshot3_text, re.IGNORECASE)
        edit_ref = edit_match.group(1) if edit_match else None
        
        if edit_ref:
            log(f"Found edit button: ref={edit_ref}")
            success, data, error = run_cli([
                "openclaw", "browser", "click", edit_ref
            ])
            await asyncio.sleep(2)
        
        # Phase 7: Enter prompt
        write_heartbeat("enter_prompt", "finding prompt textbox")
        
        success, snapshot4, error = run_cli([
            "openclaw", "browser", "snapshot", "--refs", "aria"
        ])
        
        snapshot4_text = str(snapshot4)
        
        # Find textbox with placeholder "à¸„à¸¸à¸“à¸•à¹‰à¸­à¸‡à¸à¸²à¸£à¸ªà¸£à¹‰à¸²à¸‡à¸­à¸°à¹„à¸£"
        textbox_match = re.search(r'textbox.*?\[ref=(e\d+)\]', snapshot4_text, re.IGNORECASE)
        textbox_ref = textbox_match.group(1) if textbox_match else None
        
        if not textbox_ref:
            write_heartbeat("enter_prompt", "no textbox found", "E_NO_TEXTBOX")
            return 1
        
        log(f"Found textbox: ref={textbox_ref}")
        
        # Type prompt (escape for CLI)
        safe_prompt = prompt.replace('"', '\\"').replace('\\', '\\\\')
        
        success, data, error = run_cli([
            "openclaw", "browser", "type", textbox_ref, safe_prompt
        ])
        
        await asyncio.sleep(1)
        
        # Phase 8: Click generate button
        write_heartbeat("generate", "clicking generate button")
        
        success, snapshot5, error = run_cli([
            "openclaw", "browser", "snapshot", "--refs", "aria"
        ])
        
        snapshot5_text = str(snapshot5)
        
        # Find "à¸ªà¸£à¹‰à¸²à¸‡" or "Generate" button
        gen_match = re.search(r'button.*?(?:à¸ªà¸£à¹‰à¸²à¸‡|Generate).*?\[ref=(e\d+)\]', snapshot5_text, re.IGNORECASE)
        gen_ref = gen_match.group(1) if gen_match else None
        
        if gen_ref:
            log(f"Found generate button: ref={gen_ref}")
            success, data, error = run_cli([
                "openclaw", "browser", "click", gen_ref
            ])
        else:
            write_heartbeat("generate", "no generate button found", "E_NO_GEN_BTN")
        
        # Phase 9: Wait for generation
        write_heartbeat("wait_generation", "waiting for video (up to 5 min)")
        
        max_wait = 300  # 5 minutes
        start_wait = time.time()
        video_ready = False
        
        while time.time() - start_wait < max_wait:
            await asyncio.sleep(15)
            elapsed = int(time.time() - start_wait)
            write_heartbeat("wait_generation", f"waiting... ({elapsed}s)")
            
            # Check for video element
            success, snap_vid, error = run_cli([
                "openclaw", "browser", "snapshot", "--refs", "aria"
            ])
            
            snap_vid_text = str(snap_vid)
            
            # Look for video or progress complete
            if 'video' in snap_vid_text.lower() or 'à¸žà¸£à¹‰à¸­à¸¡' in snap_vid_text or 'ready' in snap_vid_text.lower():
                video_ready = True
                log("Video generation complete!")
                break
        
        if not video_ready:
            write_heartbeat("wait_generation", "timeout", "E_GEN_TIMEOUT")
            log("RESULT: failed - E_GEN_TIMEOUT")
            return 1
        
        # Phase 10: Get console logs for signed URL
        write_heartbeat("extract_url", "getting console logs")
        
        success, console_data, error = run_cli([
            "openclaw", "browser", "console", "--limit", "50"
        ])
        
        console_text = str(console_data)
        
        # Extract GCS signed URL
        gcs_pattern = re.compile(r'https://storage\.googleapis\.com/[^\s\'"<>,)]+')
        gcs_urls = gcs_pattern.findall(console_text)
        
        if not gcs_urls:
            write_heartbeat("extract_url", "no GCS URL found in console", "E_NO_GCS_URL")
            # Fallback: try to get video src via evaluate
            log("Trying fallback: evaluate video.src")
            success, eval_data, error = run_cli([
                "openclaw", "browser", "evaluate",
                "--fn", "() => document.querySelector('video')?.src || document.querySelector('video')?.currentSrc"
            ])
            if success and eval_data.get("result"):
                gcs_urls = [eval_data["result"]]
        
        if not gcs_urls:
            write_heartbeat("extract_url", "no video URL found at all", "E_NO_VIDEO_URL")
            log("RESULT: failed - E_NO_VIDEO_URL")
            return 1
        
        gcs_url = gcs_urls[0]
        log(f"Got GCS URL: {gcs_url[:80]}...")
        
        # Phase 11: Download with PowerShell
        write_heartbeat("download", "downloading with Invoke-WebRequest")
        
        ps_script = f"""
        $url = "{gcs_url}"
        $outPath = "{output_path}"
        try {{
            Invoke-WebRequest -Uri $url -OutFile $outPath -UseBasicParsing -TimeoutSec 120
            $size = (Get-Item $outPath).Length
            Write-Host "DOWNLOADED: $size bytes"
            
            $header = Get-Content $outPath -Encoding Byte -TotalCount 12
            $isMp4 = [System.Text.Encoding]::ASCII.GetString($header[4..7]) -eq 'ftyp'
            Write-Host "MP4_VALID: $isMp4"
            
            if($isMp4 -and $size -gt 1000000) {{
                Write-Host "RESULT: success"
            }} else {{
                Write-Host "RESULT: failed - invalid file"
            }}
        }} catch {{
            Write-Host "ERROR: $_"
            Write-Host "RESULT: failed"
        }}
        """
        
        ps_result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        log(ps_result.stdout)
        if ps_result.stderr:
            log(f"STDERR: {ps_result.stderr}")
        
        if "RESULT: success" in ps_result.stdout:
            output_file = Path(output_path)
            size = output_file.stat().st_size
            log(f"OUTPUT: {output_path}")
            log(f"SIZE: {size} bytes ({size/1024/1024:.2f} MB)")
            log("RESULT: success")
            return 0
        else:
            log("RESULT: failed - download issue")
            return 1
            
    except Exception as e:
        log(f"ERROR: {e}")
        log("RESULT: failed - exception")
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    
    exit_code = asyncio.run(main(args.prompt, args.out))
    sys.exit(exit_code)

