#!/usr/bin/env python
"""
Flow Video Worker (Browser Tool + Signed URL Method)

This is the FIXED version that uses browser tool for UI interaction
and signed URL for download (bypasses headless download issues).

Usage:
  python flow_worker_browser_tool.py --prompt "..." --out "..."
"""

import argparse
import asyncio
import json
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
    HEARTBEAT_FILE.write_text(json.dumps(hb, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"HEARTBEAT: {stage} - {detail}")

async def run_browser_action(action: str, target_id: str = None, request_json: str = None, target_url: str = None) -> dict:
    """Run browser tool action via subprocess"""
    import subprocess
    
    # Build command
    cmd = ["openclaw", "browser", action, "--target", "host"]
    
    if target_id:
        cmd.extend(["--targetId", target_id])
    
    if target_url:
        cmd.extend(["--targetUrl", target_url])
    
    if request_json:
        cmd.extend(["--request", request_json])
    
    try:
        log(f"BROWSER_CMD: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.stdout:
            # Try to parse JSON
            try:
                return json.loads(result.stdout.strip())
            except:
                return {"raw": result.stdout}
        if result.stderr:
            return {"error": result.stderr}
        return {}
    except Exception as e:
        return {"error": str(e)}

async def create_flow_project(prompt: str) -> dict:
    """Create new Flow project with prompt using browser tool"""
    write_heartbeat("create_project", "opening Flow homepage")
    
    # Step 1: Open Flow homepage
    result = await run_browser_action("open", {
        "target": "host",
        "targetUrl": "https://labs.google/fx/th/tools/flow"
    })
    
    if "error" in result:
        write_heartbeat("create_project", f"failed to open Flow: {result['error']}", "E_BROWSER_OPEN")
        return {"success": False, "error": "E_BROWSER_OPEN"}
    
    target_id = result.get("targetId")
    if not target_id:
        write_heartbeat("create_project", "no targetId from browser open", "E_NO_TARGET")
        return {"success": False, "error": "E_NO_TARGET"}
    
    write_heartbeat("create_project", f"Flow opened: {target_id}")
    await asyncio.sleep(3)
    
    # Step 2: Get snapshot to find "à¹‚à¸›à¸£à¹€à¸ˆà¹‡à¸à¸•à¹Œà¹ƒà¸«à¸¡à¹ˆ" button
    write_heartbeat("create_project", "getting snapshot")
    snapshot_result = await run_browser_action("snapshot", {
        "target": "host",
        "targetId": target_id,
        "refs": "aria"
    })
    
    # Step 3: Click "à¹‚à¸›à¸£à¹€à¸ˆà¹‡à¸à¸•à¹Œà¹ƒà¸«à¸¡à¹ˆ" button
    write_heartbeat("create_project", "clicking new project button")
    
    # Use eval to click the button
    click_result = await run_browser_action("act", {
        "target": "host",
        "targetId": target_id,
        "request": json.dumps({
            "kind": "evaluate",
            "fn": """() => {
                const btn = [...document.querySelectorAll('button')].find(b => 
                    b.textContent.includes('à¹‚à¸›à¸£à¹€à¸ˆà¹‡à¸à¸•à¹Œà¹ƒà¸«à¸¡à¹ˆ') || 
                    b.textContent.includes('New Project')
                );
                if(btn) { btn.click(); return 'clicked'; }
                return 'not_found';
            }"""
        })
    })
    
    await asyncio.sleep(4)
    
    # Step 4: Find project link and click it
    write_heartbeat("create_project", "finding new project")
    
    project_result = await run_browser_action("act", {
        "target": "host",
        "targetId": target_id,
        "request": json.dumps({
            "kind": "evaluate",
            "fn": """() => {
                const links = [...document.querySelectorAll('a[href*="/project/"]')];
                if(links.length > 0) {
                    const href = links[0].href;
                    links[0].click();
                    return {clicked: true, href};
                }
                return {clicked: false, error: 'no_project_link'};
            }"""
        })
    })
    
    await asyncio.sleep(2)
    
    # Step 5: Click "à¹à¸à¹‰à¹„à¸‚à¹‚à¸›à¸£à¹€à¸ˆà¹‡à¸à¸•à¹Œ" if needed
    write_heartbeat("create_project", "entering composer")
    
    edit_result = await run_browser_action("act", {
        "target": "host",
        "targetId": target_id,
        "request": json.dumps({
            "kind": "evaluate",
            "fn": """() => {
                const editBtn = [...document.querySelectorAll('button')].find(b => 
                    b.textContent.includes('à¹à¸à¹‰à¹„à¸‚à¹‚à¸›à¸£à¹€à¸ˆà¹‡à¸à¸•à¹Œ') ||
                    b.textContent.includes('à¹€à¸£à¸´à¹ˆà¸¡')
                );
                if(editBtn) { editBtn.click(); return 'clicked_edit'; }
                return 'already_in_composer';
            }"""
        })
    })
    
    await asyncio.sleep(2)
    
    # Step 6: Enter prompt and generate
    write_heartbeat("create_project", "entering prompt")
    
    prompt_result = await run_browser_action("act", {
        "target": "host",
        "targetId": target_id,
        "request": json.dumps({
            "kind": "evaluate",
            "fn": f"""() => {{
                const textbox = document.querySelector('textarea[placeholder*="à¸„à¸¸à¸“à¸•à¹‰à¸­à¸‡à¸à¸²à¸£à¸ªà¸£à¹‰à¸²à¸‡à¸­à¸°à¹„à¸£"], input[placeholder*="à¸„à¸¸à¸“à¸•à¹‰à¸­à¸‡à¸à¸²à¸£à¸ªà¸£à¹‰à¸²à¸‡à¸­à¸°à¹„à¸£"]');
                if(textbox) {{
                    textbox.value = `{prompt}`;
                    textbox.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    
                    const genBtn = [...document.querySelectorAll('button')].find(b => 
                        b.textContent.includes('à¸ªà¸£à¹‰à¸²à¸‡') || b.textContent.includes('Generate')
                    );
                    if(genBtn) {{
                        genBtn.click();
                        return 'generating';
                    }}
                    return 'no_generate_button';
                }}
                return 'no_textbox';
            }}"""
        })
    })
    
    write_heartbeat("create_project", f"prompt entered: {prompt_result}")
    
    return {
        "success": True,
        "targetId": target_id,
        "project_created": True
    }

async def wait_for_generation(target_id: str, timeout_seconds: int = 300) -> dict:
    """Wait for video generation to complete"""
    start = time.time()
    write_heartbeat("wait_generation", f"waiting up to {timeout_seconds}s")
    
    while time.time() - start < timeout_seconds:
        await asyncio.sleep(15)
        elapsed = int(time.time() - start)
        write_heartbeat("wait_generation", f"still generating ({elapsed}s)")
        
        # Check if video is ready
        check_result = await run_browser_action("act", {
            "target": "host",
            "targetId": target_id,
            "request": json.dumps({
                "kind": "evaluate",
                "fn": """() => {
                    const video = document.querySelector('video');
                    if(video && video.src) {
                        return {ready: true, src: video.src, duration: video.duration};
                    }
                    return {ready: false};
                }"""
            })
        })
        
        if check_result.get("ready"):
            write_heartbeat("wait_generation", f"video ready! duration={check_result.get('duration')}s")
            return {"success": True, "video_src": check_result.get("src")}
    
    write_heartbeat("wait_generation", "timeout", "E_GEN_TIMEOUT")
    return {"success": False, "error": "E_GEN_TIMEOUT"}

async def download_video(target_id: str, output_path: str) -> dict:
    """Download video using signed URL from console"""
    write_heartbeat("download", "extracting signed URL")
    
    # Step 1: Get signed URL from video element
    url_result = await run_browser_action("act", {
        "target": "host",
        "targetId": target_id,
        "request": json.dumps({
            "kind": "evaluate",
            "fn": """() => {
                const video = document.querySelector('video');
                return video ? (video.currentSrc || video.src) : null;
            }"""
        })
    })
    
    video_url = url_result if isinstance(url_result, str) else url_result.get("result")
    
    if not video_url:
        write_heartbeat("download", "no video URL found", "E_NO_VIDEO_URL")
        return {"success": False, "error": "E_NO_VIDEO_URL"}
    
    write_heartbeat("download", f"video URL extracted: {video_url[:80]}...")
    
    # Step 2: Click download button to get GCS signed URL from console
    write_heartbeat("download", "clicking download button")
    
    download_click = await run_browser_action("act", {
        "target": "host",
        "targetId": target_id,
        "request": json.dumps({
            "kind": "evaluate",
            "fn": """() => {
                const downloadBtn = [...document.querySelectorAll('button')].find(b => 
                    b.textContent.includes('à¸”à¸²à¸§à¸™à¹Œà¹‚à¸«à¸¥à¸”') || b.textContent.includes('download')
                );
                if(downloadBtn) { downloadBtn.click(); return 'clicked'; }
                return 'not_found';
            }"""
        })
    })
    
    await asyncio.sleep(1)
    
    # Step 3: Click 720p option
    write_heartbeat("download", "selecting 720p")
    
    quality_click = await run_browser_action("act", {
        "target": "host",
        "targetId": target_id,
        "request": json.dumps({
            "kind": "evaluate",
            "fn": """() => {
                const items = [...document.querySelectorAll('[role="menuitem"]')];
                const target = items.find(i => i.textContent.includes('720p') || i.textContent.includes('Original'));
                if(target) { target.click(); return 'clicked_720p'; }
                return 'not_found';
            }"""
        })
    })
    
    await asyncio.sleep(2)
    
    # Step 4: Get console logs to extract GCS signed URL
    write_heartbeat("download", "getting console logs")
    
    console_result = await run_browser_action("console", {
        "target": "host",
        "targetId": target_id,
        "limit": 50
    })
    
    # Extract GCS signed URL from console
    import re
    gcs_pattern = re.compile(r'https://storage\.googleapis\.com/[^\s\'"<>,]+')
    
    signed_urls = []
    if "messages" in console_result:
        for msg in console_result["messages"]:
            text = msg.get("text", "")
            matches = gcs_pattern.findall(text)
            signed_urls.extend(matches)
    
    if not signed_urls:
        # Fallback: use video URL directly
        write_heartbeat("download", "no GCS URL in console, using video URL")
        signed_urls = [video_url]
    
    gcs_url = signed_urls[0]
    write_heartbeat("download", f"GCS URL: {gcs_url[:80]}...")
    
    # Step 5: Download using PowerShell Invoke-WebRequest
    write_heartbeat("download", "downloading with Invoke-WebRequest")
    
    ps_script = f"""
    $url = "{gcs_url}"
    $outPath = "{output_path}"
    try {{
        Invoke-WebRequest -Uri $url -OutFile $outPath -UseBasicParsing -TimeoutSec 120
        $size = (Get-Item $outPath).Length
        Write-Host "DOWNLOADED: $size bytes"
        
        # Verify MP4
        $header = Get-Content $outPath -Encoding Byte -TotalCount 12
        $isMp4 = [System.Text.Encoding]::ASCII.GetString($header[4..7]) -eq 'ftyp'
        Write-Host "MP4_VALID: $isMp4"
        
        if($isMp4 -and $size -gt 1000000) {{
            Write-Host "RESULT: success"
        }} else {{
            Write-Host "RESULT: failed"
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
        return {"success": True, "output": output_path}
    else:
        return {"success": False, "error": "E_DOWNLOAD_FAILED"}

async def main(prompt: str, output_path: str):
    log("ACK: flow_worker_browser_tool started")
    log(f"PROMPT: {prompt[:50]}...")
    log(f"OUTPUT: {output_path}")
    
    try:
        # Phase 1: Create project and generate
        result = await create_flow_project(prompt)
        if not result.get("success"):
            log(f"RESULT: failed - {result.get('error')}")
            return 1
        
        target_id = result["targetId"]
        await asyncio.sleep(2)
        
        # Phase 2: Wait for generation
        gen_result = await wait_for_generation(target_id)
        if not gen_result.get("success"):
            log(f"RESULT: failed - {gen_result.get('error')}")
            return 1
        
        # Phase 3: Download
        download_result = await download_video(target_id, output_path)
        if not download_result.get("success"):
            log(f"RESULT: failed - {download_result.get('error')}")
            return 1
        
        # Phase 4: Verify
        output_file = Path(output_path)
        if output_file.exists():
            size = output_file.stat().st_size
            log(f"OUTPUT: {output_path}")
            log(f"SIZE: {size} bytes ({size/1024/1024:.2f} MB)")
            log("RESULT: success")
            return 0
        else:
            log("RESULT: failed - file not found")
            return 1
            
    except Exception as e:
        log(f"ERROR: {e}")
        log("RESULT: failed - exception")
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flow Video Worker (Browser Tool Method)")
    parser.add_argument("--prompt", required=True, help="Video generation prompt")
    parser.add_argument("--out", required=True, help="Output file path")
    
    args = parser.parse_args()
    
    exit_code = asyncio.run(main(args.prompt, args.out))
    sys.exit(exit_code)

