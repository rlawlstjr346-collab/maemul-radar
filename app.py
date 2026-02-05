import streamlit as st
import streamlit.components.v1 as components
import urllib.parse
import requests
import re
import difflib
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import html
import math
import random

CHART_BLUE = '#0A84FF'
CHART_BLUE_LIGHT = '#5CA4FF'
CHART_BLUE_FILL = 'rgba(10, 132, 255, 0.2)'
CHART_BLUE_HIGHLIGHT = 'rgba(10, 132, 255, 0.25)'

# 네이버 검색/공유용 (og:image는 대표 이미지 URL 넣으면 링크 미리보기에 표시됨)
SEO_OG_IMAGE = ""

# ------------------------------------------------------------------
# [1] 앱 기본 설정 (RADAR V15.0: Pro Dashboard Cards)
# ------------------------------------------------------------------
st.set_page_config(
    page_title="RADAR",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ------------------------------------------------------------------
# [2] 데이터 로드 - 구글 시트 시세 연동
# ------------------------------------------------------------------
# 시트 URL: .streamlit/secrets.toml 에 google_sheet_url 설정, 없으면 기본값 사용
# 시트 구조: 모델명/키워드 | 시세(5주치) 또는 주차별 컬럼 | 해외평균(USD)
_DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQS8AftSUmG9Cr7MfczpotB5hhl1DgjH4hRCgXH5R8j5hykRiEf0M9rEyEq3uj312a5RuI4zMdjI5Jr/pub?output=csv"

def _get_sheet_url():
    try:
        url = st.secrets.get("google_sheet_url") or st.secrets.get("GOOGLE_SHEET_URL")
        return url if url else _DEFAULT_SHEET_URL
    except Exception:
        return _DEFAULT_SHEET_URL

@st.cache_data(ttl=600)
def load_price_data(nrows=None):
    """시트 lazy load - 검색 시에만 호출. nrows로 행 제한 가능 (secrets: sheet_nrows)"""
    url = _get_sheet_url()
    try:
        limit = nrows
        if limit is None:
            try:
                limit = st.secrets.get("sheet_nrows") or st.secrets.get("SHEET_NROWS")
                limit = int(limit) if limit else None
            except Exception:
                limit = None
        df = pd.read_csv(url, encoding='utf-8-sig', nrows=limit)
        df.columns = df.columns.str.strip().str.replace('\ufeff', '')
        return df
    except Exception:
        return pd.DataFrame()

# ------------------------------------------------------------------
# [3] 로직 (키워드 엔진 V2 + 금융)
# ------------------------------------------------------------------
def get_category_from_sheet(keyword, df):
    """시트에 '분류'/'category' 컬럼이 있으면 매칭된 행의 분류 반환 (우선 사용)"""
    if df is None or df.empty or not keyword or len(str(keyword).strip()) < 2:
        return None
    for col in ['분류', 'category', '카테고리']:
        if col not in df.columns:
            continue
        user_clean = str(keyword).lower().replace(" ", "").strip()
        for _, row in df.iterrows():
            k_val = _get_col(row, '모델명', '키워드', 'keyword')
            if not k_val: continue
            sheet_kw = str(k_val).lower().replace(" ", "").strip()
            if len(sheet_kw) >= 2 and (user_clean in sheet_kw or sheet_kw in user_clean or difflib.SequenceMatcher(None, user_clean, sheet_kw).ratio() > 0.6):
                cat = row.get(col)
                if pd.notna(cat) and str(cat).strip():
                    c = str(cat).strip().upper()
                    if c in ('CAMERA', 'FASHION', 'TECH', 'LIVING', 'GAME'):
                        return c
    return None

def classify_keyword_category(keyword, df=None):
    """
    [Keyword Engine V2 확장] 시트 분류 우선 → 코드 DB로 카테고리 자동 판별
    """
    if df is not None and not df.empty:
        sheet_cat = get_category_from_sheet(keyword, df)
        if sheet_cat:
            return sheet_cat
    k = str(keyword).lower().replace(" ", "")
    
    # === DB: Camera & Gear (확장) ===
    cam_db = [
        '카메라', 'camera', '렌즈', 'lens', '필름', 'film', 'dslr', '미러리스',
        '라이카', 'leica', 'm3', 'm6', 'm11', 'q2', 'q3', 'x100v', 'x100vi',
        '핫셀블라드', 'hasselblad', '핫셀', '500cm', 'x2d',
        '린호프', 'linhof', '테크니카', 'technika',
        '마미야', 'mamiya', 'rz67', 'rb67', '7ii',
        '콘탁스', 'contax', 't2', 't3', 'g1', 'g2',
        '브로니카', 'bronica', '젠자',
        '롤라이', 'rollei', '35s', '35t',
        '페이즈원', 'phaseone', 'iq4',
        '리코', 'ricoh', 'gr2', 'gr3', 'gr3x', 'gr4',
        '펜탁스', 'pentax', 'k1000', 'lx', '67',
        '보이그랜더', 'voigtlander', '녹턴', '울트론',
        '캐논', 'canon', '니콘', 'nikon', '소니', 'sony', '후지', 'fujifilm',
        '올림푸스', 'olympus', '코닥', 'kodak', '인스타', 'insta360', '고프로', 'gopro'
    ]
    
    # === DB: Fashion & Style (확장) ===
    fashion_db = [
        '나이키', 'nike', '조던', 'jordan', '덩크', 'dunk', '에어포스',
        '아디다스', 'adidas', '이지', 'yeezy', '삼바', '가젤', '이지부스트',
        '슈프림', 'supreme', '스투시', 'stussy', '팔라스', 'palace',
        '요지', 'yohji', '야마모토', 'yamamoto', '와이쓰리', 'y-3',
        '꼼데', 'commedesgarcons', '가르송',
        '아크테릭스', 'arcteryx', '베타', '알파',
        '노스페이스', 'northface', '눕시',
        '스톤아일랜드', 'stoneisland', 'cp컴퍼니',
        '뉴발란스', 'newbalance', '992', '993', '990', '2002r', '530',
        '살로몬', 'salomon', '오클리', 'oakley', 'xt-6',
        '젠틀몬스터', 'gentlemonster',
        '구찌', 'gucci', '루이비통', 'louisvuitton', '샤넬', 'chanel', '에르메스', 'hermes',
        '프라다', 'prada', '미우미우', 'miumiu', '보테가', 'bottega',
        '롤렉스', 'rolex', '오메가', 'omega', '까르띠에', 'cartier',
        '미하라', 'mihara', '크롬하츠', 'chromehearts', '비비안', 'vivienne'
    ]
    
    # === DB: Tech & IT (확장) ===
    tech_db = [
        '컴퓨터', 'pc', '데스크탑', '노트북', 'laptop',
        '그래픽', 'vga', 'gpu', 'rtx', 'gtx', '4090', '4080', '4070', '3080',
        'cpu', 'amd', '라이젠', 'ryzen', '인텔', 'intel',
        '아이폰', 'iphone', '15pro', '14pro', '13mini', '16pro',
        '맥북', 'macbook', '에어', '프로', 'm1', 'm2', 'm3', 'm4',
        '아이패드', 'ipad', '에어팟', 'airpods', '애플워치', 'applewatch',
        '갤럭시', 'galaxy', 's24', 's23', 'zflip', 'zfold',
        '플스', 'ps5', 'ps4', 'playstation', '닌텐도', 'nintendo', '스위치', 'switch',
        '키보드', 'keyboard', '마우스', 'mouse', '모니터', 'monitor',
        '스팀덱', 'steamdeck', '키크론', 'keychron', '해피해킹', 'hhkb',
        '로지텍', 'logitech', '파이널마우스', 'wooting'
    ]
    
    # === DB: Living (신규) ===
    living_db = [
        '허먼밀러', 'hermanmiller', '에어론', 'aeron',
        '리모와', 'rimowa', '스노우피크', 'snowpeak', '브롬톤', 'brompton',
        '헬리녹스', 'helinox', '다이슨', 'dyson', '발뮤다', 'balmuda',
        '제네렉', 'genelec', '루이스폴센', 'louispoulsen'
    ]
    
    # === DB: Game (신규) ===
    game_db = [
        '플스', 'ps5', 'ps4', 'playstation', '듀얼센스', 'dualsense',
        '닌텐도', 'nintendo', '스위치', 'switch', 'xbox', '엑스박스',
        '피규어', '피그마', '레고', '건담', 'gundam', '뽀삐', '피그마'
    ]
    
    # === DB: Deal (알뜰/핫딜 - 뽐뿌 등) ===
    deal_db = [
        '핫딜', '알뜰', '세일', '뽐뿌', '쿠팡', '11번가', 'gmarket', '지마켓',
        '옥션', 'auction', '와우', 'wow', '번개', '당근'
    ]
    
    # === DB: Car (보배드림 등) ===
    car_db = [
        '자동차', '중고차', '보배', 'bobaedream', '현대', '기아', 'bmw', '벤츠',
        '테슬라', 'tesla', '제네시스', 'genesis', '쏘나타', '캐스퍼'
    ]
    
    # === DB: Interior (오늘의집 등) ===
    interior_db = [
        '인테리어', '가구', '오늘의집', 'ohou', '소파', '침대', '책상',
        '조명', '램프', '의자', '테이블', '수납장', '화장대'
    ]

    if any(x in k for x in cam_db):
        return "CAMERA"
    elif any(x in k for x in fashion_db):
        return "FASHION"
    elif any(x in k for x in tech_db):
        return "TECH"
    elif any(x in k for x in living_db):
        return "LIVING"
    elif any(x in k for x in game_db):
        return "GAME"
    elif any(x in k for x in deal_db):
        return "DEAL"
    elif any(x in k for x in car_db):
        return "CAR"
    elif any(x in k for x in interior_db):
        return "INTERIOR"
    else:
        return None

# [Market Sources] 검색어별 연관 커뮤니티 매핑 - Market Sources 탭과 동기화
# (name, url, tag, relevance_tags, desc) - desc: Market Sources처럼 설명 표시
# relevance_tags: APPLE, CAMERA, TECH, PC, MOBILE, FASHION, GAME, DEAL, CAR, INTERIOR, LIVING, GENERAL
COMMUNITY_SOURCES = [
    # Apple & Life
    ("아사모", "https://cafe.naver.com/appleiphone", "asamo", ["APPLE", "MOBILE"], "아이폰/아이패드 사용자"),
    ("맥쓰사", "https://cafe.naver.com/inmacbook", "mac", ["APPLE", "TECH"], "맥북/맥 사용자 모임"),
    # Camera & Gear
    ("SLR클럽", "https://www.slrclub.com", "slr", ["CAMERA"], "국내 최대 카메라 장터"),
    ("라이카 클럽", "http://www.leicaclub.net/", "leica", ["CAMERA"], "Leica 전문"),
    ("필름카메라 동호회", "https://cafe.naver.com/35mmcamera", "film", ["CAMERA"], "필름카메라 커뮤니티"),
    ("DOF LOOK", "https://cafe.naver.com/doflook", "dof", ["CAMERA"], "전문 촬영 장비"),
    # Tech & PC
    ("퀘이사존", "https://quasarzone.com", "quasar", ["TECH", "PC"], "PC/하드웨어 뉴스"),
    ("쿨엔조이", "https://coolenjoy.net", "cool", ["TECH", "PC"], "PC 하드웨어 매니아"),
    ("미코", "https://meeco.kr", "meeco", ["TECH", "MOBILE"], "모바일/테크 정보"),
    ("클리앙", "https://www.clien.net", "clien", ["TECH", "DEAL"], "IT/알뜰구매"),
    # Game & Hobby
    ("루리웹 장터", "https://bbs.ruliweb.com/market", "ruli", ["GAME"], "게임/피규어/취미"),
    # Deal & Sale
    ("뽐뿌", "https://www.ppomppu.co.kr", "pompu", ["DEAL"], "알뜰구매/핫딜"),
    # Fashion & Style
    ("KREAM", "https://kream.co.kr", "kream", ["FASHION"], "한정판 거래 플랫폼"),
    ("나이키매니아", "https://cafe.naver.com/sssw", "nike", ["FASHION"], "스니커즈/스트릿"),
    ("어미새", "https://eomisae.co.kr", "eomisae", ["FASHION", "DEAL"], "글로벌 세일 정보"),
    ("디젤매니아", "https://cafe.naver.com/dieselmania", "diesel", ["FASHION"], "남성 패션 커뮤니티"),
    ("무신사", "https://www.musinsa.com", "musinsa", ["FASHION"], "스트릿/스니커즈"),
    # Car
    ("보배드림", "https://www.bobaedream.co.kr", "bobaedream", ["CAR"], "중고차/자동차 커뮤니티"),
    # Interior & Living
    ("오늘의집", "https://ohou.se", "ohou", ["INTERIOR", "LIVING"], "인테리어/가구"),
]

def _get_keyword_community_tags(keyword):
    """검색어에 맞는 커뮤니티 태그 반환 (Market Sources 연관 정확도 향상) - classify_keyword_category와 동기화"""
    k = keyword.lower().replace(" ", "")
    tags = set()
    # APPLE - 아이폰, 맥북, 에어팟, 애플워치
    if any(x in k for x in ['아이폰', 'iphone', '에어팟', 'airpods', '애플워치', 'applewatch', '아이패드', 'ipad',
            '15pro', '14pro', '13mini', '16pro']):
        tags.add("APPLE")
        tags.add("MOBILE")
    if any(x in k for x in ['맥북', 'macbook', '맥스튜디오', 'macstudio', '스튜디오디스플레이', 'm1', 'm2', 'm3', 'm4']):
        tags.add("APPLE")
        tags.add("TECH")
    # CAMERA (classify_keyword_category cam_db 확장 반영)
    if any(x in k for x in ['카메라', 'camera', '렌즈', 'lens', '필름', 'film', '라이카', 'leica', '니콘', 'nikon',
            '캐논', 'canon', '소니', 'sony', '후지', 'fujifilm', '리코', 'ricoh', 'gr2', 'gr3', 'gr3x', 'gr4',
            '핫셀', 'hasselblad', '콘탁스', 'contax', '마미야', 'mamiya', 'dslr', '미러리스', 'x100v', 'x100vi',
            '롤라이', 'rollei', '브로니카', 'bronica', '페이즈원', 'phaseone', '린호프', 'linhof']):
        tags.add("CAMERA")
    # FASHION (classify_keyword_category fashion_db 확장 반영)
    if any(x in k for x in ['나이키', 'nike', '조던', 'jordan', '덩크', 'dunk', '아디다스', 'adidas', '이지', 'yeezy',
            '뉴발란스', 'newbalance', '살로몬', 'salomon', '슈프림', 'supreme', '스투시', 'stussy',
            '아크테릭스', 'arcteryx', '노스페이스', 'northface', '스톤아일랜드', 'stoneisland',
            '구찌', 'gucci', '루이비통', '샤넬', 'chanel', '에르메스', 'hermes', '롤렉스', 'rolex',
            '미하라', 'mihara', '크롬하츠', 'chromehearts', '젠틀몬스터', 'gentlemonster', '오클리', 'oakley']):
        tags.add("FASHION")
    # TECH (PC, 하드웨어)
    if any(x in k for x in ['컴퓨터', 'pc', 'vga', 'gpu', 'rtx', 'gtx', '4090', '4080', '4070', '3080',
            '그래픽', '라이젠', 'ryzen', '인텔', 'intel', 'cpu', 'amd', '키보드', 'keyboard',
            '마우스', 'mouse', '모니터', 'monitor', '스팀덱', 'steamdeck', '키크론', 'keychron', '해피해킹', 'hhkb',
            '로지텍', 'logitech', '파이널마우스', 'wooting']):
        tags.add("TECH")
    # MOBILE (갤럭시 등)
    if any(x in k for x in ['갤럭시', 'galaxy', 's24', 's23', 'zflip', 'zfold']) and "APPLE" not in tags:
        tags.add("MOBILE")
    # GAME
    if any(x in k for x in ['플스', 'ps5', 'ps4', 'playstation', '닌텐도', 'nintendo', '스위치', 'switch',
            'xbox', '엑스박스', '듀얼센스', 'dualsense', '게임', '피규어', '피그마', '레고', '건담', '뽀삐']):
        tags.add("GAME")
    # DEAL - 알뜰/핫딜 (테크·패션 검색 시 참고용)
    if any(x in k for x in ['핫딜', '알뜰', '세일', '뽐뿌', '쿠팡', '11번가', 'gmarket', '지마켓', '옥션', 'auction']):
        tags.add("DEAL")
    elif tags & {"TECH", "FASHION"}:
        tags.add("DEAL")
    # CAR
    if any(x in k for x in ['자동차', '차', '보배', 'bobaedream', '중고차', '현대', '기아', 'bmw', '벤츠',
            '테슬라', 'tesla', '제네시스', 'genesis', '쏘나타', '캐스퍼']):
        tags.add("CAR")
    # INTERIOR / LIVING
    if any(x in k for x in ['인테리어', '가구', '오늘의집', 'ohou', '소파', '침대', '책상', '조명', '램프', '의자', '테이블',
            '허먼밀러', 'hermanmiller', '리모와', 'rimowa', '스노우피크', '브롬톤', '다이슨', '발뮤다']):
        tags.add("INTERIOR")
        tags.add("LIVING")
    return tags if tags else {"TECH"}  # fallback (연관 커뮤니티에 마켓 제외)

def get_related_communities(keyword):
    """검색어에 맞는 커뮤니티만 추천 (번개장터·중고나라 등 마켓 제외, 최대 5개)"""
    tags = _get_keyword_community_tags(keyword)
    matched = []
    for name, url, tag, comm_tags, desc in COMMUNITY_SOURCES:
        if tags & set(comm_tags):
            matched.append((name, url, tag, desc))
    if not matched:
        return None, None
    # 중복 제거, 최대 5개 (너무 많으면 산만함)
    seen = set()
    result = []
    for m in matched:
        if m[2] not in seen:
            seen.add(m[2])
            result.append(m)
            if len(result) >= 5:
                break
    title = "💡 연관 커뮤니티 (Market Sources)"
    return title, result

@st.cache_data(ttl=3600)  # 1시간마다 갱신
def get_exchange_rates():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url, timeout=5)
        data = response.json()
        usd = float(data['rates']['KRW'])
        jpy = (float(data['rates']['KRW']) / float(data['rates']['JPY'])) * 100
        
        # 전날 환율 (Frankfurter API - 무료, 전일 데이터 제공)
        usd_prev, jpy_prev = usd, jpy
        try:
            yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
            hist_url = f"https://api.frankfurter.app/{yesterday}?from=USD&to=KRW,JPY"
            hist = requests.get(hist_url, timeout=3)
            if hist.status_code == 200:
                h = hist.json()
                if h.get('rates'):
                    usd_prev = float(h['rates'].get('KRW', usd))
                    jpy_prev = (float(h['rates'].get('KRW', usd)) / float(h['rates'].get('JPY', 150))) * 100
        except Exception:
            pass
        
        rate_date = data.get('date', '')
        return usd, jpy, usd_prev, jpy_prev, rate_date
    except Exception:
        return 1450.0, 950.0, 1440.0, 955.0, ""

@st.cache_data(ttl=3600)
def get_translated_keyword(text, target_lang='en'):
    """번역 결과 캐싱 (1시간) - 검색 후 로딩 속도 개선"""
    if not re.search('[가-힣]', text): return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ko&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            return response.json()[0][0][0]
    except: pass
    return text

def get_translated_keywords_parallel(text):
    """영/일 번역 병렬 호출 - 2회 API 호출을 동시에 실행"""
    if not re.search('[가-힣]', text):
        return text, text
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_en = ex.submit(get_translated_keyword, text, 'en')
        f_ja = ex.submit(get_translated_keyword, text, 'ja')
        return f_en.result(), f_ja.result()

def calculate_total_import_cost(usd_price, rate):
    if usd_price <= 0: return 0
    krw_base = usd_price * rate
    shipping = 30000 
    if usd_price > 200: 
        duty = krw_base * 0.08
        vat = (krw_base + duty) * 0.1
        return (krw_base + duty + vat + shipping) / 10000
    return (krw_base + shipping) / 10000

def calculate_import_breakdown(usd_price, rate):
    """직구 비용 상세: (물품가격, 관세, 부가세, 배송비) KRW 원 단위"""
    if usd_price <= 0: return None
    krw_base = int(usd_price * rate)
    shipping = 30000
    if usd_price > 200:
        duty = int(krw_base * 0.08)
        vat = int((krw_base + duty) * 0.1)
        return {"물품가격": krw_base, "관세": duty, "부가세": vat, "배송비": shipping, "총액": krw_base + duty + vat + shipping}
    return {"물품가격": krw_base, "관세": 0, "부가세": 0, "배송비": shipping, "총액": krw_base + shipping}

@st.cache_data(ttl=60)
def get_sheet_keywords(df):
    """스프레드시트에서 검색 가능한 키워드 목록 추출"""
    if df is None or df.empty:
        return []
    keywords = set()
    kw_cols = ['모델명', '키워드', 'keyword', '제품명', '상품명', '상품', '이름', '품목', 'name', 'product']
    for col in kw_cols:
        if col in df.columns:
            for v in df[col].dropna().astype(str):
                v = str(v).strip()
                if v and v.lower() != 'nan' and len(v) >= 2:
                    keywords.add(v)
    for i in range(len(df.columns)):
        for v in df.iloc[:, i].dropna().astype(str):
            v = str(v).strip()
            if v and v.lower() != 'nan' and len(v) >= 2 and not re.match(r'^[\d\s,.;]+$', v):
                keywords.add(v)
    return sorted(keywords, key=lambda x: (len(x), x))

def _get_date_cols(df):
    """시세 주차/날짜 컬럼 탐지 - 12월4주, 1월1주, W1, 1주, 가격 등"""
    skip_keywords = ['키워드', 'keyword', '모델명', '상세스펙', '분류', '브랜드', '해외', 'usd', '비고', '메모', '링크', 'url']
    c_lower = lambda s: str(s).lower().strip()
    patterns = ['월', '주', 'week', 'date', '날짜', '주차', 'w1', 'w2', 'w3', 'w4', 'w5', '가격', 'price', '1주', '2주', '3주', '4주', '5주']
    date_cols = [c for c in df.columns if not any(sk in c_lower(c) for sk in skip_keywords)
                 and any(p in c_lower(c) for p in patterns)]
    if not date_cols and len(df.columns) >= 2:
        date_cols = list(df.columns[1:])
    return sorted(date_cols, key=lambda x: str(x)) if date_cols else list(df.columns[1:6]) if len(df.columns) >= 2 else ["12월4주", "1월1주", "1월2주", "1월3주", "1월4주"]

def _get_col(row, *names):
    """컬럼명 유연 매칭 (공백/대소문자 무시)"""
    for n in names:
        v = row.get(n, None)
        if pd.notna(v) and str(v).strip():
            return str(v).strip()
    for c in row.index:
        c_low = str(c).lower()
        if any(x in c_low for x in ['모델', '키워드', '제품', '상품', '이름', '품목', 'keyword', 'product', 'name', 'leica', '라이카']):
            v = row.get(c, None)
            if pd.notna(v) and str(v).strip() and str(v).lower() != 'nan':
                return str(v).strip()
    if len(row) >= 1:
        v = row.iloc[0]
        if pd.notna(v) and str(v).strip() and str(v).lower() != 'nan' and not re.match(r'^[\d\s,.;]+$', str(v)):
            return str(v).strip()
    return ''

def _get_raw_price_str(row):
    """시세 원본 문자열 - 시세(5주치), prices_raw, 거래가목록 등"""
    for col in ['시세 (5주치)', '시세(5주치)', 'prices_raw', '거래가목록', '시세', '가격목록', '거래가', '가격']:
        v = row.get(col, None)
        if pd.notna(v) and str(v).strip() and str(v).lower() != 'nan':
            return str(v).strip()
    for c in row.index:
        v = row.get(c, None)
        if pd.notna(v):
            s = str(v).strip()
            if ',' in s and re.search(r'\d', s) and len(re.findall(r'\d+', s)) >= 2:
                return s
    return ''

def _get_usd_val(row):
    """해외평균 USD 값"""
    for col in ['해외평균(USD)', '해외평균(usd)', '해외평균', 'usd', 'global_usd', '해외가격']:
        v = row.get(col, None)
        if pd.notna(v):
            clean = re.sub(r'[^0-9.]', '', str(v))
            if clean:
                try:
                    return float(clean)
                except ValueError:
                    pass
    return 0.0

def _normalize_for_match(s):
    """한·영 상품명 정규화 - 매칭용"""
    s = str(s).lower().replace(" ", "").strip()
    pairs = [("스타일러", "styler"), ("스탠바이미", "stanbyme"), ("라이카", "leica"), ("아이폰", "iphone"),
             ("나이키", "nike"), ("갤럭시", "galaxy"), ("맥북", "macbook"), ("소니", "sony"), ("니콘", "nikon"),
             ("캐논", "canon"), ("후지", "fuji"), ("올림푸스", "olympus"), ("파나소닉", "panasonic")]
    for ko, en in pairs:
        s = s.replace(ko, en)
    return s

def _extract_numbers(s):
    """문자열에서 숫자 시퀀스 추출 (모델번호 매칭용)"""
    return set(re.findall(r'\d+', str(s)))

def _extract_model_tokens(s):
    """모델 식별자 추출 (M3, Q3, M6 등) - M3≠Q3 구분용"""
    s = str(s).lower().replace(" ", "")
    tokens = set()
    for m in re.finditer(r'([a-z])(\d+)\b', s):
        tokens.add(m.group(1) + m.group(2))
    return tokens

@st.cache_data(ttl=300)
def get_trend_data_from_sheet(user_query, df):
    if df.empty or not user_query: return None
    user_clean = user_query.lower().replace(" ", "").strip()
    if len(user_clean) < 2: return None  # 1글자 검색 방지
    user_nums = _extract_numbers(user_query)
    pool = list(get_sheet_keywords(df)) + list(AUTOCOMPLETE_POOL) if not df.empty else list(AUTOCOMPLETE_POOL)
    pool_norm = [p.lower().replace(" ", "") for p in pool]
    user_variants = {user_clean} | set(difflib.get_close_matches(user_clean, pool_norm, n=5, cutoff=0.6))
    user_variants.add(_normalize_for_match(user_query))
    user_norm = _normalize_for_match(user_query)
    date_cols = _get_date_cols(df)
    candidates = []  # 여러 행 매칭 시 검색어와 가장 비슷한 시트 행 선택
    for _, row in df.iterrows():
        try:
            k_val = _get_col(row, '모델명', '키워드', 'keyword')
            if not k_val:
                for c in row.index:
                    v = row.get(c, None)
                    if pd.notna(v) and str(v).strip() and str(v).lower() != 'nan' and not re.match(r'^[\d\s,.;]+$', str(v)):
                        k_val = str(v).strip()
                        break
            if not k_val: continue
            sheet_keyword = str(k_val).lower().replace(" ", "").strip()
            sheet_norm = _normalize_for_match(str(k_val))
            sheet_nums = _extract_numbers(k_val)
            # [엄격 매칭] 모델명/키워드 컬럼만 사용 - 다른 셀 스캔 제거 (잘못된 연동 방지)
            MIN_LEN = 2
            match = (user_clean in sheet_keyword or sheet_keyword in user_clean or
                     user_norm in sheet_norm or sheet_norm in user_norm)
            # SequenceMatcher: 0.80 이상만 허용 (오타 보정용, 아무거나 연동 방지)
            if not match and len(sheet_keyword) >= MIN_LEN:
                match = difflib.SequenceMatcher(None, user_norm, sheet_norm).ratio() >= 0.80
            if not match:
                continue
            # [정확도] 숫자(모델번호)가 있으면 반드시 일치 - 아이폰15≠아이폰17프로
            if user_nums and sheet_nums and not (user_nums & sheet_nums):
                continue
            # [정확도] 모델 식별자(M3, Q3, M6 등)가 있으면 반드시 일치 - M3≠Q3
            user_tokens = _extract_model_tokens(user_query)
            sheet_tokens = _extract_model_tokens(k_val)
            if user_tokens and sheet_tokens and not (user_tokens & sheet_tokens):
                continue
            # 주차별 여러 시세 파싱 (예: "95, 93, 92" → [95,93,92])
            prices_per_week = []
            for col in date_cols:
                if col not in df.columns:
                    continue
                v_raw = str(row.get(col, '')).strip()
                if not v_raw or v_raw.lower() == 'nan':
                    continue
                week_prices = []
                for part in v_raw.replace(';', ',').split(','):
                    clean = re.sub(r'[^0-9.]', '', part)
                    if clean:
                        try:
                            val = float(clean)
                            if val > 0:
                                week_prices.append(val)
                        except ValueError:
                            pass
                if week_prices:
                    prices_per_week.append((col, week_prices))
            # 전체시세: 주차별 가중평균(산술평균)
            trend_prices = [sum(p) / len(p) for _, p in prices_per_week]
            valid_dates = [d for d, _ in prices_per_week]
            raw_prices = []
            for _, p in prices_per_week:
                raw_prices.extend(p)
            # 시세(5주치) 등 별도 컬럼이 있으면 raw에 병합
            raw_str = _get_raw_price_str(row)
            if raw_str:
                for part in raw_str.replace(';', ',').split(','):
                    clean = re.sub(r'[^0-9.]', '', part)
                    if clean:
                        try:
                            val = float(clean)
                            if val > 0:
                                raw_prices.append(val)
                        except ValueError:
                            pass
            if not raw_prices:
                raw_prices = list(trend_prices)
            global_usd = _get_usd_val(row)
            if not trend_prices and raw_prices:
                trend_prices = [sum(raw_prices) / len(raw_prices)]
                valid_dates = ["시세"]
            if not trend_prices:
                continue
            name = _get_col(row, '모델명', '모델명 (상세스펙/상태)')
            spec = _get_col(row, '상세스펙')
            if spec:
                name = f"{name} ({spec})".strip() if name else spec
            name = name or '상품명 미상'
            # 시세요약: 이번주 중앙값 + Q1/Q3 (극단값 제거, 자연스러운 구간)
            this_week_prices = prices_per_week[-1][1] if prices_per_week else []
            _p = this_week_prices if this_week_prices else raw_prices
            if len(_p) >= 4:
                _p = np.array(_p)
                q1, q3 = np.percentile(_p, 25), np.percentile(_p, 75)
                iqr = q3 - q1
                _filt = _p[( _p >= q1 - 1.5*iqr ) & ( _p <= q3 + 1.5*iqr )]
                _p = _filt if len(_filt) >= 2 else _p
            summary_avg = float(np.median(_p)) if len(_p) else (trend_prices[-1] if trend_prices else 0)
            summary_min = float(np.percentile(_p, 25)) if len(_p) >= 4 else (min(_p) if len(_p) else 0)
            summary_max = float(np.percentile(_p, 75)) if len(_p) >= 4 else (max(_p) if len(_p) else 0)
            # 검색어와 길이 차이 최소화 - 아이폰15프로 검색→아이폰15프로, 아이폰15→아이폰15
            len_diff = abs(len(user_clean) - len(sheet_keyword))
            exact = 0 if user_clean == sheet_keyword else 1
            candidates.append((len_diff, exact, {
                "name": name, "dates": valid_dates, "trend_prices": trend_prices, "raw_prices": raw_prices,
                "global_usd": global_usd, "matched_keyword": k_val,
                "summary_avg": summary_avg, "summary_min": summary_min, "summary_max": summary_max,
                "summary_n": len(this_week_prices)
            }))
        except: continue
    if not candidates:
        return None
    # 검색어와 가장 비슷한 시트 행: 1) 길이 차이 적은 것 2) 완전 일치 우선
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][2]

def generate_new_data():
    now = datetime.now() + timedelta(hours=9)
    return {'time': now.strftime("%Y-%m-%d %H:%M:%S")}

if 'ticker_data' not in st.session_state:
    st.session_state.ticker_data = generate_new_data()
if 'memo_pad' not in st.session_state:
    st.session_state.memo_pad = ""
# [테마] 다크 모드만 사용 (라이트 모드 제거)
st.session_state.theme_light = False

# ------------------------------------------------------------------
# [4] CSS 스타일링 (Pro Dashboard Cards)
# ------------------------------------------------------------------
st.markdown("""
<style>
    /* Global Theme - Apple-like with Navy */
    .stApp { 
        background-color: #0E1117; 
        background: radial-gradient(circle at 50% -20%, #1c2333 0%, #0E1117 80%);
        color: #F5F5F7; 
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', system-ui, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        transition: all 0.3s ease;
    }
    
    /* Light Mode Override - Cream & Black (강한 대비) */
    body.light-mode .stApp, body.light-mode {
        background-color: #EDE8E0 !important;
        background: radial-gradient(circle at 50% -20%, #F5F0E6 0%, #E8E2D8 80%) !important;
        color: #0D0D0D !important;
    }
    /* Streamlit 상단 초록색 바 제거 */
    [data-testid="stHeader"], header[data-testid="stHeader"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    
    /* Light Mode: Main Container - Cream 배경, 블랙 텍스트 */
    body.light-mode .main,
    body.light-mode .block-container,
    body.light-mode [data-testid="stAppViewContainer"] {
        background-color: #EDE8E0 !important;
        color: #0D0D0D !important;
    }
    
    /* Scroll Progress Bar - Apple Style */
    .stApp::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        height: 2px;
        width: 100%;
        background: linear-gradient(90deg, 
            rgba(10, 132, 255, 0) 0%,
            rgba(10, 132, 255, 0.8) 50%,
            rgba(10, 132, 255, 0) 100%);
        z-index: 9999;
        opacity: 0.6;
        animation: progress-glow 3s ease-in-out infinite;
    }
    @keyframes progress-glow {
        0%, 100% { opacity: 0.3; }
        50% { opacity: 0.8; }
    }
    
    /* Performance: reduce continuous animations (메인 펄스는 항상 재생) */
    .stApp::before { animation: none !important; }
    .radar-icon,
    .radar-icon-wrap::before,
    .radar-icon-wrap::after {
        animation-play-state: paused;
    }
    .radar-left:hover .radar-icon,
    .radar-left:hover .radar-icon-wrap::before,
    .radar-left:hover .radar-icon-wrap::after,
    .header-logo-standalone:hover .radar-icon,
    .header-logo-standalone:hover .radar-icon-wrap::before,
    .header-logo-standalone:hover .radar-icon-wrap::after {
        animation-play-state: running;
    }
    /* 메인화면 홈 펄스(.home-sonar-wrap)는 항상 재생 */
    .home-sonar-wrap .sonar-ring,
    .home-sonar-wrap .sonar-dot,
    .home-sonar-wrap .sonar-blip {
        animation-play-state: running !important;
    }
    .bill-content { animation-duration: 60s; }
    
    /* Back to Top Button - Apple Style */
    .back-to-top {
        position: fixed;
        bottom: 80px;
        right: 32px;
        width: 48px;
        height: 48px;
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.12), rgba(245, 245, 247, 0.08));
        backdrop-filter: blur(20px) saturate(180%);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        border: 0.5px solid rgba(255, 255, 255, 0.2);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        color: #F5F5F7;
        cursor: pointer;
        z-index: 1000;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2),
                    inset 0 1px 0 rgba(255, 255, 255, 0.15);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        opacity: 0;
        transform: translateY(20px) scale(0.8);
        pointer-events: none;
    }
    .back-to-top.visible {
        opacity: 1;
        transform: translateY(0) scale(1);
        pointer-events: auto;
    }
    .back-to-top:hover {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.18), rgba(245, 245, 247, 0.12));
        transform: translateY(-4px) scale(1.05);
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.3),
                    inset 0 1px 0 rgba(255, 255, 255, 0.2);
    }
    .back-to-top:active {
        transform: translateY(-2px) scale(1.0);
    }
    
    /* Loading Spinner - NO ROTATION */
    [data-testid="stSpinner"] > div {
        border: 3px solid rgba(10, 132, 255, 0.3) !important;
        animation: none !important;
        transform: none !important;
    }
    [data-testid="stSpinner"] {
        animation: spinner-pulse 2s ease-in-out infinite !important;
    }
    @keyframes spinner-pulse {
        0%, 100% { opacity: 0.5; }
        50% { opacity: 1; }
    }
    
    /* [Responsive] Centered Container (Max Width 1400px) */
    .block-container {
        max-width: 1400px !important;
        margin: 0 auto !important;
        padding: 1rem 1rem 6rem !important;
    }
    @media (max-width: 768px) {
        .block-container { padding: 0.75rem 0.75rem 5rem !important; }
        .radar-title { font-size: 1.4rem !important; }
        .radar-sub { font-size: 0.5rem !important; margin-left: 0 !important; }
        div[data-testid="stLinkButton"] > a { height: 72px !important; font-size: 0.9rem !important; padding: 8px !important; }
        .market-grid { grid-template-columns: 1fr !important; }
        .search-pills { flex-wrap: wrap !important; gap: 6px !important; }
        .search-pills a { font-size: 0.85rem !important; padding: 6px 12px !important; }
        .capsule-title { font-size: 1rem !important; padding: 6px 14px !important; margin-top: 20px !important; }
        .source-card { padding: 12px 14px !important; height: 52px !important; }
        .metric-card { padding: 8px 12px !important; }
        .metric-value { font-size: 0.95rem !important; }
    }
    
    /* 1. Header - 로고 + 토글(개발중 비활성화) */
    .st-key-header_logo_toggle,
    .st-key-header_logo_toggle .element-container,
    .st-key-header_logo_toggle [data-testid="stVerticalBlock"],
    .st-key-header_logo_toggle [data-testid="stVerticalBlock"] > div { margin: 0 !important; padding: 0 !important; }
    .st-key-header_logo_toggle { display: flex !important; flex-direction: column !important; align-items: flex-start !important; margin-top: 0 !important; gap: 8px !important; }
    .header-logo-area { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; margin: 0 !important; padding: 16px 0; }
    .header-logo-standalone {
        display: flex; flex-direction: column; align-items: flex-start; flex-shrink: 0;
        text-decoration: none !important; border-bottom: none !important; gap: 1px;
        position: relative;
    }
    /* 로고 후광 - 부드러운 펄스 */
    .header-logo-standalone::before {
        content: ''; 
        position: absolute; 
        inset: -14px -22px -14px -22px; 
        border-radius: 26px;
        z-index: -1; 
        pointer-events: none;
        background: radial-gradient(ellipse 120% 100% at 50% 50%, 
                                    rgba(10,132,255,0.15) 0%, 
                                    rgba(10,132,255,0.06) 40%, 
                                    transparent 75%);
        animation: logo-halo-breathe 5s ease-in-out infinite;
        box-shadow: 0 0 30px rgba(10,132,255,0.2);
        transition: opacity 0.5s ease, box-shadow 0.5s ease;
    }
    .header-logo-standalone:hover::before {
        opacity: 1;
        box-shadow: 0 0 50px rgba(10,132,255,0.35);
    }
    @keyframes logo-halo-breathe { 
        0%, 100% { 
            opacity: 0.5; 
            transform: scale(0.97);
        } 
        50% { 
            opacity: 0.75; 
            transform: scale(1.02);
        } 
    }
    .header-logo-standalone:hover, .header-logo-standalone:focus, .header-logo-standalone:visited { text-decoration: none !important; border-bottom: none !important; }
    .header-logo-standalone *, .header-logo-standalone *:hover { text-decoration: none !important; border-bottom: none !important; }
    .theme-toggle { 
        font-size: 1.2rem; 
        opacity: 0.85; 
        transition: all 0.2s ease; 
        flex-shrink: 0; 
        padding: 8px 12px; 
        display: inline-flex; 
        align-items: center; 
        justify-content: center; 
        border-radius: 12px;
        cursor: pointer;
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.12);
    }
    .theme-toggle:hover { 
        opacity: 1; 
        background: rgba(255,255,255,0.08);
        transform: scale(1.05);
    }
    .theme-toggle-disabled { font-size: 1.2rem; opacity: 0.5; flex-shrink: 0; padding: 8px 12px; display: inline-flex; align-items: center; justify-content: center; border-radius: 12px; cursor: not-allowed; pointer-events: none; border: 1px solid rgba(255,255,255,0.2); }
    /* 빌보드 래퍼: 중앙 정렬 */
    .radar-billboard-wrap { display: flex; justify-content: center; align-items: center; padding: 16px 0; }
    div[data-testid="stToggle"] { padding: 0 !important; }
    div[data-testid="stToggle"] label { display: none !important; }
    div[data-testid="stToggle"] [role="switch"] { 
        accent-color: #5C9EFF !important; 
        width: 48px !important; height: 26px !important;
        border-radius: 13px !important;
        cursor: pointer !important;
    }
    div[data-testid="stToggle"] > div { 
        padding: 4px !important; 
        background: rgba(255,255,255,0.06) !important; 
        backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
        border-radius: 16px !important; 
        border: 1px solid rgba(255,255,255,0.12) !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.06) !important;
        transition: all 0.25s ease !important;
    }
    div[data-testid="stToggle"] > div:hover { 
        background: rgba(255,255,255,0.1) !important; 
        border-color: rgba(92,158,255,0.35) !important;
        box-shadow: 0 2px 12px rgba(0,0,0,0.2), 0 0 0 1px rgba(92,158,255,0.15), inset 0 1px 0 rgba(255,255,255,0.08) !important;
    }
    .header-logo-standalone .radar-top-row { display: flex; align-items: center; gap: 12px; }
    .header-logo-standalone .radar-sub { margin-left: 48px; }
    .radar-left { 
        display: flex; flex-direction: column; align-items: flex-start; position: relative; flex-shrink: 0; 
        gap: 4px;
    }
    .radar-top-row { display: flex; align-items: center; gap: 16px; }
    .radar-icon-wrap { 
        position: relative; 
        display: inline-flex;
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.06), rgba(245, 245, 247, 0.04));
        border-radius: 18px;
        padding: 10px 12px;
        border: 0.5px solid rgba(255, 255, 255, 0.12);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15),
                    inset 0 1px 0 rgba(255, 255, 255, 0.15);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .radar-left:hover .radar-icon-wrap, 
    .header-logo-standalone:hover .radar-icon-wrap {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.12), rgba(245, 245, 247, 0.08));
        box-shadow: 0 8px 24px rgba(255, 255, 255, 0.12),
                    inset 0 1px 0 rgba(255, 255, 255, 0.2);
        transform: translateY(-2px);
    }
    /* 로고 아이콘 - 레이더 스캔 효과 */
    .radar-icon-wrap::before { 
        content: ''; 
        position: absolute; 
        left: 50%; 
        top: 50%; 
        width: 52px; 
        height: 52px; 
        margin: -26px 0 0 -26px; 
        border-radius: 50%; 
        background: radial-gradient(circle at center, rgba(10,132,255,0.3) 0%, rgba(10,132,255,0.15) 25%, transparent 60%); 
        animation: radar-pulse 3s ease-in-out infinite; 
        pointer-events: none; 
        z-index: 0;
        transition: background 0.3s ease; 
    }
    .radar-left:hover .radar-icon-wrap::before,
    .header-logo-standalone:hover .radar-icon-wrap::before {
        background: radial-gradient(circle at center, rgba(10,132,255,0.45) 0%, rgba(10,132,255,0.2) 25%, transparent 60%);
        opacity: 0.8;
    }
    .radar-icon-wrap::after {
        content: '';
        position: absolute;
        left: 50%;
        top: 50%;
        width: 80px;
        height: 80px;
        margin: -40px 0 0 -40px;
        border-radius: 50%;
        border: 2px solid rgba(10,132,255,0.2);
        animation: radar-ring 4s ease-out infinite;
        pointer-events: none;
        z-index: -1;
        transition: border-color 0.3s ease, border-width 0.3s ease;
    }
    .radar-left:hover .radar-icon-wrap::after,
    .header-logo-standalone:hover .radar-icon-wrap::after {
        border-color: rgba(10,132,255,0.4);
        border-width: 2px;
    }
    .radar-icon { 
        font-size: 1.8rem; 
        z-index: 2; 
        line-height: 1; 
        position: relative; 
        filter: drop-shadow(0 0 12px rgba(10,132,255,0.7)) 
                drop-shadow(0 0 5px rgba(255,255,255,0.5)); 
        animation: radar-scan 3s ease-in-out infinite;
        transition: transform 0.5s cubic-bezier(0.4, 0, 0.2, 1),
                    filter 0.5s ease; 
    }
    .radar-left:hover .radar-icon, .header-logo-standalone:hover .radar-icon { 
        filter: drop-shadow(0 0 16px rgba(10,132,255,0.9)) 
                drop-shadow(0 0 6px rgba(255,255,255,0.6));
        animation: radar-hover-gentle 2s ease-in-out infinite;
    }
    @keyframes radar-hover-gentle {
        0%, 100% {
            transform: scale(1.05) rotate(-3deg);
        }
        50% {
            transform: scale(1.1) rotate(3deg);
        }
    }
    
    /* 레이더 펄스 */
    @keyframes radar-pulse { 
        0%, 100% { 
            opacity: 0.25; 
            transform: scale(0.85); 
        } 
        50% { 
            opacity: 0.6; 
            transform: scale(1.1); 
        } 
    }
    
    /* 레이더 링 확산 */
    @keyframes radar-ring {
        0% {
            transform: scale(0.5);
            opacity: 0.6;
            border-color: rgba(10,132,255,0.4);
        }
        50% {
            opacity: 0.3;
        }
        100% {
            transform: scale(1.5);
            opacity: 0;
            border-color: rgba(10,132,255,0);
        }
    }
    
    /* 레이더 스캔 (회전 + 깜빡임) */
    @keyframes radar-scan {
        0%, 100% {
            filter: drop-shadow(0 0 8px rgba(10,132,255,0.5)) 
                    drop-shadow(0 0 3px rgba(255,255,255,0.3));
            transform: rotate(0deg);
        }
        25% {
            filter: drop-shadow(0 0 15px rgba(10,132,255,0.8)) 
                    drop-shadow(0 0 6px rgba(255,255,255,0.6));
        }
        50% {
            filter: drop-shadow(0 0 8px rgba(10,132,255,0.5)) 
                    drop-shadow(0 0 3px rgba(255,255,255,0.3));
            transform: rotate(8deg);
        }
        75% {
            filter: drop-shadow(0 0 15px rgba(10,132,255,0.8)) 
                    drop-shadow(0 0 6px rgba(255,255,255,0.6));
        }
    }
    
    .radar-title-wrap { position: relative; display: inline-block; }
    /* 로고 텍스트 - Premium iOS Display Typography */
    .radar-title { 
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif;
        font-size: 3.2rem; 
        font-weight: 700; 
        letter-spacing: -2.8px; 
        line-height: 1; 
        margin: 0; 
        background: linear-gradient(145deg, #FFFFFF 0%, #F5F5F7 40%, #E5E5EA 100%); 
        -webkit-background-clip: text; 
        background-clip: text; 
        -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 2px 12px rgba(255, 255, 255, 0.1)); 
        text-shadow: none;
        filter: drop-shadow(0 2px 12px rgba(255, 255, 255, 0.3)) 
                drop-shadow(0 1px 4px rgba(255, 255, 255, 0.5));
    }
    @keyframes title-shine {
        0%, 100% {
            background-position: 0% 0%;
        }
        50% {
            background-position: 100% 0%;
        }
    }
    
    /* 서브 텍스트 - 깜빡임 */
    .radar-sub { 
        font-size: 0.65rem; 
        color: #a5d8ff !important; 
        -webkit-text-fill-color: #a5d8ff !important; 
        letter-spacing: 3px; 
        font-weight: 600; 
        margin-left: 48px; 
        text-transform: uppercase; 
        text-shadow: 0 1px 2px rgba(0,0,0,0.3), 0 0 10px rgba(10,132,255,0.3);
        animation: sub-glow 4s ease-in-out infinite;
    }
    @keyframes sub-glow {
        0%, 100% {
            opacity: 0.8;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3), 0 0 8px rgba(10,132,255,0.2);
        }
        50% {
            opacity: 1;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3), 0 0 15px rgba(10,132,255,0.5);
        }
    }
    
    
    /* Billboard - 4x2 그리드, 유리 박스, 터치 영역 개선 */
    .radar-billboard {
        display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); grid-template-rows: repeat(2, 1fr);
        gap: 10px 14px;
        background: rgba(255,255,255,0.06); padding: 12px 18px; margin: 0 auto;
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255,255,255,0.18); border-radius: 16px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.06);
        width: fit-content; max-width: 880px; flex-shrink: 0;
        touch-action: pan-y;
        -webkit-overflow-scrolling: touch;
    }
    
    /* [Responsive] 화면이 좁으면 4x1, 모바일은 swipe 가능 */
    @media (max-width: 1100px) {
        .radar-billboard { 
            grid-template-rows: 1fr; 
            max-width: 620px; 
            width: fit-content;
        }
        .c-vibe, .c-living, .c-game, .c-outdoor { display: none !important; }
    }
    @media (max-width: 768px) {
        .radar-billboard-wrap { 
            display: flex; 
            overflow-x: auto; 
            overflow-y: hidden;
            -webkit-overflow-scrolling: touch;
            scroll-snap-type: x mandatory;
            padding: 8px 0;
        }
        .radar-billboard { 
            display: flex !important; 
            flex-direction: row;
            gap: 12px;
            min-width: max-content;
            scroll-snap-align: start;
            padding: 10px 14px;
        }
        .bill-col {
            min-width: 140px;
            scroll-snap-align: start;
        }
        .c-vibe, .c-living, .c-game, .c-outdoor { display: flex !important; }
    }
    .bill-col { 
        display: flex; flex-direction: column; 
        min-width: 0; overflow: hidden;
    }
    .bill-head { 
        font-size: 0.7rem; 
        font-weight: 800; 
        margin-bottom: 6px; 
        letter-spacing: 1px; 
        text-transform: uppercase; 
        border-bottom: 1px solid rgba(255, 255, 255, 0.12); 
        padding-bottom: 4px; 
        white-space: nowrap;
        color: #8E8E93;
    }
    .bill-win { 
        height: 60px; overflow: hidden; position: relative; 
        flex-shrink: 0;
        mask-image: linear-gradient(to bottom, transparent 0%, black 20%, black 80%, transparent 100%);
        -webkit-mask-image: linear-gradient(to bottom, transparent 0%, black 20%, black 80%, transparent 100%);
    }
    .bill-content { 
        display: flex; flex-direction: column; 
        animation: rolling 40s infinite cubic-bezier(0.4, 0, 0.2, 1);
    }
    /* [플립 달력] 카테고리별 다른 시점에서 시작 (엇박자) */
    .c-trend .bill-content { animation-delay: 0s; }
    .c-kicks .bill-content { animation-delay: -3s; }
    .c-lux .bill-content { animation-delay: -6s; }
    .c-tech .bill-content { animation-delay: -9s; }
    .c-vibe .bill-content { animation-delay: -12s; }
    .c-living .bill-content { animation-delay: -15s; }
    .c-game .bill-content { animation-delay: -18s; }
    .c-outdoor .bill-content { animation-delay: -21s; }
    .bill-item { 
        height: 30px; min-height: 30px; line-height: 30px; 
        color: #eee; font-weight: 700; font-family: 'Pretendard', sans-serif; 
        font-size: 0.9rem; letter-spacing: -0.2px; 
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        flex-shrink: 0;
    }
    a.bill-item { 
        color: inherit; 
        text-decoration: none; 
        display: block; 
        cursor: pointer; 
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        padding: 2px 6px;
        margin: -2px -6px;
        border-radius: 6px;
    }
    a.bill-item:hover { 
        background: rgba(10, 132, 255, 0.1);
        transform: translateX(2px);
    }
    a.bill-item:active {
        background: rgba(10, 132, 255, 0.18);
        transform: translateX(1px) scale(0.98);
    }
    
    /* Category Colors */
    .c-trend .bill-item { color: #00E5FF; }
    .c-kicks .bill-item { color: #FF4500; }
    .c-lux .bill-item { color: #FFD700; }
    .c-tech .bill-item { color: #2979FF; }
    .c-vibe .bill-item { color: #00FF88; }
    .c-living .bill-item { color: #E040FB; }
    .c-game .bill-item { color: #9C27B0; }
    .c-outdoor .bill-item { color: #4CAF50; }
    
    /* [플립 달력] 각 위치에서 잠시 멈췄다가 다음으로 넘어가는 방식 */
    @keyframes rolling {
        0%, 5% { transform: translateY(0); }
        10%, 15% { transform: translateY(-30px); }
        20%, 25% { transform: translateY(-60px); }
        30%, 35% { transform: translateY(-90px); }
        40%, 45% { transform: translateY(-120px); }
        50%, 55% { transform: translateY(-150px); }
        60%, 65% { transform: translateY(-180px); }
        70%, 75% { transform: translateY(-210px); }
        80%, 85% { transform: translateY(-240px); }
        90%, 95% { transform: translateY(-270px); }
        100% { transform: translateY(-300px); } /* Seamless Loop */
    }

    /* 2. Typewriter Effect */
    .typewriter-text {
        font-family: 'Courier New', monospace; font-size: 0.85rem; color: #3B82F6;
        margin-bottom: 5px; display: inline-block; overflow: hidden;
        border-right: .15em solid #3B82F6; white-space: nowrap;
        animation: typing 3.5s steps(40, end), blink-caret .75s step-end infinite;
    }
    @keyframes typing { from { width: 0 } to { width: 100% } }
    @keyframes blink-caret { from, to { border-color: transparent } 50% { border-color: #3B82F6; } }

    /* 3. Search Bar - 다크 모드 전용 */
    
    /* [홈 히어로] 타이틀·서브텍스트 - 여유 있게 */
    .home-hero-wrap {
        text-align: center; padding: 40px 32px 36px; margin-bottom: 28px;
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 20px;
    }
    .home-hero-title { font-size: 1.5rem; color: #e8eef4; font-weight: 700; margin: 0 0 12px 0; letter-spacing: -0.3px; line-height: 1.4; }
    .home-hero-sub { font-size: 1rem; color: #8a9aab; margin: 0; line-height: 1.6; }
    .home-hero-hidden { display: none !important; }
    
    /* [홈 빈 상태] Apple-style 레이더 - 펄스 + 타겟 블립 */
    .pulse-block { display: block; }
    .pulse-block-hidden { display: none !important; }
    .home-sonar-wrap { text-align: center; padding: 40px 20px 60px; }
    .home-sonar-wrap .sonar-wrap { 
        width: 280px; 
        height: 280px; 
        margin: 0 auto; 
        position: relative; 
        display: flex; 
        justify-content: center; 
        align-items: center;
        background: radial-gradient(circle, rgba(255, 255, 255, 0.02) 0%, transparent 70%);
        border-radius: 50%;
        border: 0.5px solid rgba(255, 255, 255, 0.08);
        box-shadow: inset 0 0 40px rgba(255, 255, 255, 0.02);
    }
    .home-sonar-wrap .sonar-ring { 
        position: absolute; 
        left: 50%; 
        top: 50%; 
        width: 50px; 
        height: 50px; 
        margin: -25px 0 0 -25px; 
        border-radius: 50%; 
        border: 1.5px solid rgba(255, 255, 255, 0.25);
        transform-origin: center center; 
        animation: home-sonar-ping 10s cubic-bezier(0.4, 0, 0.2, 1) infinite; 
        animation-fill-mode: both; 
        z-index: 1;
    }
    .home-sonar-wrap .sonar-ring:nth-child(1) { animation-delay: 0s; }
    .home-sonar-wrap .sonar-ring:nth-child(2) { animation-delay: 2s; }
    .home-sonar-wrap .sonar-ring:nth-child(3) { animation-delay: 4s; }
    .home-sonar-wrap .sonar-ring:nth-child(4) { animation-delay: 6s; }
    .home-sonar-wrap .sonar-ring:nth-child(5) { animation-delay: 8s; }
    .home-sonar-wrap .sonar-dot { 
        position: absolute; 
        left: 50%; 
        top: 50%; 
        width: 18px; 
        height: 18px; 
        margin: -9px 0 0 -9px; 
        border-radius: 50%; 
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.9), rgba(245, 245, 247, 0.7));
        box-shadow: 0 0 24px rgba(255, 255, 255, 0.5), 
                    0 0 48px rgba(255, 255, 255, 0.25),
                    inset 0 1px 0 rgba(255, 255, 255, 1);
        transform-origin: center center; 
        animation: sonar-dot-pulse 2.5s ease-in-out infinite; 
        z-index: 10;
        border: 0.5px solid rgba(255, 255, 255, 0.4);
    }
    @keyframes sonar-dot-pulse { 
        0%, 100% { 
            transform: scale(0.85); 
            opacity: 0.75;
            box-shadow: 0 0 24px rgba(255, 255, 255, 0.5), 
                        0 0 48px rgba(255, 255, 255, 0.25),
                        inset 0 1px 0 rgba(255, 255, 255, 1);
        } 
        50% { 
            transform: scale(1.15); 
            opacity: 1;
            box-shadow: 0 0 36px rgba(255, 255, 255, 0.7), 
                        0 0 72px rgba(255, 255, 255, 0.35),
                        inset 0 1px 0 rgba(255, 255, 255, 1);
        } 
    }
    .home-sonar-wrap .sonar-blip { 
        position: absolute; 
        width: 7px; 
        height: 7px; 
        margin: -3.5px 0 0 -3.5px; 
        border-radius: 50%; 
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(245, 245, 247, 0.85));
        box-shadow: 0 0 16px rgba(255, 255, 255, 0.7), 
                    0 0 32px rgba(255, 255, 255, 0.4),
                    inset 0 1px 0 rgba(255, 255, 255, 0.9); 
        opacity: 0; 
        animation: radar-blip 10s cubic-bezier(0.4, 0, 0.2, 1) infinite; 
        animation-fill-mode: both; 
        pointer-events: none; 
        z-index: 2;
        border: 0.5px solid rgba(255, 255, 255, 0.6);
    }
    @keyframes home-sonar-ping { 
        0% { 
            transform: scale(0.2); 
            opacity: 0.7; 
            border-color: rgba(255, 255, 255, 0.35);
            border-width: 1.5px;
        } 
        30% { 
            opacity: 0.5; 
            border-color: rgba(255, 255, 255, 0.2);
        } 
        70% { 
            opacity: 0.15; 
            border-color: rgba(255, 255, 255, 0.08);
            border-width: 1px;
        } 
        100% { 
            transform: scale(5); 
            opacity: 0; 
            border-color: rgba(255, 255, 255, 0.02);
            border-width: 0.5px;
        } 
    }
    @keyframes radar-blip { 
        0%, 8% { opacity: 0; transform: scale(0.4); } 
        10% { opacity: 1; transform: scale(1); } 
        12% { opacity: 0.95; transform: scale(1.15); } 
        18% { opacity: 0.5; transform: scale(1); } 
        24% { opacity: 0; transform: scale(0.8); } 
        100% { opacity: 0; transform: scale(0.8); } 
    }
    .home-sonar-hint-wrap {
        margin-top: 200px;
        padding-top: 0;
    }
    .home-sonar-hint { 
        font-size: 1.05rem; 
        margin: 0; 
        font-weight: 500; 
        letter-spacing: 0.5px;
        color: rgba(255, 255, 255, 0.5);
        padding: 0;
        background: none;
        border: none;
        text-shadow: none;
        animation: none;
    }
    .home-sonar-hint::before { 
        content: '📡'; 
        font-size: 1.15rem; 
        opacity: 0.7;
        margin-right: 8px;
    }
    
    /* [탭 중앙 정렬] 시세 분석, 마켓소스 등 */
    div[data-baseweb="tab-list"] { justify-content: center !important; }
    [data-testid="stTabs"] > div { justify-content: center !important; }
    [data-baseweb="tab-list"] { display: flex !important; justify-content: center !important; }
    
    /* [탭 선택 밑줄] 배포/로컬 동일하게 블루 (테마 그린 덮어씀) */
    [data-testid="stTabs"] [data-baseweb="tab-list"] [aria-selected="true"] {
        border-bottom: 2px solid #5C9EFF !important;
        color: #5C9EFF !important;
    }
    /* Base Web 이동형 밑줄은 첫 로드 시 위치가 왼쪽으로 틀어지므로 숨기고, 선택 탭의 border-bottom만 사용 */
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        display: none !important;
    }
    
    /* [탭 전환] 애플 스타일 - 왼쪽에서 슬라이드 인 */
    [data-testid="stTabs"] > div:last-child {
        overflow: visible !important;
        animation: tab-slide-in 0.42s cubic-bezier(0.32, 0.72, 0, 1) forwards;
    }
    [data-testid="stTabs"] [data-testid="stVerticalBlock"] {
        animation: tab-slide-in 0.42s cubic-bezier(0.32, 0.72, 0, 1) forwards;
    }
    @keyframes tab-slide-in {
        from {
            opacity: 0;
            transform: translateX(-32px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    /* Market Buttons - Apple Design System */
    div[data-testid="stLinkButton"] > a { 
        background: rgba(255, 255, 255, 0.06) !important; 
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 16px !important; 
        font-weight: 600 !important; 
        transition: all 0.2s ease !important; 
        text-decoration: none !important; 
        height: 100px !important;
        display: flex !important; 
        flex-direction: column !important; 
        align-items: center !important; 
        justify-content: center !important; 
        font-size: 1rem !important; 
        letter-spacing: -0.3px !important;
        color: #F5F5F7 !important; 
        box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif !important;
        position: relative !important;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif !important;
    }
    div[data-testid="stLinkButton"] > a::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, 
            transparent 0%, 
            rgba(255, 255, 255, 0.25) 50%, 
            transparent 100%);
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    div[data-testid="stLinkButton"] > a:hover::before {
        opacity: 1;
    }
    div[data-testid="stLinkButton"] > a:active {
        transform: scale(0.97) !important;
        box-shadow: 0 3px 12px rgba(0,0,0,0.2), 
                    inset 0 1px 0 rgba(255,255,255,0.1) !important;
        animation: haptic-pulse 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    /* Haptic Feedback Animation */
    @keyframes haptic-pulse {
        0% { transform: scale(1); }
        50% { transform: scale(0.94); }
        100% { transform: scale(0.97); }
    }
    /* Market-specific colors (simplified) */
    a[href*="bunjang"] { border-left: 3px solid #FF453A !important; }
    a[href*="bunjang"]:hover { background: rgba(255, 69, 58, 0.1) !important; border-color: rgba(255, 69, 58, 0.25) !important; }
    
    a[href*="daangn"] { border-left: 3px solid #FF9F0A !important; }
    a[href*="daangn"]:hover { background: rgba(255, 159, 10, 0.1) !important; border-color: rgba(255, 159, 10, 0.25) !important; }
    
    a[href*="joongna"] { border-left: 3px solid #30D158 !important; }
    a[href*="joongna"]:hover { background: rgba(48, 209, 88, 0.1) !important; border-color: rgba(48, 209, 88, 0.25) !important; }
    
    a[href*="fruits"] { border-left: 3px solid #BF5AF2 !important; }
    a[href*="fruits"]:hover { background: rgba(191, 90, 242, 0.1) !important; border-color: rgba(191, 90, 242, 0.25) !important; }
    
    a[href*="ebay"] { border-left: 3px solid #0A84FF !important; }
    a[href*="ebay"]:hover { background: rgba(10, 132, 255, 0.1) !important; border-color: rgba(10, 132, 255, 0.25) !important; }
    
    a[href*="mercari"] { border-left: 3px solid #8E8E93 !important; }
    a[href*="mercari"]:hover { background: rgba(142, 142, 147, 0.1) !important; }
    
    /* Ghost Button (TheCheat) */
    a[href*="thecheat"] {
        background-color: transparent !important; border: 1px solid #666 !important; color: #888 !important; height: 60px !important; font-size: 1rem !important;
    }
    a[href*="thecheat"]:hover {
        background-color: #00B4DB !important; border-color: #00B4DB !important; color: #fff !important; box-shadow: 0 0 15px rgba(0, 180, 219, 0.5);
    }

    /* Source Cards - Apple Design System */
    .source-card {
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.12); 
        border-radius: 12px; 
        padding: 16px; 
        display: flex; 
        align-items: center; 
        justify-content: space-between; 
        margin-bottom: 12px; 
        transition: all 0.2s ease;
        text-decoration: none;
        height: 64px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        cursor: pointer;
    }
    .source-card:hover {
        background: rgba(255, 255, 255, 0.08);
        border-color: rgba(255, 255, 255, 0.18);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    }
    .source-card:active {
        transform: translateY(0);
    }
    body.light-mode .source-card {
        background: #FFFBF5;
        border: 1px solid rgba(0, 0, 0, 0.2);
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
    }
    body.light-mode .source-card:hover {
        background: #FFF5E8;
        border-color: rgba(0, 0, 0, 0.3);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    
    /* Hover Effects - Apple Style Glow */
    .card-quasar:hover { background: rgba(255, 159, 10, 0.12); border-color: rgba(255, 159, 10, 0.3); }
    .card-cool:hover { background: rgba(229, 229, 234, 0.12); border-color: rgba(229, 229, 234, 0.3); }
    .card-meeco:hover { background: rgba(0, 122, 255, 0.12); border-color: rgba(0, 122, 255, 0.3); }
    .card-clien:hover { background: rgba(94, 92, 230, 0.12); border-color: rgba(94, 92, 230, 0.3); }
    
    .card-slr:hover { background: rgba(10, 132, 255, 0.12); border-color: rgba(10, 132, 255, 0.3); }
    .card-leica:hover { background: rgba(255, 59, 48, 0.12); border-color: rgba(255, 59, 48, 0.3); }
    .card-film:hover { background: rgba(255, 214, 10, 0.12); border-color: rgba(255, 214, 10, 0.3); }
    .card-dof:hover { background: rgba(142, 142, 147, 0.12); border-color: rgba(142, 142, 147, 0.3); }
    
    .card-nike:hover { background: rgba(99, 99, 102, 0.12); border-color: rgba(99, 99, 102, 0.3); }
    .card-kream:hover { background: rgba(245, 245, 247, 0.12); border-color: rgba(245, 245, 247, 0.3); }
    .card-eomisae:hover { background: rgba(191, 90, 242, 0.12); border-color: rgba(191, 90, 242, 0.3); }
    .card-diesel:hover { background: rgba(99, 99, 102, 0.12); border-color: rgba(99, 99, 102, 0.3); }
    
    .card-asamo:hover { background: rgba(50, 215, 75, 0.12); border-color: rgba(50, 215, 75, 0.3); }
    .card-mac:hover { background: rgba(152, 152, 157, 0.12); border-color: rgba(152, 152, 157, 0.3); }
    .card-joongna:hover { background: rgba(48, 209, 88, 0.12); border-color: rgba(48, 209, 88, 0.3); }
    .card-ruli:hover { background: rgba(94, 92, 230, 0.12); border-color: rgba(94, 92, 230, 0.3); }
    .card-pompu:hover { background: rgba(255, 159, 10, 0.12); border-color: rgba(255, 159, 10, 0.3); }
    .card-bobaedream:hover { background: rgba(50, 215, 75, 0.12); border-color: rgba(50, 215, 75, 0.3); }
    .card-ohou:hover { background: rgba(255, 55, 95, 0.12); border-color: rgba(255, 55, 95, 0.3); }
    .card-gmarket:hover { background: rgba(255, 214, 10, 0.12); border-color: rgba(255, 214, 10, 0.3); }
    .card-musinsa:hover { background: rgba(28, 28, 30, 0.12); border-color: rgba(28, 28, 30, 0.3); }
    .card-bunjang:hover { background: rgba(255, 69, 58, 0.12); border-color: rgba(255, 69, 58, 0.3); }
    .card-daangn:hover { background: rgba(255, 159, 10, 0.12); border-color: rgba(255, 159, 10, 0.3); }
    .card-fruits:hover { background: rgba(191, 90, 242, 0.12); border-color: rgba(191, 90, 242, 0.3); }
    .card-auction:hover { background: rgba(255, 69, 58, 0.12); border-color: rgba(255, 69, 58, 0.3); }
    .card-ebay:hover { background: rgba(10, 132, 255, 0.12); border-color: rgba(10, 132, 255, 0.3); }
    .card-mercari:hover { background: rgba(142, 142, 147, 0.12); border-color: rgba(142, 142, 147, 0.3); }

    /* Left Color Tags - Apple Colors */
    .card-quasar { border-left: 3px solid #FF9F0A !important; }
    .card-cool { border-left: 3px solid #E5E5EA !important; }
    .card-meeco { border-left: 3px solid #007AFF !important; }
    .card-clien { border-left: 3px solid #5E5CE6 !important; }
    
    .card-slr { border-left: 3px solid #0A84FF !important; }
    .card-leica { border-left: 3px solid #FF3B30 !important; }
    .card-film { border-left: 3px solid #FFD60A !important; }
    .card-dof { border-left: 3px solid #8E8E93 !important; }
    
    .card-nike { border-left: 3px solid #636366 !important; }
    .card-kream { border-left: 3px solid #F5F5F7 !important; }
    .card-eomisae { border-left: 3px solid #BF5AF2 !important; }
    .card-diesel { border-left: 3px solid #636366 !important; }
    
    .card-asamo { border-left: 3px solid #32D74B !important; }
    .card-mac { border-left: 3px solid #98989D !important; }
    .card-joongna { border-left: 3px solid #30D158 !important; }
    .card-ruli { border-left: 3px solid #5E5CE6 !important; }
    .card-pompu { border-left: 3px solid #FF9F0A !important; }
    .card-bobaedream { border-left: 3px solid #32D74B !important; }
    .card-ohou { border-left: 3px solid #FF375F !important; }
    .card-gmarket { border-left: 3px solid #FFD60A !important; }
    .card-musinsa { border-left: 3px solid #1C1C1E !important; }
    .card-bunjang { border-left: 3px solid #FF453A !important; }
    .card-daangn { border-left: 3px solid #FF9F0A !important; }
    .card-fruits { border-left: 3px solid #BF5AF2 !important; }
    .card-auction { border-left: 3px solid #FF453A !important; }
    .card-ebay { border-left: 3px solid #0A84FF !important; }
    .card-mercari { border-left: 3px solid #8E8E93 !important; }

    .source-info { display: flex; flex-direction: column; gap: 4px; }
    .source-name { 
        font-size: 1rem; 
        font-weight: 600; 
        color: #F5F5F7; 
        letter-spacing: -0.3px;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif;
    }
    .source-desc { 
        font-size: 0.75rem; 
        color: #8E8E93; 
        font-weight: 400; 
        letter-spacing: -0.1px;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif;
    }
    
    /* Category Header - Apple Design System */
    .category-header { 
        font-size: 0.75rem; 
        font-weight: 600; 
        color: #8E8E93; 
        margin-top: 32px; 
        margin-bottom: 12px; 
        letter-spacing: 0.5px; 
        text-transform: uppercase; 
        border-bottom: 1px solid rgba(255, 255, 255, 0.08); 
        padding-bottom: 8px;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif;
    }
    .category-header:first-of-type { margin-top: 0; }
    .source-card { margin-bottom: 12px !important; }

    /* Ticker (다크모드 - 항목별 색상) */
    .ticker-wrap { position: fixed; bottom: 0; left: 0; width: 100%; height: 32px; background-color: #0E1117; border-top: 1px solid #1C1C1E; z-index: 999; display: flex; align-items: center; }
    .ticker { display: inline-block; white-space: nowrap; padding-left: 100%; animation: ticker 40s linear infinite; }
    .ticker-item { margin-right: 40px; font-size: 0.8rem; font-family: 'Inter', sans-serif; font-weight: 500; }
    .ticker-val { font-weight: 700; margin-left: 5px; }
    .ticker-item.ticker-usd, .ticker-item.ticker-usd .ticker-val { color: #5C9EFF !important; }
    .ticker-item.ticker-jpy, .ticker-item.ticker-jpy .ticker-val { color: #2dd4bf !important; }
    .ticker-item.ticker-limit-us, .ticker-item.ticker-limit-us .ticker-val,
    .ticker-item.ticker-limit-jp, .ticker-item.ticker-limit-jp .ticker-val { color: #4ade80 !important; }
    .ticker-item.ticker-rate { color: #9ca3af !important; }
    .ticker-item.ticker-sys, .ticker-item.ticker-sys .ticker-val { color: #60a5fa !important; }
    .ticker-up { color: #ff4b4b; background: rgba(255, 75, 75, 0.1); padding: 2px 4px; border-radius: 4px; font-size: 0.75rem; }
    .ticker-down { color: #4b89ff; background: rgba(75, 137, 255, 0.1); padding: 2px 4px; border-radius: 4px; font-size: 0.75rem; }
    @keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-100%, 0, 0); } }
    
    /* Scam Box - Apple Design System */
    .scam-box { 
        border: 1px solid rgba(255, 69, 58, 0.25); 
        border-left: 3px solid #FF453A; 
        background: rgba(255, 69, 58, 0.08);
        padding: 32px; 
        border-radius: 12px; 
        margin-bottom: 0;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    }
    .scam-list { 
        margin-top: 12px; 
        padding-left: 0; 
        list-style-type: none; 
    }
    .scam-item { 
        color: #F5F5F7; 
        margin-bottom: 24px; 
        line-height: 1.6; 
        font-size: 0.9375rem; 
        border-bottom: 1px solid rgba(255, 255, 255, 0.08); 
        padding-bottom: 24px; 
    }
    .scam-item:last-child { border-bottom: none; padding-bottom: 0; margin-bottom: 0; }
    .scam-head { 
        color: #FF453A; 
        font-weight: 600; 
        font-size: 1rem; 
        display: block; 
        margin-bottom: 8px; 
        letter-spacing: -0.2px;
    }
    
    .legal-footer { font-size: 0.7rem; color: #333; margin-top: 80px; text-align: center; margin-bottom: 50px; }
    
    /* Buttons - Apple Design System */
    button[kind="primary"],
    button[kind="secondary"] {
        background: rgba(10, 132, 255, 0.15) !important;
        border: 1px solid rgba(10, 132, 255, 0.3) !important;
        border-radius: 12px !important;
        color: #0A84FF !important;
        font-weight: 500 !important;
        padding: 10px 20px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif !important;
        font-size: 1rem !important;
    }
    body.light-mode button[kind="primary"],
    body.light-mode button[kind="secondary"] {
        background: rgba(0, 122, 255, 0.1) !important;
        border: 1px solid rgba(0, 122, 255, 0.3) !important;
        color: #007AFF !important;
    }
    button[kind="primary"]:hover,
    button[kind="secondary"]:hover {
        background: rgba(10, 132, 255, 0.25) !important;
        border-color: rgba(10, 132, 255, 0.4) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12) !important;
    }
    body.light-mode button[kind="primary"]:hover,
    body.light-mode button[kind="secondary"]:hover {
        background: rgba(0, 122, 255, 0.2) !important;
        border-color: rgba(0, 122, 255, 0.4) !important;
        box-shadow: 0 2px 8px rgba(0, 122, 255, 0.15) !important;
    }
    button[kind="primary"]:active,
    button[kind="secondary"]:active {
        transform: translateY(0) !important;
    }
    
    /* Search Input - 통합 스타일은 아래에서 정의 */
    .stTextInput,
    .stTextInput > div,
    .stTextInput > div > div {
        background: transparent !important;
        border: none !important;
        outline: none !important;
        padding: 0 !important;
    }
    
    /* Other Inputs - Apple Design System */
    .stSelectbox > div > div,
    .stNumberInput > div > div,
    textarea,
    input[type="number"],
    input[type="text"] {
        background: rgba(255, 255, 255, 0.06) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 12px !important;
        color: #F5F5F7 !important;
        transition: all 0.2s ease !important;
        padding: 12px 16px !important;
        font-size: 1rem !important;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif !important;
    }
    .stSelectbox > div > div > div {
        background: transparent !important;
        border: none !important;
    }
    .stNumberInput > div > div,
    input[type="number"],
    textarea {
        height: auto !important;
        min-height: 44px !important;
    }
    .stSelectbox > div > div:focus-within,
    .stNumberInput > div > div:focus-within,
    input[type="number"]:focus,
    input[type="text"]:focus,
    textarea:focus {
        border-color: rgba(10, 132, 255, 0.5) !important;
        background: rgba(255, 255, 255, 0.08) !important;
        outline: none !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
    }
    .stSelectbox > div > div:hover,
    .stNumberInput > div > div:hover,
    input:hover,
    textarea:hover {
        background: rgba(255, 255, 255, 0.07) !important;
    }

    /* Ticker */
    .ticker-up { color: #ff4b4b; font-weight: 700; font-size: 0.9rem; }
    .ticker-down { color: #4b89ff; font-weight: 700; font-size: 0.9rem; }

    .capsule-sub { font-size: 0.72rem; color: #8E8E93; margin-left: 10px; font-weight: 500; letter-spacing: 0.6px; }
    
    /* Capsule Title - Apple Design System */
    .capsule-title {
        display: inline-block; 
        padding: 10px 20px; 
        background: rgba(10, 132, 255, 0.12);
        color: #0A84FF; 
        border: 1px solid rgba(10, 132, 255, 0.25);
        border-radius: 20px;
        font-size: 1rem; 
        font-weight: 600; 
        margin-top: 32px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif; 
        margin-bottom: 16px; 
        letter-spacing: -0.3px;
    }

    /* Section Title - unified below */
    
    /* Waiting for Signal - 차분한 펄스 */
    .waiting-signal { 
        animation: signal-pulse 4s ease-in-out infinite; 
        padding: 8px 0;
    }
    @keyframes signal-pulse {
        0%, 100% { opacity: 0.7; }
        50% { opacity: 0.95; }
    }
    
    /* 대기 시각화 스타일들 */
    .viz-wrap { background: rgba(20,25,35,0.6); border-radius: 12px; padding: 16px; margin: 8px 0; border: 1px solid rgba(255,255,255,0.06); }
    .eq-wrap { display: flex; align-items: flex-end; justify-content: center; gap: 6px; height: 80px; }
    .eq-bar { width: 8px; background: rgba(92,158,255,0.5); border-radius: 4px; min-height: 8px; }
    .eq-bar:nth-child(1) { animation: eq1 1.2s ease-in-out infinite; }
    .eq-bar:nth-child(2) { animation: eq2 1.2s ease-in-out infinite 0.15s; }
    .eq-bar:nth-child(3) { animation: eq3 1.2s ease-in-out infinite 0.3s; }
    .eq-bar:nth-child(4) { animation: eq4 1.2s ease-in-out infinite 0.45s; }
    .eq-bar:nth-child(5) { animation: eq5 1.2s ease-in-out infinite 0.6s; }
    .eq-bar:nth-child(6) { animation: eq4 1.2s ease-in-out infinite 0.45s; }
    .eq-bar:nth-child(7) { animation: eq3 1.2s ease-in-out infinite 0.3s; }
    .eq-bar:nth-child(8) { animation: eq2 1.2s ease-in-out infinite 0.15s; }
    .eq-bar:nth-child(9) { animation: eq1 1.2s ease-in-out infinite; }
    @keyframes eq1 { 0%,100% { height: 12px; } 50% { height: 50px; } }
    @keyframes eq2 { 0%,100% { height: 20px; } 50% { height: 65px; } }
    @keyframes eq3 { 0%,100% { height: 30px; } 50% { height: 75px; } }
    @keyframes eq4 { 0%,100% { height: 25px; } 50% { height: 55px; } }
    @keyframes eq5 { 0%,100% { height: 15px; } 50% { height: 70px; } }
    
    .dots-wrap { display: flex; justify-content: center; gap: 10px; padding: 20px; }
    .pulse-dot { width: 10px; height: 10px; border-radius: 50%; background: rgba(92,158,255,0.6); }
    .pulse-dot:nth-child(1) { animation: dot-pulse 1.5s ease-in-out infinite; }
    .pulse-dot:nth-child(2) { animation: dot-pulse 1.5s ease-in-out infinite 0.2s; }
    .pulse-dot:nth-child(3) { animation: dot-pulse 1.5s ease-in-out infinite 0.4s; }
    @keyframes dot-pulse { 0%,100% { transform: scale(0.8); opacity: 0.4; } 50% { transform: scale(1.2); opacity: 1; } }
    
    .scan-wrap { height: 80px; position: relative; overflow: hidden; border-radius: 8px; }
    .scan-line-v { position: absolute; left: 0; right: 0; height: 4px; background: linear-gradient(90deg, transparent, rgba(92,158,255,0.7), transparent); animation: scan-down 2.5s ease-in-out infinite; }
    @keyframes scan-down { 0% { top: 0; opacity: 0.6; } 50% { opacity: 1; } 100% { top: calc(100% - 4px); opacity: 0.6; } }
    
    .breath-wrap { display: flex; justify-content: center; align-items: center; height: 100px; }
    .breath-circle { width: 60px; height: 60px; border-radius: 50%; border: 2px solid rgba(92,158,255,0.4); animation: breath 3s ease-in-out infinite; }
    @keyframes breath { 0%,100% { transform: scale(0.85); opacity: 0.5; } 50% { transform: scale(1.1); opacity: 0.9; } }
    
    /* Sonar rings - CSS only */
    .sonar-wrap { display: flex; justify-content: center; align-items: center; height: 220px; position: relative; }
    .sonar-ring { position: absolute; width: 40px; height: 40px; border-radius: 50%; border: 2px solid rgba(59,130,246,0.6); animation: sonar-ping 2.5s ease-out infinite; }
    .sonar-ring:nth-child(1) { animation-delay: 0s; }
    .sonar-ring:nth-child(2) { animation-delay: 0.5s; }
    .sonar-ring:nth-child(3) { animation-delay: 1s; }
    .sonar-ring:nth-child(4) { animation-delay: 1.5s; }
    .sonar-ring:nth-child(5) { animation-delay: 2s; }
    @keyframes sonar-ping { 0% { transform: scale(0.3); opacity: 1; border-color: rgba(59,130,246,0.8); } 100% { transform: scale(4); opacity: 0; border-color: rgba(59,130,246,0.1); } }
    
    /* 차트 스타일은 하단 카드 규칙 사용 */
    /* None 숨기기 - 단일 p만 있는 블록만 숨김 (메트릭 카드 등 HTML 블록은 유지) */
    div[data-testid="stMarkdown"]:has(p:only-child) {
        font-size: 0 !important; line-height: 0 !important;
        overflow: hidden !important; height: 0 !important;
        margin: 0 !important; padding: 0 !important;
        min-height: 0 !important; display: block !important;
    }

    /* [NEW] 스켈레톤 로딩 - 차트/카드 영역 */
    /* Skeleton Loading - Apple Style */
    .skeleton-wrap { 
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.02), rgba(245, 245, 247, 0.01)); 
        border-radius: 20px; 
        padding: 24px; 
        margin: 20px 0; 
        border: 0.5px solid rgba(255,255,255,0.08);
        animation: skeleton-fade 1.5s ease-in-out infinite;
    }
    .skeleton-card { 
        background: linear-gradient(90deg, 
            rgba(255, 255, 255, 0.04) 0%, 
            rgba(255, 255, 255, 0.08) 50%, 
            rgba(255, 255, 255, 0.04) 100%); 
        background-size: 200% 100%; 
        animation: skeleton-shimmer 2s cubic-bezier(0.4, 0, 0.2, 1) infinite; 
        border-radius: 16px; 
        height: 60px; 
        margin-bottom: 12px;
        border: 0.5px solid rgba(255, 255, 255, 0.06);
    }
    .skeleton-chart { 
        background: linear-gradient(90deg, 
            rgba(255, 255, 255, 0.04) 0%, 
            rgba(255, 255, 255, 0.08) 50%, 
            rgba(255, 255, 255, 0.04) 100%); 
        background-size: 200% 100%; 
        animation: skeleton-shimmer 2s cubic-bezier(0.4, 0, 0.2, 1) infinite; 
        border-radius: 20px; 
        height: 320px; 
        margin: 16px 0;
        border: 0.5px solid rgba(255, 255, 255, 0.08);
    }
    .skeleton-chart-sm { 
        background: linear-gradient(90deg, 
            rgba(255, 255, 255, 0.04) 0%, 
            rgba(255, 255, 255, 0.08) 50%, 
            rgba(255, 255, 255, 0.04) 100%); 
        background-size: 200% 100%; 
        animation: skeleton-shimmer 2s cubic-bezier(0.4, 0, 0.2, 1) infinite; 
        border-radius: 20px; 
        height: 260px; 
        margin: 16px 0;
        border: 0.5px solid rgba(255, 255, 255, 0.08);
    }
    .skeleton-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    @keyframes skeleton-shimmer { 
        0% { background-position: -200% 0; } 
        100% { background-position: 200% 0; } 
    }
    @keyframes skeleton-fade {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }

    /* Search Pills - Premium iOS Style */
    .search-pills { 
        display: flex; 
        flex-wrap: wrap; 
        gap: 10px; 
        margin: 18px 0 28px 0; 
        align-items: center; 
        justify-content: center;
        padding: 2px 0;
    }
    .search-pills a {
        display: inline-block; 
        padding: 8px 16px; 
        background: rgba(10, 132, 255, 0.12);
        color: #0A84FF;
        border-radius: 16px; 
        border: 1px solid rgba(10, 132, 255, 0.25); 
        font-size: 0.875rem; 
        font-weight: 500; 
        text-decoration: none;
        white-space: nowrap; 
        transition: all 0.2s ease;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        letter-spacing: -0.2px;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif;
    }
    /* Category Colors - Premium Palette */
    .search-pills a[href*="조던"], .search-pills a[href*="덩크"], .search-pills a[href*="나이키"] {
        background: rgba(255, 69, 0, 0.12); color: #FF6B35; border-color: rgba(255, 69, 0, 0.25);
    }
    .search-pills a[href*="조던"]:hover, .search-pills a[href*="덩크"]:hover, .search-pills a[href*="나이키"]:hover {
        background: rgba(255, 69, 0, 0.2); border-color: rgba(255, 69, 0, 0.35);
    }
    .search-pills a[href*="롤렉스"], .search-pills a[href*="샤넬"], .search-pills a[href*="에르메스"], .search-pills a[href*="루이비통"] {
        background: rgba(255, 204, 0, 0.12); color: #FFCC00; border-color: rgba(255, 204, 0, 0.25);
    }
    .search-pills a[href*="롤렉스"]:hover, .search-pills a[href*="샤넬"]:hover, .search-pills a[href*="에르메스"]:hover, .search-pills a[href*="루이비통"]:hover {
        background: rgba(255, 204, 0, 0.2); border-color: rgba(255, 204, 0, 0.35);
    }
    .search-pills a[href*="아이폰"], .search-pills a[href*="맥북"], .search-pills a[href*="갤럭시"], .search-pills a[href*="RTX"] {
        background: rgba(10, 132, 255, 0.12); color: #0A84FF; border-color: rgba(10, 132, 255, 0.25);
    }
    .search-pills a[href*="아이폰"]:hover, .search-pills a[href*="맥북"]:hover, .search-pills a[href*="갤럭시"]:hover, .search-pills a[href*="RTX"]:hover {
        background: rgba(10, 132, 255, 0.2); border-color: rgba(10, 132, 255, 0.35);
    }
    .search-pills a[href*="스투시"], .search-pills a[href*="아크테릭스"], .search-pills a[href*="카피탈"] {
        background: rgba(52, 199, 89, 0.12); color: #34C759; border-color: rgba(52, 199, 89, 0.25);
    }
    .search-pills a[href*="스투시"]:hover, .search-pills a[href*="아크테릭스"]:hover, .search-pills a[href*="카피탈"]:hover {
        background: rgba(52, 199, 89, 0.2); border-color: rgba(52, 199, 89, 0.35);
    }
    .search-pills a:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    }
    .search-pills a:active {
        transform: translateY(0);
    }
    
    /* Section Title - Apple Design System */
    .section-title {
        margin-top: 32px; 
        margin-bottom: 0; 
        font-weight: 600; 
        font-size: 1.375rem; 
        color: #F5F5F7;
        padding: 18px 20px;
        letter-spacing: -0.5px;
        position: relative;
        display: block;
        line-height: 1.3;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 16px;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        transition: all 0.3s ease;
    }
    body.light-mode .section-title {
        color: #0D0D0D;
        background: #FFFBF5;
        border: 1px solid rgba(0, 0, 0, 0.22);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    }
    .section-title--chart {
        border-bottom-left-radius: 0;
        border-bottom-right-radius: 0;
        border-bottom: none;
    }
    .section-title--price-summary { 
        border-bottom-left-radius: 0;
        border-bottom-right-radius: 0;
        border-bottom: none;
        position: relative;
        padding-right: 200px;
    }
    .section-title .title-icon {
        display: inline-block;
        margin-right: 10px;
        font-size: 1.2em;
        vertical-align: middle;
        transition: transform 0.3s ease;
    }
    .section-title:hover .title-icon {
        transform: scale(1.15) rotate(5deg);
        animation: icon-bounce 0.6s ease;
    }
    @keyframes icon-bounce {
        0%, 100% { transform: scale(1.15) rotate(5deg); }
        50% { transform: scale(1.25) rotate(-5deg); }
    }
    /* Metric Grid - Apple Design System */
    .metric-grid { 
        display: grid; 
        grid-template-columns: 1fr 1fr; 
        gap: 12px; 
        margin: 0; 
        padding: 20px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-top: none;
        border-radius: 0 0 16px 16px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        margin-bottom: 24px;
        transition: all 0.3s ease;
    }
    body.light-mode .metric-grid {
        background: #FFFBF5;
        border: 1px solid rgba(0, 0, 0, 0.2);
        border-top: none;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.07);
        border: 1px solid rgba(255, 255, 255, 0.12); 
        border-radius: 12px; 
        padding: 16px;
        display: flex; 
        flex-direction: column; 
        gap: 6px;
        transition: all 0.2s ease;
        cursor: pointer;
        position: relative;
        overflow: hidden;
    }
    body.light-mode .metric-card {
        background: #FFFBF5;
        border: 1px solid rgba(0, 0, 0, 0.18);
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
    }
    body.light-mode .metric-card:hover {
        background: #FFF5E8;
        border-color: rgba(0, 0, 0, 0.28);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, 
            transparent 0%, 
            rgba(10, 132, 255, 0.08) 50%, 
            transparent 100%);
        transition: left 0.5s ease;
    }
    .metric-card:hover::before {
        left: 100%;
    }
    .metric-card:hover {
        background: rgba(10, 132, 255, 0.1);
        border-color: rgba(10, 132, 255, 0.3);
        transform: translateY(-3px);
        box-shadow: 0 6px 16px rgba(10, 132, 255, 0.2);
    }
    .metric-card:active {
        transform: translateY(-1px);
    }
    .metric-card > * {
        position: relative;
        z-index: 1;
    }
    
    .metric-label { 
        font-size: 0.75rem; 
        color: #8E8E93; 
        font-weight: 500; 
        text-transform: uppercase; 
        letter-spacing: 0.5px;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif;
        transition: color 0.3s ease;
    }
    body.light-mode .metric-label {
        color: #3A3A3C;
    }
    .metric-value { 
        font-size: 1.75rem; 
        font-weight: 600; 
        color: #F5F5F7; 
        letter-spacing: -0.5px;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif;
        transition: color 0.3s ease;
    }
    body.light-mode .metric-value {
        color: #0D0D0D;
    }
    .metric-change { 
        font-size: 0.75rem; 
        font-weight: 600;
        margin-top: 6px;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif;
        opacity: 0.95;
    }
    .metric-change-label {
        display: inline;
        font-size: 0.65rem;
        font-weight: 500;
        opacity: 0.7;
        margin-left: 6px;
    }

    /* Price data label */
    .price-data-label {
        position: absolute;
        top: 50%;
        right: 20px;
        transform: translateY(-50%);
        font-size: 0.75rem;
        color: #8E8E93;
        font-weight: 400;
        background: rgba(142, 142, 147, 0.12);
        padding: 6px 12px;
        border-radius: 12px;
        border: 1px solid rgba(142, 142, 147, 0.2);
    }
    .price-data-label strong {
        color: #F5F5F7;
        font-weight: 500;
        margin-left: 4px;
    }
    
    /* Tool Header - Apple Design System */
    .tool-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #F5F5F7;
        margin-bottom: 20px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        letter-spacing: -0.4px;
        line-height: 1.3;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif;
    }
    
    /* Compare Tab - Apple Design System */
    .compare-intro {
        text-align: center;
        padding: 32px 20px;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        margin-bottom: 32px;
        border: 1px solid rgba(255, 255, 255, 0.12);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    }
    .compare-intro-title {
        font-size: 1.5rem;
        font-weight: 600;
        color: #F5F5F7;
        margin-bottom: 12px;
        letter-spacing: -0.4px;
    }
    .compare-intro-desc {
        font-size: 1rem;
        color: #8E8E93;
        font-weight: 400;
    }
    .vs-badge {
        background: rgba(255, 255, 255, 0.1);
        color: #F5F5F7;
        font-weight: 700;
        font-size: 1.125rem;
        text-align: center;
        padding: 12px 0;
        border-radius: 12px;
        margin-top: 24px;
        border: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        letter-spacing: 0.5px;
    }
    .compare-result-box {
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 16px;
        padding: 32px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        transition: all 0.2s ease;
    }
    .compare-result-box:hover {
        background: rgba(255, 255, 255, 0.08);
        border-color: rgba(255, 255, 255, 0.18);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    }
    .result-label {
        font-size: 0.85rem;
        color: rgba(255, 255, 255, 0.55);
        font-weight: 600;
        margin-bottom: 18px;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
    }
    .result-content {
        font-size: 1.5rem;
        font-weight: 600;
        color: #F5F5F7;
        margin-bottom: 22px;
        line-height: 1.6;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    }
    .winner-badge {
        background: rgba(255, 255, 255, 0.15);
        color: #FFFFFF;
        padding: 8px 16px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        font-weight: 600;
        font-size: 1.25rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        display: inline-block;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif;
    }
    .price-diff {
        color: #0A84FF;
        font-weight: 600;
        font-size: 1.75rem;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif;
        letter-spacing: -0.5px;
    }
    .result-detail {
        font-size: 0.9375rem;
        color: #C7C7CC;
        padding-top: 20px;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif;
    }
    .result-detail strong {
        color: #F5F5F7;
        font-weight: 500;
    }
    /* Empty State - Apple Design System */
    .empty-state {
        text-align: center;
        padding: 64px 32px;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        border: 1px dashed rgba(255, 255, 255, 0.2);
        margin: 32px 0;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    }
    .empty-state .empty-icon {
        font-size: 3.5rem;
        margin-bottom: 20px;
        opacity: 0.6;
        transition: all 0.3s ease;
        display: inline-block;
    }
    .empty-state:hover .empty-icon {
        transform: scale(1.15) rotate(12deg);
        opacity: 0.85;
        animation: search-wobble 0.5s ease;
    }
    @keyframes search-wobble {
        0%, 100% { transform: scale(1.15) rotate(12deg); }
        25% { transform: scale(1.2) rotate(-8deg); }
        50% { transform: scale(1.25) rotate(12deg); }
        75% { transform: scale(1.2) rotate(-8deg); }
    }
    .empty-state .empty-title {
        font-size: 1.375rem;
        font-weight: 600;
        color: #F5F5F7;
        margin-bottom: 12px;
        letter-spacing: -0.4px;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif;
    }
    .empty-state .empty-desc {
        font-size: 1rem;
        color: #8E8E93;
        margin-bottom: 32px;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif;
        line-height: 1.5;
    }
    body.light-mode .empty-state {
        background: #FFFBF5;
        border: 1px dashed rgba(0, 0, 0, 0.25);
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    }
    body.light-mode .empty-state .empty-title {
        color: #0D0D0D;
    }
    body.light-mode .empty-state .empty-desc {
        color: #3A3A3C;
    }
    .empty-suggestions {
        display: flex;
        flex-direction: column;
        gap: 12px;
        max-width: 500px;
        margin: 0 auto;
    }
    .suggestion-item {
        text-align: left;
        padding: 12px 20px;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        border: 0.5px solid rgba(255, 255, 255, 0.1);
        font-size: 0.9rem;
        color: #C7C7CC;
        transition: all 0.3s ease;
    }
    .suggestion-item:hover {
        background: rgba(255, 255, 255, 0.08);
        border-color: rgba(10, 132, 255, 0.3);
        transform: translateX(4px);
    }
    .compare-empty {
        text-align: center;
        padding: 80px 20px;
        background: rgba(255, 255, 255, 0.02);
        border-radius: 20px;
        border: 1px dashed rgba(255, 255, 255, 0.2);
    }
    .empty-icon {
        font-size: 4rem;
        margin-bottom: 20px;
        opacity: 0.5;
    }
    .empty-text {
        font-size: 1.2rem;
        font-weight: 600;
        color: #F5F5F7;
        margin-bottom: 12px;
    }
    .empty-subtext {
        font-size: 0.9rem;
        color: #8E8E93;
    }
    
    /* Tools Tab Styles */
    .tools-intro {
        text-align: center;
        padding: 40px 20px 30px 20px;
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.04) 0%, rgba(245, 245, 247, 0.02) 100%);
        border-radius: 20px;
        margin-bottom: 40px;
        border: 0.5px solid rgba(255, 255, 255, 0.12);
    }
    .tools-intro-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #F5F5F7;
        margin-bottom: 12px;
        letter-spacing: -0.5px;
    }
    .tools-intro-desc {
        font-size: 0.95rem;
        color: #8E8E93;
        font-weight: 400;
    }
    .tool-card {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.04) 0%, rgba(245, 245, 247, 0.02) 100%);
        border: 0.5px solid rgba(255, 255, 255, 0.12);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
    }
    .tool-card-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;
    }
    .tool-icon {
        font-size: 2rem;
    }
    .tool-card-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: #F5F5F7;
        letter-spacing: -0.4px;
    }
    .tool-card-desc {
        font-size: 0.9rem;
        color: #8E8E93;
        line-height: 1.5;
        margin-bottom: 8px;
    }
    .tool-hint {
        background: rgba(255, 255, 255, 0.03);
        border: 0.5px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 16px 20px;
        margin-top: 20px;
        font-size: 0.9rem;
        color: #8E8E93;
        text-align: center;
    }
    
    /* Chart Container - Apple Design System */
    [data-testid="stPlotlyChart"] {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-top: none !important;
        border-radius: 0 0 16px 16px !important;
        padding: 16px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
        margin-top: 0 !important;
        margin-bottom: 24px !important;
    }
    [data-testid="stPlotlyChart"]:hover {
        box-shadow: 0 12px 48px rgba(10, 132, 255, 0.12), 
                    0 4px 16px rgba(0, 0, 0, 0.12),
                    inset 0 1px 0 rgba(255, 255, 255, 0.22),
                    inset 0 0 30px rgba(10, 132, 255, 0.03) !important;
        border-color: rgba(10, 132, 255, 0.25) !important;
    }
    /* Chart Inner - Remove Plotly's background */
    [data-testid="stPlotlyChart"] .plotly {
        background: transparent !important;
    }
    [data-testid="stPlotlyChart"] > div {
        border-radius: 16px !important;
        overflow: hidden !important;
    }
    /* Title + Chart = single card */
    .section-title + [data-testid="stPlotlyChart"] {
        margin-top: 0 !important;
        border-top: none !important;
        border-top-left-radius: 0 !important;
        border-top-right-radius: 0 !important;
    }
    .section-title + [data-testid="stPlotlyChart"] > div {
        border-top-left-radius: 0 !important;
        border-top-right-radius: 0 !important;
    }
    .section-title + .skeleton-chart,
    .section-title + .skeleton-chart-sm {
        margin-top: 0 !important;
        border-top-left-radius: 0 !important;
        border-top-right-radius: 0 !important;
    }
    
    /* Custom Message Boxes - No Streamlit Boxes */
    .hint-text {
        color: #8E8E93;
        font-size: 0.95rem;
        text-align: center;
        padding: 16px;
        margin: 12px 0;
        line-height: 1.5;
    }
    .calc-result {
        font-size: 2rem;
        font-weight: 700;
        color: #0A84FF;
        text-align: center;
        margin: 20px 0;
        letter-spacing: -0.5px;
    }
    .result-safe {
        background: rgba(52, 199, 89, 0.12);
        border: 0.5px solid rgba(52, 199, 89, 0.3);
        border-radius: 12px;
        color: #34C759;
        padding: 12px 16px;
        margin: 12px 0;
        font-weight: 600;
        text-align: center;
    }
    .result-warning {
        background: rgba(255, 69, 58, 0.12);
        border: 0.5px solid rgba(255, 69, 58, 0.3);
        border-radius: 12px;
        color: #FF453A;
        padding: 12px 16px;
        margin: 12px 0;
        font-weight: 600;
        text-align: center;
    }
    .compare-result {
        font-size: 1.4rem;
        font-weight: 600;
        color: #F5F5F7;
        text-align: center;
        padding: 20px;
        line-height: 1.6;
    }
    .highlight-price {
        color: #0A84FF;
        font-weight: 700;
        font-size: 1.6rem;
    }
    /* 중복 metric 스타일 제거 - 위에서 이미 정의됨 */
    .metric-sub { 
        font-size: 0.78rem; 
        color: #8E8E93; 
        margin-top: 4px; 
        font-weight: 500;
    }
    .signal-help { 
        color: #8E8E93 !important; 
        font-size: 0.82rem; 
        line-height: 1.5; 
    }

    /* [반응형] 태블릿 (768px 이하) */
    @media (max-width: 768px) {
        .block-container { padding: 1rem 1rem 6rem !important; max-width: 100% !important; }
        .logo-demo-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
        .radar-title { font-size: 2.2rem !important; }
        .metric-grid { grid-template-columns: 1fr !important; }
        .skeleton-grid { grid-template-columns: 1fr !important; }
        .market-grid { grid-template-columns: 1fr !important; }
        .source-card { height: 54px !important; padding: 10px 14px !important; }
        .source-name { font-size: 0.95rem !important; }
        .capsule-title { font-size: 1rem !important; padding: 6px 14px !important; }
        .section-title { font-size: 1.4rem !important; }
        .skeleton-chart { height: 220px !important; }
        .skeleton-chart-sm { height: 180px !important; }
        [data-testid="stPlotlyChart"] { min-height: 200px !important; }
        /* Chart Columns - Stack on Tablet */
        [data-testid="stHorizontalBlock"] { flex-direction: column !important; }
        [data-testid="stColumn"] { width: 100% !important; }
        .back-to-top { bottom: 60px !important; right: 20px !important; width: 44px !important; height: 44px !important; }
    }
    /* [반응형] 모바일 (480px 이하) - Touch Optimized */
    @media (max-width: 480px) {
        .block-container { padding: 0.75rem 0.75rem 5rem !important; }
        .radar-title { font-size: 1.8rem !important; }
        .radar-icon-wrap { padding: 8px 10px !important; }
        .radar-icon { font-size: 1.5rem !important; }
        .metric-card { 
            padding: 12px 14px !important; 
            min-height: 70px !important;
            touch-action: manipulation !important;
        }
        .metric-value { font-size: 1.1rem !important; }
        .metric-label { font-size: 0.75rem !important; }
        .metric-change { font-size: 0.7rem !important; }
        .metric-change-label { font-size: 0.6rem !important; margin-left: 4px !important; }
        .ticker-wrap { height: 28px; }
        .ticker-item { font-size: 0.7rem !important; margin-right: 24px !important; }
        .search-pills { gap: 8px; margin-bottom: 16px; }
        .search-pills a { 
            padding: 10px 16px !important; 
            font-size: 0.85rem !important;
            min-height: 38px !important;
            touch-action: manipulation !important;
        }
        .section-title { font-size: 1.3rem !important; }
        .back-to-top { 
            bottom: 50px !important; 
            right: 16px !important; 
            width: 44px !important; 
            height: 44px !important;
            font-size: 1.3rem !important;
        }
        .source-card {
            height: 60px !important;
            padding: 12px 16px !important;
            touch-action: manipulation !important;
        }
        div[data-testid="stLinkButton"] > a {
            min-height: 52px !important;
            touch-action: manipulation !important;
        }
    }
    
    /* [로고 컨셉 예시] 크림이 좋아할 법한 6가지 방향 */
    .logo-demo-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px 16px; margin: 24px 0; }
    .logo-demo-cell { 
        background: rgba(26,26,26,0.8); border: 1px solid #333; border-radius: 16px; 
        padding: 24px 16px; text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center;
        min-height: 160px;
    }
    .logo-demo-cell .logo-wrap { position: relative; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 12px; gap: 8px; }
    .logo-demo-cell .demo-label { font-size: 0.75rem; color: #888; font-weight: 600; margin-bottom: 4px; }
    .logo-demo-cell .demo-desc { font-size: 0.65rem; color: #666; line-height: 1.3; }
    
    /* 1. 타이포만 - 이모지 빼고 텍스트만 */
    .logo-concept-1 .logo-text { font-size: 1.8rem; font-weight: 900; letter-spacing: -1px; font-style: italic; color: #fff; }
    
    /* 2. 아이콘 추상화 - 원+스윕 라인 */
    .logo-concept-2 .logo-abstract { width: 48px; height: 48px; position: relative; flex-shrink: 0; }
    .logo-concept-2 .logo-abstract::before { content: ''; position: absolute; inset: 0; border: 2px solid #fff; border-radius: 50%; opacity: 0.8; }
    .logo-concept-2 .logo-abstract::after { content: ''; position: absolute; left: 50%; top: 50%; width: 24px; height: 2px; margin-left: 0; margin-top: -1px; background: #fff; transform-origin: left center; transform: rotate(-45deg); opacity: 0.9; }
    .logo-concept-2 .logo-text { font-size: 1.2rem; font-weight: 800; letter-spacing: 2px; color: #fff; }
    
    /* 3. 컬러 톤 다운 - 블랙/화이트/그레이 */
    .logo-concept-3 .logo-wrap { flex-direction: column; background: #1a1a1a; padding: 12px 20px; border-radius: 8px; border: 1px solid #444; }
    .logo-concept-3 .logo-text { font-size: 1.5rem; font-weight: 800; letter-spacing: 1px; color: #e0e0e0; }
    .logo-concept-3 .logo-accent { width: 100%; height: 2px; background: linear-gradient(90deg, transparent, #c9a227, transparent); margin-top: 6px; border-radius: 1px; }
    
    /* 4. 애니메이션 최소화 - 정적, 호버만 */
    .logo-concept-4 .logo-wrap { transition: opacity 0.3s; }
    .logo-concept-4 .logo-wrap:hover { opacity: 0.85; }
    .logo-concept-4 .logo-text { font-size: 1.5rem; font-weight: 700; color: #ccc; letter-spacing: 1px; }
    
    /* 5. 크림 참고 - 미니멀 워드마크 */
    .logo-concept-5 .logo-wrap { flex-direction: column; gap: 4px; }
    .logo-concept-5 .logo-text { font-size: 1.6rem; font-weight: 700; color: #fff; letter-spacing: 3px; }
    .logo-concept-5 .logo-sub { font-size: 0.55rem; color: #666; letter-spacing: 4px; }
    
    /* 6. 하이브리드 - 미니멀 + 호버 스캔 */
    .logo-concept-6 .logo-wrap { position: relative; overflow: hidden; padding: 8px 16px; border-radius: 8px; }
    .logo-concept-6 .logo-scan { position: absolute; left: 50%; top: 0; bottom: 0; width: 2px; margin-left: -1px; background: linear-gradient(180deg, transparent, rgba(255,255,255,0.5), transparent); animation: concept-scan 3s ease-in-out infinite; z-index: 0; }
    .logo-concept-6 .logo-text { font-size: 1.4rem; font-weight: 800; color: #eee; letter-spacing: 1px; position: relative; z-index: 1; }
    @keyframes concept-scan { 0% { transform: translateY(-100%); } 100% { transform: translateY(100%); } }
    
</style>
""", unsafe_allow_html=True)

# [다크 모드] 검색창 스타일 (라이트일 땐 적용 안 함)
if not st.session_state.theme_light:
    st.markdown("""
    <style>
    /* 검색창 - Apple Design System + 왼쪽 돋보기 아이콘 */
    div[data-baseweb="input"],
    .stTextInput [data-baseweb="base-input"] { 
        background: rgba(255, 255, 255, 0.06) !important; 
        border: 1px solid rgba(255, 255, 255, 0.12) !important; 
        border-radius: 12px !important; 
        height: auto !important; 
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
        transition: all 0.2s ease !important;
        padding: 0 !important;
        position: relative !important;
    }
    div[data-baseweb="input"]::before,
    .stTextInput [data-baseweb="base-input"]::before {
        content: "🔍";
        position: absolute;
        left: 14px;
        top: 50%;
        transform: translateY(-50%);
        font-size: 0.95rem;
        opacity: 0.65;
        pointer-events: none;
        z-index: 1;
    }
    div[data-baseweb="input"] > div,
    div[data-baseweb="input"] > div > div {
        background: transparent !important;
        border: none !important;
    }
    div[data-baseweb="input"] > div > input,
    .stTextInput input {
        color: #F5F5F7 !important; 
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif !important;
        font-size: 1rem !important;
        font-weight: 400 !important;
        padding: 14px 16px 14px 42px !important;
        background: transparent !important;
        border: none !important;
        outline: none !important;
    }
    div[data-baseweb="input"]:focus-within,
    .stTextInput [data-baseweb="base-input"]:focus-within { 
        border-color: rgba(10, 132, 255, 0.5) !important; 
        background: rgba(255, 255, 255, 0.08) !important;
    }
    div[data-baseweb="input"]:hover,
    .stTextInput [data-baseweb="base-input"]:hover { 
        background: rgba(255, 255, 255, 0.07) !important;
    }
    input::placeholder { 
        color: #8E8E93 !important; 
        font-size: 1rem !important;
        font-weight: 400 !important;
    }
    
    /* Light Mode: Search Input - Cream & Black */
    body.light-mode div[data-baseweb="input"],
    body.light-mode .stTextInput [data-baseweb="base-input"] {
        background: #FFFBF5 !important;
        border: 1px solid rgba(0, 0, 0, 0.25) !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08) !important;
    }
    body.light-mode div[data-baseweb="input"]::before,
    body.light-mode .stTextInput [data-baseweb="base-input"]::before {
        opacity: 0.55;
    }
    body.light-mode div[data-baseweb="input"] > div > input,
    body.light-mode .stTextInput input {
        color: #0D0D0D !important;
        padding-left: 42px !important;
    }
    body.light-mode div[data-baseweb="input"]:focus-within,
    body.light-mode .stTextInput [data-baseweb="base-input"]:focus-within {
        border-color: rgba(0, 0, 0, 0.4) !important;
        background: #FFF5E8 !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
    }
    body.light-mode .radar-title { color: #0D0D0D !important; -webkit-text-fill-color: #0D0D0D !important; background: none !important; filter: none !important; }
    body.light-mode .radar-sub { color: #3A3A3C !important; }
    body.light-mode .tool-header { color: #0D0D0D !important; }
    body.light-mode .capsule-title { color: #0D0D0D !important; background: rgba(0,0,0,0.06) !important; border: 1px solid rgba(0,0,0,0.12) !important; }
    body.light-mode .category-header { color: #3A3A3C !important; border-bottom-color: rgba(0,0,0,0.2) !important; }
    body.light-mode .source-name { color: #0D0D0D !important; }
    body.light-mode .source-url, body.light-mode .source-desc { color: #3A3A3C !important; }
    body.light-mode .home-hero-title { color: #0D0D0D !important; }
    body.light-mode .home-hero-sub { color: #3A3A3C !important; }
    body.light-mode p, body.light-mode span, body.light-mode div { color: inherit; }
    </style>
    """, unsafe_allow_html=True)

# [차트 테마] Apple Style Dark - Premium iOS Design
CHART_PAPER = "rgba(0, 0, 0, 0)"
CHART_PLOT = "rgba(0, 0, 0, 0)"
CHART_FONT = "#F5F5F7"
CHART_TEMPLATE = "plotly_dark"
CHART_LEGEND_BG = "rgba(0, 0, 0, 0)"
CHART_LEGEND_BORDER = "rgba(255,255,255,0)"
CHART_GRID = "rgba(255, 255, 255, 0.04)"  # 더 은은한 그리드

# [시맨틱 컬러 시스템] Apple HIG
COLOR_SUCCESS = "#32D74B"  # 초록 (성공, 상승)
COLOR_WARNING = "#FF9F0A"  # 주황 (경고)
COLOR_ERROR = "#FF453A"    # 빨강 (에러)
COLOR_INFO = "#0A84FF"     # 파랑 (정보)
COLOR_MINT = "#63E6E2"     # 민트 (하락)
CHART_HOVER_BG = "rgba(28, 28, 30, 0.95)"  # iOS 스타일 반투명
CHART_HOVER_FONT = "#FFFFFF"
CHART_ZEROLINE = "rgba(255,255,255,0.08)"
CHART_MARKER_LINE = "rgba(255,255,255,0.95)"
# 메인 액센트 - 아이폰 블루 그라데이션
CHART_ACCENT = "#0A84FF"
CHART_ACCENT_LIGHT = "#64B5FF"
CHART_ACCENT_HIGHLIGHT = "rgba(10, 132, 255, 0.25)"
CHART_ACCENT_FILL = "rgba(10, 132, 255, 0.15)"
# 그레이 톤 - iOS 스타일
CHART_GRAY_LINE = "#8E8E93"
CHART_GRAY_FILL = "rgba(142,142,147,0.08)"
CHART_DOTTED = "#98989D"
CHART_BAR_SCALE = [[0, 'rgba(10,132,255,0.2)'], [0.5, 'rgba(10,132,255,0.5)'], [1, 'rgba(10,132,255,0.8)']]
CHART_HOVER_BORDER = "rgba(10,132,255,0.3)"

# [인라인 색상] 다크 모드
TEXT_PRIMARY = "#eee"
TEXT_SECONDARY = "#888"
ACCENT_CURATION = "#3B82F6"
SIGNAL_HELP_COLOR = "#8a9aab"
RATE_INFO_COLOR = "#888"
ONLINE_COLOR = "#7BA3D4"

# ------------------------------------------------------------------
# [5] 메인 헤더
# ------------------------------------------------------------------
# [속도 최적화] 환율만 초기 로드 - 시트는 검색 시 lazy load
now_time = st.session_state.ticker_data['time']
usd, jpy, usd_prev, jpy_prev, rate_date = get_exchange_rates()

# [Billboard Data Pools] - 2025 트렌드 확장 (카테고리당 50+ 항목)
MASTER_TREND = [
    "아이폰 16 Pro", "갤럭시 S25", "맥북 에어 M4", "RTX 5090", "Steam Deck 2", "PS5 Pro", "Ricoh GR IV", "후지필름 X100VI",
    "나이키 덩크 로우", "뉴발란스 550", "아디다스 삼바", "살로몬 ACS 프로", "Jordan 1 로우", "아식스 젤 1130", "New Balance 993", "Crocs 클로그",
    "스투시", "캐하트 WIP", "아크테릭스 베타", "Stone Island", "노스페이스 눕시", "뉴발란스 2002R", "코스", "미하라 야스히로",
    "라이카 Q3", "Leica M6", "Sony A7RV", "니콘 Z8", "Canon R6 Mark II", "DJI Mini 4 Pro", "GoPro Hero 13", "인스타360 Ace Pro",
    "Stanley 퀀처", "다이슨 에어스트레이트", "발뮤다 토스터", "허먼밀러 에어론", "Rimowa", "브롬톤", "Snow Peak", "Helinox",
    "롤렉스 서브마리너", "오메가 스피드마스터", "샤넬 클래식", "에르메스 버킨", "프라다 나일론", "Bottega Veneta", "Miu Miu", "디메즐",
    "Keychron Q1", "NuPhy Air75", "해피해킹", "로지텍 MX Master 3S", "애플워치 울트라 2", "AirPods Pro 2", "아이패드 프로 M4", "Mac Studio",
    "Garmin Fenix 7", "Bose QC 울트라", "소니 WH-1000XM6", "카시나", "우로보로스", "제네렉", "루이스폴센"
]

MASTER_VIBE = [
    "Stüssy", "스투시", "Carhartt WIP", "캐하트", "Arc'teryx", "아크테릭스", "Stone Island", "스톤아일랜드",
    "Palace", "팔라스", "KITH", "키스", "Human Made", "휴먼메이드", "Aimé Leon Dore", "에임레온도어",
    "Needles", "니들스", "Auralee", "오로리", "Engineered Garments", "엔지니어드 가먼츠",
    "Birkenstock", "비르켄슈톡", "Porter", "포터", "Freitag", "프라이탁",
    "Comoli", "꼼올리", "Beams", "비즈", "United Arrows", "유나이티드 애로우즈",
    "Visvim", "비스빔", "Kapital", "카피탈", "Nanamica", "나나미카",
    "Acne Studios", "아크네", "Toteme", "토템", "Lemaire", "르메르",
    "Muji", "무인양품", "Uniqlo U", "유니클로 U", "COS", "코스"
]

MASTER_SNEAKERS = [
    "Nike Dunk Low", "나이키 덩크 로우", "Jordan 1 Low", "조던 1 로우", "Jordan 4", "조던 4", "Jordan 11", "조던 11",
    "New Balance 550", "뉴발란스 550", "New Balance 993", "뉴발란스 993", "New Balance 2002R", "뉴발란스 2002R", "New Balance 990", "뉴발란스 990",
    "Adidas Samba", "아디다스 삼바", "Adidas Gazelle", "아디다스 가젤", "Salomon ACS Pro", "살로몬 ACS 프로", "Salomon XT-6", "살로몬 XT-6",
    "Asics Gel-1130", "아식스 젤 1130", "Asics Gel-Kayano 14", "아식스 젤카야노", "Hoka One One", "호카", "Hoka Clifton", "호카 클리프톤",
    "Crocs 클로그", "크록스", "Yeezy 350", "이지 350", "Yeezy Slide", "이지 슬라이드", "Converse Chuck 70", "컨버스 척 70",
    "Vans Old Skool", "반스 올드스쿨", "Onitsuka Tiger", "오니츠카 타이거", "Balenciaga Track", "발렌시아가 트랙",
    "Rick Owens", "릭 오웬스", "Maison Margiela Tabi", "마르지엘라 타비", "미하라 야스히로", "카시나", "디메즐"
]

MASTER_LUXURY = [
    "Rolex Submariner", "롤렉스 서브마리너", "Rolex Daytona", "롤렉스 데이토나", "Rolex GMT", "롤렉스 GMT", "Rolex Datejust", "롤렉스 데이저스트",
    "Omega Speedmaster", "오메가 스피드마스터", "Cartier Tank", "까르띠에 탱크", "Cartier Santos", "까르띠에 산토스",
    "Chanel Classic Flap", "샤넬 클래식", "Chanel Boy", "샤넬 보이", "Hermes Birkin", "에르메스 버킨", "Hermes Kelly", "에르메스 켈리",
    "Louis Vuitton", "루이비통", "Goyard", "고야드", "Dior Saddle", "디올 새들", "Celine Triomphe", "셀린느 트리옹프",
    "Bottega Veneta", "보테가 베네타", "Prada Nylon", "프라다 나일론", "Gucci Jackie", "구찌 재키", "Loewe Puzzle", "로에베 퍼즐",
    "Rimowa", "리모와", "Chrome Hearts", "크롬하츠", "Van Cleef", "반클리프", "Tiffany", "티파니", "Bulgari", "불가리"
]

MASTER_TECH = [
    "iPhone 16 Pro", "아이폰 16 프로", "iPhone 16", "아이폰 16", "Galaxy S25", "갤럭시 S25", "Galaxy Z Fold 6", "갤럭시 Z폴드",
    "MacBook Air M4", "맥북 에어 M4", "MacBook Pro M4", "맥북 프로 M4", "iPad Pro M4", "아이패드 프로 M4", "Mac Studio", "맥 스튜디오",
    "RTX 5090", "RTX 5080", "RTX 4090", "Steam Deck 2", "Steam Deck OLED", "PS5 Pro", "PlayStation 5", "플스5",
    "Nintendo Switch 2", "닌텐도 스위치 2", "Switch OLED", "스위치 OLED",
    "Keychron Q1", "키크론 Q1", "NuPhy Air75", "누피 에어75", "해피해킹", "HHKB", "로지텍 MX Master 3S", "로지텍 마스터",
    "Apple Watch Ultra 2", "애플워치 울트라", "AirPods Pro 2", "에어팟 프로", "Bose QC Ultra", "보스 QC", "Sony XM6", "소니 헤드폰",
    "DJI Mini 4 Pro", "DJI 미니 4", "GoPro Hero 13", "고프로 13", "Insta360 Ace Pro", "인스타360",
    "Garmin Fenix 7", "가민 페닉스", "Studio Display", "스튜디오 디스플레이", "LG StanbyME", "LG 스탠바이미"
]

MASTER_LIVING = [
    "Stanley Quencher", "스탠리 퀀처", "Stanley 텀블러", "스탠리 텀블러", "Yeti", "예티", "Hydro Flask", "하이드로플라스크",
    "Dyson Airstrait", "다이슨 에어스트레이트", "Dyson V15", "다이슨 V15", "Dyson Airwrap", "다이슨 에어랩",
    "Balmuda Toaster", "발뮤다 토스터", "Balmuda Kettle", "발뮤다 전기포트",
    "Herman Miller Aeron", "허먼밀러 에어론", "Herman Miller Embody", "허먼밀러 엠바디",
    "Rimowa", "리모와", "Brompton", "브롬톤", "Super73", "슈퍼73", "Strida", "스트라이더",
    "Snow Peak", "스노우피크", "Helinox", "헬리녹스", "Coleman", "콜맨",
    "Nespresso", "네스프레소", "Fellow Ode", "펠로우 오드", "Comandante C40", "코만단테",
    "Moccamaster", "모카마스터", "Balmuda Coffee", "발뮤다 커피머신",
    "Genelec", "제네렉", "Sonos", "소노스", "Bose", "보스",
    "Roborock S8", "로보락 S8", "LG Styler", "LG 스타일러", "Dyson V15", "다이슨 청소기"
]

MASTER_GAME = [
    "PS5 Pro", "PlayStation 5", "플스5", "Nintendo Switch 2", "닌텐도 스위치 2", "Switch OLED", "스위치 OLED",
    "Steam Deck 2", "Steam Deck OLED", "스팀덱", "Xbox Series X", "엑스박스",
    "RTX 5090", "RTX 5080", "RTX 4090", "게임 그래픽카드",
    "DualSense", "듀얼센스", "Xbox 컨트롤러", "Pro Controller", "프로콘",
    "게임 피규어", "피그마", "레고 스타워즈", "반다이 건담"
]

MASTER_OUTDOOR = [
    "Snow Peak", "스노우피크", "Helinox", "헬리녹스", "Coleman", "콜맨", "노르디스크",
    "캠핑 텐트", "캠핑체어", "캠핑테이블", "캠핑랜턴",
    "Brompton", "브롬톤", "Super73", "슈퍼73", "Strida", "스트라이더",
    "등산화", "등산배낭", "아크테릭스", "노스페이스", "살로몬",
    "Stanley 텀블러", "Yeti", "예티", "Hydro Flask", "하이드로플라스크"
]

# [자동완성] 시트 + 빌보드 키워드 통합 (시트 부족해도 풍부한 자동완성)
AUTOCOMPLETE_POOL = list(dict.fromkeys(
    MASTER_TREND + MASTER_SNEAKERS + MASTER_TECH + MASTER_LUXURY +
    MASTER_LIVING + MASTER_GAME + MASTER_OUTDOOR + MASTER_VIBE
))

# [추천검색어] 카테고리별 풀 - 마우스→모카마스터 같은 무관 추천 방지 (아이폰처럼 연관만)
SUGGESTION_POOL_TECH = set(MASTER_TECH + MASTER_GAME)
SUGGESTION_POOL_FASHION = set(MASTER_SNEAKERS + MASTER_LUXURY + MASTER_VIBE)
SUGGESTION_POOL_CAMERA = {k for k in AUTOCOMPLETE_POOL if classify_keyword_category(k) == "CAMERA"}
SUGGESTION_POOL_LIVING = set(MASTER_LIVING)
SUGGESTION_POOL_GAME = set(MASTER_GAME)

@st.cache_data(ttl=600)
def get_autocomplete_keywords(df):
    """자동완성용 키워드: 시트 우선 + 빌보드 풀 보완 (캐싱으로 검색 속도 개선)"""
    if df is None or df.empty:
        return sorted(AUTOCOMPLETE_POOL, key=lambda x: (1, len(x), x))
    sheet_kw = set(get_sheet_keywords(df))
    pool = sheet_kw | set(AUTOCOMPLETE_POOL)
    return sorted(pool, key=lambda x: (x not in sheet_kw, len(x), x))  # 시트 키워드 우선

# [State Persistence] 빌보드 - 8카테고리 랜덤 배치 (컬럼 순서 셔플)
_BILL_COLS = [
    ('TREND', '🔥 TRENDING', MASTER_TREND, 'c-trend'),
    ('KICKS', '👟 SNEAKERS', MASTER_SNEAKERS, 'c-kicks'),
    ('LUX', '💎 LUXURY', MASTER_LUXURY, 'c-lux'),
    ('TECH', '💻 TECH', MASTER_TECH, 'c-tech'),
    ('VIBE', '🌊 VIBE', MASTER_VIBE, 'c-vibe'),
    ('LIVING', '🏠 LIVING', MASTER_LIVING, 'c-living'),
    ('GAME', '🎮 GAME', MASTER_GAME, 'c-game'),
    ('OUTDOOR', '⛺ OUTDOOR', MASTER_OUTDOOR, 'c-outdoor')
]
if 'billboard_data' not in st.session_state:
    _shuffled = random.sample(_BILL_COLS, 8)
    st.session_state.billboard_data = {k: random.sample(pool, min(28, len(pool))) for k, _, pool, _ in _shuffled}
    st.session_state.billboard_order = _shuffled

def _bill_cols():
    return st.session_state.get('billboard_order', _BILL_COLS)

def make_bill_html(items):
    # [Seamless Loop] 10개 스크롤 + 처음 2개 반복 (12 items × 30px = 360px)
    # [빌보드 클릭 → 자동 검색] 클릭 시 ?q=키워드로 검색
    display_items = items[:10] + items[:2]
    return "".join([f'<a href="?q={urllib.parse.quote(item)}" target="_self" class="bill-item" title="클릭하여 검색">· {html.escape(item)}</a>' for item in display_items])

# [테마 전환] URL 링크 방식 - 클릭 시 ?theme=dark/light로 이동, 확실한 전환
def _theme_url(t):
    try:
        _qp = getattr(st, "query_params", None)
        qp = dict(_qp) if _qp else {}
        qp["theme"] = t
        return "?" + urllib.parse.urlencode(qp)
    except Exception:
        return f"?theme={t}"

# [헤더] 로고(빌보드 중앙 왼쪽) + 빌보드(화면 중앙) | 토글(개발중 비활성화)
_header_c1, _header_c2, _header_c3 = st.columns([1.5, 5, 1.5], vertical_alignment="center", gap="small")
with _header_c1:
    _header_box = st.container(key="header_logo_toggle")
    with _header_box:
        st.markdown("""
        <div class="header-logo-area">
            <a href="/" target="_self" class="header-logo-standalone">
                <span class="radar-top-row">
                    <span class="radar-icon-wrap"><span class="radar-icon">📡</span></span>
                    <span class="radar-title-wrap"><span class="radar-title">RADAR</span></span>
                </span>
                <span class="radar-sub">Price Intelligence</span>
            </a>
        </div>
        """, unsafe_allow_html=True)
with _header_c2:
    st.markdown(f"""
    <div class="radar-billboard-wrap">
        <div class="radar-billboard">{"".join([f'<div class="bill-col {cls}"><div class="bill-head">{head}</div><div class="bill-win"><div class="bill-content">{make_bill_html(st.session_state.billboard_data.get(k, []))}</div></div></div>' for k, head, _, cls in _bill_cols()])}</div>
    </div>
    """, unsafe_allow_html=True)

# ------------------------------------------------------------------
# [6] 메인 네비게이션 - 탭 중앙
# ------------------------------------------------------------------
_nav_col1, _nav_col2, _nav_col3 = st.columns([1, 5, 1])
with _nav_col2:
    tab_home, tab_source, tab_tools, tab_safety, tab_compare = st.tabs(["🏠 시세 분석", "📂 Market Sources", "🧰 도구", "👮‍♂️ 사기 조회", "⚖️ 비교"])

# [Back to Top + Keyboard Shortcuts + Performance]
components.html("""
<div class="back-to-top" id="backToTop" onclick="scrollToTop()">↑</div>
<div class="keyboard-hint" id="keyboardHint">
    <div style="font-size: 0.75rem; margin-bottom: 8px; color: #8E8E93;">⌨️ 단축키</div>
    <div style="font-size: 0.7rem; line-height: 1.6;">
        <div><kbd>/</kbd> 검색 포커스</div>
        <div><kbd>ESC</kbd> 검색 초기화</div>
        <div><kbd>?</kbd> 도움말</div>
    </div>
</div>
<div class="help-button" onclick="toggleHelp()">?</div>

<style>
.keyboard-hint {
    position: fixed;
    bottom: 140px;
    right: 32px;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.12), rgba(245, 245, 247, 0.08));
    backdrop-filter: blur(20px) saturate(180%);
    border: 0.5px solid rgba(255, 255, 255, 0.2);
    border-radius: 12px;
    padding: 12px 16px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    opacity: 0;
    pointer-events: none;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    transform: translateY(10px);
    z-index: 1001;
    color: #F5F5F7;
}
.keyboard-hint.show {
    opacity: 1;
    transform: translateY(0);
}
.keyboard-hint kbd {
    background: rgba(255, 255, 255, 0.15);
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 600;
    border: 0.5px solid rgba(255, 255, 255, 0.2);
    color: #F5F5F7;
    font-family: 'SF Mono', 'Monaco', monospace;
}
.help-button {
    position: fixed;
    bottom: 140px;
    right: 32px;
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, rgba(10, 132, 255, 0.15), rgba(10, 132, 255, 0.08));
    backdrop-filter: blur(20px);
    border: 0.5px solid rgba(10, 132, 255, 0.3);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    font-weight: 700;
    color: #0A84FF;
    cursor: pointer;
    z-index: 1000;
    transition: all 0.3s ease;
}
.help-button:hover {
    background: linear-gradient(135deg, rgba(10, 132, 255, 0.25), rgba(10, 132, 255, 0.15));
    transform: scale(1.1);
}
</style>

<script>
(function() {
    window.scrollToTop = function() {};
    window.toggleHelp = function() {};
    window.saveRecentSearch = function() {};
    function run() {
        try {
            var doc = null;
            try { doc = window.parent && window.parent.document; } catch(e) {}
            if (!doc) return;
            var head = doc.head || doc.getElementsByTagName('head')[0];
            if (head) {
                var baseUrl = (window.top && window.top.location && window.top.location.href) ? window.top.location.href.split('?')[0] : '';
                var ogImage = '__SEO_OG_IMAGE__';
                var meta = [
                    { n: 'description', c: '중고나라, 번개장터, 당근마켓 매물을 한 번에. 실패 없는 중고 거래를 위한 통합 검색 및 빈티지/카메라 시세 분석 서비스 RADAR.' },
                    { n: 'keywords', c: '중고매물 통합검색, 중고 통합검색, 중고 시세 조회, 빈티지 시세, 중고 카메라 시세, RADAR, 라다, 중고거래 통합검색, 중고 시세 통합, 번개장터 시세, 중고나라 시세, 당근마켓 시세, 중고 가격 비교, 중고 시세 분석, 직구 시세, 해외직구 시세, 빈티지 카메라 시세, 중고 물품 시세, 중고 가격 추이, 중고 통합 검색기, 시세 통합 사이트, 중고 시세 검색' },
                    { n: 'author', c: '김진석' },
                    { n: 'naver-site-verification', c: '8a4e84698543f5c3404697202b190be23532de00' }
                ];
                for (var i = 0; i < meta.length; i++) {
                    var el = doc.querySelector('meta[name="' + meta[i].n + '"]');
                    if (!el) { el = doc.createElement('meta'); el.setAttribute('name', meta[i].n); head.appendChild(el); }
                    el.setAttribute('content', meta[i].c);
                }
                var og = [
                    { p: 'og:type', c: 'website' },
                    { p: 'og:site_name', c: 'RADAR' },
                    { p: 'og:title', c: 'RADAR - 중고매물 통합검색 & 빈티지 시세 조회' },
                    { p: 'og:description', c: '여기저기 다닐 필요 없습니다. 중고 시세와 매물을 데이터로 통합해 드립니다.' },
                    { p: 'og:url', c: baseUrl }
                ];
                if (ogImage) og.push({ p: 'og:image', c: ogImage });
                for (var j = 0; j < og.length; j++) {
                    var o = doc.querySelector('meta[property="' + og[j].p + '"]');
                    if (!o) { o = doc.createElement('meta'); o.setAttribute('property', og[j].p); head.appendChild(o); }
                    o.setAttribute('content', og[j].c);
                }
            }
            doc.title = 'RADAR - 중고매물 통합검색 & 빈티지 시세 조회';
            function setTabTitle() { try { window.top.document.title = doc.title; } catch(e) {} try { doc.title = doc.title; } catch(e) {} }
            setTabTitle();
            setTimeout(setTabTitle, 400);
            setTimeout(setTabTitle, 1200);
            try { if (doc.body) doc.body.classList.remove('light-mode'); } catch(e) {}
            window.scrollToTop = function() { try { var m = window.parent && window.parent.document && window.parent.document.querySelector('.main'); if (m) m.scrollTo({ top: 0, behavior: 'smooth' }); } catch(e) {} };
            var main = doc.querySelector ? doc.querySelector('.main') : null;
            if (main) try { main.addEventListener('scroll', function() { var btn = document.getElementById('backToTop'); if (btn) btn.classList.toggle('visible', this.scrollTop > 500); }); } catch(e) {}
            var helpVisible = false;
            window.toggleHelp = function() { helpVisible = !helpVisible; var h = document.getElementById('keyboardHint'); if (h) h.classList.toggle('show', helpVisible); };
            if (doc.addEventListener) try {
                doc.addEventListener('keydown', function(e) {
                    if (e.key === '/') { e.preventDefault(); var i = doc.querySelector('input[placeholder*="여기에 검색"]'); if (i) i.focus(); }
                    if (e.key === 'Escape') { var i = doc.querySelector('input[placeholder*="여기에 검색"]'); if (i && i === doc.activeElement) { i.value = ''; i.blur(); } }
                    if (e.key === '?') { e.preventDefault(); window.toggleHelp(); }
                });
            } catch(e) {}
            window.saveRecentSearch = function(kw) { try { var r = JSON.parse(localStorage.getItem('radar_recent_searches') || '[]'); r = r.filter(function(k) { return k !== kw; }); r.unshift(kw); localStorage.setItem('radar_recent_searches', JSON.stringify(r.slice(0, 5))); } catch(e) {} };
            setTimeout(function() { try { var i = doc.querySelector('input[placeholder*="여기에 검색"]'); if (i && i.value) window.saveRecentSearch(i.value); } catch(e) {} }, 1500);
        } catch(e) {}
    }
    if (document.readyState === 'complete') setTimeout(run, 0);
    else window.addEventListener('load', function() { setTimeout(run, 0); });
})();
</script>
""".replace("__SEO_OG_IMAGE__", (SEO_OG_IMAGE or "").replace("\\", "\\\\").replace("'", "\\'")), height=0)

# [빌보드/최근검색 클릭] query params
try:
    qp = getattr(st, "query_params", None)
    if qp and qp.get("q"):
        st.session_state.search_input = qp.get("q")
        try: del st.query_params["q"]
        except Exception: pass
except Exception:
    pass

# [토스트] 검색 결과별 한 번만 표시
if "last_toast_keyword" not in st.session_state:
    st.session_state.last_toast_keyword = None

# ==========================================
# 🏠 TAB 1: 홈
# ==========================================
with tab_home:
    if 'search_input' not in st.session_state: st.session_state.search_input = ""
    
    # [홈 히어로] 카드형 + 중앙정렬 (검색 시에는 숨김)
    _has_search = bool(st.session_state.get("search_input", "").strip())
    _hero_hide = "home-hero-hidden" if _has_search else ""
    _hero_col1, _hero_col2, _hero_col3 = st.columns([1, 4, 1])
    with _hero_col2:
        st.markdown(f"""
        <div class="home-hero-wrap {_hero_hide}">
            <p class="home-hero-title">중고 시세를 한눈에, 직구 비용까지</p>
            <p class="home-hero-sub">모델명·브랜드명을 검색하면 국내 시세와 해외 직구 비용을 비교할 수 있어요</p>
        </div>
        """, unsafe_allow_html=True)
        keyword = st.text_input("시세 검색", placeholder="여기에 검색하세요 · 라이카 M6, 나이키 조던, 아이폰 16 Pro", key="search_input", label_visibility="collapsed")
        if not _has_search:
            components.html("""
            <script>
            (function(){
                setTimeout(function(){
                    try {
                        var doc = window.parent.document;
                        var inp = doc.querySelector('input[placeholder*="여기에 검색"]');
                        if (inp && !inp.value) inp.focus();
                    } catch(e){}
                }, 150);
            })();
            </script>
            """, height=0)
    
    # 메인화면: 검색창 하단 펄스 애니메이션 (components.html iframe으로 무조건 표시)
    if not (keyword and keyword.strip()):
        _n = 8
        _items = []
        for _ in range(_n):
            a, r = random.uniform(0, 360), random.uniform(12, 35)
            l = 50 + r * math.cos(math.radians(a))
            t = 50 + r * math.sin(math.radians(a))
            _items.append((f"left:{l:.1f}%;top:{t:.1f}%", 2.0 + (r - 12) / 23 * 5.0, 9.0))
        _blip = "".join([f'<div class="sb" style="{p};animation-delay:{d:.1f}s;animation-duration:{u:.1f}s;"></div>' for p, d, u in _items])
        _pulse_html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ background: transparent; min-height: 400px; font-family: -apple-system, sans-serif; }}
        .wrap {{ text-align: center; padding: 40px 20px 60px; }}
        .sonar {{ width: 280px; height: 280px; margin: 0 auto; position: relative; display: flex; justify-content: center; align-items: center;
            background: radial-gradient(circle, rgba(255,255,255,0.02) 0%, transparent 70%); border-radius: 50%;
            border: 0.5px solid rgba(255,255,255,0.08); box-shadow: inset 0 0 40px rgba(255,255,255,0.02); }}
        .ring {{ position: absolute; left: 50%; top: 50%; width: 50px; height: 50px; margin: -25px 0 0 -25px;
            border-radius: 50%; border: 1.5px solid rgba(255,255,255,0.25); transform-origin: center center;
            animation: ping 10s cubic-bezier(0.4,0,0.2,1) infinite; animation-fill-mode: both; z-index: 1; }}
        .ring:nth-child(1) {{ animation-delay: 0s; }} .ring:nth-child(2) {{ animation-delay: 2s; }}
        .ring:nth-child(3) {{ animation-delay: 4s; }} .ring:nth-child(4) {{ animation-delay: 6s; }}
        .ring:nth-child(5) {{ animation-delay: 8s; }}
        .dot {{ position: absolute; left: 50%; top: 50%; width: 18px; height: 18px; margin: -9px 0 0 -9px;
            border-radius: 50%; background: linear-gradient(135deg, rgba(255,255,255,0.9), rgba(245,245,247,0.7));
            box-shadow: 0 0 24px rgba(255,255,255,0.5), 0 0 48px rgba(255,255,255,0.25), inset 0 1px 0 rgba(255,255,255,1);
            animation: dotpulse 2.5s ease-in-out infinite; z-index: 10; border: 0.5px solid rgba(255,255,255,0.4); }}
        .sb {{ position: absolute; width: 7px; height: 7px; margin: -3.5px 0 0 -3.5px; border-radius: 50%;
            background: linear-gradient(135deg, rgba(255,255,255,0.95), rgba(245,245,247,0.85));
            box-shadow: 0 0 16px rgba(255,255,255,0.7), 0 0 32px rgba(255,255,255,0.4), inset 0 1px 0 rgba(255,255,255,0.9);
            opacity: 0; animation: blip 10s cubic-bezier(0.4,0,0.2,1) infinite; animation-fill-mode: both;
            pointer-events: none; z-index: 2; border: 0.5px solid rgba(255,255,255,0.6); }}
        @keyframes ping {{ 0% {{ transform: scale(0.2); opacity: 0.7; border-color: rgba(255,255,255,0.35); border-width: 1.5px; }}
            30% {{ opacity: 0.5; border-color: rgba(255,255,255,0.2); }}
            70% {{ opacity: 0.15; border-color: rgba(255,255,255,0.08); border-width: 1px; }}
            100% {{ transform: scale(5); opacity: 0; border-color: rgba(255,255,255,0.02); border-width: 0.5px; }} }}
        @keyframes dotpulse {{ 0%,100% {{ transform: scale(0.85); opacity: 0.75;
            box-shadow: 0 0 24px rgba(255,255,255,0.5), 0 0 48px rgba(255,255,255,0.25), inset 0 1px 0 rgba(255,255,255,1); }}
            50% {{ transform: scale(1.15); opacity: 1;
            box-shadow: 0 0 36px rgba(255,255,255,0.7), 0 0 72px rgba(255,255,255,0.35), inset 0 1px 0 rgba(255,255,255,1); }} }}
        @keyframes blip {{ 0%,8% {{ opacity: 0; transform: scale(0.4); }} 10% {{ opacity: 1; transform: scale(1); }}
            12% {{ opacity: 0.95; transform: scale(1.15); }} 18% {{ opacity: 0.5; transform: scale(1); }}
            24% {{ opacity: 0; transform: scale(0.8); }} 100% {{ opacity: 0; transform: scale(0.8); }} }}
        .hint {{ margin-top: 60px; font-size: 1.05rem; font-weight: 500; color: rgba(255,255,255,0.5); letter-spacing: 0.5px; }}
        .hint::before {{ content: "📡 "; font-size: 1.15rem; opacity: 0.7; margin-right: 8px; }}
        </style></head><body><div class="wrap"><div class="sonar">
        <div class="ring"></div><div class="ring"></div><div class="ring"></div><div class="ring"></div><div class="ring"></div>
        <div class="dot"></div>{_blip}</div><p class="hint">레이더가 매물을 찾고 있어요</p></div></body></html>'''
        components.html(_pulse_html, height=420, scrolling=False)
    
    df_prices = load_price_data() if (keyword and keyword.strip()) else pd.DataFrame()
    
    # [스켈레톤 로딩] 검색 시 데이터 로드 전 차트/카드 영역에 스켈레톤 표시
    skel_ph = st.empty()
    if keyword and keyword.strip():
        with skel_ph.container():
            st.markdown("""
            <div class="skeleton-wrap">
                <div class="section-title section-title--price-summary section-title--pretty"><span class="title-icon">📊</span>시세 요약</div>
                <div class="skeleton-grid">
                    <div class="skeleton-card"></div>
                    <div class="skeleton-card"></div>
                    <div class="skeleton-card"></div>
                    <div class="skeleton-card"></div>
                </div>
                <div class="section-title section-title--chart section-title--pretty"><span class="title-icon">📶</span>시세 추이</div>
                <div class="skeleton-chart"></div>
                <div class="section-title section-title--chart section-title--pretty"><span class="title-icon">🔷</span>가격 분포</div>
                <div class="skeleton-chart-sm"></div>
            </div>
            """, unsafe_allow_html=True)
    
    matched = get_trend_data_from_sheet(keyword, df_prices) if keyword else None
    if keyword and keyword.strip():
        skel_ph.empty()
    
    # [토스트 알림] 검색 완료 / 데이터 없음 / 에러
    if keyword and keyword.strip():
        if st.session_state.last_toast_keyword != keyword:
            st.session_state.last_toast_keyword = keyword
            if df_prices.empty:
                st.toast("❌ 시세 데이터를 불러오는데 실패했습니다", icon="❌", duration=5)
            elif matched:
                st.toast(f"✅ '{keyword}' 시세 조회 완료", icon="✅")
            else:
                st.toast("⚠️ 시세 데이터를 찾을 수 없습니다", icon="⚠️")
    else:
        st.session_state.last_toast_keyword = None
    
    # [유사 검색어] 검색창 바로 아래 - 아이폰처럼 연관만 (마우스→모카마스터 같은 무관 추천 방지)
    ac_keywords = get_autocomplete_keywords(df_prices)
    pills = []
    if keyword and len(keyword.strip()) >= 1:
        q = keyword.lower().replace(" ", "").strip()
        sheet_kw = set(get_sheet_keywords(df_prices))
        user_cat = classify_keyword_category(keyword, df_prices)
        if user_cat == "TECH":
            suggestion_pool = sheet_kw | (SUGGESTION_POOL_TECH & set(ac_keywords))
        elif user_cat == "FASHION":
            suggestion_pool = sheet_kw | (SUGGESTION_POOL_FASHION & set(ac_keywords))
        elif user_cat == "CAMERA":
            suggestion_pool = sheet_kw | (SUGGESTION_POOL_CAMERA & set(ac_keywords))
        elif user_cat == "LIVING":
            suggestion_pool = sheet_kw | (SUGGESTION_POOL_LIVING & set(ac_keywords))
        elif user_cat == "GAME":
            suggestion_pool = sheet_kw | (SUGGESTION_POOL_GAME & set(ac_keywords))
        else:
            suggestion_pool = set(ac_keywords)
        pool_list = sorted(suggestion_pool, key=lambda x: (x not in sheet_kw, len(x), x))
        pool_norm = [k.lower().replace(" ", "") for k in pool_list]
        q_variants = {q} | set(difflib.get_close_matches(q, pool_norm, n=5, cutoff=0.6))
        suggestions = [k for k in pool_list if any(v in k.lower().replace(" ","") or k.lower().replace(" ","") in v for v in q_variants)][:3]
        pills = [(s, f"?q={urllib.parse.quote(s)}") for s in suggestions]
    
    if keyword and keyword.strip() and pills:
        pill_html = " ".join([f'<a href="{url}" target="_self">{html.escape(t)}</a>' for t, url in pills])
        st.markdown(f'<div class="search-pills">{pill_html}</div>', unsafe_allow_html=True)
    
    if keyword:
        col_left, col_right = st.columns([0.6, 0.4], gap="medium")
        with col_left:
            with st.spinner("번역·분석 중..."):
                eng_keyword, jp_keyword = get_translated_keywords_parallel(keyword)
            encoded_kor = urllib.parse.quote(keyword)
            encoded_eng = urllib.parse.quote(eng_keyword)
            encoded_jp = urllib.parse.quote(jp_keyword)
            
            st.markdown(f"<div style='margin-top:20px; font-size:1.3rem; font-weight:700; color:{TEXT_PRIMARY};'>'{html.escape(keyword)}' 분석 결과</div>", unsafe_allow_html=True)

            # [기존 카드 UI] - 새 탭
            st.markdown("<div class='capsule-title'>🇰🇷 국내 마켓</div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class="market-grid" style="display:grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                <a href="https://m.bunjang.co.kr/search/products?q={encoded_kor}" target="_blank" class="source-card card-bunjang" style="text-decoration:none;"><div class="source-info"><span class="source-name">⚡ 번개장터</span></div><span>🔗</span></a>
                <a href="https://www.daangn.com/search/{encoded_kor}" target="_blank" class="source-card card-daangn" style="text-decoration:none;"><div class="source-info"><span class="source-name">🥕 당근마켓</span></div><span>🔗</span></a>
                <a href="https://web.joongna.com/search?keyword={encoded_kor}" target="_blank" class="source-card card-joongna" style="text-decoration:none;"><div class="source-info"><span class="source-name">🟢 중고나라</span></div><span>🔗</span></a>
                <a href="https://fruitsfamily.com/search/{encoded_kor}" target="_blank" class="source-card card-fruits" style="text-decoration:none;"><div class="source-info"><span class="source-name">🟣 Fruits</span></div><span>🔗</span></a>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("<div class='capsule-title'>🌎 해외 직구</div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class="market-grid" style="display:grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                <a href="https://www.ebay.com/sch/i.html?_nkw={encoded_eng}" target="_blank" class="source-card card-ebay" style="text-decoration:none;"><div class="source-info"><span class="source-name">🔵 eBay ({html.escape(eng_keyword)})</span></div><span>🔗</span></a>
                <a href="https://jp.mercari.com/search?keyword={encoded_jp}" target="_blank" class="source-card card-mercari" style="text-decoration:none;"><div class="source-info"><span class="source-name">⚪ Mercari ({html.escape(jp_keyword)})</span></div><span>🔗</span></a>
            </div>
            """, unsafe_allow_html=True)
            
            # [커뮤니티 추천] 시세 매칭된 키워드만 사용 - 없으면 검색어 그대로 (잘못된 대체 방지)
            community_keyword = keyword
            try:
                if matched and isinstance(matched, dict) and matched.get("matched_keyword"):
                    community_keyword = matched["matched_keyword"]
                # matched 없을 때 get_close_matches로 대체하지 않음 → 다른 상품 연동 방지
                curation_title, curation_list = get_related_communities(community_keyword)
            except Exception:
                curation_title, curation_list = None, None
            if curation_title and curation_list:
                st.markdown(f"<div style='margin-top:30px; margin-bottom:10px; color:{ACCENT_CURATION}; font-weight:700;'>💡 {html.escape(str(curation_title))}</div>", unsafe_allow_html=True)
                cards_html = "".join([
                    f'<a href="{url}" target="_blank" class="source-card card-{tag}" style="text-decoration:none;"><div class="source-info"><span class="source-name">{html.escape(name)}</span><span class="source-desc">{html.escape(desc)}</span></div><span style="font-size:1.2rem;">🔗</span></a>'
                    for (name, url, tag, desc) in curation_list
                ])
                st.markdown(f"""
                <div class="market-grid" style="display:grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                    {cards_html}
                </div>
                """, unsafe_allow_html=True)

        with col_right:
            if matched:
                global_krw = calculate_total_import_cost(matched['global_usd'], usd)
                prices = matched['trend_prices']
                raw = matched['raw_prices']
                dates = matched["dates"]
                # 시세 요약: 이번주 중앙값 (summary_avg/min/max)
                kr_avg = matched.get('summary_avg', sum(prices)/len(prices) if prices else 0)
                kr_min = matched.get('summary_min', min(raw) if raw else 0)
                kr_max = matched.get('summary_max', max(raw) if raw else 0)
                n_data = len(raw)
                kr_avg = kr_avg if kr_avg is not None else 0
                kr_min = kr_min if kr_min is not None else 0
                kr_max = kr_max if kr_max is not None else 0
                df_full = pd.DataFrame({"날짜": dates, "가격(만원)": prices})
                df_1m = df_full.tail(4) if len(df_full) >= 4 else df_full
                
                # 가격 변동률 계산 (지난 데이터 대비)
                price_change_pct = 0
                price_change_symbol = ""
                price_change_color = "#8E8E93"
                price_change_label = ""
                if len(prices) >= 2:
                    current_price = prices[-1]
                    prev_price = prices[-2]
                    if prev_price > 0:
                        price_change_pct = ((current_price - prev_price) / prev_price) * 100
                        if price_change_pct > 0:
                            price_change_symbol = "↗"
                            price_change_color = "#FF453A"
                        elif price_change_pct < 0:
                            price_change_symbol = "↘"
                            price_change_color = "#0A84FF"
                        else:
                            price_change_symbol = "→"
                        # 시점 라벨 계산
                        if len(dates) >= 2:
                            price_change_label = f"({dates[-2]} 대비)"
                
                # [1] 시세 요약 2x2 + 시그널 (다크 모드 색상)
                def _signal_strength(n):
                    if n >= 15: return ("●●●●", "강함", "#5C9EFF")
                    if n >= 8: return ("●●●", "보통", "#7BB3FF")
                    if n >= 4: return ("●●", "약함", "#9BC4FF")
                    return ("●", "희미", "#B8D5FF")
                sig_bar, sig_text, sig_color = _signal_strength(n_data)
                _data_label = matched.get("matched_keyword") or keyword
                st.markdown(f"""
                <div class='section-title section-title--price-summary section-title--pretty'>
                    <span class='title-icon'>📊</span>시세 요약
                    <div class='price-data-label'>📋 <strong>{html.escape(str(_data_label))}</strong></div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown(f"""
                <div class="metric-grid">
                    <div class="metric-card">
                        <div class="metric-label">평균가</div>
                        <div class="metric-value">{kr_avg:,.1f}만</div>
                        <div class="metric-change" style="color:{price_change_color};">
                            {price_change_symbol} {abs(price_change_pct):.1f}%<span class="metric-change-label">{price_change_label}</span>
                        </div>
                    </div>
                    <div class="metric-card"><div class="metric-label">시그널</div><div class="metric-value" style="font-size:0.9rem;"><span style="color:{sig_color};">{sig_bar}</span> {sig_text}</div></div>
                    <div class="metric-card"><div class="metric-label">최고가</div><div class="metric-value">{kr_max:,.1f}만</div></div>
                    <div class="metric-card"><div class="metric-label">최저가</div><div class="metric-value">{kr_min:,.1f}만</div></div>
                    <p class="signal-help" style="grid-column: 1 / -1; margin:14px 0 0 0;font-size:0.78rem;color:{SIGNAL_HELP_COLOR};line-height:1.5;">
                        💡 시그널은 수집된 거래 데이터 건수에 비례합니다. ●●●●(강함)일수록 가격분포 데이터가 풍부해 <strong>검색 결과 신뢰도</strong>가 높습니다.
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                # [2] 전체 시세 (세로 배치) - iOS Style Premium
                st.markdown("<div class='section-title section-title--chart section-title--pretty'><span class='title-icon'>📶</span>시세 추이</div>", unsafe_allow_html=True)
                fig = go.Figure()
                # 전체 시세 레이어 - 부드러운 그레이 톤
                fig.add_trace(go.Scatter(x=dates, y=prices, mode='lines+markers', name='전체 시세',
                    line=dict(color=CHART_GRAY_LINE, width=2.5, shape='spline', smoothing=1.3),
                    marker=dict(size=7, color=CHART_GRAY_LINE, line=dict(width=1.5, color='rgba(255,255,255,0.3)'), symbol='circle'),
                    fill='tozeroy', fillcolor=CHART_GRAY_FILL,
                    hovertemplate='<b>%{x}</b><br>%{y:,.1f}만원<extra></extra>'))
                # 최근 1달 하이라이트 - 애플 블루 그라데이션
                if len(df_1m) >= 2:
                    d1m = df_1m['날짜'].tolist()
                    p1m = df_1m['가격(만원)'].tolist()
                    fig.add_trace(go.Scatter(x=d1m, y=p1m, mode='lines+markers', name='최근 1달',
                        line=dict(color=CHART_ACCENT, width=3.5, shape='spline', smoothing=1.2),
                        marker=dict(size=10, color=CHART_ACCENT_LIGHT, line=dict(width=2, color=CHART_MARKER_LINE), 
                                    opacity=0.95),
                        fill='tozeroy', fillcolor=CHART_ACCENT_HIGHLIGHT,
                        hovertemplate='<b>%{x}</b> (최근 1달)<br>%{y:,.1f}만원<extra></extra>'))
                # 해외직구 참고선 - 점선
                if global_krw > 0:
                    fig.add_trace(go.Scatter(x=dates, y=[global_krw]*len(dates), mode='lines', name='해외직구',
                        line=dict(color=CHART_DOTTED, width=1.5, dash='dot'),
                        hovertemplate=f'해외직구 추산: {global_krw:,.1f}만원<extra></extra>'))
                y_min = max(0, min(prices)*0.92) if prices else 0
                y_max = max(prices)*1.1 if prices else 100
                if y_max - y_min < 10: y_max = y_min + 20
                fig.update_layout(height=340, margin=dict(l=15, r=15, t=15, b=35),
                    title=dict(text=''), annotations=[],
                    hovermode='x unified',
                    hoverlabel=dict(bgcolor=CHART_HOVER_BG, font_size=14, font_color=CHART_HOVER_FONT,
                        bordercolor=CHART_HOVER_BORDER, align='left', namelength=-1),
                    xaxis=dict(showgrid=False, title='', tickfont=dict(size=11, color=CHART_FONT, family='-apple-system'), 
                               fixedrange=True, showline=False),
                    yaxis=dict(title='만원', title_font=dict(size=12, color=CHART_FONT), 
                               tickfont=dict(size=11, color=CHART_FONT),
                        showgrid=True, gridcolor=CHART_GRID, gridwidth=0.5, 
                        zeroline=True, zerolinecolor=CHART_ZEROLINE, zerolinewidth=0.5,
                        range=[y_min, y_max], fixedrange=True, showline=False),
                    paper_bgcolor=CHART_PAPER, plot_bgcolor=CHART_PLOT, font_color=CHART_FONT,
                    showlegend=False,
                    template=CHART_TEMPLATE, dragmode=False,
                    transition={'duration': 400, 'easing': 'cubic-in-out'})
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False}, key="radar_trend_chart")
                
                # [3] 가격 분포 (세로 배치) - iOS Style Premium
                st.markdown("<div class='section-title section-title--chart section-title--pretty'><span class='title-icon'>🔷</span>가격 분포</div>", unsafe_allow_html=True)
                if len(raw) >= 1:
                    n_bins = min(15, max(3, len(raw)//2)) if len(raw) > 1 else 5
                    hist, edges = np.histogram(raw, bins=n_bins)
                    mid = [(edges[i]+edges[i+1])/2 for i in range(len(hist))]
                    fig2 = go.Figure(go.Scatter(x=mid, y=hist, mode='lines+markers', name='가격 분포',
                        line=dict(color=CHART_ACCENT, width=3.5, shape='spline', smoothing=1.3),
                        marker=dict(size=10, color=CHART_ACCENT_LIGHT, line=dict(width=2, color=CHART_MARKER_LINE),
                                    opacity=0.95),
                        fill='tozeroy', fillcolor=CHART_ACCENT_HIGHLIGHT,
                        hovertemplate='<b>%{x:,.0f}만원대</b><br>%{y}건<extra></extra>'))
                    fig2.update_layout(height=340, margin=dict(l=15, r=15, t=15, b=35),
                        title=dict(text=''), annotations=[],
                        hovermode='x unified',
                        hoverlabel=dict(bgcolor=CHART_HOVER_BG, font_size=14, font_color=CHART_HOVER_FONT,
                            bordercolor=CHART_HOVER_BORDER, align='left', namelength=-1),
                        xaxis=dict(title='가격(만원)', title_font=dict(size=12, color=CHART_FONT), 
                                   showgrid=False, tickfont=dict(size=11, color=CHART_FONT, family='-apple-system'),
                                   showline=False),
                        yaxis=dict(title='건수', title_font=dict(size=12, color=CHART_FONT), 
                                   showgrid=True, gridcolor=CHART_GRID, gridwidth=0.5,
                                   tickfont=dict(size=11, color=CHART_FONT),
                                   showline=False),
                        paper_bgcolor=CHART_PAPER, plot_bgcolor=CHART_PLOT, font_color=CHART_FONT, 
                        showlegend=False, template=CHART_TEMPLATE,
                        transition={'duration': 400, 'easing': 'cubic-in-out'})
                    st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False}, key="radar_dist_chart")
            
            else:
                if keyword:
                    # 검색했는데 시세 데이터 없음 → 명확한 메시지
                    st.markdown(f"""
                    <div class="empty-state">
                        <div class="empty-icon">🔍</div>
                        <div class="empty-title">'{html.escape(keyword)}' 시세 데이터가 없습니다</div>
                        <div class="empty-desc">
                            현재 데이터베이스에 등록되지 않은 상품입니다<br>
                            다른 상품명으로 검색해보세요
                        </div>
                        <div class="empty-suggestions">
                            <div class="suggestion-item">✓ 정확한 상품명으로 검색 (예: 아이폰 16 Pro)</div>
                            <div class="suggestion-item">✓ 다른 키워드로 검색 (예: 브랜드명, 모델명)</div>
                            <div class="suggestion-item">✓ 유사 검색어를 참고해보세요</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                # 빈 그래프 대신 추천 검색어 표시
                if pills:
                    st.markdown("""
                    <div class="empty-suggestions" style="margin-top: 40px;">
                        <div style="text-align: center; font-size: 1.1rem; color: #8E8E93; margin-bottom: 20px;">
                            💡 이런 검색어는 어떠세요?
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        pass  # 메인화면(검색 없음): 펄스는 검색창 하단에서 이미 표시

# ==========================================
# 📂 TAB 2: 마켓 소스 (Pro Dashboard Style)
# ==========================================
with tab_source:
    col_left, col_right = st.columns(2, gap="large")
    
    with col_left:
        st.markdown("""
        <div class='category-header'>💻 IT / Tech</div>
        <a href="https://quasarzone.com" target="_blank" class="source-card card-quasar"><div class="source-info"><span class="source-name">퀘이사존</span><span class="source-desc">PC/하드웨어 뉴스</span></div></a>
        <a href="https://coolenjoy.net" target="_blank" class="source-card card-cool"><div class="source-info"><span class="source-name">쿨엔조이</span><span class="source-desc">PC 하드웨어 매니아</span></div></a>
        <a href="https://meeco.kr" target="_blank" class="source-card card-meeco"><div class="source-info"><span class="source-name">미코 (Meeco)</span><span class="source-desc">모바일/테크 정보</span></div></a>
        <a href="https://www.clien.net" target="_blank" class="source-card card-clien"><div class="source-info"><span class="source-name">클리앙</span><span class="source-desc">IT/알뜰구매</span></div></a>
        
        <div class='category-header'>📷 Camera & Gear</div>
        <a href="https://www.slrclub.com" target="_blank" class="source-card card-slr"><div class="source-info"><span class="source-name">SLR클럽</span><span class="source-desc">국내 최대 카메라 장터</span></div></a>
        <a href="http://www.leicaclub.net/" target="_blank" class="source-card card-leica"><div class="source-info"><span class="source-name">라이카 클럽</span><span class="source-desc">Leica 전문</span></div></a>
        <a href="https://cafe.naver.com/35mmcamera" target="_blank" class="source-card card-film"><div class="source-info"><span class="source-name">필름카메라 동호회</span><span class="source-desc">필름카메라 커뮤니티</span></div></a>
        <a href="https://cafe.naver.com/doflook" target="_blank" class="source-card card-dof"><div class="source-info"><span class="source-name">DOF LOOK</span><span class="source-desc">전문 촬영 장비</span></div></a>
        
        <div class='category-header'>🎮 게임 / 콘솔</div>
        <a href="https://bbs.ruliweb.com/market" target="_blank" class="source-card card-ruli"><div class="source-info"><span class="source-name">루리웹 장터</span><span class="source-desc">게임/피규어/취미</span></div></a>
        
        <div class='category-header'>💰 알뜰 / 세일</div>
        <a href="https://www.ppomppu.co.kr" target="_blank" class="source-card card-pompu"><div class="source-info"><span class="source-name">뽐뿌</span><span class="source-desc">알뜰구매/핫딜</span></div></a>
        """, unsafe_allow_html=True)

    with col_right:
        st.markdown("""
        <div class='category-header'>👟 Fashion & Style</div>
        <a href="https://kream.co.kr" target="_blank" class="source-card card-kream"><div class="source-info"><span class="source-name">KREAM</span><span class="source-desc">한정판 거래 플랫폼</span></div></a>
        <a href="https://cafe.naver.com/sssw" target="_blank" class="source-card card-nike"><div class="source-info"><span class="source-name">나이키매니아</span><span class="source-desc">스니커즈/스트릿</span></div></a>
        <a href="https://eomisae.co.kr" target="_blank" class="source-card card-eomisae"><div class="source-info"><span class="source-name">어미새</span><span class="source-desc">글로벌 세일 정보</span></div></a>
        <a href="https://cafe.naver.com/dieselmania" target="_blank" class="source-card card-diesel"><div class="source-info"><span class="source-name">디젤매니아</span><span class="source-desc">남성 패션 커뮤니티</span></div></a>
        <a href="https://www.musinsa.com" target="_blank" class="source-card card-musinsa"><div class="source-info"><span class="source-name">무신사</span><span class="source-desc">스트릿/스니커즈</span></div></a>
        
        <div class='category-header'>🍎 Apple & Life</div>
        <a href="https://cafe.naver.com/appleiphone" target="_blank" class="source-card card-asamo"><div class="source-info"><span class="source-name">아사모</span><span class="source-desc">아이폰/아이패드 사용자</span></div></a>
        <a href="https://cafe.naver.com/inmacbook" target="_blank" class="source-card card-mac"><div class="source-info"><span class="source-name">맥쓰사</span><span class="source-desc">맥북/맥 사용자 모임</span></div></a>
        
        <div class='category-header'>🏠 종합 마켓</div>
        <a href="https://m.bunjang.co.kr" target="_blank" class="source-card card-bunjang" style="text-decoration:none;"><div class="source-info"><span class="source-name">번개장터</span><span class="source-desc">중고 거래 플랫폼</span></div><span>🔗</span></a>
        <a href="https://www.daangn.com" target="_blank" class="source-card card-daangn" style="text-decoration:none;"><div class="source-info"><span class="source-name">당근마켓</span><span class="source-desc">지역 중고 거래</span></div><span>🔗</span></a>
        <a href="https://web.joongna.com" target="_blank" class="source-card card-joongna" style="text-decoration:none;"><div class="source-info"><span class="source-name">중고나라</span><span class="source-desc">국내 최대 종합 장터</span></div><span>🔗</span></a>
        <a href="https://fruitsfamily.com" target="_blank" class="source-card card-fruits" style="text-decoration:none;"><div class="source-info"><span class="source-name">Fruits</span><span class="source-desc">중고 거래 플랫폼</span></div><span>🔗</span></a>
        <a href="https://www.gmarket.co.kr" target="_blank" class="source-card card-gmarket"><div class="source-info"><span class="source-name">G마켓</span><span class="source-desc">종합 이커머스</span></div></a>
        <a href="https://www.auction.co.kr" target="_blank" class="source-card card-auction"><div class="source-info"><span class="source-name">옥션</span><span class="source-desc">종합 이커머스</span></div></a>
        
        <div class='category-header'>🚗 자동차</div>
        <a href="https://www.bobaedream.co.kr" target="_blank" class="source-card card-bobaedream"><div class="source-info"><span class="source-name">보배드림</span><span class="source-desc">중고차/자동차 커뮤니티</span></div></a>
        
        <div class='category-header'>🏡 인테리어</div>
        <a href="https://ohou.se" target="_blank" class="source-card card-ohou"><div class="source-info"><span class="source-name">오늘의집</span><span class="source-desc">인테리어/가구</span></div></a>
        """, unsafe_allow_html=True)

# ==========================================
# 🧰 TAB 3: 도구
# ==========================================
with tab_tools:
    st.markdown('''
    <div class="tools-intro">
        <div class="tools-intro-title">🧰 유틸리티 도구</div>
        <div class="tools-intro-desc">배송 추적부터 관세 계산까지, 필요한 도구를 한 곳에서</div>
    </div>
    ''', unsafe_allow_html=True)
    
    t1, t2 = st.columns(2, gap="large")
    
    with t1:
        st.markdown('''
        <div class="tool-card">
            <div class="tool-card-header">
                <span class="tool-icon">📦</span>
                <div class="tool-card-title">배송 조회</div>
            </div>
            <div class="tool-card-desc">택배 운송장 번호로 실시간 배송 상태를 확인하세요</div>
        </div>
        ''', unsafe_allow_html=True)
        
        carrier = st.selectbox("택배사 선택", ["CJ대한통운", "우체국택배", "한진택배", "롯데택배", "로젠택배", "CU편의점택배", "GS25반값택배"], key="tool_carrier")
        track_no = st.text_input("운송장 번호", placeholder="- 없이 숫자만 입력", key="tool_track")
        
        if track_no:
            query = f"{carrier} {track_no}"
            encoded_query = urllib.parse.quote(query)
            st.markdown('<div style="margin-top:20px;"></div>', unsafe_allow_html=True)
            st.link_button(f"🔍 {carrier} 조회하기", f"https://search.naver.com/search.naver?query={encoded_query}", use_container_width=True)
        else:
            st.markdown('<div class="tool-hint">💡 운송장 번호를 입력하면 네이버에서 배송을 조회할 수 있습니다</div>', unsafe_allow_html=True)
            
    with t2:
        st.markdown('''
        <div class="tool-card">
            <div class="tool-card-header">
                <span class="tool-icon">💱</span>
                <div class="tool-card-title">관세 계산기</div>
            </div>
            <div class="tool-card-desc">해외 직구 시 예상 관세와 부가세를 미리 계산해보세요</div>
        </div>
        ''', unsafe_allow_html=True)
        
        currency_mode = st.radio("통화 선택", ["USD", "JPY"], horizontal=True, key="tool_currency")
        
        if "USD" in currency_mode:
            st.caption(f"💵 적용 환율: {usd:,.1f}원")
            p_u = st.number_input("물품 가격 ($)", 190, step=10, key="tool_usd")
            krw_val = p_u * usd
            
            st.markdown('<div style="margin-top:24px;"></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="calc-result">≈ {krw_val:,.0f} 원</div>', unsafe_allow_html=True)
            
            if p_u <= 200: 
                st.markdown('<div class="result-safe">✅ 면세 범위 (안전)</div>', unsafe_allow_html=True)
            else: 
                duty = krw_val * 0.08
                vat = (krw_val + duty) * 0.1
                total_tax = duty + vat
                st.markdown(f'<div class="result-warning">🚨 과세 대상 (약 {total_tax:,.0f}원 부과 예상)</div>', unsafe_allow_html=True)
                st.caption("ℹ️ 관세 8% + 부가세 10% 기준 (일반 품목)")
        else:
            st.caption(f"💴 적용 환율: {jpy:,.1f}원")
            p_j = st.number_input("물품 가격 (¥)", 15000, step=1000, key="tool_jpy")
            krw_val = p_j * (jpy/100)
            
            st.markdown('<div style="margin-top:24px;"></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="calc-result">≈ {krw_val:,.0f} 원</div>', unsafe_allow_html=True)
            
            if (krw_val/usd) <= 150: 
                st.markdown('<div class="result-safe">✅ 면세 범위 (안전)</div>', unsafe_allow_html=True)
            else: 
                duty = krw_val * 0.08
                vat = (krw_val + duty) * 0.1
                total_tax = duty + vat
                st.markdown(f'<div class="result-warning">🚨 과세 대상 (약 {total_tax:,.0f}원 부과 예상)</div>', unsafe_allow_html=True)
                st.caption("ℹ️ 관세 8% + 부가세 10% 기준 (일반 품목)")
        
        st.caption("⚠️ 품목별 관세율은 달라질 수 있습니다. 정확한 세율은 관세청에서 확인하세요.")

# ==========================================
# 👮‍♂️ TAB 4: 사기 조회 (Ghost Button)
# ==========================================
with tab_safety:
    st.markdown('<div style="margin-bottom: 32px;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">👮‍♂️ 사기 피해 방지</div>', unsafe_allow_html=True)
    st.markdown('<div style="margin-bottom: 24px;"></div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="scam-box">
        <ul class="scam-list">
            <li class="scam-item">
                <span class="scam-head">🚫 카카오톡 유도 100% 사기</span>
                판매자가 "카톡으로 대화하자"며 아이디를 주면 즉시 차단하세요.
            </li>
            <li class="scam-item">
                <span class="scam-head">🚫 가짜 안전결제 링크 주의</span>
                네이버페이 등 결제 링크를 판매자가 직접 보내주면 '가짜 사이트'입니다. <span style="color:#ff4b4b; font-weight:bold;">절대 결제하거나 송금하지 마세요.</span>
            </li>
            <li class="scam-item">
                <span class="scam-head">🚫 더치트 2회 조회 필수</span>
                계좌번호 뿐만 아니라 '전화번호'로도 반드시 조회하세요. (대포폰 확인)
            </li>
            <li class="scam-item">
                <span class="scam-head">🚫 시세보다 너무 싼 가격</span>
                상태가 좋은데 가격이 터무니없이 저렴하면 미끼 상품일 확률이 높습니다.
            </li>
            <li class="scam-item">
                <span class="scam-head">🚫 인증샷 요구하기</span>
                물건 옆에 종이로 '오늘 날짜/구매자 닉네임'을 적어서 찍어달라고 요청하세요.
            </li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div style="margin-top: 48px; margin-bottom: 24px;"></div>', unsafe_allow_html=True)
    st.link_button("👮‍♂️ 더치트 무료 조회 바로가기", "https://thecheat.co.kr", type="secondary", use_container_width=True)

# ==========================================
# ⚖️ TAB 5: 2개 상품 비교
# ==========================================
with tab_compare:
    st.markdown('''
    <div class="compare-intro">
        <div class="compare-intro-title">⚖️ 2개 상품 시세 비교</div>
        <div class="compare-intro-desc">두 상품의 평균 가격과 시세 추이를 비교해보세요</div>
    </div>
    ''', unsafe_allow_html=True)
    
    comp_col1, vs_col, comp_col2 = st.columns([5, 1, 5])
    with comp_col1:
        kw1 = st.text_input("상품 A", placeholder="예: 라이카 M6", key="compare_kw1")
    with vs_col:
        st.markdown('<div class="vs-badge">VS</div>', unsafe_allow_html=True)
    with comp_col2:
        kw2 = st.text_input("상품 B", placeholder="예: 나이키 조던 1", key="compare_kw2")
    
    st.markdown('<div style="margin:40px 0;"></div>', unsafe_allow_html=True)
    
    if kw1 and kw2:
        df_prices = load_price_data()
        m1 = get_trend_data_from_sheet(kw1, df_prices)
        m2 = get_trend_data_from_sheet(kw2, df_prices)
        
        comp_left, comp_right = st.columns(2, gap="large")
        with comp_left:
            st.markdown(f'<div class="tool-header">{html.escape(kw1)}</div>', unsafe_allow_html=True)
            if m1:
                avg1 = m1.get('summary_avg', sum(m1['trend_prices'])/len(m1['trend_prices']) if m1['trend_prices'] else 0)
                min1 = m1.get('summary_min', min(m1['raw_prices']) if m1['raw_prices'] else 0)
                max1 = m1.get('summary_max', max(m1['raw_prices']) if m1['raw_prices'] else 0)
                
                st.markdown(f'''
                <div class="metric-grid">
                    <div class="metric-card">
                        <div class="metric-label">평균가</div>
                        <div class="metric-value">{avg1:,.1f}만</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">최저~최고</div>
                        <div class="metric-value" style="font-size:0.92rem;">{min1:,.0f}~{max1:,.0f}만</div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
                
                fig1 = go.Figure(go.Scatter(x=m1['dates'], y=m1['trend_prices'], mode='lines+markers', name=kw1,
                    line=dict(color=CHART_ACCENT, width=3.5, shape='spline', smoothing=1.3),
                    marker=dict(size=9, color=CHART_ACCENT_LIGHT, line=dict(width=2, color=CHART_MARKER_LINE), opacity=0.95),
                    fill='tozeroy', fillcolor=CHART_ACCENT_FILL))
                fig1.update_layout(height=220, margin=dict(l=10,r=10,t=10,b=25), 
                    paper_bgcolor=CHART_PAPER, plot_bgcolor=CHART_PLOT,
                    xaxis=dict(showticklabels=True, tickfont=dict(size=10, color=CHART_FONT, family='-apple-system'),
                               showgrid=False, showline=False), 
                    yaxis=dict(title='만원', title_font=dict(size=11, color=CHART_FONT), 
                               tickfont=dict(size=10, color=CHART_FONT),
                               showgrid=True, gridcolor=CHART_GRID, gridwidth=0.5, showline=False), 
                    template=CHART_TEMPLATE, showlegend=False,
                    hoverlabel=dict(bgcolor=CHART_HOVER_BG, font_size=13, font_color=CHART_HOVER_FONT),
                    transition={'duration': 600, 'easing': 'cubic-in-out'})
                st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': False}, key="comp_chart1")
            else:
                st.caption("📊 데이터 없음")
            
        with comp_right:
            st.markdown(f'<div class="tool-header">{html.escape(kw2)}</div>', unsafe_allow_html=True)
            if m2:
                avg2 = m2.get('summary_avg', sum(m2['trend_prices'])/len(m2['trend_prices']) if m2['trend_prices'] else 0)
                min2 = m2.get('summary_min', min(m2['raw_prices']) if m2['raw_prices'] else 0)
                max2 = m2.get('summary_max', max(m2['raw_prices']) if m2['raw_prices'] else 0)
                
                st.markdown(f'''
                <div class="metric-grid">
                    <div class="metric-card">
                        <div class="metric-label">평균가</div>
                        <div class="metric-value">{avg2:,.1f}만</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">최저~최고</div>
                        <div class="metric-value" style="font-size:0.92rem;">{min2:,.0f}~{max2:,.0f}만</div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
                
                fig2 = go.Figure(go.Scatter(x=m2['dates'], y=m2['trend_prices'], mode='lines+markers', name=kw2,
                    line=dict(color=CHART_ACCENT, width=3.5, shape='spline', smoothing=1.3),
                    marker=dict(size=9, color=CHART_ACCENT_LIGHT, line=dict(width=2, color=CHART_MARKER_LINE), opacity=0.95),
                    fill='tozeroy', fillcolor=CHART_ACCENT_FILL))
                fig2.update_layout(height=220, margin=dict(l=10,r=10,t=10,b=25), 
                    paper_bgcolor=CHART_PAPER, plot_bgcolor=CHART_PLOT,
                    xaxis=dict(showticklabels=True, tickfont=dict(size=10, color=CHART_FONT, family='-apple-system'),
                               showgrid=False, showline=False), 
                    yaxis=dict(title='만원', title_font=dict(size=11, color=CHART_FONT), 
                               tickfont=dict(size=10, color=CHART_FONT),
                               showgrid=True, gridcolor=CHART_GRID, gridwidth=0.5, showline=False), 
                    template=CHART_TEMPLATE, showlegend=False,
                    hoverlabel=dict(bgcolor=CHART_HOVER_BG, font_size=13, font_color=CHART_HOVER_FONT),
                    transition={'duration': 600, 'easing': 'cubic-in-out'})
                st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False}, key="comp_chart2")
            else:
                st.caption("📊 데이터 없음")
        
        if m1 and m2:
            avg1 = sum(m1['trend_prices'])/len(m1['trend_prices'])
            avg2 = sum(m2['trend_prices'])/len(m2['trend_prices'])
            diff = avg1 - avg2
            
            st.markdown('<div style="margin:50px 0 30px 0;"></div>', unsafe_allow_html=True)
            
            winner = kw1 if diff > 0 else kw2
            comparison_text = "더 비쌈" if diff > 0 else "더 쌈"
            
            st.markdown(f'''
            <div class="compare-result-box">
                <div class="result-label">📊 비교 결과</div>
                <div class="result-content">
                    <span class="winner-badge">{html.escape(winner)}</span> 평균가가
                    <span class="price-diff">{abs(diff):,.1f}만원</span> {html.escape(comparison_text)}
                </div>
                <div class="result-detail">
                    {html.escape(kw1)}: <strong>{avg1:,.1f}만원</strong> &nbsp;|&nbsp; {html.escape(kw2)}: <strong>{avg2:,.1f}만원</strong>
                </div>
            </div>
            ''', unsafe_allow_html=True)
    else:
        st.markdown('''
        <div class="compare-empty">
            <div class="empty-icon">⚖️</div>
            <div class="empty-text">비교할 두 상품을 입력하세요</div>
            <div class="empty-subtext">상품명을 정확히 입력하면 더 정확한 결과를 얻을 수 있습니다</div>
        </div>
        ''', unsafe_allow_html=True)



st.markdown('<div class="legal-footer">© 2026 RADAR | Global Price Intelligence</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------
# [8] 하단 고정 티커 (유지)
# ------------------------------------------------------------------
diff_usd = usd - usd_prev
diff_jpy = jpy - jpy_prev

sign_usd = "🔺" if diff_usd >= 0 else "🔻"
class_usd = "ticker-up" if diff_usd >= 0 else "ticker-down"
usd_text = f"{usd:,.0f}원 <span class='{class_usd}'>{sign_usd} {abs(diff_usd):.1f}원</span>"

sign_jpy = "🔺" if diff_jpy >= 0 else "▼"
class_jpy = "ticker-up" if diff_jpy >= 0 else "ticker-down"
jpy_text = f"{jpy:,.0f}원 <span class='{class_jpy}'>{sign_jpy} {abs(diff_jpy):.1f}원</span>"

us_limit_krw = usd * 200

jp_limit_jpy = 150 * (usd / (jpy / 100))
jp_limit_krw = usd * 150

# [Ticker Insight] - 객관적 표현 (변동 수치만 표시)
if diff_jpy < -5.0:
    insight_msg = f"JPY ▼{abs(diff_jpy):.1f}원"
    insight_color = "#00E5FF"
elif diff_usd > 5.0:
    insight_msg = f"USD ▲{diff_usd:.1f}원"
    insight_color = "#ff4b4b"
else:
    insight_msg = f"변동 ±5원 이내"
    insight_color = "#888"

# 환율기준: 현재 시각(KST) + 전일대비 방향 (이쁘게)
now_utc = datetime.now(timezone.utc)
now_kst = now_utc + timedelta(hours=9)
if abs(diff_usd) < 3 and abs(diff_jpy) < 5:
    trend_txt, trend_color = "보합", RATE_INFO_COLOR
elif diff_usd > 0 and diff_jpy > 0:
    trend_txt, trend_color = "상승세", "#ff4b4b"
elif diff_usd < 0 and diff_jpy < 0:
    trend_txt, trend_color = "하락세", "#4b89ff"
else:
    trend_txt, trend_color = "혼조", RATE_INFO_COLOR
rate_info = f"{now_kst.strftime('%Y-%m-%d %H:%M')} KST · 전일 <span style='color:{trend_color}; font-weight:600;'>{trend_txt}</span>"
ticker_content = f"""
<div class="ticker-wrap">
    <div class="ticker">
        <span class="ticker-item ticker-usd">USD/KRW <span class="ticker-val">{usd_text}</span></span>
        <span class="ticker-item ticker-jpy">JPY/KRW <span class="ticker-val">{jpy_text}</span></span>
        <span class="ticker-item ticker-limit-us">미국면세 한도 <span class="ticker-val">$200 (약 {us_limit_krw/10000:.0f}만원)</span></span>
        <span class="ticker-item ticker-limit-jp">일본면세 한도 <span class="ticker-val">¥{jp_limit_jpy:,.0f} (약 {jp_limit_krw/10000:.0f}만원)</span></span>
        <span class="ticker-item"><span class="ticker-val" style="color:{insight_color};">{insight_msg}</span></span>
        <span class="ticker-item ticker-rate">환율기준 <span class="ticker-val" style="color:{RATE_INFO_COLOR}; font-size:0.7rem;">{rate_info}</span></span>
        <span class="ticker-item ticker-sys">SYSTEM <span class="ticker-val" style="color:{ONLINE_COLOR}">ONLINE 🔵</span></span>
    </div>
</div>
"""
st.markdown(ticker_content, unsafe_allow_html=True)

