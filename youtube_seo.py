#!/usr/bin/env python3
"""Build a crawlable YouTube ranking landing page from existing content.json.
Run after collect.py. Changes do not touch the collector or original data.
"""
import html
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
SITE = ROOT / 'site'
BASE = 'https://piqlemuu.github.io/issue-piqle/'
START = '<!-- YOUTUBE_SEO_LINK_START -->'
END = '<!-- YOUTUBE_SEO_LINK_END -->'


def e(v):
    return html.escape(str(v if v is not None else ''), quote=True)


def compact(n):
    try:
        return f'{int(n):,}'
    except (TypeError, ValueError):
        return '집계 전'


def safe_youtube_url(item):
    ident = str(item.get('id') or '')
    if re.fullmatch(r'[A-Za-z0-9_-]{11}', ident):
        return 'https://www.youtube.com/watch?v=' + ident
    link = str(item.get('link') or '')
    p = urlparse(link)
    if p.scheme == 'https' and p.netloc.lower() in {'www.youtube.com', 'youtube.com', 'youtu.be'}:
        return link
    return ''


def get_data():
    f = SITE / 'content.json'
    if not f.is_file():
        return {}, []
    try:
        data = json.loads(f.read_text(encoding='utf-8'))
        assert isinstance(data, dict)
        items = [x for x in data.get('youtube', []) if isinstance(x, dict)]
        return data, items[:100]
    except (ValueError, AssertionError) as ex:
        print(f'[youtube_seo] content.json unusable: {ex}')
        return {}, []


def build():
    data, items = get_data()
    valid = [v for v in items if safe_youtube_url(v) and v.get('title')]
    updated = str(data.get('updated') or '')
    hours = data.get('youtube_hours') or 6
    try:
        hours = int(hours)
        if not 1 <= hours <= 48:
            hours = 6
    except (ValueError, TypeError):
        hours = 6

    rows = []
    for i, v in enumerate(valid, 1):
        rank = v.get('rank') if isinstance(v.get('rank'), int) and v['rank'] > 0 else i
        channel = v.get('channel') or '채널 정보 없음'
        title = v.get('title') or '제목 없음'
        gain = v.get('gain')
        hrs = v.get('hrs')
        details = f'누적 조회수 {compact(v.get("views"))}회'
        if gain is not None:
            details += f' · 관측 조회수 증가 {compact(gain)}회'
            if hrs:
                details += f' ({e(hrs)}시간 관측)'
        url = safe_youtube_url(v)
        rows.append(f'<li class="yt-item"><span class="yt-rank">{e(rank)}</span><div>'
                    f'<a href="{e(url)}" rel="noopener noreferrer" target="_blank">{e(title)}</a>'
                    f'<p class="yt-channel">{e(channel)}</p><p class="yt-numbers">{details}</p>'
                    f'</div></li>')

    if not rows:
        rows.append('<li class="yt-empty">지금은 공개할 수 있는 유튜브 순위 데이터가 없습니다. 다음 수집 이후 업데이트됩니다.</li>')

    structured = {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        'name': '한국 유튜브 인기 영상 순위 TOP 100 | 이슈피클',
        'url': BASE + 'youtube-trending.html',
        'inLanguage': 'ko-KR',
        'description': '한국 유튜브 인기 영상 중 최근 조회수 증가 속도를 기준으로 비교한 순위',
    }
    if valid:
        structured['mainEntity'] = {
            '@type': 'ItemList',
            'numberOfItems': len(valid),
            'itemListElement': [
                {'@type': 'ListItem', 'position': idx, 'name': str(v.get('title') or ''), 'url': safe_youtube_url(v)}
                for idx, v in enumerate(valid, 1)
            ]
        }
    data_markup = json.dumps(structured, ensure_ascii=False).replace('<', '\\u003c')
    page = '''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>유튜브 인기 영상 순위 TOP 100 | 조회수 증가 랭킹 - 이슈피클</title>
<meta name="description" content="한국 유튜브 인기 영상 TOP 100을 최근 조회수 증가 속도로 비교합니다. 최신 순위와 누적 조회수, 관측 증가량, 집계 기준을 확인하세요.">
<link rel="canonical" href="''' + BASE + '''youtube-trending.html">
<meta property="og:type" content="website">
<meta property="og:site_name" content="이슈피클">
<meta property="og:title" content="유튜브 인기 영상 순위 TOP 100 | 이슈피클">
<meta property="og:description" content="최근 조회수 증가 속도로 보는 한국 유튜브 인기 영상 순위">
<meta property="og:url" content="''' + BASE + '''youtube-trending.html">
<meta property="og:image" content="''' + BASE + '''og.jpg">
<link rel="stylesheet" href="style.css">
<script type="application/ld+json">''' + data_markup + '''</script>
<style>
.ytseo{max-width:920px;margin:0 auto;padding:22px 16px 60px;line-height:1.65;word-break:keep-all}
.ytseo h1{font-size:clamp(1.55rem,3.8vw,2.2rem);line-height:1.35;margin:14px 0 10px}
.ytseo h2{font-size:1.2rem;margin:36px 0 10px}
.ytseo p{margin:9px 0}.ytseo a{color:inherit}
.yt-eyebrow{font-size:.8rem;font-weight:800;color:var(--sub,#666)}
.yt-summary{color:var(--sub,#555);max-width:740px}
.yt-meta{font-size:.85rem;color:var(--sub,#555);margin-top:8px}
.yt-links{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0 22px}
.yt-links a{border:1px solid var(--line,#ddd);border-radius:9px;padding:8px 12px;text-decoration:none;font-size:.88rem}
.yt-items{list-style:none;padding:0;margin:20px 0;display:grid;gap:10px}
.yt-item{display:grid;grid-template-columns:36px minmax(0,1fr);gap:10px;padding:15px;
 border:1px solid var(--line,#ddd);border-radius:12px;background:var(--card,#fff)}
.yt-rank{font-weight:900;font-size:1.15rem}.yt-item a{font-weight:800;text-decoration:none;line-height:1.5}
.yt-item a:hover{text-decoration:underline}.yt-channel,.yt-numbers{color:var(--sub,#555);font-size:.85rem}
.yt-empty{padding:24px;background:var(--card,#fff);border-radius:12px}
.yt-disclosure{margin-top:28px;padding:16px 18px;background:var(--card,#fff);border:1px solid var(--line,#ddd);border-radius:13px}
</style>
</head>
<body>
<header class="top"><div class="wrap top-in"><div class="logo"><a href="index.html">이슈<span>피클</span></a></div></div></header>
<main class="ytseo">
<p class="yt-eyebrow">ISSUE PIQLE · YOUTUBE RANKING</p>
<h1>지금 뜨는 유튜브 인기 영상 TOP 100</h1>
<p class="yt-summary">한국 유튜브 인기 영상의 최근 조회수 증가 속도를 비교해 순위를 보여줍니다. 누적 조회수 순위와는 다르며, 수집 가능한 영상과 데이터에 따라 순위가 달라집니다.</p>
<p class="yt-meta" id="yt-updated">최근 데이터 갱신: ''' + e(updated or '집계 전') + ''' · 비교 기준: 최근 ''' + e(hours) + '''시간</p>
<nav class="yt-links" aria-label="관련 페이지"><a href="content.html#youtube">기존 유튜브 순위 화면</a><a href="content.html#boxoffice">박스오피스</a><a href="content.html#netflix">넷플릭스 TOP 10</a><a href="index.html">이슈피클 홈</a></nav>
<section aria-labelledby="yt-list-title"><h2 id="yt-list-title">한국 유튜브 인기 영상 조회수 증가 순위</h2>
<p>공식 YouTube Data API의 한국 인기 영상 후보를 대상으로, 최근 관측한 조회수 증가량을 바탕으로 정렬합니다.</p>
<ol class="yt-items" id="yt-list">''' + '\n'.join(rows) + '''</ol></section>
<section class="yt-disclosure" aria-labelledby="yt-how"><h2 id="yt-how">순위는 어떻게 계산하나요?</h2>
<p>YouTube Data API에서 한국(regionCode=KR) 인기 영상 후보를 가져와 최근 ''' + e(hours) + '''시간에 해당하는 조회수 증가 속도를 환산해 순위를 매깁니다. 전체 유튜브 영상의 공식 순위가 아니라 이슈피클 자체 집계 순위입니다.</p>
<p>같은 영상의 이전 조회수 기록이 충분하지 않으면 영상의 현재 조회수와 게시 후 경과시간을 활용한 추정치가 반영될 수 있습니다. 영상별로 표시되는 ‘관측 조회수 증가’는 실제로 비교 가능한 기록이 있을 때만 제공됩니다.</p>
<p>집계는 자동 갱신되며 API 응답 지연·수집 실패 등으로 업데이트가 늦어지거나 영상이 누락될 수 있습니다. 콘텐츠의 저작권은 각 원저작자에게 있습니다. 영상 제목을 누르면 원본 유튜브 페이지로 이동합니다.</p></section>
<footer class="foot"><nav aria-label="사이트 안내"><a href="about.html">사이트 소개</a><a href="copyright.html">저작권 정책</a><a href="privacy.html">개인정보처리방침</a><a href="terms.html">이용약관</a></nav><p>© 2026 이슈피클</p></footer>
</main>
<script>
// The initial ranking is server-rendered for crawlers. Refresh only the list for active readers.
const listEl=document.getElementById('yt-list');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function fmt(n){return n==null?'집계 전':Number(n).toLocaleString('ko-KR')}
function youtubeUrl(v){const id=String(v.id||'');return /^[\\w-]{11}$/.test(id)?'https://www.youtube.com/watch?v='+id:''}
async function refresh(){
 try{
  const response=await fetch('content.json?t='+Date.now(),{cache:'no-store'});
  if(!response.ok)throw Error('HTTP '+response.status);
  const d=await response.json();
  const items=(Array.isArray(d.youtube)?d.youtube:[]).filter(v=>v&&v.title&&youtubeUrl(v)).slice(0,100);
  if(!items.length)return;
  listEl.innerHTML=items.map((v,i)=>'<li class="yt-item"><span class="yt-rank">'+esc(v.rank||i+1)+'</span><div><a target="_blank" rel="noopener noreferrer" href="'+youtubeUrl(v)+'">'+esc(v.title)+'</a><p class="yt-channel">'+esc(v.channel||'채널 정보 없음')+'</p><p class="yt-numbers">누적 조회수 '+fmt(v.views)+'회'+(v.gain==null?'':' · 관측 조회수 증가 '+fmt(v.gain)+'회'+(v.hrs?' ('+esc(v.hrs)+'시간 관측)':''))+'</p></div></li>').join('');
  document.getElementById('yt-updated').textContent='최근 데이터 갱신: '+(d.updated||'집계 전')+' · 비교 기준: 최근 '+(d.youtube_hours||6)+'시간';
 }catch(err){/* Keep crawlable build-time snapshot if refresh fails. */}
}
refresh();setInterval(refresh,10*60*1000);
</script>
</body></html>'''
    (SITE / 'youtube-trending.html').write_text(page, encoding='utf-8')
    print(f'[youtube_seo] Built YouTube SEO page with {len(valid)} entries')


def add_nav_links():
    for filename, insertion in [
        ('content.html', '<p class="note" style="margin:12px 0"><a href="youtube-trending.html">유튜브 인기 영상 TOP 100 · 순위 집계 기준 자세히 보기</a></p>'),
        ('index.html', '<p class="note" style="margin:12px 0"><a href="youtube-trending.html">유튜브 인기 영상 TOP 100 · 조회수 증가 순위</a></p>'),
    ]:
        path = SITE / filename
        if not path.is_file():
            continue
        doc = path.read_text(encoding='utf-8')
        doc = re.sub(re.escape(START) + r'.*?' + re.escape(END), '', doc, flags=re.S)
        if filename == 'content.html':
            anchor = '<div class="ctabs" id="tabs"'
        else:
            anchor = '<!-- ③ 실시간 이슈 순위 -->'
        pos = doc.find(anchor)
        if pos < 0:
            print(f'[youtube_seo] No anchor in {filename}; left unchanged')
            continue
        doc = doc[:pos] + START + '\n' + insertion + '\n' + END + '\n' + doc[pos:]
        path.write_text(doc, encoding='utf-8')


def add_sitemap():
    path = SITE / 'sitemap.xml'
    if not path.is_file():
        print('[youtube_seo] sitemap missing: no insertion')
        return
    xml = path.read_text(encoding='utf-8')
    loc = BASE + 'youtube-trending.html'
    if '<loc>' + loc + '</loc>' in xml:
        return
    if '</urlset>' not in xml:
        raise RuntimeError('Cannot add sitemap entry: invalid urlset document')
    # The original seo.py rebuilds sitemap on every collection run.
    entry = '<url><loc>' + loc + '</loc><changefreq>daily</changefreq><priority>0.8</priority></url>'
    xml = xml.replace('</urlset>', '  ' + entry + '\n</urlset>', 1)
    path.write_text(xml, encoding='utf-8')


def main():
    if not (SITE / 'content.html').is_file():
        raise FileNotFoundError('Run collect.py before youtube_seo.py')
    build()
    add_nav_links()
    add_sitemap()


if __name__ == '__main__':
    main()
