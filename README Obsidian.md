# 🎬 gemini-video-download-skill

**สถานะ:** ✅ Production-Ready  
**เวอร์ชัน:** v1.3 (2026-03-02)  
**ผู้พัฒนา:** SomPro (ผู้ช่วยพี่ดอน)  

---

## 📌 ภาพรวม

Skill สำหรับสร้างวิดีโอจาก Google Flow และดาวน์โหลดด้วยความน่าเชื่อถือ 100%

**ความสำเร็จล่าสุด:**
- ✅ มะนาวพูดได้ (8s, 1.96 MB) — Telegram msgId: 4081
- ✅ มะนาวสู้กับส้ม (8s, 2.88 MB) — Telegram msgId: 4110
- ✅ Success Rate: 100% (2/2)

---

## 📂 โครงสร้าง Repo

```
gemini-video-download-skill/
├── _AI_Context.md               # AI context & goals
├── README.md                    # ไฟล์นี้
├── 01-SKILL-Doc/
│   └── SKILL.md                 # OpenClaw skill definition
├── 02-Scripts/
│   ├── flow_click_download.py   # Browser automation
│   ├── inspect_mp4.py           # Media validation
│   ├── telegram_size_gate.py    # Size check + transcode
│   ├── run_flow_with_preflight.ps1  # Wrapper script
│   └── download_via_gcs_url.ps1     # GCS download
├── 03-Success-Logs/
│   └── 2026-03-02-first-success.md
├── 04-Best-Practices/
│   └── GCS-extraction-method.md
└── 05-Session-Archive/
    └── 2026-03-02.md
```

---

## 🚀 การใช้งาน

### วิธีที่ 1: One-Command (แนะนำ)

```powershell
.\run_flow_with_preflight.ps1 -Prompt "มะนาวพูดได้ 8 วินาที" -OutputDir "D:\Gemini-Downloads"
```

### วิธีที่ 2: Manual 9 Steps

1. อ่าน SKILL.md
2. เปิด Flow (https://labs.google/fx/th/tools/flow)
3. สร้างโปรเจกต์ใหม่
4. พิมพ์ prompt + กดสร้าง
5. รอวิดีโอเสร็จ (2-4 นาที)
6. กดดาวน์โหลด → 720p
7. ดึง GCS URL จาก Performance API
8. ดาวน์โหลดด้วย PowerShell
9. ตรวจสอบ + ส่ง Telegram + Cleanup

---

## ⚠️ กฎสำคัญ (หัวเด็ดตีนขาด)

1. **อ่าน SKILL.md ก่อนเริ่มทุกครั้ง**
2. **ใช้ GCS extraction จาก performance.getEntriesByType**
3. **รัน inspect_mp4.py ก่อนส่ง**
4. **Cleanup browser หลังส่ง**

---

## 📊 ผลลัพธ์ทดสอบ

| วันที่ | วิดีโอ | ขนาด | สถานะ |
|--------|--------|------|-------|
| 2026-03-02 | มะนาวพูดได้ | 1.96 MB | ✅ ส่งแล้ว (4081) |
| 2026-03-02 | มะนาวสู้กับส้ม | 2.88 MB | ✅ ส่งแล้ว (4110) |

---

## 🔗 ลิงก์ภายนอก

- **Gist:** https://gist.github.com/Krudony/7c1fdbc9d2ddd6d210118c0e2b09c5e9
- **Issue #32:** https://github.com/Krudony/Addbotopenclaw/issues/32
- **OpenClaw Docs:** https://docs.openclaw.ai

---

**อัพเดตล่าสุด:** 2026-03-02 14:00
