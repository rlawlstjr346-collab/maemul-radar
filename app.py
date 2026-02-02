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

CHART_BLUE = '#5C9EFF'
CHART_BLUE_LIGHT = '#90CAF9'
CHART_BLUE_FILL = 'rgba(92, 158, 255, 0.15)'
CHART_BLUE_HIGHLIGHT = 'rgba(92, 158, 255, 0.35)'

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
# [테마] 라이트 모드 개발 중단 - 다크 모드만 사용 (빠른 배포)
st.session_state.theme_light = False

# ------------------------------------------------------------------
# [4] CSS 스타일링 (Pro Dashboard Cards)
# ------------------------------------------------------------------
st.markdown("""
<style>
    /* Global Theme */
    .stApp { 
        background-color: #0E1117; 
        background: radial-gradient(circle at 50% -20%, #1c2333 0%, #0E1117 80%);
        color: #EEEEEE; font-family: 'Inter', 'Pretendard', sans-serif; 
    }
    /* Streamlit 상단 초록색 바 제거 */
    [data-testid="stHeader"], header[data-testid="stHeader"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    
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
    .st-key-header_logo_toggle { display: flex !important; flex-direction: column !important; align-items: flex-start !important; margin-top: 40px !important; gap: 8px !important; }
    .header-logo-area { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; margin: 0 !important; }
    .header-logo-standalone {
        display: flex; flex-direction: column; align-items: flex-start; flex-shrink: 0;
        text-decoration: none !important; border-bottom: none !important; gap: 1px;
        position: relative;
    }
    .header-logo-standalone::before {
        content: ''; position: absolute; inset: -14px -22px -14px -22px; border-radius: 26px;
        z-index: -1; pointer-events: none;
        background: radial-gradient(ellipse 120% 100% at 50% 50%, rgba(92,158,255,0.1) 0%, rgba(92,158,255,0.03) 50%, transparent 70%);
        animation: logo-halo-pulse 3.5s ease-in-out infinite;
    }
    @keyframes logo-halo-pulse { 0%, 100% { opacity: 0.6; transform: scale(0.98); } 50% { opacity: 1; transform: scale(1.02); } }
    .header-logo-standalone:hover, .header-logo-standalone:focus, .header-logo-standalone:visited { text-decoration: none !important; border-bottom: none !important; }
    .header-logo-standalone *, .header-logo-standalone *:hover { text-decoration: none !important; border-bottom: none !important; }
    .theme-toggle { font-size: 1.2rem; opacity: 0.85; transition: opacity 0.2s; flex-shrink: 0; padding: 8px 12px; display: inline-flex; align-items: center; justify-content: center; border-radius: 12px; }
    .theme-toggle:hover { opacity: 1; background: rgba(255,255,255,0.08); }
    .theme-toggle-disabled { font-size: 1.2rem; opacity: 0.5; flex-shrink: 0; padding: 8px 12px; display: inline-flex; align-items: center; justify-content: center; border-radius: 12px; cursor: not-allowed; pointer-events: none; border: 1px solid rgba(255,255,255,0.2); }
    /* 빌보드 래퍼: 중앙 정렬 */
    .radar-billboard-wrap { display: flex; justify-content: center; align-items: center; }
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
        gap: 2px;
    }
    .radar-top-row { display: flex; align-items: center; gap: 14px; }
    .radar-icon-wrap { position: relative; display: inline-flex; }
    .radar-icon-wrap::before { content: ''; position: absolute; left: 50%; top: 50%; width: 52px; height: 52px; margin: -26px 0 0 -26px; border-radius: 50%; background: radial-gradient(circle at center, rgba(92,158,255,0.18) 0%, rgba(120,180,255,0.08) 25%, transparent 55%); animation: icon-pulse 3.2s ease-in-out infinite 0.4s; pointer-events: none; z-index: 0; }
    .radar-icon { font-size: 1.8rem; z-index: 2; line-height: 1; position: relative; filter: drop-shadow(0 0 8px rgba(92,158,255,0.5)) drop-shadow(0 0 3px rgba(255,255,255,0.4)) drop-shadow(0 1px 2px rgba(0,0,0,0.3)); animation: icon-glow 3.2s ease-in-out infinite; transition: transform 0.3s ease; }
    .radar-left:hover .radar-icon, .header-logo-standalone:hover .radar-icon { transform: scale(1.12) rotate(-6deg); }
    @keyframes icon-pulse { 0%, 100% { opacity: 0.2; transform: scale(0.92); } 50% { opacity: 0.5; transform: scale(1.05); } }
    @keyframes icon-glow { 0%, 100% { filter: drop-shadow(0 0 5px rgba(92,158,255,0.3)) drop-shadow(0 0 2px rgba(255,255,255,0.2)); } 50% { filter: drop-shadow(0 0 12px rgba(92,158,255,0.5)) drop-shadow(0 0 3px rgba(255,255,255,0.35)); } }
    .radar-title-wrap { position: relative; display: inline-block; }
    .radar-title { 
        font-size: 1.9rem; font-weight: 900; letter-spacing: -1px; font-style: italic; z-index: 2; line-height: 1;
        background: linear-gradient(90deg, #ffffff 0%, #ffffff 68%, #fefefe 78%, #fcfcfc 86%, #f9f9f9 93%, #f6f6f6 100%);
        background-size: 100% 100%;
        background-position: 0% 0%;
        -webkit-background-clip: text; background-clip: text;
        -webkit-text-fill-color: transparent; color: transparent;
        position: relative;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
    }
    .radar-sub { font-size: 0.65rem; color: #a5d8ff !important; -webkit-text-fill-color: #a5d8ff !important; letter-spacing: 3px; font-weight: 600; margin-left: 48px; text-transform: uppercase; text-shadow: 0 1px 2px rgba(0,0,0,0.3); }
    
    
    /* Billboard - 4x2 그리드, 유리 박스, 구분감 강화 */
    .radar-billboard {
        display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); grid-template-rows: repeat(2, 1fr);
        gap: 10px 14px;
        background: rgba(255,255,255,0.06); padding: 12px 18px; margin: 0 auto;
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255,255,255,0.18); border-radius: 16px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.06);
        width: fit-content; max-width: 880px; flex-shrink: 0;
    }
    
    /* [Responsive] 화면이 좁으면 4x1 (상단 4개만) */
    @media (max-width: 1100px) {
        .radar-billboard { grid-template-rows: 1fr; max-width: 620px; width: fit-content; }
        .c-vibe, .c-living, .c-game, .c-outdoor { display: none !important; }
    }
    @media (max-width: 768px) {
        .radar-billboard { display: none !important; }
    }
    .bill-col { 
        display: flex; flex-direction: column; 
        min-width: 0; overflow: hidden;
    }
    .bill-head { 
        font-size: 0.7rem; color: #888; font-weight: 800; margin-bottom: 6px; 
        letter-spacing: 1px; text-transform: uppercase; 
        border-bottom: 1px solid #444; padding-bottom: 4px; white-space: nowrap;
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
        will-change: transform;
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
    a.bill-item { color: inherit; text-decoration: none; display: block; cursor: pointer; transition: opacity 0.2s; }
    a.bill-item:hover { opacity: 0.8; }
    
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
    
    /* [홈 빈 상태] 전투기 레이더 스타일 - 펄스 + 타겟 블립 */
    .home-sonar-wrap { text-align: center; padding: 40px 20px 60px; }
    .home-sonar-wrap .sonar-wrap { width: 220px; height: 220px; margin: 0 auto; position: relative; display: flex; justify-content: center; align-items: center; }
    .home-sonar-wrap .sonar-ring { position: absolute; left: 50%; top: 50%; width: 40px; height: 40px; margin: -20px 0 0 -20px; border-radius: 50%; border: 2px solid rgba(59,130,246,0.5); transform-origin: center center; animation: home-sonar-ping 8.5s ease-out infinite; will-change: transform; animation-fill-mode: both; z-index: 1; }
    .home-sonar-wrap .sonar-ring:nth-child(1) { animation-delay: 0s; }
    .home-sonar-wrap .sonar-ring:nth-child(2) { animation-delay: 1.8s; }
    .home-sonar-wrap .sonar-ring:nth-child(3) { animation-delay: 3.6s; }
    .home-sonar-wrap .sonar-ring:nth-child(4) { animation-delay: 5.4s; }
    .home-sonar-wrap .sonar-ring:nth-child(5) { animation-delay: 7.2s; }
    .home-sonar-wrap .sonar-dot { position: absolute; left: 50%; top: 50%; width: 12px; height: 12px; margin: -6px 0 0 -6px; border-radius: 50%; background: #3B82F6; box-shadow: 0 0 12px rgba(59,130,246,0.6); transform-origin: center center; animation: sonar-dot-pulse 1.5s ease-in-out infinite; z-index: 10; }
    @keyframes sonar-dot-pulse { 0%, 100% { transform: scale(0.95); opacity: 1; } 50% { transform: scale(1.1); opacity: 1; } }
    .home-sonar-wrap .sonar-blip { position: absolute; width: 4px; height: 4px; margin: -2px 0 0 -2px; border-radius: 50%; background: rgba(92,158,255,0.95); box-shadow: 0 0 10px rgba(92,158,255,0.8), 0 0 20px rgba(92,158,255,0.4); opacity: 0; animation: radar-blip 9s linear infinite; animation-fill-mode: both; pointer-events: none; z-index: 2; }
    @keyframes home-sonar-ping { 0% { transform: scale(0.15); opacity: 0.9; border-color: rgba(59,130,246,0.8); } 30% { opacity: 0.9; border-color: rgba(59,130,246,0.5); } 80% { opacity: 0.3; border-color: rgba(59,130,246,0.15); } 100% { transform: scale(5.5); opacity: 0; border-color: rgba(59,130,246,0.02); } }
    @keyframes radar-blip { 0%, 8% { opacity: 0; } 10% { opacity: 1; } 12% { opacity: 1; } 18% { opacity: 0.5; } 22% { opacity: 0; } 100% { opacity: 0; } }
    .home-sonar-hint { font-size: 1.1rem; margin: 24px 0 0 0; font-weight: 600; letter-spacing: 0.3px; display: inline-flex; align-items: center; gap: 10px; padding: 12px 20px; border-radius: 12px; background: linear-gradient(135deg, rgba(59,130,246,0.08) 0%, rgba(0,229,255,0.04) 100%); border: 1px solid rgba(59,130,246,0.2); color: #b8d4f0; text-shadow: 0 0 20px rgba(59,130,246,0.3); animation: hint-glow 3s ease-in-out infinite; }
    .home-sonar-hint::before { content: '📡'; font-size: 1.2rem; opacity: 0.95; filter: drop-shadow(0 0 4px rgba(0,229,255,0.4)); }
    @keyframes hint-glow { 0%, 100% { box-shadow: 0 0 0 rgba(59,130,246,0); } 50% { box-shadow: 0 0 16px rgba(59,130,246,0.15); } }
    
    /* [탭 중앙 정렬] 시세 분석, 마켓소스 등 — 히어로와 통일감 */
    div[data-baseweb="tab-list"] { justify-content: center !important; }
    [data-testid="stTabs"] > div { justify-content: center !important; }
    [data-baseweb="tab-list"] { display: flex !important; justify-content: center !important; }

    /* 4. Neon Glass Buttons (Direct Access) */
    div[data-testid="stLinkButton"] > a { 
        background-color: rgba(255, 255, 255, 0.03) !important; 
        backdrop-filter: blur(5px);
        border-radius: 16px; 
        font-weight: 700; 
        transition: all 0.3s ease; 
        text-decoration: none; 
        border-width: 2px !important;
        border-style: solid !important;
        height: 110px;
        display: flex; flex-direction: column; align-items: center; justify-content: center; 
        font-size: 1.1rem; letter-spacing: -0.5px;
        color: #ddd !important; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    }
    a[href*="bunjang"] { border-color: #D32F2F !important; }
    a[href*="bunjang"]:hover { background-color: rgba(211, 47, 47, 0.15) !important; color: #FFF !important; box-shadow: 0 0 25px rgba(211, 47, 47, 0.5); transform: translateY(-3px); }
    a[href*="daangn"] { border-color: #FF6F00 !important; }
    a[href*="daangn"]:hover { background-color: rgba(255, 111, 0, 0.15) !important; color: #FFF !important; box-shadow: 0 0 25px rgba(255, 111, 0, 0.5); transform: translateY(-3px); }
    a[href*="joongna"] { border-color: #2E7D32 !important; }
    a[href*="joongna"]:hover { background-color: rgba(46, 125, 50, 0.15) !important; color: #FFF !important; box-shadow: 0 0 25px rgba(46, 125, 50, 0.5); transform: translateY(-3px); }
    a[href*="fruits"] { border-color: #7B1FA2 !important; }
    a[href*="fruits"]:hover { background-color: rgba(123, 31, 162, 0.15) !important; color: #FFF !important; box-shadow: 0 0 25px rgba(123, 31, 162, 0.5); transform: translateY(-3px); }
    a[href*="ebay"] { border-color: #0055ff !important; }
    a[href*="ebay"]:hover { background-color: rgba(0, 85, 255, 0.15) !important; color: #FFF !important; box-shadow: 0 0 25px rgba(0, 85, 255, 0.5); transform: translateY(-3px); }
    a[href*="mercari"] { border-color: #999 !important; }
    a[href*="mercari"]:hover { background-color: rgba(255, 255, 255, 0.15) !important; color: #FFF !important; box-shadow: 0 0 25px rgba(255, 255, 255, 0.4); transform: translateY(-3px); }
    
    /* Ghost Button (TheCheat) */
    a[href*="thecheat"] {
        background-color: transparent !important; border: 1px solid #666 !important; color: #888 !important; height: 60px !important; font-size: 1rem !important;
    }
    a[href*="thecheat"]:hover {
        background-color: #00B4DB !important; border-color: #00B4DB !important; color: #fff !important; box-shadow: 0 0 15px rgba(0, 180, 219, 0.5);
    }

    /* 5. [NEW] Pro Dashboard Cards (Color Tag Style) */
    .source-card {
        background-color: #1A1A1A; /* Dark Grey Base */
        border: 1px solid #333; 
        border-radius: 6px; 
        padding: 15px 20px; 
        display: flex; align-items: center; justify-content: space-between; 
        margin-bottom: 10px; 
        transition: all 0.2s ease-in-out; 
        text-decoration: none;
        height: 60px;
        position: relative;
        overflow: hidden;
    }
    
    /* Hover Effects: Glow based on tag color */
    .card-quasar:hover { background-color: rgba(255, 153, 0, 0.15); border-color: #FF9900; }
    .card-cool:hover { background-color: rgba(255, 255, 255, 0.15); border-color: #FFF; }
    .card-meeco:hover { background-color: rgba(52, 152, 219, 0.15); border-color: #3498db; }
    .card-clien:hover { background-color: rgba(55, 96, 146, 0.2); border-color: #376092; }
    
    .card-slr:hover { background-color: rgba(66, 165, 245, 0.15); border-color: #42A5F5; }
    .card-leica:hover { background-color: rgba(213, 0, 0, 0.15); border-color: #D50000; }
    .card-film:hover { background-color: rgba(244, 208, 63, 0.15); border-color: #F4D03F; }
    .card-dof:hover { background-color: rgba(189, 195, 199, 0.15); border-color: #BDC3C7; }
    
    .card-nike:hover { background-color: rgba(255, 255, 255, 0.1); border-color: #AAA; }
    .card-kream:hover { background-color: rgba(255, 255, 255, 0.1); border-color: #FFF; font-style: italic; }
    .card-eomisae:hover { background-color: rgba(142, 36, 170, 0.15); border-color: #8E24AA; }
    .card-diesel:hover { background-color: rgba(100, 100, 100, 0.2); border-color: #777; }
    
    .card-asamo:hover { background-color: rgba(46, 204, 113, 0.15); border-color: #2ecc71; }
    .card-mac:hover { background-color: rgba(200, 200, 200, 0.15); border-color: #CCC; }
    .card-joongna:hover { background-color: rgba(0, 211, 105, 0.15); border-color: #00d369; }
    .card-ruli:hover { background-color: rgba(46, 117, 182, 0.2); border-color: #2E75B6; }
    .card-pompu:hover { background-color: rgba(255, 69, 0, 0.15); border-color: #FF4500; }
    .card-bobaedream:hover { background-color: rgba(34, 139, 34, 0.15); border-color: #228B22; }
    .card-ohou:hover { background-color: rgba(255, 105, 180, 0.15); border-color: #FF69B4; }
    .card-gmarket:hover { background-color: rgba(255, 215, 0, 0.15); border-color: #FFD700; }
    .card-musinsa:hover { background-color: rgba(0, 0, 0, 0.2); border-color: #333; }
    .card-bunjang:hover { background-color: rgba(211, 47, 47, 0.15); border-color: #D32F2F; }
    .card-daangn:hover { background-color: rgba(255, 111, 0, 0.15); border-color: #FF6F00; }
    .card-fruits:hover { background-color: rgba(156, 39, 176, 0.15); border-color: #9C27B0; }
    .card-auction:hover { background-color: rgba(244, 67, 54, 0.15); border-color: #F44336; }
    .card-ebay:hover { background-color: rgba(0, 85, 255, 0.15); border-color: #0055ff; }
    .card-mercari:hover { background-color: rgba(255, 255, 255, 0.15); border-color: #999; }

    /* Left Color Tags */
    .card-quasar { border-left: 6px solid #FF9900 !important; }
    .card-cool { border-left: 6px solid #DDD !important; }
    .card-meeco { border-left: 6px solid #3498db !important; }
    .card-clien { border-left: 6px solid #376092 !important; }
    
    .card-slr { border-left: 6px solid #42A5F5 !important; }
    .card-leica { border-left: 6px solid #D50000 !important; }
    .card-film { border-left: 6px solid #F4D03F !important; }
    .card-dof { border-left: 6px solid #95a5a6 !important; }
    
    .card-nike { border-left: 6px solid #333 !important; }
    .card-kream { border-left: 6px solid #FFF !important; }
    .card-eomisae { border-left: 6px solid #8E24AA !important; }
    .card-diesel { border-left: 6px solid #555 !important; }
    
    .card-asamo { border-left: 6px solid #2ecc71 !important; }
    .card-mac { border-left: 6px solid #aaa !important; }
    .card-joongna { border-left: 6px solid #00d369 !important; }
    .card-ruli { border-left: 6px solid #2E75B6 !important; }
    .card-pompu { border-left: 6px solid #FF4500 !important; }
    .card-bobaedream { border-left: 6px solid #228B22 !important; }
    .card-ohou { border-left: 6px solid #FF69B4 !important; }
    .card-gmarket { border-left: 6px solid #FFD700 !important; }
    .card-musinsa { border-left: 6px solid #333 !important; }
    .card-bunjang { border-left: 6px solid #D32F2F !important; }
    .card-daangn { border-left: 6px solid #FF6F00 !important; }
    .card-fruits { border-left: 6px solid #9C27B0 !important; }
    .card-auction { border-left: 6px solid #F44336 !important; }
    .card-ebay { border-left: 6px solid #0055ff !important; }
    .card-mercari { border-left: 6px solid #999 !important; }

    .source-info { display: flex; flex-direction: column; gap: 2px; }
    .source-name { font-weight: 800; color: #eee; font-size: 1.05rem; letter-spacing: -0.5px; }
    .source-desc { font-size: 0.8rem; color: #777; font-weight: 400; }
    
    .category-header { font-size: 0.8rem; font-weight: 700; color: #777; margin-top: 24px; margin-bottom: 8px; letter-spacing: 1.5px; text-transform: uppercase; border-bottom: 1px solid #2a2a2a; padding-bottom: 6px; }
    .category-header:first-of-type { margin-top: 0; }
    .source-card { margin-bottom: 8px !important; }

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
    
    /* Scam Box */
    .scam-box { border: 1px solid #333; border-left: 4px solid #ff4b4b; background-color: #1A0505; padding: 25px; border-radius: 12px; margin-bottom: 20px; }
    .scam-list { margin-top: 10px; padding-left: 0; list-style-type: none; }
    .scam-item { color: #ddd; margin-bottom: 15px; line-height: 1.5; font-size: 1rem; border-bottom: 1px solid #333; padding-bottom: 10px; }
    .scam-item:last-child { border-bottom: none; }
    .scam-head { color: #ff4b4b; font-weight: 800; font-size: 1.1rem; display: block; margin-bottom: 4px; }
    
    .legal-footer { font-size: 0.7rem; color: #333; margin-top: 80px; text-align: center; margin-bottom: 50px; }

    /* [NEW] Metric Cards (Blue Accent, Compact) */
    .metric-card { 
        background: linear-gradient(90deg, rgba(26,26,26,1) 0%, rgba(26,26,26,0.5) 100%);
        border: 1px solid #333; border-left: 3px solid #5C9EFF;
        padding: 6px 10px; border-radius: 10px; margin-bottom: 6px; position: relative; 
        transition: all 0.3s ease;
    }
    .metric-card:hover {
        border-color: #555; border-left-color: #5C9EFF;
        box-shadow: 0 0 20px rgba(92, 158, 255, 0.15); transform: translateX(3px);
    }
    .metric-label { font-size: 0.65rem; color: #888; font-weight: 500; margin-bottom: 1px; }
    .metric-value { font-size: 1.05rem; font-weight: 800; color: #eee; letter-spacing: -0.5px; font-family: 'Inter', sans-serif; }
    .metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; }
    .metric-sub { font-size: 0.8rem; color: #666; margin-top: 5px; font-family: 'Inter', sans-serif; }
    .ticker-up { color: #ff4b4b; font-weight: 700; font-size: 0.9rem; }
    .ticker-down { color: #4b89ff; font-weight: 700; font-size: 0.9rem; }

    /* [NEW] Capsule Title (Section Header) */
    .capsule-title {
        font-size: 1.1rem;
        font-weight: 800;
        color: #fff;
        margin-top: 30px;
        margin-bottom: 15px;
        display: inline-flex;
        align-items: center;
        background: #1A1A1A;
        padding: 8px 20px;
        border-radius: 30px;
        border: 1px solid #333;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }
    .capsule-sub { font-size: 0.75rem; color: #666; margin-left: 10px; font-weight: 400; letter-spacing: 0.5px; }

    /* 섹션 제목 (HTML div - p:only-child 숨김 대상 제외) */
    .section-title { font-size: 1.1rem; font-weight: 700; color: #eee; margin-bottom: 8px; }
    
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
    
    /* 차트: 아이덴티티 - 둥근 모서리 + 부드러운 그림자 */
    [data-testid="stPlotlyChart"] { 
        border-radius: 16px !important; overflow: hidden;
        margin-top: 4px !important; margin-bottom: 4px !important;
        box-shadow: 0 4px 24px rgba(0,0,0,0.25), 0 0 1px rgba(92,158,255,0.15);
        border: 1px solid rgba(255,255,255,0.06);
    }
    [data-testid="stPlotlyChart"] > div { border-radius: 16px !important; }

    /* None 숨기기 - 단일 p만 있는 블록만 숨김 (메트릭 카드 등 HTML 블록은 유지) */
    div[data-testid="stMarkdown"]:has(p:only-child) {
        font-size: 0 !important; line-height: 0 !important;
        overflow: hidden !important; height: 0 !important;
        margin: 0 !important; padding: 0 !important;
        min-height: 0 !important; display: block !important;
    }

    /* [NEW] 스켈레톤 로딩 - 차트/카드 영역 */
    .skeleton-wrap { background: rgba(20,25,35,0.6); border-radius: 12px; padding: 16px; margin: 8px 0; border: 1px solid rgba(255,255,255,0.06); }
    .skeleton-card { background: linear-gradient(90deg, #2a2a2a 25%, #3a3a3a 50%, #2a2a2a 75%); background-size: 200% 100%; animation: skeleton-shimmer 1.5s infinite; border-radius: 10px; height: 52px; margin-bottom: 6px; }
    .skeleton-chart { background: linear-gradient(90deg, #2a2a2a 25%, #3a3a3a 50%, #2a2a2a 75%); background-size: 200% 100%; animation: skeleton-shimmer 1.5s infinite; border-radius: 12px; height: 280px; margin: 8px 0; }
    .skeleton-chart-sm { background: linear-gradient(90deg, #2a2a2a 25%, #3a3a3a 50%, #2a2a2a 75%); background-size: 200% 100%; animation: skeleton-shimmer 1.5s infinite; border-radius: 12px; height: 220px; margin: 8px 0; }
    .skeleton-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; }
    @keyframes skeleton-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

    /* [NEW] 검색 자동완성 - 미니멀 pill (중앙 정렬), 모바일에서 시세 요약 가림 방지 */
    .search-pills { display: flex; flex-wrap: wrap; gap: 6px 10px; margin-top: 8px; margin-bottom: 12px; align-items: center; justify-content: center; }
    .search-pills a { 
        display: inline-block; padding: 4px 10px; font-size: 0.8rem; color: #8a9aab; 
        background: rgba(255,255,255,0.04); border: 1px solid #333; border-radius: 20px; 
        text-decoration: none; transition: all 0.2s; white-space: nowrap;
    }
    .search-pills a:hover { color: #5C9EFF; border-color: rgba(92,158,255,0.4); background: rgba(92,158,255,0.08); }
    
    /* 시세 요약 섹션 (다크모드) */
    .section-title--price-summary { 
        margin-top: 20px; margin-bottom: 12px; 
        font-weight: 800; font-size: 1.15rem; color: #eee;
        padding-bottom: 10px; border-bottom: 2px solid rgba(92,158,255,0.35);
        letter-spacing: -0.3px; text-shadow: 0 1px 2px rgba(0,0,0,0.3);
    }
    .metric-grid { gap: 10px 14px; margin-bottom: 4px; }
    .metric-card { 
        background: linear-gradient(135deg, rgba(26,32,45,0.95) 0%, rgba(20,26,38,0.9) 100%);
        border: 1px solid rgba(92,158,255,0.2); border-left: 4px solid #5C9EFF;
        padding: 10px 14px; border-radius: 12px; 
        box-shadow: 0 2px 12px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.04);
        transition: all 0.25s ease;
    }
    .metric-card:hover {
        border-color: rgba(92,158,255,0.4); border-left-color: #5C9EFF;
        box-shadow: 0 4px 20px rgba(92,158,255,0.12), 0 2px 12px rgba(0,0,0,0.25);
        transform: translateX(2px);
    }
    .metric-label { font-size: 0.7rem; color: #8a9aab; font-weight: 600; margin-bottom: 2px; letter-spacing: 0.3px; text-transform: uppercase; }
    .metric-value { font-size: 1.1rem; font-weight: 800; color: #eee; letter-spacing: -0.5px; }
    .signal-help { color: #8a9aab !important; font-size: 0.8rem; line-height: 1.5; }

    /* [반응형] 태블릿 (768px 이하) */
    @media (max-width: 768px) {
        .block-container { padding: 1rem 1rem 6rem !important; max-width: 100% !important; }
        .logo-demo-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
        .radar-title { font-size: 1.8rem !important; }
        .metric-grid { grid-template-columns: 1fr !important; }
        .skeleton-grid { grid-template-columns: 1fr !important; }
        .market-grid { grid-template-columns: 1fr !important; }
        .source-card { height: 54px !important; padding: 10px 14px !important; }
        .source-name { font-size: 0.95rem !important; }
        .capsule-title { font-size: 1rem !important; padding: 6px 14px !important; }
        .section-title { font-size: 1rem !important; }
        .skeleton-chart { height: 220px !important; }
        .skeleton-chart-sm { height: 180px !important; }
        [data-testid="stPlotlyChart"] { min-height: 200px !important; }
    }
    /* [반응형] 모바일 (480px 이하) - 추천검색어 영역 축소, 시세 요약 가림 방지 */
    @media (max-width: 480px) {
        .block-container { padding: 0.75rem 0.75rem 5rem !important; }
        .radar-title { font-size: 1.5rem !important; }
        .metric-card { padding: 8px 10px !important; }
        .metric-value { font-size: 0.95rem !important; }
        .ticker-wrap { height: 28px; }
        .ticker-item { font-size: 0.7rem !important; margin-right: 24px !important; }
        .search-pills { gap: 5px 8px; margin-bottom: 16px; }
        .search-pills a { padding: 3px 8px; font-size: 0.75rem; }
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
    div[data-baseweb="input"] { 
        background: rgba(255,255,255,0.04) !important; 
        border: 1px solid rgba(92,158,255,0.18) !important; 
        border-radius: 12px !important; 
        color: white !important; 
        height: 56px !important; 
        box-shadow: none !important;
        transition: all 0.25s ease;
    }
    div[data-baseweb="input"] > div > input {
        color: white !important; 
        font-family: -apple-system, 'Inter', 'Pretendard', sans-serif !important;
        font-size: 1.05rem !important;
        padding: 0 24px !important;
    }
    div[data-baseweb="input"]:focus-within { 
        border-color: rgba(92,158,255,0.45) !important; 
        background: rgba(92,158,255,0.06) !important;
        box-shadow: 0 0 0 1px rgba(92,158,255,0.15) !important;
    }
    div[data-baseweb="input"]:hover { 
        border-color: rgba(92,158,255,0.35) !important; 
        background: rgba(92,158,255,0.05) !important;
    }
    input::placeholder { color: rgba(255,255,255,0.25) !important; font-size: 1rem; }
    </style>
    """, unsafe_allow_html=True)

# [차트 테마] 다크 모드 전용
CHART_PAPER = "#0E1117"
CHART_PLOT = "rgba(20,25,35,0.8)"
CHART_FONT = "#b8c5d4"
CHART_TEMPLATE = "plotly_dark"
CHART_LEGEND_BG = "#0E1117"
CHART_LEGEND_BORDER = "rgba(255,255,255,0.1)"
CHART_GRID = "rgba(92,158,255,0.12)"
CHART_HOVER_BG = "#1e2a38"
CHART_HOVER_FONT = "#e8eef4"
CHART_ZEROLINE = "rgba(255,255,255,0.1)"
CHART_MARKER_LINE = "#ffffff"
CHART_ACCENT = CHART_BLUE
CHART_ACCENT_LIGHT = CHART_BLUE_LIGHT
CHART_ACCENT_HIGHLIGHT = CHART_BLUE_HIGHLIGHT
CHART_ACCENT_FILL = CHART_BLUE_FILL
CHART_GRAY_LINE = "#7B8B9C"
CHART_GRAY_FILL = "rgba(123,139,156,0.06)"
CHART_DOTTED = "#8B9BAB"
CHART_BAR_SCALE = [[0, 'rgba(92,158,255,0.35)'], [0.4, 'rgba(92,158,255,0.7)'], [0.7, CHART_BLUE], [1, CHART_BLUE_LIGHT]]
CHART_HOVER_BORDER = "rgba(92,158,255,0.4)"

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
_header_c1, _header_c2, _header_c3 = st.columns([1.5, 5, 1.5], vertical_alignment="top", gap="small")
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

# [빌보드/최근검색 클릭] query params → 검색창에 반영 후 URL에서 q 제거 (다른 검색 가능하도록)
try:
    q = getattr(st, "query_params", None)
    if q and q.get("q"):
        st.session_state.search_input = q.get("q")
        try:
            del st.query_params["q"]  # URL에서 q 제거 → 다음 rerun에서 사용자 입력 덮어쓰기 방지
        except Exception:
            pass
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
        if st.session_state.theme_light:
            st.markdown("""
            <style>
            /* 검색창: 크림 팔레트 */
            .stApp div[data-baseweb="input"], [data-testid="stAppViewContainer"] div[data-baseweb="input"],
            div[data-baseweb="input"], div[data-baseweb="input"] > div { 
                background: #faf7f0 !important; background-color: #faf7f0 !important;
                border: 1px solid #e5e0d5 !important; border-radius: 10px !important;
                box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
            }
            div[data-baseweb="input"] > div > input, input[placeholder*="여기에 검색"] { 
                color: #1c1b19 !important; background: transparent !important; background-color: transparent !important;
            }
            div[data-baseweb="input"]:focus-within, div[data-baseweb="input"]:focus-within > div { 
                background: #faf7f0 !important; background-color: #faf7f0 !important; border-color: #1c1b19 !important;
            }
            div[data-baseweb="input"]:hover, div[data-baseweb="input"]:hover > div { 
                background: #faf7f0 !important; background-color: #faf7f0 !important; border-color: #d9d3c5 !important;
            }
            input::placeholder { color: #6b6560 !important; }
            </style>
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
    
    df_prices = load_price_data() if (keyword and keyword.strip()) else pd.DataFrame()
    
    # [스켈레톤 로딩] 검색 시 데이터 로드 전 차트/카드 영역에 스켈레톤 표시
    skel_ph = st.empty()
    if keyword and keyword.strip():
        with skel_ph.container():
            st.markdown("""
            <div class="skeleton-wrap">
                <div class="section-title section-title--price-summary">📊 시세 요약</div>
                <div class="skeleton-grid">
                    <div class="skeleton-card"></div>
                    <div class="skeleton-card"></div>
                    <div class="skeleton-card"></div>
                    <div class="skeleton-card"></div>
                </div>
                <div class="section-title">📈 전체 시세</div>
                <div class="skeleton-chart"></div>
                <div class="section-title">📊 가격 분포</div>
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

            # [Fruits Name Fixed] - HTML 링크로 변경 (link_button의 None 라벨 이슈 회피)
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
                <a href="https://www.ebay.com/sch/i.html?_nkw={encoded_eng}" target="_blank" class="source-card card-ebay" style="text-decoration:none;"><div class="source-info"><span class="source-name">🔵 eBay ({eng_keyword})</span></div><span>🔗</span></a>
                <a href="https://jp.mercari.com/search?keyword={encoded_jp}" target="_blank" class="source-card card-mercari" style="text-decoration:none;"><div class="source-info"><span class="source-name">⚪ Mercari ({jp_keyword})</span></div><span>🔗</span></a>
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
                st.markdown(f"<div style='margin-top:30px; margin-bottom:10px; color:{ACCENT_CURATION}; font-weight:700;'>💡 {curation_title}</div>", unsafe_allow_html=True)
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
                
                # [1] 시세 요약 2x2 + 시그널 (다크 모드 색상)
                def _signal_strength(n):
                    if n >= 15: return ("●●●●", "강함", "#5C9EFF")
                    if n >= 8: return ("●●●", "보통", "#7BB3FF")
                    if n >= 4: return ("●●", "약함", "#9BC4FF")
                    return ("●", "희미", "#B8D5FF")
                sig_bar, sig_text, sig_color = _signal_strength(n_data)
                _data_label = matched.get("matched_keyword") or keyword
                _sec1, _sec2 = st.columns(2)
                with _sec1:
                    st.markdown("<div class='section-title section-title--price-summary'>📊 시세 요약</div>", unsafe_allow_html=True)
                with _sec2:
                    st.markdown(f"<div class='section-title' style='margin-top:0;text-align:right;font-size:0.85rem;color:{SIGNAL_HELP_COLOR};'>📋 시세 데이터: <strong>{html.escape(str(_data_label))}</strong></div>", unsafe_allow_html=True)
                st.markdown(f"""
                <div class="metric-grid">
                    <div class="metric-card"><div class="metric-label">평균가</div><div class="metric-value">{kr_avg:,.1f}만</div></div>
                    <div class="metric-card"><div class="metric-label">시그널</div><div class="metric-value" style="font-size:0.9rem;"><span style="color:{sig_color};">{sig_bar}</span> {sig_text}</div></div>
                    <div class="metric-card"><div class="metric-label">최고가</div><div class="metric-value">{kr_max:,.1f}만</div></div>
                    <div class="metric-card"><div class="metric-label">최저가</div><div class="metric-value">{kr_min:,.1f}만</div></div>
                </div>
                <p class="signal-help" style="margin-top:8px;font-size:0.8rem;color:{SIGNAL_HELP_COLOR};line-height:1.4;">
                    💡 시그널은 수집된 거래 데이터 건수에 비례합니다. ●●●●(강함)일수록 가격분포 데이터가 풍부해 <strong>검색 결과 신뢰도</strong>가 높습니다.
                </p>
                """, unsafe_allow_html=True)
                
                # [2] 전체 시세 (전체 회색 + 최근 1달 파란색 강조)
                st.markdown("<div class='section-title'>📈 전체 시세</div>", unsafe_allow_html=True)
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=dates, y=prices, mode='lines+markers', name='전체 시세',
                    line=dict(color=CHART_GRAY_LINE, width=2, shape='spline', smoothing=0.5),
                    marker=dict(size=6, color=CHART_GRAY_LINE, line=dict(width=0), symbol='circle'),
                    fill='tozeroy', fillcolor=CHART_GRAY_FILL,
                    hovertemplate='<b>%{x}</b><br>%{y:,.1f}만원<extra></extra>'))
                if len(df_1m) >= 2:
                    d1m = df_1m['날짜'].tolist()
                    p1m = df_1m['가격(만원)'].tolist()
                    fig.add_trace(go.Scatter(x=d1m, y=p1m, mode='lines+markers', name='최근 1달',
                        line=dict(color=CHART_ACCENT, width=3.2, shape='spline', smoothing=0.55),
                        marker=dict(size=10, color=CHART_ACCENT_LIGHT, line=dict(width=1, color=CHART_MARKER_LINE)),
                        fill='tozeroy', fillcolor=CHART_ACCENT_HIGHLIGHT,
                        hovertemplate='<b>%{x}</b> (최근 1달)<br>%{y:,.1f}만원<extra></extra>'))
                if global_krw > 0:
                    fig.add_trace(go.Scatter(x=dates, y=[global_krw]*len(dates), mode='lines', name='해외직구',
                        line=dict(color=CHART_DOTTED, width=1.8, dash='dot', shape='spline', smoothing=0.3),
                        hovertemplate=f'해외직구 추산: {global_krw:,.1f}만원<extra></extra>'))
                y_min = max(0, min(prices)*0.92) if prices else 0
                y_max = max(prices)*1.1 if prices else 100
                if y_max - y_min < 10: y_max = y_min + 20
                fig.update_layout(height=280, margin=dict(l=52, r=24, t=12, b=40),
                    title=dict(text=''), annotations=[],
                    hovermode='x unified',
                    hoverlabel=dict(bgcolor=CHART_HOVER_BG, font_size=13, font_color=CHART_HOVER_FONT,
                        bordercolor=CHART_HOVER_BORDER, align='left'),
                    xaxis=dict(showgrid=False, title='', tickfont=dict(size=12, color=CHART_FONT), fixedrange=True),
                    yaxis=dict(title='만원', title_font=dict(size=13, color=CHART_FONT), tickfont=dict(size=12, color=CHART_FONT),
                        showgrid=True, gridcolor=CHART_GRID, zeroline=True, zerolinecolor=CHART_ZEROLINE, range=[y_min, y_max], fixedrange=True),
                    paper_bgcolor=CHART_PAPER, plot_bgcolor=CHART_PLOT, font_color=CHART_FONT,
                    showlegend=True, legend=dict(orientation='h', y=1.05, x=0, xanchor='left', font=dict(size=12), bgcolor=CHART_LEGEND_BG, bordercolor=CHART_LEGEND_BORDER),
                    template=CHART_TEMPLATE, dragmode=False)
                st.plotly_chart(fig, use_container_width=True, config={
                    'displayModeBar': True, 'displaylogo': False, 'scrollZoom': False,
                    'modeBarButtonsToRemove': ['lasso2d', 'select2d']
                }, key="radar_trend_chart")
                
                # [3] 가격 분포
                st.markdown("<div class='section-title'>📊 가격 분포</div>", unsafe_allow_html=True)
                if len(raw) >= 1:
                    n_bins = min(15, max(3, len(raw)//2)) if len(raw) > 1 else 5
                    hist, edges = np.histogram(raw, bins=n_bins)
                    mid = [(edges[i]+edges[i+1])/2 for i in range(len(hist))]
                    fig2 = go.Figure(go.Bar(x=mid, y=hist, marker=dict(
                        color=hist, colorscale=CHART_BAR_SCALE,
                        line=dict(width=0), cornerradius=12, opacity=0.92, cmin=0),
                        hovertemplate='<b>%{x:,.0f}만원대</b><br>%{y}건<extra></extra>'))
                    fig2.update_layout(height=220, margin=dict(l=48, r=24, t=12, b=40), bargap=0.2, bargroupgap=0.05,
                        title=dict(text=''), annotations=[],
                        hovermode='x unified',
                        hoverlabel=dict(bgcolor=CHART_HOVER_BG, font_size=13, font_color=CHART_HOVER_FONT,
                            bordercolor=CHART_HOVER_BORDER, align='left'),
                        xaxis=dict(title='가격(만원)', title_font=dict(size=12), showgrid=False, tickfont=dict(size=11, color=CHART_FONT)),
                        yaxis=dict(title='건수', title_font=dict(size=12), showgrid=True, gridcolor=CHART_GRID, tickfont=dict(size=11, color=CHART_FONT)),
                        paper_bgcolor=CHART_PAPER, plot_bgcolor=CHART_PLOT, font_color=CHART_FONT, showlegend=False, template=CHART_TEMPLATE)
                    st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False}, key="radar_dist_chart")
            
            else:
                if keyword:
                    # 검색했는데 시세 데이터 없음 → 아이폰처럼 동일 레이아웃에 "데이터 없음" 표시
                    st.markdown("<div class='section-title section-title--price-summary'>📊 시세 요약</div>", unsafe_allow_html=True)
                _placeholder_color = CHART_FONT
                st.markdown(f"""
                <div class="metric-grid">
                    <div class="metric-card"><div class="metric-label">평균가</div><div class="metric-value" style="color:{_placeholder_color};">—</div></div>
                    <div class="metric-card"><div class="metric-label">시그널</div><div class="metric-value" style="font-size:0.9rem;"><span style="color:{CHART_ACCENT};">●</span> 없음</div></div>
                    <div class="metric-card"><div class="metric-label">최고가</div><div class="metric-value" style="color:{_placeholder_color};">—</div></div>
                    <div class="metric-card"><div class="metric-label">최저가</div><div class="metric-value" style="color:{_placeholder_color};">—</div></div>
                </div>
                <p class="signal-help" style="margin-top:8px;font-size:0.8rem;color:{SIGNAL_HELP_COLOR};line-height:1.4;">
                    💡 시그널은 수집된 거래 데이터 건수에 비례합니다. ●●●●(강함)일수록 가격분포 데이터가 풍부해 <strong>검색 결과 신뢰도</strong>가 높습니다.
                </p>
                """, unsafe_allow_html=True)
                st.markdown("<div class='section-title'>📈 전체 시세</div>", unsafe_allow_html=True)
                fig_empty = go.Figure()
                fig_empty.update_layout(height=280, margin=dict(l=52, r=24, t=12, b=40), title=dict(text=''),
                    annotations=[dict(text="데이터 없음", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(size=16, color=CHART_FONT))],
                    hovermode='x unified',
                    hoverlabel=dict(bgcolor=CHART_HOVER_BG, font_size=13, font_color=CHART_HOVER_FONT,
                        bordercolor=CHART_HOVER_BORDER, align='left'),
                    xaxis=dict(showgrid=False, title='', tickfont=dict(size=12, color=CHART_FONT), fixedrange=True),
                    yaxis=dict(title='만원', title_font=dict(size=13, color=CHART_FONT), tickfont=dict(size=12, color=CHART_FONT),
                        showgrid=True, gridcolor=CHART_GRID, zeroline=True, zerolinecolor=CHART_ZEROLINE, range=[0, 100], fixedrange=True),
                    paper_bgcolor=CHART_PAPER, plot_bgcolor=CHART_PLOT, font_color=CHART_FONT,
                    showlegend=True, legend=dict(orientation='h', y=1.05, x=0, xanchor='left', font=dict(size=12), bgcolor=CHART_LEGEND_BG, bordercolor=CHART_LEGEND_BORDER),
                    template=CHART_TEMPLATE, dragmode=False)
                st.plotly_chart(fig_empty, use_container_width=True, config={
                    'displayModeBar': True, 'displaylogo': False, 'scrollZoom': False,
                    'modeBarButtonsToRemove': ['lasso2d', 'select2d']
                }, key="radar_empty_trend")
                st.markdown("<div class='section-title'>📊 가격 분포</div>", unsafe_allow_html=True)
                fig_empty2 = go.Figure(go.Bar(x=[], y=[]))
                fig_empty2.update_layout(height=220, margin=dict(l=48, r=24, t=12, b=40), bargap=0.2, bargroupgap=0.05,
                    title=dict(text=''),
                    annotations=[dict(text="데이터 없음", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font=dict(size=16, color=CHART_FONT))],
                    hovermode='x unified',
                    hoverlabel=dict(bgcolor=CHART_HOVER_BG, font_size=13, font_color=CHART_HOVER_FONT,
                        bordercolor=CHART_HOVER_BORDER, align='left'),
                    xaxis=dict(title='가격(만원)', title_font=dict(size=12), showgrid=False, tickfont=dict(size=11, color=CHART_FONT)),
                    yaxis=dict(title='건수', title_font=dict(size=12), showgrid=True, gridcolor=CHART_GRID, tickfont=dict(size=11, color=CHART_FONT)),
                    paper_bgcolor=CHART_PAPER, plot_bgcolor=CHART_PLOT, font_color=CHART_FONT, showlegend=False, template=CHART_TEMPLATE)
                st.plotly_chart(fig_empty2, use_container_width=True, config={'displayModeBar': False}, key="radar_empty_dist")
    else:
        # 메인화면 (검색 전) → 전투기 레이더: 펄스가 닿으면 한번 빛나고 사라짐, 다음 사이클엔 랜덤 다른 위치
        _c1, _c2, _c3 = st.columns([1, 3, 1])
        with _c2:
            _n_blips = 8
            _blip_items = []
            for _ in range(_n_blips):
                a, r = random.uniform(0, 360), random.uniform(12, 35)
                l = 50 + r * math.cos(math.radians(a))
                t = 50 + r * math.sin(math.radians(a))
                pos = f"left:{l:.1f}%;top:{t:.1f}%"
                delay = 2.0 + (r - 12) / 23 * 5.0
                dur = 9.0
                _blip_items.append((pos, delay, dur))
            _blip_html = "".join([f'<div class="sonar-blip" style="{p};animation-delay:{d:.1f}s;animation-duration:{u:.1f}s;"></div>' for p, d, u in _blip_items])
            st.markdown(f"""
            <div class="home-sonar-wrap">
                <div class="sonar-wrap">
                    <div class="sonar-ring"></div>
                    <div class="sonar-ring"></div>
                    <div class="sonar-ring"></div>
                    <div class="sonar-ring"></div>
                    <div class="sonar-ring"></div>
                    <div class="sonar-dot"></div>
                    {_blip_html}
                </div>
                <p class="home-sonar-hint">레이더가 매물을 찾고 있어요</p>
            </div>
            """, unsafe_allow_html=True)

# ==========================================
# 📂 TAB 2: 마켓 소스 (Pro Dashboard Style)
# ==========================================
with tab_source:
    st.markdown("#### 📂 Market Sources")
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
        <a href="https://m.bunjang.co.kr" target="_blank" class="source-card card-bunjang"><div class="source-info"><span class="source-name">번개장터</span><span class="source-desc">중고 거래 플랫폼</span></div></a>
        <a href="https://www.daangn.com" target="_blank" class="source-card card-daangn"><div class="source-info"><span class="source-name">당근마켓</span><span class="source-desc">지역 중고 거래</span></div></a>
        <a href="https://web.joongna.com" target="_blank" class="source-card card-joongna"><div class="source-info"><span class="source-name">중고나라</span><span class="source-desc">국내 최대 종합 장터</span></div></a>
        <a href="https://fruitsfamily.com" target="_blank" class="source-card card-fruits"><div class="source-info"><span class="source-name">Fruits</span><span class="source-desc">중고 거래 플랫폼</span></div></a>
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
    with st.expander("📋 구글 시트 연결 확인 (검색 안 될 때)"):
        _df = load_price_data()
        if _df.empty:
            st.warning("시트 데이터를 불러오지 못했습니다. secrets.toml의 google_sheet_url을 확인하세요.")
        else:
            st.caption(f"행 {len(_df)}개 · 컬럼: {list(_df.columns)}")
            _kw = get_sheet_keywords(_df)
            st.caption(f"검색 가능 키워드 {len(_kw)}개 (일부): {_kw[:15]}")
    t1, t2 = st.columns(2)
    with t1:
        st.markdown("#### 📦 배송 조회")
        carrier = st.selectbox("택배사 선택", ["CJ대한통운", "우체국택배", "한진택배", "롯데택배", "로젠택배", "CU편의점택배", "GS25반값택배"])
        track_no = st.text_input("운송장 번호", placeholder="- 없이 숫자만 입력")
        
        if track_no:
            query = f"{carrier} {track_no}"
            encoded_query = urllib.parse.quote(query)
            st.link_button(f"{carrier} 조회하기 (네이버)", f"https://search.naver.com/search.naver?query={encoded_query}", use_container_width=True)
        else:
            st.info("택배사와 운송장 번호를 입력하세요.")
            
    with t2:
        st.markdown("#### 💱 관세 계산기")
        currency_mode = st.radio("통화 선택", ["USD", "JPY"], horizontal=True)
        if "USD" in currency_mode:
            st.caption(f"적용 환율: {usd:,.1f}원")
            p_u = st.number_input("물품 가격 ($)", 190, step=10)
            krw_val = p_u * usd
            st.markdown(f"### ≈ {krw_val:,.0f} 원")
            if p_u <= 200: st.success("✅ 면세 범위 (안전)")
            else: 
                duty = krw_val * 0.08
                vat = (krw_val + duty) * 0.1
                total_tax = duty + vat
                st.error(f"🚨 과세 대상 (약 {total_tax:,.0f}원 부과 예상)")
                st.caption("ℹ️ 관세 8% + 부가세 10% 기준 (일반 품목)")
        else:
            st.caption(f"적용 환율: {jpy:,.1f}원")
            p_j = st.number_input("물품 가격 (¥)", 15000, step=1000)
            krw_val = p_j * (jpy/100)
            st.markdown(f"### ≈ {krw_val:,.0f} 원")
            if (krw_val/usd) <= 150: st.success("✅ 면세 범위 (안전)")
            else: 
                duty = krw_val * 0.08
                vat = (krw_val + duty) * 0.1
                total_tax = duty + vat
                st.error(f"🚨 과세 대상 (약 {total_tax:,.0f}원 부과 예상)")
                st.caption("ℹ️ 관세 8% + 부가세 10% 기준 (일반 품목)")
        
        st.markdown(f"<span style='font-size:0.8rem; color:{TEXT_SECONDARY};'>⚠️ 품목별 관세율은 달라질 수 있습니다. 정확한 세율은 관세청에서 확인하세요.</span>", unsafe_allow_html=True)

# ==========================================
# 👮‍♂️ TAB 4: 사기 조회 (Ghost Button)
# ==========================================
with tab_safety:
    st.markdown("#### 👮‍♂️ 사기 피해 방지 (The Cheat)")
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
    st.link_button("👮‍♂️ 더치트 무료 조회 바로가기", "https://thecheat.co.kr", type="secondary", use_container_width=True)

# ==========================================
# ⚖️ TAB 5: 2개 상품 비교
# ==========================================
with tab_compare:
    st.markdown("#### ⚖️ 2개 상품 시세 비교")
    comp_col1, comp_col2 = st.columns(2)
    with comp_col1:
        kw1 = st.text_input("상품 A", placeholder="예: 라이카 M6", key="compare_kw1")
    with comp_col2:
        kw2 = st.text_input("상품 B", placeholder="예: 나이키 조던 1", key="compare_kw2")
    
    if kw1 and kw2:
        df_prices = load_price_data()
        m1 = get_trend_data_from_sheet(kw1, df_prices)
        m2 = get_trend_data_from_sheet(kw2, df_prices)
        
        comp_left, comp_right = st.columns(2, gap="large")
        with comp_left:
            st.markdown(f"**{kw1}**")
            if m1:
                avg1 = m1.get('summary_avg', sum(m1['trend_prices'])/len(m1['trend_prices']) if m1['trend_prices'] else 0)
                min1 = m1.get('summary_min', min(m1['raw_prices']) if m1['raw_prices'] else 0)
                max1 = m1.get('summary_max', max(m1['raw_prices']) if m1['raw_prices'] else 0)
                st.metric("평균가", f"{avg1:,.1f}만", None)
                st.metric("최저~최고", f"{min1:,.0f}~{max1:,.0f}만", None)
                fig1 = go.Figure(go.Scatter(x=m1['dates'], y=m1['trend_prices'], mode='lines+markers', name=kw1,
                    line=dict(color=CHART_ACCENT, width=2), fill='tozeroy', fillcolor=CHART_ACCENT_FILL))
                fig1.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor=CHART_PAPER, plot_bgcolor=CHART_PLOT,
                    xaxis=dict(showticklabels=True, tickfont=dict(size=10, color=CHART_FONT)), yaxis=dict(title='만원', title_font=dict(color=CHART_FONT)), template=CHART_TEMPLATE, showlegend=False)
                st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': False}, key="comp_chart1")
            else:
                st.info("데이터 없음")
        with comp_right:
            st.markdown(f"**{kw2}**")
            if m2:
                avg2 = m2.get('summary_avg', sum(m2['trend_prices'])/len(m2['trend_prices']) if m2['trend_prices'] else 0)
                min2 = m2.get('summary_min', min(m2['raw_prices']) if m2['raw_prices'] else 0)
                max2 = m2.get('summary_max', max(m2['raw_prices']) if m2['raw_prices'] else 0)
                st.metric("평균가", f"{avg2:,.1f}만", None)
                st.metric("최저~최고", f"{min2:,.0f}~{max2:,.0f}만", None)
                fig2 = go.Figure(go.Scatter(x=m2['dates'], y=m2['trend_prices'], mode='lines+markers', name=kw2,
                    line=dict(color=CHART_ACCENT, width=2), fill='tozeroy', fillcolor=CHART_ACCENT_FILL))
                fig2.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor=CHART_PAPER, plot_bgcolor=CHART_PLOT,
                    xaxis=dict(showticklabels=True, tickfont=dict(size=10, color=CHART_FONT)), yaxis=dict(title='만원', title_font=dict(color=CHART_FONT)), template=CHART_TEMPLATE, showlegend=False)
                st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False}, key="comp_chart2")
            else:
                st.info("데이터 없음")
        
        if m1 and m2:
            avg1 = sum(m1['trend_prices'])/len(m1['trend_prices'])
            avg2 = sum(m2['trend_prices'])/len(m2['trend_prices'])
            diff = avg1 - avg2
            st.markdown(f"**차이:** {kw1} 평균이 {abs(diff):,.1f}만원 {'더 비쌈' if diff > 0 else '더 쌈'}")
    else:
        st.info("비교할 두 상품을 입력하세요.")

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

