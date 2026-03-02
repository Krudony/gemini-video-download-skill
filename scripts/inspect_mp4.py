import struct
import sys
from pathlib import Path


def read_u32(b, o):
    return struct.unpack_from('>I', b, o)[0]

def read_u64(b, o):
    return struct.unpack_from('>Q', b, o)[0]

def walk_boxes(data, start=0, end=None):
    if end is None:
        end = len(data)
    o = start
    while o + 8 <= end:
        size = read_u32(data, o)
        typ = data[o+4:o+8].decode('latin1', 'replace')
        hdr = 8
        if size == 1:
            if o + 16 > end:
                break
            size = read_u64(data, o+8)
            hdr = 16
        elif size == 0:
            size = end - o
        if size < hdr or o + size > end:
            break
        yield o, size, typ, hdr
        o += size


def find_child(data, parent_off, parent_size, parent_hdr, child_type):
    s = parent_off + parent_hdr
    e = parent_off + parent_size
    return [b for b in walk_boxes(data, s, e) if b[2] == child_type]


def parse_mdhd(data, off, size, hdr):
    p = off + hdr
    if p + 4 > off + size:
        return None
    version = data[p]
    p += 4
    try:
        if version == 1:
            p += 16
            timescale = read_u32(data, p); p += 4
            duration = read_u64(data, p)
        else:
            p += 8
            timescale = read_u32(data, p); p += 4
            duration = read_u32(data, p)
        return timescale, duration
    except Exception:
        return None


def parse_hdlr(data, off, size, hdr):
    p = off + hdr
    if p + 12 > off + size:
        return None
    p += 8
    return data[p:p+4].decode('latin1', 'replace')


def parse_stsz(data, off, size, hdr):
    p = off + hdr
    if p + 12 > off + size:
        return None
    p += 4
    _sample_size = read_u32(data, p); p += 4
    sample_count = read_u32(data, p)
    return sample_count


def main(path):
    p = Path(path)
    data = p.read_bytes()

    if data[:16].lower().startswith(b'<!doctype html'):
        print('ORIGINAL_VIDEO_REQUIRED: html file, not mp4')
        return 2

    moov_list = [b for b in walk_boxes(data) if b[2] == 'moov']
    if not moov_list:
        print('ORIGINAL_VIDEO_REQUIRED: no moov box')
        return 2

    tracks = []
    for moov in moov_list:
        traks = find_child(data, moov[0], moov[1], moov[3], 'trak')
        for trak in traks:
            kind, dur_sec, samples = None, None, None
            mdia_list = find_child(data, trak[0], trak[1], trak[3], 'mdia')
            for mdia in mdia_list:
                for h in find_child(data, mdia[0], mdia[1], mdia[3], 'hdlr'):
                    kind = parse_hdlr(data, h[0], h[1], h[3]) or kind
                for m in find_child(data, mdia[0], mdia[1], mdia[3], 'mdhd'):
                    md = parse_mdhd(data, m[0], m[1], m[3])
                    if md and md[0]:
                        dur_sec = md[1] / md[0]
                for minf in find_child(data, mdia[0], mdia[1], mdia[3], 'minf'):
                    for stbl in find_child(data, minf[0], minf[1], minf[3], 'stbl'):
                        for stsz in find_child(data, stbl[0], stbl[1], stbl[3], 'stsz'):
                            samples = parse_stsz(data, stsz[0], stsz[1], stsz[3])
            tracks.append((kind, dur_sec, samples or 0))

    has_video = any(k == 'vide' and s > 0 for k, _, s in tracks)
    has_audio = any(k == 'soun' and s > 0 for k, _, s in tracks)

    print(f'FILE={p}')
    print(f'SIZE={p.stat().st_size}')
    print(f'TRACKS={len(tracks)}')
    for i, (k, d, s) in enumerate(tracks, 1):
        print(f'TRACK_{i}_TYPE={k}')
        print(f'TRACK_{i}_DURATION_SEC={d}')
        print(f'TRACK_{i}_SAMPLES={s}')
    print(f'HAS_VIDEO={has_video}')
    print(f'HAS_AUDIO={has_audio}')

    if not (has_video and has_audio):
        print('ORIGINAL_VIDEO_REQUIRED: missing video/audio track')
        return 2
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: inspect_mp4.py <file>')
        raise SystemExit(1)
    raise SystemExit(main(sys.argv[1]))
