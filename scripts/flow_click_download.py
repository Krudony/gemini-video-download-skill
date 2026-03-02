import argparse
import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

# ============================================================
# REVIEW NOTES (DO NOT DELETE) — quality comments for future readers
# ============================================================
# ✅ Good in this script:
# - Has explicit progress signals: ACK / HEARTBEAT / RESULT
# - Uses CDP fallback chain (env -> 18801 -> 18802)
# - Writes run-report JSON + artifacts (screenshot/html) on failures
# - Uses preflight wrapper externally to block bad runs early
# - Includes fallback download path when browser download event fails
#
# ⚠ Not good / risky areas:
# - Heartbeat here is stdout-only; chat relay must be handled by orchestrator
# - Selector fragility: Flow UI changes can break prompt/download locators
# - Long waits still depend on polling + fixed timeout windows
# - Mixed concerns in one file (connect, generate, download, reporting)
# - Hardcoded URLs/labels may need frequent maintenance
#
# 📌 Maintenance reminder:
# - If users report "silent run", fix orchestration relay (not only this script)
# - If E_INPUT_FIELD/E_COMPOSER_NOT_READY rises, update composer selectors first
# - Keep end-of-run contract: HEARTBEAT_STOP -> RESULT -> (optional CLEANUP_DONE)
# ============================================================

DEFAULT_CDP_CANDIDATES = [
    os.environ.get('FLOW_CDP_URL', '').strip(),
    'http://127.0.0.1:18801',
    'http://127.0.0.1:18802',
]


def ts() -> str:
    return datetime.now().strftime('%Y%m%d-%H%M%S')


def log_hb(stage: str, detail: str = ''):
    msg = f'HEARTBEAT stage={stage}'
    if detail:
        msg += f' detail={detail}'
    print(msg, flush=True)


def write_report(artifact_dir: Path, payload: dict):
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report = artifact_dir / f'run-report-{ts()}.json'
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'RUN_REPORT={report}', flush=True)


async def save_artifacts(page, artifact_dir: Path, tag: str):
    artifact_dir.mkdir(parents=True, exist_ok=True)
    png = artifact_dir / f'{ts()}-{tag}.png'
    html = artifact_dir / f'{ts()}-{tag}.html'
    saved = {'screenshot': None, 'html': None}
    try:
        await page.screenshot(path=str(png), full_page=True)
        html.write_text(await page.content(), encoding='utf-8')
        saved = {'screenshot': str(png), 'html': str(html)}
        print(f'ARTIFACT_SCREENSHOT={png}', flush=True)
        print(f'ARTIFACT_HTML={html}', flush=True)
    except Exception as e:
        print(f'ARTIFACT_ERROR={e}', flush=True)
    return saved


async def click_first(candidates):
    for c in candidates:
        try:
            if await c.count() > 0:
                await c.first.click(timeout=10000)
                return True
        except Exception:
            pass
    return False


async def open_new_project(page):
    log_hb('open_flow', 'navigating to Flow')
    await page.goto('https://labs.google/fx/tools/flow', wait_until='domcontentloaded')
    await page.wait_for_timeout(1800)

    # Dismiss overlays
    await click_first([
        page.get_by_role('button', name=re.compile(r'close|ปิด', re.I)),
        page.locator("button:has-text('close')"),
        page.locator("button[aria-label*='close' i]"),
    ])
    await page.wait_for_timeout(400)

    # Get current project count before creating new one
    before_count = await page.locator("a[href*='/project/']").count()
    log_hb('open_flow', f'project_count_before={before_count}')

    # Click "New Project" button - EXPANDED SELECTORS
    created = await click_first([
        page.get_by_role('button', name=re.compile(r'\+?\s*โปรเจ็กต์ใหม่|new project|เริ่มcreate|create with flow|create|new', re.I)),
        page.get_by_role('button', name=re.compile(r'create with flow|create', re.I)),
        page.get_by_text(re.compile(r'\+?\s*โปรเจ็กต์ใหม่|new project|create with flow|create', re.I)),
        page.locator("button:has-text('โปรเจ็กต์ใหม่')"),
        page.locator("button:has-text('new project')"),
        page.locator("button:has-text('create')"),
        page.get_by_role('link', name=re.compile(r'โปรเจ็กต์ใหม่|new project', re.I)),
        page.locator("a:has-text('โปรเจ็กต์ใหม่')"),
        page.locator("[role='button']:has-text('โปรเจ็กต์ใหม่')"),
    ])
    log_hb('open_flow', f'new_project_clicked={created}')
    
    if created:
        # Wait for page to refresh and new project to appear
        await page.wait_for_timeout(6000)
        
        # Try multiple selectors to find project link
        link_clicked = False
        for selector in [
            "a[href*='/project/']",
            "a[href*='/tools/flow/project']",
            "a[href*='/edit/']",
        ]:
            links = page.locator(selector)
            count = await links.count()
            if count > 0:
                try:
                    await links.first.click(timeout=10000)
                    log_hb('open_flow', f'clicked_project_link_selector={selector}')
                    link_clicked = True
                    await page.wait_for_timeout(3000)
                    break
                except Exception as e:
                    log_hb('open_flow', f'click_selector_failed={selector} error={e}')
        
        if not link_clicked:
            log_hb('open_flow', 'no_project_link_found_trying_dashboard_edit')
            # Fallback: try clicking any "แก้ไขโปรเจ็กต์" button on dashboard
            edit_btn = page.get_by_role('button', name=re.compile(r'^แก้ไขโปรเจ็กต์$|edit project', re.I))
            if await edit_btn.count() > 0:
                await edit_btn.first.click(timeout=10000)
                await page.wait_for_timeout(2000)


async def ensure_composer_ready(page):
    """Guarantee we are on a project composer page before finding prompt box."""
    await page.wait_for_timeout(1500)
    url = page.url or ''
    
    # If not on project page, try opening any visible project card/link
    if '/project/' not in url:
        opened = await click_first([
            page.locator("a[href*='/project/']"),
            page.get_by_role('link', name=re.compile(r'.*')),
        ])
        if opened:
            await page.wait_for_timeout(2000)
    
    url = page.url or ''
    # If on project dashboard (not edit mode), click "แก้ไขโปรเจ็กต์" or "เริ่ม" button
    if '/project/' in url and '/edit/' not in url:
        # Try "แก้ไขโปรเจ็กต์" button first (on dashboard list)
        edited = await click_first([
            page.get_by_role('button', name=re.compile(r'^แก้ไขโปรเจ็กต์$|edit project', re.I)),
            page.locator("button:has-text('แก้ไขโปรเจ็กต์')"),
        ])
        if not edited:
            # Fallback to "เริ่ม" button
            edited = await click_first([
                page.get_by_role('button', name=re.compile(r'^เริ่ม$|start', re.I)),
                page.locator("button:has-text('เริ่ม')"),
                page.get_by_text(re.compile(r'^เริ่ม$|start', re.I)),
            ])
        if edited:
            log_hb('ensure_composer', f'clicked_edit_button={edited}')
            await page.wait_for_timeout(2000)
    
    # Final check: must be on /edit/ URL and have prompt textbox
    url = page.url or ''
    if '/edit/' not in url:
        log_hb('ensure_composer', f'final_check_failed url={url}')
        return False
    
    # Composer marker: textbox with placeholder prompt
    has_prompt = await page.locator("text=คุณต้องการสร้างอะไร").count() > 0
    if not has_prompt:
        await page.wait_for_timeout(1000)
        has_prompt = await page.locator("text=คุณต้องการสร้างอะไร").count() > 0
    
    log_hb('ensure_composer', f'has_prompt={has_prompt}')
    return has_prompt


async def find_prompt_box(page):
    candidates = [
        page.locator("[contenteditable='true'][role='textbox']"),
        page.locator("[contenteditable='true'][aria-label*='prompt' i]"),
        page.locator("[contenteditable='true']"),
        page.get_by_role('textbox', name=re.compile(r'คุณต้องการสร้างอะไร|what do you want to create|prompt', re.I)),
        page.get_by_role('textbox'),
    ]

    for group in candidates:
        n = await group.count()
        for i in range(n - 1, -1, -1):
            b = group.nth(i)
            try:
                if not (await b.is_visible()) or not (await b.is_enabled()):
                    continue
                text = ((await b.inner_text()) or '').strip().lower()
                aria = ((await b.get_attribute('aria-label')) or '').strip().lower()
                if ('feb ' in text and '-' in text) or ('ข้อความที่แก้ไขได้' in aria):
                    continue
                return b
            except Exception:
                pass

    for fr in page.frames:
        try:
            group = fr.locator("[contenteditable='true'][role='textbox'], [contenteditable='true']")
            n = await group.count()
            for i in range(n - 1, -1, -1):
                b = group.nth(i)
                if await b.is_visible() and await b.is_enabled():
                    return b
        except Exception:
            pass
    return None


async def set_video_frames_x1(page):
    opened = await click_first([
        page.get_by_role('button', name=re.compile(r'วิดีโอ|video', re.I)),
    ])
    if not opened:
        return False

    await page.wait_for_timeout(500)
    await click_first([page.get_by_role('tab', name=re.compile(r'video', re.I))])
    await click_first([page.get_by_role('tab', name=re.compile(r'frames', re.I))])
    await click_first([page.get_by_role('tab', name=re.compile(r'^x1$', re.I))])
    await click_first([page.get_by_role('button', name=re.compile(r'วิดีโอ|video', re.I))])
    return True


async def wait_generation_with_heartbeat(page, timeout_sec: int = 900):
    """Poll for download button with heartbeat; fail fast on clear error."""
    start = asyncio.get_event_loop().time()
    next_hb = 45

    while True:
        elapsed = int(asyncio.get_event_loop().time() - start)
        if elapsed >= timeout_sec:
            return False, 'timeout'

        # Quick fail detector
        try:
            failed = page.locator('text=/ล้มเหลว|failed/i')
            if await failed.count() > 0:
                return False, 'generation_failed'
        except Exception:
            pass

        # Ready detector
        try:
            btn = page.locator('button:has-text("ดาวน์โหลด"), button:has-text("Download")')
            if await btn.count() > 0:
                return True, 'ready'
        except Exception:
            pass

        if elapsed >= next_hb:
            log_hb('generating', f'elapsed={elapsed}s waiting_download_button')
            next_hb += 45

        await page.wait_for_timeout(5000)


async def run_once(page, prompt: str, out: Path, artifact_dir: Path, report: dict):
    composer_ok = await ensure_composer_ready(page)
    if not composer_ok:
        report['error_code'] = 'E_COMPOSER_NOT_READY'
        report['error_detail'] = f'not in composer page, url={page.url}'
        report['artifacts'].append(await save_artifacts(page, artifact_dir, 'composer-not-ready'))
        return False

    box = await find_prompt_box(page)
    if not box:
        report['error_code'] = 'E_INPUT_FIELD'
        report['error_detail'] = f'prompt textbox not found, url={page.url}'
        report['artifacts'].append(await save_artifacts(page, artifact_dir, 'no-input-field'))
        return False

    log_hb('compose', 'filling prompt')
    await box.click()
    try:
        await box.fill(prompt)
    except Exception:
        await page.keyboard.press('Control+A')
        await page.keyboard.type(prompt, delay=8)

    mode_ok = await set_video_frames_x1(page)
    report['mode_set'] = mode_ok
    log_hb('compose', f'mode_set={mode_ok}')

    started = await click_first([
        page.get_by_role('button', name=re.compile(r'arrow_forward\s*สร้าง|สร้าง|generate|send', re.I)),
    ])
    if not started:
        report['error_code'] = 'E_START_BUTTON'
        report['error_detail'] = 'generate/start button not found'
        report['artifacts'].append(await save_artifacts(page, artifact_dir, 'no-start-button'))
        return False

    log_hb('generating', 'generation started')
    ok_ready, reason = await wait_generation_with_heartbeat(page, timeout_sec=900)
    if not ok_ready:
        report['error_code'] = 'E_GEN_TIMEOUT' if reason == 'timeout' else 'E_GEN_FAILED'
        report['error_detail'] = f'wait_download_button_failed:{reason}'
        report['artifacts'].append(await save_artifacts(page, artifact_dir, f'gen-{reason}'))
        return False

    log_hb('download', 'download button ready')
    if not await click_first([
        page.get_by_role('button', name=re.compile(r'ดาวน์โหลด|download', re.I)),
        page.locator('button:has-text("ดาวน์โหลด"), button:has-text("Download")'),
    ]):
        report['error_code'] = 'E_DOWNLOAD_MENU'
        report['error_detail'] = 'download menu button not found'
        report['artifacts'].append(await save_artifacts(page, artifact_dir, 'no-download-menu'))
        return False

    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with page.expect_download(timeout=180000) as dl_info:
            picked = await click_first([
                page.get_by_role('menuitem', name=re.compile(r'720p|original', re.I)),
                page.get_by_text(re.compile(r'720p|original', re.I)),
            ])
            if not picked:
                raise RuntimeError('720p option not found')

        dl = await dl_info.value
        await dl.save_as(str(out))
        report['size'] = out.stat().st_size
        report['download_url'] = dl.url
        print(f'OUT={out}', flush=True)
        print(f'SIZE={out.stat().st_size}', flush=True)
        log_hb('download', f'saved={out.name} size={out.stat().st_size}')
        return True
    except Exception as e:
        # Fallback: direct fetch from video element src/resource url
        try:
            media_url = await page.evaluate("""
              () => {
                const v = document.querySelector('video');
                const src = v ? (v.currentSrc || v.src || '') : '';
                return src || '';
              }
            """)
            if media_url and str(media_url).startswith('http'):
                import urllib.request
                with urllib.request.urlopen(str(media_url), timeout=120) as r:
                    data = r.read()
                out.write_bytes(data)
                report['size'] = out.stat().st_size
                report['download_url'] = str(media_url)
                print(f'OUT={out}', flush=True)
                print(f'SIZE={out.stat().st_size}', flush=True)
                log_hb('download', f'fallback_saved={out.name} size={out.stat().st_size}')
                return True
        except Exception:
            pass

        report['error_code'] = 'E_DOWNLOAD'
        report['error_detail'] = str(e)
        report['artifacts'].append(await save_artifacts(page, artifact_dir, 'download-fail'))
        return False


async def connect_browser_with_fallback(playwright, report: dict):
    errs = []
    for cdp in [x for x in DEFAULT_CDP_CANDIDATES if x]:
        try:
            log_hb('connect', f'trying_cdp={cdp}')
            browser = await playwright.chromium.connect_over_cdp(cdp)
            report['cdp'] = cdp
            log_hb('connect', f'connected_cdp={cdp}')
            return browser
        except Exception as e:
            errs.append(f'{cdp}: {e}')
            log_hb('connect', f'failed_cdp={cdp}')
    raise RuntimeError(' | '.join(errs) if errs else 'No CDP endpoints available')


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prompt', required=True)
    ap.add_argument('--out', default=r'D:\Gemini-Downloads\flow-video-720p.mp4')
    ap.add_argument('--retries', type=int, default=3)
    ap.add_argument('--artifact-dir', default=r'D:\Gemini-Downloads\artifacts')
    args = ap.parse_args()

    out = Path(args.out)
    artifact_dir = Path(args.artifact_dir)
    report = {
        'script': 'flow_click_download.py',
        'status': 'running',
        'error_code': None,
        'error_detail': None,
        'cdp': None,
        'retries': args.retries,
        'attempt': 0,
        'artifacts': []
    }

    print('ACK: started flow video pipeline', flush=True)

    try:
        async with async_playwright() as p:
            browser = await connect_browser_with_fallback(p, report)
            if not browser.contexts:
                raise RuntimeError('No browser context')
            page = browser.contexts[0].pages[0] if browser.contexts[0].pages else await browser.contexts[0].new_page()

            for i in range(1, args.retries + 1):
                report['attempt'] = i
                log_hb('attempt', f'index={i}/{args.retries}')
                created = await open_new_project(page)
                if not created:
                    report['error_code'] = 'E_FLOW_CREATE'
                    report['error_detail'] = 'cannot open/create new project'
                    report['artifacts'].append(await save_artifacts(page, artifact_dir, f'create-fail-{i}'))
                    continue

                await page.wait_for_timeout(1500)
                ok = await run_once(page, args.prompt, out, artifact_dir, report)
                if ok:
                    report['status'] = 'success'
                    write_report(artifact_dir, report)
                    print('HEARTBEAT_STOP', flush=True)
                    print('RESULT: success', flush=True)
                    return

            report['status'] = 'failed'
            write_report(artifact_dir, report)
            print(f"ERROR_CODE={report.get('error_code')}", flush=True)
            print(f"ERROR_DETAIL={report.get('error_detail')}", flush=True)
            print('HEARTBEAT_STOP', flush=True)
            print('RESULT: failed', flush=True)
            print('ORIGINAL_VIDEO_REQUIRED: flow pipeline failed after retries', flush=True)
            raise SystemExit(2)

    except Exception as e:
        report['status'] = 'failed'
        report['error_code'] = 'E_PROFILE_DOWN'
        report['error_detail'] = str(e)
        write_report(artifact_dir, report)
        print('ERROR_CODE=E_PROFILE_DOWN', flush=True)
        print(f'ERROR_DETAIL={e}', flush=True)
        print('HEARTBEAT_STOP', flush=True)
        print('RESULT: failed', flush=True)
        print('ORIGINAL_VIDEO_REQUIRED: profile/cdp unavailable', flush=True)
        raise SystemExit(2)


if __name__ == '__main__':
    asyncio.run(main())
