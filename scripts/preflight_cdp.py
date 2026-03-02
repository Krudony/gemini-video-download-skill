import json
import sys
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

CANDIDATES = [
    "http://127.0.0.1:18801",
    "http://127.0.0.1:18802",
]


def check(base: str):
    try:
        with urlopen(base + "/json/version", timeout=3) as r:
            data = json.loads(r.read().decode("utf-8", errors="ignore"))
            ws = data.get("webSocketDebuggerUrl", "")
            if ws:
                return True, ws
            return False, "no webSocketDebuggerUrl"
    except (URLError, HTTPError, TimeoutError, OSError) as e:
        return False, str(e)


if __name__ == "__main__":
    print("ACK: preflight cdp check")
    for c in CANDIDATES:
        ok, detail = check(c)
        if ok:
            print(f"PRECHECK_OK CDP={c}")
            print(f"WS={detail}")
            sys.exit(0)
        print(f"PRECHECK_FAIL CDP={c} DETAIL={detail}")

    print("RESULT: failed")
    print("ERROR_CODE=E_PREFLIGHT_CDP_DOWN")
    print("ERROR_DETAIL=no reachable cdp endpoint")
    sys.exit(2)
