// 임시저장 글의 사진 내려받기 (에고라이트 · 맥)
//   폰 블로그 앱으로 «사진만» 올려 임시저장한 글을 글쓰기 화면에서 불러와,
//   사진을 순서대로 내 컴퓨터에 받는다. 글은 건드리지 않는다(저장 버튼을 누르지 않는다).
// 입력: PAYLOAD_PATH 의 JSON — {blogId, keyword, outDir, spaceName}
//   keyword 가 비면 임시저장 목록 «맨 위»(방금 저장한 글)를 연다.
const fs = await import("node:fs/promises");
const path = await import("node:path");
const P = JSON.parse(await fs.readFile(PAYLOAD_PATH, "utf-8"));
const log = (...a) => console.log("[ego]", ...a);
const WRITE_URL = `https://blog.naver.com/${P.blogId}?Redirect=Write&`;

const task = await taskSpace(P.spaceName || "체험단 자동");
const page = task.page("p1");
let _closed = false;
async function done(obj, code = 0) {
  console.log(JSON.stringify(obj));
  if (!_closed) { _closed = true; try { await task.finish({ keep: [] }); } catch {} }
  if (code) process.exit(code);
}
process.on("unhandledRejection", async (e) => { await done({ ok: false, why: `드라이버 예외: ${String(e).slice(0, 160)}` }, 5); });

// 프레임 안 문서에서 실행하는 도우미(에디터는 #mainFrame 안에 있다)
const inFrame = (fn, arg) => page.evaluate(`(() => {
  const f = document.querySelector("#mainFrame");
  const d = (f && f.contentDocument) ? f.contentDocument : document;
  return (${fn.toString()})(d, ${JSON.stringify(arg ?? null)});
})()`);

try { await page.goto(WRITE_URL); }
catch (e) { try { await page.acceptDialog(); } catch {} await page.waitForTimeout(800); await page.goto(WRITE_URL); }
try { await page.dismissDialog(); } catch {}
await page.waitForTimeout(3000);

if ((await page.url()).includes("nidlogin")) {
  await done({ ok: false, why: "네이버 로그인이 안 돼 있습니다 — 에고라이트를 열고 직접 로그인해 주세요(로그인 상태 유지 켜기)." }, 2);
}
// 화면 크기 0 대응(창이 최대화된 채 0×0으로 잡히는 경우)
try {
  const sz = await page.evaluate(() => [innerWidth, innerHeight]);
  if (!sz[0] || !sz[1]) {
    const w = await task.cdp("Browser.getWindowForTarget", { targetId: page.targetId });
    await task.cdp("Browser.setWindowBounds", { windowId: w.windowId, bounds: { windowState: "normal" } });
    await task.cdp("Browser.setWindowBounds", { windowId: w.windowId, bounds: { left: 100, top: 60, width: 1280, height: 900 } });
    await page.waitForTimeout(1500);
  }
} catch {}

// «작성 중인 글이 있습니다» → 취소(이어쓰기 안 함)
for (let i = 0; i < 3; i++) {
  try {
    const s = await page.snapshot();
    if (s.includes("작성 중인 글이 있습니다")) { await page.click('text="취소"', { label: "skip resume" }); await page.waitForTimeout(1000); }
    else break;
  } catch { break; }
}
try {
  await page.waitForSelector("css=.se-section-documentTitle", { state: "visible", timeout: 25000 });
} catch {
  await done({ ok: false, why: "글쓰기 화면이 안 열립니다 — 에고라이트 창을 앞으로 꺼내 두고 다시 해 주세요." }, 4);
}
const url = await page.url();
if (!url.includes(P.blogId)) await done({ ok: false, why: `다른 블로그 계정으로 로그인돼 있습니다(${url.slice(0, 80)}) — 내정보.txt 의 블로그ID와 같은 계정으로 로그인해 주세요.` }, 2);

// 도움말·팝업 닫기
await inFrame((d) => {
  const vis = (e) => e && (e.offsetParent || e.getClientRects().length);
  d.querySelectorAll("button.se-popup-button-cancel, button.se-help-panel-close-button").forEach((b) => { if (vis(b)) b.click(); });
});
await page.waitForTimeout(600);

// 임시저장 목록 열기 — 「저장」 옆 숫자 버튼
const opened = await inFrame((d) => {
  const vis = (e) => e && (e.offsetParent || e.getClientRects().length);
  const b = [...d.querySelectorAll("button")].filter(vis).find((x) => /^\d+$/.test((x.innerText || "").trim()));
  if (b) { b.click(); return (b.innerText || "").trim(); }
  return "";
});
if (!opened || opened === "0") await done({ ok: false, why: "임시저장 글이 없습니다 — 폰 블로그 앱에서 사진을 올리고 «임시저장»을 눌렀는지 확인해 주세요." }, 3);
await page.waitForTimeout(1500);

// 목록에서 고르기 — 키워드가 있으면 그 글, 없으면 맨 위(최신)
const picked = await inFrame((d, kw) => {
  const vis = (e) => e && (e.offsetParent || e.getClientRects().length);
  const lists = [...d.querySelectorAll('[class*="temp"] li, [class*="list"] li, li[class*="item"]')].filter(vis)
    .filter((el) => (el.innerText || "").trim().length > 2)
    .filter((el) => !/추가$/.test((el.innerText || "").trim()));
  if (!lists.length) return null;
  let t = kw ? lists.find((el) => (el.innerText || "").includes(kw)) : null;
  if (!t) t = lists[0];
  const label = (t.innerText || "").trim().replace(/\s+/g, " ").slice(0, 60);
  (t.querySelector("a, button, [class*=title]") || t).click();
  return { label, all: lists.slice(0, 8).map((el) => (el.innerText || "").trim().replace(/\s+/g, " ").slice(0, 40)) };
}, P.keyword || "");
if (!picked) await done({ ok: false, why: "임시저장 목록을 읽지 못했습니다." }, 3);
log("임시저장 목록:", JSON.stringify(picked.all));
log("고른 글:", picked.label);
await page.waitForTimeout(1000);
// «불러오시겠습니까» 확인
await inFrame((d) => {
  const vis = (e) => e && (e.offsetParent || e.getClientRects().length);
  d.querySelectorAll("button.se-popup-button-confirm").forEach((b) => { if (vis(b)) b.click(); });
});
await page.waitForTimeout(3500);

// 사진은 화면에 보여야 진짜 주소가 붙는다(그 전엔 회색 자리표시) → 아직 안 뜬 사진만 골라 천천히 다시 비춘다.
//   ★빨리 지나가면 건너뛴다(실측 10/19: 120ms 간격 → 7장 중 2장). 한 장에 0.6초씩, 최대 5바퀴.
try { await page.cdp("Page.bringToFront"); } catch {}
for (let round = 0; round < 5; round++) {
  const pending = await inFrame((d) => [...d.querySelectorAll(".se-component.se-image")]
    .map((c, i) => [i, (c.querySelector("img")?.getAttribute("src") || "")])
    .filter(([, s]) => !s || s.startsWith("data:")).map(([i]) => i));
  if (!pending.length) break;
  log(`아직 안 뜬 사진 ${pending.length}장 — 화면에 비추는 중(${round + 1}바퀴)`);
  for (const i of pending) {
    await inFrame((d, idx) => { const c = d.querySelectorAll(".se-component.se-image")[idx]; if (c) c.scrollIntoView({ block: "center" }); }, i);
    await page.waitForTimeout(600);
  }
}
await page.waitForTimeout(1200);
const info = await inFrame((d) => {
  const canvas = d.querySelector(".se-canvas") || d.querySelector(".se-content") || d;
  const comps = [...canvas.querySelectorAll(".se-component")].filter((c) => !c.parentElement.closest(".se-component"));
  const title = (d.querySelector(".se-section-documentTitle")?.innerText || "").trim();
  const imgs = []; let videos = 0; let texts = 0;
  for (const c of comps) {
    if (/se-image|se-imageStrip|se-imageGroup/.test(c.className)) {
      c.querySelectorAll("img").forEach((im) => { if (im.src && !im.src.startsWith("data:")) imgs.push(im.src); });
    } else if (/se-video/.test(c.className)) videos++;
    else if (/se-text/.test(c.className) && (c.innerText || "").trim()) texts++;
  }
  return { title, imgs: [...new Set(imgs)], videos, texts };
});
log("불러온 글 제목:", info.title || "(제목 없음)", "· 사진", info.imgs.length, "· 동영상", info.videos);
if (!info.imgs.length) await done({ ok: false, why: "불러온 임시저장 글에 사진이 없습니다.", picked: picked.label }, 3);

await fs.mkdir(P.outDir, { recursive: true });
const files = []; const fails = [];
for (let i = 0; i < info.imgs.length; i++) {
  const src = info.imgs[i];
  const fn = path.join(P.outDir, `${String(i + 1).padStart(2, "0")}.jpg`);
  let ok = false;
  // ①그대로 받기(주소에 토큰이 붙어 있다 — 주소를 바꾸면 404) ②안 되면 페이지 안에서 받기
  try {
    const r = await fetch(src, { headers: { Referer: "https://blog.naver.com/" } });
    if (r.ok) { await fs.writeFile(fn, Buffer.from(await r.arrayBuffer())); ok = true; }
  } catch {}
  if (!ok) {
    try { await page.fetch(src, { saveAs: fn, credentials: "include" }); ok = true; } catch {}
  }
  if (ok) files.push(fn); else fails.push(i + 1);
}
await done({ ok: true, title: info.title, picked: picked.label, count: files.length, fails, videos: info.videos,
             texts: info.texts, outDir: P.outDir });
// 글은 저장하지 않고 닫는다 — 원본 임시저장은 그대로 남는다.
