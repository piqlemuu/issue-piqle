"""이슈피클 검색 노출용 페이지 만들기

- explain.md 에 직접 쓴 '이슈 해설'을 site/i/*.html 정적 페이지로 만들어요.
  (글자가 HTML 안에 처음부터 들어 있어서 구글·네이버가 바로 읽을 수 있어요)
- 검색에 내보낼 페이지만 담은 sitemap.xml, 이슈피클 rss.xml 을 만들어요.
- 자동으로 만들어지는 화면(이슈 상세 issue.html)은 검색 제외(noindex)로 두고,
  사람이 쓴 글이 있는 페이지만 검색에 내보내요.
"""
import html
import json
import re
import urllib.parse
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path

import os
# 사이트 주소: GitHub Actions에서는 저장소 이름으로 자동으로 맞춰요 (저장소 이름을 바꿔도 따로 고칠 필요 없음)
_repo = os.environ.get("GITHUB_REPOSITORY", "piqlemuu/issue-piqle")
SITE_URL = f"https://{_repo.split('/')[0].lower()}.github.io/{_repo.split('/')[1]}/"
SITE_NAME = "이슈피클"
OG_IMG = SITE_URL + "og.jpg"   # 카톡·SNS 공유 미리보기 그림 (site/og.jpg)
ROOT = Path(__file__).resolve().parent
EXPLAIN_FILE = ROOT / "explain.md"
SITE = ROOT / "site"
OUT_DIR = SITE / "i"

FIELDS = {"키워드": "keyword", "날짜": "date", "수정": "updated", "요약": "summary",
          "무슨 일": "what", "왜 화제": "why", "앞으로": "next", "출처": "source"}

STATIC_PAGES = [  # (주소, 바뀌는 주기, 중요도)
    ("", "hourly", "1.0"), ("memes.html", "daily", "0.8"), ("content.html", "daily", "0.7"),
    ("about.html", "monthly", "0.4"), ("copyright.html", "yearly", "0.2"),
    ("privacy.html", "yearly", "0.2"), ("terms.html", "yearly", "0.2"),
]

e = lambda s: html.escape(str(s or ""), quote=True)


def slug(title):
    return re.sub(r"[^0-9A-Za-z가-힣]+", "-", title).strip("-")[:60] or "issue"


def page_path(title):
    return "i/" + slug(title) + ".html"


def page_url(title):
    return SITE_URL + "i/" + urllib.parse.quote(slug(title)) + ".html"


def read_explains():
    """explain.md 를 읽어요. '## 제목' 아래에 '항목: 내용' 형식."""
    if not EXPLAIN_FILE.exists():
        return []
    out = []
    for block in re.split(r"^##\s+", EXPLAIN_FILE.read_text(encoding="utf-8"), flags=re.M)[1:]:
        lines = block.splitlines()
        it = {"title": lines[0].strip(), "keyword": "", "date": "", "updated": "", "summary": [],
              "what": "", "why": "", "next": "", "source": []}
        cur = None
        for ln in lines[1:]:
            if ln.strip().startswith("<!--") or ln.strip().startswith("#"):
                continue
            m = re.match(r"^\s*(키워드|날짜|수정|요약|무슨 일|왜 화제|앞으로|출처)\s*[:：]\s*(.*)$", ln)
            if m:
                cur, val = FIELDS[m.group(1)], m.group(2).strip()
                if cur == "source":
                    if val:
                        name, _, link = val.partition("|")
                        it["source"].append({"name": name.strip(), "link": link.strip()} if link
                                            else {"name": "", "link": name.strip()})
                elif cur == "summary":
                    if val:
                        it["summary"].append(val.lstrip("-• ").strip())
                else:
                    it[cur] = val
                continue
            if cur == "summary" and ln.strip().startswith(("-", "•")):
                it["summary"].append(ln.strip().lstrip("-• ").strip())
            elif cur in ("what", "why", "next"):
                it[cur] += "\n" + ln.rstrip()
        for k in ("what", "why", "next"):
            it[k] = it[k].strip()
        it["keyword"] = it["keyword"] or it["title"].split()[0]
        blob = " ".join([it["what"], it["why"], it["next"]] + it["summary"])
        if "[확인 필요" in blob:          # 확인 안 된 내용이 남아 있으면 아직 내보내지 않아요
            print(f"[해설] '{it['title']}' 에 [확인 필요] 가 남아 있어서 아직 페이지로 만들지 않았어요.")
            continue
        if it["title"] and (it["what"] or it["summary"]):
            out.append(it)
    return out


def plain(t):
    """검색 설명·미리보기처럼 형광펜을 쓸 수 없는 곳에서는 == 기호를 빼요"""
    return (t or "").replace("==", "").replace("!!", "")


def hl(escaped):
    """==핵심 문장== 은 굵은 글씨+민트 밑줄, !!주의 문구!! 는 빨간 물결 밑줄로 바꿔요. 이미 e()로 감싼 글자에 써요."""
    if "==" in escaped and "!!" in escaped:      # 한 문단에 강조는 하나만: 핵심 문장이 있으면 주의 표시는 빼요
        escaped = escaped.replace("!!", "")
    escaped = re.sub(r"==(.+?)==", r'<mark class="hl">\1</mark>', escaped)       # 핵심 문장
    return re.sub(r"!!(.+?)!!", r'<mark class="warn">\1</mark>', escaped)          # 주의 문구 (과태료·마감일 등)


HL_STYLE = "background:linear-gradient(transparent 58%,rgba(255,214,0,.55) 58%);color:inherit;font-weight:700;padding:0 2px"
WARN_STYLE = "background:none;color:inherit;text-decoration:underline wavy #e5484d;text-underline-offset:4px"
H3_STYLE = "font-size:1.05rem;font-weight:800;margin:1.4rem 0 .4rem;padding-left:.6rem;border-left:4px solid #14a38b;line-height:1.5"
FIG_STYLE = "margin:1rem 0"
IMG_STYLE = "display:block;width:100%;height:auto;border-radius:12px"
CAP_STYLE = "font-size:.8rem;color:#888;margin-top:.35rem;line-height:1.5"


def rich(escaped):
    """==형광펜==, !!주의!!, **굵게** 를 꾸며요. 이미 e()로 감싼 글자에 써요."""
    s = hl(escaped)
    s = s.replace('<mark class="hl">', f'<mark class="hl" style="{HL_STYLE}">')
    s = s.replace('<mark class="warn">', f'<mark class="warn" style="{WARN_STYLE}">')
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)


def paras(text):
    """문단을 HTML로 바꿔요.
    ▶ 소제목          → 작은 제목
    사진: 주소 | 설명 | 출처  → 사진과 설명
    **굵게**, ==형광펜==, !!주의!!  → 강조
    """
    out = []
    for p in re.split(r"\n\s*\n", text):
        lines = [ln.strip() for ln in p.strip().split("\n") if ln.strip()]
        buf = []

        def flush():
            if buf:
                out.append(f"<p>{rich(e(' '.join(buf)))}</p>")
                buf.clear()

        for ln in lines:
            if ln.startswith("▶"):
                flush()
                out.append(f'<h3 style="{H3_STYLE}">{rich(e(ln[1:].strip()))}</h3>')
            elif re.match(r"^사진\s*[:：]", ln):
                flush()
                parts = [x.strip() for x in re.sub(r"^사진\s*[:：]\s*", "", ln).split("|")]
                src = parts[0]
                if not re.match(r"^(https?://|\.\./|/)", src):
                    continue
                cap = parts[1] if len(parts) > 1 else ""
                credit = parts[2] if len(parts) > 2 else ""
                caption = e(cap) + (f" · 출처 {e(credit)}" if credit else "")
                out.append(
                    f'<figure style="{FIG_STYLE}"><img src="{e(src)}" alt="{e(cap)}" loading="lazy" style="{IMG_STYLE}">'
                    + (f'<figcaption style="{CAP_STYLE}">{caption}</figcaption>' if caption else "")
                    + "</figure>"
                )
            else:
                buf.append(ln)
        flush()
    return "".join(out)




def chart_svg(hist, temp):
    if not hist or len(hist) < 2:
        return ""
    ts = [datetime.fromisoformat(h[0]).timestamp() for h in hist]
    t0, t1 = min(ts), max(ts)
    if t1 - t0 < 600:
        return ""
    W, H, P = 320, 130, 16
    vals = [h[1] for h in hist]
    lo, hi = max(0, min(vals) - 8), min(100, max(vals) + 8)
    pts = [(P + (W - 2 * P) * ((t - t0) / (t1 - t0)), H - 24 - (H - 48) * ((v - lo) / max(hi - lo, 1)))
           for t, v in zip(ts, vals)]
    line = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f} {y:.1f}" for i, (x, y) in enumerate(pts))
    hrs = round((t1 - t0) / 3600, 1)
    lx, ly = pts[-1]
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="최근 {hrs}시간 온도 추이, 마지막 {temp}도">'
            f'<line x1="{P}" y1="{H-24}" x2="{W-P}" y2="{H-24}" stroke="var(--line)"/>'
            f'<path d="{line}" stroke="var(--text)" stroke-width="2.5" fill="none" stroke-linejoin="round"/>'
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="var(--text)"/>'
            f'<text x="{min(lx, W-24):.1f}" y="{ly-10:.1f}" text-anchor="middle" font-size="12" font-weight="700" fill="var(--text)">{temp}°</text>'
            f'<text x="{P}" y="{H-6}" font-size="11" fill="var(--sub)">{hrs}시간 전</text>'
            f'<text x="{W-P}" y="{H-6}" font-size="11" fill="var(--sub)" text-anchor="end">마지막 기록</text></svg>')


HEAD = """<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article"><meta property="og:site_name" content="이슈피클">
<meta property="og:title" content="{ogtitle}"><meta property="og:description" content="{desc}"><meta property="og:url" content="{url}">
<meta property="og:image" content="{ogimg}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="alternate" type="application/rss+xml" title="이슈피클" href="../rss.xml">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<link rel="stylesheet" href="../style.css">
<script>try{{var d=document.documentElement,t=localStorage.getItem("theme"),f=localStorage.getItem("fsize");d.setAttribute("data-theme",t||(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"));d.setAttribute("data-fs",{{l:"l",xl:"xl"}}[f]||"m")}}catch(e){{}}</script>
<style>
.ex h1{{font-size:1.5rem;font-weight:700;letter-spacing:-.02em;line-height:1.3;margin:.375rem 0 0}}
.ex .sum{{margin-top:.875rem;padding:1rem}}
.ex .sum h2{{font-size:.875rem;color:var(--sub);font-weight:600;margin-bottom:.375rem}}
.ex .sum ul{{margin:0;padding-left:1.1rem}}.ex .sum li{{margin:.25rem 0;line-height:1.6}}
.ex article{{padding:1.125rem 1rem;font-size:1rem;line-height:1.75}}
.ex article h2{{font-size:1.125rem;font-weight:700;margin:1.25rem 0 .375rem}}.ex article h2:first-child{{margin-top:0}}
.ex article p{{margin:.375rem 0}}
.ex .by{{color:var(--sub);font-size:.8125rem;margin-top:.5rem}}
.ex .rel .rs{{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:.875rem;line-height:1.5;color:var(--sub);margin-top:.125rem}}
.ex .sec-more{{font-size:.8125rem;font-weight:600;color:var(--sub);white-space:nowrap;align-self:flex-end}}
.ex .go-home{{margin-top:.75rem;padding:1rem;display:flex;flex-direction:column;gap:.25rem;background:var(--soft)}}
.ex .go-home b{{font-size:1rem}}.ex .go-home span{{font-size:.875rem;color:var(--sub)}}
.ex .go-btn{{margin-top:.5rem;display:flex;align-items:center;justify-content:center;min-height:2.75rem;border-radius:10px;background:var(--text);color:var(--card);font-weight:700}}
.ex .go-wide{{display:grid;grid-template-columns:auto 1fr auto;gap:.75rem;align-items:center;margin-top:.625rem;padding:.875rem 1rem;border-radius:var(--r-card);background:var(--logo);color:#fff}}
.ex .go-wide .pk{{font-size:1.5rem}}.ex .go-wide b{{display:block;font-size:1rem}}.ex .go-wide small{{display:block;font-size:.8125rem;opacity:.92}}.ex .go-wide .ar{{font-size:1.5rem;font-weight:300}}
.ex .live{{display:flex;align-items:center;justify-content:center;min-height:2.75rem;margin-top:.75rem;border:1px solid var(--line);border-radius:10px;background:var(--card);font-weight:600}}
</style>
<script type="application/ld+json">{ld}</script>
</head>
<body>
<header class="top"><div class="wrap top-in"><div class="logo"><a href="../index.html">이슈<span>피클</span></a></div>
<button class="icon-btn" id="settings-btn" aria-label="화면 설정" aria-haspopup="dialog" aria-controls="settings"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/></svg></button></div></header>
<main class="wrap ex">
"""

FOOT = """
<footer class="foot">
<p><b>이슈피클</b> — 해설은 새콤기자가 근거 기사를 바탕으로 직접 정리했어요. 기사 저작권은 각 언론사에 있어요.</p>
<nav aria-label="사이트 안내"><a href="../about.html">이슈피클이란?</a><a href="../copyright.html">저작권 정책</a><a href="../privacy.html">개인정보처리방침</a><a href="../terms.html">이용약관</a></nav>
<p>© 2026 이슈피클</p></footer>
</main>
<nav class="bnav" data-here=""></nav>
<script src="../ui.js"></script>
<script>document.querySelectorAll('.bnav a').forEach(a=>{const h=a.getAttribute('href');if(!/^(https?:|\\.\\.\\/|#)/.test(h))a.setAttribute('href','../'+h)})</script>
</body></html>
"""


RELATED_N = 4   # 해설 페이지 '다른 이슈 해설' 개수


def related_html(ex, all_explains):
    """최신 해설부터, 지금 보는 글과 키워드가 다른 해설을 골라 요약 한 줄과 함께 보여 줘요"""
    seen, others = {ex["keyword"]}, []
    for o in sorted(all_explains, key=lambda o: o.get("date", ""), reverse=True):
        if o["title"] == ex["title"] or o["keyword"] in seen:
            continue
        seen.add(o["keyword"])
        others.append(o)
        if len(others) >= RELATED_N:
            break
    if not others:
        return ""
    rows = "".join(
        f'<li><a href="{e(slug(o["title"]))}.html"><span><span class="tt">{e(o["title"])}</span>'
        + (f'<span class="rs">{e(plain(o["summary"][0]))}</span>' if o.get("summary") else "")
        + f'<small>{e(o["date"].replace("-", "."))} 해설</small></span><span class="ext" aria-hidden="true">›</span></a></li>'
        for o in others)
    return ('<section class="sec"><div class="sec-head"><div><h2>다른 이슈 해설</h2><p>새콤기자가 정리한 다른 이야기도 읽어 보세요</p></div>'
            '<a class="sec-more" href="./">전체 보기 ›</a></div>'
            f'<div class="box"><ul class="nlist rel">{rows}</ul></div>'
            # 해설을 더 둘러본 뒤 홈으로: 이슈피클 색 넓은 버튼
            '<a class="go-wide" href="../index.html"><span class="pk" aria-hidden="true">🥒</span>'
            '<span><b>지금 뜨는 이슈 전체 보기</b><small>이슈피클 홈 · 30분마다 갱신</small></span>'
            '<span class="ar" aria-hidden="true">›</span></a></section>')


def build_page(ex, snap, all_explains):
    title = ex["title"]
    url = page_url(title)
    date = ex["date"] or (snap or {}).get("first", "")[:10]
    updated = ex["updated"] or date
    summary = ex["summary"][:3]
    desc = plain(" ".join(summary) or ex["what"])[:150]
    img = (snap or {}).get("img", "")
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "Article", "headline": title[:110], "description": desc,
         "datePublished": date, "dateModified": updated, "inLanguage": "ko",
         "author": {"@type": "Person", "name": "새콤기자", "url": SITE_URL + "about.html"}, "publisher": {"@type": "Organization", "name": "이슈피클"},
         "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL},
         "mainEntityOfPage": url, "image": OG_IMG},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": SITE_NAME, "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "이슈 해설", "item": SITE_URL + "i/"},
            {"@type": "ListItem", "position": 3, "name": title, "item": url}]}]}
    head = HEAD.format(title=e(f"{title} — 무슨 일이야? 왜 화제? | 이슈피클"), desc=e(desc), url=e(url),
                       ogtitle=e(f"{title} — 이슈피클 해설"),
                       ogimg=e(OG_IMG),
                       ld=json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"))
    body = [f'<a class="back" href="../index.html">‹ 홈으로</a>',
            f'<p class="crumb">이슈 해설{" · " + e(snap["cat"]) if snap and snap.get("cat") else ""}'
            f'{" · " + e(date.replace("-", ".")) + " 작성" if date else ""}'
            f'{" · " + e(updated.replace("-", ".")) + " 수정" if updated and updated != date else ""}</p>',
            f'<h1>{e(title)}</h1>']
    if summary:
        body.append('<section class="box sum" aria-labelledby="h-sum"><h2 id="h-sum">3줄 요약</h2><ul>'
                    + "".join(f"<li>{hl(e(s))}</li>" for s in summary) + "</ul></section>")
    art = []
    for key, head_txt in (("what", "무슨 일이야?"), ("why", "왜 화제야?"), ("next", "앞으로 볼 점")):
        if ex[key]:
            art.append(f"<h2>{head_txt}</h2>{paras(ex[key])}")
    if art:
        body.append('<article class="box" style="margin-top:.75rem">' + "".join(art)
                    + '<p class="by"><b>새콤기자</b> · 긴 기사도 새콤하게 세 줄로 🥒<br>아래 근거 기사를 바탕으로 정리했어요.</p></article>')
    # 다 읽은 뒤 홈으로: 질문형 안내 카드
    body.append('<aside class="box go-home"><b>이 이슈 말고, 오늘은 뭐가 떴을까?</b>'
                '<span>실시간 순위 1위부터 30분마다 새로 골라 둬요</span>'
                '<a class="go-btn" href="../index.html">오늘의 이슈 순위 보러 가기 ›</a></aside>')
    body.append(related_html(ex, all_explains))           # 근거 기사 위: 다른 이슈 해설로 계속 이어 읽기
    if ex["source"]:
        body.append('<section class="sec"><div class="sec-head"><div><h2>근거 기사</h2><p>누르면 원문이 새 창으로 열려요</p></div></div>'
                    '<div class="box"><ul class="nlist">' + "".join(
                        f'<li><a href="{e(s["link"])}" target="_blank" rel="noopener nofollow"><span><span class="tt">{e(s["name"] or s["link"])}</span></span>'
                        f'<span class="ext" aria-hidden="true">원문 ↗</span></a></li>' for s in ex["source"]) + "</ul></div></section>")
    if snap:
        k = (f'<div class="box kpis"><div><b>{snap.get("temp", "–")}°</b><small>온도</small></div>'
             f'<div><b>{snap.get("sources", "–")}곳</b><small>보도한 언론사</small></div>'
             f'<div><b>{snap.get("articles", "–")}건</b><small>관련 기사</small></div></div>')
        body.append(f'<section class="sec"><div class="sec-head"><div><h2>숫자로 보는 이슈</h2>'
                    f'<p>{e(snap.get("at", "")[:16].replace("T", " "))} 이슈피클 집계 기준</p></div></div>{k}'
                    + (f'<div class="box chart" style="margin-top:.625rem">{chart_svg(snap.get("hist"), snap.get("temp"))}</div>' if chart_svg(snap.get("hist"), snap.get("temp")) else "")
                    + "</section>")
        seen, rows = set(), []
        for n in snap.get("news", []):
            if n["source"] in seen:
                continue
            seen.add(n["source"])
            rows.append(f'<li><a href="{e(n["link"])}" target="_blank" rel="noopener nofollow"><span><span class="tt">{e(n["title"])}</span>'
                        f'<small>{e(n["source"])}</small></span><span class="ext" aria-hidden="true">원문 ↗</span></a></li>')
        if len(rows) >= 2:
            body.append('<section class="sec"><div class="sec-head"><div><h2>매체별 제목 비교</h2><p>같은 이슈를 언론사마다 어떻게 썼는지예요</p></div></div>'
                        f'<div class="box"><ul class="nlist">{"".join(rows[:6])}</ul></div></section>')
        if snap.get("live"):
            body.append(f'<a class="live" href="../issue.html?k={urllib.parse.quote(ex["keyword"])}">지금 온도·관련 기사 실시간으로 보기 ›</a>')
    return head + "\n".join(body) + FOOT


def build_index(explains):
    """해설 모아 보기 (i/index.html)"""
    url = SITE_URL + "i/"
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "이슈피클 이슈 해설", "url": url}
    head = HEAD.format(title="이슈 해설 모아 보기 | 이슈피클", desc="요즘 화제가 된 이슈를 무슨 일인지, 왜 화제인지 짧게 정리한 이슈피클 해설 모음이에요.",
                       url=url, ogtitle="이슈피클 이슈 해설", ogimg=e(OG_IMG), ld=json.dumps(ld, ensure_ascii=False))
    items = "".join(f'<li><a href="{e(slug(x["title"]))}.html"><span><span class="tt">{e(x["title"])}</span>'
                    f'<small>{e(x["date"].replace("-", "."))} · {e(plain((x["summary"] or [x["what"]])[0])[:60])}</small></span></a></li>'
                    for x in explains)
    return head + ('<a class="back" href="../index.html">‹ 홈으로</a><h1>이슈 해설</h1>'
                   '<p class="note">요즘 화제가 된 이슈를 새콤기자가 짧게 정리했어요.</p>'
                   f'<div class="box" style="margin-top:.75rem"><ul class="nlist">{items or "<li class=state>아직 해설이 없어요.</li>"}</ul></div>') + FOOT


# ───────────── 날짜별 '오늘의 이슈' 페이지 (b/2026-11-10.html) ─────────────
# 순위 기록만 있는 날은 검색에 내보내지 않고(noindex), 새콤기자 해설이 있는 날만 검색에 내보내요.
DAY_DIR = SITE / "b"
WEEK = "월화수목금토일"


def day_label(day):
    d = datetime.strptime(day, "%Y-%m-%d")
    return f"{d.month}월 {d.day}일 ({WEEK[d.weekday()]})"


def small(t):
    return f"<small>{e(t['headline'])}</small>" if t.get("headline") else ""


DAILY_FILE = ROOT / "daily.md"
DAY_MIN_SUMMARY = 5   # 한 줄 요약이 이 개수 이상 있는 날은 해설이 없어도 검색에 내보내요


def read_daily_summaries():
    """daily.md: '## 2026-11-10' 아래에 '- 키워드: 한 줄 요약'"""
    out = {}
    if not DAILY_FILE.exists():
        return out
    for block in re.split(r"^##\s+", DAILY_FILE.read_text(encoding="utf-8"), flags=re.M)[1:]:
        lines = block.splitlines()
        day = lines[0].strip()[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            continue
        for ln in lines[1:]:
            m = re.match(r"^\s*[-•]\s*([^:：]+?)\s*[:：]\s*(.+)$", ln)
            if m and "[확인 필요" not in m.group(2):
                out.setdefault(day, {})[m.group(1).strip()] = m.group(2).strip()
    return out


def issue_card(rank, kw, t, one, ex):
    """하루 정리 페이지의 이슈 카드: 한 줄 요약 + 매체별 제목 + 함께 나온 말 + 하루 흐름"""
    head = (f'<div class="ih"><span class="rk">{rank}</span><b>{e(t["title"])}</b>'
            f'{"<span class=ic>" + e(t["cat"]) + "</span>" if t.get("cat") else ""}</div>')
    parts = [head]
    if one:
        parts.append(f'<p class="one">{hl(e(one))}</p>')
    titles = t.get("titles") or ([{"title": t["headline"], "source": "", "link": ""}] if t.get("headline") else [])
    if titles:
        lis = "".join(
            (f'<li><a href="{e(x["link"])}" target="_blank" rel="noopener nofollow">{e(x["title"])}</a>' if x.get("link") else f'<li>{e(x["title"])}')
            + (f' <small>{e(x["source"])}</small>' if x.get("source") else "") + "</li>" for x in titles[:3])
        parts.append(f'<ul class="hdl">{lis}</ul>')
    words = [w for w in (t.get("words") or {}) if w not in t["title"]][:5]
    if words:
        parts.append(f'<p class="wd">함께 나온 말 · {" · ".join(e(w) for w in words)}</p>')
    flow = []
    if t.get("first") and t.get("first") == t.get("best_at"):
        flow.append(f'{t["first"]} 처음 10위 안 (곧바로 최고 {t["best"]}위)')
    else:
        if t.get("first"):
            flow.append(f'{t["first"]} 처음 10위 안')
        flow.append(f'{t["best_at"] + " " if t.get("best_at") else ""}최고 {t["best"]}위')
    if t.get("last") and t.get("last_rank") and t.get("last") != t.get("best_at"):
        flow.append(f'{t["last"]} {t["last_rank"]}위')
    parts.append(f'<p class="fl">{" → ".join(flow)}</p>')
    if ex:
        parts.append(f'<a class="exl" href="../i/{e(slug(ex["title"]))}.html">📝 새콤기자 해설 읽기 ›</a>')
    return f'<li id="{e(slug(kw))}">' + "".join(parts) + "</li>"


DAY_CSS = (".ex .ic2{list-style:none;margin:0;padding:0}.ex .ic2>li{padding:1rem;border-top:1px solid var(--line)}.ex .ic2>li:first-child{border-top:0}"
           ".ex .ih{display:flex;align-items:center;gap:.5rem}.ex .ih b{font-size:1.0625rem}"
           ".ex .rk{min-width:1.5rem;font-weight:800;color:var(--sub);font-variant-numeric:tabular-nums}"
           ".ex .ic{font-size:.75rem;color:var(--sub);background:var(--soft);border-radius:4px;padding:.0625rem .375rem}"
           ".ex .one{margin:.5rem 0 0;font-size:.9688rem;line-height:1.65}"
           ".ex .hdl{margin:.5rem 0 0;padding-left:1.1rem;font-size:.875rem;line-height:1.55}.ex .hdl li{margin:.125rem 0}"
           ".ex .hdl a{color:var(--text)}.ex .hdl small{color:var(--sub);font-size:.75rem}"
           ".ex .wd{margin:.5rem 0 0;font-size:.8125rem;color:var(--sub)}"
           ".ex .fl{margin:.25rem 0 0;font-size:.8125rem;color:var(--sub);font-variant-numeric:tabular-nums}"
           ".ex .exl{display:inline-block;margin-top:.5rem;font-size:.875rem;font-weight:600;color:var(--logo)}")


def build_day(day, rec, day_explains, prev_day, next_day, now_iso, summaries=None, all_explains=()):
    url = SITE_URL + f"b/{day}.html"
    label = day_label(day)
    tops = sorted(rec.get("top", {}).items(), key=lambda kv: (-kv[1]["count"], kv[1]["best"]))[:10]
    summaries = summaries or {}
    indexable = bool(day_explains) or len(summaries) >= DAY_MIN_SUMMARY
    is_today = now_iso[:10] == day
    lead = ""
    if tops:
        k, t = tops[0]
        lead = (f"{label} 이슈피클 실시간 순위 상위 10위 안에 오른 이슈는 {len(rec['top'])}개였어요. "
                f"그중 가장 오래 상위권에 머문 이슈는 '{t['title']}'(최고 {t['best']}위)예요.")
    if day_explains or summaries:
        lead += " 이슈마다 새콤기자가 핵심을 한 줄로 정리했어요." if summaries else " 새콤기자가 이날의 주요 이슈를 직접 정리했어요."
    desc = (lead or f"{label} 이슈 정리")[:150]
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": f"{label} 오늘의 이슈", "url": url,
          "datePublished": day, "dateModified": (rec.get("last") or day)[:10], "inLanguage": "ko",
          "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL}}
    head = HEAD.format(title=e(f"{label} 오늘의 이슈 정리 — 무슨 일이 화제였나 | 이슈피클"), desc=e(desc), url=e(url),
                       ogtitle=e(f"{label} 오늘의 이슈 — 이슈피클"), ogimg=e(OG_IMG),
                       ld=json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"))
    if not indexable:
        head = head.replace("<title>", '<meta name="robots" content="noindex,follow">\n<title>', 1)
    head = head.replace('href="../rss.xml"', 'href="../rss.xml"').replace("</style>",
        ".ex .tl{list-style:none;margin:0;padding:0}.ex .tl li{padding:.5rem 1rem;border-top:1px solid var(--line);font-size:.9375rem;line-height:1.55}"
        ".ex .tl li:first-child{border-top:0}.ex .tl small{display:block;color:var(--sub);font-size:.8125rem}"
        ".ex .dnav{display:flex;justify-content:space-between;gap:.5rem;margin-top:1rem}.ex .dnav a{color:var(--sub);font-size:.875rem;font-weight:600}" + DAY_CSS + "</style>", 1)
    body = ['<a class="back" href="../index.html">‹ 홈으로</a>',
            f'<p class="crumb">오늘의 이슈 · {e(day.replace("-", "."))}{" · " + e(now_iso[11:16]) + "까지 집계" if is_today else ""}</p>',
            f"<h1>{e(label)} 이슈 정리</h1>"]
    if lead:
        body.append(f'<p class="note" style="margin-top:.5rem;font-size:.9375rem;line-height:1.7">{e(lead)}</p>')
    if day_explains:
        items = "".join(
            f'<li><a href="../i/{e(slug(x["title"]))}.html"><span><span class="tt">{e(x["title"])}</span>'
            f'<small>{e(plain((x["summary"] or [x["what"]])[0])[:90])}</small></span></a></li>' for x in day_explains)
        body.append('<section class="sec"><div class="sec-head"><div><h2>📝 새콤기자 해설</h2><p>이날 화제가 된 이슈를 직접 정리했어요</p></div></div>'
                    f'<div class="box"><ul class="nlist">{items}</ul></div></section>')
    if tops:
        ex_by_kw = {x["keyword"]: x for x in all_explains}
        rows = []
        for n, (kw, t) in enumerate(tops, 1):
            ex = ex_by_kw.get(kw)
            one = summaries.get(kw) or (plain(ex["summary"][0]) if ex and ex.get("summary") else "")
            rows.append(issue_card(n, kw, t, one, ex))
        body.append('<section class="sec"><div class="sec-head"><div><h2>하루 동안 오래 머문 이슈</h2>'
                    '<p>실시간 순위 10위 안에 오래 머문 순서예요 · 제목을 누르면 원문이 열려요</p></div></div>'
                    f'<div class="box"><ol class="ic2">{"".join(rows)}</ol></div></section>')
    if rec.get("briefs"):
        bl = ""
        for b in rec["briefs"]:
            h = int(b["slot"][11:13])
            lines = "".join(f'<li>{e(l["icon"])} {e(l["label"])}: <b>{e(l["text"])}</b></li>' for l in b["lines"] if l.get("label") != "관심이 식은 이슈")
            bl += f'<h3 style="font-size:.9375rem;margin:.875rem 0 .25rem">{"자정" if h == 0 else str(h) + "시"} 브리핑</h3><div class="box"><ul class="tl">{lines}</ul></div>'
        body.append(f'<section class="sec"><div class="sec-head"><div><h2>시간대별 브리핑</h2><p>3시간마다 순위가 어떻게 바뀌었는지예요</p></div></div>{bl}</section>')
    nav = '<nav class="dnav" aria-label="다른 날">'
    nav += f'<a href="{prev_day}.html">‹ {e(day_label(prev_day))}</a>' if prev_day else "<span></span>"
    nav += '<a href="index.html">날짜별 모아 보기</a>'
    nav += f'<a href="{next_day}.html">{e(day_label(next_day))} ›</a>' if next_day else "<span></span>"
    body.append(nav + "</nav>")
    return head + "\n".join(body) + FOOT, indexable


def build_days(daily, explains, now_iso):
    """날짜별 페이지를 만들고, 검색에 내보낼(해설이 있는) 날짜 목록을 돌려줘요"""
    DAY_DIR.mkdir(parents=True, exist_ok=True)
    days = sorted(daily or {})
    sums = read_daily_summaries()
    good = []
    for i, day in enumerate(days):
        exs = [x for x in explains if x["date"] == day]
        html_, ok = build_day(day, daily[day], exs, days[i - 1] if i else None,
                              days[i + 1] if i + 1 < len(days) else None, now_iso, sums.get(day), explains)
        (DAY_DIR / f"{day}.html").write_text(html_, encoding="utf-8")
        if ok:
            good.append(day)
    url = SITE_URL + "b/"
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "날짜별 오늘의 이슈", "url": url}
    head = HEAD.format(title="날짜별 오늘의 이슈 | 이슈피클", desc="하루 동안 화제가 된 이슈와 새콤기자 해설을 날짜별로 모았어요.",
                       url=url, ogtitle="날짜별 오늘의 이슈 — 이슈피클", ogimg=e(OG_IMG), ld=json.dumps(ld, ensure_ascii=False))
    items = "".join(f'<li><a href="{d}.html"><span><span class="tt">{e(day_label(d))}</span>'
                    f'<small>{"📝 해설 " + str(sum(1 for x in explains if x["date"] == d)) + "개 · " if d in good else ""}'
                    f'순위에 오른 이슈 {len(daily[d].get("top", {}))}개</small></span></a></li>' for d in reversed(days))
    (DAY_DIR / "index.html").write_text(head + '<a class="back" href="../index.html">‹ 홈으로</a><h1>날짜별 오늘의 이슈</h1>'
        '<p class="note">하루 동안 화제가 된 이슈를 날짜별로 모았어요.</p>'
        f'<div class="box" style="margin-top:.75rem"><ul class="nlist">{items or "<li class=state>아직 기록이 없어요.</li>"}</ul></div>' + FOOT,
        encoding="utf-8")
    return good


# ───────────── 이번 달 달라지는 것 (calendar.md → m/2026-11.html) ─────────────
CAL_FILE = ROOT / "calendar.md"
MON_DIR = SITE / "m"
CAL_MIN_INDEX = 3   # 이 개수 이상 적힌 달만 검색에 내보내요
CAL_FIELDS = {"날짜": "date", "분류": "cat", "대상": "who", "내용": "body", "출처": "source"}


def read_calendar():
    if not CAL_FILE.exists():
        return []
    out = []
    for block in re.split(r"^##\s+", CAL_FILE.read_text(encoding="utf-8"), flags=re.M)[1:]:
        lines = block.splitlines()
        it = {"title": lines[0].strip(), "date": "", "cat": "", "who": "", "body": "", "source": []}
        cur = None
        for ln in lines[1:]:
            m = re.match(r"^\s*(날짜|분류|대상|내용|출처)\s*[:：]\s*(.*)$", ln)
            if m:
                cur, val = CAL_FIELDS[m.group(1)], m.group(2).strip()
                if cur == "source":
                    name, _, link = val.partition("|")
                    if link.strip().startswith("http"):
                        it["source"].append({"name": name.strip(), "link": link.strip()})
                else:
                    it[cur] = val
            elif cur == "body" and ln.strip():
                it["body"] += " " + ln.strip()
        it["date"] = (re.match(r"\d{4}-\d{2}(-\d{2})?", it["date"]) or [""])[0]
        blob = " ".join([it["title"], it["who"], it["body"]])
        if "[확인 필요" in blob:
            print(f"[달력] '{it['title']}' 에 [확인 필요] 가 남아 있어서 올리지 않았어요.")
            continue
        if it["title"] and it["date"] and it["body"] and not it["title"].startswith("("):
            out.append(it)
    out.sort(key=lambda x: (x["date"][:7], x["date"] if len(x["date"]) == 10 else x["date"] + "-99"))
    return out


def cal_when(it, today):
    """날짜 표시와 D-day 글자"""
    d = it["date"]
    if len(d) == 7:
        return f"{int(d[5:])}월 중", "이달 중"
    dt = datetime.strptime(d, "%Y-%m-%d")
    left = (dt.date() - datetime.strptime(today, "%Y-%m-%d").date()).days
    label = f"{dt.month}월 {dt.day}일 ({WEEK[dt.weekday()]})"
    return label, ("오늘" if left == 0 else f"D-{left}" if left > 0 else "시행 중")


def calendar_home(today, n=5):
    """첫 화면용: 오늘 이후 일정 먼저, 남으면 이번 달 지난 일정"""
    items = read_calendar()
    month = today[:7]
    up = [x for x in items if (len(x["date"]) == 10 and x["date"] >= today) or (len(x["date"]) == 7 and x["date"] == month)]
    past = [x for x in items if len(x["date"]) == 10 and x["date"][:7] == month and x["date"] < today]
    out = []
    for it in (up + list(reversed(past)))[:n]:
        when, dd = cal_when(it, today)
        out.append({"title": it["title"], "when": when, "dday": dd, "cat": it["cat"], "month": it["date"][:7],
                    "anchor": slug(it["title"])})
    return out


def who_html(x):
    return f'<p class="who">대상: {e(x["who"])}</p>' if x["who"] else ""


def build_months(today):
    items = read_calendar()
    MON_DIR.mkdir(parents=True, exist_ok=True)
    months = sorted({x["date"][:7] for x in items})
    for i, mon in enumerate(months):
        y, m = int(mon[:4]), int(mon[5:])
        its = [x for x in items if x["date"][:7] == mon]
        url = SITE_URL + f"m/{mon}.html"
        title = f"{y}년 {m}월 달라지는 것 총정리"
        lead = plain(f"{y}년 {m}월에 시행되거나 바뀌는 생활 제도와 일정 {len(its)}가지를 날짜순으로 정리했어요. "
                + " · ".join(x["title"] for x in its[:3]) + (" 등" if len(its) > 3 else "") + ".")
        ld = {"@context": "https://schema.org", "@graph": [
            {"@type": "Article", "headline": title, "description": lead[:150], "inLanguage": "ko",
             "datePublished": f"{mon}-01", "dateModified": today, "image": OG_IMG, "mainEntityOfPage": url,
             "author": {"@type": "Person", "name": "새콤기자", "url": SITE_URL + "about.html"},
             "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL}},
            {"@type": "ItemList", "itemListElement": [
                {"@type": "ListItem", "position": k + 1, "name": f'{cal_when(x, today)[0]} {x["title"]}'} for k, x in enumerate(its)]}]}
        head = HEAD.format(title=e(f"{title} — 날짜별 시행일 정리 | 이슈피클"), desc=e(lead[:150]), url=e(url),
                           ogtitle=e(f"{title} — 이슈피클"), ogimg=e(OG_IMG),
                           ld=json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"))
        if len(its) < CAL_MIN_INDEX:      # 일정이 너무 적은 달은 검색에 내보내지 않아요 (얕은 페이지 방지)
            head = head.replace("<title>", '<meta name="robots" content="noindex,follow">\n<title>', 1)
        head = head.replace("</style>",
            ".ex .cal{list-style:none;margin:0;padding:0}.ex .cal>li{padding:1rem;border-top:1px solid var(--line)}.ex .cal>li:first-child{border-top:0}"
            ".ex .cal .d{display:flex;align-items:center;gap:.5rem;font-size:.875rem;color:var(--sub);font-weight:600}"
            ".ex .cal .dd{font-size:.75rem;font-weight:700;padding:.0625rem .4375rem;border-radius:999px;background:var(--soft);color:var(--text)}"
            ".ex .cal .dd.on{background:var(--logo);color:#fff}"
            ".ex .cal h2{font-size:1.0625rem;font-weight:700;margin:.375rem 0 .25rem;line-height:1.45}"
            ".ex .cal p{margin:.25rem 0;line-height:1.7;font-size:.9375rem}.ex .cal .who{color:var(--sub);font-size:.875rem}"
            ".ex .cal .src{margin:.375rem 0 0;padding-left:1.1rem;font-size:.8125rem}.ex .cal .src a{color:var(--sub);text-decoration:underline}"
            ".ex .dnav{display:flex;justify-content:space-between;gap:.5rem;margin-top:1rem}.ex .dnav a{color:var(--sub);font-size:.875rem;font-weight:600}</style>", 1)
        rows = []
        for x in its:
            when, dd = cal_when(x, today)
            src = "".join(f'<li><a href="{e(s["link"])}" target="_blank" rel="noopener nofollow">{e(s["name"] or s["link"])}</a></li>' for s in x["source"])
            rows.append(f'<li id="{e(slug(x["title"]))}"><div class="d">{e(when)}<span class="dd{" on" if dd.startswith("D-") or dd == "오늘" else ""}">{e(dd)}</span>'
                        f'{"<span>· " + e(x["cat"]) + "</span>" if x["cat"] else ""}</div>'
                        f'<h2>{e(x["title"])}</h2>{who_html(x)}'
                        f'<p>{hl(e(x["body"]))}</p>{f"<ol class=src>{src}</ol>" if src else ""}</li>')
        body = ['<a class="back" href="../index.html">‹ 홈으로</a>',
                f'<p class="crumb">이번 달 달라지는 것 · {today.replace("-", ".")} 기준</p>',
                f"<h1>{e(title)}</h1>",
                f'<p class="note" style="margin-top:.5rem;font-size:.9375rem;line-height:1.7">{e(lead)}</p>',
                f'<div class="box" style="margin-top:.875rem"><ul class="cal">{"".join(rows)}</ul></div>',
                '<p class="note" style="margin-top:.75rem">공식 발표와 언론 보도를 2곳 이상 확인해 새콤기자가 정리했어요. 세부 조건은 출처와 담당 기관 안내를 꼭 확인하세요.</p>']
        prev_m, next_m = (months[i - 1] if i else None), (months[i + 1] if i + 1 < len(months) else None)
        nav = '<nav class="dnav" aria-label="다른 달">'
        nav += f'<a href="{prev_m}.html">‹ {int(prev_m[5:])}월</a>' if prev_m else "<span></span>"
        nav += '<a href="index.html">월별 모아 보기</a>'
        nav += f'<a href="{next_m}.html">{int(next_m[5:])}월 ›</a>' if next_m else "<span></span>"
        body.append(nav + "</nav>")
        (MON_DIR / f"{mon}.html").write_text(head + "\n".join(body) + FOOT, encoding="utf-8")
    url = SITE_URL + "m/"
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "월별 달라지는 것", "url": url}
    head = HEAD.format(title="월별 달라지는 것 모아 보기 | 이슈피클", desc="달마다 시행되거나 바뀌는 생활 제도와 일정을 날짜순으로 정리했어요.",
                       url=url, ogtitle="월별 달라지는 것 — 이슈피클", ogimg=e(OG_IMG), ld=json.dumps(ld, ensure_ascii=False))
    lis = "".join(f'<li><a href="{mm}.html"><span><span class="tt">{int(mm[:4])}년 {int(mm[5:])}월 달라지는 것</span>'
                  f'<small>{sum(1 for x in items if x["date"][:7] == mm)}가지</small></span></a></li>' for mm in reversed(months))
    (MON_DIR / "index.html").write_text(head + '<a class="back" href="../index.html">‹ 홈으로</a><h1>월별 달라지는 것</h1>'
        f'<div class="box" style="margin-top:.75rem"><ul class="nlist">{lis or "<li class=state>아직 정리한 달이 없어요.</li>"}</ul></div>' + FOOT,
        encoding="utf-8")
    return [mm for mm in months if sum(1 for x in items if x["date"][:7] == mm) >= CAL_MIN_INDEX]


def build_all(details, old_snaps, now_iso, memes_dict, daily=None):
    """해설 페이지·sitemap·rss 를 만들고, 이슈→해설 주소 지도와 스냅숏을 돌려줘요."""
    explains = sorted(read_explains(), key=lambda x: x["date"], reverse=True)
    snaps = dict(old_snaps or {})
    issues = (details or {}).get("issues", {})
    link_map = {}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for ex in explains:
        s = slug(ex["title"])
        cur = issues.get(ex["keyword"])
        if cur:   # 지금 순위에 있는 이슈면 숫자를 최신으로 저장해 둬요 (순위에서 빠져도 마지막 기록을 보여줘요)
            snaps[s] = {"at": now_iso, "temp": cur.get("temp"), "sources": cur.get("sources"),
                        "articles": cur.get("articles"), "hist": cur.get("hist"), "news": cur.get("news", [])[:8],
                        "cat": (cur.get("cat") or {}).get("name", ""), "img": cur.get("img", ""),
                        "first": snaps.get(s, {}).get("first", now_iso)}
            link_map[ex["keyword"]] = {"url": page_path(ex["title"]), "summary": [plain(x) for x in ex["summary"][:3]]}
        snap = dict(snaps.get(s) or {})
        if snap:
            snap["live"] = bool(cur)
        (OUT_DIR / f"{s}.html").write_text(build_page(ex, snap or None, explains), encoding="utf-8")
    (OUT_DIR / "index.html").write_text(build_index(explains), encoding="utf-8")
    good_days = build_days(daily, explains, now_iso)
    months = build_months(now_iso[:10])
    keep = {slug(x["title"]) for x in explains}
    snaps = {k: v for k, v in snaps.items() if k in keep}

    # sitemap: 검색에 내보낼 페이지만
    today = now_iso[:10]
    urls = [(SITE_URL + p, today if p in ("", "memes.html", "content.html") else None, f, pr) for p, f, pr in STATIC_PAGES]
    memes_pages = [m for m in memes_dict if re.fullmatch(r"[\w.-]+\.html", m.get("page", "") or "")]
    urls += [(SITE_URL + m["page"], m.get("date") or None, "weekly", "0.7") for m in memes_pages]
    if explains:
        urls.append((SITE_URL + "i/", explains[0]["date"] or today, "daily", "0.8"))
    urls += [(page_url(x["title"]), x["updated"] or x["date"] or None, "weekly", "0.8") for x in explains]
    if good_days:
        urls.append((SITE_URL + "b/", good_days[-1], "daily", "0.7"))
    if months:
        urls.append((SITE_URL + "m/", now_iso[:10], "weekly", "0.8"))
        urls += [(SITE_URL + f"m/{mm}.html", now_iso[:10], "weekly", "0.8") for mm in months]
    urls += [(SITE_URL + f"b/{d}.html", d, "monthly", "0.6") for d in good_days]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lm, fq, pr in urls:
        sm.append(f"  <url><loc>{e(loc)}</loc>{f'<lastmod>{lm}</lastmod>' if lm else ''}<changefreq>{fq}</changefreq><priority>{pr}</priority></url>")
    sm.append("</urlset>")
    (SITE / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")

    # rss: 해설 + 밈절임 글
    feed = [(x["date"], x["title"] + " — 이슈피클 해설", page_url(x["title"]), plain(" ".join(x["summary"]) or x["what"][:200])) for x in explains]
    feed += [(m.get("date", ""), m["word"] + " — 밈절임", SITE_URL + m["page"], m.get("meaning", "")) for m in memes_pages]
    feed = sorted([f for f in feed if f[0]], reverse=True)[:30]
    items = []
    for d, t, link, desc in feed:
        try:
            pub = format_datetime(datetime.fromisoformat(d + "T09:00:00+09:00"))
        except ValueError:
            pub = ""
        items.append(f"<item><title>{e(t)}</title><link>{e(link)}</link><guid>{e(link)}</guid>"
                     f"{f'<pubDate>{pub}</pubDate>' if pub else ''}<description>{e(desc)}</description></item>")
    rss = ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
           f"<title>이슈피클</title><link>{SITE_URL}</link><description>요즘 뜨는 이슈와 밈을 짧게 정리해요</description>"
           f"<language>ko</language>{''.join(items)}</channel></rss>\n")
    (SITE / "rss.xml").write_text(rss, encoding="utf-8")
    print(f"검색용 페이지: 해설 {len(explains)}개 · 날짜별 {len(daily or {})}일(검색 노출 {len(good_days)}일) · 사이트맵 {len(urls)}개 주소")
    return link_map, snaps
