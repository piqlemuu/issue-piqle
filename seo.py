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


def paras(text):
    return "".join(f"<p>{e(p.strip())}</p>" for p in re.split(r"\n\s*\n", text) if p.strip())


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
{ogimg}<meta name="twitter:card" content="summary_large_image">
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


def build_page(ex, snap, all_explains):
    title = ex["title"]
    url = page_url(title)
    date = ex["date"] or (snap or {}).get("first", "")[:10]
    updated = ex["updated"] or date
    summary = ex["summary"][:3]
    desc = (" ".join(summary) or ex["what"])[:150]
    img = (snap or {}).get("img", "")
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "Article", "headline": title[:110], "description": desc,
         "datePublished": date, "dateModified": updated, "inLanguage": "ko",
         "author": {"@type": "Person", "name": "새콤기자", "url": SITE_URL + "about.html"}, "publisher": {"@type": "Organization", "name": "이슈피클"},
         "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL},
         "mainEntityOfPage": url, **({"image": img} if img else {})},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": SITE_NAME, "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "이슈 해설", "item": SITE_URL + "i/"},
            {"@type": "ListItem", "position": 3, "name": title, "item": url}]}]}
    head = HEAD.format(title=e(f"{title} — 무슨 일이야? 왜 화제? | 이슈피클"), desc=e(desc), url=e(url),
                       ogtitle=e(f"{title} — 이슈피클 해설"),
                       ogimg=f'<meta property="og:image" content="{e(img)}">\n' if img else "",
                       ld=json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"))
    body = [f'<a class="back" href="../index.html">‹ 홈으로</a>',
            f'<p class="crumb">이슈 해설{" · " + e(snap["cat"]) if snap and snap.get("cat") else ""}'
            f'{" · " + e(date.replace("-", ".")) + " 작성" if date else ""}'
            f'{" · " + e(updated.replace("-", ".")) + " 수정" if updated and updated != date else ""}</p>',
            f'<h1>{e(title)}</h1>']
    if summary:
        body.append('<section class="box sum" aria-labelledby="h-sum"><h2 id="h-sum">3줄 요약</h2><ul>'
                    + "".join(f"<li>{e(s)}</li>" for s in summary) + "</ul></section>")
    art = []
    for key, head_txt in (("what", "무슨 일이야?"), ("why", "왜 화제야?"), ("next", "앞으로 볼 점")):
        if ex[key]:
            art.append(f"<h2>{head_txt}</h2>{paras(ex[key])}")
    if art:
        body.append('<article class="box" style="margin-top:.75rem">' + "".join(art)
                    + '<p class="by"><b>새콤기자</b> · 긴 기사도 새콤하게 세 줄로 🥒<br>아래 근거 기사를 바탕으로 정리했어요.</p></article>')
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
    others = [o for o in all_explains if o["title"] != title][:5]
    if others:
        body.append('<section class="sec"><div class="sec-head"><div><h2>다른 이슈 해설</h2></div></div><div class="box"><ul class="nlist">'
                    + "".join(f'<li><a href="{e(slug(o["title"]))}.html"><span><span class="tt">{e(o["title"])}</span>'
                              f'<small>{e(o["date"].replace("-", "."))}</small></span></a></li>' for o in others) + "</ul></div></section>")
    return head + "\n".join(body) + FOOT


def build_index(explains):
    """해설 모아 보기 (i/index.html)"""
    url = SITE_URL + "i/"
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "이슈피클 이슈 해설", "url": url}
    head = HEAD.format(title="이슈 해설 모아 보기 | 이슈피클", desc="요즘 화제가 된 이슈를 무슨 일인지, 왜 화제인지 짧게 정리한 이슈피클 해설 모음이에요.",
                       url=url, ogtitle="이슈피클 이슈 해설", ogimg="", ld=json.dumps(ld, ensure_ascii=False))
    items = "".join(f'<li><a href="{e(slug(x["title"]))}.html"><span><span class="tt">{e(x["title"])}</span>'
                    f'<small>{e(x["date"].replace("-", "."))} · {e((x["summary"] or [x["what"]])[0][:60])}</small></span></a></li>'
                    for x in explains)
    return head + ('<a class="back" href="../index.html">‹ 홈으로</a><h1>이슈 해설</h1>'
                   '<p class="note">요즘 화제가 된 이슈를 새콤기자가 짧게 정리했어요.</p>'
                   f'<div class="box" style="margin-top:.75rem"><ul class="nlist">{items or "<li class=state>아직 해설이 없어요.</li>"}</ul></div>') + FOOT


def build_all(details, old_snaps, now_iso, memes_dict):
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
            link_map[ex["keyword"]] = {"url": page_path(ex["title"]), "summary": ex["summary"][:3]}
        snap = dict(snaps.get(s) or {})
        if snap:
            snap["live"] = bool(cur)
        (OUT_DIR / f"{s}.html").write_text(build_page(ex, snap or None, explains), encoding="utf-8")
    (OUT_DIR / "index.html").write_text(build_index(explains), encoding="utf-8")
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
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lm, fq, pr in urls:
        sm.append(f"  <url><loc>{e(loc)}</loc>{f'<lastmod>{lm}</lastmod>' if lm else ''}<changefreq>{fq}</changefreq><priority>{pr}</priority></url>")
    sm.append("</urlset>")
    (SITE / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")

    # rss: 해설 + 밈절임 글
    feed = [(x["date"], x["title"] + " — 이슈피클 해설", page_url(x["title"]), " ".join(x["summary"]) or x["what"][:200]) for x in explains]
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
    print(f"검색용 페이지: 해설 {len(explains)}개 · 사이트맵 {len(urls)}개 주소")
    return link_map, snaps
