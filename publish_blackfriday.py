#!/usr/bin/env python3
"""Post-build publisher for a researched ISSUE PIQLE editorial with in-article ads.
Never changes GitHub source site/ files; run after collect/home_editorial/section_seo.
Idempotent across scheduled rebuilds.
"""
from pathlib import Path
import re
import html

ROOT=Path(__file__).resolve().parent
SITE=ROOT/'site'
ARTICLE=SITE/'i'/'coupang-blackfriday-2026-buy-now-or-wait.html'
URL='https://piqlemuu.github.io/issue-piqle/i/coupang-blackfriday-2026-buy-now-or-wait.html'
TITLE='쿠팡 블랙프라이데이 2026, 지금 살까? 23일 라이브까지 기다릴까'
DESCRIPTION='쿠팡 가전·디지털 블랙프라이데이 11월 16~29일과 23~27일 블프페스타 라이브 차이, 가격 비교 기준, 카드·쿠폰 확인법을 정리했습니다.'

# Both original Coupang partner parameters must remain unchanged.
BANNER='''<aside class="ad-block" aria-label="쿠팡파트너스 광고"><span class="ad-label">AD · 쿠팡파트너스 광고</span><div class="ad-scroll"><div class="ad-fixed"><script src="https://ads-partners.coupang.com/g.js"></script><script>new PartnersCoupang.G({"id":1051923,"template":"carousel","trackingCode":"AF1144527","width":"680","height":"140","tsource":""});</script></div></div><p class="ad-desc">이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</p></aside>'''

STYLE='''
:root{--bg:#f4f5f5;--paper:#fff;--ink:#1f2931;--muted:#6a7581;--line:#e0e4e8;--blue:#2a72a3;--pale:#eef4f7}
*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--bg);font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;line-height:1.84;word-break:keep-all}
a{color:var(--blue)}header{position:sticky;top:0;background:#fffdfdf5;border-bottom:1px solid var(--line);z-index:5}header .inside{max-width:840px;margin:auto;padding:14px 20px;display:flex;align-items:center;justify-content:space-between;gap:14px}.logo{font-size:22px;font-weight:850;letter-spacing:-1px;text-decoration:none;color:var(--ink)}.logo span{color:var(--blue)}.smallnav{font-size:12px;text-decoration:none}main{max-width:840px;margin:0 auto;padding:26px 20px 90px}.crumb{font-size:12px;color:var(--muted);margin-bottom:25px}.eyebrow{font-size:12px;letter-spacing:.12em;font-weight:750;color:var(--blue)}h1{font-size:clamp(29px,5vw,42px);line-height:1.3;letter-spacing:-.045em;margin:10px 0 20px}h2{font-size:clamp(21px,3.5vw,27px);line-height:1.45;letter-spacing:-.035em;margin:42px 0 16px}.deck{font-size:18px;line-height:1.75;color:#52616e;margin:0 0 18px}.meta{font-size:12px;color:var(--muted);border-bottom:1px solid var(--line);padding-bottom:22px;margin-bottom:29px}p,li{font-size:17px;line-height:1.92}p{margin:16px 0}.lede{font-size:19px;line-height:1.9}.lead-strong{font-weight:750}.summary{border-top:3px solid var(--blue);background:var(--pale);padding:19px 22px;margin:30px 0;border-radius:0 0 12px 12px}.summary strong{display:block;font-size:13px;letter-spacing:.08em;color:var(--blue)}.summary ul{padding-left:21px;margin:9px 0 0}.summary li{font-size:15px;margin:5px 0}.note{background:#fff;border:1px solid var(--line);border-radius:14px;padding:17px 19px;margin:23px 0}.note b{font-size:15px}.note p{font-size:15px;margin:8px 0 0}.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:520px;font-size:15px;background:#fff}th,td{padding:14px 13px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}th{background:#e9f1f5;font-size:14px}.check{list-style:none;padding:0}.check li{padding:14px 0 14px 28px;border-bottom:1px solid var(--line);position:relative}.check li:before{content:'✓';position:absolute;left:4px;color:var(--blue);font-weight:900}.ad-block{border:1px solid #d9dfe4;border-radius:14px;background:#fff;margin:42px 0;padding:14px 13px 13px}.ad-label{display:block;color:#6e7e88;font-size:11px;font-weight:700;margin-bottom:9px}.ad-scroll{width:100%;overflow-x:auto;overflow-y:hidden;overscroll-behavior-x:contain}.ad-fixed{width:680px;min-height:140px;max-width:none}.ad-desc{margin:10px 2px 0;color:#76818a;font-size:11px;line-height:1.6}.source{font-size:14px;color:#566675}.source li{font-size:14px}.footer{margin-top:48px;border-top:1px solid var(--line);padding-top:24px;font-size:13px;color:var(--muted)}.cta{display:inline-block;border:1px solid var(--blue);border-radius:8px;padding:10px 17px;color:var(--blue);font-weight:750;text-decoration:none}a:focus-visible{outline:3px solid var(--blue);outline-offset:3px}@media(max-width:580px){main{padding:21px 16px 70px}h1{font-size:31px}p,li{font-size:16px}.deck{font-size:17px}.lede{font-size:17px}.summary{padding:16px}.ad-block{margin:35px 0;padding:10px}}
'''

def article():
    return f'''<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{html.escape(TITLE)} | 이슈피클 새콤해설</title>
<meta name="description" content="{html.escape(DESCRIPTION,quote=True)}">
<link rel="canonical" href="{URL}">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:type" content="article"><meta property="og:site_name" content="이슈피클"><meta property="og:title" content="{html.escape(TITLE)}"><meta property="og:description" content="{html.escape(DESCRIPTION,quote=True)}"><meta property="og:url" content="{URL}">
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"Article","headline":"{TITLE}","description":"{DESCRIPTION}","datePublished":"2026-11-19","dateModified":"2026-11-19","inLanguage":"ko-KR","author":{{"@type":"Organization","name":"이슈피클"}},"publisher":{{"@type":"Organization","name":"이슈피클"}},"mainEntityOfPage":"{URL}","isAccessibleForFree":true}}</script>
<style>{STYLE}</style></head><body>
<header><div class="inside"><a class="logo" href="../index.html">이슈<span>피클</span></a><a class="smallnav" href="index.html">새콤해설 전체</a></div></header>
<main><nav class="crumb" aria-label="위치"><a href="../index.html">홈</a> / <a href="index.html">새콤해설</a> / 소비·쇼핑</nav>
<div class="eyebrow">SAEKOM EXPLAIN · 소비를 읽는 법</div>
<h1>블랙프라이데이, 지금 사면 손해일 수도 있어요</h1>
<p class="deck">쿠팡 가전·디지털 블프가 시작됐습니다. 그런데 23일부터 라이브 추가 혜택도 예정돼 있다면, 오늘 보이는 가격이 가장 싼 가격일까요?</p>
<div class="meta">이슈피클 에디터 · 2026.11.19 · 기준: 쿠팡 11월 15일 발표 · 광고 포함</div>
<p class="lede">블랙프라이데이만 되면 사람은 둘로 나뉩니다. 원래 필요했던 걸 싸게 사는 사람. 그리고 <strong>할인이라서 필요해진 물건을 사는 사람.</strong> 문제는 구매 버튼 앞에서 둘이 꽤 비슷해 보인다는 겁니다.</p>
<p>쿠팡은 올해 11월 16일부터 가전·디지털 블랙프라이데이를 진행한다고 발표했습니다. 23일부터 27일까지는 별도의 ‘블프페스타 라이브’도 예정돼 있고요. 그렇다면 지금 바로 결제하는 게 맞을까요? 답은 단순합니다. <strong class="lead-strong">가격 하나보다 구매 조건 세 가지를 먼저 확인해야 합니다.</strong></p>
<div class="summary"><strong>30초 요약</strong><ul><li>가전·디지털 블프: 쿠팡 보도자료 본문 기준 11월 16~29일</li><li>블프페스타 라이브: 11월 23~27일, 일부 브랜드의 추가 혜택 예정</li><li>지금 가격과 라이브 가격 중 어느 쪽이 낮을지는 상품별로 다릅니다</li><li>최종 결제금액·카드/쿠폰 조건·재고를 함께 확인하세요</li></ul></div>
<section><h2>할인 시작일과 '가장 싸지는 날'은 다릅니다</h2>
<p>쿠팡이 발표한 가전·디지털 블랙프라이데이에는 국내외 가전·디지털 브랜드가 참여합니다. 11월 23~27일에는 LG전자·인텔·샤오미·바디프랜드 등이 참여하는 라이브 방송을 통해 추가 할인과 경품 추첨이 예정돼 있습니다.</p>
<p>여기서 중요한 단어는 <strong>‘추가’</strong>입니다. 라이브 혜택이 있다는 사실이 모든 상품의 가격이 그때 더 낮아진다는 뜻은 아닙니다. 참여 브랜드, 적용 상품, 재고, 할인 수단이 달라질 수 있으니까요.</p>
<div class="note"><b>기간 표기 주의</b><p>쿠팡 공식 보도자료 본문에는 행사 기간이 11월 16~29일로 안내되지만 일부 홍보 이미지에는 11월 30일까지로 표시됩니다. 종료일이 다른 만큼 구매 시점에는 쿠팡 행사 페이지에서 적용 기간을 다시 확인해야 합니다.</p></div>
</section>
{BANNER}
<section><h2>지금 살까, 라이브를 기다릴까?</h2>
<div class="table-scroll"><table><thead><tr><th>상황</th><th>판단 기준</th></tr></thead><tbody>
<tr><td>지금 필요한 제품</td><td>현재 결제금액·배송일·재고가 납득된다면 구매를 고려할 수 있습니다.</td></tr>
<tr><td>급하지 않은 고가 제품</td><td>11월 23~27일 관련 브랜드 라이브 편성 여부를 확인한 뒤 비교해도 됩니다.</td></tr>
<tr><td>카드·쿠폰 혜택이 있는 제품</td><td>표시 할인율이 아니라 내가 실제 적용받는 결제금액으로 비교하세요.</td></tr>
<tr><td>모델명이 비슷한 제품</td><td>정확한 모델 코드·연식·구성품·용량이 같은지 먼저 확인하세요.</td></tr>
</tbody></table></div>
<p>예를 들어 같은 청소기처럼 보여도 구성품과 배터리 개수가 다르면 가격 비교 자체가 틀어집니다. “50% 할인”이라고 써 있어도 기준 가격이 무엇이었는지, 다른 판매처의 동일 모델 가격은 얼마인지 확인해야 합니다.</p>
</section>
<section><h2>결제하기 전에 이 다섯 가지만</h2><ul class="check">
<li><strong>정확한 모델명</strong> — 제품 뒤에 붙은 영문·숫자까지 같은 제품인가?</li>
<li><strong>실제 결제금액</strong> — 카드, 쿠폰, 멤버십 조건을 내가 적용받을 수 있나?</li>
<li><strong>구성 차이</strong> — 색상, 용량, 부속품, 설치비까지 동일한가?</li>
<li><strong>기간과 재고</strong> — 오늘 가격이 언제까지 적용되며 품절 가능성은 어떤가?</li>
<li><strong>반품·A/S</strong> — 판매자, 설치 상품의 회수 비용, 보증 조건은 어떤가?</li>
</ul>
<p>가격 기록도 유용합니다. 오늘 확인한 모델명과 결제금액을 캡처해 두면 라이브 방송 당일 달라진 조건을 비교하기가 쉬워집니다. 단, 아직 발표되지 않은 라이브 특가나 최저가를 미리 확정할 수는 없습니다.</p></section>
{BANNER}
<section><h2>다시 돌아와서, 진짜 싼 건 무엇일까</h2>
<p>할인율이 70%인 충동구매보다, 한 달 전부터 살 예정이던 물건을 10% 싸게 사는 편이 더 낫기도 합니다. 물론 꼭 필요한 물건이라면 할인 종료를 기다리는 사이 배송일이 늦어질 수도 있겠죠.</p>
<p>블랙프라이데이의 핵심은 '무조건 오늘 사라'도 '무조건 23일까지 기다려라'도 아닙니다. <strong>이미 필요한 물건인지, 같은 모델인지, 내게 적용되는 최종 가격이 얼마인지.</strong> 이 세 가지를 확인했다면 적어도 할인 문구에 끌려가기보다 스스로 선택할 수 있습니다.</p>
<p>이번 주말 쇼핑 목록을 만들었다면 상품명 옆에 금액 하나만 더 적어두세요. <strong>‘할인가’가 아니라 ‘내 결제 예상가’.</strong> 생각보다 그 차이가 큽니다.</p>
</section>
<section class="note"><b>확인한 자료</b><ol class="source"><li><a href="https://news.coupang.com/archives/68557/" rel="noopener noreferrer" target="_blank">쿠팡 뉴스룸, 가전·디지털 블랙프라이데이 보도자료 (2026.11.15)</a></li><li><a href="https://www.yna.co.kr/view/AKR20261115021500030" rel="noopener noreferrer" target="_blank">연합뉴스, 쿠팡 행사 및 라이브 일정 보도 (2026.11.15)</a></li></ol><p>가격·재고·경품 당첨 조건은 상품과 행사마다 달라질 수 있습니다. 특정 상품의 실시간 최저가나 구매 수익을 보장하지 않습니다.</p></section>
<p><a class="cta" href="index.html">새콤해설 더 읽기</a></p>
<div class="footer">© 이슈피클 ISSUE PIQLE · 편집 해설 · 2026.11.19 작성. 광고·제휴 콘텐츠는 표시된 영역에서 구분합니다.</div>
</main></body></html>'''

MARK='<!-- ISSUEPIQLE_BLACKFRIDAY_2026 -->'

def insert_teasers():
    index=SITE/'i'/'index.html'
    if not index.is_file():raise FileNotFoundError('site/i/index.html is missing')
    src=index.read_text(encoding='utf-8')
    teaser=f'''{MARK}<div class="ip-bf-feature" style="border:1px solid var(--line,#ddd);border-radius:14px;padding:16px;margin:18px 0;background:var(--card,#fff)"><span style="display:block;font-size:12px;color:var(--sub,#777)">NEW · 2026.11.19 · 소비·쇼핑</span><a style="font-weight:800;font-size:19px;line-height:1.5;display:block;margin:6px 0" href="coupang-blackfriday-2026-buy-now-or-wait.html">블랙프라이데이, 지금 사면 손해일 수도 있어요</a><p style="font-size:14px;color:var(--sub,#777);margin:0">11월 23일 라이브 추가 혜택, 오늘 결제해도 괜찮을까? 확인할 조건 다섯 가지.</p></div>'''
    if MARK not in src:
        # Prefer top of editorial list, immediately after its intro; no fragile source replacements.
        marker='<div class="sk-tabs">'
        tabs=re.search(r'<div class="sk-tabs">.*?</div>',src,re.S)
        if tabs:src=src[:tabs.end()]+'\n'+teaser+src[tabs.end():]
        elif marker in src:src=src.replace(marker,teaser+'\n'+marker,1)
        elif '<main class="wrap ex">' in src:src=src.replace('<main class="wrap ex">','<main class="wrap ex">'+teaser,1)
        else:raise ValueError('Could not find editorial index main container')
    index.write_text(src,encoding='utf-8')
    home=SITE/'index.html'
    if home.exists():
        src=home.read_text(encoding='utf-8')
        if MARK not in src:
            card=f'''{MARK}<section class="sec" style="padding:14px 0 22px"><a href="i/coupang-blackfriday-2026-buy-now-or-wait.html" style="display:block;background:var(--card,#fff);border:1px solid var(--line,#ddd);padding:17px;border-radius:13px;text-decoration:none;color:inherit"><small style="color:var(--sub,#888)">NEW · 새콤해설 · 2026.11.19</small><strong style="display:block;font-size:18px;margin:5px 0">블랙프라이데이, 지금 사면 손해일 수도 있어요</strong><span style="color:var(--sub,#888);font-size:14px">쿠팡 가전·디지털 블프, 라이브 기다릴지 지금 살지 비교하기 ›</span></a></section>'''
            if '<!-- ISSUEPIQLE_ORIGINAL_START -->' in src:src=src.replace('<!-- ISSUEPIQLE_ORIGINAL_START -->',card+'\n<!-- ISSUEPIQLE_ORIGINAL_START -->',1)
            elif '<footer class="foot">' in src:src=src.replace('<footer class="foot">',card+'\n<footer class="foot">',1)
            else:raise ValueError('Homepage footer anchor missing')
        home.write_text(src,encoding='utf-8')

def insert_sitemap():
    sitemap=SITE/'sitemap.xml'
    if not sitemap.exists():return
    s=sitemap.read_text(encoding='utf-8')
    if URL not in s and '</urlset>' in s:
        s=s.replace('</urlset>',f'  <url><loc>{URL}</loc></url>\n</urlset>',1)
        sitemap.write_text(s,encoding='utf-8')

def main():
    ARTICLE.parent.mkdir(parents=True,exist_ok=True)
    text=article()
    if text.count('new PartnersCoupang.G(')!=2:raise ValueError('Missing Coupang dynamic banners')
    ARTICLE.write_text(text,encoding='utf-8')
    insert_teasers()
    insert_sitemap()
    print('ISSUE PIQLE published:',ARTICLE.relative_to(ROOT),'| Coupang banners: 2')

if __name__=='__main__':main()
