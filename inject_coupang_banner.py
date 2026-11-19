#!/usr/bin/env python3
"""ISSUE PIQLE homepage: native Coupang carousel between briefing and issue ranking.

No decorative '파트너스 추천' heading or '(광고)' above the banner.
Keeps a one-line transparent PNG affiliate disclosure directly below it.
Patches only the generated site/index.html; leaves GitHub source homepage unchanged.
Run by existing .github/workflows/update.yml after home_editorial.py.
"""
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent
HOME = ROOT / 'site' / 'index.html'
SOURCE_PNG = ROOT / 'assets' / 'coupang-fee-disclosure.png'
DEST_PNG = ROOT / 'site' / 'assets' / 'system' / 'coupang-fee-disclosure.png'
START = '<!-- ISSUEPIQLE_COUPANG_TOP_START -->'
END = '<!-- ISSUEPIQLE_COUPANG_TOP_END -->'
STYLE_START = '<!-- ISSUEPIQLE_COUPANG_TOP_STYLE_START -->'
STYLE_END = '<!-- ISSUEPIQLE_COUPANG_TOP_STYLE_END -->'
OLD_STYLE_START = '<!-- ISSUEPIQLE_COUPANG_TOP_STYLE -->'
DISCLOSURE = '이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.'

STYLE = f'''{STYLE_START}
<style>
/* Quiet editorial placement: after the live briefing, just before issue ranking */
.ip-coupang{{max-width:45rem;margin:18px auto 26px;padding:0 var(--pad,16px);background:transparent}}
.ip-coupang-inner{{border:1px solid var(--line,#e2e5e9);border-radius:15px;background:var(--card,#fff);overflow:hidden;padding:8px 0 7px}}
.ip-coupang-scroll{{max-width:100%;width:100%;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain;scrollbar-width:none;margin:0;padding:0}}
.ip-coupang-scroll::-webkit-scrollbar{{display:none}}
.ip-coupang-slot{{min-width:600px;width:600px;min-height:100px;height:100px;line-height:0}}
.ip-coupang-disclosure{{overflow:hidden;text-align:left;padding:1px 8px 0;margin:0;line-height:0}}
.ip-coupang-disclosure img{{display:block;width:371px;min-width:371px;height:22px;max-width:none;border:0;background:transparent;margin:0}}
@media (min-width:720px){{.ip-coupang-scroll{{display:flex;justify-content:center}}}}
@media (max-width:719px){{.ip-coupang{{margin:14px auto 23px;padding:0 var(--pad,16px)}}.ip-coupang-inner{{padding-top:5px}}}}
</style>
{STYLE_END}'''

BANNER = f'''{START}
<section class="ip-coupang" aria-label="쿠팡 파트너스 광고">
  <div class="ip-coupang-inner">
    <div class="ip-coupang-scroll" role="region" aria-label="상품 광고 배너, 좌우 스크롤 가능" tabindex="0">
      <div class="ip-coupang-slot">
        <script src="https://ads-partners.coupang.com/g.js"></script>
        <script>new PartnersCoupang.G({{"id":1051992,"template":"carousel","trackingCode":"AF1144527","width":"600","height":"100","tsource":""}});</script>
      </div>
    </div>
    <div class="ip-coupang-disclosure" role="note">
      <img src="assets/system/coupang-fee-disclosure.png" width="1484" height="88" alt="{DISCLOSURE}" loading="eager">
    </div>
  </div>
</section>
{END}'''


def drop_marked(doc, start, end):
    pattern = re.compile(r'\s*' + re.escape(start) + r'.*?' + re.escape(end) + r'\s*', re.S)
    return pattern.sub('\n', doc)


def main():
    if not HOME.is_file() or not SOURCE_PNG.is_file():
        raise SystemExit('Missing site/index.html or assets/coupang-fee-disclosure.png')
    doc = HOME.read_text(encoding='utf-8')
    if doc.count('</head>') != 1 or doc.count('</header>') != 1:
        raise SystemExit('Unexpected homepage structure; safe abort')
    if 'id="sec-top"' not in doc or '<main class="wrap">' not in doc:
        raise SystemExit('Cannot locate live issue ranking; safe abort')

    # Existing source / previously generated page may already contain the old banner.
    doc = drop_marked(doc, START, END)
    doc = drop_marked(doc, STYLE_START, STYLE_END)
    doc = re.sub(r'\s*' + re.escape(OLD_STYLE_START) + r'\s*<style>.*?</style>\s*', '\n', doc, flags=re.S)

    doc = doc.replace('</head>', STYLE + '\n</head>', 1)
    # Insert only after the existing briefing and SEO utility line, before live rankings.
    mark = re.search(r'(?P<prefix>\s*)(?P<section><section\s+class="sec"\s+id="sec-top")', doc)
    if not mark:
        raise SystemExit('Live issue ranking anchor changed; safe abort')
    doc = doc[:mark.start()] + '\n' + BANNER + '\n' + doc[mark.start():]

    if doc.count('new PartnersCoupang.G(') != 1 or doc.count(START) != 1:
        raise SystemExit('Duplicated ad code; safe abort')
    if '파트너스 추천' in BANNER:
        raise SystemExit('Unexpected decorative label')
    if not doc.index('</header>') < doc.index(START) < doc.index('id="sec-top"'):
        raise SystemExit('Banner placement invalid')

    DEST_PNG.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE_PNG, DEST_PNG)
    HOME.write_text(doc, encoding='utf-8')
    print('ISSUE PIQLE: quiet ad block without decorative title, before issue rankings; PNG disclosure kept.')


if __name__ == '__main__':
    main()
