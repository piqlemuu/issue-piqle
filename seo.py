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
from datetime import datetime, timedelta
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


HL_STYLE = "background:none;color:inherit;font-weight:700"
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
            elif re.match(r"^사진\s*[:：]", ln) or re.match(r"^!\[[^\]]*\]\([^)]+\)\s*$", ln):
                flush()
                md = re.match(r"^!\[([^\]]*)\]\(([^)\s]+)[^)]*\)", ln)
                if md:                                         # ![설명](coinone-lead.png) 모양도 사진으로 읽어요
                    parts = [md.group(2), md.group(1)]
                else:
                    parts = [x.strip() for x in re.sub(r"^사진\s*[:：]\s*", "", ln).split("|")]
                src = parts[0]
                if re.match(r"^[\w.-]+\.(png|jpe?g|gif|webp|svg)$", src, re.I):
                    src = "../" + src                          # site 폴더에 올린 그림 이름만 적어도 돼요
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
    if day in WEEK_OF:
        nav += f'<a href="../w/{WEEK_OF[day]}.html">이번 주 정리</a>'
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
        wks = sorted({wk for d, wk in WEEK_OF.items() if d[:7] == mon and week_range(wk)[3][:7] == mon})
        if wks:
            wl = "".join(f'<li><a href="../w/{wk}.html">{e(week_label(wk)[0])} 이슈 정리 ›</a></li>' for wk in wks)
            body.append(f'<div class="box" style="margin-top:.875rem"><ul class="cal">{wl}</ul></div>')
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


# ───────────── 이번 주 이슈 정리 (weekly.md → w/2026-W46.html) ─────────────
WEEK_FILE = ROOT / "weekly.md"
WEEK_DIR = SITE / "w"
WEEK_MIN_ISSUES = 3   # 사람이 쓴 '이번 주 한 줄'과 이슈 정리가 이 개수 이상 있는 주만 검색에 내보내요
WEEK_OF = {}          # 날짜(2026-11-12) → 주 이름(2026-W46). 날짜별 페이지에서 주간 정리로 이어 줘요


def week_range(wk):
    y, w = int(wk[:4]), int(wk[6:])
    mon = datetime.fromisocalendar(y, w, 1).date()
    return [(mon + timedelta(days=i)).isoformat() for i in range(7)]


def week_label(wk):
    days = week_range(wk)
    a, b = datetime.strptime(days[0], "%Y-%m-%d"), datetime.strptime(days[-1], "%Y-%m-%d")
    # 그 주 목요일이 속한 달의 몇째 주인지
    thu = datetime.strptime(days[3], "%Y-%m-%d")
    nth = (thu.day - 1) // 7 + 1
    return f"{thu.year}년 {thu.month}월 {['첫', '둘', '셋', '넷', '다섯'][nth - 1]}째 주", f"{a.month}월 {a.day}일 ~ {b.month}월 {b.day}일"


def read_weekly():
    """weekly.md: '## 2026-W46' 아래에 이번 주 한 줄 / 이슈 / 다음 주 / 출처"""
    if not WEEK_FILE.exists():
        return []
    out = []
    for block in re.split(r"^##\s+", WEEK_FILE.read_text(encoding="utf-8"), flags=re.M)[1:]:
        lines = block.splitlines()
        wk = lines[0].strip()[:8]
        if not re.fullmatch(r"\d{4}-W\d{2}", wk):
            continue
        it = {"week": wk, "one": "", "issues": [], "next": [], "source": []}
        cur = None
        for ln in lines[1:]:
            m = re.match(r"^\s*(이번 주 한 줄|이슈|다음 주|출처|기간)\s*[:：]\s*(.*)$", ln)
            if m:
                cur, val = m.group(1), m.group(2).strip()
                if cur == "이번 주 한 줄":
                    it["one"] = val
                elif cur == "출처":
                    name, _, link = val.partition("|")
                    if link.strip().startswith("http"):
                        it["source"].append({"name": name.strip(), "link": link.strip()})
                continue
            sub = re.match(r"^\s+해설\s*[:：]\s*(.+)$", ln)
            if sub and cur == "이슈" and it["issues"]:
                it["issues"][-1]["ex"] = sub.group(1).strip()
                continue
            m = re.match(r"^\s*[-•]\s*([^:：]+?)\s*[:：]\s*(.+)$", ln)
            if m and cur in ("이슈", "다음 주"):
                if "[확인 필요" in m.group(2):
                    print(f"[주간] {wk} '{m.group(1)}' 에 [확인 필요] 가 남아 있어서 올리지 않았어요.")
                    continue
                (it["issues"] if cur == "이슈" else it["next"]).append({"title": m.group(1).strip(), "body": m.group(2).strip(), "ex": ""})
        if "[확인 필요" in it["one"]:
            it["one"] = ""
        if it["issues"]:
            out.append(it)
    return sorted(out, key=lambda x: x["week"])


def build_weeks(weeks, explains, day_pages, today):
    """주간 정리 페이지를 만들고, 검색에 내보낼 주 목록을 돌려줘요"""
    WEEK_DIR.mkdir(parents=True, exist_ok=True)
    ex_by_title = {x["title"]: x for x in explains}
    good = []
    names = [w["week"] for w in weeks]
    for i, w in enumerate(weeks):
        wk = w["week"]
        days = week_range(wk)
        for d in days:
            WEEK_OF[d] = wk
        title_l, span = week_label(wk)
        indexable = bool(w["one"]) and len(w["issues"]) >= WEEK_MIN_ISSUES
        url = SITE_URL + f"w/{wk}.html"
        title = f"{title_l} 이슈 정리"
        lead = plain(w["one"]) or f"{span} 화제가 된 이슈를 정리했어요."
        ld = {"@context": "https://schema.org", "@graph": [
            {"@type": "Article", "headline": title, "description": lead[:150], "inLanguage": "ko",
             "datePublished": days[-1] if days[-1] <= today else today, "dateModified": today, "image": OG_IMG, "mainEntityOfPage": url,
             "author": {"@type": "Person", "name": "새콤기자", "url": SITE_URL + "about.html"},
             "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL}},
            {"@type": "ItemList", "itemListElement": [
                {"@type": "ListItem", "position": k + 1, "name": x["title"]} for k, x in enumerate(w["issues"])]}]}
        head = HEAD.format(title=e(f"{title} — {span} 무슨 일이 있었나 | 이슈피클"), desc=e(lead[:150]), url=e(url),
                           ogtitle=e(f"{title} — 이슈피클"), ogimg=e(OG_IMG),
                           ld=json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"))
        if not indexable:
            head = head.replace("<title>", '<meta name="robots" content="noindex,follow">\n<title>', 1)
        head = head.replace("</style>",
            ".ex .wk{list-style:none;margin:0;padding:0;counter-reset:w}.ex .wk>li{padding:1rem;border-top:1px solid var(--line)}.ex .wk>li:first-child{border-top:0}"
            ".ex .wk h2{font-size:1.0625rem;font-weight:700;margin:0 0 .25rem;line-height:1.45}.ex .wk h2:before{counter-increment:w;content:counter(w) '. ';color:var(--logo)}"
            ".ex .wk p{margin:.25rem 0;line-height:1.7;font-size:.9375rem}.ex .wk .exl{display:inline-block;margin-top:.375rem;font-size:.875rem;font-weight:700}"
            ".ex .one{font-size:1.0625rem;font-weight:700;line-height:1.6;padding:1rem;border-radius:12px;background:var(--soft);margin:.75rem 0 0}"
            ".ex .tl{list-style:none;margin:0;padding:0}.ex .tl li{padding:.5rem 1rem;border-top:1px solid var(--line);font-size:.9375rem;line-height:1.55}.ex .tl li:first-child{border-top:0}"
            ".ex .src{margin:.375rem 0 0;padding-left:1.1rem;font-size:.8125rem}.ex .src a{color:var(--sub);text-decoration:underline}"
            ".ex .dnav{display:flex;justify-content:space-between;gap:.5rem;margin-top:1rem;flex-wrap:wrap}.ex .dnav a{color:var(--sub);font-size:.875rem;font-weight:600}</style>", 1)
        rows = []
        for x in w["issues"]:
            ex = ex_by_title.get(x["ex"]) if x["ex"] else None
            link = f'<a class="exl" href="../i/{e(slug(ex["title"]))}.html">📝 새콤기자 해설 읽기 ›</a>' if ex else ""
            rows.append(f'<li><h2>{e(x["title"])}</h2><p>{hl(e(x["body"]))}</p>{link}</li>')
        body = ['<a class="back" href="../index.html">‹ 홈으로</a>',
                f'<p class="crumb">이번 주 이슈 정리 · {e(span)}</p>',
                f"<h1>{e(title)}</h1>"]
        if w["one"]:
            body.append(f'<p class="one">🫙 {hl(e(w["one"]))}</p>')
        body.append(f'<section class="sec"><div class="sec-head"><div><h2>이번 주 주요 이슈</h2><p>새콤기자가 고른 {len(w["issues"])}가지예요</p></div></div>'
                    f'<div class="box"><ol class="wk">{"".join(rows)}</ol></div></section>')
        if w["next"]:
            nx = "".join(f'<li><b>{e(x["title"])}</b> · {hl(e(x["body"]))}</li>' for x in w["next"])
            body.append(f'<section class="sec"><div class="sec-head"><div><h2>다음 주에 볼 일정</h2></div></div><div class="box"><ul class="tl">{nx}</ul></div></section>')
        dl = "".join(f'<li><a href="../b/{d}.html">{e(day_label(d))} 이슈 정리 ›</a></li>' for d in days if d in day_pages)
        if dl:
            body.append(f'<section class="sec"><div class="sec-head"><div><h2>날짜별로 더 보기</h2></div></div><div class="box"><ul class="tl">{dl}</ul></div></section>')
        if w["source"]:
            src = "".join(f'<li><a href="{e(s["link"])}" target="_blank" rel="noopener nofollow">{e(s["name"] or s["link"])}</a></li>' for s in w["source"])
            body.append(f'<details style="margin-top:1rem"><summary style="font-weight:700;cursor:pointer">📚 참고한 자료 {len(w["source"])}건</summary><ol class="src">{src}</ol></details>')
        body.append('<p class="note" style="margin-top:.75rem">공식 발표와 언론 보도를 2곳 이상 확인해 새콤기자가 정리했어요.</p>')
        prev_w, next_w = (names[i - 1] if i else None), (names[i + 1] if i + 1 < len(names) else None)
        mon = days[3][:7]
        nav = '<nav class="dnav" aria-label="다른 주">'
        nav += f'<a href="{prev_w}.html">‹ 지난주</a>' if prev_w else "<span></span>"
        nav += f'<a href="index.html">주별 모아 보기</a><a href="../m/{mon}.html">{int(mon[5:])}월 달라지는 것</a>'
        nav += f'<a href="{next_w}.html">다음 주 ›</a>' if next_w else "<span></span>"
        body.append(nav + "</nav>")
        (WEEK_DIR / f"{wk}.html").write_text(head + "\n".join(body) + FOOT, encoding="utf-8")
        if indexable:
            good.append(wk)
    url = SITE_URL + "w/"
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "주별 이슈 정리", "url": url}
    head = HEAD.format(title="주별 이슈 정리 모아 보기 | 이슈피클", desc="한 주 동안 화제가 된 이슈를 새콤기자가 골라 정리했어요.",
                       url=url, ogtitle="주별 이슈 정리 — 이슈피클", ogimg=e(OG_IMG), ld=json.dumps(ld, ensure_ascii=False))
    lis = "".join(f'<li><a href="{w["week"]}.html"><span><span class="tt">{e(week_label(w["week"])[0])} 이슈 정리</span>'
                  f'<small>{e(week_label(w["week"])[1])} · {len(w["issues"])}가지</small></span></a></li>' for w in reversed(weeks))
    (WEEK_DIR / "index.html").write_text(head + '<a class="back" href="../index.html">‹ 홈으로</a><h1>주별 이슈 정리</h1>'
        f'<div class="box" style="margin-top:.75rem"><ul class="nlist">{lis or "<li class=state>아직 정리한 주가 없어요.</li>"}</ul></div>' + FOOT,
        encoding="utf-8")
    return good


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
    # editorial-articles.json 글에 "keyword"가 있으면, 순위에 그 키워드가 뜰 때 '왜떴어?' 표시로 이어 줘요.
    try:
        for _it in _piqle_editorial_items():
            _kw = str(_it.get("keyword") or "").strip()
            if _kw and _kw in issues and _kw not in link_map and (OUT_DIR / _it["url"]).is_file():
                link_map[_kw] = {"url": "i/" + _it["url"], "summary": [plain(_it.get("sum") or "")][:1]}
    except Exception as _err:
        print("[왜떴어] 순위 연결을 만들지 못했어요:", _err)
    (OUT_DIR / "index.html").write_text(build_index(explains), encoding="utf-8")
    weeks = read_weekly()
    good_weeks = build_weeks(weeks, explains, set(daily or {}), now_iso[:10])
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
    # editorial-articles.json 에 등록한 직접 작성 글(HTML)도 사이트맵에 넣어요. 주소는 파일 이름 그대로라 바뀌지 않아요.
    try:
        _known = {u for u, *_ in urls}
        for _it in _piqle_editorial_items():
            _loc = SITE_URL + "i/" + urllib.parse.quote(_it["url"])
            if _loc not in _known and (OUT_DIR / _it["url"]).is_file():
                urls.append((_loc, _it.get("updated") or _it["date"], "weekly", "0.8"))
    except Exception as _err:
        print("[sitemap] 직접 작성 글을 사이트맵에 넣지 못했어요:", _err)
    if good_days:
        urls.append((SITE_URL + "b/", good_days[-1], "daily", "0.7"))
    if months:
        urls.append((SITE_URL + "m/", now_iso[:10], "weekly", "0.8"))
        urls += [(SITE_URL + f"m/{mm}.html", now_iso[:10], "weekly", "0.8") for mm in months]
    urls += [(SITE_URL + f"b/{d}.html", d, "monthly", "0.6") for d in good_days]
    if good_weeks:
        urls.append((SITE_URL + "w/", today, "weekly", "0.8"))
        urls += [(SITE_URL + f"w/{wk}.html", min(week_range(wk)[-1], today), "weekly", "0.8") for wk in good_weeks]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lm, fq, pr in urls:
        sm.append(f"  <url><loc>{e(loc)}</loc>{f'<lastmod>{lm}</lastmod>' if lm else ''}<changefreq>{fq}</changefreq><priority>{pr}</priority></url>")
    sm.append("</urlset>")
    (SITE / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")

    # rss: 해설 + 밈절임 글
    feed = [(x["date"], x["title"] + " — 이슈피클 해설", page_url(x["title"]), plain(" ".join(x["summary"]) or x["what"][:200])) for x in explains]
    feed += [(m.get("date", ""), m["word"] + " — 밈절임", SITE_URL + m["page"], m.get("meaning", "")) for m in memes_pages]
    wk_map = {w["week"]: w for w in weeks}
    feed += [(min(week_range(wk)[-1], today), week_label(wk)[0] + " 이슈 정리 — 이슈피클", SITE_URL + f"w/{wk}.html",
              plain(wk_map[wk]["one"])) for wk in good_weeks]
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
    print(f"검색용 페이지: 해설 {len(explains)}개 · 날짜별 {len(daily or {})}일(검색 노출 {len(good_days)}일) · 주간 {len(weeks)}주(검색 노출 {len(good_weeks)}주) · 사이트맵 {len(urls)}개 주소")
    return link_map, snaps

# ==================================================================
# 새콤 해설 블로그 꾸미기 (seo.py 맨 아래에 붙여 넣는 부분)
# - 해설 모음(i/index.html): 소개 + 분야 탭 + 대표 그림 카드
# - 해설 글(i/*.html): 위쪽 '새콤 해설' 링크, 아래쪽 작성자 상자·이전/다음 글·함께 읽을 해설
# - 문제가 생기면 원래 모양으로 그대로 만들어져요(사이트가 멈추지 않아요).
# ==================================================================
import html as _sk_html
import re as _sk_re

HL_STYLE = "background:none;color:inherit;font-weight:700"  # 형광펜은 사이트 기본 민트색만

SK_NAME = "새콤 해설"
SK_INTRO = "새콤기자가 오늘 화제인 이슈를 무슨 일인지, 왜 화제인지 쉽게 풀어 드려요"
SK_AUTHOR = "새콤기자"
SK_AUTHOR_LINE = "복잡한 이슈를 새콤하게, 핵심만 쉽게 풀어 드려요."
SK_TABS = ["생활·경제", "연예", "커뮤니티", "스포츠"]
SK_COLORS = ["#e6f4ff", "#d9f3ec", "#fff1e0", "#efedff", "#fde3dd"]

SK_CSS = """<style>
.sk{max-width:720px;margin:0 auto;padding:0 0 1rem;word-break:keep-all}
.sk *{box-sizing:border-box}
.sk-intro{margin:.5rem 0 1rem}
.sk-intro h1{font-size:1.5rem;font-weight:900;margin:0}
.sk-intro p{color:var(--sub);font-size:.875rem;margin:.25rem 0 0;line-height:1.6}
.sk-tabs{display:flex;gap:.5rem;overflow-x:auto;padding-bottom:.25rem;margin-bottom:.75rem}
.sk-tab{flex:none;font:inherit;font-size:.8125rem;font-weight:700;padding:.4rem .8rem;border-radius:999px;
 background:var(--card);border:1px solid var(--line);color:var(--sub);cursor:pointer}
.sk-tab.on{background:var(--text);color:var(--bg);border-color:var(--text)}
.sk a{color:inherit;text-decoration:none}
.sk-card{display:block;background:var(--card);border:1px solid var(--line);border-radius:16px;overflow:hidden;margin-top:.75rem}
.sk-feat img{display:block;width:100%;height:clamp(160px,30vw,240px);object-fit:cover;object-position:center 18%}
.sk-feat .sk-t{padding:.9rem 1rem 1rem}
.sk-feat h2{font-size:1.2rem;line-height:1.4;margin:.4rem 0 0;font-weight:900}
.sk-row{display:flex;gap:.75rem;padding:.75rem}
.sk-th{flex:none;width:112px;height:76px;border-radius:10px;background-size:cover;background-position:center;
 display:flex;align-items:center;justify-content:center;text-align:center;font-size:.8125rem;font-weight:900;
 line-height:1.35;padding:.4rem;color:#1d1d1f}
.sk-row h3{font-size:.95rem;line-height:1.4;margin:.3rem 0 0;font-weight:800}
.sk-sum{font-size:.85rem;color:var(--sub);line-height:1.55;margin:.35rem 0 0}
.sk-meta{font-size:.75rem;color:var(--sub);margin-top:.4rem;opacity:.85}
.sk-chip{display:inline-block;font-size:.72rem;font-weight:700;padding:.15rem .5rem;border-radius:6px;background:#e9f7f3;color:#0f8a75}
.sk-new{display:inline-block;margin-left:.35rem;font-size:.7rem;font-weight:800;color:#fff;background:#e5484d;padding:.1rem .4rem;border-radius:5px}
.sk-sec{font-size:1rem;font-weight:900;margin:1.4rem 0 .25rem}
.sk-author{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:1rem;margin-top:1rem}
.sk-author b{font-size:1rem}.sk-author p{margin:.2rem 0 0;font-size:.85rem;color:var(--sub);line-height:1.6}
.sk-author a{color:#14a38b;font-weight:700}
.sk-pn{display:flex;gap:.6rem;margin-top:.75rem}
.sk-pn a,.sk-pn span.sk-empty{flex:1;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:.75rem;
 font-size:.85rem;font-weight:700;line-height:1.4}
.sk-pn small{display:block;font-size:.72rem;color:var(--sub);font-weight:500;margin-bottom:.25rem}
.sk-pn span.sk-empty{visibility:hidden}
.sk-grid{display:grid;grid-template-columns:1fr 1fr;gap:.6rem}
.sk-grid .sk-card{margin-top:.5rem}
.sk-grid .sk-th{width:100%;height:86px;border-radius:0}
.sk-grid .sk-tx{padding:.55rem .65rem .7rem;font-size:.82rem;font-weight:800;line-height:1.4}
.sk-hide{display:none!important}
</style>"""


def _sk_e(s):
    return _sk_html.escape(str(s or ""))


def _sk_slug(title):
    return _sk_re.sub(r"[^0-9A-Za-z가-힣]+", "-", title).strip("-")[:60]


def _sk_extra():
    """explain.md 에서 제목별 '분야:'와 첫 번째 '사진:' 주소를 읽어요."""
    out = {}
    try:
        text = EXPLAIN_FILE.read_text(encoding="utf-8")
    except Exception:
        return out
    for block in _sk_re.split(r"^##\s+", text, flags=_sk_re.M)[1:]:
        lines = block.split("\n")
        title = lines[0].strip()
        cat, img = "", ""
        for ln in lines[1:]:
            s = ln.strip()
            m = _sk_re.match(r"^분야\s*[:：]\s*(.+)$", s)
            if m and not cat:
                cat = m.group(1).strip()
            m = _sk_re.match(r"^사진\s*[:：]\s*([^|]+)", s) or _sk_re.match(r"^!\[[^\]]*\]\(([^)\s]+)", s)
            if m and not img:
                u = m.group(1).strip()
                if _sk_re.match(r"^[\w.-]+\.(png|jpe?g|gif|webp|svg)$", u, _sk_re.I):
                    u = SITE_URL + u
                if _sk_re.match(r"^(https?://|\.\./|/)", u):
                    img = u
        out[title] = {"cat": cat, "img": img}
    return out


def _sk_items(explains):
    extra = _sk_extra()
    items = []
    for ex in explains or []:
        try:
            title = (ex.get("title") or "").strip()
            if not title:
                continue
            x = extra.get(title, {})
            body = " ".join(str(ex.get(k) or "") for k in ("what", "why", "next"))
            body = _sk_re.sub(r"^\s*(사진\s*[:：].*|!\[.*|▶.*)$", "", body, flags=_sk_re.M)
            mins = max(1, round(len(_sk_re.sub(r"\s+", "", body)) / 500))
            summ = ex.get("summary") or []
            if isinstance(summ, str):
                summ = [summ]
            items.append({
                "title": title,
                "url": _sk_slug(title) + ".html",
                "date": str(ex.get("date") or ""),
                "sum": _sk_re.sub(r"==|!!|\*\*", "", summ[0]) if summ else "",
                "cat": x.get("cat") or "이슈",
                "img": x.get("img", ""),
                "mins": mins,
            })
        except Exception:
            continue
    items.sort(key=lambda it: it["date"], reverse=True)
    return items


def _sk_thumb(it, i, cls="sk-th"):
    if it["img"]:
        return f'<div class="{cls}" style="background-image:url(\'{_sk_e(it["img"])}\')"></div>'
    word = it["title"][:14]
    return f'<div class="{cls}" style="background:{SK_COLORS[i % len(SK_COLORS)]}">{_sk_e(word)}</div>'


def _sk_date(d):
    return d.replace("-", ".")


_sk_old_build_index = build_index


def build_index(explains):
    page = _sk_old_build_index(explains)
    try:
        items = _sk_items(explains)
        if not items or "<h1>이슈 해설</h1>" not in page:
            raise ValueError("skip")
        used = [t for t in SK_TABS if any(it["cat"] == t for it in items)]
        tabs = ('<button class="sk-tab on" data-c="전체">전체</button>' + "".join(
            f'<button class="sk-tab" data-c="{_sk_e(t)}">{_sk_e(t)}</button>' for t in used)) if used else ""
        cards = []
        for i, it in enumerate(items):
            chip = f'<span class="sk-chip">{_sk_e(it["cat"])}</span>'
            meta = f'<div class="sk-meta">{_sk_e(_sk_date(it["date"]))} · {_sk_e(it.get("author") or SK_AUTHOR)} · {it["mins"]}분 읽기</div>'
            if i == 0:
                img = (f'<img src="{_sk_e(it["img"])}" alt="" loading="lazy">' if it["img"]
                       else f'<div class="sk-th" style="width:100%;height:160px;border-radius:0;font-size:1.1rem;'
                            f'background:{SK_COLORS[0]}">{_sk_e(it["title"][:20])}</div>')
                cards.append(f'<a class="sk-card sk-feat" data-c="{_sk_e(it["cat"])}" href="{_sk_e(it["url"])}">{img}'
                             f'<div class="sk-t">{chip}<span class="sk-new">NEW</span><h2>{_sk_e(it["title"])}</h2>'
                             f'<p class="sk-sum">{_sk_e(it["sum"])}</p>{meta}</div></a>')
                cards.append('<div class="sk-sec">최신 해설</div>')
            else:
                cards.append(f'<a class="sk-card sk-row" data-c="{_sk_e(it["cat"])}" href="{_sk_e(it["url"])}">'
                             f'{_sk_thumb(it, i)}<div>{chip}<h3>{_sk_e(it["title"])}</h3>{meta}</div></a>')
        js = """<script>(function(){var b=document.querySelectorAll('.sk-tab');b.forEach(function(t){t.onclick=function(){
b.forEach(function(x){x.classList.remove('on')});t.classList.add('on');var c=t.getAttribute('data-c');
document.querySelectorAll('.sk-card').forEach(function(a){a.style.display=(c==='전체'||a.getAttribute('data-c')===c)?'':'none'});
document.querySelectorAll('.sk-sec').forEach(function(s){s.style.display=c==='전체'?'':'none'})}})})();</script>"""
        block = (SK_CSS + '<div class="sk" id="sk-list"><div class="sk-intro"><h1>' + SK_NAME + '</h1><p>'
                 + SK_INTRO + '</p></div><div class="sk-tabs">' + tabs + '</div>' + "".join(cards) + '</div>' + js
                 + '<style>#sk-list ~ :not(nav):not(script):not(footer):not(style){display:none!important}</style>')
        page = page.replace("<h1>이슈 해설</h1>", block, 1)
        page = page.replace("이슈 해설 모아 보기", SK_NAME + " 모아 보기").replace("이슈피클 이슈 해설", "이슈피클 " + SK_NAME)
        return page
    except Exception:
        return page


_sk_old_build_page = build_page


def build_page(ex, snap, all_explains):
    page = _sk_old_build_page(ex, snap, all_explains)
    try:
        page = page.replace('<p class="crumb">이슈 해설', f'<p class="crumb"><a href="index.html">{SK_NAME}</a>', 1)
        page = page.replace('"name": "이슈 해설"', f'"name": "{SK_NAME}"')
        items = _sk_items(all_explains)
        me = (ex.get("title") or "").strip()
        idx = next((i for i, it in enumerate(items) if it["title"] == me), None)
        if idx is None:
            return page
        cur = items[idx]
        older = items[idx + 1] if idx + 1 < len(items) else None
        newer = items[idx - 1] if idx > 0 else None
        def pn(it, label, right=False):
            if not it:
                return '<span class="sk-empty"></span>'
            st = ' style="text-align:right"' if right else ""
            return f'<a href="{_sk_e(it["url"])}"{st}><small>{label}</small>{_sk_e(it["title"])}</a>'
        others = [it for it in items if it["title"] != me]
        same = [it for it in others if it["cat"] == cur["cat"]]
        rel = (same + [it for it in others if it not in same])[:2]
        rel_html = "".join(
            f'<a class="sk-card" href="{_sk_e(it["url"])}">{_sk_thumb(it, i)}'
            f'<div class="sk-tx"><span class="sk-chip">{_sk_e(it["cat"])}</span><br>{_sk_e(it["title"])}</div></a>'
            for i, it in enumerate(rel))
        block = (SK_CSS + '<div class="sk">'
                 + f'<div class="sk-author"><b>{SK_AUTHOR}</b><p>{SK_AUTHOR_LINE}<br>'
                 + f'<a href="index.html">{SK_NAME} 전체 보기 ›</a></p></div>'
                 + '<div class="sk-pn">' + pn(older, "‹ 이전 글") + pn(newer, "다음 글 ›", True) + '</div>'
                 + (f'<div class="sk-sec">함께 읽으면 좋은 해설</div><div class="sk-grid">{rel_html}</div>' if rel else "")
                 + '</div>')
        for mark in ('<nav class="bnav"', "</main>", "</body>"):
            if mark in page:
                return page.replace(mark, block + mark, 1)
        return page + block
    except Exception:
        return page

# PIQLE 직접 작성 글 목록. HTML 원고와 등록 정보를 분리해 자동 수집 시에도 보존합니다.
_sk_automatic_items = _sk_items


def _piqle_editorial_items():
    path = ROOT / "editorial-articles.json"
    if not path.is_file():
        return []
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("editorial-articles.json은 글 목록 배열이어야 합니다")
    result = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("글 목록 항목이 올바르지 않습니다")
        item = dict(record)
        if not re.fullmatch(r"[0-9A-Za-z가-힣][0-9A-Za-z가-힣_.-]*\.html", str(item.get("url", ""))):
            raise ValueError("직접 작성 글 경로는 i 폴더 안의 HTML 파일명이어야 합니다")
        datetime.strptime(item["date"], "%Y-%m-%d")
        if not item.get("title"):
            raise ValueError("글 제목이 필요합니다")
        item.setdefault("sum", "")
        item.setdefault("cat", "생활·경제")
        item.setdefault("img", "")
        item.setdefault("mins", 3)
        result.append(item)
    return result


def _sk_items(explains):
    merged = {item["url"]: item for item in _sk_automatic_items(explains)}
    for item in _piqle_editorial_items():
        merged[item["url"]] = item
    return sorted(merged.values(), key=lambda item: item["date"], reverse=True)


# ── 왜떴어? (2026-11 리뉴얼) ──────────────────────────────────────────────
# 해설 모음(i/index.html)을 '생활 | 화제' 두 칸 구조로 만들어요.
# - 생활: 돈·제도·쇼핑·보안처럼 내 생활에 바로 영향이 있는 글. editorial-articles.json 에 "todo"(지금 할 일)를 적으면 카드에 같이 보여요.
# - 화제: 연예·스포츠·커뮤니티·사회·밈.
# - explain.md 의 '분야:' 로 칸이 정해져요. 직접 정하고 싶으면 editorial-articles.json 에 "tab": "생활" 또는 "화제".
# 다른 스크립트(home_editorial, section_seo)가 찾는 표시(<div class="sk-tabs">, sk-row 카드)는 그대로 둬요.
WT_NAME = "왜떴어?"
WT_MARK = "<!-- WT_LAYOUT -->"
WT_LIFE_CATS = {"생활·경제", "소비·쇼핑", "생활", "교통", "돈·제도", "쇼핑·할인", "보안"}
WT_TABS = {"life": "생활", "buzz": "화제"}

WT_CSS = """<style>
.wt{--wt-red:#D23A22;--wt-red-text:var(--red);--wt-red-soft:#FFF1EC;--wt-teal:#0F6E64;--wt-teal-soft:#E3F2EF;--wt-tile:#2B2C33;--wt-tile-life:#123F3A}
html[data-theme=dark] .wt{--wt-red-soft:rgba(255,122,127,.13);--wt-teal:#5FD3C1;--wt-teal-soft:rgba(95,211,193,.12);--wt-tile:#2A2C33;--wt-tile-life:#173A36}
.wt{padding-bottom:8px}
.wt-eyebrow{margin:18px 0 0;font-size:.8125rem;font-weight:700;color:var(--wt-red-text)}
.wt h1{margin:6px 0 0;font-size:1.875rem;font-weight:900;line-height:1.25;letter-spacing:-.03em}
.wt-search{margin-top:16px;display:flex;gap:8px}
.wt-search input{flex:1;min-width:0;height:48px;border:2px solid var(--text);border-radius:12px;padding:0 14px;font:inherit;font-size:1rem;background:var(--card);color:var(--text)}
.wt-search button{height:48px;padding:0 18px;border:0;border-radius:12px;background:var(--text);color:var(--bg);font-weight:700;font-size:.9375rem;cursor:pointer}
.wt-chips{margin-top:10px;display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.wt-chips span{font-size:.75rem;color:var(--sub)}
.wt-chip{padding:9px 13px;border-radius:999px;background:var(--card);border:1px solid var(--line);font-size:.8125rem;font-weight:700;cursor:pointer;color:var(--text)}
.wt .sk-tabs{position:sticky;top:3.25rem;z-index:5;background:var(--bg);display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:10px 0;margin:14px 0 6px}
.wt .sk-tabs button{height:52px;border-radius:14px;border:2px solid var(--text);background:var(--card);cursor:pointer;color:var(--text);display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.2}
.wt .sk-tabs b{font-weight:900;font-size:1.0625rem}
.wt .sk-tabs small{font-size:.6875rem;color:var(--sub)}
.wt .sk-tabs button[aria-selected=true]{background:var(--text);color:var(--bg)}
.wt .sk-tabs button[aria-selected=true] small{color:var(--line)}
.wt-feature{display:block;background:var(--card);border:1px solid var(--line);border-radius:18px;overflow:hidden;color:var(--text)}
.wt-feature[hidden],.wt-item[hidden]{display:none}
.wt-tile{position:relative;background:var(--wt-tile);color:#F6F4EE;display:flex;align-items:flex-end;padding:14px 16px;font-weight:900;letter-spacing:-.03em;overflow:hidden;background-size:cover;background-position:center}
.wt-life .wt-tile,.wt-item.wt-life .wt-tile{background-color:var(--wt-tile-life)}
.wt-tile.has-img{color:transparent}
.wt-feature .wt-tile{height:150px;font-size:2.25rem}
.wt-badge{position:absolute;top:12px;left:12px;background:var(--wt-red);color:#fff;font-size:.75rem;font-weight:700;padding:5px 10px;border-radius:999px;letter-spacing:0}
.wt-life .wt-badge{background:#fff;color:#0F6E64}
.wt-fbody{padding:14px 16px 16px}
.wt-meta{display:block;margin:0;font-size:.75rem;color:var(--sub)}
.wt-feature h2{margin:6px 0 0;font-weight:800;font-size:1.1875rem;line-height:1.38;letter-spacing:-.02em}
.wt-answer{margin:10px 0 0;padding:10px 12px;background:var(--wt-red-soft);border-radius:10px;font-size:.875rem;line-height:1.55}
.wt-answer b{color:var(--wt-red-text);margin-right:4px}
.wt-todo{margin:8px 0 0;padding:10px 12px;background:var(--wt-teal-soft);border-radius:10px;font-size:.875rem;line-height:1.55}
.wt-todo b{color:var(--wt-teal);margin-right:4px}
.wt-btn{margin-top:12px;display:flex;height:48px;align-items:center;justify-content:center;background:var(--wt-red);color:#fff;border-radius:12px;font-weight:700;font-size:.9375rem}
.wt-life .wt-btn{background:#0F6E64}
.wt-listhead{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-top:24px}
.wt-listhead h2{font-size:1.0625rem;font-weight:800}
.wt-listhead p{margin:0;font-size:.75rem;color:var(--sub)}
.wt-filters{display:flex;gap:6px;margin:12px 0 4px;overflow-x:auto;padding-bottom:4px}
.wt-filters button{flex:none;padding:9px 14px;border-radius:999px;border:1px solid var(--line);background:transparent;font-size:.8125rem;font-weight:700;color:var(--text);cursor:pointer}
.wt-filters button[aria-pressed=true]{background:var(--text);border-color:var(--text);color:var(--bg)}
.wt-note{margin:12px 0 0;font-size:.8125rem;color:var(--sub)}
.wt-note button{border:0;background:none;color:var(--wt-red-text);font-weight:700;font-size:.8125rem;cursor:pointer;padding:8px 4px}
.wt-item{display:flex;gap:12px;padding:14px 0;border-bottom:1px solid var(--line);color:var(--text)}
.wt-item .wt-tile{width:64px;height:64px;flex:none;border-radius:12px;padding:8px;font-size:.8125rem;line-height:1.15}
.wt-txt{display:flex;flex-direction:column;gap:4px;min-width:0}
.wt-item h3{margin:0;font-size:.9375rem;font-weight:700;line-height:1.4}
.wt-item .sk-sum{margin:0;font-size:.8125rem;color:var(--sub);line-height:1.45;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.wt-item .wt-do{font-size:.8125rem;line-height:1.45;color:var(--wt-teal);font-weight:700}
.wt-item:hover h3{text-decoration:underline}
.wt-kind{display:inline-block;font-size:.6875rem;font-weight:700;padding:1px 7px;border-radius:999px;background:var(--soft);margin-right:4px}
.wt-empty{padding:18px 16px;margin-top:12px;background:var(--card);border:1px dashed var(--line);border-radius:14px;font-size:.875rem;line-height:1.6}
.wt-empty a{color:var(--wt-red-text);font-weight:700}
.wt-side{margin:22px 0 0;display:block;background:#121214;color:#F2F2F2;border-radius:18px;padding:18px}
.wt-side b{font-weight:900;font-size:1.25rem;color:#FF4F9A}
.wt-side p{margin:6px 0 0;font-size:.8125rem;color:#C4C4CC;line-height:1.5}
.wt-side span{display:inline-block;margin-top:10px;font-size:.8125rem;font-weight:700;color:#D6FF3F}
.wt-rules{margin:22px 0 0;padding:16px;border-radius:14px;background:var(--soft);font-size:.8125rem;line-height:1.65;color:var(--sub)}
.wt-rules b{display:block;color:var(--text);margin-bottom:4px}
</style>"""

WT_JS = """<script>(function(){
var root=document.getElementById('wt');if(!root)return;
var tabsBox=root.querySelector('.sk-tabs');tabsBox.setAttribute('role','tablist');tabsBox.setAttribute('aria-label','해설 종류');
var tabs=[].slice.call(tabsBox.querySelectorAll('button'));
var items=[].slice.call(root.querySelectorAll('.wt-item'));
var feats=[].slice.call(root.querySelectorAll('.wt-feature'));
var filters=document.getElementById('wt-filters'),note=document.getElementById('wt-note'),empty=document.getElementById('wt-empty');
var q=document.getElementById('wt-q'),head=document.getElementById('wt-listtitle');
var CATS=JSON.parse(root.getAttribute('data-cats'));
var st={tab:'life',cat:'전체',q:''};
var p=new URLSearchParams(location.search);if(p.get('tab')==='buzz')st.tab='buzz';if(p.get('q')){st.q=p.get('q').trim();q.value=st.q;}
function norm(s){return String(s||'').toLowerCase().replace(/\\s+/g,'');}
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function sync(){try{var u=new URL(location.href);st.q?u.searchParams.set('q',st.q):u.searchParams.delete('q');st.tab==='buzz'?u.searchParams.set('tab','buzz'):u.searchParams.delete('tab');history.replaceState(null,'',u);}catch(e){}}
function render(){
 var nq=norm(st.q);
 tabs.forEach(function(b){var on=b.getAttribute('data-tab')===st.tab;b.setAttribute('role','tab');b.setAttribute('aria-selected',on);b.tabIndex=on?0:-1;});
 feats.forEach(function(f){f.hidden=!!nq||f.getAttribute('data-tab')!==st.tab;});
 filters.hidden=!!nq;
 filters.innerHTML=(['전체'].concat(CATS[st.tab]||[])).map(function(c){return '<button type="button" data-cat="'+esc(c)+'" aria-pressed="'+(st.cat===c)+'">'+esc(c)+'</button>';}).join('');
 var n=0;
 items.forEach(function(a){
  var ok;
  if(nq){ok=norm(a.getAttribute('data-k')).indexOf(nq)>-1;}
  else{ok=a.getAttribute('data-tab')===st.tab&&(st.cat==='전체'?!a.hasAttribute('data-feature'):a.getAttribute('data-c')===st.cat);}
  a.hidden=!ok;if(ok)n++;
  var k=a.querySelector('.wt-kind');if(k)k.hidden=!nq;
 });
 head.textContent=nq?'검색 결과':(st.tab==='life'?'생활':'화제')+' 최신 해설';
 if(nq){note.hidden=false;note.innerHTML='‘'+esc(st.q)+'’ 해설 '+n+'개 · 생활·화제 모두에서 찾았어요 <button type="button" id="wt-clear">검색 지우기</button>';document.getElementById('wt-clear').onclick=function(){setQ('');q.focus();};}
 else note.hidden=true;
 empty.hidden=n>0;
 if(!n){empty.querySelector('b').textContent=nq?'아직 ‘'+st.q+'’ 해설이 없어요.':'아직 이 분야 해설이 없어요.';}
}
function setQ(v){st.q=v.trim();q.value=st.q;sync();render();}
function setTab(t){st.tab=t;st.cat='전체';st.q='';q.value='';sync();render();}
function jump(){head.scrollIntoView({behavior:'smooth',block:'start'});}
document.getElementById('wt-form').addEventListener('submit',function(e){e.preventDefault();setQ(q.value);jump();});
q.addEventListener('input',function(){st.q=q.value.trim();render();});
root.querySelectorAll('.wt-chip').forEach(function(b){b.addEventListener('click',function(){setQ(b.getAttribute('data-q'));jump();});});
tabs.forEach(function(b){b.addEventListener('click',function(){setTab(b.getAttribute('data-tab'));});
 b.addEventListener('keydown',function(e){if(e.key==='ArrowRight'||e.key==='ArrowLeft'){var t=st.tab==='life'?'buzz':'life';setTab(t);tabsBox.querySelector('[data-tab='+t+']').focus();}});});
filters.addEventListener('click',function(e){var c=e.target.getAttribute('data-cat');if(!c)return;st.cat=c;render();});
render();
})();</script>"""


def _wt_tab(it):
    t = str(it.get("tab") or "").strip()
    if t in ("생활", "life"):
        return "life"
    if t in ("화제", "buzz"):
        return "buzz"
    return "life" if it.get("cat") in WT_LIFE_CATS else "buzz"


def _wt_items(explains):
    kw = {(ex.get("title") or "").strip(): ex.get("keyword") or "" for ex in explains or []}
    out = []
    for it in _sk_items(explains):
        it = dict(it)
        it["tab"] = _wt_tab(it)
        it["name"] = (it.get("name") or kw.get(it["title"], "") or it["title"])[:12]
        out.append(it)
    return out


def _wt_tile(it, badge=""):
    img = str(it.get("img") or "")
    style = ""
    cls = "wt-tile"
    if img and not img.lower().startswith(("javascript:", "data:")):
        style = f' style="background-image:url(\'{_sk_e(img)}\')"'
        cls += " has-img"
    return f'<span class="{cls}" aria-hidden="true"{style}>{badge}{_sk_e(it["name"])}</span>'


def _wt_block(items):
    cats = {t: [] for t in WT_TABS}
    for it in items:
        if it["cat"] not in cats[it["tab"]]:
            cats[it["tab"]].append(it["cat"])
    feats, rows, featured = [], [], set()
    for tab in WT_TABS:
        first = next((it for it in items if it["tab"] == tab), None)
        if not first:
            continue
        featured.add(first["url"])
        life = tab == "life"
        badge = '<span class="wt-badge">' + ("지금 할 일 있어요" if life and first.get("todo") else "왜 떴어?") + "</span>"
        feats.append(
            f'<a class="wt-feature{" wt-life" if life else ""}" data-tab="{tab}" href="{_sk_e(first["url"])}">'
            + _wt_tile(first, badge)
            + '<span class="wt-fbody" style="display:block">'
            + f'<span class="wt-meta">{_sk_e(first["cat"])} · {_sk_e(_sk_date(first["date"]))} · 새콤기자 · {first["mins"]}분</span>'
            + f'<h2>{_sk_e(first["title"])}</h2>'
            + (f'<span class="wt-answer" style="display:block"><b>한 줄 답</b>{_sk_e(first["sum"])}</span>' if first.get("sum") else "")
            + (f'<span class="wt-todo" style="display:block"><b>지금 할 일</b>{_sk_e(first["todo"])}</span>' if first.get("todo") else "")
            + f'<span class="wt-btn">{"지금 할 일 보기" if life and first.get("todo") else "1분 해설 보기"}</span>'
            + "</span></a>")
    for it in items:
        life = it["tab"] == "life"
        blob = " ".join([it["title"], it["name"], it["cat"], it.get("sum", ""), it.get("keyword", "")])
        line = (f'<span class="wt-do">할 일 · {_sk_e(it["todo"])}</span>' if life and it.get("todo")
                else f'<p class="sk-sum">{_sk_e(it.get("sum", ""))}</p>')
        rows.append(
            f'<a class="wt-item sk-row{" wt-life" if life else ""}" data-tab="{it["tab"]}" data-c="{_sk_e(it["cat"])}"'
            + (' data-feature=""' if it["url"] in featured else "")
            + f' data-k="{_sk_e(blob)}" href="{_sk_e(it["url"])}">'
            + _wt_tile(it)
            + f'<span class="wt-txt"><h3>{_sk_e(it["title"])}</h3>{line}'
            + f'<span class="wt-meta"><span class="wt-kind" hidden>{WT_TABS[it["tab"]]}</span>'
            + f'{_sk_e(it["cat"])} · {_sk_e(_sk_date(it["date"]))} · {it["mins"]}분</span></span></a>')
    chips_src = [it["name"] for it in items[:4]]
    chips = "".join(f'<button type="button" class="wt-chip" data-q="{_sk_e(c)}">{_sk_e(c)}</button>' for c in chips_src)
    return (WT_MARK + WT_CSS
        + f'<div class="wt" id="wt" data-cats=\'{_sk_e(json.dumps(cats, ensure_ascii=False))}\'>'
        + '<p class="wt-eyebrow">이름은 봤는데, 무슨 일인지 모를 때</p>'
        + '<h1>오늘 뜬 이슈,<br>1분이면 따라잡아요</h1>'
        + '<form class="wt-search" id="wt-form" role="search"><label class="sr" for="wt-q">궁금한 이슈 검색</label>'
        + '<input id="wt-q" type="search" placeholder="궁금한 이름·단어" autocomplete="off" enterkeyhint="search">'
        + '<button type="submit">찾기</button></form>'
        + f'<div class="wt-chips" aria-label="최근 해설 키워드"><span>최근 뜬</span>{chips}</div>'
        + '<div class="sk-tabs"><button type="button" data-tab="life"><b>생활</b><small>지금 할 일까지</small></button>'
        + '<button type="button" data-tab="buzz"><b>화제</b><small>왜 떴는지까지</small></button></div>'
        + "".join(feats)
        + '<div class="wt-listhead"><h2 id="wt-listtitle">최신 해설</h2><p>근거 기사 2곳 이상 확인한 것만</p></div>'
        + '<div class="wt-filters" id="wt-filters" role="group" aria-label="분야 고르기"></div>'
        + '<p class="wt-note" id="wt-note" hidden></p>'
        + '<div class="wt-list">' + "".join(rows) + '</div>'
        + '<div class="wt-empty" id="wt-empty" hidden><b></b><br>새콤기자는 근거 기사가 2곳 이상 나온 이슈만 써요. '
        + '지금 뜨는 이슈는 <a href="../">실시간 이슈 순위</a>에서 먼저 확인해 보세요.</div>'
        + '<a class="wt-side" href="tteokbap.html"><b>떡밥정리소</b><p>팬 시선으로 이어 보는 정리 모음은 따로 모았어요. '
        + '컴백 순서, 라인업처럼 줄 세워 봐야 보이는 것들이요.</p><span>떡밥정리소 가기 ›</span></a>'
        + '<aside class="wt-rules"><b>새콤기자가 쓰는 기준</b>공식 발표와 기사 2곳 이상이 있고, ‘왜 지금 떴는지’를 한 줄로 말할 수 있을 때만 써요. '
        + '생활 해설에는 근거 기사에 나온 ‘지금 할 일’만 적어요. 열애·사생활 추측, 확인 안 된 폭로, 외모 평가는 다루지 않아요.</aside>'
        + '</div>' + WT_JS)


_wt_prev_build_index = build_index


def build_index(explains):
    page = _wt_prev_build_index(explains)
    try:
        items = _wt_items(explains)
        open_tag = '<main class="wrap ex">'
        if not items or open_tag not in page or '<footer class="foot">' not in page:
            raise ValueError("skip")
        start = page.index(open_tag) + len(open_tag)
        end = page.index('<footer class="foot">', start)
        page = page[:start] + _wt_block(items) + "\n" + page[end:]
        page = _sk_re.sub(r"<title>.*?</title>", f"<title>{WT_NAME} | 이름은 봤는데 무슨 일인지 모를 때 - 이슈피클 해설</title>", page, count=1, flags=_sk_re.S)
        return page
    except Exception as err:
        print("[왜떴어] 새 해설 모음을 만들지 못해 예전 화면을 써요:", err)
        return page
