// 체험단 서이추 — 에고라이트 드라이버 (2026-10-25 · 체험단 2기 2회차)
//   원본: 에디님 블로그 이웃관리 ego/neighbor.mjs(2026-10-14 실측) 에서 «계정 확인 · 서이추»만 떼어 왔다.
//   호출측(buddy_auto.py)이 맨 앞에 `const PAYLOAD_PATH = "...";` 한 줄을 붙여 stdin으로 넘긴다.
//   결과는 마지막에 `@@RESULT {json}` 한 줄로 낸다.
//
// op:
//   session — GoBlogWrite.naver 로 가서 리다이렉트 주소를 돌려준다(어느 계정인지 확인)
//   buddy   — 서로이웃 신청(모바일 BuddyAddForm)
//
// 🔴안전: 버튼이 애매하면 누르지 않는다 · 삭제/차단 버튼은 절대 건드리지 않는다 ·
//   대화상자/자동입력방지/제한 문구가 보이면 그 문구를 그대로 돌려주고 멈춘다(호출측이 그날 멈춘다).
const fs = await import("node:fs/promises");
const payloadPath = (typeof PAYLOAD_PATH !== "undefined") ? PAYLOAD_PATH : "/tmp/ego_neighbor.json";
const P = JSON.parse(await fs.readFile(payloadPath, "utf-8"));
const log = (...a) => console.log("[ego]", ...a);
const done = (o) => console.log(JSON.stringify(o));   // common.run_ego 가 «{ … "ok" … }» 줄을 읽는다

const BLOCK_SIGNS = ["제한되었습니다", "제한됩니다", "이용이 제한", "스팸", "과도한", "보안문자",
  "자동입력 방지", "자동입력방지", "잠시 후 다시", "일시적으로", "비정상적인"];
const blockOf = (s) => BLOCK_SIGNS.find((w) => (s || "").includes(w)) || "";

// ── 공간: 수강생 컴퓨터는 에고라이트 기본 프로필 하나다. 주인 손에 있는 공간이면 « 2»로 ──
const BASE = "체험단 서이추";
let spaceName = BASE;
try {
  const ss = await listTaskSpaces();
  if (ss.some((s) => s.name === BASE && s.ownership !== "agent")) spaceName = BASE + " 2";
} catch (e) { /* 목록 실패는 무시 */ }
let task;
try { task = await taskSpace(spaceName); }
catch (e) {
  const m = String(e);
  done({ ok: false, why: /control|user/i.test(m) ? "user_control" : `공간 열기 실패: ${m.slice(0, 140)}` });
  process.exit(0);
}
const page = task.page("p1");
let _closed = false;
async function closeSpace() {
  if (_closed) return; _closed = true;
  try { await task.finish({ keep: [] }); } catch (e) { log("공간 닫기 실패(무시):", String(e).slice(0, 80)); }
}
process.on("unhandledRejection", async (e) => {
  const m = String(e);
  done({ ok: false, why: /taken control|user control/i.test(m) ? "user_control" : `드라이버 예외: ${m.slice(0, 160)}` });
  await closeSpace(); process.exit(0);
});

// 🔴화면 0×0(잠긴 화면) 가드 — publish.mjs 2026-10-14와 같은 처방
async function guardSize() {
  try {
    const sz = await page.evaluate(() => [innerWidth, innerHeight]);
    if (!sz[0] || !sz[1]) {
      const w = await task.cdp("Browser.getWindowForTarget", { targetId: page.targetId });
      await task.cdp("Browser.setWindowBounds", { windowId: w.windowId, bounds: { windowState: "normal" } });
      await task.cdp("Browser.setWindowBounds", { windowId: w.windowId, bounds: { left: 100, top: 60, width: 1280, height: 900 } });
      await page.waitForTimeout(1200);
      log("화면 크기 0 → 창 다시 펼침");
    }
  } catch (e) { log("화면 크기 확인 실패(진행):", String(e).slice(0, 60)); }
}

async function dialogMsg() {
  try {
    const inf = await page.info();
    const d = inf && inf.dialog;
    if (d) {
      const msg = d.message || d.text || JSON.stringify(d);
      try { await page.acceptDialog(); } catch (e) {}
      return String(msg);
    }
  } catch (e) {}
  return "";
}

async function sleep(ms) { await page.waitForTimeout(ms); }
// 안내 레이어(경고·제한·완료 문구) — 누르기 전 값을 기준으로 «새로 뜬 것»만 본다
const LAYER_SEL = '.u_cbox_layer_wrap, .u_cbox_alert, [class*="u_cbox_layer"], [role="alertdialog"], [id^="_alertLayer"], [class*="alert"]';
async function layerText() {
  return page.evaluate((sel) => [...document.querySelectorAll(sel)].filter((e) => e.offsetParent !== null)
    .map((e) => (e.innerText || '').trim()).filter(Boolean).join(' | ').slice(0, 400), LAYER_SEL);
}
const rnd = (a, b) => a + Math.floor(Math.random() * (b - a + 1));

// 사람처럼 — 몇 글자씩 끊어서 넣는다(한글은 키 입력보다 insertText가 안전)
async function typeHuman(text) {
  let i = 0;
  while (i < text.length) {
    const n = rnd(2, 6);
    await page.keyboard.insertText(text.slice(i, i + n));
    i += n;
    await sleep(rnd(60, 220));
  }
}

// 댓글 입력칸에 커서 넣기 — 칸 위에 안내 문구 div(«댓글을 입력해주세요»)가 덮여 있어 칸을 바로 못 누른다(2026-10-14 실측).
//   ①칸을 누르고 ②막히면 덮은 안내 div를 누르고 ③그래도 아니면 focus. 마지막에 «정말 그 칸에 커서가 있나»를 본다.
async function tagAndClick(fn, arg, label) {
  const ok = await page.evaluate(fn, arg);
  if (!ok) return { ok: false };
  const r = await page.click('css=[data-edi-t="1"]', { label });
  await page.evaluate(() => document.querySelectorAll('[data-edi-t]').forEach((e) => e.removeAttribute('data-edi-t')));
  return { ok: true, receipt: r };
}

// ── op들 ──────────────────────────────────────────────────────────────
async function opSession() {
  await page.goto("https://blog.naver.com/GoBlogWrite.naver");
  await sleep(3500);
  await guardSize();
  const url = await page.url();
  // 글쓰기 화면을 오래 열어 두지 않는다 — 바로 빈 페이지로
  try { await page.goto("about:blank"); } catch (e) {}
  return { ok: true, url };
}

async function opBuddy() {
  await page.goto(`https://m.blog.naver.com/BuddyAddForm.naver?blogId=${P.target}`);
  await sleep(2200);
  await guardSize();
  if ((await page.url()).includes("nidlogin")) return { ok: false, why: "세션만료" };
  const s0 = await page.evaluate(() => {
    const vis = (el) => el && el.offsetParent !== null;
    const b = document.querySelector('#bothBuddyRadio');
    return { has: !!b, disabled: b ? b.disabled : null, body: (document.body.innerText || '').slice(0, 600) };
  });
  const dm0 = await dialogMsg();
  const lay0 = await layerText();
  const pre = `${lay0} ${dm0}`;
  // 🔴«서로이웃 신청 진행중입니다. 취소하시겠습니까? [취소][확인]» — 여기서 확인을 누르면 신청이 **취소**된다(2026-10-14 실측). 절대 누르지 않고 빠진다.
  if (/이미 (추가한 )?이웃|신청 (진행 ?)?중|진행중|신청하신 상태|이미 신청|취소하시겠습니까/.test(pre + s0.body.slice(0, 160))) return { ok: false, skip: true, already: true, why: (pre.trim() || s0.body.slice(0, 80)) };
  if (/하루|초과|더 이상|한도|제한/.test(pre)) return { ok: false, limit: true, blocked: blockOf(pre), why: pre.slice(0, 160) };
  if (!s0.has || s0.disabled) return { ok: false, skip: true, noBuddy: true, why: "서로이웃을 받지 않는 블로그" };
  if (P.dry) return { ok: true, dry: true, why: "서로이웃 선택 가능(신청 안 함)" };
  const r1 = await tagAndClick(() => {
    const b = document.querySelector('#bothBuddyRadio');
    const l = b.closest('label') || document.querySelector('label[for=bothBuddyRadio]') || b.parentElement.querySelector('label');
    (l || b).setAttribute('data-edi-t', '1'); return true;
  }, null, "choose mutual neighbor");
  await sleep(500);
  const chk = await page.evaluate(() => !!(document.querySelector('#bothBuddyRadio') || {}).checked);
  if (!chk) return { ok: false, why: `서로이웃 선택 실패(${r1.ok})` };
  const ta = await page.evaluate(() => { const t = document.querySelector('#inviteMessage'); return !!(t && t.offsetParent !== null); });
  if (ta && P.message) {
    await page.click('css=#inviteMessage', { label: "focus invite message" });
    await sleep(200);
    await page.keyboard.press("ControlOrMeta+a");
    await page.keyboard.press("Backspace");
    await typeHuman(P.message);
    await sleep(400);
  }
  const base = await layerText();
  const r2 = await tagAndClick(() => {
    const bs = [...document.querySelectorAll('a.btn_ok, button.btn_ok')].filter((b) => b.offsetParent !== null && /확인/.test(b.innerText || ''));
    if (bs.length !== 1) return false;
    bs[0].setAttribute('data-edi-t', '1'); return true;
  }, null, "send neighbor request");
  if (!r2.ok) return { ok: false, why: "확인 버튼이 애매해서 누르지 않음" };
  let after = "", dm = "";
  for (let i = 0; i < 16; i++) {
    await sleep(500);
    dm = dm || await dialogMsg();
    const lt = await layerText();
    after = lt && lt !== base ? lt : "";
    if (dm || after || !(await page.url()).includes("BuddyAddForm")) break;
  }
  const url = await page.url();
  const txt = `${dm} ${after}`.trim();
  if (/하루|초과|더 이상|한도/.test(txt)) return { ok: false, limit: true, blocked: blockOf(txt), why: txt.slice(0, 160) };
  const b = blockOf(txt);
  if (b) return { ok: false, blocked: b, why: txt.slice(0, 160) };
  const formGone = await page.evaluate(() => !document.querySelector('#bothBuddyRadio') || !(document.querySelector('#bothBuddyRadio').offsetParent));
  if (/신청|보냈|완료/.test(txt) || formGone || !url.includes("BuddyAddForm")) {
    // 확인: 신청 화면을 다시 열면 «서로이웃 신청 진행중입니다»가 떠야 한다. **아무것도 누르지 않는다**(확인 = 신청 취소).
    await sleep(1500);
    await page.goto(`https://m.blog.naver.com/BuddyAddForm.naver?blogId=${P.target}`);
    await sleep(2200);
    const chk = await page.evaluate(() => (document.body.innerText || '').slice(0, 300));
    if (/진행중|진행 중|이미 (추가한 )?이웃/.test(chk)) return { ok: true, why: `확인됨: ${chk.replace(/\s+/g, ' ').slice(0, 60)}` };
    return { ok: false, why: `신청 뒤 확인 안 됨: ${(txt || chk).replace(/\s+/g, ' ').slice(0, 100)}` };
  }
  return { ok: false, why: `결과 확인 안 됨: ${txt.slice(0, 100)}` };
}

let res;
try {
  if (P.op === "session") res = await opSession();
  else if (P.op === "buddy") res = await opBuddy();
  else res = { ok: false, why: `모르는 op: ${P.op}` };
} catch (e) {
  const m = String(e);
  res = { ok: false, why: /taken control|user control/i.test(m) ? "user_control" : `예외: ${m.slice(0, 200)}` };
}
await closeSpace();
done(res);
