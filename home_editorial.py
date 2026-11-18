"""ISSUE PIQLE: adds an indexable original-editorial section to site/index.html.

Run AFTER collect.py, so seo.py has generated the article pages. Idempotent.
This does NOT change the real-time ranking JavaScript or collected data.
"""
from __future__ import annotations
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOME = ROOT / 'site' / 'index.html'
EXPLAINS = ROOT / 'explain.md'
START = '<!-- ISSUEPIQLE_ORIGINAL_START -->'
END = '<!-- ISSUEPIQLE_ORIGINAL_END -->'
MAX_ITEMS = 6


def slug(title: str) -> str:
    # Must match seo.py slug()
    return re.sub(r'[^0-9A-Za-z가-힣]+', '-', title).strip('-')[:60] or 'issue'


def entries():
    if not EXPLAINS.is_file():
        return []
    raw = EXPLAINS.read_text(encoding='utf-8')
    result = []
    for block in re.split(r'^##\s+', raw, flags=re.M)[1:]:
        lines = block.splitlines()
        title = lines[0].strip() if lines else ''
        if not title or title == '쓰는 법':
            continue
        meta = {'date': '', 'summary': '', 'what': ''}
        field = None
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith(('#', '<!--')):
                continue
            m = re.match(r'^\s*(날짜|요약|무슨 일|왜 화제|앞으로|출처|키워드|수정|분야)\s*[:：]\s*(.*)', line)
            if m:
                name, value = m.groups()
                field = name
                if name == '날짜':
                    meta['date'] = value.strip()
                elif name == '요약' and value.strip():
                    meta['summary'] = value.lstrip('-• ').strip()
                elif name == '무슨 일':
                    meta['what'] = value.strip()
                continue
            if field == '요약' and stripped.startswith(('-', '•')) and not meta['summary']:
                meta['summary'] = stripped.lstrip('-• ').strip()
            elif field == '무슨 일' and stripped and not meta['what']:
                meta['what'] = stripped
        excerpt = (meta['summary'] or meta['what']).replace('==', '').replace('!!', '').replace('**', '')
        # In line with seo.py: skip unverified or blank editorial entries
        if '[확인 필요' in block or not excerpt:
            continue
        dest = ROOT / 'site' / 'i' / (slug(title) + '.html')
        if not dest.exists():
            # Only link to pages actually created by seo.py
            continue
        result.append((meta['date'], title, excerpt[:130], slug(title)))
    result.sort(key=lambda x: x[0], reverse=True)
    return result[:MAX_ITEMS]


def build_section():
    articles = entries()
    if articles:
        cards = []
        for date, title, summary, filename in articles:
            cards.append(
                '<li class="ip-original-item"><a href="i/' + html.escape(filename, quote=True) + '.html">'
                '<strong>' + html.escape(title) + '</strong>'
                + ('<time datetime="' + html.escape(date, quote=True) + '">' + html.escape(date) + '</time>' if re.fullmatch(r'\d{4}-\d{2}-\d{2}', date) else '')
                + '<span>' + html.escape(summary) + '</span></a></li>'
            )
        listing = '<ul class="ip-original-list">' + ''.join(cards) + '</ul>'
    else:
        listing = '<p class="ip-original-empty">새콤 해설은 준비 중입니다. 발행된 글은 해설 모음에서 확인할 수 있습니다.</p>'
    return (START + '\n'
        '<section class="sec ip-original" aria-labelledby="ip-original-heading">\n'
        '<div class="sec-head"><div><h2 id="ip-original-heading">이슈피클이 직접 정리한 이야기</h2>'
        '<p>실시간 순위와 별개로 사실과 출처를 확인해 맥락을 정리했습니다.</p></div></div>\n'
        + listing + '\n<a class="more" href="i/">새콤 해설 전체 보기 ›</a>\n'
        '</section>\n' + END)


def main():
    s = HOME.read_text(encoding='utf-8')
    # Remove any prior injected section before re-adding the latest articles
    s = re.sub(re.escape(START) + r'.*?' + re.escape(END), '', s, flags=re.S)
    if '<!-- ISSUEPIQLE_ORIGINAL_STYLE -->' not in s:
        style = '''<!-- ISSUEPIQLE_ORIGINAL_STYLE -->
<style>
.ip-original-list{list-style:none;margin:12px 0 16px;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.ip-original-item{min-width:0}
.ip-original-item>a{display:flex;flex-direction:column;gap:6px;height:100%;padding:17px;border:1px solid var(--line,#ddd);border-radius:12px;background:var(--card,#fff);color:var(--text,inherit);text-decoration:none}
.ip-original-item strong{font-size:1rem;line-height:1.55;word-break:keep-all}
.ip-original-item time{font-size:.73rem;color:var(--sub,#64748b)}
.ip-original-item span{font-size:.85rem;line-height:1.7;color:var(--sub,#64748b);word-break:keep-all}
.ip-original-empty{padding:1rem;line-height:1.8}
@media(max-width:650px){.ip-original-list{grid-template-columns:1fr}}
</style>'''
        if '</head>' not in s:
            raise ValueError('Missing </head> in site/index.html')
        s = s.replace('</head>', style + '\n</head>', 1)
    if '<footer class="foot">' not in s:
        raise ValueError('Expected site homepage footer not found; no changes written')
    s = s.replace('  <footer class="foot">', build_section() + '\n\n  <footer class="foot">', 1)
    # Explicit canonical prevents splitting root/index.html tracking.
    if 'rel="canonical"' not in s and '</head>' in s:
        s = s.replace('</head>', '<link rel="canonical" href="https://piqlemuu.github.io/issue-piqle/">\n</head>', 1)
    HOME.write_text(s, encoding='utf-8')
    print('Home original editorial section updated:', len(entries()), 'articles')

if __name__ == '__main__':
    main()
