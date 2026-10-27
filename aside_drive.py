"""윈도우 서이추 — 어사이드(Aside) CLI로 어사이드 창을 직접 움직인다 (2026-10-25 · 체험단 2기 2회차).

왜 이렇게 하나: 윈도우에서 어사이드 자체 AI(Ask 칸)에 프롬프트를 붙여넣는 방식은 「안 된다」고 막혔다(2·3기).
→ 어사이드 CLI(`aside`)를 깔면 **프로그램이 어사이드 창을 직접** 연다. 어사이드 AI에게 부탁하지 않는다.

뼈대는 홈판 3기 3주차 이웃관리/browser_drive.py(2026-10-24 에디 맥 실측)에서 가져왔다:
  · `aside repl "코드"` 한 번짜리로 연 탭은 명령이 끝나면 닫힌다 → `aside repl` 을 **하나 띄워 두고** 줄마다 명령을 보낸다.
  · 한 줄이 명령 하나다. 페이지에 넣는 함수는 JSON 문자열로 보내 new Function 으로 되살린다.
  · `window.open`·`page.context()`는 막혀 있다. 명령 하나는 120초 제한.
서이추 순서는 맥(ego/buddy.mjs = 에디님 블로그 neighbor.mjs)과 같다.
🔴«서로이웃 신청 진행중입니다. 취소하시겠습니까?» 에서 [확인]을 누르면 신청이 **취소**된다(10/14 실측).
  → 대화상자는 전부 «닫기(dismiss)»로 처리한다. 확인을 누르지 않는다.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time

BLOCK_SIGNS = ["제한되었습니다", "제한됩니다", "이용이 제한", "스팸", "과도한", "보안문자",
               "자동입력 방지", "자동입력방지", "잠시 후 다시", "일시적으로", "비정상적인"]


def block_of(s: str) -> str:
    return next((w for w in BLOCK_SIGNS if w in (s or "")), "")


def aside_bin() -> str:
    cands = [shutil.which("aside"), os.path.expanduser("~/.local/bin/aside")]
    la = os.environ.get("LOCALAPPDATA")
    if la:   # 윈도우 설치 위치(설치 스크립트 기본값 %LOCALAPPDATA%\Aside\CLI) — 🔴윈도우 실기 미확인
        for name in ("aside.exe", "aside.cmd", "aside"):
            cands += [os.path.join(la, "Aside", "CLI", name), os.path.join(la, "Aside", "CLI", "bin", name)]
    for c in cands:
        if c and os.path.exists(c):
            return c
    return ""


def _one_line(js: str) -> str:
    return " ".join(s.strip() for s in js.strip().splitlines() if s.strip())


class AsidePage:
    """`aside repl` 하나를 띄워 두고 줄 단위로 명령을 보낸다. 탭은 어사이드 창에 그대로 보인다."""

    def __init__(self):
        b = aside_bin()
        if not b:
            raise RuntimeError(
                "어사이드 CLI(aside)가 없습니다 — 어사이드 앱 → 왼쪽 아래 프로필 → Settings → Developers → "
                "「Aside CLI」 Install(안 되면 Copy command를 클로드 코드에 붙여넣기). "
                "설치 뒤에는 클로드 코드 창을 닫았다가 다시 여세요.")
        self._n = 0
        self._closed = False
        self._q: queue.Queue = queue.Queue()
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = 0x08000000   # CREATE_NO_WINDOW
        self._proc = subprocess.Popen([b, "repl"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                      errors="replace", bufsize=1, **kw)
        threading.Thread(target=self._pump, daemon=True).start()
        self._opened = False

    def _pump(self):
        for line in self._proc.stdout:
            self._q.put(line)
        self._q.put(None)

    def send(self, js: str, timeout=110):
        """명령 한 줄을 보내고 `@@R{...}` 한 줄을 받는다. 실패하면 RuntimeError."""
        self._n += 1
        tag = f"@@R{self._n}@@"
        line = (f"try {{ const __v{self._n} = await (async () => {{ {_one_line(js)} }})(); "
                f"console.log({json.dumps(tag)} + JSON.stringify({{ok: true, v: __v{self._n} ?? null}})); }} "
                f"catch (e) {{ console.log({json.dumps(tag)} + JSON.stringify({{ok: false, e: String(e).slice(0, 300)}})); }}")
        try:
            self._proc.stdin.write(line + "\n")
            self._proc.stdin.flush()
        except (OSError, ValueError):
            self._closed = True
            raise RuntimeError("어사이드 REPL이 끝났습니다")
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                out = self._q.get(timeout=max(0.1, deadline - time.time()))
            except queue.Empty:
                break
            if out is None:
                self._closed = True
                raise RuntimeError("어사이드 REPL이 끝났습니다 — 어사이드 앱이 켜져 있는지 보세요")
            i = out.find(tag)
            if i >= 0:
                r = json.loads(out[i + len(tag):].strip())
                if not r.get("ok"):
                    raise RuntimeError(r.get("e") or "어사이드 명령 실패")
                return r.get("v")
        raise RuntimeError("어사이드가 응답하지 않습니다(시간 초과)")

    def goto(self, url):
        if not self._opened:
            # 대화상자는 전부 닫기(dismiss)로 받고 문구만 모아 둔다 — 확인을 누르면 서이추가 취소될 수 있다
            self.send(f"globalThis.__edi = await openTab({json.dumps(url)}); globalThis.__ediDlg = []; "
                      "try { __edi.on('dialog', async (d) => { __ediDlg.push(String(d.message())); "
                      "try { await d.dismiss(); } catch (e) {} }); } catch (e) {} return __edi.url();")
            self._opened = True
        else:
            self.send(f"await __edi.goto({json.dumps(url)}); return __edi.url();")

    def url(self) -> str:
        try:
            return self.send("return __edi.url();", timeout=20) or ""
        except RuntimeError:
            return ""

    def evaluate(self, fn: str, arg=None):
        a = "" if arg is None else ", " + json.dumps(arg, ensure_ascii=False)
        return self.send(f"return await __edi.evaluate(new Function('return ' + {json.dumps(fn, ensure_ascii=False)})(){a});")

    def dialogs(self) -> str:
        """그동안 뜬 대화상자 문구(모아 둔 것)를 꺼내고 비운다."""
        try:
            return self.send("const __d = (globalThis.__ediDlg || []).join(' | '); globalThis.__ediDlg = []; return __d;",
                             timeout=20) or ""
        except RuntimeError:
            return ""

    def click_tagged(self) -> bool:
        """data-edi-t=x1 을 단 요소를 **진짜 마우스**로 누른다(mouse.click — isTrusted=true).
        🔴어사이드의 locator().click()은 네이버 화면에서 못 믿는다(홈판 3기 10/25 실측: 눌러도 초점이 안 갔다).
        좌표를 못 구하면 DOM click 으로 대신한다."""
        pt = self.evaluate("() => { const e = document.querySelector('[data-edi-t=x1]'); if (!e) return null; "
                           "e.scrollIntoView({block: 'center'}); const r = e.getBoundingClientRect(); "
                           "if (!r.width || !r.height) return null; "
                           "return {x: r.left + Math.min(r.width / 2, 40), y: r.top + r.height / 2}; }")
        ok = False
        if pt:
            try:
                self.send(f"await __edi.mouse.click({float(pt['x'])}, {float(pt['y'])}); return 1;", timeout=30)
                ok = True
            except RuntimeError:
                ok = False
        if not ok:
            ok = bool(self.evaluate("() => { const e = document.querySelector('[data-edi-t=x1]'); "
                                    "if (!e) return false; e.click(); return true; }"))
        self.evaluate("() => document.querySelectorAll('[data-edi-t]').forEach((e) => e.removeAttribute('data-edi-t'))")
        return ok

    def type_human(self, text: str):
        self.send(f"await __edi.keyboard.type({json.dumps(text, ensure_ascii=False)}, {{delay: 90}}); return 1;",
                  timeout=110)

    def close(self):
        """우리가 연 탭만 닫고 REPL을 끝낸다. 사람이 쓰던 다른 탭은 건드리지 않는다."""
        try:
            if self._opened and not self._closed:
                self.send("await closeTab(__edi); return 1;", timeout=20)
        except RuntimeError:
            pass
        try:
            self._proc.stdin.write("exit\n")
            self._proc.stdin.flush()
            self._proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            self._proc.kill()


LAYER_JS = """() => [...document.querySelectorAll('.u_cbox_layer_wrap, .u_cbox_alert, [class*="u_cbox_layer"], [role="alertdialog"], [id^="_alertLayer"], [class*="alert"]')]
  .filter((e) => e.offsetParent !== null).map((e) => (e.innerText || '').trim()).filter(Boolean).join(' | ').slice(0, 400)"""


def op_session(pg: AsidePage) -> dict:
    pg.goto("https://blog.naver.com/GoBlogWrite.naver")
    time.sleep(3.5)
    u = pg.url()
    try:
        pg.goto("about:blank")
    except RuntimeError:
        pass
    return {"ok": True, "url": u}


def op_buddy(pg: AsidePage, target: str, message: str, dry: bool = False) -> dict:
    """에고 buddy.mjs 의 opBuddy 와 같은 판단 순서."""
    import re
    form = f"https://m.blog.naver.com/BuddyAddForm.naver?blogId={target}"
    pg.goto(form)
    time.sleep(2.2)
    if "nidlogin" in pg.url():
        return {"ok": False, "why": "세션만료"}
    s0 = pg.evaluate("() => { const b = document.querySelector('#bothBuddyRadio'); "
                     "return { has: !!b, disabled: b ? b.disabled : null, body: (document.body.innerText || '').slice(0, 600) }; }")
    pre = f"{pg.evaluate(LAYER_JS) or ''} {pg.dialogs()}"
    if re.search(r"이미 (추가한 )?이웃|신청 (진행 ?)?중|진행중|신청하신 상태|이미 신청|취소하시겠습니까", pre + s0["body"][:160]):
        return {"ok": False, "skip": True, "already": True, "why": (pre.strip() or s0["body"][:80])}
    if re.search(r"하루|초과|더 이상|한도|제한", pre):
        return {"ok": False, "limit": True, "blocked": block_of(pre), "why": pre[:160]}
    if not s0["has"] or s0["disabled"]:
        return {"ok": False, "skip": True, "noBuddy": True, "why": "서로이웃을 받지 않는 블로그"}
    pg.evaluate("() => { const b = document.querySelector('#bothBuddyRadio'); "
                "const l = b.closest('label') || document.querySelector('label[for=bothBuddyRadio]') || b; "
                "l.setAttribute('data-edi-t', 'x1'); return true; }")
    pg.click_tagged()
    time.sleep(0.5)
    if not pg.evaluate("() => !!(document.querySelector('#bothBuddyRadio') || {}).checked"):
        return {"ok": False, "why": "서로이웃 선택 실패"}
    # 메시지 칸: 예전 #inviteMessage → 지금은 이름 없는 textarea.textarea_t1(10/27 실측). 기본 글(예: «ㅇㅇ»)을 비운다
    has_ta = pg.evaluate("() => { const t = [...document.querySelectorAll('#inviteMessage, textarea')]"
                         ".find((e) => e.offsetParent !== null); if (!t) return false; t.focus(); t.select(); t.value = ''; "
                         "t.dispatchEvent(new Event('input', {bubbles: true})); return true; }")
    if has_ta and message:
        pg.type_human(message)
        time.sleep(0.4)
    if dry:   # 미리보기: 선택·메시지까지 채우고 [확인]은 누르지 않는다(탭을 닫으면 사라진다)
        typed = pg.evaluate("() => { const t = [...document.querySelectorAll('#inviteMessage, textarea')]"
                            ".find((e) => e.offsetParent !== null); return t ? t.value : ''; }") or ""
        return {"ok": True, "dry": True, "why": f"서로이웃 선택·메시지 칸 채움(신청 안 함) · 칸: «{typed}»"}
    base = pg.evaluate(LAYER_JS) or ""
    one = pg.evaluate("() => { const bs = [...document.querySelectorAll('a.btn_ok, button.btn_ok')]"
                      ".filter((b) => b.offsetParent !== null && /확인/.test(b.innerText || '')); "
                      "if (bs.length !== 1) return false; bs[0].setAttribute('data-edi-t', 'x1'); return true; }")
    if not one:
        return {"ok": False, "why": "확인 버튼이 애매해서 누르지 않음"}
    pg.click_tagged()
    after, dm = "", ""
    for _ in range(16):
        time.sleep(0.5)
        dm = dm or pg.dialogs()
        lt = pg.evaluate(LAYER_JS) or ""
        after = lt if lt and lt != base else ""
        if dm or after or "BuddyAddForm" not in pg.url():
            break
    txt = f"{dm} {after}".strip()
    if re.search(r"하루|초과|더 이상|한도", txt):
        return {"ok": False, "limit": True, "blocked": block_of(txt), "why": txt[:160]}
    b = block_of(txt)
    if b:
        return {"ok": False, "blocked": b, "why": txt[:160]}
    gone = pg.evaluate("() => !document.querySelector('#bothBuddyRadio') || !(document.querySelector('#bothBuddyRadio').offsetParent)")
    if re.search(r"신청|보냈|완료", txt) or gone or "BuddyAddForm" not in pg.url():
        # 확인: 신청 화면을 다시 열면 «서로이웃 신청 진행중»이 떠야 한다. 아무것도 누르지 않는다(확인 = 신청 취소).
        time.sleep(1.5)
        pg.goto(form)
        time.sleep(2.2)
        chk = (pg.evaluate("() => (document.body.innerText || '').slice(0, 300)") or "") + " " + pg.dialogs()
        if re.search(r"진행중|진행 중|이미 (추가한 )?이웃", chk):
            return {"ok": True, "why": "확인됨: " + re.sub(r"\s+", " ", chk)[:60]}
        return {"ok": False, "why": "신청 뒤 확인 안 됨: " + re.sub(r"\s+", " ", txt or chk)[:100]}
    return {"ok": False, "why": f"결과 확인 안 됨: {txt[:100]}"}
