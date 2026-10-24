"""서로이웃(서이추) 자동 신청 — 우리 동네 맛집·카페 블로그에 (2026-10-25 · 체험단 2기 2회차)

    python3 buddy_auto.py            오늘 몫 신청(사람마다 2.5~4분 간격)
    python3 buddy_auto.py --dry      신청 없이 «누구에게 갈지»만 보기(간격 없음)
    python3 buddy_auto.py --cap 3    오늘은 3명만(상한보다 줄이는 것만 된다)

맥     = 에고라이트(ego/buddy.mjs) · 윈도우 = 어사이드 CLI(aside_drive.py)가 화면을 직접 움직인다.
에디님 블로그에서 2026-10-14부터 쓰는 완전 자동 방식을 수강생 계정에 맞게 더 조였다.

🔴안전장치 (에디님 2026-10-25 확정 — 끄거나 늘리지 말 것)
  · 하루 상한: 처음 7일은 **5명**, 그다음부터 **10명** (같은 날 다시 돌려도 넘지 않는다)
  · 간격: 사람마다 **150~240초** 랜덤
  · 네이버 경고(제한·스팸·자동입력 방지·잠시 후 다시·비정상적인 …)가 뜨면 **그날 바로 멈춤**
  · 연속 3번 실패해도 그날 멈춤
  · 「상대방의 이웃수」·「블로그 주인이 설정」이 뜨면 그 블로그만 건너뜀
  · 서이추기록/장부.json 으로 같은 사람에게 두 번 가지 않는다 — **지우지 말 것**
  · 체험단 블로그 아이디로 로그인돼 있지 않으면 시작하지 않는다
  · 신청 메시지는 서이추_인사말.txt 에서 돌아가며 쓴다(주인이 고른 문장)
"""
from __future__ import annotations

import argparse
import html as _html
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime

import common

REC = os.path.join(common.HERE, "서이추기록")
LEDGER = os.path.join(REC, "장부.json")
START = os.path.join(REC, "시작일.txt")
MSG_FILE = os.path.join(common.HERE, "서이추_인사말.txt")
TODAY = date.today().isoformat()
STAMP = date.today().strftime("%Y%m%d")
DAY_FILE = os.path.join(REC, f"{TODAY}.json")
STOP_FILE = os.path.join(REC, f"멈춤_{STAMP}.txt")
LOG_FILE = os.path.join(REC, f"기록_{STAMP}.log")

GAP = (150, 240)            # 사람마다 간격(초)
CAP_FIRST, CAP_AFTER, FIRST_DAYS = 5, 10, 7
MAX_FAILS = 3
EXCLUDE = ["성인", "출장", "제휴문의", "도박", "토토", "대출", "코인", "리딩방", "부업", "마사지", "분양"]
SKIP_OTHER_SIDE = ("상대방의 이웃수", "블로그 주인이 설정")
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


def log(msg: str) -> None:
    line = f"{datetime.now():%H:%M:%S} {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_json(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return d


def save_json(p, data):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


# ───────────────────────── 하루 상한 ─────────────────────────

def today_cap() -> int:
    try:
        first = date.fromisoformat(open(START, encoding="utf-8").read().strip())
    except (OSError, ValueError):
        return CAP_FIRST
    return CAP_FIRST if (date.today() - first).days < FIRST_DAYS else CAP_AFTER


def mark_start():
    if not os.path.exists(START):
        with open(START, "w", encoding="utf-8") as f:
            f.write(TODAY)


# ───────────────────────── 신청 메시지 ─────────────────────────

def messages(town: str) -> list:
    try:
        lines = open(MSG_FILE, encoding="utf-8-sig").read().splitlines()
    except OSError:
        lines = []
    out = []
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        ln = ln.replace("{동네}", town or "우리 동네").strip()
        if 5 <= len(ln) <= 60:
            out.append(ln)
    return out


def pick_message(msgs: list, last: str) -> str:
    cand = [m for m in msgs if m != last] or msgs
    return random.choice(cand) if cand else ""


# ───────────────────────── 대상 찾기(읽기만) ─────────────────────────

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def keywords(info: dict) -> list:
    own = [k.strip() for k in re.split(r"[,，]", info.get("서이추 키워드", "")) if k.strip()]
    town = info.get("내 동네", "").strip()
    if own:
        return own
    if not town:
        return []
    return [f"{town} 맛집", f"{town} 카페", f"{town} 맛집 후기", f"{town} 맛집 추천",
            f"{town} 내돈내산", f"{town} 체험단", f"{town} 밥집", f"{town} 디저트"]


def search(keyword: str, need_any: list, me: str) -> list:
    """블로그 탭 검색 상위 — 동네 이름이 제목·미리보기에 있는 것만(같은 이름 다른 지역 섞임 방지)."""
    url = "https://m.search.naver.com/search.naver?ssc=tab.m_blog.all&query=" + urllib.parse.quote(keyword)
    try:
        body = fetch(url)
    except Exception as e:  # noqa: BLE001
        log(f"  검색 실패({keyword}): {str(e)[:60]}")
        return []
    pat = re.compile(r'<a[^>]+href="(https://m\.blog\.naver\.com/([A-Za-z0-9_-]+)/(\d{9,}))"[^>]*>(.*?)</a>', re.S)
    hits, order = {}, []
    for m in pat.finditer(body):
        u, bid, log_no, text = m.group(1), m.group(2), m.group(3), strip_tags(m.group(4))
        if len(text) < 6:
            continue
        if u not in hits:
            hits[u] = {"blogId": bid, "logNo": log_no, "title": text, "snippet": "", "kw": keyword}
            order.append(u)
        elif not hits[u]["snippet"]:
            hits[u]["snippet"] = text
    out, seen = [], set()
    for u in order:
        h = hits[u]
        hay = f"{h['title']} {h['snippet']}"
        if h["blogId"] == me or h["blogId"] in seen or any(w in hay for w in EXCLUDE):
            continue
        if need_any and not any(w in hay for w in need_any):
            continue
        seen.add(h["blogId"])
        out.append(h)
    return out


def latest_date(blog_id: str) -> str:
    url = ("https://blog.naver.com/PostTitleListAsync.naver"
           f"?blogId={blog_id}&viewdate=&currentPage=1&categoryNo=0&parentCategoryNo=&countPerPage=5")
    try:
        body = fetch(url)
    except Exception:  # noqa: BLE001
        return ""
    m = re.search(r'"addDate"\s*:\s*"(.*?)"', body)
    return m.group(1) if m else ""


def recent_enough(add_date: str, days: int = 30) -> bool:
    """최근 30일 안에 글을 쓴 블로그만. 날짜를 못 읽으면 건너뛴다(쉬는 블로그일 수 있다)."""
    if not add_date:
        return False
    if "전" in add_date:          # «3시간 전» 같은 표시
        return True
    m = re.match(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", add_date)
    if not m:
        return False
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return False
    return (date.today() - d).days <= days


class Candidates:
    def __init__(self, info: dict, me: str):
        self.kws = keywords(info)
        town = info.get("내 동네", "").strip()
        self.need_any = [w for w in town.split() if len(w) >= 2]
        self.me = me
        self.queue: list = []
        self.seen: set = set()
        self.i = 0

    def next(self, ledger: dict):
        while True:
            while self.queue:
                h = self.queue.pop(0)
                bid = h["blogId"]
                if bid in self.seen or bid in ledger:
                    continue
                self.seen.add(bid)
                d = latest_date(bid)
                time.sleep(random.uniform(0.4, 0.9))
                if not recent_enough(d):
                    log(f"  건너뜀 {bid} — 최근 30일 글 없음({d or '날짜 못 읽음'})")
                    continue
                return h
            if self.i >= len(self.kws):
                return None
            kw = self.kws[self.i]
            self.i += 1
            found = search(kw, self.need_any, self.me)
            log(f"  「{kw}」 후보 {len(found)}곳")
            self.queue.extend(found)
            time.sleep(random.uniform(0.8, 1.6))


# ───────────────────────── 브라우저 ─────────────────────────

class Driver:
    def __init__(self):
        self.mode = common.mode()
        self.pg = None
        if self.mode == "aside":
            import aside_drive
            self.ad = aside_drive
            self.pg = aside_drive.AsidePage()

    @property
    def name(self):
        return "어사이드" if self.mode == "aside" else "에고라이트"

    def session(self) -> dict:
        if self.mode == "aside":
            return self.ad.op_session(self.pg)
        return common.run_ego("buddy.mjs", {"op": "session"}, timeout=180, log_name="ego_buddy.log")

    def buddy(self, target: str, message: str, dry: bool) -> dict:
        try:
            if self.mode == "aside":
                return self.ad.op_buddy(self.pg, target, message, dry)
            return common.run_ego("buddy.mjs", {"op": "buddy", "target": target, "message": message, "dry": dry},
                                  timeout=300, log_name="ego_buddy.log")
        except RuntimeError as e:
            return {"ok": False, "why": str(e)[:200]}

    def close(self):
        if self.pg:
            self.pg.close()


# ───────────────────────── 메인 ─────────────────────────

def stop_today(why: str):
    with open(STOP_FILE, "w", encoding="utf-8") as f:
        f.write(f"{datetime.now():%H:%M} {why}\n")
    log(f"⛔ 오늘 서이추를 멈췄습니다 — {why}")
    log("   네이버가 보낸 신호일 수 있습니다. 오늘은 더 돌리지 마세요.")
    log("   어떤 문구가 떴는지 화면 사진을 찍어 단톡방에 올려 주세요. 내일 다시 하면 됩니다.")


def main() -> int:
    ap = argparse.ArgumentParser(description="서로이웃 자동 신청(하루 상한·간격·경고 시 멈춤)")
    ap.add_argument("--dry", action="store_true", help="신청 없이 누구에게 갈지만 보기")
    ap.add_argument("--cap", type=int, default=0, help="오늘 몫을 이보다 줄이기(늘리기는 안 됨)")
    args = ap.parse_args()
    os.makedirs(REC, exist_ok=True)

    me = common.need_blog_id()
    info = common.myinfo()
    if os.path.exists(STOP_FILE) and not args.dry:
        log("⛔ 오늘은 이미 멈춘 날입니다: " + open(STOP_FILE, encoding="utf-8").read().strip())
        log("   내일 다시 해 주세요.")
        return 0
    msgs = messages(info.get("내 동네", ""))
    if not msgs:
        print("[!] 서이추_인사말.txt 에 쓸 문장이 없습니다. 인사말을 2개 이상 남겨 주세요.")
        return 1
    if not keywords(info):
        print("[!] 내정보.txt 의 「내 동네」(또는 「서이추 키워드」)가 비어 있습니다. 먼저 채워 주세요.")
        return 1

    cap = today_cap()
    if args.cap > 0:
        cap = min(cap, args.cap)
    day = load_json(DAY_FILE, {"date": TODAY, "items": []})
    done = sum(1 for x in day["items"] if x.get("result") == "신청")
    left = cap - done if not args.dry else cap
    log(f"════ 서이추 {'미리보기(신청 안 함)' if args.dry else '시작'} — 오늘 상한 {cap}명 · 이미 {done}명 · 남은 몫 {max(0, left)}명")
    if left <= 0:
        log("오늘 몫을 다 했습니다. 내일 다시 해 주세요.")
        return 0

    try:
        drv = Driver()
    except RuntimeError as e:
        print("[!]", e)
        return 1
    try:
        r = drv.session()
        url = r.get("url", "")
        if not r.get("ok") or "nidlogin" in url:
            log(f"✗ {drv.name}에 네이버 로그인이 안 돼 있습니다 — {drv.name}를 열고 체험단 블로그 아이디로 직접 로그인해 주세요.")
            return 1
        if me not in url:
            log(f"✗ {drv.name}가 다른 블로그 계정으로 로그인돼 있습니다({url[:70]}).")
            log(f"   체험단 블로그({me})로 로그인한 뒤 다시 해 주세요. 홈판 블로그로는 돌리지 않습니다.")
            return 1
        log(f"✓ 계정 확인 — {me} ({drv.name})")

        cands = Candidates(info, me)
        last_msg, fails, busy, n = "", 0, 0, 0
        while n < left:
            ledger = load_json(LEDGER, {})
            h = cands.next(ledger)
            if h is None:
                log("후보가 더 없습니다. 내정보.txt 에 「서이추 키워드:」 줄을 넣어 키워드를 늘려 보세요.")
                break
            bid = h["blogId"]
            msg = pick_message(msgs, last_msg)
            log(f"→ {bid} 「{h['title'][:30]}」 ({h['kw']})")
            res = drv.buddy(bid, msg, args.dry)
            why = str(res.get("why") or "")
            item = {"at": datetime.now().strftime("%H:%M:%S"), "blogId": bid, "title": h["title"][:60],
                    "keyword": h["kw"], "message": msg, "why": why[:160]}
            if why == "user_control":
                busy += 1
                log(f"  {drv.name} 창을 지금 직접 쓰고 계십니다 — 5분 뒤 다시 합니다(손을 떼 주세요).")
                cands.seen.discard(bid)
                cands.queue.insert(0, h)
                if busy >= 3:
                    log("  세 번 연속 창을 쓰고 계셔서 오늘은 여기까지 합니다.")
                    break
                time.sleep(300)
                continue
            busy = 0
            if args.dry:
                item["result"] = "미리보기" if res.get("ok") else "건너뜀"
                log(f"  {'✓ 신청 가능' if res.get('ok') else '건너뜀'} · {why[:60]}" + (f" · 메시지: {msg}" if res.get("ok") else ""))
                if res.get("ok"):
                    n += 1
                continue

            entry = ledger.setdefault(bid, {})
            if res.get("ok"):
                fails = 0
                n += 1
                last_msg = msg
                mark_start()
                entry.update(requested=TODAY, message=msg)
                item["result"] = "신청"
                log(f"  ✓ 서이추 신청 ({n}/{left}) · {msg}")
            elif res.get("blocked") or res.get("limit") or "세션만료" in why:
                item["result"] = "멈춤"
                day["items"].append(item)
                save_json(DAY_FILE, day)
                save_json(LEDGER, ledger)
                stop_today(res.get("blocked") or why[:80])
                return 2
            elif any(w in why for w in SKIP_OTHER_SIDE) or res.get("noBuddy"):
                entry["skipped"] = f"{TODAY} 상대 쪽 제한"
                item["result"] = "건너뜀"
                log("  건너뜀 — 상대 블로그 쪽 제한(이 사람만 넘어갑니다)")
            elif res.get("already"):
                entry["already"] = TODAY
                item["result"] = "건너뜀"
                log("  건너뜀 — 이미 이웃이거나 신청 중")
            else:
                fails += 1
                item["result"] = "실패"
                log(f"  ✗ 실패 ({fails}/{MAX_FAILS}) · {why[:100]}")
                if fails >= MAX_FAILS:
                    day["items"].append(item)
                    save_json(DAY_FILE, day)
                    save_json(LEDGER, ledger)
                    stop_today(f"연속 {MAX_FAILS}번 실패 — 마지막: {why[:60]}")
                    return 2
            day["items"].append(item)
            save_json(DAY_FILE, day)
            save_json(LEDGER, ledger)
            if item["result"] in ("신청", "실패") and n < left:
                wait = random.uniform(*GAP)
                log(f"  다음 사람까지 {int(wait // 60)}분 {int(wait % 60)}초 쉽니다(계정을 지키는 간격입니다)")
                time.sleep(wait)
    finally:
        drv.close()

    got = sum(1 for x in day["items"] if x.get("result") == "신청")
    log(f"════ 끝 — 오늘 신청 {got}명 / 상한 {cap}명" + (" (미리보기)" if args.dry else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
