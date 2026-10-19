"""원고.txt 읽기 · 점검 — make_draft.py 와 check_post.py 가 같이 쓴다.

원고.txt 모양 (--- 위는 정보, 아래는 본문):

    제목: 부천 신중동 삼겹살, 두툼한 목살에 반한 동네 고깃집
    종류: 협찬                  ← 협찬(체험단으로 받은 곳) / 내돈내산(내 돈으로 간 곳)
    필수키워드: 부천 신중동 삼겹살
    태그: #부천신중동삼겹살 #부천삼겹살 #신중동맛집 #부천고깃집 #신중동삼겹살
    지도: 참돼짓간 부천신중동점   ← 방문형만. 체인점은 지점명까지
    카테고리: 맛집
    ---
    #협찬 참돼짓간으로부터 식사를 무상으로 제공받아 솔직하게 작성했습니다.
    도입 문장 한두 줄
    [사진1]
    사진1 아래 문장 1~3줄
    [인용] 소제목
    [사진2]
    ...
    [정보]
    ▪ 주소: …
    ▪ 영업시간: …
    [/정보]

- 한 줄 = 한 문단(사이에 빈 줄이 저절로 들어간다)
- 강조: {{빨강:글자}}(빨강+굵게) · {{굵게:글자}} · {{형광:글자}}(노란 바탕)
"""
from __future__ import annotations

import os
import re

PHOTO = re.compile(r"^\s*\[사진\s*(\d+)\s*\]\s*$")
QUOTE = re.compile(r"^\s*\[인용\]\s*(.+)$")
EXTRA = re.compile(r"^\s*\[사진\s*(\d+)\s*추가\s*[:：]\s*(.+?)\]\s*$")   # 보조 사진(extra_photos.py)
SPAN = re.compile(r"\{\{(빨강|굵게|굵빨|형광|형광빨):(.+?)\}\}")
RED, YELLOW = "rgb(255, 0, 16)", "rgb(255, 255, 0)"
AD_WORDS = ("#협찬", "#광고", "무상으로 제공", "무상 제공", "제공받아", "원고료", "협찬을 받아", "광고")
BANNED = ("무조건", "100%", "효과 보장", "보장합니다", "치료", "완치", "의사", "최저가")


def read(path: str) -> dict:
    text = open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")
    if "\n---" not in text:
        raise SystemExit("[!] 원고에 --- 줄이 없습니다(위는 정보, 아래는 본문).")
    head, body = text.split("\n---", 1)
    meta = {}
    for line in head.splitlines():
        if re.search(r"[:：]", line):
            k, v = re.split(r"[:：]", line, maxsplit=1)
            meta[k.strip()] = v.strip()
    return {"meta": meta, "lines": [l.rstrip() for l in body.lstrip("-").split("\n")]}


def spans_of(raw: str):
    out, plain, cur = [], "", 0
    for m in SPAN.finditer(raw):
        plain += raw[cur:m.start()]
        s = len(plain)
        plain += m.group(2)
        kind = m.group(1)
        st = {}
        if "빨" in kind:
            st.update(color=RED, bold=True)
        if kind == "굵게":
            st["bold"] = True
        if "형광" in kind:
            st["bg"] = YELLOW
        out.append([s, len(plain), st])
        cur = m.end()
    plain += raw[cur:]
    return plain, out


def blocks(doc: dict, photo_dir: str) -> list:
    """본문 → 에고라이트 드라이버가 아는 블록 목록."""
    res, info, in_info = [], [], False
    qstyles = ["default", "quotation_bubble", "quotation_postit"]
    qn = 0
    for line in doc["lines"]:
        s = line.strip()
        if not s:
            continue
        if s == "[정보]":
            in_info, info = True, []
            continue
        if s == "[/정보]":
            in_info = False
            res.append({"type": "quote", "style": "quotation_corner", "text": "\n".join(info)})
            continue
        if in_info:
            info.append(SPAN.sub(lambda m: m.group(2), s))
            continue
        m = EXTRA.match(s)
        if m:
            n = int(m.group(1))
            pth = os.path.join(photo_dir, f"{n:02d}.jpg")
            if os.path.exists(pth):
                res.append({"type": "image", "n": n, "path": pth, "extra": True})
            else:   # 못 구한 자리 → 빨간 글자로 남긴다(주인이 직접 넣기)
                res.append({"type": "marker", "n": n, "text": f"[사진{n}] {m.group(2)}"})
            continue
        m = PHOTO.match(s)
        if m:
            n = int(m.group(1))
            res.append({"type": "image", "n": n, "path": os.path.join(photo_dir, f"{n:02d}.jpg")})
            continue
        m = QUOTE.match(s)
        if m:
            res.append({"type": "quote", "style": qstyles[qn % len(qstyles)], "text": SPAN.sub(lambda x: x.group(2), m.group(1))})
            qn += 1
            continue
        plain, sp = spans_of(s)
        res.append({"type": "text", "text": plain, "spans": sp})
    return res


def check(doc: dict, photo_dir: str) -> tuple:
    """(고칠 것[], 살펴볼 것[]) — 고칠 것이 있으면 임시저장하지 않는다."""
    err, warn = [], []
    meta = doc["meta"]
    title = meta.get("제목", "")
    kind = meta.get("종류", "")
    kw = meta.get("필수키워드", "")
    bl = blocks(doc, photo_dir)
    texts = [b["text"] for b in bl if b["type"] in ("text", "quote")]
    body = "\n".join(texts)

    if not title:
        err.append("제목이 비어 있습니다.")
    elif len(title) > 40:
        warn.append(f"제목이 {len(title)}자입니다 — 40자 안쪽이 폰에서 안 잘립니다.")
    if kind not in ("협찬", "내돈내산"):
        err.append("종류: 칸에 «협찬» 또는 «내돈내산» 중 하나를 적어 주세요.")

    # 🔴광고 표시 — 제목 또는 본문 첫 부분(첫 두 문단)
    first = " ".join([title] + [b["text"] for b in bl if b["type"] == "text"][:2])
    if kind == "협찬":
        if not any(w in first for w in AD_WORDS):
            err.append("협찬 글인데 광고 표시가 제목·첫 부분에 없습니다 — 첫 줄에 "
                       "「#협찬 ○○로부터 무상으로 제공받아 작성했습니다」를 넣어 주세요.")
        if "체험단" in first and not any(w in first for w in AD_WORDS):
            err.append("「체험단」이라고만 쓰면 광고 표시로 인정되지 않습니다.")
    elif kind == "내돈내산" and any(w in first for w in ("#협찬", "무상으로 제공")):
        warn.append("내돈내산인데 협찬 문구가 들어 있습니다 — 내 돈으로 간 곳이면 빼세요.")

    if kw:
        if not title.replace(" ", "").startswith(kw.replace(" ", "")[:4]):
            warn.append(f"필수키워드 «{kw}»를 제목 맨 앞에 두면 검색에 잘 걸립니다.")
        c = body.count(kw)
        if c < 5 or c > 7:
            warn.append(f"본문에 필수키워드가 {c}번 — 5~7번이 알맞습니다.")
    n_chars = len(re.sub(r"\s", "", body))
    if n_chars < 1300:
        warn.append(f"글자 수(공백 빼고) {n_chars}자 — 1,300자 이상이 좋습니다.")
    tags = [t for t in meta.get("태그", "").split() if t.startswith("#")]
    if len(tags) < 3:
        warn.append("태그가 3개보다 적습니다(5개 권장).")

    # 사진
    have = sorted(int(f[:2]) for f in os.listdir(photo_dir) if re.match(r"^\d\d\.jpg$", f)) if os.path.isdir(photo_dir) else []
    used = [b["n"] for b in bl if b["type"] == "image" and not b.get("extra")]
    marks = [b["n"] for b in bl if b["type"] == "marker"]
    if marks:
        warn.append(f"빨간 자리로 남는 사진: {marks} — 임시저장 뒤 직접 넣어 주세요.")
    if any(b.get("extra") for b in bl):
        warn.append("보조 사진(무료 사진·AI 그림)이 들어갑니다 — AI 그림이면 발행 전 그 사진의 «AI 활용 설정»을 켜 주세요.")
    for n in used:
        if n not in have:
            err.append(f"[사진{n}] 파일이 없습니다({photo_dir}).")
    if len(set(used)) != len(used):
        err.append("같은 사진 번호가 두 번 나옵니다.")
    miss = [n for n in have if n not in used]
    if miss:
        warn.append(f"글에 안 쓴 사진: {miss}")
    prev, gap = None, 0
    for i, b in enumerate(bl):
        if b["type"] in ("image", "marker"):
            b = dict(b, type="image")
            if prev == "image":
                warn.append(f"[사진{b['n']}] 앞에 글이 없습니다(사진 두 장이 붙음) — 짧은 한 줄을 넣어 주세요.")
            if i and gap > 100 and used and b["n"] != used[0]:
                warn.append(f"[사진{b['n']}] 앞 글이 {gap}자 — 사진 사이 글은 짧게(1~3줄).")
            gap = 0
        elif b["type"] == "text":
            gap += len(re.sub(r"\s", "", b["text"]))
        prev = b["type"]

    for line in doc["lines"]:
        s = line.strip()
        if s.startswith("[") and not (PHOTO.match(s) or QUOTE.match(s) or EXTRA.match(s) or s in ("[정보]", "[/정보]")):
            err.append(f"대괄호로 시작하는 줄은 글이 삼켜집니다: «{s[:20]}» — 고쳐 주세요.")
    bad = [w for w in BANNED if w in body or w in title]
    if bad:
        warn.append(f"조심할 말: {bad} — 과장·의료 표현은 빼 주세요.")
    return err, warn
