"""(필요할 때만) 모자란 사진 채우기 — 내가 찍은 사진이 본체, 이건 보조다.

    python3 extra_photos.py 가게이름

원고.txt 의 `[사진21 추가: 장면 설명]` 줄을 찾아 글/<가게>/사진/21.jpg 를 만든다.
순서(전부 무료): ① 픽사베이 무료 사진(내정보.txt 「사진 키」) → ② 제미나이(에고라이트·맥)
              → ③ 챗GPT(에고라이트·맥) → ④ 그래도 없으면 글에 빨간 [사진N] 자리로 남긴다(내가 직접 넣기).

🔴가게·음식·메뉴판처럼 «내가 본 것»을 지어낸 그림으로 채우지 않는다. 보조 사진은
  동네 풍경·계절 분위기·재료 설명처럼 «방문 증거가 아닌 자리»에만 쓴다.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import urllib.parse
import urllib.request

import check_post
import common
import post


def pixabay(query: str, out: str, key: str) -> bool:
    try:
        url = "https://pixabay.com/api/?" + urllib.parse.urlencode({
            "key": key, "q": query[:100], "image_type": "photo", "orientation": "horizontal",
            "safesearch": "true", "per_page": 10, "lang": "ko" if re.search(r"[가-힣]", query) else "en"})
        with urllib.request.urlopen(url, timeout=20) as r:
            hits = json.loads(r.read().decode("utf-8")).get("hits") or []
        if not hits:
            return False
        h = random.choice(hits[:10])
        req = urllib.request.Request(h.get("largeImageURL") or h.get("webformatURL"), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as ir:
            open(out, "wb").write(ir.read())
        return os.path.getsize(out) > 1000
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    if len(sys.argv) < 2:
        print("사용: python3 extra_photos.py 가게이름")
        return 1
    src, photos = check_post.paths(sys.argv[1])
    doc = post.read(src)
    want = [(int(m.group(1)), m.group(2).strip()) for l in doc["lines"]
            if (m := post.EXTRA.match(l.strip()))]
    want = [(n, d) for n, d in want if not os.path.exists(os.path.join(photos, f"{n:02d}.jpg"))]
    if not want:
        print("채울 보조 사진이 없습니다.")
        return 0
    os.makedirs(photos, exist_ok=True)
    key = common.myinfo().get("사진 키", "")
    left = []
    for n, d in want:
        out = os.path.join(photos, f"{n:02d}.jpg")
        if key and pixabay(d, out, key):
            print(f"  사진{n}: 무료 사진 ✅")
        else:
            left.append((n, d))
    if left and common.mode() == "ego":
        import ego_images
        for name, fn in (("제미나이", ego_images.gemini), ("챗GPT", ego_images.chatgpt)):
            if not left:
                break
            print(f"  {name}에서 {len(left)}장 만드는 중… (에고라이트에서 {name}에 로그인돼 있어야 합니다)")
            res = fn([d for _, d in left], [os.path.join(photos, f"{n:02d}.jpg") for n, _ in left])
            for (n, _), ok in zip(left, res):
                if ok:
                    print(f"  사진{n}: {name} ✅")
            left = [x for x, ok in zip(left, res) if not ok]
    for n, d in left:
        print(f"  사진{n}: 못 만들었습니다 → 글에 빨간 [사진{n}] 자리로 남깁니다({d})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
