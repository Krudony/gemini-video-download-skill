import argparse
import subprocess
import sys
import threading
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--interval', type=int, default=30)
    p.add_argument('cmd', nargs=argparse.REMAINDER)
    args = p.parse_args()

    if not args.cmd:
        print('RESULT: failed', flush=True)
        print('ERROR_CODE=E_RELAY_NO_CMD', flush=True)
        sys.exit(2)

    cmd = args.cmd
    if cmd and cmd[0] == '--':
        cmd = cmd[1:]

    print('ACK: relay runner started', flush=True)
    print(f'PROGRESS: launching child: {cmd[0]}', flush=True)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        bufsize=1,
    )

    stop = threading.Event()
    start = time.time()

    def ticker():
        while not stop.wait(args.interval):
            elapsed = int(time.time() - start)
            print(f'HEARTBEAT stage=relay elapsed={elapsed}s child_running={proc.poll() is None}', flush=True)

    t = threading.Thread(target=ticker, daemon=True)
    t.start()

    try:
        for line in proc.stdout:
            print(line.rstrip('\n'), flush=True)
    finally:
        proc.wait()
        stop.set()
        t.join(timeout=1)

    print('HEARTBEAT_STOP', flush=True)
    if proc.returncode == 0:
        print('RESULT: success', flush=True)
    else:
        print('RESULT: failed', flush=True)
        print(f'ERROR_CODE=E_CHILD_EXIT_{proc.returncode}', flush=True)

    sys.exit(proc.returncode)


if __name__ == '__main__':
    main()
