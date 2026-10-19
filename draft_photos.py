"""① 방금 임시저장한 글의 사진을 내 컴퓨터로 받는다.

    python3 draft_photos.py 가게이름              # 임시저장 목록 맨 위(방금 저장한 글)
    python3 draft_photos.py 가게이름 --글 "제목 일부"   # 특정 임시저장 글

받은 사진: 글/<가게이름>/사진/01.jpg, 02.jpg … (올린 순서 그대로)

맥     = 에고라이트로 받는다(에고라이트에 네이버 로그인만 돼 있으면 된다).
윈도우 = 크롬 부품 창으로 받는다. 처음 한 번 창이 뜨면 **내가 직접** 네이버에 로그인한다.
안 되면: 폰 사진을 글/<가게이름>/사진/ 폴더에 직접 넣어도 된다(이 단계 건너뛰기).
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import time

import common

SESSION = os.path.join(common.HERE, "session", "naver_state.json")


def out_dir(shop: str) -> str:
    return os.path.join(common.HERE, "글", common.safe_name(shop), "사진")


def by_ego(bid: str, kw: str, outdir: str) -> dict:
    print("에고라이트로 임시저장 글을 열어 사진을 받습니다…")
    return common.run_ego("draft_photos.mjs", {"blogId": bid, "keyword": kw, "outDir": outdir,
                                               "spaceName": common.SPACE_NAME},
                          timeout=900, log_name="ego_draft_photos.log")


def _login(p) -> None:
    """크롬 부품 창을 띄워 **주인이 직접** 로그인하게 한다(비밀번호를 대신 넣지 않는다)."""
    print()
    print("  네이버 로그인 창을 띄웁니다. 창에서 직접 로그인해 주세요(‘로그인 상태 유지’ 켜기).")
    print("  로그인이 끝나면 저절로 다음으로 넘어갑니다. (5분 기다립니다)")
    br = p.chromium.launch(headless=False)
    ctx = br.new_context()
    pg = ctx.new_page()
    pg.goto("https://nid.naver.com/nidlogin.login")
    for _ in range(300):
        time.sleep(1)
        try:
            if any(c["name"] == "NID_AUT" for c in ctx.cookies()):
                break
        except Exception:  # noqa: BLE001
            pass
    else:
        br.close()
        raise SystemExit("[!] 5분 안에 로그인이 안 됐습니다. 다시 실행해 주세요.")
    os.makedirs(os.path.dirname(SESSION), exist_ok=True)
    ctx.storage_state(path=SESSION)
    br.close()
    print("  로그인 저장 완료.")


def by_chrome(bid: str, kw: str, outdir: str) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "why": "부품(playwright)이 없습니다 — 설치 파일을 먼저 실행해 주세요."}
    js_open = """() => {
        const vis = e => e && (e.offsetParent || e.getClientRects().length);
        document.querySelectorAll('button.se-popup-button-cancel, button.se-help-panel-close-button')
          .forEach(b => { if (vis(b)) b.click(); });
    }"""
    with sync_playwright() as p:
        if not os.path.exists(SESSION):
            _login(p)
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(storage_state=SESSION)
        pg = ctx.new_page()
        pg.goto(f"https://blog.naver.com/{bid}/postwrite", wait_until="domcontentloaded")
        pg.wait_for_timeout(3500)
        if "nidlogin" in pg.url:
            br.close()
            os.remove(SESSION)
            return {"ok": False, "why": "로그인이 풀렸습니다 — 한 번 더 실행하면 로그인 창이 뜹니다."}
        for _ in range(3):
            pg.evaluate(js_open)
            pg.wait_for_timeout(500)
        pg.wait_for_selector(".se-canvas, .se-content", timeout=30000)
        n = pg.evaluate("""() => {
            const vis = e => e && (e.offsetParent || e.getClientRects().length);
            const b = [...document.querySelectorAll('button')].filter(vis).find(x => /^\\d+$/.test((x.innerText||'').trim()));
            if (b) { b.click(); return (b.innerText||'').trim(); } return '';
        }""")
        if not n or n == "0":
            br.close()
            return {"ok": False, "why": "임시저장 글이 없습니다 — 폰 블로그 앱에서 «임시저장»을 눌렀는지 확인해 주세요."}
        pg.wait_for_timeout(1500)
        picked = pg.evaluate("""(kw) => {
            const vis = e => e && (e.offsetParent || e.getClientRects().length);
            const L = [...document.querySelectorAll('[class*="temp"] li, [class*="list"] li, li[class*="item"]')]
                .filter(vis).filter(el => (el.innerText||'').trim().length > 2)
                .filter(el => !/추가$/.test((el.innerText||'').trim()));
            if (!L.length) return '';
            let t = kw ? L.find(el => (el.innerText||'').includes(kw)) : null;
            if (!t) t = L[0];
            (t.querySelector('a, button, [class*=title]') || t).click();
            return (t.innerText||'').trim().replace(/\\s+/g,' ').slice(0,60);
        }""", kw)
        pg.wait_for_timeout(1000)
        pg.evaluate("""() => { const vis = e => e && (e.offsetParent || e.getClientRects().length);
            document.querySelectorAll('button.se-popup-button-confirm').forEach(b => { if (vis(b)) b.click(); }); }""")
        pg.wait_for_timeout(3500)
        for _ in range(5):   # 아직 안 뜬 사진(회색 자리표시)만 천천히 다시 비춘다
            pend = pg.evaluate("""() => [...document.querySelectorAll('.se-component.se-image')]
                .map((c, i) => [i, (c.querySelector('img') || {}).src || ''])
                .filter(([, s]) => !s || s.startsWith('data:')).map(([i]) => i)""")
            if not pend:
                break
            for i in pend:
                pg.evaluate("(i) => { const c = document.querySelectorAll('.se-component.se-image')[i]; if (c) c.scrollIntoView({block:'center'}); }", i)
                pg.wait_for_timeout(600)
        info = pg.evaluate("""() => {
            const canvas = document.querySelector('.se-canvas') || document.querySelector('.se-content');
            const comps = [...canvas.querySelectorAll('.se-component')].filter(c => !c.parentElement.closest('.se-component'));
            const imgs = []; let videos = 0;
            for (const c of comps) {
              if (/se-image/.test(c.className)) c.querySelectorAll('img').forEach(im => { if (im.src && !im.src.startsWith('data:')) imgs.push(im.src); });
              else if (/se-video/.test(c.className)) videos++;
            }
            const title = (document.querySelector('.se-section-documentTitle')||{}).innerText || '';
            return {imgs: [...new Set(imgs)], videos, title: title.trim()};
        }""")
        os.makedirs(outdir, exist_ok=True)
        got, fails = 0, []
        for i, src in enumerate(info["imgs"], 1):
            r = ctx.request.get(src)          # 주소 그대로(토큰이 붙어 있다 — 바꾸면 404)
            if r.status == 200:
                open(os.path.join(outdir, f"{i:02d}.jpg"), "wb").write(r.body())
                got += 1
            else:
                fails.append(i)
        ctx.storage_state(path=SESSION)
        br.close()
    return {"ok": got > 0, "count": got, "fails": fails, "videos": info["videos"], "title": info["title"],
            "picked": picked, "why": "" if got else "사진을 하나도 못 받았습니다."}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("shop", help="가게 이름(폴더 이름이 됩니다)")
    ap.add_argument("--글", dest="kw", default="", help="임시저장 제목 일부(없으면 맨 위 글)")
    a = ap.parse_args()
    bid = common.need_blog_id()
    outdir = out_dir(a.shop)
    old = sorted(glob.glob(os.path.join(outdir, "*.jpg")))
    if old:
        print(f"이미 사진 {len(old)}장이 있습니다: {outdir}")
        print("다시 받으려면 그 폴더를 비우고 실행하세요. 지금 있는 사진으로 진행합니다.")
        return
    r = by_ego(bid, a.kw, outdir) if common.mode() == "ego" else by_chrome(bid, a.kw, outdir)
    if not r.get("ok"):
        print("[!]", r.get("why"))
        print(f"    안 되면 폰 사진을 이 폴더에 직접 넣고 다음 단계로 가도 됩니다:\n    {outdir}")
        sys.exit(2)
    print()
    print(f"사진 {r.get('count')}장 받음 → {outdir}")
    print(f"불러온 임시저장 글: {r.get('picked') or r.get('title') or '(제목 없음)'}")
    if r.get("videos"):
        print(f"동영상 {r['videos']}개는 받지 않았습니다(글에는 그대로 두세요).")
    if r.get("fails"):
        print(f"못 받은 사진 번호: {r['fails']}")


if __name__ == "__main__":
    main()
