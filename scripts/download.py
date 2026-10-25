#!/usr/bin/env python3
"""download.py — yt-dlp로 영상(mp4)과 자막(srt)을 받고 결과 경로를 JSON으로 출력한다.

OS·셸마다 다른 따옴표 규칙을 피하려고 yt-dlp 옵션을 이 스크립트 안에 고정했다.

사용 예:
    python download.py "https://youtu.be/<id>" --outdir work
    python download.py "<URL>" --outdir work --langs ko,en,ja
    python download.py "<URL>" --outdir work --cookies-from-browser chrome   # 연령 제한·봇 확인 시
    python download.py "<URL>" --outdir work --subs-only                      # 자막만 (영상 없이 노트 초안)

출력 (stdout, JSON):
    {"id": ..., "title": ..., "channel": ..., "duration": "HH:MM:SS", "url": ...,
     "video": "work/<id>.mp4" | null, "subtitles": {"ko": "work/<id>.ko.srt", ...}}

파일명은 `<영상 id>.<ext>`로 고정한다. 제목을 파일명에 쓰면 한글·이모지·`/:|` 때문에
Windows에서 저장이 실패하거나 셸 인용이 깨진다. 제목은 JSON의 "title"로 받는다.

yt-dlp 위치: --yt-dlp 인자 → YTDLP 환경변수 → PATH의 yt-dlp → `python -m yt_dlp` 순.
ffmpeg 위치: FFMPEG 환경변수가 있으면 yt-dlp에 --ffmpeg-location으로 넘긴다.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

FORMAT = (
    "bv*[height<=1080][ext=mp4]+ba[ext=m4a]"
    "/b[height<=1080][ext=mp4]"
    "/bv*[height<=1080]+ba"
    "/b"
)


def yt_dlp_cmd(explicit: str | None) -> list[str] | None:
    for cand in (explicit, os.environ.get("YTDLP"), "yt-dlp"):
        if cand and shutil.which(cand):
            return [shutil.which(cand)]
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        return None
    return [sys.executable, "-m", "yt_dlp"]


def js_runtime_args() -> list[str]:
    # 최신 yt-dlp는 YouTube 처리에 JS 런타임이 필요하고 기본으로 deno만 켜져 있다.
    # deno가 없고 node/bun이 있으면 그걸 쓰도록 알려준다.
    if shutil.which("deno"):
        return []
    for rt in ("node", "bun"):
        if shutil.which(rt):
            return ["--js-runtimes", rt]
    return []


def _hms(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--outdir", type=Path, default=Path("."))
    ap.add_argument("--langs", default="ko,en", help="자막 언어 우선순위 (쉼표 구분, 기본 ko,en)")
    ap.add_argument("--cookies-from-browser", metavar="BROWSER", help="chrome, firefox, safari, edge 등")
    ap.add_argument("--subs-only", action="store_true", help="영상은 받지 않고 자막·메타데이터만")
    ap.add_argument("--yt-dlp", dest="yt_dlp", help="yt-dlp 실행 파일 경로")
    ap.add_argument("extra", nargs="*", help="`--` 뒤에 붙인 인자는 yt-dlp에 그대로 전달")
    args = ap.parse_args()

    base = yt_dlp_cmd(args.yt_dlp)
    if not base:
        print(
            "yt-dlp를 찾을 수 없습니다. 설치 후 다시 실행하세요.\n"
            '  pip install -U "yt-dlp[default]"   (또는 brew/winget install yt-dlp)',
            file=sys.stderr,
        )
        return 1

    args.outdir.mkdir(parents=True, exist_ok=True)
    cmd = base + [
        "--no-playlist",
        "--write-sub", "--write-auto-sub",
        "--sub-langs", args.langs,
        "--convert-subs", "srt",
        "--write-info-json",
        "-P", str(args.outdir),
        "-o", "%(id)s.%(ext)s",
        "--no-simulate",
        "--print", "after_move:%(id)s",
    ]
    if args.subs_only:
        cmd += ["--skip-download"]
    else:
        cmd += ["-f", FORMAT, "--merge-output-format", "mp4"]
    if os.environ.get("FFMPEG"):
        cmd += ["--ffmpeg-location", os.environ["FFMPEG"]]
    if args.cookies_from_browser:
        cmd += ["--cookies-from-browser", args.cookies_from_browser]
    cmd += js_runtime_args() + args.extra + [args.url]

    print("$ " + " ".join(cmd), file=sys.stderr)
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    ids = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    if proc.returncode != 0 and not ids:
        print(f"yt-dlp 실패 (exit {proc.returncode}). SKILL.md의 '다운로드 실패 대응'을 참고하세요.", file=sys.stderr)
        return proc.returncode or 1
    vid = ids[-1] if ids else None

    info_path = args.outdir / f"{vid}.info.json"
    info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
    video = args.outdir / f"{vid}.mp4"
    subs = {}
    for lang in [l.strip() for l in args.langs.split(",") if l.strip()]:
        p = args.outdir / f"{vid}.{lang}.srt"
        if p.exists() and p.stat().st_size > 0:
            subs[lang] = str(p)

    result = {
        "id": vid,
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "duration": _hms(info.get("duration")),
        "upload_date": info.get("upload_date"),
        "url": info.get("webpage_url") or args.url,
        "video": str(video) if video.exists() else None,
        "subtitles": subs,
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()

    if not subs:
        print("경고: 자막을 받지 못했습니다. 영상에 자막이 없거나 요청 제한(429)일 수 있습니다.", file=sys.stderr)
    if not args.subs_only and not result["video"]:
        print("경고: mp4가 없습니다. ffmpeg가 없으면 영상·음성 병합이 실패합니다.", file=sys.stderr)
    return 0 if subs and (args.subs_only or result["video"]) else 3


if __name__ == "__main__":
    raise SystemExit(main())
