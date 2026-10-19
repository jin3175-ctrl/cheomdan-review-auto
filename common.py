"""공통 도우미 — 내정보.txt 읽기 · 브라우저 고르기 · 에고라이트 실행.

맥     → 에고라이트(ego lite): 내가 로그인한 브라우저로 사진 받기·임시저장을 직접 한다.
윈도우 → 어사이드(Aside): 원고를 보기 좋은 페이지로 만들어 두고, 어사이드에게 프롬프트 한 장으로 넣게 한다.
         사진 받기는 내 손으로 로그인한 크롬 부품(Playwright) 창으로 한다.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "work")
SPACE_NAME = "체험단 자동"

if hasattr(sys.stdout, "reconfigure"):          # 윈도우 콘솔에서 한글이 깨져 죽지 않게
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def myinfo() -> dict:
    """내정보.txt → {키: 값}. '(여기에 …)' 로 남은 칸은 빈칸으로 본다."""
    out = {}
    try:
        text = open(os.path.join(HERE, "내정보.txt"), encoding="utf-8-sig").read()
    except OSError:
        return out
    for line in text.splitlines():
        if line.strip().startswith("#") or not re.search(r"[:：]", line):
            continue
        k, v = re.split(r"[:：]", line, maxsplit=1)
        v = v.strip()
        if v.startswith("(여기에") or v.startswith("（여기에"):
            v = ""
        out[k.strip()] = v
    return out


def blog_id() -> str:
    v = myinfo().get("내 블로그ID", "")
    v = re.sub(r"^https?://(m\.)?blog\.naver\.com/", "", v).strip("/ ")
    return v


def need_blog_id() -> str:
    b = blog_id()
    if not b:
        print("[!] 내정보.txt 의 「내 블로그ID」가 비어 있습니다. 먼저 채워 주세요.")
        print("    (내 블로그 주소 blog.naver.com/여기부분)")
        sys.exit(1)
    return b


def mode() -> str:
    """'ego'(맥 기본) | 'aside'(윈도우 기본). 내정보.txt 「브라우저:」 줄이나 환경변수로 바꿀 수 있다."""
    v = (os.environ.get("CHEOMDAN_BROWSER") or myinfo().get("브라우저", "")).strip().lower()
    if v in ("에고", "에고라이트", "ego"):
        return "ego"
    if v in ("어사이드", "aside"):
        return "aside"
    return "ego" if sys.platform == "darwin" else "aside"


def ego_bin() -> str:
    for c in (shutil.which("ego-browser"), os.path.expanduser("~/.local/bin/ego-browser"),
              "/usr/local/bin/ego-browser", "/opt/homebrew/bin/ego-browser"):
        if c and os.path.exists(c):
            return c
    return ""


def run_ego(script: str, payload: dict, timeout: int = 1800, log_name: str = "ego.log") -> dict:
    """ego/<script> 를 에고라이트로 돌리고 마지막 JSON 한 줄을 돌려준다."""
    b = ego_bin()
    if not b:
        return {"ok": False, "why": "에고라이트가 없습니다 — https://lite.ego.app 에서 설치하고 앱을 한 번 열어 "
                                     "첫 화면을 끝내 주세요."}
    os.makedirs(WORK, exist_ok=True)
    pp = os.path.join(WORK, "ego_payload.json")
    with open(pp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    src = f"const PAYLOAD_PATH = {json.dumps(pp)};\n" + open(os.path.join(HERE, "ego", script), encoding="utf-8").read()
    try:
        p = subprocess.run([b, "nodejs"], input=src, text=True, capture_output=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        out = (p.stdout or "") + "\n" + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return {"ok": False, "why": "에고라이트가 너무 오래 걸려 멈췄습니다."}
    with open(os.path.join(WORK, log_name), "w", encoding="utf-8") as f:
        f.write(out)
    for line in out.splitlines():
        if line.startswith("[ego]"):
            print("   ", line[5:].strip())
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{") and '"ok"' in line:
            try:
                return json.loads(line)
            except ValueError:
                continue
    if "control" in out.lower():
        return {"ok": False, "why": "에고라이트 창을 지금 직접 쓰고 계십니다 — 손을 떼고 다시 실행해 주세요."}
    return {"ok": False, "why": "에고라이트 결과를 못 읽었습니다: " + out.strip()[-200:]}


def safe_name(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|\s]+', "_", (s or "").strip()).strip("_")
    return s[:30] or "가게"
