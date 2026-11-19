#!/usr/bin/env python3
"""Insert the specified Coupang Partners carousel below ISSUE PIQLE home header.

Runs on generated site/index.html after home_editorial.py. Safe to rerun.
Only the ISSUE PIQLE home is modified; no other pages are touched.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
HOME = ROOT / 'site' / 'index.html'
START = '<!-- ISSUEPIQLE_COUPANG_TOP_START -->'
END = '<!-- ISSUEPIQLE_COUPANG_TOP_END -->'

BANNER = '''<!-- ISSUEPIQLE_COUPANG_TOP_START -->
<section class="ip-coupang" aria-label="쿠팡 파트너스 추천 상품 광고">
  <div class="ip-coupang-inner">
    <div class="ip-coupang-label">광고</div>
    <div class="ip-coupang-scroll" role="region" aria-label="추천 상품 배너, 가로로 스크롤 가능" tabindex="0">
      <div class="ip-coupang-slot">
        <script src="https://ads-partners.coupang.com/g.js"></script>
        <script>
          new PartnersCoupang.G({"id":1051923,"template":"carousel","trackingCode":"AF1144527","width":"680","height":"140","tsource":""});
        </script>
      </div>
    </div>
    <p class="ip-coupang-disclosure">이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</p>
  </div>
</section>
<!-- ISSUEPIQLE_COUPANG_TOP_END -->'''

STYLE = '''<!-- ISSUEPIQLE_COUPANG_TOP_STYLE -->
<style>
.ip-coupang{background:var(--bg,#f2f3f6);padding:10px 0 8px}
.ip-coupang-inner{max-width:45rem;margin:0 auto;padding:0 var(--pad,16px)}
.ip-coupang-label{font-size:11px;line-height:1.5;color:var(--sub,#626873);margin:0 0 5px;font-weight:700}
.ip-coupang-scroll{width:100%;max-width:100%;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain}
.ip-coupang-slot{width:680px;min-width:680px;min-height:140px;line-height:0}
.ip-coupang-disclosure{margin:6px 0 0;color:var(--sub,#626873);font-size:11px;line-height:1.5}
@media(min-width:720px){.ip-coupang-scroll{display:flex;justify-content:center}}
</style>'''


def main():
    if not HOME.is_file():
        raise FileNotFoundError('site/index.html is missing; run collect.py first')
    doc = HOME.read_text(encoding='utf-8')
    # Avoid duplicate ads if the generated home already has our banner.
    if START in doc:
        if END not in doc or doc.count('new PartnersCoupang.G(') != 1:
            raise ValueError('Partial/duplicated Coupang banner: inspect homepage')
        print('ISSUE PIQLE: existing banner kept unchanged.')
        return
    if doc.count('</header>') != 1 or doc.count('</head>') != 1:
        raise ValueError('Expected exactly one </header> and </head> in homepage; aborting')
    if 'class="logo"' not in doc or '<main class="wrap">' not in doc:
        raise ValueError('ISSUE PIQLE logo / main layout not found; aborting')
    doc = doc.replace('</head>', STYLE + '\n</head>', 1)
    doc = doc.replace('</header>', '</header>\n' + BANNER + '\n', 1)
    if doc.count('new PartnersCoupang.G(') != 1:
        raise ValueError('Expected exactly one Coupang banner')
    HOME.write_text(doc, encoding='utf-8')
    print('ISSUE PIQLE: Coupang carousel placed directly below the logo header.')


if __name__ == '__main__':
    main()
