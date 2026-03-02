"""
Flow Video Downloader - Click-Based
ดาวน์โหลดวิดีโอจาก Google Flow โดยการคลิกปุ่มดาวน์โหลดใน UI
"""
import sys
import os
import time
from pathlib import Path

def main():
    output_dir = os.environ.get('OUTPUT_DIR', 'D:\\Gemini-Downloads')
    prompt_keyword = os.environ.get('PROMPT_KEYWORD', '')
    
    print(f"OUTPUT_DIR={output_dir}")
    print(f"PROMPT_KEYWORD={prompt_keyword}")
    print("STATUS=ready")
    
    # Script จะทำงานผ่าน browser tool ของ OpenClaw
    # ไฟล์นี้เป็น marker ให้รู้ว่าต้องดาวน์โหลด via UI click
    print("METHOD=ui_click")
    print("WAIT_FOR_BROWSER=true")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
