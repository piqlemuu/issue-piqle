#!/usr/bin/env python3
"""Post-build SEO improvements for ISSUE PIQLE calendar & Saekom index.

Executed AFTER collect.py and home_editorial.py. This file changes only generated
HTML under site/m/ and site/i/index.html. No source data or calendar dates altered.
"""
from __future__ import annotations
import html
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / 'site'
BASE = 'https://piqlemuu.github.io/issue-piqle/'
START = '<!-- PIQLE_SECTION_SEO_BEGIN -->'
END = '<!-- PIQLE_SECTION_SEO_END -->'


def plain(s):
    return ' '.join(html.unescape(re.sub(r'<[^>]*>', '', s)).split())


def meta_escape(s):
    return html.escape(s, quote=True)


def update_meta(markup, *, title, description, canonical, og_title):
    markup = re.sub(r'<title>.*?</title>', '<title>' + html.escape(title) + '</title>', markup, count=1, flags=re.S)
    if '<meta name="description"' in markup:
        markup = re.sub(r'<meta name="description"\s+content="[^"]*"\s*/?>',
                        '<meta name="description" content="' + meta_escape(description) + '">', markup, count=1)
    else:
        markup = markup.replace('</head>', '<meta name="description" content="' + meta_escape(description) + '">\n</head>', 1)
    markup = re.sub(r'<link rel="canonical"\s+href="[^"]*"\s*/?>', '', markup)
    markup = markup.replace('</head>', '<link rel="canonical" href="' + meta_escape(canonical) + '">\n</head>', 1)
    for prop, content in [('og:title', og_title), ('og:description', description), ('og:url', canonical)]:
        rx = r'<meta property="' + re.escape(prop) + r'"\s+content="[^"]*"\s*/?>'
        tag = '<meta property="' + prop + '" content="' + meta_escape(content) + '">'
        if re.search(rx, markup):
            markup = re.sub(rx, lambda m: tag, markup, count=1)
        else:
            markup = markup.replace('</head>', tag + '\n</head>', 1)
    return markup


def replace_block(markup, new_block, before):
    markup = re.sub(re.escape(START) + r'.*?' + re.escape(END), '', markup, flags=re.S)
    if before not in markup:
        raise ValueError('Insertion anchor absent: ' + before[:65])
    return markup.replace(before, new_block + '\n' + before, 1)


def insert_schema(markup, data):
    # Add as a separate JSON-LD block rather than replacing the source schema.
    content = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    tag = '<!-- PIQLE_SECTION_SCHEMA_BEGIN --><script type="application/ld+json">' + content + '</script><!-- PIQLE_SECTION_SCHEMA_END -->'
    markup = re.sub(r'<!-- PIQLE_SECTION_SCHEMA_BEGIN -->.*?<!-- PIQLE_SECTION_SCHEMA_END -->', '', markup, flags=re.S)
    return markup.replace('</head>', tag + '\n</head>', 1)


def month_page(path):
    month = path.stem
    if not re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])', month):
        return False
    source = path.read_text(encoding='utf-8')
    # Only optimize calendar HTML generated from actual dates/items; no fake events.
    calendar_items = re.findall(r'<li\s+id="[^"]+"[^>]*>.*?</li>', source, re.S)
    if not calendar_items:
        print('[skip] no actual calendar items:', path)
        return False
    count = len(calendar_items)
    yr, mo = month.split('-')
    url = BASE + 'm/' + month + '.html'
    title = f'{yr}년 {int(mo)}월 주요 일정·생활 제도 변경 | 날짜별 정리 - 이슈피클'
    description = (f'{yr}년 {int(mo)}월 주요 일정 {count}건을 날짜별로 확인하세요. '
                   '시행일, 신청 대상, 행사 조건과 원문 출처를 확인할 수 있습니다. 내용은 발표·변경에 따라 달라질 수 있습니다.')
    source = re.sub(re.escape(START) + r'.*?' + re.escape(END), '', source, flags=re.S)
    source = update_meta(source, title=title, description=description, canonical=url, og_title=title)
    # H1 is meaningful and visible, preserving existing content.
    source = re.sub(r'<h1>\d{4}년\s+\d{1,2}월 달라지는 것 총정리</h1>',
                    f'<h1>{yr}년 {int(mo)}월 주요 일정과 달라지는 생활 제도</h1>', source, count=1)
    # Source generator may place next/prev links. Preserve them.
    guide = (START + '\n<section class="ip-seo-guide" aria-label="이달 일정 확인 방법" '
             'style="margin:1rem 0;padding:1rem;border:1px solid var(--line);border-radius:12px;line-height:1.7">'
             f'<h2 style="font-size:1rem;margin:0 0 .4rem">{yr}년 {int(mo)}월 일정 확인 방법</h2>'
             '<p>아래 일정은 시행일이나 행사 날짜순으로 정리했습니다. '
             '대상·신청 기간·혜택 내용은 일정마다 다르므로 항목별 안내와 원문 링크를 확인하세요. '
             '월 단위로만 발표된 일정은 정확한 날짜가 아직 확정되지 않았을 수 있습니다.</p>'
             '<p style="margin:.6rem 0 0"><a href="index.html">다른 달 일정 보기</a> · '
             '<a href="../i/">새콤해설 읽기</a></p></section>\n' + END)
    # Insert before the actual calendar box; avoid changing contents.
    marker = '<div class="box" style="margin-top:.875rem"><ul class="cal">'
    if marker not in source:
        print('[skip] unrecognized calendar structure:', path)
        return False
    source = source.replace(marker, guide + '\n' + marker, 1)
    # Existing build_months generates Article/ItemList, we do not fabricate an Event.
    path.write_text(source, encoding='utf-8')
    print('[month]',month,count)
    return True


def month_index(path):
    source = path.read_text(encoding='utf-8')
    item_re = re.compile(r'<li><a\s+href="(20\d\d-(?:0[1-9]|1[0-2])\.html)"[^>]*>.*?<span class="tt">(.*?)</span>.*?</li>', re.S)
    items = item_re.findall(source)
    url = BASE + 'm/'
    title = '월별 주요 일정·생활 제도 변경 총정리 | 2026년 이후 - 이슈피클'
    description = '월별 주요 일정과 달라지는 생활 제도를 모아 확인하세요. 월별 페이지에서 시행일, 대상, 신청 조건 및 원문 출처를 확인할 수 있습니다.'
    source = re.sub(re.escape(START) + r'.*?' + re.escape(END), '', source, flags=re.S)
    source = update_meta(source, title=title, description=description, canonical=url, og_title=title)
    source = source.replace('<h1>월별 달라지는 것</h1>', '<h1>월별 주요 일정과 달라지는 생활 제도</h1>', 1)
    text = (START + '\n<section class="ip-seo-guide" aria-label="월별 일정 안내" '
            'style="margin:.9rem 0 1rem;line-height:1.75">'
            '<p>매달 새롭게 시행되는 생활 제도, 신청·지원 일정과 주요 변화를 날짜별로 정리합니다. '
            '궁금한 달을 선택하면 일정별 대상과 조건, 확인 가능한 원문 출처를 볼 수 있습니다.</p>'
            '<p>일정은 새로운 발표나 변경에 따라 업데이트될 수 있습니다. '
            '개별 혜택은 신청 전 공식 안내를 확인하세요.</p></section>\n' + END)
    anchor = '<div class="box" style="margin-top:.75rem"><ul class="nlist">'
    if anchor not in source:
        raise ValueError('Month index list missing')
    source = source.replace(anchor, text + '\n' + anchor, 1)
    schema_items = [{'@type':'ListItem','position':i+1, 'name':plain(name), 'url':BASE+'m/'+namefile}
                    for i,(namefile,name) in enumerate(items)]
    source = insert_schema(source, {'@context':'https://schema.org','@type':'ItemList',
                                    'name':'월별 주요 일정 모음','itemListElement':schema_items})
    path.write_text(source,encoding='utf-8')
    print('[months index]',len(items))


def editorial_index(path):
    source = path.read_text(encoding='utf-8')
    url = BASE + 'i/'
    title = '왜떴어? | 이름은 봤는데 무슨 일인지 모를 때 - 이슈피클 해설'
    description = '검색어에 뜬 그 이슈, 무슨 일인지 1분 만에. 생활 이슈는 지금 할 일까지, 연예·스포츠·사회 화제는 왜 떴는지까지 새콤기자가 근거 기사로 정리해요.'
    source = re.sub(re.escape(START) + r'.*?' + re.escape(END), '', source, flags=re.S)
    source = update_meta(source, title=title, description=description, canonical=url, og_title=title)
    anchor = '<div class="sk-tabs">'
    if anchor not in source:
        raise ValueError('Saekom tabs missing: generated layout changed')
    block = (START + '\n<div class="ip-editorial-seo" style="margin:.65rem 0 1rem;line-height:1.7">'
             '<p>새콤해설은 실시간 순위와 별개로, 이슈의 배경과 핵심 쟁점을 직접 정리한 글입니다. '
             '각 글에서 사건의 개요와 관련 출처를 확인할 수 있습니다.</p>'
             '<p style="margin:.35rem 0 0;font-size:.85rem;color:var(--sub)">'
             '관심 있는 주제를 선택하거나 최신 글부터 살펴보세요.</p></div>\n' + END)
    if '<!-- WT_LAYOUT -->' not in source:
        source = source.replace(anchor, block + '\n' + anchor, 1)
    # Only include cards with a title/link and actual HTML file.
    cards=[]; seen=set()
    for m in re.finditer(r'<a\b[^>]*class="[^"]*\bsk-(?:feat|row)\b[^"]*"[^>]*>.*?</a>',source,re.S):
        card=m.group(0)
        href=re.search(r'\bhref="([^"]+)"',card.split('>',1)[0])
        heading=re.search(r'<h[23][^>]*>(.*?)</h[23]>',card,re.S)
        if not href or not heading: continue
        value=html.unescape(href.group(1))
        if not re.fullmatch(r'[\w가-힣.%\-]+\.html',value) or value in seen: continue
        if not (path.parent / value).exists():continue
        seen.add(value)
        cards.append({'@type':'ListItem','position':len(cards)+1,
                      'name':plain(heading.group(1)), 'url':url+value})
        if len(cards)>=50: break
    # Current generator already outputs CollectionPage; ItemList adds real linked articles.
    source = insert_schema(source,{'@context':'https://schema.org','@type':'ItemList',
                                   'name':'왜떴어? 최신 해설','itemListElement':cards})
    path.write_text(source,encoding='utf-8')
    print('[editorial index]',len(cards))


def main():
    m = SITE/'m'
    if not (m/'index.html').exists():
        raise FileNotFoundError('No generated calendar pages: run collect.py first')
    month_index(m/'index.html')
    for page in sorted(m.glob('20??-??.html')):
        month_page(page)
    i = SITE/'i'/'index.html'
    if not i.exists():
        raise FileNotFoundError('No Saekom index: run collect.py first')
    editorial_index(i)


if __name__=='__main__': main()
