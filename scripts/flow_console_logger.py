#!/usr/bin/env python
"""
Flow Console Logger — Extract signed URLs from browser console

Usage:
  python flow_console_logger.py --target-id <tab_id> --output-json <path>

Outputs:
  - JSON with all console messages
  - Extracted signed URLs (GCS storage.googleapis.com links)
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

# This would be called from supervisor after worker starts
# For now, provides utility functions

def extract_signed_urls(console_messages: list) -> list:
    """Extract GCS signed URLs from console error messages"""
    urls = []
    gcs_pattern = re.compile(r'https://storage\.googleapis\.com/[^\s\'",]+')
    
    for msg in console_messages:
        if msg.get('type') == 'error' and 'storage.googleapis.com' in msg.get('text', ''):
            matches = gcs_pattern.findall(msg['text'])
            urls.extend(matches)
    
    return urls

def parse_console_log(log_text: str) -> list:
    """Parse console log text into structured messages"""
    messages = []
    # Simple parser - assumes one message per line with timestamp
    for line in log_text.strip().split('\n'):
        if not line.strip():
            continue
        
        # Try to extract type and text
        msg = {
            "raw": line,
            "timestamp": datetime.now().isoformat(),
            "type": "unknown"
        }
        
        if 'error' in line.lower():
            msg['type'] = 'error'
        elif 'warn' in line.lower():
            msg['type'] = 'warning'
        elif 'log' in line.lower():
            msg['type'] = 'log'
        
        messages.append(msg)
    
    return messages

def main():
    parser = argparse.ArgumentParser(description="Flow Console Logger")
    parser.add_argument("--input", help="Input console log file")
    parser.add_argument("--output-json", help="Output JSON file for extracted URLs")
    
    args = parser.parse_args()
    
    if args.input:
        log_text = Path(args.input).read_text(encoding='utf-8')
        messages = parse_console_log(log_text)
        urls = extract_signed_urls(messages)
        
        result = {
            "total_messages": len(messages),
            "signed_urls": urls,
            "messages": messages
        }
        
        if args.output_json:
            Path(args.output_json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"Extracted {len(urls)} signed URL(s) to {args.output_json}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Usage: flow_console_logger.py --input <console.log> --output-json <result.json>")

if __name__ == "__main__":
    main()
