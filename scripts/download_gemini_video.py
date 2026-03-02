import argparse
import asyncio
import base64
import json
import os
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

CDP = os.environ.get('FLOW_CDP_URL', 'http://127.0.0.1:18801')  # krudon default

JS_FETCH_VIDEO = r'''
async () => {
  const candidates = Array.from(document.querySelectorAll('video'));
  const v = candidates.find(x => (x.currentSrc || x.src)) || candidates[0];
  const src = v?.currentSrc || v?.src;
  if (!src) return {ok:false, error:'no video src'};

  const r = await fetch(src, {credentials:'include'});
  const ab = await r.arrayBuffer();
  const bytes = new Uint8Array(ab);
  let bin = '';
  const chunk = 0x8000;
  for (let i=0; i<bytes.length; i+=chunk) {
    bin += String.fromCharCode(...bytes.subarray(i, i+chunk));
  }
  const b64 = btoa(bin);
  const head = Array.from(bytes.slice(0,16)).map(x=>x.toString(16).padStart(2,'0')).join(' ');
  return {ok:true, status:r.status, type:r.headers.get('content-type'), len:bytes.length, head, b64, src};
}
'''


def ts() -> str:
  return datetime.now().strftime('%Y%m%d-%H%M%S')


def write_report(artifact_dir: Path, payload: dict):
  artifact_dir.mkdir(parents=True, exist_ok=True)
  report = artifact_dir / f'run-report-{ts()}.json'
  report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
  print(f'RUN_REPORT={report}')


async def save_artifacts(page, artifact_dir: Path, tag: str):
  artifact_dir.mkdir(parents=True, exist_ok=True)
  stamp = ts()
  png = artifact_dir / f'{stamp}-{tag}.png'
  html = artifact_dir / f'{stamp}-{tag}.html'
  saved = {'screenshot': None, 'html': None}
  try:
    await page.screenshot(path=str(png), full_page=True)
    html.write_text(await page.content(), encoding='utf-8')
    print(f'ARTIFACT_SCREENSHOT={png}')
    print(f'ARTIFACT_HTML={html}')
    saved['screenshot'] = str(png)
    saved['html'] = str(html)
  except Exception as e:
    print(f'ARTIFACT_ERROR={e}')
  return saved


async def run(target: str, out: Path, artifact_dir: Path):
  report = {
    'script': 'download_gemini_video.py',
    'status': 'running',
    'error_code': None,
    'error_detail': None,
    'cdp': CDP,
    'target': target,
    'output': str(out),
    'artifacts': []
  }

  async with async_playwright() as p:
    browser = await p.chromium.connect_over_cdp(CDP)
    if not browser.contexts:
      report['status'] = 'failed'
      report['error_code'] = 'E_NO_CONTEXT'
      report['error_detail'] = 'No browser contexts'
      write_report(artifact_dir, report)
      print('ERROR_CODE=E_NO_CONTEXT')
      raise RuntimeError('No browser contexts')
    ctx = browser.contexts[0]

    page = None
    for pg in ctx.pages:
      if target in (pg.url or ''):
        page = pg
        break

    if page is None:
      page = await ctx.new_page()
      await page.goto(f'https://gemini.google.com/app/{target}', wait_until='domcontentloaded')

    await page.wait_for_timeout(1400)

    for label in ['ดาวน์โหลดวิดีโอ', 'Download video', 'ดาวน์โหลด', 'Download']:
      try:
        btn = page.get_by_role('button', name=label)
        if await btn.count() > 0:
          await btn.first.click(timeout=2500)
          break
      except Exception:
        pass

    result = await page.evaluate(JS_FETCH_VIDEO)
    if not result.get('ok'):
      art = await save_artifacts(page, artifact_dir, 'no-video-src')
      report['artifacts'].append(art)
      report['status'] = 'failed'
      report['error_code'] = 'E_VIDEO_SRC'
      report['error_detail'] = 'no video source'
      write_report(artifact_dir, report)
      print('ERROR_CODE=E_VIDEO_SRC')
      print('ORIGINAL_VIDEO_REQUIRED: no video source')
      raise SystemExit(2)

    data = base64.b64decode(result['b64'])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)

    print(f"OUT={out}")
    print(f"LEN={len(data)}")
    print(f"TYPE={result.get('type')}")
    print(f"STATUS={result.get('status')}")
    print(f"HEAD={result.get('head')}")
    print(f"SRC={result.get('src')}")

    report['status'] = 'success'
    report['size'] = len(data)
    report['content_type'] = result.get('type')
    report['http_status'] = result.get('status')
    report['src'] = result.get('src')
    write_report(artifact_dir, report)

    await browser.close()


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument('--target', required=True, help='Gemini chat id, e.g. 79d46d5d74160c3c')
  ap.add_argument('--out', default=r'D:\Gemini-Downloads\gemini-video.mp4', help='Output mp4 path (must be on D: drive)')
  ap.add_argument('--artifact-dir', default=r'D:\Gemini-Downloads\artifacts')
  args = ap.parse_args()

  out_path = Path(args.out)
  artifact_dir = Path(args.artifact_dir)
  if str(out_path).lower().startswith('d:') is False:
    report = {
      'script': 'download_gemini_video.py',
      'status': 'failed',
      'error_code': 'E_OUT_PATH',
      'error_detail': 'output path must be on D: drive',
      'output': str(out_path)
    }
    write_report(artifact_dir, report)
    print('ERROR_CODE=E_OUT_PATH')
    print('ORIGINAL_VIDEO_REQUIRED: output path must be on D: drive')
    raise SystemExit(2)

  asyncio.run(run(args.target, out_path, artifact_dir))

if __name__ == '__main__':
  main()
