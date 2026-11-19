#!/usr/bin/env python3
"""Insert/update the ISSUE PIQLE Coupang Partners banner directly below the home logo header.

- Places the banner immediately below </header> in site/index.html
- Uses Coupang carousel 600x100 (id 1051992)
- No visible '(광고)' label above the banner
- Mobile: zero horizontal padding around the dynamic banner area
- Adds a one-line disclosure as an image, left-aligned and tight under the ad
- Safe to rerun (replaces prior injected block/style)
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
HOME = ROOT / 'site' / 'index.html'
ASSET_DIR = ROOT / 'site' / 'assets' / 'system'
DISCLOSURE_FILE = ASSET_DIR / 'coupang-fee-disclosure.svg'

BANNER_START = '<!-- ISSUEPIQLE_COUPANG_TOP_START -->'
BANNER_END = '<!-- ISSUEPIQLE_COUPANG_TOP_END -->'
STYLE_START = '<!-- ISSUEPIQLE_COUPANG_TOP_STYLE_START -->'
STYLE_END = '<!-- ISSUEPIQLE_COUPANG_TOP_STYLE_END -->'

DISCLOSURE_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="920" height="24" viewBox="0 0 920 24" role="img" aria-labelledby="t">
  <title id="t">이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</title>
  <rect width="920" height="24" fill="white"/>
  <text x="0" y="16" font-family="-apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', Arial, sans-serif" font-size="12" fill="#6b7280">이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</text>
</svg>
'''

STYLE = f'''{STYLE_START}
<style>
.ip-coupang{{background:var(--bg,#f2f3f6);padding:0 0 8px;margin:0}}
.ip-coupang-inner{{max-width:45rem;margin:0 auto;padding:0 var(--pad,16px)}}
.ip-coupang-scroll{{width:100%;max-width:100%;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain;margin:0;padding:0}}
.ip-coupang-scroll::-webkit-scrollbar{{display:none}}
.ip-coupang-slot{{width:600px;min-width:600px;min-height:100px;line-height:0;margin:0}}
.ip-coupang-slot iframe,.ip-coupang-slot ins,.ip-coupang-slot div{{max-width:none}}
.ip-coupang-disclosure{{margin:2px 0 0;line-height:0;text-align:left}}
.ip-coupang-disclosure img{{display:block;width:auto;max-width:100%;height:16px;margin:0}}
@media (max-width: 719px){{
  .ip-coupang-inner{{max-width:none;padding:0}}
  .ip-coupang-scroll{{padding:0;margin:0}}
  .ip-coupang-disclosure{{padding:0 0 0 0}}
}}
@media (min-width: 720px){{
  .ip-coupang-scroll{{display:flex;justify-content:center}}
}}
</style>
{STYLE_END}'''

BANNER = f'''{BANNER_START}
<section class="ip-coupang" aria-label="쿠팡 파트너스 추천 상품 광고">
  <div class="ip-coupang-inner">
    <div class="ip-coupang-scroll" role="region" aria-label="추천 상품 배너, 가로로 스크롤 가능" tabindex="0">
      <div class="ip-coupang-slot">
        <script src="https://ads-partners.coupang.com/g.js"></script>
        <script>
          new PartnersCoupang.G({{"id":1051992,"template":"carousel","trackingCode":"AF1144527","width":"600","height":"100","tsource":""}});
        </script>
      </div>
    </div>
    <div class="ip-coupang-disclosure">
      <img src="assets/system/coupang-fee-disclosure.svg" alt="이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다." width="920" height="24" />
    </div>
  </div>
</section>
{BANNER_END}'''


def replace_between(doc: str, start: str, end: str, replacement: str) -> str:
    pattern = re.compile(re.escape(start) + r'.*?' + re.escape(end), re.S)
    if pattern.search(doc):
        return pattern.sub(replacement, doc, count=1)
    return doc


def main():
    if not HOME.is_file():
        raise FileNotFoundError('site/index.html is missing; run collect.py first')
    doc = HOME.read_text(encoding='utf-8')

    if doc.count('</header>') != 1 or doc.count('</head>') != 1:
        raise ValueError('Expected exactly one </header> and </head> in homepage; aborting')

    # remove/replace previously injected style and banner if present
    if STYLE_START in doc and STYLE_END in doc:
        doc = replace_between(doc, STYLE_START, STYLE_END, STYLE)
    else:
        doc = doc.replace('</head>', STYLE + '\n</head>', 1)

    if BANNER_START in doc and BANNER_END in doc:
        doc = replace_between(doc, BANNER_START, BANNER_END, BANNER)
    else:
        doc = doc.replace('</header>', '</header>\n' + BANNER + '\n', 1)

    # Avoid accidental visible ad labels above banner from previous variants
    doc = doc.replace('<div class="ip-coupang-label">광고</div>', '')
    doc = doc.replace('<div class="ip-coupang-label">(광고)</div>', '')

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    DISCLOSURE_FILE.write_text(DISCLOSURE_SVG, encoding='utf-8')
    HOME.write_text(doc, encoding='utf-8')
    print('ISSUE PIQLE: updated Coupang banner to 600x100 and left-aligned image disclosure directly below it.')


if __name__ == '__main__':
    main()
