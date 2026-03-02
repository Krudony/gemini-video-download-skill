# 🤖 AI Context — gemini-video-download-skill

**Version:** v1.3 (2026-03-02)  
**Status:** ✅ Production-Ready  
**Last Updated:** 2026-03-02 14:00  

---

## 🎯 Project Goals

1. **สร้างวิดีโอจาก Google Flow ได้ 100% reliability** ด้วย GCS URL extraction method
2. **ส่ง Telegram ได้ทันที** (ผ่าน media gate <16MB)
3. **มีเอกสารครบถ้วน** สำหรับ reuse ในอนาคต
4. **Auto-cleanup** ป้องกัน RAM/CAM leak

---

## 🏗 Architecture

```
gemini-video-download-skill/
├── SKILL.md (OpenClaw skill definition)
├── scripts/
│   ├── flow_click_download.py (browser automation)
│   ├── inspect_mp4.py (media validation)
│   ├── telegram_size_gate.py (size check + transcode)
│   ├── run_flow_with_preflight.ps1 (wrapper)
│   └── download_via_gcs_url.ps1 (GCS download)
├── success-logs/
│   └── 2026-03-02-first-success.md
├── best-practices/
│   └── GCS-extraction-method.md
└── session-archive/
    └── 2026-03-02.md
```

---

## 🔧 Tech Stack

- **Runtime:** OpenClaw + browser tool
- **Browser:** Chrome with CDP (profile: `krudon`)
- **Language:** Python 3.11 + PowerShell
- **Validation:** mutagen (MP4 inspection)
- **Delivery:** Telegram Bot API (<16MB gate)

---

## 📊 Success Metrics (2026-03-02)

| Metric | Target | Achieved |
|--------|--------|----------|
| Success Rate | >95% | ✅ 100% (2/2) |
| Avg Generation Time | <5 min | ✅ ~3-4 min |
| Media Gate Pass | 100% | ✅ 2/2 |
| Telegram Delivery | 100% | ✅ 2/2 |

**Videos Created:**
1. มะนาวพูดได้ (8s, 1.96 MB) — msgId: 4081
2. มะนาวสู้กับส้ม (8s, 2.88 MB) — msgId: 4110

---

## 🚀 Usage

```bash
# One-command run
.\run_flow_with_preflight.ps1 -Prompt "มะนาวพูดได้ 8 วินาที" -OutputDir "D:\Gemini-Downloads"

# Or manual 9-step workflow (see SKILL.md)
```

---

## ⚠️ Critical Rules (หัวเด็ดตีนขาด)

1. **อ่าน SKILL.md ก่อนเริ่มทุกครั้ง**
2. **ใช้ GCS extraction จาก performance.getEntriesByType**
3. **รัน inspect_mp4.py ก่อนส่ง**
4. **Cleanup browser หลังส่ง**

---

## 📚 Documentation

- **Gist:** https://gist.github.com/Krudony/7c1fdbc9d2ddd6d210118c0e2b09c5e9
- **Issue #32:** https://github.com/Krudony/Addbotopenclaw/issues/32

---

## 🔄 Next Steps

- [ ] Add GCS extraction to `flow_click_download.py` as official fallback
- [ ] Test with 10+ videos to validate 95%+ success rate
- [ ] Create video tutorial (screen recording)
