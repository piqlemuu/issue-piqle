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
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

# ═════════════ 설정 (여기만 바꿔도 됩니다) ═════════════
TOP_N = 20            # '지금 뜨는 이슈' 개수
CAT_N = 10            # 분야별 이슈 개수
PEOPLE_N = 10         # 이슈人 개수
RISING_N = 8          # 치고 올라오는 이슈 개수
NEWS_PER_ISSUE = 5    # 이슈마다 보여줄 관련 기사 수
MAX_AGE_HOURS = 24    # 이 시간보다 오래된 기사는 버림
RISING_HOURS = 2      # '최근' 으로 볼 시간 (치고 올라오는 이슈)

G = "https://news.google.com/rss"
Q = "hl=ko&gl=KR&ceid=KR:ko"
def topic(name): return f"{G}/headlines/section/topic/{name}?{Q}"
def search(word): return f"{G}/search?q={urllib.parse.quote(word)}+when:1d&{Q}"

GENERAL_FEEDS = [f"{G}?{Q}"]   # 분야 없이 전체 주요 뉴스

# 분야 추가·삭제는 여기서. (화면에는 자동으로 반영돼요)
CATEGORIES = {
    "pol":  {"name": "정치",    "feeds": [search("정치"), search("국회")]},
    "eco":  {"name": "경제",    "feeds": [topic("BUSINESS"), search("경제")]},
    "soc":  {"name": "사회",    "feeds": [topic("NATION"), search("사회")]},
    "ent":  {"name": "연예",    "feeds": [topic("ENTERTAINMENT"), search("연예")]},
    "spo":  {"name": "스포츠",  "feeds": [topic("SPORTS")]},
    "it":   {"name": "IT·과학", "feeds": [topic("TECHNOLOGY"), topic("SCIENCE")]},
    "wor":  {"name": "세계",    "feeds": [topic("WORLD")]},
}

TRENDS_URL = "https://trends.google.com/trending/rss?geo=KR"
NETFLIX_URL = "https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv"
NETFLIX_EVERY_H = 12  # 넷플릭스는 주 1회 바뀌어서 12시간에 한 번만 받음
YT_WINDOW_H = 6       # 유튜브: 최근 몇 시간 동안 늘어난 조회수로 순위를 매길지
YT_CATS = {"1": "영화·애니", "10": "음악", "17": "스포츠", "20": "게임", "22": "인물",
           "23": "엔터", "24": "엔터", "25": "뉴스·정치"}   # 나머지는 '기타'

# 비밀 키 (GitHub Secrets 에 넣으면 자동으로 들어와요. 없으면 그 섹션만 빠져요)
YOUTUBE_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()
KOBIS_KEY = os.environ.get("KOBIS_API_KEY", "").strip()

# 순위에서 뺄 흔한 단어 (이상한 키워드가 순위에 뜨면 여기에 추가하세요)
STOPWORDS = set("""
기자 뉴스 속보 단독 종합 오늘 내일 어제 올해 지난 이번 관련 대한 위해 통해 위한
있는 없는 한다 했다 하는 하고 것으로 대해 이후 가능 사진 영상 포토 공개 발표 진행
예정 최근 오후 오전 확인 결국 논란 기준 전망 이유 상황 우리 국내 해외 정부 한국
대표 시장 사람 모두 다시 이제 계속 직접 지금 이미 함께 가장 무슨 어떻게 왜 연예 경제
첫날 결과 확정 기대 돌파 등극 이상 이하 이어 따라 만에 억원 만원 그룹 회장 사장
정치 사회 세계 스포츠 국회 대통령 장관 의원 주요 전국 지역 서울 사실 문제 추진
피해 사태 사고 조사 착수 수용 상정 불발 공방 활약 참석 주연 출연 발매 매진 시작 급증 급등
급락 상승 하락 증가 감소 신제품 이용자 첫방송 방송 소식 입장 반응 의혹 혐의 체포 구속 사망
개최 국민 제정 지원 요청 수상 확대 촉구 사업 송치 VS 의장 여성 위기 강화 추가 개선 협력
선정 운영 참여 마련 실시 도입 점검 대응 논의 합의 반대 찬성 비판 지적 강조 주장 제안 검토
출범 개막 개장 오픈 기념 행사 축제 설명 판결 선고 기소 수사 조사 압수수색 혐의 재판 처리
통과 의결 가결 부결 경신 기록 달성 유지 전환 변경 연장 중단 재개 완료 성공 실패 공식
이유 방법 모습 의미 효과 영향 우려 가운데 사이 직후 직전 당일 연속 이틀 사흘 매년 처음
청년 시민 주민 학생 아이 부모 노인 어린이 가족 남성 여성 국민들 업계 기업 회사 단체
씨 등 것 수 때 중
""".split())

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
    return (c.text or "").strip() if c is not None else ""


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
        if len(w) < 2 or re.match(r"^\d", w) or w in STOPWORDS:
            continue
        found.add(w.upper() if w.isascii() else w)
    return found


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


def score_terms(articles, extract, min_sources=2):
    """단어별로 (점수, 단어, 기사 수, 매체 수, 기사 목록) 을 계산"""
    stats = defaultdict(list)
    for a in articles:
        for kw in extract(a["title"]):
            stats[kw].append(a)
    out = []
    for kw, arts in stats.items():
        n_src = len({a["source"] for a in arts})
        if n_src >= min_sources:
            out.append((n_src * 3 + len(arts), kw, len(arts), n_src, arts))
    out.sort(key=lambda x: (-x[0], x[1]))
    return out


def pick(scored, n, old_ranks):
    """겹치는 이슈를 합치고 상위 n 개를 고른 뒤 온도·순위변화를 붙임"""
    issues, used = [], []
    for score, kw, n_art, n_src, arts in scored:
        ids = {a["link"] for a in arts}
        if any(len(ids & u) / len(ids) > 0.6 for u in used):
            continue                       # 이미 뽑힌 이슈와 기사가 거의 같음 → 같은 이슈
        if any((kw in it["keyword"] or it["keyword"] in kw)
               and len(ids & {a["link"] for a in it["_arts"]}) / len(ids) > 0.3 for it in issues):
            continue                       # '의장' 과 '국회의장' 처럼 겹치는 단어 → 하나만
        used.append(ids)
        news = sorted(arts, key=lambda a: a["time"], reverse=True)[:NEWS_PER_ISSUE]
        issues.append({"keyword": kw, "score": score, "articles": n_art, "sources": n_src,
                       "headline": news[0]["title"], "news": news, "_arts": arts})
        if len(issues) >= n:
            break
    top = issues[0]["score"] if issues else 1
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


def rising(scored, now):
    """최근 RISING_HOURS 시간에 기사가 몰린 이슈"""
    recent_cut = (now - timedelta(hours=RISING_HOURS)).isoformat()
    cand = []
    for score, kw, n_art, n_src, arts in scored[:80]:
        recent = [a for a in arts if a["time"] >= recent_cut]
        if len(recent) >= 2 and len(recent) / n_art >= 0.5:
            cand.append((len(recent) * 3 + n_src, kw, n_art, n_src, arts, len(recent)))
    cand.sort(key=lambda x: (-x[0], x[1]))
    out, used = [], []
    for s, kw, n_art, n_src, arts, n_recent in cand:
        ids = {a["link"] for a in arts}
        if any(len(ids & u) / len(ids) > 0.7 for u in used):
            continue
        used.append(ids)
        news = sorted(arts, key=lambda a: a["time"], reverse=True)
        out.append({"keyword": kw, "recent": n_recent, "articles": n_art, "sources": n_src,
                    "headline": news[0]["title"], "news": news[:NEWS_PER_ISSUE]})
        if len(out) >= RISING_N:
            break
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
        for _ in range(4):                                   # 50개씩 4번 = 200개
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
        })
    vids.sort(key=lambda x: -x.pop("_est"))
    for i, x in enumerate(vids, 1):
        x["rank"] = i
        x["change"] = (0 if old_ranks is None else
                       old_ranks[x["id"]] - i if x["id"] in old_ranks else "new")

    keep = (now - timedelta(hours=YT_WINDOW_H + 1)).isoformat()
    snaps = [s_ for s_ in snaps if s_["t"] >= keep]
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

    all_seen, per_cat = collect_feeds(GENERAL_FEEDS, cutoff), {}
    for cid, cat in CATEGORIES.items():
        seen = collect_feeds(cat["feeds"], cutoff)
        per_cat[cid] = list(seen.values())
        for k, a in seen.items():
            all_seen.setdefault(k, a)
        print(f"{cat['name']}: 기사 {len(seen)}건")
    articles = list(all_seen.values())
    print(f"전체: 기사 {len(articles)}건")

    if not articles:
        print("[오류] 기사를 하나도 못 가져왔어요. 이전 데이터를 그대로 둡니다.", file=sys.stderr)
        sys.exit(1)

    scored = score_terms(articles, keywords)
    old_cats = old.get("categories", {})

    result = {
        "updated": now.isoformat(timespec="minutes"),
        "total_articles": len(articles),
        "total_sources": len({a["source"] for a in articles}),
        "top": clean(pick(scored, TOP_N, old_rank_map(old.get("top")))),
        "rising": rising(scored, now),
        "people": clean(pick(score_terms(articles, find_people(articles)), PEOPLE_N,
                             old_rank_map(old.get("people")))),
        "categories": {
            cid: {"name": cat["name"],
                  "issues": clean(pick(score_terms(per_cat[cid], keywords), CAT_N,
                                       old_rank_map(old_cats.get(cid, {}).get("issues"))))}
            for cid, cat in CATEGORIES.items()
        },
        "search": collect_trends(),
    }
    vids, result["_yt"] = collect_youtube(old.get("_yt"), now)
    result["videos"] = vids[:10]
    result["_nf"] = collect_netflix(old.get("_nf"), now)

    content = {"updated": result["updated"], "youtube": vids[:200],
               "youtube_hours": YT_WINDOW_H,
               "boxoffice": collect_boxoffice(now), "netflix": result["_nf"]}

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    CONTENT_OUT.write_text(json.dumps(content, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    bo, nf = content["boxoffice"], content["netflix"]
    print(f"저장 완료: 이슈 {len(result['top'])} · 인물 {len(result['people'])} · "
          f"검색어 {len(result['search'])} · 영상 {len(vids)} · "
          f"박스오피스 {len(bo['items']) if bo else 0} · 넷플릭스 {len(nf['tv']) + len(nf['films']) if nf else 0}")


if __name__ == "__main__":
    main()
