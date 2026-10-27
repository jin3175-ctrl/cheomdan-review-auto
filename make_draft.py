"""③ 원고 + 사진 → 네이버 «임시저장» (발행은 내가 직접)

    python3 make_draft.py 가게이름

맥     = 에고라이트가 글쓰기 화면에 제목·글·사진·지도·태그를 넣고 임시저장한다.
         (사진만 올렸던 처음 임시저장 글은 그대로 남는다 — 새 글을 확인한 뒤 지워도 된다)
윈도우 = 어사이드 CLI가 글쓰기 화면에 제목·글·사진·태그를 직접 넣고 「저장」만 누른다(aside_publish.py).
         CLI가 없거나 실패하면 예전 방식: 어사이드용/ 폴더에 「글 페이지」와 「붙여넣을 프롬프트」.
"""
from __future__ import annotations

import html
import os
import sys

import check_post
import common
import post

ASIDE_DIR = os.path.join(common.HERE, "어사이드용")


def by_ego(doc: dict, photos: str, bid: str) -> int:
    m = doc["meta"]
    payload = {"blogId": bid, "title": m.get("제목", ""), "blocks": post.blocks(doc, photos),
               "category": m.get("카테고리", "") or common.myinfo().get("내 카테고리", ""),
               "align": "center", "tags": m.get("태그", ""), "place": m.get("지도", ""),
               "spaceName": common.SPACE_NAME}
    print("\n에고라이트로 글쓰기 화면을 열어 넣습니다(임시저장까지만). 사진이 많으면 5~10분 걸립니다.")
    print("그동안 에고라이트 창을 만지지 마세요.\n")
    r = common.run_ego("publish.mjs", payload, timeout=2400, log_name="ego_publish.log")
    if not r.get("ok"):
        print("[!] 임시저장 실패:", r.get("why"))
        return 2
    print(f"\n✅ 임시저장 완료 · 사진 {r.get('images', 0)}장")
    if r.get("place"):
        print(f"   지도: {r['place']}  ← 주소가 맞는지 꼭 확인하세요")
    for n in r.get("notes") or []:
        print("   ⚠️", n)
    print("\n이제 내 블로그 글쓰기 → 「저장」 옆 숫자 → 맨 위 글을 열어 확인하고, 발행은 직접 누르세요.")
    print("사진만 올렸던 처음 글은 임시저장 목록에 그대로 있습니다(새 글을 확인한 뒤 지워도 됩니다).")
    return 0


def by_aside_cli(doc: dict, photos: str, bid: str) -> int:
    """윈도우 기본 — 어사이드 CLI가 글쓰기 화면에 제목·글·사진·태그를 직접 넣고 「저장」만 누른다."""
    import aside_publish
    if not aside_publish.available():
        print("[!] 어사이드 CLI(aside)가 없습니다 — 어사이드 → Settings → Developers → 「Aside CLI」 Install,")
        print("    그다음 클로드 코드 창을 닫았다가 다시 여세요.")
        return 2
    m = doc["meta"]
    tags = [t for t in m.get("태그", "").replace(",", " ").split() if t.strip("#")]
    print("\n어사이드 창에 글쓰기 화면을 열어 넣습니다(임시저장까지만). 사진이 많으면 5~10분 걸립니다.")
    print("그동안 어사이드 창을 만지거나 가리지 마세요.\n")
    r = aside_publish.draft(bid, m.get("제목", ""), post.blocks(doc, photos), log=lambda x: print("   ", x),
                            category=m.get("카테고리", "") or common.myinfo().get("내 카테고리", ""),
                            align="center", tags=tags)
    for n in r.get("notes") or []:
        print("   ⚠️", n)
    if not r.get("ok"):
        print("[!]", r.get("message"))
        return 2
    print(f"\n✅ {r.get('message')}")
    if m.get("지도"):
        print(f"   지도는 발행할 때 직접 «장소»로 넣어 주세요: {m['지도']}")
    print("\n이제 내 블로그 글쓰기 → 「저장」 옆 숫자 → 맨 위 글을 열어 확인하고, 발행은 직접 누르세요.")
    print("사진만 올렸던 처음 글은 임시저장 목록에 그대로 있습니다(새 글을 확인한 뒤 지워도 됩니다).")
    return 0


ASIDE_PROMPT = """너는 내 네이버 블로그 글쓰기 도우미야. 「발행」 버튼은 절대 누르지 마.

① 지금 열려 있는 「체험단 글」 탭을 끝까지 읽어. 사진 번호마다 그 아래 넣을 글이 적혀 있어.
② 새 탭에서 https://blog.naver.com/{blog_id}?Redirect=Write& 를 열어.
   로그인 화면이 나오면 멈추고 나에게 «로그인해 주세요»라고 말해. (아이디·비밀번호는 내가 직접 넣어)
   «작성 중인 글이 있습니다»가 뜨면 «취소».
③ 오른쪽 위 「저장」 옆 숫자를 눌러 임시저장 목록을 열고, 맨 위 글(사진만 있는 글)을 불러와.
④ 제목 칸에 「체험단 글」 탭의 제목을 넣어.
⑤ 첫 번째 사진 «위»에 「맨 앞 글」을 넣어. (광고 표시 문장이 있으면 반드시 맨 첫 줄)
⑥ 사진마다 그 사진 «바로 아래»를 눌러 같은 번호의 글을 넣어. (사진1 아래 → 「사진1 아래」 글 …)
   - ■ 표시 줄은 굵게 한 줄로, ▪ 정보 묶음은 인용구(모서리 모양)로 넣으면 좋아.
   - 사진 순서를 바꾸거나 사진을 지우지 마.
⑦ 태그·지도는 넣지 마(발행할 때 내가 직접 넣을게).
⑧ 오른쪽 위 「저장」(임시저장)만 눌러. 「발행」은 누르지 마.
⑨ 끝나면 «임시저장 완료»와 넣지 못한 칸이 있으면 그 번호를 알려줘.
"""


def by_aside(doc: dict, photos: str, bid: str, shop: str) -> int:
    os.makedirs(ASIDE_DIR, exist_ok=True)
    m = doc["meta"]
    bl = post.blocks(doc, photos)
    rel = os.path.relpath(photos, ASIDE_DIR).replace("\\", "/")
    secs, cur, label = [], [], "맨 앞 글 (첫 사진 위)"
    for b in bl:
        if b["type"] == "image":
            secs.append((label, cur, None))
            label, cur = f"사진{b['n']} 아래", []
            secs.append((None, None, b["n"]))
        elif b["type"] == "quote":
            cur.append(("quote", b["text"]))
        else:
            cur.append(("p", b["text"]))
    secs.append((label, cur, None))
    parts = []
    for lab, items, n in secs:
        if n is not None:
            parts.append(f'<div class="ph"><img src="{html.escape(rel)}/{n:02d}.jpg"><span>사진{n}</span></div>')
            continue
        if not items:
            continue
        parts.append(f"<h2>{html.escape(lab)}</h2>")
        for k, t in items:
            if k == "quote":
                inner = html.escape(t).replace("\n", "<br>")
                parts.append(f"<blockquote>{inner}</blockquote>" if "▪" in t else f"<p><b>■ {inner}</b></p>")
            else:
                parts.append(f"<p>{html.escape(t)}</p>")
    tags = html.escape(m.get("태그", ""))
    place = html.escape(m.get("지도", ""))
    page = os.path.join(ASIDE_DIR, f"{common.safe_name(shop)}_체험단글.html")
    with open(page, "w", encoding="utf-8") as f:
        f.write("<!doctype html><meta charset='utf-8'><title>체험단 글</title>"
                "<style>body{max-width:720px;margin:32px auto;font:17px/1.8 sans-serif;padding:0 16px}"
                "h1{font-size:24px}h2{font-size:15px;color:#06c;margin:26px 0 4px}"
                "blockquote{border:2px solid #999;margin:12px 0;padding:6px 14px}"
                ".ph{display:flex;gap:10px;align-items:center;margin:14px 0;color:#c00;font-weight:bold}"
                ".ph img{width:120px;border-radius:6px}.meta{color:#555;font-size:15px}</style>"
                f"<h1>제목: {html.escape(m.get('제목', ''))}</h1>"
                f"<p class='meta'>태그: {tags}<br>지도(장소): {place or '없음'}</p>" + "\n".join(parts))
    pp = os.path.join(ASIDE_DIR, "어사이드에_붙여넣을_프롬프트.txt")
    with open(pp, "w", encoding="utf-8") as f:
        f.write(ASIDE_PROMPT.format(blog_id=bid))
    print("\n✅ 어사이드용 준비 완료")
    print(f"   글 페이지: {page}")
    print(f"   프롬프트:  {pp}")
    print("\n이렇게 하세요:")
    print("  1. 글 페이지(.html) 파일을 어사이드 창으로 끌어다 놓기")
    print("  2. 프롬프트 파일을 메모장으로 열어 전부 복사 → 어사이드 Ask 칸에 붙여넣기")
    print("  3. 끝나면 임시저장 글을 열어 확인 → 발행할 때 태그·지도를 넣고 발행은 직접")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("사용: python3 make_draft.py 가게이름")
        return 1
    shop = sys.argv[1]
    bid = common.need_blog_id()
    if not check_post.run(shop):
        print("\n고칠 것을 고친 뒤 다시 실행하세요. (임시저장하지 않았습니다)")
        return 1
    src, photos = check_post.paths(shop)
    doc = post.read(src)
    if common.mode() == "ego":
        return by_ego(doc, photos, bid)
    r = by_aside_cli(doc, photos, bid)
    if r == 0:
        return 0
    print("\n어사이드 CLI로 못 넣었습니다 → 예전 방식(글 페이지 + 프롬프트)으로 준비합니다.")
    return by_aside(doc, photos, bid, shop)


if __name__ == "__main__":
    sys.exit(main())
