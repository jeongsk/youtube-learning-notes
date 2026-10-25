#!/usr/bin/env python3
"""parse_srt.py — SRT 자막을 cue 리스트로 파싱한다.

사용 예:
    python parse_srt.py <input.srt>              # 전체 cue를 JSON으로 출력
    python parse_srt.py <input.srt> --preview 5  # 앞 5개 cue만 사람이 읽기 좋은 형식으로
    python parse_srt.py <input.srt> --duration   # 마지막 cue의 종료 시각만 출력

cue는 다음 키를 가진다:
    - index   (int)         : SRT 원본 순번
    - start   (float)       : 시작 초
    - end     (float)       : 종료 초
    - start_hms (str)       : "HH:MM:SS" (스크린샷 추출용)
    - text    (str)         : 줄바꿈 정리된 자막 텍스트
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 시(hour)가 없는 "MM:SS.mmm" 형식(일부 VTT→SRT 변환 결과)도 허용한다.
TIME_RE = re.compile(
    r"(?:(\d{1,2}):)?(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
    r"(?:(\d{1,2}):)?(\d{2}):(\d{2})[,.](\d{1,3})"
)


def _to_seconds(h: str | None, m: str, s: str, ms: str) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def _to_hms(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def parse_srt(path: Path) -> list[dict]:
    # utf-8-sig: BOM이 있으면 첫 cue의 인덱스("\ufeff1")가 숫자로 인식되지 않는 문제 방지
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    # SRT 블록은 빈 줄로 구분
    blocks = re.split(r"\n\s*\n", raw.strip())
    cues: list[dict] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        # 1행은 보통 인덱스지만 자동자막에 종종 빠져있어 유연하게 처리
        idx_line = lines[0]
        time_line_pos = 1 if idx_line.isdigit() else 0
        if time_line_pos >= len(lines):
            continue
        m = TIME_RE.search(lines[time_line_pos])
        if not m:
            continue
        start = _to_seconds(*m.group(1, 2, 3, 4))
        end = _to_seconds(*m.group(5, 6, 7, 8))
        text_lines = lines[time_line_pos + 1 :]
        # 자동자막의 인라인 타이밍 태그(<00:00:01.000>) 제거
        text = " ".join(text_lines)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        cues.append(
            {
                "index": int(idx_line) if idx_line.isdigit() else len(cues) + 1,
                "start": round(start, 3),
                "end": round(end, 3),
                "start_hms": _to_hms(start),
                "text": text,
            }
        )
    return cues


def main() -> int:
    # Windows 콘솔(cp949/cp1252)에서도 한글·이모지 출력이 깨지거나 죽지 않도록
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path)
    ap.add_argument("--preview", type=int, default=0, help="앞 N개만 사람이 읽기 좋게 출력")
    ap.add_argument("--duration", action="store_true", help="총 길이(마지막 cue 종료 시각)만 출력")
    args = ap.parse_args()

    if not args.path.exists():
        print(f"파일을 찾을 수 없음: {args.path}", file=sys.stderr)
        return 1

    cues = parse_srt(args.path)
    if not cues:
        print("자막 cue를 찾지 못했습니다. 파일이 비어있거나 형식이 다를 수 있습니다.", file=sys.stderr)
        return 2

    if args.duration:
        print(_to_hms(cues[-1]["end"]))
        return 0

    if args.preview:
        for c in cues[: args.preview]:
            print(f"[{c['start_hms']}] {c['text']}")
        print(f"... (총 {len(cues)}개 cue)")
        return 0

    json.dump(cues, sys.stdout, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
