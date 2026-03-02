import argparse
import subprocess
from pathlib import Path
import imageio_ffmpeg

MAX_BYTES = 16 * 1024 * 1024


def transcode(src: Path, dst: Path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, '-y', '-i', str(src),
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '30',
        '-c:a', 'aac', '-b:a', '96k',
        '-movflags', '+faststart',
        str(dst)
    ]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--infile', required=True)
    ap.add_argument('--outfile', required=True)
    args = ap.parse_args()

    src = Path(args.infile)
    dst = Path(args.outfile)

    if not src.exists():
        print('ORIGINAL_VIDEO_REQUIRED: input not found')
        raise SystemExit(2)

    size = src.stat().st_size
    if size <= MAX_BYTES:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        print(f'OUT={dst}')
        print(f'SIZE={dst.stat().st_size}')
        print('TRANSCODED=False')
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    transcode(src, dst)
    out_size = dst.stat().st_size
    print(f'OUT={dst}')
    print(f'SIZE={out_size}')
    print('TRANSCODED=True')

    if out_size > MAX_BYTES:
        print('ORIGINAL_VIDEO_REQUIRED: still exceeds telegram limit')
        raise SystemExit(2)


if __name__ == '__main__':
    main()
