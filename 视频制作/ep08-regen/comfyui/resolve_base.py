#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os as _os
# 4-core / 6GB cgroup: keep BLAS/torch/ffmpeg thread counts low (Lead resource rule)
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    _os.environ.setdefault(_k, "2")
"""EP08 entry resolver: find the working ComfyUI base among known entries.

Candidates (in order): $H3_BASE from /home/admin/.h3.env or the process env, then
previously seen ports on the same host (ep05: 24909, ep07: 22815 / 34076), then any
extra base passed with --base. A new entry handed over by the user/Lead can simply be
exported as H3_BASE (or passed with --base) — nothing is hardcoded to one port.

Prints one line per attempt; on success prints the working base as the LAST line and
exits 0. LOGIN_REJECTED -> exit 3; timeout/NOT_REACHABLE -> exit 2.

  python3 resolve_base.py 1800
  python3 resolve_base.py 600 --base https://host:PORT
"""
import argparse
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Load credentials/entry into the process env BEFORE importing the client: ComfyClient
# captures H3_USER/H3_PASS defaults at import time, so a later load would be invisible.
ENV = Path("/home/admin/.h3.env")
if ENV.exists():
    for ln in ENV.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln.startswith("export "):
            ln = ln[len("export "):]
        if "=" in ln:
            k, _, v = ln.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

sys.path.insert(0, str(HERE / "tools"))
from comfy_client import ComfyClient, AppDownError  # noqa: E402

HOST = os.environ.get("H3_HOST", "wp08.unicorn.org.cn")
KNOWN_PORTS = (24909, 22815, 34076)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("budget", nargs="?", type=float, default=900)
    ap.add_argument("--base", action="append", default=[], help="extra base URL candidate")
    ap.add_argument("--interval", type=float, default=15)
    args = ap.parse_args()

    cands = []
    for b in [os.environ.get("H3_BASE", "")] + list(args.base) + [
            f"https://{HOST}:{p}" for p in KNOWN_PORTS]:
        if b and b.rstrip("/") not in cands:
            cands.append(b.rstrip("/"))
    deadline = time.time() + args.budget
    print(f"candidates: {cands}; budget={args.budget:.0f}s", flush=True)
    n = 0
    rejected = []
    while time.time() < deadline:
        n += 1
        for base in cands:
            if base in rejected:
                continue
            c = ComfyClient(base, os.environ.get("H3_USER", ""),
                        os.environ.get("H3_PASS", ""), timeout=12)
            try:
                c.login()
            except SystemExit as e:
                rejected.append(base)
                print(f"[{time.strftime('%H:%M:%SZ', time.gmtime())}] {base} "
                      f"LOGIN_REJECTED: {str(e)[:100]}", flush=True)
                continue
            except Exception as e:  # noqa: BLE001
                print(f"[{time.strftime('%H:%M:%SZ', time.gmtime())}] attempt {n} {base} "
                      f"unreachable: {type(e).__name__}", flush=True)
                continue
            try:
                st = c.system_stats()
                dev = (st.get("devices") or [{}])[0]
                print(f"[{time.strftime('%H:%M:%SZ', time.gmtime())}] {base} STATS_OK "
                      f"comfy={st.get('system', {}).get('comfyui_version')} "
                      f"gpu={dev.get('name')}", flush=True)
                print(base)
                sys.exit(0)
            except AppDownError:
                print(f"[{time.strftime('%H:%M:%SZ', time.gmtime())}] {base} login OK but "
                      f"backend 502 (booting)", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[{time.strftime('%H:%M:%SZ', time.gmtime())}] {base} stats error: "
                      f"{type(e).__name__}", flush=True)
        if rejected and len(rejected) == len(cands):
            print("ALL_CANDIDATES_REJECTED")
            sys.exit(3)
        time.sleep(args.interval)
    print("NOT_REACHABLE")
    sys.exit(2)


if __name__ == "__main__":
    main()
