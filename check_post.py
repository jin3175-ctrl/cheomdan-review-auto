"""② 원고 점검 — 임시저장 전에 꼭 돌린다.

    python3 check_post.py 가게이름

광고 표시(협찬이면 제목·첫 부분) · 필수키워드 횟수 · 글자 수 · 사진 번호 · 사진 사이 글 길이를 본다.
"""
from __future__ import annotations

import os
import sys

import common
import post


def paths(shop: str) -> tuple:
    d = os.path.join(common.HERE, "글", common.safe_name(shop))
    return os.path.join(d, "원고.txt"), os.path.join(d, "사진")


def run(shop: str) -> bool:
    src, photos = paths(shop)
    if not os.path.exists(src):
        print(f"[!] 원고가 없습니다: {src}")
        return False
    doc = post.read(src)
    err, warn = post.check(doc, photos)
    print(f"원고: {src}")
    print(f"제목: {doc['meta'].get('제목', '')}  ·  종류: {doc['meta'].get('종류', '')}")
    if err:
        print("\n🔴 고칠 것 (이게 있으면 임시저장하지 않습니다)")
        for e in err:
            print("  -", e)
    if warn:
        print("\n🟡 살펴볼 것")
        for w in warn:
            print("  -", w)
    if not err and not warn:
        print("\n✅ 점검 통과")
    elif not err:
        print("\n✅ 고칠 것은 없습니다(살펴볼 것만 확인)")
    return not err


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용: python3 check_post.py 가게이름")
        sys.exit(1)
    sys.exit(0 if run(sys.argv[1]) else 1)
