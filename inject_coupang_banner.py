#!/usr/bin/env python3
"""ISSUE PIQLE: one 200x150 Coupang carousel AFTER the top-5/expand rankings.

Generated homepage only: this is run from .github/workflows/update.yml.
Does not change source homepage or other editorial pages.
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
LEGACY_STYLE = '<!-- ISSUEPIQLE_COUPANG_TOP_STYLE -->'
DISCLOSURE = '이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.'

STYLE = f'''{STYLE_START}
<style>
/* Ad has the exact content-column width of the existing ranking cards. */
.ip-coupang{{width:100%;max-width:none;margin:22px 0 27px;padding:0;box-sizing:border-box}}
.ip-coupang-inner{{width:100%;min-width:0;box-sizing:border-box;overflow:hidden;border:1px solid var(--line,#e2e5e9);border-radius:var(--r-card,12px);box-shadow:var(--shadow,none);background:var(--card,#fff);padding:14px 10px 10px}}
.ip-coupang-slot{{width:200px;max-width:100%;height:150px;min-height:150px;line-height:0;margin:0 auto;overflow:hidden}}
.ip-coupang-slot iframe{{max-width:100%;border:0}}
.ip-coupang-disclosure{{margin:8px 0 0;padding:0;text-align:left;line-height:0;overflow:hidden}}
.ip-coupang-disclosure img{{display:block;width:371px;max-width:100%;height:auto;margin:0;border:0;background:transparent}}
@media (max-width:380px){{.ip-coupang-inner{{padding:10px 7px 8px}}.ip-coupang{{margin:18px 0 24px}}}}
</style>
{STYLE_END}'''

BANNER = f'''{START}
<section class="ip-coupang" aria-label="쿠팡 파트너스 광고">
  <div class="ip-coupang-inner">
    <div class="ip-coupang-slot">
      <script src="https://ads-partners.coupang.com/g.js"></script>
      <script>new PartnersCoupang.G({{"id":1052403,"template":"carousel","trackingCode":"AF1144527","width":"200","height":"150","tsource":""}});</script>
    </div>
    <div class="ip-coupang-disclosure" role="note">
      <img src="assets/system/coupang-fee-disclosure.png" width="1484" height="88" alt="{DISCLOSURE}" loading="lazy">
    </div>
  </div>
</section>
{END}'''


def remove_section(doc, start, end):
    marker = re.compile(r'\s*' + re.escape(start) + r'.*?' + re.escape(end) + r'\s*', re.S)
    if (start in doc) != (end in doc):
        raise ValueError('Partially injected ad marker found: refusing to publish')
    return marker.sub('\n', doc)


def main():
    if not HOME.is_file():
        raise FileNotFoundError('Missing site/index.html; run collect.py before this script.')
    if not SOURCE_PNG.is_file():
        raise FileNotFoundError('Missing assets/coupang-fee-disclosure.png; keep existing repo image.')
    doc = HOME.read_text(encoding='utf-8')
    if doc.count('</head>') != 1 or doc.count('<section class="sec" id="sec-top"') != 1:
        raise ValueError('Unexpected ISSUE PIQLE home markup; refusing to edit')
    doc = remove_section(doc, START, END)
    doc = remove_section(doc, STYLE_START, STYLE_END)
    doc = re.sub(r'\s*' + re.escape(LEGACY_STYLE) + r'\s*<style>.*?</style>\s*', '\n', doc, flags=re.S)
    # Put the unit after the entire top ranking section, including the expand button.
    # The next original section starts with this unique marker.
    next_section = '<!-- ④ 분야별 이슈 -->'
    if doc.count(next_section) != 1:
        raise ValueError('Cannot locate boundary after live issue ranking')
    top = doc.index('<section class="sec" id="sec-top"')
    boundary = doc.index(next_section)
    if top >= boundary or '<button class="more" id="top-more"' not in doc[top:boundary]:
        raise ValueError('Live issue ranking structure changed; refusing to insert')
    doc = doc.replace('</head>', STYLE + '\n</head>', 1)
    doc = doc.replace(next_section, BANNER + '\n\n  ' + next_section, 1)
    if doc.count('new PartnersCoupang.G(') != 1:
        raise ValueError('Exactly one Coupang unit expected')
    if not doc.index('id="sec-top"') < doc.index(START) < doc.index('id="sec-cat"'):
        raise ValueError('Ad placement outside intended ranking boundary')
    if '"id":1051992' in doc or '"id":1051923' in doc:
        raise ValueError('Legacy Coupang unit remains; not publishing duplicate ads')
    DEST_PNG.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(SOURCE_PNG,DEST_PNG)
    HOME.write_text(doc,encoding='utf-8')
    print('ISSUE PIQLE: one Coupang 200x150 unit after top 5/expand button and before categories.')

if __name__ == '__main__':
    main()
