# youtube-learning-notes

YouTube 영상 하나를 **자막 + 스크린샷이 결합된 한국어 학습 노트(Markdown)** 로 바꿔 주는 AI 에이전트 스킬입니다.
영상을 다시 보지 않아도 핵심 흐름, 슬라이드·코드 같은 시각 정보, 주요 인용을 파악할 수 있게 정리합니다.

Claude Code, Codex 등 [Agent Skills](https://agentskills.io) 형식(`SKILL.md`)을 읽는 에이전트에서 동작하며,
macOS · Linux · Windows 모두 지원합니다. 보조 스크립트는 Python 표준 라이브러리만 사용합니다.

## 무엇을 하나

1. **환경 점검** — yt-dlp, ffmpeg, JS 런타임이 있는지 확인하고 없으면 OS별 설치 명령 안내
2. **다운로드** — yt-dlp로 영상(mp4)과 자막(srt, 수동 자막 우선·없으면 자동 자막)
3. **장면 선정** — 자막을 파싱해 주제 전환 지점 10~20개 선정
4. **스크린샷 추출** — ffmpeg로 각 시점 프레임 캡처
5. **매칭 QA** — 모델이 스크린샷을 직접 보고 검은 화면·중복·엇갈린 장면을 다시 뽑음
6. **노트 작성** — 요약 → 장면별 설명(스크린샷 인라인) → 체크리스트 → 원문 인용

강연·튜토리얼처럼 화면 정보가 중요한 영상(A형)은 슬라이드·코드를 텍스트로 옮기고,
인터뷰·대담(B형)은 화면 묘사 없이 화자의 요점을 산문으로 정리합니다.

## 요구 사항

| 도구 | 필수 | macOS | Ubuntu/Debian | Windows |
|---|---|---|---|---|
| Python 3.8+ | ✅ | 기본 설치 또는 `brew install python` | `sudo apt install python3` | `winget install Python.Python.3.12` |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | ✅ | `brew install yt-dlp` | `python3 -m pip install -U "yt-dlp[default]"` | `winget install yt-dlp.yt-dlp` |
| [ffmpeg](https://ffmpeg.org) (ffprobe 포함) | ✅ | `brew install ffmpeg` | `sudo apt install ffmpeg` | `winget install Gyan.FFmpeg` |
| [deno](https://deno.com) (또는 node·bun) | 권장 | `brew install deno` | `curl -fsSL https://deno.land/install.sh \| sh` | `winget install DenoLand.Deno` |

- 최신 yt-dlp는 YouTube를 처리할 때 JS 런타임을 사용합니다. deno가 없고 node나 bun이 있으면 스크립트가 자동으로 그쪽을 씁니다.
- pip로 설치할 때는 `yt-dlp[default]`로 설치해야 YouTube용 보조 컴포넌트(`yt-dlp-ejs`)가 함께 들어옵니다.

설치 후 점검:

```bash
python3 scripts/check_env.py
```

## 설치

스킬 폴더 이름은 `youtube-learning-notes`로 유지하세요 (`SKILL.md`의 `name`과 같아야 합니다).

### Claude Code

```bash
# 모든 프로젝트에서 사용 (개인)
git clone https://github.com/jeongsk/youtube-learning-notes ~/.claude/skills/youtube-learning-notes

# 특정 프로젝트에서만 사용
git clone https://github.com/jeongsk/youtube-learning-notes .claude/skills/youtube-learning-notes
```

Windows PowerShell:

```powershell
git clone https://github.com/jeongsk/youtube-learning-notes "$env:USERPROFILE\.claude\skills\youtube-learning-notes"
```

### Codex 및 기타 Agent Skills 호환 에이전트

에이전트가 스킬을 읽는 폴더(예: `~/.agents/skills/`, `~/.codex/skills/`, 프로젝트의 `.agents/skills/`)에 같은 방식으로 클론합니다.
정확한 위치는 사용하는 에이전트의 문서를 확인하세요.

```bash
git clone https://github.com/jeongsk/youtube-learning-notes ~/.agents/skills/youtube-learning-notes
```

### Claude.ai (웹·데스크톱 앱)

[최신 릴리스의 `youtube-learning-notes.zip`](https://github.com/jeongsk/youtube-learning-notes/releases/latest/download/youtube-learning-notes.zip)을 받아
설정의 Skills 메뉴(예: **Settings → Capabilities → Skills**)에서 업로드합니다. 메뉴 위치는 앱 버전에 따라 다를 수 있습니다. 단, 이 환경의 샌드박스는 YouTube 접속이 막혀 있는 경우가 많습니다.
그럴 때 스킬은 다운로드 명령을 안내하고, 사용자가 자신의 PC에서 받은 mp4·srt를 업로드하면 이어서 노트를 만듭니다.

## 사용법

에이전트에게 YouTube 링크와 함께 요청하면 됩니다.

```
https://www.youtube.com/watch?v=XXXXXXXXXXX 이 영상 학습 노트로 정리해줘
```

```
이 강연 스크린샷 넣어서 요약해줘. 저장은 ~/notes 폴더에. https://youtu.be/XXXXXXXXXXX
```

스크립트만 따로 써도 됩니다.

```bash
# 영상 + 자막 다운로드 → 결과 경로를 JSON으로 출력
python3 scripts/download.py "https://youtu.be/XXXXXXXXXXX" --outdir work

# 자막 앞부분 미리보기
python3 scripts/parse_srt.py work/XXXXXXXXXXX.ko.srt --preview 20

# 스크린샷 추출
python3 scripts/extract_screenshots.py work/XXXXXXXXXXX.mp4 --outdir work/screenshots \
  --shot 1@00:00:45 --shot 2@00:02:10@intro
```

## 결과물

```
youtube_<영상ID>/
├── <영상ID>.mp4
├── <영상ID>.ko.srt
├── <영상ID>.info.json
├── screenshots/
│   ├── scene_01_00h00m45s.jpg
│   └── ...
└── <노트 제목>.md
```

노트는 Obsidian 등 일반 Markdown 뷰어에서 스크린샷이 상대경로로 바로 보이도록 작성됩니다.
노트 구조는 [`assets/note_template.md`](assets/note_template.md)를 참고하세요.

## 구성

```
youtube-learning-notes/
├── SKILL.md                      # 에이전트가 읽는 워크플로우 (스킬 본체)
├── scripts/
│   ├── check_env.py              # 필수 도구 점검 + OS별 설치 안내
│   ├── download.py               # yt-dlp 래퍼 (ID 기반 파일명, 결과 JSON)
│   ├── parse_srt.py              # SRT → cue JSON
│   └── extract_screenshots.py    # 시점 목록 → ffmpeg 일괄 캡처
└── assets/
    └── note_template.md          # 노트 본보기 (A형·B형)
```

## 문제 해결

| 증상 | 해결 |
|---|---|
| `HTTP Error 403`, `Signature extraction failed` | yt-dlp 업데이트: `yt-dlp -U` / `brew upgrade yt-dlp` / `pip install -U "yt-dlp[default]"`. JS 런타임 설치 여부 확인 |
| `Sign in to confirm you're not a bot`, 연령 제한 영상 | `python3 scripts/download.py <URL> --cookies-from-browser chrome` |
| `HTTP Error 429` (자막) | 잠시 후 재시도, 또는 `... -- --sleep-subtitles 5` |
| 자막이 없음 | 자막이 아예 없는 영상입니다. 다른 언어(`--langs ja,en`)를 시도하거나 Whisper 등 음성 인식을 별도로 사용 |
| mp4가 안 만들어짐 | ffmpeg가 없으면 영상·음성 병합이 실패합니다. `check_env.py`로 확인 |
| ffmpeg가 PATH에 없음 | `FFMPEG=/path/to/ffmpeg` 환경변수 또는 `--ffmpeg` 옵션 |
| Windows에서 한글이 깨짐 | 스크립트는 UTF-8로 출력합니다. 터미널에서 `chcp 65001` 또는 Windows Terminal 사용 |

## 주의

다운로드한 영상과 자막은 개인 학습 용도로만 사용하고, 각 영상의 저작권과 YouTube 이용약관을 지켜 주세요.

## 라이선스

[MIT](LICENSE)
