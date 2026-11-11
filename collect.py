#!/usr/bin/env python3
"""
이슈 수집기
-----------
GitHub Actions 가 30분마다 이 파일을 실행해서 site/data.json 을 만듭니다.

  - 뉴스:        구글 뉴스 RSS (무료, 키 필요 없음)
  - 검색 급상승: 구글 트렌드 RSS (무료, 키 필요 없음)
  - 유튜브:      YouTube Data API (무료, API 키 필요 → README 5단계)
  - 박스오피스:  영화진흥위원회 오픈API (무료, 키 필요 → README 6단계)
  - 넷플릭스:    넷플릭스 공식 주간 TOP 10 (무료, 키 필요 없음)

직접 실행해 보려면:  python collect.py
"""
import base64
import html as htmllib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

# ═════════════ 설정 (여기만 바꿔도 됩니다) ═════════════
TOP_N = 20            # '지금 뜨는 이슈' 개수
CAT_N = 20            # 분야별 이슈 개수
PEOPLE_N = 10         # 이슈人 개수
RISING_N = 5          # 치고 올라오는 이슈 개수
RISING_MIN_RATIO = 1.5  # 최근 3시간 기사가 그 전 3시간보다 이만큼 이상 늘어야 '급부상' (새로 등장한 이슈는 통과)
RISING_SKIP_TOP = 5   # 실시간 순위 이 순위 안에 이미 있는 이슈는 급부상에서 빼요 (0 = 빼지 않음)
RISING_PER_CAT = 2    # 분야마다 최대 몇 개까지 (먼저 분야마다 1개씩, 남으면 2개째)
NEWS_PER_ISSUE = 5    # 첫 화면에서 이슈마다 보여줄 관련 기사 수
MAX_AGE_HOURS = 24    # 이 시간보다 오래된 기사는 버림
RISING_HOURS = 2      # '최근' 으로 볼 시간 (치고 올라오는 이슈)

G = "https://news.google.com/rss"
Q = "hl=ko&gl=KR&ceid=KR:ko"
def topic(name): return f"{G}/headlines/section/topic/{name}?{Q}"
def search(word): return f"{G}/search?q={urllib.parse.quote(word)}+when:1d&{Q}"

GENERAL_FEEDS = [f"{G}?{Q}"]   # 분야 없이 전체 주요 뉴스

# 분야 추가·삭제는 여기서. (화면에는 자동으로 반영돼요)
QUERY_WORDS = set()   # 분야를 찾으려고 넣은 검색어는 이슈 키워드에서 빼요 (안 그러면 '할인'·'카페'가 1위가 돼요)
def find(*words):
    QUERY_WORDS.update(w for w in words if " " not in w)
    return search(" OR ".join(words))

CATEGORIES = {
    "ent":    {"name": "연예",      "feeds": [topic("ENTERTAINMENT"), search("연예")]},
    "spo":    {"name": "스포츠",    "feeds": [topic("SPORTS")]},
    # 생활·경제: 국민이 꼭 알아야 할 돈·생활 뉴스 (물가·요금 인상·금리·세금·해킹·사기·리콜 등)
    "life":   {"name": "생활·경제", "feeds": [topic("BUSINESS"),
                                          find("물가", "요금", "금리", "대출", "환율", "집값", "전세"),
                                          find("세금", "연금", "건강보험료", "최저임금", "지원금"),
                                          find("해킹", "\"개인정보 유출\"", "보이스피싱", "리콜", "\"소비자 피해\"")]},
    "food":   {"name": "음식·카페", "feeds": [find("맛집", "카페", "디저트", "신메뉴"), find("편의점", "프랜차이즈", "배달")]},
    "beauty": {"name": "뷰티·패션", "feeds": [find("화장품", "뷰티", "스킨케어"), find("패션", "운동화", "명품")]},
    "shop":   {"name": "쇼핑·혜택", "feeds": [find("할인", "쿠폰", "환급", "적립"), find("쇼핑", "이커머스", "다이소", "올리브영")]},
    "trip":   {"name": "여행·공간", "feeds": [find("여행", "축제", "호텔", "항공권"), find("팝업스토어", "핫플", "전시회")]},
    "cul":    {"name": "문화·여가", "feeds": [find("공연", "뮤지컬", "웹툰", "신간"), find("영화", "게임", "OTT")]},
    "it":     {"name": "IT·테크",   "feeds": [topic("TECHNOLOGY"), topic("SCIENCE")]},
    "sisa":   {"name": "시사",      "feeds": [search("정치"), topic("NATION"), topic("WORLD")]},
}
QUERY_WORDS |= {"인상", "인하", "유출", "피해", "소비자", "혜택", "이벤트", "출시"}   # 너무 흔한 말이라 키워드로는 안 써요
QUERY_WORDS -= {"다이소", "올리브영", "OTT"}   # 브랜드 이름은 그 자체로 이슈가 될 수 있어서 남겨요
DEFAULT_CAT = "sisa"
CAT_BY_NAME_INIT = {c["name"]: k for k, c in CATEGORIES.items()}  # 어느 분야에도 안 잡힌 기사(전체 주요 뉴스)는 시사로 봐요
TOP_CAT_CAP = 3       # 실시간 순위 10위마다 같은 분야는 최대 3개
PEOPLE_CAT_CAP = 2    # 화제의 인물 5명마다 같은 분야는 최대 2명
CAP_FREE = {"life"}   # 개수 제한 없이 다 넣는 분야 (생활·경제)

TRENDS_URL = "https://trends.google.com/trending/rss?geo=KR"
NETFLIX_URL = "https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv"
NETFLIX_EVERY_H = 12  # 넷플릭스는 주 1회 바뀌어서 12시간에 한 번만 받음
YT_WINDOW_H = 6       # 유튜브: 최근 몇 시간 동안 늘어난 조회수로 순위를 매길지
YT_CATS = {"1": "영화·애니", "10": "음악", "17": "스포츠", "20": "게임", "22": "인물",
           "23": "엔터", "24": "엔터", "25": "뉴스·정치"}   # 나머지는 '기타'

# 비밀 키 (GitHub Secrets 에 넣으면 자동으로 들어와요. 없으면 그 섹션만 빠져요)
YOUTUBE_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()
KOBIS_KEY = os.environ.get("KOBIS_API_KEY", "").strip()
KAKAO_KEY = os.environ.get("KAKAO_REST_KEY", "").strip()   # 있으면 기사 원문 주소 찾기에 써요 (없어도 돼요)

# 기사 사진 썸네일: 기사 원문의 대표 사진(og:image)을 작게 보여줘요. 끄려면 False 로.
ARTICLE_IMAGES = True
IMG_NEW_PER_RUN = 60   # 한 번 실행할 때 새로 찾아볼 기사 수 (사이트에 부담 안 주게)
IMG_KEEP_H = 48        # 찾아 둔 사진 주소를 기억하는 시간
NAVER_ID = os.environ.get("NAVER_CLIENT_ID", "").strip()          # 네이버 데이터랩 (선택)
NAVER_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
DATALAB_EVERY_H = 3   # 네이버 데이터랩 확인 간격(시간)

# 순위에서 뺄 흔한 단어 (이상한 키워드가 순위에 뜨면 여기에 추가하세요)
STOPWORDS = set("""
최대 최소 가을 겨울 여름 봄 사과 오전 오후 이날 당시 직접 최근 결국 다시 계속
기자 뉴스 속보 단독 종합 오늘 내일 어제 올해 지난 이번 관련 대한 위해 통해 위한
있는 없는 한다 했다 하는 하고 것으로 대해 이후 가능 사진 영상 포토 공개 발표 진행
예정 최근 오후 오전 확인 결국 논란 기준 전망 이유 상황 우리 국내 해외 정부 한국
대표 시장 사람 모두 다시 이제 계속 직접 지금 이미 함께 가장 무슨 어떻게 왜 연예 경제
첫날 결과 확정 기대 돌파 등극 이상 이하 이어 따라 만에 억원 만원 그룹 회장 사장
정치 사회 세계 스포츠 국회 대통령 장관 의원 주요 전국 지역 서울 사실 문제 추진
피해 사태 사고 조사 착수 수용 상정 불발 공방 활약 참석 주연 출연 발매 매진 시작 급증 급등
급락 상승 하락 증가 감소 이용자 첫방송 방송 소식 입장 반응 의혹 혐의 체포 구속 사망
개최 국민 제정 지원 요청 수상 확대 촉구 사업 송치 VS 의장 여성 위기 강화 추가 개선 협력
선정 운영 참여 마련 실시 도입 점검 대응 논의 합의 반대 찬성 비판 지적 강조 주장 제안 검토
출범 개막 개장 오픈 기념 행사 축제 설명 판결 선고 기소 수사 조사 압수수색 혐의 재판 처리
통과 의결 가결 부결 경신 기록 달성 유지 전환 변경 연장 중단 재개 완료 성공 실패 공식
이유 방법 모습 의미 효과 영향 우려 가운데 사이 직후 직전 당일 연속 이틀 사흘 매년 처음
청년 시민 주민 학생 아이 부모 노인 어린이 가족 남성 여성 국민들 업계 기업 회사 단체
씨 등 것 수 때 중 넘어 최초 현장 근황 돌아온 난리 소감 만든 찾아
 quot amp nbsp apos lt gt QUOT AMP NBSP APOS LT GT""".split())
# ↑ 여기에는 '등·것·오전'처럼 어느 기사에나 나오는 단어만 넣어요.
#   '진출·공략·브랜드'처럼 뜻이 넓은 단어는 아래 '한 단어 제목 규칙'이 알아서 순위를 낮춰요.

# 한 단어 제목 규칙: 키워드로 '미국 매장'처럼 2단어 이상 제목을 못 만들면
# (= 기사들이 서로 다른 이야기라 공통 구절이 없으면) 섞인 이슈로 보고 점수를 깎아요.
SINGLE_TITLE_FACTOR = 0.3   # 점수에 곱하는 값. 1 = 규칙 끄기, 0 = 아예 순위에서 빼기
SINGLE_OK = set("""
""".split())                # 한 단어 제목이어도 깎지 않을 단어 (예: 트럼프). 화제의 인물 이름은 자동으로 안 깎아요.

# 넓은 단어 규칙: '브랜드·참가·판매'처럼 '뷰티 브랜드', '할인 판매' 같은 두 단어 제목은 만들어지지만
# 여전히 여러 이야기가 섞인 단어도 한 단어 제목처럼 점수를 깎아요 (SINGLE_TITLE_FACTOR 를 같이 써요).
#   ① 아래 목록에 적은 단어  ② 기사가 BROAD_SPREAD 개 이상 분야에 고루 퍼진 단어 (자동)
BROAD_WORDS = set("""
브랜드 참가 판매 가능성 최우수 매출 매장 성장 공략 진출 출시 할인 혜택 고객 소비자 상품 제품
신제품 연말 내년 글로벌 시장 투자 전략 협업 인기 화제 눈길 관심 주목 성료 선보여 론칭 체험
대상 아들 딸 남편 아내 차량 콘서트 직장인 공개된 무대 현장 소식
출격 출사표 가세 합류 등판 귀환 컴백
""".split())
BROAD_SPREAD = 5            # 기사가 이만큼 많은 분야(10개 중)에 걸쳐 있으면 넓은 단어로 봐요. 0 = 자동 판단 끄기

# 보도자료로 보이는 기사는 점수를 덜 쳐요 (같은 보도자료를 여러 매체가 받아써서 순위가 부풀지 않게)
PR_WEIGHT = 0.3             # 1 = 규칙 끄기
PR_SOURCES = {"뉴스와이어", "보도자료", "PR Newswire", "비즈니스와이어", "Business Wire"}
PR_TITLE = re.compile(
    r"\[(보도자료|PR|알림|게시판|신상품|신제품|이벤트|출시)\]|"
    r"(성료|성황리|선봬|선보여|선보인다|론칭|런칭|기획전|프로모션|이벤트 진행|업무협약|MOU|협약 체결|"
    r"기념 이벤트|할인 행사|특가|오픈 기념|사회공헌|최우수상 수상|대상 수상|기탁)")

# 구글 검색 급상승(실시간 트렌드)에 같은 단어가 있으면 가산점: 1위 ×(1+TREND_MAX_BONUS) … 10위 ×1.05
TREND_MAX_BONUS = 0.5       # 0 = 가산점 끄기
TREND_BOOST = {}            # main() 에서 채워요

# 브리핑에 '관심이 식은 이슈'(💤) 줄을 넣을지. False = 넣지 않아요 (홈·날짜별 페이지 모두)
SHOW_GONE = False

# 이슈人: 이 단어 바로 앞(또는 뒤)에 붙은 2~4글자를 사람 이름으로 봅니다.
TITLES_AFTER = set("""
대통령 전대통령 총리 장관 차관 의원 대표 위원장 원내대표 시장 지사 도지사 구청장 교육감
의장 감독 코치 선수 배우 가수 교수 후보 비서실장 대변인 총장
""".split())
TITLES_BEFORE = set("배우 가수 감독 선수 개그맨 개그우먼 방송인 아나운서 유튜버 모델 작가".split())
NOT_PEOPLE = set("""
국회 여당 야당 민주당 국민의힘 정부 대통령실 현직 전직 신임 차기 당시 미국 중국 일본 북한
서울시 경기도 부산시 법원 검찰 경찰 기업 삼성 현대 국가대표 대표팀 한국 우리 각국 여야
""".split())
# 호칭 뒤에 오는 이름(김OO 의원)은 흔한 성씨로 시작하는 3글자만 사람으로 봄
SURNAMES = set("""
김 이 박 최 정 강 조 윤 장 임 한 오 서 신 권 황 안 송 류 유 전 홍 고 문 양 손 배 백 허 남 심 노
하 곽 성 차 주 우 구 민 진 나 지 엄 채 원 천 방 공 현 함 변 염 여 추 도 소 석 선 설 마 길 연 위
표 명 기 반 왕 금 옥 육 인 맹 제 모 탁 국 어 은 편 용 예 경 봉 사 부 피 감 태 승 범 탄
""".split())
# 이런 글자로 끝나면 사람이 아니라 기관·회사로 봄
ORG_SUFFIX = ("증권", "전자", "은행", "그룹", "공사", "재단", "협회", "위원회", "카드", "보험",
              "건설", "제약", "통신", "자동차", "기획", "엔터", "당", "청", "처")
# 자동으로 못 잡는 인물을 직접 넣고 싶으면 여기에 이름 추가
PEOPLE_EXTRA = set()

JOSA = sorted("""
에서는 으로는 에게서 이라는 이라고 에서도 으로도 에서 으로 에게 까지 부터 라는 라고
조차 마저 처럼 보다 하며 은 는 이 가 을 를 의 에 도 로 와 과 만 께
""".split(), key=len, reverse=True)
# ═══════════════════════════════════════════════════

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site" / "data.json"
CONTENT_OUT = ROOT / "site" / "content.json"
MEME_OUT = ROOT / "site" / "memes.json"
ISSUES_OUT = ROOT / "site" / "issues.json"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (issue-radar bot)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def local(tag):
    return tag.rsplit("}", 1)[-1]


def child(el, name):
    """네임스페이스와 상관없이 자식 태그 찾기"""
    for c in el:
        if local(c.tag) == name:
            return c
    return None


def text(el, name):
    c = child(el, name)
    if c is None or not c.text:
        return ""
    t = c.text
    for _ in range(2):                    # 일부 언론사 RSS는 &amp;quot; 처럼 두 번 감싸서 보내요 → 진짜 글자로 풀기
        t = htmllib.unescape(t)
    return re.sub(r"\s+", " ", t.replace("\xa0", " ")).strip()


# ───────────── 뉴스 ─────────────
def parse_news(xml_bytes):
    items = []
    for it in ET.fromstring(xml_bytes).iter("item"):
        title, link = text(it, "title"), text(it, "link")
        source = text(it, "source")
        # 구글 뉴스 제목은 "기사 제목 - 언론사" 형태
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)]
        elif " - " in title and not source:
            title, source = title.rsplit(" - ", 1)
        try:
            pub = parsedate_to_datetime(text(it, "pubDate")).astimezone(KST)
        except Exception:
            pub = datetime.now(KST)
        if title and link.startswith("http"):
            items.append({"title": title, "source": source or "알 수 없음",
                          "link": link, "time": pub.isoformat(timespec="minutes")})
    return items


def normalize(title):
    return re.sub(r"[^가-힣A-Za-z0-9]", "", title).lower()


def strip_josa(w):
    if re.fullmatch(r"[가-힣]+", w):
        for j in JOSA:
            if w.endswith(j) and len(w) - len(j) >= 2:
                return w[: -len(j)]
    return w


def tokens(title):
    title = re.sub(r"\[[^\]]*\]|\([^)]*\)|【[^】]*】|<[^>]*>|'|\"|‘|’|“|”", " ", title)
    return re.findall(r"[가-힣A-Za-z0-9]+", title)


def keywords(title):
    found = set()
    for w in tokens(title):
        w = strip_josa(w)
        if len(w) < 2 or re.match(r"^\d", w) or w in STOPWORDS or w in QUERY_WORDS:
            continue
        found.add(w.upper() if w.isascii() else w)
    return found


TITLE_MAX = 18   # 이슈 제목 최대 글자 수


def _norm_tok(w):
    w = strip_josa(w)
    return w.upper() if w.isascii() else w


def _ok_edge(w):
    return len(w) >= 2 and not re.match(r"^\d+$", w) and w not in STOPWORDS


def make_title(kw, arts):
    """한 단어 키워드를 '구자욱 우승'처럼 2~4단어 제목으로 만들어요.
    1) 여러 기사 제목에 똑같이 붙어 나오는 구절(키워드 포함)을 먼저 찾고
    2) 없으면 기사 제목에 자주 같이 나오는 단어를 키워드 앞뒤에 붙여요."""
    srcs = {_norm_tok(w) for a in arts for w in tokens(a.get("source", ""))}   # 언론사 이름은 제목에서 빼요
    titles = [[w for w in (_norm_tok(x) for x in tokens(a["title"])) if w == kw or w not in srcs] for a in arts]
    titles = [t for t in titles if kw in t]
    n = len(titles)
    if n < 2:
        return kw
    need = max(2, round(n * 0.25))
    # 1) 키워드를 포함한 연속 구절
    grams = Counter()
    for t in titles:
        seen = set()
        for size in (2, 3, 4):
            for i in range(len(t) - size + 1):
                g = tuple(t[i:i + size])
                if kw in g and _ok_edge(g[0]) and _ok_edge(g[-1]) and len(set(g)) == size:
                    seen.add(g)
        grams.update(seen)
    best = [(c * (1 + 0.2 * len(g)), g) for g, c in grams.items()
            if c >= need and len(" ".join(g)) <= TITLE_MAX]
    if best:
        return " ".join(max(best)[1])
    # 2) 자주 같이 나오는 단어 (키워드 기준 앞뒤 위치 순서로)
    co, pos = Counter(), defaultdict(list)
    for t in titles:
        k = t.index(kw)
        for i, w in enumerate(t):
            if w != kw and _ok_edge(w) and len(w) <= 8:
                pos[w].append(i - k)
        co.update({w for w in t if w != kw and _ok_edge(w) and len(w) <= 8})
    picks = [w for w, c in co.most_common(4) if c >= max(2, round(n * 0.35))][:2]
    if not picks:
        return kw
    words = sorted(picks + [kw], key=lambda w: 0 if w == kw else sum(pos[w]) / len(pos[w]))
    title = " ".join(words)
    return title if len(title) <= TITLE_MAX else kw


def collect_feeds(urls, cutoff):
    seen = {}
    for url in urls:
        try:
            for a in parse_news(fetch(url)):
                if "포토" in a["title"][:6] or a["time"] < cutoff:
                    continue                                  # 포토·오래된 기사 제외
                seen.setdefault(normalize(a["title"]), a)     # 같은 제목(전재 기사) 제외
        except Exception as e:
            print(f"[경고] 수집 실패: {url} ({e})", file=sys.stderr)
    return seen


def is_pr(a):
    return a.get("source") in PR_SOURCES or bool(PR_TITLE.search(a.get("title", "")))


def trend_boost_map(trends):
    """급상승 검색어 → {정규화한 단어: 배율}. 검색어 전체와 그 안의 낱말(2글자 이상)을 모두 등록"""
    out, n = {}, max(len(trends), 1)
    for t in trends:
        mult = 1 + TREND_MAX_BONUS * (n + 1 - t["rank"]) / n
        for w in {normalize(t["keyword"])} | {normalize(strip_josa(x)) for x in tokens(t["keyword"])}:
            if len(w) >= 2 and w not in STOPWORDS and w.upper() not in STOPWORDS:
                out[w] = max(out.get(w, 1), mult)
    return out


def trend_mult(kw):
    k = normalize(kw)
    if k in TREND_BOOST:
        return TREND_BOOST[k]
    best = 1          # 'KBO' ↔ 'kbo리그' 처럼 이슈 단어가 검색어의 절반 이상이면 같은 것으로 봐요
    for w, m in TREND_BOOST.items():
        if len(k) >= 2 and ((k in w and len(k) * 2 >= len(w)) or (w in k and len(w) * 2 >= len(k))):
            best = max(best, m)
    return best


def score_terms(articles, extract, min_sources=2):
    """단어별로 (점수, 단어, 기사 수, 매체 수, 기사 목록) 을 계산.
    보도자료 기사는 PR_WEIGHT 만큼만 치고, 구글 급상승 검색어와 겹치면 가산점을 줘요."""
    stats = defaultdict(list)
    for a in articles:
        for kw in extract(a["title"]):
            stats[kw].append(a)
    out = []
    for kw, arts in stats.items():
        n_src = len({a["source"] for a in arts})
        if n_src < min_sources:
            continue
        w_src, w_art = defaultdict(float), 0.0
        for a in arts:
            w = PR_WEIGHT if is_pr(a) else 1.0
            w_art += w
            w_src[a["source"]] = max(w_src[a["source"]], w)
        score = (sum(w_src.values()) * 3 + w_art) * trend_mult(kw)
        out.append((round(score, 1), kw, len(arts), n_src, arts))
    out.sort(key=lambda x: (-x[0], x[1]))
    return out


def is_broad(kw, arts, link_cat=None):
    if kw in BROAD_WORDS:
        return True
    if BROAD_SPREAD and link_cat:
        return len({link_cat[a["link"]] for a in arts if a["link"] in link_cat}) >= BROAD_SPREAD
    return False


def title_rule(scored, keep=frozenset(), link_cat=None):
    """한 단어 제목밖에 못 만드는 키워드(섞인 이슈)와 넓은 단어는 점수를 깎고 다시 줄 세워요.
    돌려주는 값: (새 점수 목록, 깎인 키워드 모음)"""
    out, single = [], set()
    for score, kw, n_art, n_src, arts in scored:
        if kw not in keep and kw not in SINGLE_OK and (make_title(kw, arts) == kw or is_broad(kw, arts, link_cat)):
            single.add(kw)
            if SINGLE_TITLE_FACTOR <= 0:
                continue
            score = score * SINGLE_TITLE_FACTOR
        out.append((score, kw, n_art, n_src, arts))
    out.sort(key=lambda x: (-x[0], x[1]))
    return out, single


def cat_of(arts, link_cat):
    cnt = Counter(link_cat[a["link"]] for a in arts if a["link"] in link_cat)
    return cnt.most_common(1)[0][0] if cnt else DEFAULT_CAT


def pick(scored, n, old_ranks, link_cat=None, cap=None, per=10):
    """겹치는 이슈를 합치고 상위 n 개를 고른 뒤 온도·순위변화를 붙임.
    cap 을 주면 per 개마다 같은 분야는 cap 개까지만 (한 분야가 순위를 독차지하지 않게)"""
    issues, used, cnt, skipped = [], [], Counter(), []
    for score, kw, n_art, n_src, arts in scored:
        ids = {a["link"] for a in arts}
        if any(len(ids & u) / len(ids) > 0.6 for u in used):
            continue                       # 이미 뽑힌 이슈와 기사가 거의 같음 → 같은 이슈
        if any((kw in it["keyword"] or it["keyword"] in kw)
               and len(ids & {a["link"] for a in it["_arts"]}) / len(ids) > 0.3 for it in issues):
            continue                       # '의장' 과 '국회의장' 처럼 겹치는 단어 → 하나만
        words = set(make_title(kw, arts).split())
        if any((it["keyword"] in words or kw in it["title"].split())
               and len(ids & {a["link"] for a in it["_arts"]}) / len(ids) > 0.15 for it in issues):
            continue                       # '서울카페쇼 참가' 처럼 이미 뽑힌 이슈 이름이 제목에 들어 있음 → 같은 이슈
        cid = cat_of(arts, link_cat) if link_cat is not None else None
        if cap and cid not in CAP_FREE and cnt[cid] >= cap * (1 + len(issues) // per):
            skipped.append((score, kw, n_art, n_src, arts, cid))
            continue                       # 이 분야는 이미 충분히 올라와 있음 (자리가 남으면 나중에 채움)
        cnt[cid] += 1
        used.append(ids)
        news = sorted(arts, key=lambda a: a["time"], reverse=True)[:NEWS_PER_ISSUE]
        it = {"keyword": kw, "title": make_title(kw, arts), "score": score, "articles": n_art, "sources": n_src,
              "headline": news[0]["title"], "news": news, "_arts": arts}
        if cid in CATEGORIES:
            it["cat"] = CATEGORIES[cid]["name"]
        issues.append(it)
        if len(issues) >= n:
            break
    for score, kw, n_art, n_src, arts, cid in skipped:   # 다른 분야로 다 못 채우면 남은 자리를 채움
        if len(issues) >= n:
            break
        ids = {a["link"] for a in arts}
        if any(len(ids & u) / len(ids) > 0.6 for u in used):
            continue
        used.append(ids)
        news = sorted(arts, key=lambda a: a["time"], reverse=True)[:NEWS_PER_ISSUE]
        it = {"keyword": kw, "title": make_title(kw, arts), "score": score, "articles": n_art, "sources": n_src,
              "headline": news[0]["title"], "news": news, "_arts": arts}
        if cid in CATEGORIES:
            it["cat"] = CATEGORIES[cid]["name"]
        issues.append(it)
    top = max((x["score"] for x in issues), default=1)
    for i, it in enumerate(issues, 1):
        it["rank"] = i
        it["temp"] = round(30 + 70 * it.pop("score") / top)          # 30~100도
        if old_ranks is None:
            it["change"] = 0
        elif it["keyword"] in old_ranks:
            it["change"] = old_ranks[it["keyword"]] - i
        else:
            it["change"] = "new"
    return issues


def clean(issues):
    for it in issues:
        it.pop("_arts", None)
    return issues


def old_rank_map(lst, key="keyword"):
    return {x[key]: x["rank"] for x in lst} if lst is not None else None


def rising(scored, now, link_cat=None, single=frozenset(), exclude=()):
    """최근 RISING_HOURS 시간에 기사가 몰린 이슈. 모자라면 최근 기사 증가가 큰 순으로 채움.
    분야(정치·경제…)마다 먼저 1개씩 고르고, 자리가 남으면 분야당 2개까지 채움.
    single 에 든 키워드(한 단어 제목)는 여기서도 점수를 깎아요."""
    link_cat = link_cat or {}
    factor = lambda kw: SINGLE_TITLE_FACTOR if kw in single else 1
    recent_cut = (now - timedelta(hours=RISING_HOURS)).isoformat()
    c3 = (now - timedelta(hours=3)).isoformat()
    c6 = (now - timedelta(hours=6)).isoformat()

    def metrics(arts):
        last3 = sum(1 for a in arts if a["time"] >= c3)
        prev3 = sum(1 for a in arts if c6 <= a["time"] < c3)
        return last3, prev3

    strict, loose = [], []
    for score, kw, n_art, n_src, arts in scored[:80]:
        recent = [a for a in arts if a["time"] >= recent_cut]
        last3, prev3 = metrics(arts)
        if len(recent) >= 2 and len(recent) / n_art >= 0.5:
            strict.append(((len(recent) * 3 + n_src) * factor(kw), kw, n_art, n_src, arts, len(recent), False))
        elif last3 >= 1:                                   # 채우기 후보: 최근 3시간 증가가 큰 순
            loose.append((((last3 - prev3) * 3 + last3 * 2 + n_src) * factor(kw), kw, n_art, n_src, arts,
                          len(recent), True))
    strict.sort(key=lambda x: (-x[0], x[1]))
    loose.sort(key=lambda x: (-x[0], x[1]))

    # 실시간 순위 위쪽에 이미 있는 이슈 (키워드나 제목이 같으면 같은 이슈)
    skip_kw = {it["keyword"] for it in exclude}
    skip_title = {it.get("title") or it["keyword"] for it in exclude}
    cands, used, titles = [], [], set()
    for c in strict + loose:                              # 기사가 70% 넘게 겹치면 같은 이슈로 봄
        kw, arts = c[1], c[4]
        last3, prev3 = metrics(arts)
        if prev3 and last3 / prev3 < RISING_MIN_RATIO:    # 별로 안 늘었으면 '급부상'이 아니에요
            continue
        title = make_title(kw, arts)
        if kw in skip_kw or title in skip_title or title in titles:
            continue                                      # 실시간 순위와 겹치거나, 제목이 같은 이슈가 이미 있음
        ids = {a["link"] for a in arts}
        if any(len(ids & u) / len(ids) > 0.7 for u in used):
            continue
        used.append(ids)
        titles.add(title)
        cands.append((len(cands), cat_of(arts, link_cat), c))

    picked, per = [], Counter()
    for limit in range(1, RISING_PER_CAT + 1):            # 1바퀴: 분야마다 1개 → 2바퀴: 2개째
        for order, cid, c in cands:
            if len(picked) >= RISING_N:
                break
            if (cid in CAP_FREE or per[cid] < limit) and all(order != p[0] for p in picked):
                picked.append((order, cid, c))
                per[cid] += 1
    picked.sort(key=lambda p: p[0])                       # 원래 점수 순서대로

    out = []
    for _, cid, (s, kw, n_art, n_src, arts, n_recent, filled) in picked:
        news = sorted(arts, key=lambda a: a["time"], reverse=True)
        last3, prev3 = metrics(arts)
        out.append({"keyword": kw, "title": make_title(kw, arts), "recent": n_recent, "articles": n_art, "sources": n_src,
                    "headline": news[0]["title"], "latest": news[0]["time"], "score": s,
                    "filled": filled, "last3": last3,
                    # '방금' 표시는 조건을 통과한 이슈 중 3시간 전에 기사가 없던 것만
                    "is_new": (not filled) and prev3 == 0,
                    "ratio": round(last3 / prev3, 1) if prev3 else None,
                    "cat": CATEGORIES[cid]["name"] if cid in CATEGORIES else "",
                    "news": news[:NEWS_PER_ISSUE]})
    n = len(out)
    for i, it in enumerate(out):                         # 온도: 순서대로 100도 → 40도
        it.pop("score")
        it["temp"] = round(100 - i * 60 / max(n - 1, 1))
    return out


# ───────────── 이슈人 ─────────────
def find_people(articles):
    names = set(PEOPLE_EXTRA)
    for a in articles:
        ws = [strip_josa(w) for w in tokens(a["title"])]
        for i, w in enumerate(ws):
            if w in TITLES_AFTER and i > 0:
                cand = ws[i - 1]     # 김OO 의원 → 성씨로 시작하는 3글자만
                if not (len(cand) == 3 and cand[0] in SURNAMES):
                    continue
            elif w in TITLES_BEFORE and i + 1 < len(ws):
                cand = ws[i + 1]     # 배우 OOO → 예명도 허용
            else:
                continue
            if (re.fullmatch(r"[가-힣]{2,4}", cand) and cand not in NOT_PEOPLE
                    and cand not in STOPWORDS and not cand.endswith("모")
                    and not cand.endswith(ORG_SUFFIX)):
                names.add(cand)

    def extract(title):
        return {strip_josa(w) for w in tokens(title)} & names
    extract.names = names          # 한 단어 제목 규칙에서 사람 이름은 안 깎으려고 같이 넘겨요
    return extract


# ───────────── 검색 급상승 ─────────────
def collect_trends():
    try:
        root = ET.fromstring(fetch(TRENDS_URL))
    except Exception as e:
        print(f"[경고] 검색 급상승 수집 실패 ({e})", file=sys.stderr)
        return []
    out = []
    for i, it in enumerate(root.iter("item"), 1):
        news = []
        for c in it:
            if local(c.tag) == "news_item":
                url = text(c, "news_item_url")
                if url.startswith("http"):
                    news.append({"title": text(c, "news_item_title"),
                                 "source": text(c, "news_item_source"), "link": url})
        out.append({"rank": i, "keyword": text(it, "title"),
                    "traffic": text(it, "approx_traffic"), "news": news[:3]})
        if i >= 10:
            break
    return out


# ───────────── 위키백과 많이 본 문서 (한국어, 하루 단위) ─────────────
WIKI_N = 10
WIKI_EVERY_H = 3            # 새 날짜 자료가 아직 없으면 3시간 뒤에 다시 시도
WIKI_UA = "IssuePickle/1.0 (https://piqlemuu.github.io/issue-piqle/)"   # 위키미디어가 요구하는 봇 이름
WIKI_SKIP = ("대문", "위키백과:대문")


def wiki_day(day):
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/top/ko.wikipedia/all-access/"
           + day.strftime("%Y/%m/%d"))
    req = urllib.request.Request(url, headers={"User-Agent": WIKI_UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        arts = json.loads(r.read())["items"][0]["articles"]
    out = []
    for a in arts:
        t = a["article"]
        if ":" in t or t in WIKI_SKIP:      # 특수:검색, 분류:, 틀: 같은 위키 내부 문서는 뺌
            continue
        out.append({"title": t.replace("_", " "), "views": a["views"], "_key": t})
    return out


def collect_wiki(cache, now):
    utc = now.astimezone(timezone.utc).date()
    want = (utc - timedelta(days=1)).isoformat()
    if cache and (cache.get("date") == want or
                  cache.get("tried", "") >= (now - timedelta(hours=WIKI_EVERY_H)).isoformat()):
        return cache
    for back in (1, 2):                      # 어제 자료가 아직 안 나왔으면 그저께
        day = utc - timedelta(days=back)
        try:
            cur = wiki_day(day)
        except Exception as e:
            print(f"[경고] 위키백과 {day} 수집 실패 ({e})", file=sys.stderr)
            continue
        if not cur:
            continue
        if cache and cache.get("date") == day.isoformat():
            cache["tried"] = now.isoformat(timespec="minutes")
            return cache
        try:
            prev = {a["_key"]: i for i, a in enumerate(wiki_day(day - timedelta(days=1)), 1)}
        except Exception:
            prev = {}
        items = []
        for i, a in enumerate(cur[:WIKI_N], 1):
            k = a.pop("_key")
            items.append({**a, "rank": i, "change": (prev[k] - i) if k in prev else "new",
                          "link": "https://ko.wikipedia.org/wiki/" + urllib.parse.quote(k)})
        return {"date": day.isoformat(), "tried": now.isoformat(timespec="minutes"), "items": items}
    if cache:
        cache["tried"] = now.isoformat(timespec="minutes")
    return cache


# ───────────── 유튜브 (콘텐츠 랭킹) ─────────────
def yt_get(path, **params):
    params["key"] = YOUTUBE_KEY
    return json.loads(fetch("https://www.googleapis.com/youtube/v3/" + path + "?"
                            + urllib.parse.urlencode(params)))


def collect_youtube(state, now):
    """인기 영상 200개를 모아 최근 YT_WINDOW_H 시간 동안 늘어난 조회수 순으로 정렬"""
    state = state or {}
    if not YOUTUBE_KEY:
        print("[안내] YOUTUBE_API_KEY 가 없어 영상은 건너뜁니다.")
        return [], state
    items, token = [], None
    try:
        for _ in range(4):                                   # 전체 인기: 50개씩 4번 = 200개
            p = dict(part="snippet,statistics", chart="mostPopular", regionCode="KR", maxResults=50)
            if token:
                p["pageToken"] = token
            d = yt_get("videos", **p)
            items += d.get("items", [])
            token = d.get("nextPageToken")
            if not token:
                break
        subs, ch = {}, sorted({v["snippet"]["channelId"] for v in items})
        for i in range(0, len(ch), 50):                      # 구독자 수
            for c in yt_get("channels", part="statistics", id=",".join(ch[i:i + 50])).get("items", []):
                st = c.get("statistics", {})
                if not st.get("hiddenSubscriberCount"):
                    subs[c["id"]] = int(st.get("subscriberCount", 0))
    except Exception as e:
        print(f"[경고] 유튜브 수집 실패 ({type(e).__name__})", file=sys.stderr)  # 키가 로그에 안 찍히게
        return [], state

    snaps = sorted(state.get("snaps", []), key=lambda x: x["t"])
    win_start = (now - timedelta(hours=YT_WINDOW_H, minutes=15)).isoformat()
    old_ranks = state.get("ranks")
    vids = []
    for v in items:
        sn, vid = v["snippet"], v["id"]
        views = int(v.get("statistics", {}).get("viewCount", 0))
        gain = hrs = None
        for snap in snaps:                                  # 6시간 안의 가장 오래된 기록과 비교
            if snap["t"] >= win_start and vid in snap["v"]:
                gain = views - snap["v"][vid]
                hrs = (now - datetime.fromisoformat(snap["t"])).total_seconds() / 3600
                break
        try:
            age = (now - datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))).total_seconds() / 3600
        except Exception:
            age = 999
        if age <= YT_WINDOW_H and (hrs is None or age < hrs):  # 6시간 안에 올라온 영상은 조회수 전체가 증가분
            gain, hrs = views, age
        # 순위는 '시간당 늘어난 조회수' 로 공평하게 비교 (기록이 쌓이기 전 초반에도 정확하도록)
        est = (gain / max(hrs, 0.5) if gain is not None else views / max(age, 1)) * YT_WINDOW_H
        thumbs = sn.get("thumbnails", {})
        vids.append({
            "id": vid, "title": sn.get("title", ""), "channel": sn.get("channelTitle", ""),
            "subs": subs.get(sn["channelId"]), "cat": YT_CATS.get(sn.get("categoryId"), "기타"),
            "thumb": (thumbs.get("medium") or thumbs.get("default") or {}).get("url", ""),
            "views": views, "gain": gain, "hrs": max(1, round(hrs)) if hrs is not None else None,
            "link": f"https://www.youtube.com/watch?v={vid}", "_est": est,
            "_tags": sn.get("tags", [])[:20],                # 밈 후보 찾기에만 쓰고 저장 안 함
        })
    vids.sort(key=lambda x: -x.pop("_est"))
    for i, x in enumerate(vids, 1):
        x["rank"] = i
        x["change"] = (0 if old_ranks is None else
                       old_ranks[x["id"]] - i if x["id"] in old_ranks else "new")

    keep = (now - timedelta(hours=YT_WINDOW_H + 1)).isoformat()
    thinned = []                                             # 기록은 약 1시간 간격으로만 보관 (파일 크기 줄이기)
    for s_ in snaps:
        if s_["t"] < keep:
            continue
        if thinned and (datetime.fromisoformat(s_["t"]) - datetime.fromisoformat(thinned[-1]["t"])) < timedelta(minutes=50):
            continue
        thinned.append(s_)
    snaps = thinned
    snaps.append({"t": now.isoformat(timespec="minutes"), "v": {x["id"]: x["views"] for x in vids}})
    return vids, {"snaps": snaps, "ranks": {x["id"]: x["rank"] for x in vids}}


# ───────────── 박스오피스 (영화진흥위원회) ─────────────
def collect_boxoffice(now):
    if not KOBIS_KEY:
        print("[안내] KOBIS_API_KEY 가 없어 박스오피스는 건너뜁니다.")
        return None
    day = (now - timedelta(days=1)).strftime("%Y%m%d")       # 어제 기준 (오늘 집계는 내일 나옴)
    path = ("www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json?"
            + urllib.parse.urlencode({"key": KOBIS_KEY, "targetDt": day}))
    for scheme in ("https://", "http://"):
        try:
            res = json.loads(fetch(scheme + path))["boxOfficeResult"]
            break
        except Exception as e:
            err = type(e).__name__
    else:
        print(f"[경고] 박스오피스 수집 실패 ({err})", file=sys.stderr)
        return None
    items = []
    for m in res.get("dailyBoxOfficeList", []):
        inten = int(m.get("rankInten") or 0)
        items.append({"rank": int(m["rank"]), "title": m.get("movieNm", ""), "open": m.get("openDt", ""),
                      "audi": int(m.get("audiCnt") or 0), "acc": int(m.get("audiAcc") or 0),
                      "share": m.get("salesShare", ""),
                      "change": "new" if m.get("rankOldAndNew") == "NEW" else inten})
    return {"date": f"{day[:4]}-{day[4:6]}-{day[6:]}", "items": items}


# ───────────── 넷플릭스 (공식 주간 TOP 10, 한국) ─────────────
def collect_netflix(cache, now):
    if cache and cache.get("fetched", "") >= (now - timedelta(hours=NETFLIX_EVERY_H)).isoformat():
        return cache                                      # 자주 바뀌지 않아서 몇 시간에 한 번만 받음
    try:
        lines = fetch(NETFLIX_URL).decode("utf-8").splitlines()
    except Exception as e:
        print(f"[경고] 넷플릭스 수집 실패 ({e})", file=sys.stderr)
        return cache
    head = lines[0].split("\t")
    col = {h: i for i, h in enumerate(head)}
    rows = [r for r in (l.split("\t") for l in lines[1:])
            if len(r) == len(head) and r[col["country_iso2"]] == "KR"]
    if not rows:
        return cache
    weeks = sorted({r[col["week"]] for r in rows})
    out = {"fetched": now.isoformat(timespec="minutes"), "week": weeks[-1]}
    for key, cat in (("tv", "TV"), ("films", "Films")):
        def lst(week):
            return sorted((r for r in rows if r[col["week"]] == week and r[col["category"]] == cat),
                          key=lambda r: int(r[col["weekly_rank"]]))
        prev = {(r[col["show_title"]], r[col["season_title"]]): int(r[col["weekly_rank"]])
                for r in lst(weeks[-2])} if len(weeks) > 1 else {}
        out[key] = []
        for r in lst(weeks[-1]):
            k = (r[col["show_title"]], r[col["season_title"]])
            rank = int(r[col["weekly_rank"]])
            season = r[col["season_title"]]
            out[key].append({"rank": rank, "title": r[col["show_title"]],
                             "season": "" if season in ("", "N/A") else season,
                             "weeks": int(r[col["cumulative_weeks_in_top_10"]] or 1),
                             "change": prev[k] - rank if k in prev else "new"})
    return out


# ───────────── 트렌드 밈 ─────────────
MEME_STOP = set("""
SHORTS SHORT MV M/V OFFICIAL LIVE EP VLOG FULL HD 4K TEASER TRAILER HIGHLIGHTS HIGHLIGHT
REACTION ENG SUB KOR VS FT FEAT THE AND FOR WITH YOU OF TO IN ON MY ME IS
쇼츠 숏츠 영상 브이로그 하이라이트 풀버전 예고 티저 리액션 라이브 공식 직캠 무대 노래 커버
모음 레전드 리뷰 먹방 일상 실황 플레이 생방송 다시보기 클립 편집 최초 공개 반응 근황 진짜
처음 오늘 이번 역대 최고 미친 대박 ㅋㅋ ㅋㅋㅋ ㅎㅎ 구독 좋아요 알림 채널 시즌 회차 방송
꿀팁 여행 정리 토크 예능 뮤직비디오 애니메이션 신작 요리 게임 음악 스포츠 뉴스 드라마 영화 애니
경기 주요 모습 장면 순간 이야기 사람 친구 엄마 아빠 한국 일본 미국 중국 세계 리그 시리즈
""".split())
MEME_KEEP_DAYS = 10
MEME_N = 15


def meme_words(text):
    """제목·해시태그·태그에서 단어 뽑기 (해시태그는 통째로)"""
    out = set()
    for h in re.findall(r"#([0-9A-Za-z가-힣_]{2,20})", text):
        out.add(h.upper() if h.isascii() else h)
    text = re.sub(r"#[0-9A-Za-z가-힣_]+", " ", text)
    for w in tokens(text):
        if not w.endswith("이"):                 # '플레이' 같은 말이 '플레' 로 잘리지 않게
            w = strip_josa(w)
        if len(w) < 2 or len(w) > 12 or re.match(r"^\d", w):
            continue
        w = w.upper() if w.isascii() else w
        if w in STOPWORDS or w in MEME_STOP:
            continue
        out.add(w)
    return out


def read_sources():
    """sources.txt 에 적힌 커뮤니티 RSS 목록 읽기"""
    path = ROOT / "sources.txt"
    out = []
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "|" in ln:
                name, url = (x.strip() for x in ln.split("|", 1))
                if url.startswith("http"):
                    out.append((name, url))
    return out


def collect_community(now):
    """커뮤니티 공식 RSS 에서 최근 글 제목만 모으기 (본문은 저장 안 함)"""
    posts, cutoff = [], (now - timedelta(hours=MAX_AGE_HOURS)).isoformat()
    for name, url in read_sources():
        try:
            items = parse_news(fetch(url))
            got = 0
            for a in items:
                if a["time"] >= cutoff:
                    posts.append({"title": a["title"], "link": a["link"], "channel": name, "src": name, "time": a["time"]})
                    got += 1
            print(f"[커뮤니티] {name}: 글 {got}개 ({url})")
        except Exception as e:
            print(f"[커뮤니티] {name}: 실패 ({type(e).__name__}) {url}", file=sys.stderr)
    return posts


# ───────────── 커뮤니티 화제 (언론 보도로 거꾸로 찾기 + 운영자 직접 고른 것) ─────────────
# 커뮤니티를 직접 긁지 않고, 기자들이 "커뮤니티에서 화제"라고 쓴 기사를 구글 뉴스 검색 RSS로 모아요.
BUZZ_QUERIES = ['"온라인 커뮤니티" 화제', '누리꾼 갑론을박', '커뮤니티 갑론을박', '"온라인에서 화제"', '"누리꾼들" 반응']
BUZZ_N = 10            # 화면에 보여 줄 자동 수집 개수
BUZZ_PIN_DAYS = 7      # community.md 에 적은 항목을 며칠 동안 보여 줄지
BUZZ_SKIP = ["사망", "숨져", "숨진", "살해", "자살", "극단적", "성폭", "성추행", "시신", "유족", "참사", "흉기"]


def collect_buzz(cutoff):
    """같은 이야기를 다룬 기사끼리 묶고, 여러 매체가 다룬 것부터 보여 줘요"""
    arts = []
    for a in collect_feeds([search(q) for q in BUZZ_QUERIES], cutoff).values():
        if not any(w in a["title"] for w in BUZZ_SKIP):
            arts.append(a)
    groups = []                                            # [대표 기사, 단어 집합, 매체 집합, 기사 수]
    for a in sorted(arts, key=lambda x: x["time"], reverse=True):
        ws = set(keywords(a["title"])) - QUERY_WORDS - {"누리꾼", "커뮤니티", "온라인", "갑론을박", "화제", "반응"}
        for g in groups:
            if ws and g[1] and len(ws & g[1]) / min(len(ws), len(g[1])) >= 0.5:
                g[2].add(a["source"]); g[3] += 1; g[1] |= ws
                break
        else:
            groups.append([a, ws, {a["source"]}, 1])
    groups.sort(key=lambda g: (len(g[2]), g[0]["time"]), reverse=True)
    out = []
    for a, _, srcs, n in groups[:BUZZ_N]:
        out.append({"title": a["title"], "link": a["link"], "source": a["source"],
                    "time": a["time"], "sources": len(srcs)})
    print(f"[커뮤니티 화제] 기사 {len(arts)}건 → 이야기 {len(groups)}개")
    return out


def read_buzz_picks(now):
    """community.md 에 운영자가 직접 적은 '커뮤니티 화제' (## 제목 / 설명: / 링크: / 날짜:)"""
    path = ROOT / "community.md"
    if not path.exists():
        return []
    since = (now - timedelta(days=BUZZ_PIN_DAYS)).strftime("%Y-%m-%d")
    items = []
    for block in re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.M)[1:]:
        lines = block.strip().splitlines()
        it = {"title": lines[0].strip(), "desc": "", "link": "", "date": ""}
        for ln in lines[1:]:
            m = re.match(r"^\s*(설명|링크|날짜)\s*[:：]\s*(.*)$", ln)
            if m:
                it[{"설명": "desc", "링크": "link", "날짜": "date"}[m.group(1)]] = m.group(2).strip()
        if it["title"] and not it["title"].startswith("(") and it["date"] >= since:
            if not it["link"].startswith("http"):
                it["link"] = ""
            items.append(it)
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


def datalab_check(words, state, now):
    """네이버 검색어 트렌드(NAVER API HUB)로 후보 단어의 최근 검색량 변화 확인. 키가 없으면 건너뜀.
    약관상 API 결과를 광고와 함께 화면에 보여주면 안 되므로, 결과는 순위 계산에만 쓰고 화면에는 내보내지 않음"""
    state = dict(state or {})
    if not (NAVER_ID and NAVER_SECRET) or not words:
        return state
    last = state.get("_checked", "")
    if last >= (now - timedelta(hours=DATALAB_EVERY_H)).isoformat():
        return state                                    # 무료 한도를 아끼려고 몇 시간에 한 번만
    end = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    start = (now - timedelta(days=14)).strftime("%Y-%m-%d")
    for i in range(0, len(words), 5):                   # 한 번에 5개씩
        body = {"startDate": start, "endDate": end, "timeUnit": "date",
                "keywordGroups": [{"groupName": w, "keywords": [w]} for w in words[i:i + 5]]}
        try:
            # 2026년부터 네이버 클라우드 'NAVER API HUB' 로 옮겨진 검색어 트렌드 API
            req = urllib.request.Request("https://naverapihub.apigw.ntruss.com/search-trend/v1/search",
                                         data=json.dumps(body).encode(), method="POST",
                                         headers={"X-NCP-APIGW-API-KEY-ID": NAVER_ID,
                                                  "X-NCP-APIGW-API-KEY": NAVER_SECRET,
                                                  "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read())
        except Exception as e:
            print(f"[경고] 네이버 데이터랩 실패 ({type(e).__name__})", file=sys.stderr)
            return state
        for g in res.get("results", []):
            vals = [d["ratio"] for d in g.get("data", [])]
            if len(vals) < 4:
                state[g["title"]] = None                # 검색량이 너무 적어 데이터 없음
                continue
            recent, before = vals[-2:], vals[:-2]
            b = sum(before) / len(before) if before else 0
            state[g["title"]] = round(sum(recent) / 2 / b, 1) if b > 0 else None
    state = {w: state.get(w) for w in words}            # 지금 후보 단어만 보관
    state["_checked"] = now.isoformat(timespec="minutes")
    return state


def find_memes(vids, trends, articles, community, state, now):
    """영상·검색어에서 갑자기 많이 쓰이는데 뉴스엔 잘 안 나오는 단어 = 밈 후보"""
    state = state or {}
    today = now.strftime("%Y-%m-%d")
    docs = defaultdict(list)                       # 단어 → 그 단어가 나온 영상들
    tagged = defaultdict(int)                      # 해시태그·태그로 쓰인 횟수 (밈일 가능성 ↑)
    for v in vids:
        words = meme_words(v["title"])
        for h in re.findall(r"#([0-9A-Za-z가-힣_]{2,20})", v["title"]):
            tagged[h.upper() if h.isascii() else h] += 1
        for t in v.get("_tags", []):
            t = re.sub(r"\s+", "", t)
            if 2 <= len(t) <= 12 and not t.isdigit():
                t = t.upper() if t.isascii() else t
                if t not in STOPWORDS and t not in MEME_STOP:
                    words.add(t)
                    tagged[t] += 1
        words -= {v["channel"], v["channel"].replace(" ", "")}   # 채널 이름은 빼기
        for w in words:
            docs[w].append({"title": v["title"], "link": v["link"], "channel": v["channel"], "src": "유튜브"})
    for p in community:                            # 커뮤니티 글 제목
        for w in meme_words(p["title"]):
            docs[w].append(p)
    for t in trends:
        for w in meme_words(t["keyword"]) | {t["keyword"].replace(" ", "")}:
            docs[w].append({"title": t["keyword"], "link": (t["news"][0]["link"] if t["news"] else
                                                             "https://www.google.com/search?q=" + urllib.parse.quote(t["keyword"])),
                            "channel": "구글 검색 급상승", "src": "구글 급상승"})
    news_cnt = defaultdict(int)
    for a in articles:
        for w in meme_words(a["title"]):
            news_cnt[w] += 1

    days = {d: c for d, c in state.get("days", {}).items()
            if d >= (now - timedelta(days=MEME_KEEP_DAYS)).strftime("%Y-%m-%d")}
    past = [d for d in days if d != today]
    first = dict(state.get("first", {}))

    cands = []
    for w, vs in docs.items():
        n = len({x["link"] for x in vs})
        if n < 3 or n > max(10, (len(vids) + len(community)) * 0.25):  # 너무 흔한 단어는 제외
            continue
        srcs = {x["src"] for x in vs}
        if news_cnt[w] > n:                        # 뉴스에 더 많이 나오면 '밈' 보다는 '뉴스'
            continue
        hist = sum(days[d].get(w, 0) for d in past) / len(past) if past else 0
        novelty = n / (1 + hist)
        if past and novelty < 2:                  # 예전부터 늘 많이 쓰이던 단어는 제외
            continue
        first.setdefault(w, today)
        # 화제성 점수: 새로움 + 쓰인 곳 수 + 해시태그 + 여러 출처에서 동시에(교차) - 뉴스 비중
        cands.append((novelty * 2 + n + min(tagged[w], n) * 2 + (len(srcs) - 1) * 4 - news_cnt[w] * 0.5,
                      w, n, vs))
    cands.sort(key=lambda x: (-x[0], x[1]))

    out, used = [], []
    for score, w, n, vs in cands:
        links = {x["link"] for x in vs}
        if any(len(links & u) / len(links | u) > 0.6 for u in used):
            continue                               # 거의 같은 영상들에서 나온 단어는 하나만
        used.append(links)
        by_src = defaultdict(int)
        for x in vs:
            by_src[x["src"]] += 1
        picks, seen_src = [], set()                # 출처가 골고루 보이게 예시 고르기
        for x in vs:
            if x["src"] not in seen_src:
                picks.append(x); seen_src.add(x["src"])
        picks += [x for x in vs if x not in picks]
        out.append({"word": w, "count": n, "news": news_cnt[w], "first": first[w],
                    "sources": dict(sorted(by_src.items(), key=lambda kv: -kv[1])),
                    "samples": [{"title": x["title"], "link": x["link"], "channel": x["channel"]}
                                for x in picks[:4]]})
        if len(out) >= MEME_N:
            break

    days[today] = {**days.get(today, {}),
                   **{w: max(len({x["link"] for x in vs}), days.get(today, {}).get(w, 0))
                      for w, vs in docs.items() if len(vs) >= 2}}
    first = {w: d for w, d in first.items() if d >= min(days)}
    return out, {"days": days, "first": first}


def read_meme_dictionary():
    """memes.md 에 직접 쓴 밈 사전을 읽어요. (## 단어 / 뜻: / 예문: / 유래: / 날짜: / 출처: / 글: / 이미지: / 영상:)"""
    path = ROOT / "memes.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    keys = {"뜻": "meaning", "예문": "example", "유래": "origin", "날짜": "date", "출처": "source", "글": "page", "이미지": "img", "영상": "video"}
    items = []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        it = {"word": lines[0].strip(), "meaning": "", "example": "", "origin": "", "date": "", "source": "", "page": "", "img": "", "video": ""}
        cur = None
        for ln in lines[1:]:
            m = re.match(r"^\s*(뜻|예문|유래|날짜|출처|글|이미지|영상)\s*[:：]\s*(.*)$", ln)
            if m:
                cur = keys[m.group(1)]
                it[cur] = m.group(2).strip()
            elif cur and ln.strip() and not ln.startswith("#"):
                it[cur] += "\n" + ln.strip()
        if it["word"] and it["meaning"] and not it["word"].startswith("("):
            items.append(it)
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


# ───────────── 기사 대표 사진 (작은 썸네일용) ─────────────
def google_to_url(link):
    """구글 뉴스 링크 안에 원문 주소가 들어 있으면 꺼내요 (옛 형식만 가능)"""
    m = re.search(r"/articles/([A-Za-z0-9_-]+)", link)
    if not m:
        return ""
    try:
        raw = base64.urlsafe_b64decode(m.group(1) + "=" * (-len(m.group(1)) % 4))
    except Exception:
        return ""
    u = re.search(rb"https?://[\x21-\x7e]+", raw)
    return u.group(0).decode("ascii", "ignore") if u else ""


def kakao_url(title, source):
    """카카오 검색 API로 같은 제목의 원문 주소 찾기 (KAKAO_REST_KEY 가 있을 때만)"""
    if not KAKAO_KEY:
        return ""
    q = urllib.parse.urlencode({"query": title, "size": 3})
    req = urllib.request.Request("https://dapi.kakao.com/v2/search/web?" + q,
                                 headers={"Authorization": "KakaoAK " + KAKAO_KEY})
    with urllib.request.urlopen(req, timeout=10) as r:
        docs = json.loads(r.read()).get("documents", [])
    key = normalize(title)[:20]
    for d in docs:
        if key and key in normalize(re.sub(r"<[^>]+>", "", d.get("title", ""))):
            return d.get("url", "")
    return ""


def og_image(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (issue-pickle link preview)"})
    with urllib.request.urlopen(req, timeout=10) as r:
        final = r.geturl()
        page = r.read(400_000).decode("utf-8", "ignore")
    if "news.google.com" in urllib.parse.urlparse(final).netloc:
        return ""
    for pat in (r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
                r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)'):
        m = re.search(pat, page, re.I)
        if m:
            img = urllib.parse.urljoin(final, htmllib.unescape(m.group(1).strip()))
            if img.startswith("http") and not re.search(r"logo|default|noimage|no_image|blank", img, re.I):
                return img.replace("http://", "https://", 1)
    return ""


PRESS_FILE = Path(__file__).parent / "press.txt"


def press_key(title):
    return normalize(re.sub(r"\[[^\]]*\]", "", title))[:24]


CAT_BY_NAME = CAT_BY_NAME_INIT   # '연예' → 'ent'


def read_press():
    """press.txt: 언론사 | 분야 | RSS 주소  (분야는 연예·스포츠·… 또는 - )"""
    out = []
    if not PRESS_FILE.exists():
        return out
    for line in PRESS_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "|" not in line:
            continue
        parts = [x.strip() for x in line.split("|")]
        name, cat, url = (parts[0], parts[1], parts[2]) if len(parts) >= 3 else (parts[0], "-", parts[1])
        out.append((name, CAT_BY_NAME.get(cat), url))
    return out


def collect_press(cutoff):
    """분야별 주 매체의 공식 RSS 기사 (원문 주소가 그대로 있어서 대표 사진을 바로 가져올 수 있어요)"""
    arts = []
    for name, cid, url in read_press():
        try:
            got = 0
            for it in ET.fromstring(fetch(url)).iter("item"):
                title, link = text(it, "title").strip(), text(it, "link").strip()
                if not title or not link.startswith("http"):
                    continue
                try:
                    pub = parsedate_to_datetime(text(it, "pubDate")).astimezone(KST).isoformat(timespec="minutes")
                except Exception:
                    continue                                   # 날짜 없는 기사는 최신인지 몰라서 뺌
                if pub < cutoff or "포토" in title[:6]:
                    continue
                img = ""
                for el in it.iter():
                    tag = local(el.tag)
                    if tag in ("content", "thumbnail", "enclosure") and el.get("url", "").startswith("http"):
                        if tag != "enclosure" or "image" in el.get("type", "image"):
                            img = el.get("url"); break
                if not img:
                    m = re.search(r'<img[^>]+src=["\']([^"\']+)', text(it, "description") or "")
                    img = m.group(1) if m and m.group(1).startswith("http") else ""
                a = {"title": title, "source": name, "link": link, "time": pub}
                if img:
                    a["img"] = img
                arts.append((a, cid))
                got += 1
            print(f"[언론사 RSS] {name}: 기사 {got}건")
        except Exception as e:
            print(f"[언론사 RSS] {name}: 실패 ({type(e).__name__}) {url}", file=sys.stderr)
    return arts


def attach_images(result, cache, now, press_arts):
    """순위에 나온 이슈마다, 언론사 RSS 와 제목이 같은 기사를 찾아 대표 사진을 붙여요"""
    keep = (now - timedelta(hours=IMG_KEEP_H)).isoformat()
    cache = {k: v for k, v in (cache or {}).items() if v[1] >= keep}
    if not ARTICLE_IMAGES:
        return cache
    press = {press_key(a["title"]): (a["link"], a.get("img", "")) for a in press_arts}
    groups = [result["rising"], result["top"], result["people"]] + [c["issues"] for c in result["categories"].values()]
    groups.append(result.get("search") or [])                          # 검색 급상승: 관련 기사 사진
    groups.append([{"_arts": [b]} for b in (result.get("buzz") or {}).get("auto") or []])   # 커뮤니티 화제: 기사 자체에 사진을 붙여요
    tried = found = 0
    for g in groups:
        for it in g:
            arts = sorted(it.get("_arts") or it.get("news") or [], key=lambda a: a.get("time", ""), reverse=True)
            for a in arts:
                if a["link"] in cache and cache[a["link"]][0]:
                    a["img"] = cache[a["link"]][0]; break
                if "news.google.com" not in a["link"]:
                    hit = (a["link"], a.get("img", ""))       # 주 매체 기사: 원문 주소를 이미 알아요
                else:
                    hit = press.get(press_key(a["title"]))
                if not hit and KAKAO_KEY and tried < IMG_NEW_PER_RUN and a is arts[0]:
                    try:
                        u = kakao_url(a["title"], a["source"])
                        hit = (u, "") if u else None
                    except Exception:
                        hit = None
                if not hit or a["link"] in cache:
                    continue
                url, img = hit
                if not img and tried < IMG_NEW_PER_RUN:
                    tried += 1
                    try:
                        img = og_image(url)
                    except Exception:
                        img = ""
                cache[a["link"]] = [img, now.isoformat(timespec="minutes")]
                if img:
                    found += 1
                    a["img"] = img
                    break
            im = next((a["img"] for a in arts if a.get("img")), "")
            if im:
                it["img"] = im
                for n in it.get("news", []):            # 화면에 나가는 기사 목록에도 표시
                    c = cache.get(n["link"])
                    if c and c[0]:
                        n["img"] = c[0]
    with_img = sum(1 for g in groups for it in g if it.get("img"))
    print(f"기사 사진: 원문 확인 {tried}건 · 새로 찾음 {found}건 · 사진 붙은 이슈 {with_img}개")
    return cache

# ───────────── 이슈 상세 페이지 데이터 ─────────────
COMMUNITY_PER_ISSUE = 5   # 상세 페이지에 보여 줄 커뮤니티 관련글 수
DETAIL_NEWS = 8      # 상세 페이지에 보여줄 관련 기사 수
HIST_HOURS = 8       # 온도 추이 그래프에 남길 시간


def traffic_score(t):
    n = int(re.sub(r"[^0-9]", "", t or "") or 0)
    return 100 if n >= 50000 else 80 if n >= 20000 else 65 if n >= 10000 else 50 if n >= 5000 else 35


def build_details(result, kw_arts, vids, community, now, old_hist):
    c3 = (now - timedelta(hours=3)).isoformat()
    c6 = (now - timedelta(hours=6)).isoformat()
    keep = (now - timedelta(hours=HIST_HOURS)).isoformat()
    top_map = {it["keyword"]: it for it in result["top"]}
    cat_map = {}
    for cid, c in result["categories"].items():
        for it in c["issues"]:
            cat_map.setdefault(it["keyword"], (cid, c["name"], it["rank"]))
    entries, hist = {}, {}

    def add(it, kind):
        kw = it["keyword"]
        if kw in entries:
            return
        arts = kw_arts.get(kw) or it.get("_arts") or it.get("news") or []
        if not arts:
            return
        news = sorted(arts, key=lambda a: a["time"], reverse=True)
        src_cnt = defaultdict(int)
        for a in arts:
            src_cnt[a["source"]] += 1
        last3 = sum(1 for a in arts if a["time"] >= c3)
        prev3 = sum(1 for a in arts if c6 <= a["time"] < c3)
        low = kw.lower()
        vmatch = [v for v in vids if low in v["title"].lower()]
        # 커뮤니티 관련글: 최근 24시간 커뮤니티 글 '제목'에 이 키워드가 그대로 들어 있는 글
        # (영문 키워드는 'AI'가 'MAIL'에 걸리지 않게 단어 단위로만)
        if kw.isascii():
            pat = re.compile(r"(?<![A-Za-z])" + re.escape(low) + r"(?![A-Za-z])")
            cmatch = [p for p in community if pat.search(p["title"].lower())]
        else:
            cmatch = [p for p in community if low in p["title"].lower()]
        cmatch.sort(key=lambda p: p.get("time", ""), reverse=True)
        tmatch = [t for t in result["search"] if len(kw) >= 2 and (low in t["keyword"].lower() or t["keyword"].lower() in low)]
        base = top_map.get(kw, it)
        temp = base.get("temp", 50)
        cat = cat_map.get(kw)
        evidence = ([{"type": "커뮤니티", "title": p["title"], "link": p["link"], "src": p["channel"]} for p in cmatch[:3]]
                    + [{"type": "검색", "title": f"구글 검색 급상승 '{t['keyword']}' ({t['traffic']})",
                        "link": "https://www.google.com/search?q=" + urllib.parse.quote(t["keyword"]), "src": "구글 트렌드"}
                       for t in tmatch[:1]]
                    + [{"type": "영상", "title": v["title"], "link": v["link"], "src": v["channel"]} for v in vmatch[:2]])
        entries[kw] = {
            "keyword": kw, "title": base.get("title") or it.get("title") or kw,
            "kind": kind, "temp": temp, "headline": news[0]["title"],
            "articles": len(arts), "sources": len(src_cnt),
            "source_names": [k for k, _ in sorted(src_cnt.items(), key=lambda kv: -kv[1])[:3]],
            "rank": base.get("rank") if kw in top_map else None,
            "change": top_map[kw].get("change") if kw in top_map else None,
            "cat": {"id": cat[0], "name": cat[1], "rank": cat[2]} if cat else None,
            "last3": last3, "prev3": prev3, "ratio": round(last3 / prev3, 1) if prev3 else None,
            "signals": {"news": min(100, round(len(src_cnt) * 7 + len(arts) * 2)),
                        "search": traffic_score(tmatch[0]["traffic"]) if tmatch else None,
                        "video": min(100, len(vmatch) * 25) if vmatch else None,
                        "community": min(100, len(cmatch) * 15) if cmatch else None},
            "evidence": evidence,
            "community": [{"title": p["title"], "link": p["link"], "src": p["channel"], "time": p.get("time", "")}
                          for p in cmatch[:COMMUNITY_PER_ISSUE]],
            "news": [dict({"title": a["title"], "source": a["source"], "link": a["link"], "time": a["time"]},
                          **({"img": a["img"]} if a.get("img") else {}))
                     for a in news[:DETAIL_NEWS]],
        }
        entries[kw]["img"] = next((a["img"] for a in news if a.get("img")), "")
        h = [x for x in (old_hist or {}).get(kw, []) if x[0] >= keep]
        stamp = now.isoformat(timespec="minutes")
        if h and h[-1][0] == stamp:                      # 같은 시각에 두 번 돌면 마지막 값만
            h.pop()
        h.append([stamp, temp])
        hist[kw] = h
        entries[kw]["hist"] = h

    for it in result["top"]:
        add(it, "이슈")
    for it in result["rising"]:
        add(it, "이슈")
    for c in result["categories"].values():
        for it in c["issues"]:
            add(it, "이슈")
    for it in result["people"]:
        add(it, "인물")
    cats = {cid: {"name": c["name"], "list": [it["keyword"] for it in c["issues"]]}
            for cid, c in result["categories"].items()}
    sites = sorted({name for name, _ in read_sources()})
    return {"updated": result["updated"], "issues": entries, "cats": cats, "community_sites": sites}, hist


# ───────────── 브리핑 (첫 화면 맨 위 '지금 한눈에') ─────────────
# 이번 수집 결과를 지난번과 비교해서, 사람이 쓰지 않아도 되는 '사실만' 몇 줄로 정리해요.
BRIEF_KEEP = 6          # 지난 브리핑을 몇 개까지 보관할지 (화면에서 '지난 브리핑'으로 볼 수 있음)
BRIEF_HOURS = [0, 9, 12, 15, 18, 21]   # 브리핑을 새로 쓰는 시각 (새벽 3·6시는 뉴스가 적어 건너뜀)


def brief_slot(now):
    """지금 시각이 속한 브리핑 시각 (예: 14시 → 12시)"""
    h = max([x for x in BRIEF_HOURS if x <= now.hour] or [0])
    return now.replace(hour=h, minute=0, second=0, microsecond=0)


def update_brief(result, old, now):
    """정해진 시각이 바뀌었을 때만 새 브리핑을 쓰고, 그 사이에는 이전 브리핑을 그대로 둬요"""
    slot = brief_slot(now).isoformat(timespec="minutes")
    ob = old.get("brief") or {}
    if ob.get("slot") == slot:
        return ob, old.get("brief_hist") or [ob], old.get("_brief_snap") or []
    prev_top = old.get("_brief_snap") or []               # 지난 브리핑 시각의 순위와 비교
    brief, hist = make_brief(result, {"top": prev_top, "brief_hist": old.get("brief_hist")}, now)
    brief["slot"] = slot
    hist[0] = brief
    snap = [{"keyword": it["keyword"], "title": it.get("title", "")} for it in result.get("top", [])[:10]]
    return brief, hist, snap


def make_brief(result, old, now):
    name = lambda it: it.get("title") or it["keyword"]
    top, lines = result.get("top", []), []
    if top:
        t = top[0]
        lines.append({"icon": "🔥", "label": "지금 1위", "text": name(t), "sub": t.get("headline", ""),
                      "k": t["keyword"]})
    old_top = {it["keyword"] for it in (old.get("top") or [])[:10]}
    new_in = [it for it in top[:10] if it["keyword"] not in old_top] if old_top else []
    if new_in:
        lines.append({"icon": "🆕", "label": "새로 10위 안에", "text": ", ".join(name(it) for it in new_in[:3]),
                      "k": new_in[0]["keyword"]})
    up = [it for it in top[:10] if isinstance(it.get("change"), int) and it["change"] >= 3]
    up = [it for it in up if it not in new_in and it is not (top[0] if top else None)]
    if up:
        u = max(up, key=lambda it: it["change"])
        lines.append({"icon": "⬆️", "label": "순위 급상승", "text": f"{name(u)} ({u['change']}계단 ▲)", "k": u["keyword"]})
    r = (result.get("rising") or [None])[0]
    if r:
        how = f"3시간 전보다 {r['ratio']}배" if r.get("ratio") else "새로 등장"
        lines.append({"icon": "📈", "label": "가장 빨리 뜨는 중", "text": f"{name(r)} ({how})", "k": r["keyword"]})
    now_kw = {x["keyword"] for x in top[:10]}
    gone = [it for it in (old.get("top") or [])[:5] if it["keyword"] not in now_kw]
    if gone and SHOW_GONE:                 # '관심이 식은 이슈' 줄은 기본으로 꺼 둬요 (위쪽 SHOW_GONE)
        lines.append({"icon": "💤", "label": "관심이 식은 이슈", "text": ", ".join(name(it) for it in gone[:2])})
    if result.get("search"):
        lines.append({"icon": "🔎", "label": "검색 1위", "text": result["search"][0]["keyword"]})
    b = (result.get("buzz") or {}).get("auto") or []
    if b:
        lines.append({"icon": "💬", "label": "커뮤니티 화제", "text": b[0]["title"], "link": b[0]["link"]})
    brief = {"time": now.isoformat(timespec="minutes"), "lines": lines[:6]}
    hist = [brief] + [x for x in (old.get("brief_hist") or []) if x.get("time", "") < brief["time"] and x.get("slot")]
    return brief, hist[:BRIEF_KEEP]


# ───────────── 날짜별 '오늘의 이슈' 기록 (seo.py 가 b/날짜.html 페이지로 만들어요) ─────────────
DAILY_KEEP_DAYS = 60     # 며칠 치를 보관할지


def update_daily(result, old, now):
    daily = dict(old.get("_daily") or {})
    day = now.strftime("%Y-%m-%d")
    d = daily.get(day) or {"top": {}, "briefs": [], "runs": 0}
    d["runs"] += 1
    hm = now.strftime("%H:%M")
    for i, it in enumerate(result.get("top", [])[:10]):
        rec = d["top"].get(it["keyword"]) or {"title": it.get("title") or it["keyword"], "best": i + 1, "count": 0,
                                              "headline": it.get("headline", ""), "cat": it.get("cat", ""),
                                              "first": hm, "best_at": hm, "titles": [], "words": {}}
        rec["count"] += 1
        rec["last"], rec["last_rank"] = hm, i + 1
        if i + 1 < rec["best"] or (i + 1 == rec["best"] and not rec.get("best_at")):
            rec["best"], rec["best_at"] = i + 1, hm
            rec["headline"] = it.get("headline", "") or rec["headline"]
        # 서로 다른 언론사 제목 최대 3개 (원문 주소가 있는 기사 먼저)
        seen = {t["source"] for t in rec.setdefault("titles", [])}
        for n in sorted(it.get("news", []), key=lambda n: "news.google.com" in n.get("link", "")):
            if len(rec["titles"]) >= 3:
                break
            if n.get("source") and n["source"] not in seen and n.get("title"):
                rec["titles"].append({"title": n["title"], "source": n["source"], "link": n.get("link", "")})
                seen.add(n["source"])
        # 제목에 함께 나온 단어 (이슈를 한눈에 알게)
        w = rec.setdefault("words", {})
        srcs = {n.get("source", "") for n in it.get("news", [])}
        for n in it.get("news", []):
            for t in keywords(n.get("title", "")):
                if t != it["keyword"] and t not in it["keyword"] and t not in QUERY_WORDS and t not in srcs \
                        and not any(t in x for x in srcs):
                    w[t] = w.get(t, 0) + 1
        rec["words"] = dict(sorted(w.items(), key=lambda kv: -kv[1])[:8])
        d["top"][it["keyword"]] = rec
    b = result.get("brief")
    if b and b.get("slot", "")[:10] == day and all(x.get("slot") != b["slot"] for x in d["briefs"]):
        d["briefs"].append({"slot": b["slot"], "lines": b["lines"]})
    d["last"] = now.isoformat(timespec="minutes")
    daily[day] = d
    for k in sorted(daily)[:-DAILY_KEEP_DAYS]:
        daily.pop(k)
    return daily


# ───────────── 실행 ─────────────
def main():
    now = datetime.now(KST)
    cutoff = (now - timedelta(hours=MAX_AGE_HOURS)).isoformat()

    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            old = {}

    # 분야별 주 매체 기사를 먼저 넣어요. 구글 뉴스에 같은 기사가 있으면 원문 주소가 있는 이쪽을 써요.
    press_pairs = collect_press(cutoff)
    press_arts = [a for a, _ in press_pairs]
    by_title, press_cat = {}, {}
    for a, cid in press_pairs:
        by_title.setdefault(normalize(a["title"]), a)
        if cid:
            press_cat.setdefault(a["link"], cid)
    # 분야를 정한 주 매체 기사만 이슈 수집에 넣고, 분야가 '-' 인 RSS는 사진 찾기에만 써요
    all_seen = {k: a for k, a in by_title.items() if a["link"] in press_cat}
    per_cat = {cid: [] for cid in CATEGORIES}
    for k, a in collect_feeds(GENERAL_FEEDS, cutoff).items():
        all_seen.setdefault(k, by_title.get(k, a))
    for cid, cat in CATEGORIES.items():
        seen = collect_feeds(cat["feeds"], cutoff)
        for k, a in seen.items():
            seen[k] = by_title.get(k, a)
        for k, a in by_title.items():
            if press_cat.get(a["link"]) == cid:
                seen.setdefault(k, a)
        per_cat[cid] = list(seen.values())
        for k, a in seen.items():
            all_seen.setdefault(k, a)
        print(f"{cat['name']}: 기사 {len(seen)}건")
    articles = list(all_seen.values())
    print(f"전체: 기사 {len(articles)}건")
    link_cat = {}                                          # 기사 → 처음 잡힌 분야
    for cid, arts in per_cat.items():
        for a in arts:
            link_cat.setdefault(a["link"], cid)

    if not articles:
        print("[오류] 기사를 하나도 못 가져왔어요. 이전 데이터를 그대로 둡니다.", file=sys.stderr)
        sys.exit(1)

    people_extract = find_people(articles)
    person_names = frozenset(people_extract.names)
    trends = collect_trends()
    TREND_BOOST.clear()
    TREND_BOOST.update(trend_boost_map(trends))
    print(f"보도자료로 본 기사: {sum(1 for a in articles if is_pr(a))}건 / 급상승 가산 단어: {len(TREND_BOOST)}개")
    raw = score_terms(articles, keywords)
    scored, single = title_rule(raw, person_names, link_cat)
    print(f"한 단어 제목이라 점수를 깎은 키워드: {len(single)}개 "
          f"(위쪽 10개: {', '.join([kw for _, kw, *_ in raw if kw in single][:10])})")
    old_cats = old.get("categories", {})
    top_list = pick(scored, TOP_N, old_rank_map(old.get("top")), link_cat, TOP_CAT_CAP)

    result = {
        "updated": now.isoformat(timespec="minutes"),
        "total_articles": len(articles),
        "total_sources": len({a["source"] for a in articles}),
        "top": top_list,
        "rising": rising(scored, now, link_cat, single, top_list[:RISING_SKIP_TOP]),
        "people": pick(score_terms(articles, people_extract), PEOPLE_N,
                       old_rank_map(old.get("people")), link_cat, PEOPLE_CAT_CAP, 5),
        "categories": {
            cid: {"name": cat["name"],
                  "issues": pick(title_rule(score_terms(per_cat[cid], keywords), person_names)[0], CAT_N,
                                 old_rank_map(old_cats.get(cid, {}).get("issues")))}
            for cid, cat in CATEGORIES.items()
        },
        "search": trends,
    }
    result["wiki"] = collect_wiki(old.get("wiki"), now)
    vids, result["_yt"] = collect_youtube(old.get("_yt"), now)
    result["videos"] = vids[:10]
    result["_nf"] = collect_netflix(old.get("_nf"), now)

    community = collect_community(now)
    result["buzz"] = {"picks": read_buzz_picks(now), "auto": collect_buzz(cutoff)}
    memes, result["_meme"] = find_memes(vids, result["search"], articles, community, old.get("_meme"), now)
    result["_dl"] = datalab_check([m["word"] for m in memes[:10]], old.get("_dl"), now)
    # 네이버 검색량이 실제로 늘어난 단어를 위로 (결과 숫자 자체는 화면에 내보내지 않음)
    memes.sort(key=lambda m: -(min(result["_dl"].get(m["word"]) or 1, 5) >= 1.5))
    for v in vids:
        v.pop("_tags", None)

    # 기사 대표 사진 (기사 목록 앞 작은 썸네일)
    result["_img"] = attach_images(result, old.get("_img"), now, press_arts)

    # 이슈 상세 페이지용 데이터 (issues.json) + 온도 기록
    kw_arts = {kw: arts for _, kw, _, _, arts in raw}
    details, result["_hist"] = build_details(result, kw_arts, vids, community, now, old.get("_hist"))
    clean(result["top"]); clean(result["people"])
    for c in result["categories"].values():
        clean(c["issues"])
    result["brief"], result["brief_hist"], result["_brief_snap"] = update_brief(result, old, now)
    result["_daily"] = update_daily(result, old, now)
    # 검색 노출용: 직접 쓴 이슈 해설 페이지 + 사이트맵 + RSS (seo.py)
    try:
        import seo
        link_map, result["_explain"] = seo.build_all(details, old.get("_explain"),
                                                     now.isoformat(timespec="minutes"), read_meme_dictionary(),
                                                     result["_daily"])
        result["calendar"] = seo.calendar_home(now.strftime("%Y-%m-%d"))
        for kw, v in link_map.items():
            details["issues"][kw]["explain"] = v
        for g in [result["top"], result["rising"], result["people"]] + [c["issues"] for c in result["categories"].values()]:
            for it in g:
                if it["keyword"] in link_map:
                    it["explain"] = link_map[it["keyword"]]["url"]
    except Exception as ex:
        print(f"[경고] 해설 페이지 만들기 실패 ({type(ex).__name__}: {ex})", file=sys.stderr)
        result["_explain"] = old.get("_explain", {})
    ISSUES_OUT.write_text(json.dumps(details, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    MEME_OUT.write_text(json.dumps({"updated": result["updated"], "candidates": memes,
                                    "dictionary": read_meme_dictionary()},
                                   ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    content = {"updated": result["updated"], "youtube": vids,
               "youtube_hours": YT_WINDOW_H,
               "boxoffice": collect_boxoffice(now), "netflix": result["_nf"]}

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    CONTENT_OUT.write_text(json.dumps(content, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    bo, nf = content["boxoffice"], content["netflix"]
    print(f"저장 완료: 이슈 {len(result['top'])} · 인물 {len(result['people'])} · "
          f"검색어 {len(result['search'])} · 영상 {len(vids)} · "
          f"박스오피스 {len(bo['items']) if bo else 0} · 넷플릭스 {len(nf['tv']) + len(nf['films']) if nf else 0} · "
          f"밈 후보 {len(memes)}")


if __name__ == "__main__":
    main()
