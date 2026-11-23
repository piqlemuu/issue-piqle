"""Post-build editorial enhancer. Run AFTER collect.py (already done in update.yml)."""
from __future__ import annotations
import html
import json
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent
HOME = ROOT / 'site/index.html'
INDEX = ROOT / 'site/i/index.html'
START = '<!-- ISSUEPIQLE_ORIGINAL_START -->'
END = '<!-- ISSUEPIQLE_ORIGINAL_END -->'
STYLE = '<!-- ISSUEPIQLE_ORIGINAL_STYLE -->'
SIGNGATE_BANNER = '''<aside aria-label="제휴 광고" style="margin:20px auto 28px;padding:0 12px;text-align:center;max-width:516px">
  <p style="margin:0 auto 6px;font-size:12px;color:var(--sub,#53606a);text-align:left;max-width:468px">AD</p>
  <a href="https://click.linkprice.com/click.php?m=signgate&amp;a=A100710283&amp;l=0008&amp;u_id=" target="_blank" rel="sponsored noopener" style="display:block;color:inherit">
    <img src="https://img.linkprice.com/files/stlink/signgate/0007" alt="한국정보인증 SignGate 배너" width="468" height="60" loading="lazy" decoding="async" style="display:block;width:100%;max-width:468px;height:auto;margin:auto" onerror="this.hidden=true;this.style.display='none';this.nextElementSibling.hidden=false">
    <span hidden style="padding:10px 12px;border:1px solid var(--line,#ddd);border-radius:8px;background:var(--card,#fff)">한국정보인증 SignGate 바로가기 ↗</span>
  </a>
  <img src="https://track.linkprice.com/lpshow.php?m_id=signgate&amp;a_id=A100710283&amp;p_id=0000&amp;l_id=0008&amp;l_cd1=2&amp;l_cd2=0" width="1" height="1" alt="" style="display:none">
</aside>'''
CARD = re.compile(r'<a\b(?=[^>]*class="[^"]*\bsk-(?:feat|row)\b)[^>]*>.*?</a>', re.S)
DATE = re.compile(r'20\d{2}[.-]\d{2}[.-]\d{2}')


def text(s):
    return html.unescape(re.sub(r'<[^>]+>', '', s)).strip()


def extract(raw):
    header = raw.split('>', 1)[0]
    def attr(name):
        m = re.search(r'\b'+name+r'="([^"]*)"', header)
        return html.unescape(m.group(1)) if m else ''
    title = re.search(r'<h[23][^>]*>(.*?)</h[23]>', raw, re.S)
    meta = DATE.search(text(raw))
    excerpt = re.search(r'<p class="sk-sum">(.*?)</p>', raw, re.S)
    img = re.search(r'<img[^>]*\bsrc="([^"]+)"', raw)
    bg = re.search(r'background-image\s*:\s*url\([\'\"]?([^\'\"\)]+)', raw)
    return dict(raw=raw, href=attr('href'), category=attr('data-c') or '이슈',
                title=text(title.group(1)) if title else '',
                date=meta.group().replace('.', '-') if meta else '',
                summary=text(excerpt.group(1)) if excerpt else '',
                image=html.unescape(img.group(1) if img else bg.group(1) if bg else ''))


def is_published(c):
    href = unquote(c['href'].split('?', 1)[0].split('#', 1)[0])
    if not (c['title'] and c['date'] and href.endswith('.html')):
        return False
    if href.startswith(('/', 'http:', 'https:')) or '..' in href.split('/'):
        return False
    return (INDEX.parent / href).is_file()


def hero(c):
    esc = lambda s: html.escape(s, quote=True)
    image = (f'<img src="{esc(c["image"])}" alt="" loading="eager" decoding="async">'
             if c['image'] and not c['image'].lower().startswith(('javascript:', 'data:'))
             else '<div class="ip-hero-placeholder" aria-hidden="true">ISSUE PIQLE</div>')
    return (f'<a class="sk-card sk-feat ip-latest-hero" data-c="{esc(c["category"])}" href="{esc(c["href"])}">'
            + image + '<div class="sk-t"><span class="sk-chip">최신 새콤해설</span>'
            + f'<h2>{esc(c["title"])}</h2>'
            + (f'<p class="sk-sum">{esc(c["summary"])}</p>' if c['summary'] else '')
            + f'<div class="sk-meta">{esc(c["date"])} · 새콤해설</div></div></a>')

FEATURE_STYLE = '''<!-- ISSUEPIQLE_LATEST_STYLE --><style>
.ip-latest-hero{display:block;margin:14px 0 24px;border:1px solid var(--line,#ddd);border-radius:17px;overflow:hidden;background:var(--card,#fff);text-decoration:none}
.ip-latest-hero>img{display:block;width:100%;height:auto;aspect-ratio:16/9;max-height:360px;object-fit:cover}
.ip-latest-hero .sk-t{padding:18px 20px 22px}
.ip-latest-hero h2{font-size:clamp(1.3rem,2.9vw,1.9rem);line-height:1.45;margin:12px 0 8px;word-break:keep-all}
.ip-latest-hero .sk-sum{font-size:.93rem;line-height:1.7;margin-top:10px}
.ip-hero-placeholder{height:180px;display:grid;place-items:center;background:var(--soft,#edf4f1);font-weight:900;letter-spacing:.12em}
@media(max-width:600px){.ip-latest-hero .sk-t{padding:15px}.ip-latest-hero>img{max-height:240px}}
</style>'''

HOME_STYLE = STYLE + '''<style>
.ip-original .sec-head h2{font-size:1.25rem;font-weight:900}
.ip-original .sec-head .ip-all{font-size:.8125rem;color:var(--sub);white-space:nowrap}
.ip-original-list{list-style:none;margin:2px 0 0;padding:0}
.ip-original-list li+li{border-top:1px solid var(--line)}
.ip-original-list a{display:flex;gap:10px;align-items:baseline;padding:10px 0;color:var(--text);text-decoration:none}
.ip-original-list a:hover strong{text-decoration:underline}
.ip-lab{flex:none;font-size:.6875rem;font-weight:800;padding:2px 7px;border-radius:4px;background:#D23A22;color:#fff}
.ip-life .ip-lab{background:#0F6E64}
.ip-txt{display:flex;flex-direction:column;gap:2px;min-width:0}
.ip-original-list strong{font-size:.98rem;line-height:1.42;word-break:keep-all}
.ip-original-list .ip-do{font-size:.8125rem;line-height:1.5;color:#0F6E64;font-weight:700}
html[data-theme=dark] .ip-original-list .ip-do{color:#5FD3C1}
</style>'''


WT_MARK = '<!-- WT_LAYOUT -->'


def change_index(doc):
    # Run on generated HTML. Remove old hero and newest row before making the hero.
    all_matches = [(m, extract(m.group())) for m in CARD.finditer(doc)]
    if WT_MARK in doc:
        # 왜떴어? 화면은 seo.py가 대표 카드까지 직접 만들어요. 목록만 읽어 홈에 씁니다.
        published = sorted([c for m, c in all_matches if is_published(c)], key=lambda x: x['date'], reverse=True)
        return doc, published
    published = [(m,c) for m,c in all_matches if is_published(c)]
    if not published:
        print('No eligible published editorial cards, keeping the original page.')
        return doc, []
    latest_m, latest = max(published, key=lambda x: (x[1]['date'], -x[0].start()))
    remove = [(m.start(),m.end()) for m,c in all_matches
              if 'sk-feat' in m.group().split('>',1)[0] or m.start()==latest_m.start()]
    for start,end in sorted(remove, reverse=True):
        doc=doc[:start]+doc[end:]
    tabs=re.search(r'<div class="sk-tabs">.*?</div>',doc,re.S)
    if not tabs: raise ValueError('The existing category tabs were not found; aborting.')
    doc=doc[:tabs.start()]+hero(latest)+'\n'+doc[tabs.start():]  # 소개 문구 바로 아래에 최신 새콤해설
    if 'ISSUEPIQLE_LATEST_STYLE' not in doc:
        doc=doc.replace('</head>', FEATURE_STYLE+'\n</head>',1)
    other=sorted([c for m,c in published if m.start()!=latest_m.start() and c['href']!=latest['href']],
                 key=lambda x:x['date'], reverse=True)
    return doc,[latest]+other


BANNER_START = '<!-- ISSUEPIQLE_SIGNGATE_START -->'
BANNER_END = '<!-- ISSUEPIQLE_SIGNGATE_END -->'
LIFE_CATS = {'생활·경제', '소비·쇼핑', '생활', '교통', '돈·제도', '쇼핑·할인', '보안'}
HOME_ANCHOR = '<!-- ②-2 브리핑: 3시간 사이 가장 큰 변화 한 줄 (누르면 펼쳐짐) -->'  # 홈 첫 화면: 왜떴어? → 실시간 순위


def _tab(c):
    t = c.get('tab') or ''
    if t in ('생활', 'life'): return 'life'
    if t in ('화제', 'buzz'): return 'buzz'
    return 'life' if c.get('category') in LIFE_CATS else 'buzz'


def change_home(doc, items):
    if not items: return doc
    doc=re.sub(re.escape(START)+r'.*?'+re.escape(END)+r'\n?','',doc,flags=re.S)
    doc=re.sub(re.escape(BANNER_START)+r'.*?'+re.escape(BANNER_END)+r'\n?','',doc,flags=re.S)
    doc=re.sub(re.escape(STYLE)+r'<style>.*?</style>','',doc,flags=re.S)
    if '</head>' not in doc or '<footer class="foot">' not in doc or doc.count(HOME_ANCHOR)!=1:
        raise ValueError('Expected homepage elements absent; aborting.')
    doc=doc.replace('</head>',HOME_STYLE+'\n</head>',1)
    esc=lambda s:html.escape(str(s or ''),quote=True)
    life=[c for c in items if _tab(c)=='life'][:2]
    buzz=[c for c in items if _tab(c)=='buzz'][:1]
    def card(c):
        t=_tab(c)
        lab='생활' if t=='life' else '화제'
        line=(f'<span class="ip-do">할 일 · {esc(c["todo"])}</span>' if t=='life' and c.get('todo') else '')
        return (f'<li class="ip-{t}"><a href="i/{esc(c["href"])}"><span class="ip-lab">{lab}</span>'
                f'<span class="ip-txt"><strong>{esc(c["title"])}</strong>{line}</span></a></li>')
    pick=sorted(life+buzz,key=lambda c:c['date'],reverse=True)[:3]
    cards=[card(c) for c in pick] or [card(c) for c in items[:3]]
    section=(START+'\n<section class="sec ip-original" aria-labelledby="ip-original-heading">'
       +'<div class="sec-head"><div><h2 id="ip-original-heading">왜떴어?</h2></div><a class="ip-all" href="i/">전체 ›</a></div>'
       +'<ul class="ip-original-list">'+''.join(cards)+'</ul>'
       +'</section>\n'
       +END+'\n')
    doc=doc.replace(HOME_ANCHOR,section+'\n  '+HOME_ANCHOR,1)
    doc=doc.replace('<footer class="foot">',BANNER_START+'\n'+SIGNGATE_BANNER+'\n'+BANNER_END+'\n<footer class="foot">',1)
    if 'rel="canonical"' not in doc:
        doc=doc.replace('</head>','<link rel="canonical" href="https://piqlemuu.github.io/issue-piqle/">\n</head>',1)
    return doc



def registered_home_items(items):
    """새콤해설 직접 작성 글과 홈 제목 목록이 같은 등록 파일을 사용합니다."""
    path = ROOT / 'editorial-articles.json'
    merged = {item['href']: dict(item) for item in items}
    if path.is_file():
        records = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(records, list):
            raise ValueError('editorial-articles.json must contain a list')
        for record in records:
            item = dict(href=record.get('url', ''), title=record.get('title', ''),
                        date=record.get('date', ''), summary=record.get('sum', ''),
                        category=record.get('cat', '생활·경제'), image=record.get('img', ''),
                        tab=record.get('tab', ''), todo=record.get('todo', ''))
            if is_published(item):
                merged[item['href']] = item
    return sorted(merged.values(), key=lambda item: item['date'], reverse=True)


def main():
    if not (INDEX.is_file() and HOME.is_file()):
        raise FileNotFoundError('Run collect.py first; site/i/index.html and site/index.html required.')
    new_index,items=change_index(INDEX.read_text(encoding='utf-8'))
    items=registered_home_items(items)
    new_home=change_home(HOME.read_text(encoding='utf-8'),items)
    INDEX.write_text(new_index,encoding='utf-8')
    HOME.write_text(new_home,encoding='utf-8')
    print('Featured:',items[0]['title'] if items else 'No eligible article', '| cards:',len(items))

if __name__=='__main__': main()

