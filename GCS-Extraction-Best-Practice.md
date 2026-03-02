# 🎯 GCS URL Extraction Method — Best Practice

**เวอร์ชัน:** 1.0 (2026-03-02)  
**สถานะ:** ✅ Proven Working (100% success rate)  

---

## 📌 Problem Statement

เมื่อดาวน์โหลดวิดีโอจาก Google Flow ใน headless/browser-tool mode:

❌ **ปัญหาที่พบ:**
- Browser download events ไม่ทำงาน
- Console logs ไม่มี GCS signed URLs
- Redirect URLs (`/api/trpc/media.getMediaUrlRedirect`) ต้องใช้ authenticated session
- HTTP request ธรรมดาได้ login HTML แทนวิดีโอ

---

## ✅ Solution: Performance API Extraction

### วิธีการ (9 ขั้นตอน)

```javascript
// 1. คลิกปุ่ม "ดาวน์โหลด"
// 2. เลือก "720p Original Size"
// 3. รอ 3-5 วินาที (สำคัญมาก!)

// 4. ดึง GCS URL จาก Performance API
const gcsUrl = performance.getEntriesByType('resource')
  .find(e => e.name.includes('storage.googleapis.com'))?.name;

// 5. จะได้ URL แบบนี้:
// https://storage.googleapis.com/ai-sandbox-videofx/video/[ID]?GoogleAccessId=...&Expires=...&Signature=...

// 6. ดาวน์โหลดด้วย PowerShell ( bypass CORS)
Invoke-WebRequest -Uri $gcsUrl -OutFile $outPath -UseBasicParsing

// 7. ตรวจสอบไฟล์
$size = (Get-Item $outPath).Length
$header = Get-Content $outPath -Encoding Byte -TotalCount 12
$isMp4 = [System.Text.Encoding]::ASCII.GetString($header[4..7]) -eq 'ftyp'

// 8. รัน inspect_mp4.py
python scripts/inspect_mp4.py $outPath

// 9. ส่ง Telegram + Cleanup
```

---

## 🔬 ทำไมวิธีนี้ทำงาน

### การทำงานของ Flow

1. **User คลิกดาวน์โหลด** → Flow สร้าง signed URL จาก GCS
2. **Browser โหลดวิดีโอ** → เพื่อ preview/playback ใน player
3. **Performance API จับได้** → ทุก resource request ที่ browser ทำ

### ข้อได้เปรียบ

| วิธี | Reliability | ข้อจำกัด |
|------|-------------|----------|
| Browser Download Event | ❌ ต่ำ | ไม่ทำงานใน headless mode |
| Console Logs | ❌ ต่ำ | Flow ไม่ selalu log URL |
| Redirect API | ❌ ต่ำ | ต้องใช้ authenticated session |
| **Performance API** | ✅ **100%** | จับได้ทุกครั้งที่มี preview |

---

## 📊 Test Results

| วันที่ | วิดีโอ | วิธี | ผลลัพธ์ |
|--------|--------|------|---------|
| 2026-03-02 | มะนาวพูดได้ | Performance API | ✅ 1.96 MB |
| 2026-03-02 | มะนาวสู้กับส้ม | Performance API | ✅ 2.88 MB |

**Success Rate:** 2/2 = 100%

---

## ⚠️ ข้อควรระวัง

### 1. รอให้พอหลังคลิก 720p
- **รออย่างน้อย 3-5 วินาที**
- ถ้าเร็วไป → Performance API ยังไม่มี entry

### 2. Filter ให้ถูก
```javascript
// ✅ ถูก
.find(e => e.name.includes('storage.googleapis.com'))

// ❌ ผิด (กว้างไป)
.find(e => e.name.includes('googleapis.com'))
```

### 3. CORS ใน Browser Eval
```javascript
// ❌ ไม่ทำงาน (CORS block)
fetch(gcsUrl)

// ✅ ทำงาน (PowerShell bypass CORS)
Invoke-WebRequest -Uri $gcsUrl
```

---

## 🛠 Implementation Code

### Browser Eval (JavaScript)
```javascript
() => {
  const entries = performance.getEntriesByType('resource')
    .filter(e => e.name.includes('storage.googleapis.com'));
  return entries.length > 0 ? entries[0].name : 'NOT_FOUND';
}
```

### PowerShell Download
```powershell
param(
    [Parameter(Mandatory=$true)]
    [string]$GcsUrl,
    
    [Parameter(Mandatory=$true)]
    [string]$OutFile
)

Invoke-WebRequest -Uri $GcsUrl -OutFile $OutFile -UseBasicParsing

$size = (Get-Item $OutFile).Length
Write-Host "DOWNLOADED: $size bytes ($([math]::Round($size/1MB,2)) MB)"

$header = Get-Content $OutFile -Encoding Byte -TotalCount 12
$isMp4 = [System.Text.Encoding]::ASCII.GetString($header[4..7]) -eq 'ftyp'
Write-Host "MP4_VALID: $isMp4"

if (-not $isMp4) {
    throw "File is not valid MP4!"
}
```

---

## 📚 อ้างอิง

- **Gist:** https://gist.github.com/Krudony/7c1fdbc9d2ddd6d210118c0e2b09c5e9
- **Issue #32:** https://github.com/Krudony/Addbotopenclaw/issues/32
- **MDN Performance API:** https://developer.mozilla.org/en-US/docs/Web/API/Performance/getEntriesByType

---

**อัพเดตล่าสุด:** 2026-03-02
