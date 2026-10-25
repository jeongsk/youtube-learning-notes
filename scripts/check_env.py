#!/usr/bin/env python3
"""check_env.py — 이 스킬에 필요한 도구가 준비됐는지 점검하고, 없으면 OS별 설치 명령을 알려준다.

사용 예:
    python check_env.py          # 사람이 읽는 표
    python check_env.py --json   # 에이전트가 파싱하기 쉬운 JSON

필수: Python 3.8+, yt-dlp, ffmpeg, ffprobe
권장: JS 런타임(deno 또는 node/bun) — 최신 yt-dlp가 YouTube를 처리할 때 필요
종료 코드: 필수 항목이 모두 있으면 0, 하나라도 없으면 1
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys

INSTALL = {
    "yt-dlp": {
        "Darwin": "brew install yt-dlp",
        "Linux": 'python3 -m pip install -U "yt-dlp[default]"',
        "Windows": "winget install yt-dlp.yt-dlp",
    },
    "ffmpeg": {
        "Darwin": "brew install ffmpeg",
        "Linux": "sudo apt install ffmpeg   # Fedora: sudo dnf install ffmpeg",
        "Windows": "winget install Gyan.FFmpeg",
    },
    "deno": {
        "Darwin": "brew install deno",
        "Linux": "curl -fsSL https://deno.land/install.sh | sh",
        "Windows": "winget install DenoLand.Deno",
    },
}


def _version(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    line = (out.stdout or out.stderr).strip().splitlines()
    return line[0][:80] if out.returncode == 0 and line else None


def check() -> list[dict]:
    osname = platform.system()
    rows = []

    py_ok = sys.version_info >= (3, 8)
    rows.append({"name": "python", "required": True, "ok": py_ok, "version": platform.python_version(),
                 "hint": None if py_ok else "Python 3.8 이상을 설치하세요."})

    ytdlp = shutil.which(os.environ.get("YTDLP", "yt-dlp"))
    ver = _version([ytdlp, "--version"]) if ytdlp else _version([sys.executable, "-m", "yt_dlp", "--version"])
    rows.append({"name": "yt-dlp", "required": True, "ok": bool(ver), "version": ver,
                 "hint": None if ver else INSTALL["yt-dlp"].get(osname)})

    for tool in ("ffmpeg", "ffprobe"):
        env = os.environ.get("FFMPEG")
        path = shutil.which(tool)
        if not path and env:
            cand = os.path.join(os.path.dirname(env) if os.path.isfile(env) else env, tool)
            path = shutil.which(cand) or shutil.which(cand + ".exe")
        ver = _version([path, "-version"]) if path else None
        rows.append({"name": tool, "required": True, "ok": bool(ver), "version": ver,
                     "hint": None if ver else INSTALL["ffmpeg"].get(osname)})

    js = next((rt for rt in ("deno", "node", "bun") if shutil.which(rt)), None)
    rows.append({"name": "js-runtime", "required": False, "ok": bool(js), "version": js,
                 "hint": None if js else INSTALL["deno"].get(osname) + "  (또는 node / bun)"})
    return rows


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = check()
    missing = [r for r in rows if r["required"] and not r["ok"]]
    if args.json:
        json.dump({"os": platform.system(), "ok": not missing, "checks": rows}, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")
        for r in rows:
            mark = "OK " if r["ok"] else ("MISSING" if r["required"] else "WARN")
            print(f"  [{mark:^7}] {r['name']:<10} {r['version'] or ''}")
            if r["hint"]:
                print(f"            설치: {r['hint']}")
        print("\n준비 완료" if not missing else f"\n필수 도구 {len(missing)}개가 없습니다.")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
