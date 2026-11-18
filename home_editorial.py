"""Post-build editorial enhancer. Run AFTER collect.py (already done in update.yml)."""
from __future__ import annotations
import html
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent
HOME = ROOT / 'site/index.html'
INDEX = ROOT / 'site/i/index.html'
START = '<!-- ISSUEPIQLE_ORIGINAL_START -->'
END = '<!-- ISSUEPIQLE_ORIGINAL_END -->'
STYLE = '<!-- ISSUEPIQLE_ORIGINAL_STYLE -->'
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
.ip-original-list{list-style:none;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:14px 0 18px;padding:0}
.ip-original-list li{min-width:0}
.ip-original-list a{display:flex;flex-direction:column;gap:7px;height:100%;padding:17px;border:1px solid var(--line,#ddd);border-radius:13px;background:var(--card,#fff);color:var(--text,inherit);text-decoration:none}
.ip-original-list strong{font-size:1rem;line-height:1.5;word-break:keep-all}
.ip-original-list time{font-size:.75rem;color:var(--sub,#64748b)}
.ip-original-list span{font-size:.84rem;line-height:1.65;color:var(--sub,#64748b)}
@media(max-width:650px){.ip-original-list{grid-template-columns:1fr}}
</style>'''


def change_index(doc):
    # Run on generated HTML. Remove old hero and newest row before making the hero.
    all_matches = [(m, extract(m.group())) for m in CARD.finditer(doc)]
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
    doc=doc[:tabs.end()]+'\n'+hero(latest)+'\n'+doc[tabs.end():]
    if 'ISSUEPIQLE_LATEST_STYLE' not in doc:
        doc=doc.replace('</head>', FEATURE_STYLE+'\n</head>',1)
    other=sorted([c for m,c in published if m.start()!=latest_m.start() and c['href']!=latest['href']],
                 key=lambda x:x['date'], reverse=True)
    return doc,[latest]+other


def change_home(doc, items):
    if not items: return doc
    doc=re.sub(re.escape(START)+r'.*?'+re.escape(END),'',doc,flags=re.S)
    doc=re.sub(re.escape(STYLE)+r'<style>.*?</style>','',doc,flags=re.S)
    if '</head>' not in doc or '<footer class="foot">' not in doc:
        raise ValueError('Expected homepage elements absent; aborting.')
    doc=doc.replace('</head>',HOME_STYLE+'\n</head>',1)
    cards=[]
    for c in items[:6]:
        esc=lambda s:html.escape(s,quote=True)
        cards.append(f'<li><a href="i/{esc(c["href"])}"><strong>{esc(c["title"])}</strong>'
                     +f'<time datetime="{esc(c["date"])}">{esc(c["date"])}</time>'
                     +(f'<span>{esc(c["summary"])}</span>' if c['summary'] else '')+'</a></li>')
    section=(START+'\n<section class="sec ip-original" aria-labelledby="ip-original-heading">'
       +'<div class="sec-head"><div><h2 id="ip-original-heading">이슈피클이 직접 정리한 이야기</h2>'
       +'<p>실시간 순위와 별개로 출처와 맥락을 확인해 정리한 새콤해설입니다.</p></div></div>'
       +'<ul class="ip-original-list">'+''.join(cards)+'</ul>'
       +'<a class="more" href="i/">새콤해설 전체 보기 ›</a></section>\n'+END)
    doc=doc.replace('<footer class="foot">',section+'\n<footer class="foot">',1)
    if 'rel="canonical"' not in doc:
        doc=doc.replace('</head>','<link rel="canonical" href="https://piqlemuu.github.io/issue-piqle/">\n</head>',1)
    return doc


def main():
    if not (INDEX.is_file() and HOME.is_file()):
        raise FileNotFoundError('Run collect.py first; site/i/index.html and site/index.html required.')
    new_index,items=change_index(INDEX.read_text(encoding='utf-8'))
    new_home=change_home(HOME.read_text(encoding='utf-8'),items)
    INDEX.write_text(new_index,encoding='utf-8')
    HOME.write_text(new_home,encoding='utf-8')
    print('Featured:',items[0]['title'] if items else 'No eligible article', '| cards:',len(items))

if __name__=='__main__': main()
