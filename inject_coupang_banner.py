#!/usr/bin/env python3
"""ISSUE PIQLE homepage: 600×100 Coupang carousel + mobile-readable transparent PNG disclosure.

Run after home_editorial.py as configured in .github/workflows/update.yml.
Only touches generated site/index.html and a generated asset in site/assets/system.
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
# Size as displayed in browser: 441×22 CSS px, full-resolution source is 1764×88.
DISCLOSURE = '이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.'

STYLE = f'''{STYLE_START}
<style>
.ip-coupang{{background:var(--bg,#f2f3f6);padding:0 0 6px;margin:0}}
.ip-coupang-inner{{max-width:45rem;margin:0 auto;padding:0 var(--pad,16px)}}
.ip-coupang-scroll{{width:100%;max-width:100%;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain;padding:0;margin:0}}
.ip-coupang-slot{{width:600px;min-width:600px;min-height:100px;line-height:0}}
.ip-coupang-disclosure{{margin:1px 0 0;padding:0;text-align:left;max-width:100%;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch}}
.ip-coupang-disclosure img{{display:block;width:441px;min-width:441px;height:22px;max-width:none;margin:0;border:0;background:transparent}}
@media(max-width:719px){{.ip-coupang-inner{{max-width:none;padding:0}}.ip-coupang-disclosure{{padding:0}}}}
@media(min-width:720px){{.ip-coupang-scroll{{display:flex;justify-content:center}}}}
</style>
{STYLE_END}'''

BANNER = f'''{START}
<section class="ip-coupang" aria-label="쿠팡 파트너스 추천 상품 배너">
  <div class="ip-coupang-inner">
    <div class="ip-coupang-scroll" role="region" aria-label="추천 상품 배너: 모바일에서는 가로 스크롤" tabindex="0">
      <div class="ip-coupang-slot">
        <script src="https://ads-partners.coupang.com/g.js"></script>
        <script>new PartnersCoupang.G({{"id":1051992,"template":"carousel","trackingCode":"AF1144527","width":"600","height":"100","tsource":""}});</script>
      </div>
    </div>
    <div class="ip-coupang-disclosure" role="note" aria-label="{DISCLOSURE}">
      <img src="assets/system/coupang-fee-disclosure.png" width="1764" height="88" alt="{DISCLOSURE}">
    </div>
  </div>
</section>
{END}'''


def replace_marked(doc, start, end, payload):
    pat = re.compile(re.escape(start) + r'.*?' + re.escape(end), re.S)
    return pat.sub(lambda _: payload, doc, count=1) if pat.search(doc) else None


def main():
    if not HOME.is_file():
        raise SystemExit('site/index.html missing; first run collect.py')
    if not SOURCE_PNG.is_file():
        raise SystemExit('assets/coupang-fee-disclosure.png missing; upload the PNG too')
    doc = HOME.read_text(encoding='utf-8')
    if doc.count('</head>') != 1 or doc.count('</header>') != 1:
        raise SystemExit('Expected homepage head/header, refusing to modify')
    current = replace_marked(doc, STYLE_START, STYLE_END, STYLE)
    if current is None:
        # Backward compatibility for original home banner injector (single style marker).
        old = re.compile(r'<!-- ISSUEPIQLE_COUPANG_TOP_STYLE -->\s*<style>.*?</style>', re.S)
        if old.search(doc):
            doc = old.sub(lambda _: STYLE, doc, count=1)
        else:
            doc = doc.replace('</head>', STYLE + '\n</head>', 1)
    else:
        doc = current
    current = replace_marked(doc, START, END, BANNER)
    if current is None:
        doc = doc.replace('</header>', '</header>\n' + BANNER + '\n', 1)
    else:
        doc = current
    if doc.count('new PartnersCoupang.G(') != 1:
        raise SystemExit('Expected exactly one Coupang carousel')
    if doc.count('ip-coupang-disclosure') < 2:
        raise SystemExit('Disclosure missing')
    DEST_PNG.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE_PNG, DEST_PNG)
    HOME.write_text(doc, encoding='utf-8')
    print('ISSUE PIQLE homepage banner updated; transparent PNG disclosure embedded directly below.')


if __name__ == '__main__':
    main()
