#!/usr/bin/env python3
"""extract_screenshots.py — 시점 목록을 받아 ffmpeg로 일괄 스크린샷을 뽑는다.

사용 예:
    # JSON 입력 (stdin)
    echo '[
      {"index": 1, "time": "00:00:45"},
      {"index": 2, "time": "00:02:10", "label": "intro-slide"}
    ]' | python extract_screenshots.py <video.mp4> --outdir screenshots

    # JSON 파일 입력 (Windows PowerShell처럼 따옴표·파이프가 까다로운 셸에서 권장)
    python extract_screenshots.py <video.mp4> --outdir screenshots --json shots.json

    # 인자 반복
    python extract_screenshots.py <video.mp4> --outdir screenshots \\
        --shot 1@00:00:45 --shot 2@02:10@intro-slide

각 항목은 `{index, time[, label]}` 형식. time은 "HH:MM:SS", "MM:SS", "SS" 모두
가능하고 소수 초("00:01:02.5")도 받는다. 출력 파일명은
    scene_{index:02d}_{HHhMMmSSs}[_label].jpg

--shot의 구분자는 `@`이다. 예전 형식 "index:HH:MM:SS[:label]"도 계속 받는다.

ffmpeg 호출:
    ffmpeg -y -ss <time> -i <video> -frames:v 1 -q:v 2 <out.jpg>

ffmpeg 위치는 --ffmpeg 인자 → FFMPEG 환경변수 → PATH 순으로 찾는다.
검증(QA) 단계에서 단일 장면을 다시 뽑을 때는 이 스크립트를 한 항목으로 호출하면 된다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

INSTALL_HINT = (
    "ffmpeg를 찾을 수 없습니다. 설치 후 다시 실행하세요.\n"
    "  macOS   : brew install ffmpeg\n"
    "  Ubuntu  : sudo apt install ffmpeg\n"
    "  Windows : winget install Gyan.FFmpeg\n"
    "PATH에 없으면 --ffmpeg <경로> 또는 FFMPEG 환경변수로 지정할 수 있습니다."
)


def find_ffmpeg(explicit: str | None) -> str | None:
    for cand in (explicit, os.environ.get("FFMPEG"), "ffmpeg"):
        if not cand:
            continue
        found = shutil.which(cand)
        if found:
            return found
        if Path(cand).is_file():
            return str(Path(cand))
    return None


def _safe_label(label: str | None) -> str:
    if not label:
        return ""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", label).strip("-")
    return f"_{cleaned}" if cleaned else ""


def _split_time(time: str) -> tuple[int, int, float]:
    # "HH:MM:SS(.f)" / "MM:SS(.f)" / "SS(.f)" → (h, m, s)
    parts = [p for p in str(time).strip().split(":")]
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"시간 형식 오류: {time!r}")
    parts = ["0"] * (3 - len(parts)) + parts
    h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
    total = h * 3600 + m * 60 + s
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return int(h), int(m), s


def _time_to_filename(time: str) -> str:
    h, m, s = _split_time(time)
    return f"{h:02d}h{m:02d}m{int(s):02d}s"


def _time_to_ffmpeg(time: str) -> str:
    h, m, s = _split_time(time)
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def _parse_shot(raw: str) -> dict:
    if "@" in raw:
        parts = raw.split("@")
        if len(parts) not in (2, 3):
            raise ValueError(raw)
        return {"index": int(parts[0]), "time": parts[1], "label": parts[2] if len(parts) == 3 else None}
    # 예전 형식: "index:HH:MM:SS[:label]"
    parts = raw.split(":")
    if len(parts) < 4:
        raise ValueError(raw)
    return {"index": int(parts[0]), "time": ":".join(parts[1:4]), "label": parts[4] if len(parts) >= 5 else None}


def extract_one(ffmpeg: str, video: Path, time: str, out: Path) -> bool:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", _time_to_ffmpeg(time),
        "-i", str(video),
        "-frames:v", "1",
        "-q:v", "2",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        last = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "출력 파일이 생성되지 않음 (영상 길이를 넘는 시점일 수 있음)"
        print(f"[FAIL] {time} → {out.name}\n       {last}", file=sys.stderr)
        return False
    print(f"[OK]   {time} → {out.name}")
    return True


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path, help="입력 영상 (mp4 등 ffmpeg가 읽을 수 있는 형식)")
    ap.add_argument("--outdir", type=Path, default=Path("screenshots"))
    ap.add_argument("--json", type=Path, help="시점 목록 JSON 파일 경로 (stdin 대신)")
    ap.add_argument("--ffmpeg", help="ffmpeg 실행 파일 경로 (기본: FFMPEG 환경변수 → PATH)")
    ap.add_argument(
        "--shot",
        action="append",
        default=[],
        help='반복 사용. 형식 "index@time[@label]" 예: "1@00:02:10@intro"',
    )
    args = ap.parse_args()

    ffmpeg = find_ffmpeg(args.ffmpeg)
    if not ffmpeg:
        print(INSTALL_HINT, file=sys.stderr)
        return 1

    if not args.video.exists():
        print(f"영상 파일을 찾을 수 없음: {args.video}", file=sys.stderr)
        return 1

    shots: list[dict] = []
    try:
        if args.shot:
            shots = [_parse_shot(raw) for raw in args.shot]
        elif args.json:
            shots = json.loads(args.json.read_text(encoding="utf-8-sig"))
        else:
            data = sys.stdin.read().strip()
            if not data:
                print("입력 시점 없음. --shot, --json 또는 stdin JSON을 주세요.", file=sys.stderr)
                return 1
            shots = json.loads(data)
    except (ValueError, OSError) as e:
        print(f"시점 입력 오류: {e}", file=sys.stderr)
        return 1

    args.outdir.mkdir(parents=True, exist_ok=True)
    ok, fail = 0, 0
    for shot in shots:
        index = int(shot["index"])
        time = str(shot["time"])
        label = shot.get("label")
        try:
            fname = f"scene_{index:02d}_{_time_to_filename(time)}{_safe_label(label)}.jpg"
        except ValueError as e:
            print(f"[FAIL] {e}", file=sys.stderr)
            fail += 1
            continue
        if extract_one(ffmpeg, args.video, time, args.outdir / fname):
            ok += 1
        else:
            fail += 1

    print(f"\n완료: {ok}장 성공 / {fail}장 실패", file=sys.stderr)
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
