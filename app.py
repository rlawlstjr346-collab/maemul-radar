import streamlit as st
import urllib.parse
import requests
import re
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import html
import random

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
# [2] 데이터 로드
# ------------------------------------------------------------------
sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQS8AftSUmG9Cr7MfczpotB5hhl1DgjH4hRCgXH5R8j5hykRiEf0M9rEyEq3uj312a5RuI4zMdjI5Jr/pub?output=csv"

@st.cache_data(ttl=60)
def load_price_data():
    try:
        df = pd.read_csv(sheet_url)
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

# ------------------------------------------------------------------
# [3] 로직 (키워드 엔진 V2 + 금융)
# ------------------------------------------------------------------
def classify_keyword_category(keyword):
    """
    [Keyword Engine V2] 브랜드/모델명 데이터베이스를 통해 카테고리를 자동 판별
    """
    k = keyword.lower().replace(" ", "")
    
    # === DB: Camera & Gear ===
    cam_db = [
        '카메라', 'camera', '렌즈', 'lens', '필름', 'film', 'dslr', '미러리스',
        '라이카', 'leica', 'm3', 'm6', 'm11', 'q2', 'q3',
        '핫셀블라드', 'hasselblad', '핫셀', '500cm', 'x2d',
        '린호프', 'linhof', '테크니카', 'technika',
        '마미야', 'mamiya', 'rz67', 'rb67',
        '콘탁스', 'contax', 't2', 't3', 'g1', 'g2',
        '브로니카', 'bronica', '젠자',
        '롤라이', 'rollei', '35s', '35t',
        '페이즈원', 'phaseone', 'iq4',
        '리코', 'ricoh', 'gr2', 'gr3', 'gr3x',
        '펜탁스', 'pentax', 'k1000', 'lx', '67',
        '보이그랜더', 'voigtlander', '녹턴', '울트론',
        '캐논', 'canon', '니콘', 'nikon', '소니', 'sony', '후지', 'fujifilm'
    ]
    
    # === DB: Fashion & Style ===
    fashion_db = [
        '나이키', 'nike', '조던', 'jordan', '덩크', 'dunk', '에어포스',
        '아디다스', 'adidas', '이지', 'yeezy', '삼바', '가젤',
        '슈프림', 'supreme', '스투시', 'stussy', '팔라스', 'palace',
        '요지', 'yohji', '야마모토', 'yamamoto', '와이쓰리', 'y-3',
        '꼼데', 'commedesgarcons', '가르송',
        '아크테릭스', 'arcteryx', '베타', '알파',
        '노스페이스', 'northface', '눕시',
        '스톤아일랜드', 'stoneisland', 'cp컴퍼니',
        '뉴발란스', 'newbalance', '992', '993', '990',
        '살로몬', 'salomon', '오클리', 'oakley',
        '젠틀몬스터', 'gentlemonster',
        '구찌', 'gucci', '루이비통', 'louisvuitton', '샤넬', 'chanel', '에르메스', 'hermes',
        '프라다', 'prada', '미우미우', 'miumiu', '보테가', 'bottega',
        '롤렉스', 'rolex', '오메가', 'omega', '까르띠에', 'cartier'
    ]
    
    # === DB: Tech & IT ===
    tech_db = [
        '컴퓨터', 'pc', '데스크탑', '노트북', 'laptop',
        '그래픽', 'vga', 'gpu', 'rtx', 'gtx', '4090', '4080', '4070', '3080',
        'cpu', 'amd', '라이젠', 'ryzen', '인텔', 'intel',
        '아이폰', 'iphone', '15pro', '14pro', '13mini',
        '맥북', 'macbook', '에어', '프로', 'm1', 'm2', 'm3',
        '아이패드', 'ipad', '에어팟', 'airpods', '애플워치', 'applewatch',
        '갤럭시', 'galaxy', 's24', 's23', 'zflip', 'zfold',
        '플스', 'ps5', 'ps4', 'playstation', '닌텐도', 'nintendo', '스위치', 'switch',
        '키보드', 'keyboard', '마우스', 'mouse', '모니터', 'monitor'
    ]

    if any(x in k for x in cam_db):
        return "CAMERA"
    elif any(x in k for x in fashion_db):
        return "FASHION"
    elif any(x in k for x in tech_db):
        return "TECH"
    else:
        return None

def get_related_communities(keyword):
    category = classify_keyword_category(keyword)
    
    if category == "CAMERA":
        return "📷 전문가급 카메라/장비 커뮤니티", [
            ("SLR클럽", "https://www.slrclub.com", "slr"),
            ("라이카 클럽", "http://www.leicaclub.net/", "leica"),
            ("필름카메라 동호회", "https://cafe.naver.com/35mmcamera", "film"),
            ("DOF LOOK", "https://cafe.naver.com/doflook", "dof")
        ]
    elif category == "FASHION":
        return "👟 패션/스니커즈/명품 커뮤니티", [
            ("KREAM", "https://kream.co.kr", "kream"),
            ("나이키매니아", "https://cafe.naver.com/sssw", "nike"),
            ("어미새", "https://eomisae.co.kr", "eomisae"),
            ("디젤매니아", "https://cafe.naver.com/dieselmania", "diesel")
        ]
    elif category == "TECH":
        return "💻 IT/테크/얼리어답터 커뮤니티", [
            ("퀘이사존", "https://quasarzone.com", "quasar"),
            ("쿨엔조이", "https://coolenjoy.net", "cool"),
            ("미코", "https://meeco.kr", "meeco"),
            ("클리앙", "https://www.clien.net", "clien")
        ]
    else:
        return None, None

@st.cache_data(ttl=86400)
def get_exchange_rates():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url, timeout=3)
        data = response.json()
        usd = data['rates']['KRW']
        jpy = (data['rates']['KRW'] / data['rates']['JPY']) * 100
        usd_prev = usd * 0.996 
        jpy_prev = jpy * 1.002 
        
        # [Demo Simulation] 어제 종가를 약간의 랜덤성을 주어 계산 (포트폴리오 시연용)
        usd_prev = usd * (1 + random.uniform(-0.005, 0.005)) 
        jpy_prev = jpy * (1 + random.uniform(-0.005, 0.005)) 
        return usd, jpy, usd_prev, jpy_prev
    except:
        return 1450.0, 950.0, 1440.0, 955.0

def get_translated_keyword(text, target_lang='en'):
    if not re.search('[가-힣]', text): return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ko&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            return response.json()[0][0][0]
    except: pass
    return text

def calculate_total_import_cost(usd_price, rate):
    if usd_price <= 0: return 0
    krw_base = usd_price * rate
    shipping = 30000 
    if usd_price > 200: 
        duty = krw_base * 0.08
        vat = (krw_base + duty) * 0.1
        return (krw_base + duty + vat + shipping) / 10000
    return (krw_base + shipping) / 10000

def get_trend_data_from_sheet(user_query, df):
    if df.empty or not user_query: return None
    user_clean = user_query.lower().replace(" ", "").strip()
    date_cols = ["12월 4주", "1월 1주", "1월 2주", "1월 3주", "1월 4주"]
    for _, row in df.iterrows():
        try:
            k_val = row.get('키워드', row.get('keyword', ''))
            if pd.isna(k_val): continue
            sheet_keyword = str(k_val).lower().replace(" ", "").strip()
            if sheet_keyword in user_clean or user_clean in sheet_keyword:
                trend_prices = []
                valid_dates = []
                for col in date_cols:
                    if col in df.columns:
                        v_raw = str(row.get(col, '0')).strip()
                        v_clean = re.sub(r'[^0-9.]', '', v_raw)
                        if v_clean:
                            try: val = float(v_clean); trend_prices.append(val); valid_dates.append(col) if val > 0 else None
                            except: pass
                raw_str = str(row.get('시세 (5주치)', '')).strip()
                raw_prices = []
                if raw_str and raw_str.lower() != 'nan':
                    for p in raw_str.split(','):
                        clean_p = re.sub(r'[^0-9.]', '', p)
                        if clean_p:
                            try: val = float(clean_p); raw_prices.append(val) if val > 0 else None
                            except: continue
                if not raw_prices: raw_prices = trend_prices
                g_raw = str(row.get('해외평균(USD)', '0')).strip()
                g_clean = re.sub(r'[^0-9.]', '', g_raw)
                global_usd = float(g_clean) if g_clean else 0.0
                if not trend_prices: continue
                return {"name": row.get('모델명 (상세스펙/상태)', '상품명 미상'), "dates": valid_dates, "trend_prices": trend_prices, "raw_prices": raw_prices, "global_usd": global_usd}
        except: continue
    return None

def generate_new_data():
    now = datetime.now() + timedelta(hours=9)
    return {'time': now.strftime("%Y-%m-%d %H:%M:%S")}

if 'ticker_data' not in st.session_state:
    st.session_state.ticker_data = generate_new_data()
if 'memo_pad' not in st.session_state:
    st.session_state.memo_pad = ""

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
    
    /* [Responsive] Centered Container (Max Width 1400px) */
    .block-container {
        max-width: 1400px !important;
        margin: 0 auto !important;
    }
    
    /* 1. Header */
    .header-container { 
        display: flex; align-items: center; justify-content: space-between; 
        margin-bottom: 20px; padding: 12px 30px; gap: 40px;
        background-color: rgba(14, 17, 23, 0.85); /* Glassmorphism */
        backdrop-filter: blur(12px);
        position: sticky; top: 15px; z-index: 999; /* Floating Sticky */
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 24px; /* Rounded Corners */
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .radar-left { display: flex; align-items: center; position: relative; padding-right: 50px; transition: transform 0.3s ease; }
    .radar-left:hover .radar-icon { transform: scale(1.1) rotate(-10deg); }
    .radar-icon { 
        font-size: 2.2rem; margin-right: 10px; z-index: 2; 
        transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
        animation: radar-ping 3s infinite;
    }
    .radar-title { 
        font-size: 2.5rem; font-weight: 900; letter-spacing: -1px; font-style: italic; z-index: 2;
        background: linear-gradient(95deg, #FFFFFF 60%, #888888 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 0 20px rgba(255,255,255,0.1);
    }
    
    @keyframes radar-ping {
        0% { filter: drop-shadow(0 0 2px rgba(0,255,136,0.3)); }
        50% { filter: drop-shadow(0 0 15px rgba(0,255,136,0.8)); }
        100% { filter: drop-shadow(0 0 2px rgba(0,255,136,0.3)); }
    }
    
    .scan-line {
        height: 4px; width: 60px; background: linear-gradient(90deg, transparent, #00FF88, transparent);
        position: absolute; top: 50%; left: 0;
        animation: scan 2s ease-in-out infinite; opacity: 0.8;
        filter: drop-shadow(0 0 5px #00FF88);
    }
    @keyframes scan { 
        0% { left: -20px; opacity: 0; width: 20px; } 
        50% { opacity: 1; width: 80px; } 
        100% { left: 100px; opacity: 0; width: 20px; } 
    }
    
    /* Billboard Style Header */
    .radar-billboard {
        display: grid; grid-template-columns: repeat(6, 1fr); gap: 15px;
        background: rgba(255,255,255,0.03); padding: 10px 20px; border-radius: 12px; border: 1px solid #333;
    }
    
    /* [Responsive] 화면 크기에 따라 빌보드 자동 조절 */
    @media (max-width: 1200px) {
        .radar-billboard { grid-template-columns: repeat(3, 1fr); }
        .c-tech, .c-vibe, .c-living { display: none; } /* 화면이 좁으면 3개만 표시 */
    }
    @media (max-width: 768px) {
        .radar-billboard { display: none; } /* 모바일에서는 숨김 */
    }
    .bill-col { display: flex; flex-direction: column; min-width: 120px; }
    .bill-head { font-size: 0.8rem; color: #888; font-weight: 800; margin-bottom: 8px; letter-spacing: 1px; text-transform: uppercase; border-bottom: 1px solid #444; padding-bottom: 5px; }
    .bill-win { height: 60px; overflow: hidden; position: relative; } /* 2 lines height (30px * 2) */
    .bill-content { display: flex; flex-direction: column; animation: rolling 40s infinite cubic-bezier(0.4, 0, 0.2, 1); }
    .bill-item { height: 30px; line-height: 30px; color: #eee; font-weight: 700; font-family: 'Pretendard', sans-serif; font-size: 1.0rem; letter-spacing: -0.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    
    /* Category Colors */
    .c-trend .bill-item { color: #00E5FF; }
    .c-kicks .bill-item { color: #FF4500; }
    .c-lux .bill-item { color: #FFD700; }
    .c-tech .bill-item { color: #2979FF; }
    .c-vibe .bill-item { color: #00FF88; }
    .c-living .bill-item { color: #E040FB; }
    
    /* Staggered Animation (엇박자) */
    .c-trend .bill-content { animation-delay: 0s; }
    .c-kicks .bill-content { animation-delay: -3s; }
    .c-lux .bill-content { animation-delay: -6s; }
    .c-tech .bill-content { animation-delay: -9s; }
    .c-vibe .bill-content { animation-delay: -12s; }
    .c-living .bill-content { animation-delay: -15s; }
    
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
        100% { transform: translateY(-300px); } /* Seamless Loop Point */
    }

    /* 2. Typewriter Effect */
    .typewriter-text {
        font-family: 'Courier New', monospace; font-size: 0.85rem; color: #00FF88;
        margin-bottom: 5px; display: inline-block; overflow: hidden;
        border-right: .15em solid #00FF88; white-space: nowrap;
        animation: typing 3.5s steps(40, end), blink-caret .75s step-end infinite;
    }
    @keyframes typing { from { width: 0 } to { width: 100% } }
    @keyframes blink-caret { from, to { border-color: transparent } 50% { border-color: #00FF88; } }

    /* 3. Search Bar */
    div[data-baseweb="input"] { background-color: rgba(20, 20, 20, 0.7) !important; border: 1px solid #333 !important; border-radius: 12px; color: white; backdrop-filter: blur(10px); }
    div[data-testid="stVerticalBlock"] > div:nth-child(1) div[data-baseweb="input"] {
        height: 65px; border-radius: 12px; font-size: 1.3rem; border: 1px solid #333 !important; box-shadow: 0 10px 30px rgba(0,0,0,0.5); transition: all 0.3s ease;
    }
    div[data-baseweb="input"]:focus-within { border: 1px solid #00FF88 !important; box-shadow: 0 0 0 1px #00FF88, 0 0 20px rgba(0, 255, 136, 0.3) !important; }

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

    .source-name { font-weight: 800; color: #eee; font-size: 1.05rem; letter-spacing: -0.5px; }
    .source-desc { font-size: 0.8rem; color: #777; font-weight: 400; }
    
    .category-header { font-size: 0.85rem; font-weight: 700; color: #666; margin-top: 20px; margin-bottom: 10px; letter-spacing: 1px; text-transform: uppercase; border-bottom: 1px solid #333; padding-bottom: 5px; }

    /* Ticker */
    .ticker-wrap { position: fixed; bottom: 0; left: 0; width: 100%; height: 32px; background-color: #0E1117; border-top: 1px solid #1C1C1E; z-index: 999; display: flex; align-items: center; }
    .ticker { display: inline-block; white-space: nowrap; padding-left: 100%; animation: ticker 40s linear infinite; }
    .ticker-item { margin-right: 40px; font-size: 0.8rem; color: #888; font-family: 'Inter', sans-serif; font-weight: 500; }
    .ticker-val { color: #eee; font-weight: 700; margin-left: 5px; }
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

    /* [NEW] Metric Cards (Financial Style) */
    .metric-card { 
        background: linear-gradient(90deg, rgba(26,26,26,1) 0%, rgba(26,26,26,0.5) 100%);
        border: 1px solid #333; border-left: 4px solid #00FF88; /* Tech Accent */
        padding: 15px; border-radius: 6px; margin-bottom: 10px; position: relative; 
        transition: all 0.3s ease;
    }
    .metric-card:hover {
        border-color: #555; border-left-color: #00FF88;
        box-shadow: 0 0 25px rgba(0, 255, 136, 0.15); transform: translateX(5px);
    }
    .metric-label { font-size: 0.8rem; color: #888; font-weight: 500; margin-bottom: 5px; }
    .metric-value { font-size: 1.6rem; font-weight: 800; color: #eee; letter-spacing: -1px; }
    .metric-sub { font-size: 0.8rem; color: #666; margin-top: 5px; }
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
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [5] 메인 헤더
# ------------------------------------------------------------------
now_time = st.session_state.ticker_data['time']
usd, jpy, usd_prev, jpy_prev = get_exchange_rates()

# [Billboard Data Pools]
MASTER_TREND = [
    "Leica M6", "Nike Jordan 1", "iPhone 15 Pro", "Rolex Submariner", "Ricoh GR3x", "Arc'teryx Beta", "Sony A7M4", "Stussy Tee", "New Balance 993", "Fujifilm X100VI",
    "RTX 4090", "MacBook Pro M3", "Steam Deck", "HHKB Hybrid", "PlayStation 5", "Hasselblad 500CM", "Contax T3", "Mamiya 7", "Leica Q3", "Nikon Zf",
    "Adidas Samba", "Asics Kayano", "Salomon XT-6", "Supreme Box Logo", "Stone Island", "Yohji Yamamoto", "Miu Miu Bag", "Prada Nylon", "Bottega Veneta", "Acne Studios",
    "Dyson Airstrait", "Omega Speedmaster", "Helinox Chair", "Balmuda Toaster", "Genelec 8010", "Herman Miller", "Rimowa Classic", "Snow Peak", "Brompton P Line", "USM Haller",
    "Galaxy S24 Ultra", "iPad Pro M4", "AirPods Max", "Nintendo Switch 2", "Keychron Q1", "Sony WH-1000XM5", "LG StanbyME", "Apple Watch Ultra", "Bose QC Ultra", "Garmin Fenix"
]

MASTER_VIBE = [
    "Yohji Yamamoto", "Stone Island", "Supreme Box Logo", "Miu Miu Bag", "Salomon XT-6", "Herman Miller", "Rimowa Classic", "Snow Peak", "Brompton P Line", "USM Haller",
    "Comoli Shirt", "Visvim FBT", "Prada Nylon", "Bottega Veneta", "Acne Studios", "Dyson Airstrait", "Omega Speedmaster", "Helinox Chair", "Balmuda Toaster", "Genelec 8010",
    "Human Made", "Kith Box Logo", "Palace Tri-Ferg", "Kapital Bone", "Needles Track", "Engineered Garments", "Auralee Denim", "JJJJound 990", "Aimé Leon Dore", "Clarks Wallabee",
    "Birkenstock Boston", "Porter Tanker", "Freitag Jamie", "Louis Poulsen", "Fritz Hansen", "Vitra Eames", "Artek Stool", "Tekla Fabrics", "Aesop Handwash", "Le Labo Santal"
]

MASTER_SNEAKERS = [
    "Jordan 1 Chicago", "Jordan 1 Mocha", "Jordan 4 Bred", "Jordan 11 Concord", "Nike Dunk Panda", "Nike SB Dunk", "Travis Scott Jordan", "Off-White Nike", "Sacai Vaporwaffle", "Kobe 6 Protro",
    "Adidas Samba OG", "Adidas Gazelle", "Adidas Spezials", "Yeezy 350 V2", "Yeezy Slide", "Yeezy Foam Rnr", "New Balance 992", "New Balance 993", "New Balance 2002R", "New Balance 530",
    "Asics Gel-Kayano", "Asics Gel-1130", "Salomon XT-6", "Salomon ACS Pro", "Hoka One One", "Mihara Yasuhiro", "Rick Owens Ramones", "Balenciaga Triple S", "Balenciaga Track", "Crocs Pollex"
]

MASTER_LUXURY = [
    "Rolex Submariner", "Rolex Daytona", "Rolex Datejust", "Rolex GMT-Master", "Audemars Piguet Royal Oak", "Patek Philippe Nautilus", "Vacheron Constantin", "Omega Speedmaster", "Cartier Tank", "Cartier Santos",
    "Chanel Classic Flap", "Chanel Boy Bag", "Hermes Birkin 30", "Hermes Kelly 28", "Goyard Saint Louis", "Louis Vuitton Speedy", "Dior Saddle Bag", "Celine Triomphe", "Bottega Veneta Cassette", "Prada Re-Edition",
    "Gucci Jackie", "Fendi Baguette", "Saint Laurent Loulou", "Loewe Puzzle", "Miu Miu Wander", "Chrome Hearts Ring", "Van Cleef & Arpels", "Tiffany & Co.", "Bulgari Serpenti", "Rimowa Original"
]

MASTER_TECH = [
    "RTX 4090", "MacBook Pro M3", "Steam Deck", "HHKB Hybrid", "PlayStation 5", "Keychron Q1", "LG StanbyME", "Apple Watch Ultra", "iPad Pro",
    "Nintendo Switch 2", "Galaxy S24", "Garmin Fenix", "iPhone 16 Pro", "Mac Studio", "Studio Display", "Logi MX Master", "NuPhy Air75",
    "Wooting 60HE", "Finalmouse", "Razer Viper", "Fuji GFX100", "Sony A7C2", "Canon R6 Mark II", "Nikon Z8", "DJI Osmo Pocket 3",
    "GoPro Hero 12", "Insta360 Ace Pro", "Drone DJI Mini 4", "Synology NAS", "Unifi Dream Machine", "Raspberry Pi 5", "Arduino Uno", "Flipper Zero", "Analogue Pocket", "Playdate"
]

MASTER_LIVING = [
    "Herman Miller", "Rimowa Classic", "Snow Peak", "Brompton P Line", "USM Haller", "Dyson Airstrait", "Balmuda Toaster", "Helinox Chair", "Fritz Hansen", "Louis Poulsen",
    "Fujifilm Instax", "Super73", "Nespresso Vertuo", "Fellow Ode", "Acaia Pearl", "Hario Switch", "Comandante C40",
    "Moccamaster", "Breville 870", "La Marzocco", "Mazzer Mini", "Weber Key", "Kinto Tumbler", "Stanley Cup", "Yeti Cooler", "Nordisk Tent", "Hilleberg",
    "Helinox Cot", "Brompton T Line", "Moulton", "Birdy", "Strida", "Gubi Multi-Lite", "Anglepoise Lamp", "Dyson V15", "Roborock S8", "LG Styler"
]

# Random Sampling for Billboard (30 items each to keep it fresh but light)
POOL_TREND = random.sample(MASTER_TREND, 15)
POOL_KICKS = random.sample(MASTER_SNEAKERS, 15)
POOL_LUX = random.sample(MASTER_LUXURY, 15)
POOL_TECH = random.sample(MASTER_TECH, 15)
POOL_VIBE = random.sample(MASTER_VIBE, 15)
POOL_LIVING = random.sample(MASTER_LIVING, 15)
# [State Persistence] 빌보드 데이터가 상호작용할 때마다 바뀌지 않도록 세션에 저장
if 'billboard_data' not in st.session_state:
    st.session_state.billboard_data = {
        'TREND': random.sample(MASTER_TREND, 15),
        'KICKS': random.sample(MASTER_SNEAKERS, 15),
        'LUX': random.sample(MASTER_LUXURY, 15),
        'TECH': random.sample(MASTER_TECH, 15),
        'VIBE': random.sample(MASTER_VIBE, 15),
        'LIVING': random.sample(MASTER_LIVING, 15)
    }

def make_bill_html(items):
    # [Seamless Loop Logic] 10개 보여주고, 처음 2개를 뒤에 붙여서 자연스럽게 이어지게 함
    display_items = items[:10] + items[:2]
    return "".join([f'<span class="bill-item">· {item}</span>' for item in display_items])

st.markdown(f"""
    <div class="header-container">
        <a href="/" target="_self" style="text-decoration: none;">
            <div class="radar-left">
                <span class="radar-icon">📡</span>
                <div style="display:flex; flex-direction:column;">
                    <span class="radar-title">RADAR</span>
                    <span style="font-size:0.6rem; color:#00FF88; letter-spacing:2px; margin-top:-5px; font-weight:700;">SYSTEM: ONLINE <span style="animation: blink 1s infinite;">●</span></span>
                </div>
                <div class="scan-line"></div>
            </div>
        </a>
        <div class="radar-billboard">
            <div class="bill-col c-trend">
                <div class="bill-head">🔥 TRENDING</div>
                <div class="bill-win"><div class="bill-content">{make_bill_html(POOL_TREND)}</div></div>
                <div class="bill-win"><div class="bill-content">{make_bill_html(st.session_state.billboard_data['TREND'])}</div></div>
            </div>
            <div class="bill-col c-kicks">
                <div class="bill-head">👟 SNEAKERS</div>
                <div class="bill-win"><div class="bill-content">{make_bill_html(POOL_KICKS)}</div></div>
                <div class="bill-win"><div class="bill-content">{make_bill_html(st.session_state.billboard_data['KICKS'])}</div></div>
            </div>
            <div class="bill-col c-lux">
                <div class="bill-head">💎 LUXURY</div>
                <div class="bill-win"><div class="bill-content">{make_bill_html(POOL_LUX)}</div></div>
                <div class="bill-win"><div class="bill-content">{make_bill_html(st.session_state.billboard_data['LUX'])}</div></div>
            </div>
            <div class="bill-col c-tech">
                <div class="bill-head">💻 TECH</div>
                <div class="bill-win"><div class="bill-content">{make_bill_html(POOL_TECH)}</div></div>
                <div class="bill-win"><div class="bill-content">{make_bill_html(st.session_state.billboard_data['TECH'])}</div></div>
            </div>
            <div class="bill-col c-vibe">
                <div class="bill-head">🌊 VIBE</div>
                <div class="bill-win"><div class="bill-content">{make_bill_html(POOL_VIBE)}</div></div>
                <div class="bill-win"><div class="bill-content">{make_bill_html(st.session_state.billboard_data['VIBE'])}</div></div>
            </div>
            <div class="bill-col c-living">
                <div class="bill-head">🏠 LIVING</div>
                <div class="bill-win"><div class="bill-content">{make_bill_html(POOL_LIVING)}</div></div>
                <div class="bill-win"><div class="bill-content">{make_bill_html(st.session_state.billboard_data['LIVING'])}</div></div>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [6] 메인 네비게이션
# ------------------------------------------------------------------
tab_home, tab_source, tab_tools, tab_safety = st.tabs(["🏠 시세 분석", "📂 Market Sources", "🧰 도구", "👮‍♂️ 사기 조회"])

# ==========================================
# 🏠 TAB 1: 홈
# ==========================================
with tab_home:
    col_left, col_right = st.columns([0.6, 0.4], gap="large")

    with col_left:
        st.markdown('<div class="typewriter-text">System Ready... Waiting for input_</div>', unsafe_allow_html=True)

        if 'search_input' not in st.session_state: st.session_state.search_input = ""

        keyword = st.text_input("검색", placeholder="모델명 입력 (예: 라이카 M6, 나이키 조던)", label_visibility="collapsed", key="search_input")

        if keyword:
            eng_keyword = get_translated_keyword(keyword, 'en')
            jp_keyword = get_translated_keyword(keyword, 'ja')
            encoded_kor = urllib.parse.quote(keyword)
            encoded_eng = urllib.parse.quote(eng_keyword)
            encoded_jp = urllib.parse.quote(jp_keyword)
            
            st.markdown(f"<div style='margin-top:20px; font-size:1.3rem; font-weight:700; color:#eee;'>'{html.escape(keyword)}' 분석 결과</div>", unsafe_allow_html=True)

            # [Fruits Name Fixed]
            st.markdown("<div class='capsule-title' style='border-left: 3px solid #FF6F00;'>🇰🇷 국내 마켓 <span class='capsule-sub'>Direct Access</span></div>", unsafe_allow_html=True)
            d1, d2 = st.columns(2)
            d1.link_button("⚡ 번개장터", f"https://m.bunjang.co.kr/search/products?q={encoded_kor}", use_container_width=True)
            d2.link_button("🥕 당근마켓", f"https://www.daangn.com/search/{encoded_kor}", use_container_width=True)
            d3, d4 = st.columns(2)
            d3.link_button("🟢 중고나라", f"https://web.joongna.com/search?keyword={encoded_kor}", use_container_width=True)
            d4.link_button("🟣 Fruits", f"https://fruitsfamily.com/search/{encoded_kor}", use_container_width=True)

            st.markdown("<div class='capsule-title' style='border-left: 3px solid #0055ff;'>🌎 해외 직구 <span class='capsule-sub'>Global Shipping</span></div>", unsafe_allow_html=True)
            g1, g2 = st.columns(2)
            g1.link_button(f"🔵 eBay ({eng_keyword})", f"https://www.ebay.com/sch/i.html?_nkw={encoded_eng}", use_container_width=True)
            g2.link_button(f"⚪ Mercari ({jp_keyword})", f"https://jp.mercari.com/search?keyword={encoded_jp}", use_container_width=True)
            
            # [SMART CURATION V2]
            curation_title, curation_list = get_related_communities(keyword)
            if curation_list:
                st.markdown(f"<div style='margin-top:30px; margin-bottom:10px; color:#00FF88; font-weight:700;'>💡 {curation_title}</div>", unsafe_allow_html=True)
                cur_cols = st.columns(2)
                for idx, (name, url, tag) in enumerate(curation_list):
                    col = cur_cols[idx % 2]
                    # 스마트 큐레이션은 심플한 카드로 표시 (여기서는 태그 스타일 미적용)
                    col.markdown(f"""
                    <a href="{url}" target="_blank" class="source-card card-{tag}">
                        <div class="source-info"><span class="source-name">{name}</span></div>
                        <span style="font-size:1.2rem;">🔗</span>
                    </a>
                    """, unsafe_allow_html=True)

    with col_right:
        st.markdown("#### 📊 데이터 요약 (Sheet)")
        df_prices = load_price_data()
        matched = get_trend_data_from_sheet(keyword, df_prices)
        
        if matched:
            global_krw = calculate_total_import_cost(matched['global_usd'], usd)
            kr_avg = sum(matched['trend_prices'])/len(matched['trend_prices']) if matched['trend_prices'] else 0
            
            m1, m2 = st.columns(2)
            with m1: st.markdown(f"<div class='metric-card'><div class='metric-label'>📉 시트 평균가</div><div class='metric-value'>{kr_avg:,.1f}만</div></div>", unsafe_allow_html=True)
            with m2:
                gap = kr_avg - global_krw
                diff_text = f"Gap: +{gap:,.1f}만 (이득)" if gap > 0 else f"Gap: {gap:,.1f}만 (손해)"
                sub_class = "ticker-up" if (kr_avg - global_krw) > 0 else "ticker-down"
                if global_krw <= 0: diff_text = "데이터 없음"; sub_class = "metric-sub"
                st.markdown(f"<div class='metric-card'><div class='metric-label'>🌎 직구 추산가 (관세포함)</div><div class='metric-value'>{global_krw:,.1f}만</div><div class='{sub_class}'>{diff_text}</div></div>", unsafe_allow_html=True)
            
            st.write("")
            tab_trend, tab_dist = st.tabs(["📈 시세 추이", "📊 매물 분포"])
            with tab_trend:
                chart_df = pd.DataFrame({"날짜": matched["dates"], "국내": matched["trend_prices"], "해외직구": [global_krw] * len(matched["dates"])})
                base = alt.Chart(chart_df).encode(x=alt.X('날짜:N', sort=None))
                area = base.mark_area(opacity=0.3, color='#00FF88').encode(y=alt.Y('국내:Q', title=None))
                line = base.mark_line(color='#00FF88', size=3).encode(y=alt.Y('국내:Q', title=None))
                charts = area + line
                if global_krw > 0: charts += base.mark_line(color='#666', strokeDash=[5,5]).encode(y='해외직구:Q')
                st.altair_chart(charts.properties(height=250), use_container_width=True)
            with tab_dist:
                dist_df = pd.DataFrame({"가격": matched["raw_prices"]})
                dist_chart = alt.Chart(dist_df).mark_bar(color='#333').encode(x=alt.X('가격:Q', bin=alt.Bin(maxbins=15)), y=alt.Y('count()', axis=alt.Axis(tickMinStep=1, format='d'))).properties(height=250)
                st.altair_chart(dist_chart, use_container_width=True)
        else:
            dummy_df = pd.DataFrame({'x': range(5), 'y': [10, 12, 11, 13, 12]})
            dummy_chart = alt.Chart(dummy_df).mark_line(color='#222', strokeDash=[5,5]).encode(x=alt.X('x', axis=None), y=alt.Y('y', axis=None)).properties(height=250, title="데이터 대기중")
            st.altair_chart(dummy_chart, use_container_width=True)

        st.markdown("#### ⚡ 스마트 트레이더")
        tab_m1, tab_m2, tab_memo = st.tabs(["💬 멘트", "💳 결제", "📝 메모"])
        with tab_m1:
            quick_opt = st.radio("유형", ["👋 구매 인사", "💸 가격 제안"], label_visibility="collapsed")
            if "인사" in quick_opt: st.code("안녕하세요! 게시글 보고 연락드립니다. 구매 가능할까요?", language="text")
            else:
                nego_price = st.text_input("희망 가격", placeholder="숫자만 입력")
                fmt_price = f"{int(nego_price):,}" if nego_price else "[   ]"
                st.code(f"안녕하세요. 혹시 실례지만 {fmt_price}원에 가격조정 가능할지 여쭤보고 싶습니다. 가능하시다면 바로 구매가능합니다.", language="text")
        with tab_m2:
            pay_opt = st.radio("방식", ["계좌", "직거래"], horizontal=True, label_visibility="collapsed")
            if pay_opt == "계좌": st.code("계좌결제로 하겠습니다. 계좌 부탁드립니다.", language="text")
            else: st.code("직거래로 가능하신지 여쭤봅니다.", language="text")
        with tab_memo: st.session_state.memo_pad = st.text_area("메모장", value=st.session_state.memo_pad, height=100)

# ==========================================
# 📂 TAB 2: 마켓 소스 (Pro Dashboard Style)
# ==========================================
with tab_source:
    st.markdown("#### 📂 Market Sources")
    col_left, col_right = st.columns(2)
    
    # Left Column
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
        <a href="https://cafe.naver.com/35mmcamera" target="_blank" class="source-card card-film"><div class="source-info"><span class="source-name">필름카메라 동호회</span><span class="source-desc">빈티지 필름 감성</span></div></a>
        <a href="https://cafe.naver.com/doflook" target="_blank" class="source-card card-dof"><div class="source-info"><span class="source-name">DOF LOOK</span><span class="source-desc">전문 촬영 장비</span></div></a>
        """, unsafe_allow_html=True)

    # Right Column
    with col_right:
        st.markdown("""
        <div class='category-header'>👟 Fashion & Style</div>
        <a href="https://kream.co.kr" target="_blank" class="source-card card-kream"><div class="source-info"><span class="source-name">KREAM</span><span class="source-desc">한정판 거래 플랫폼</span></div></a>
        <a href="https://cafe.naver.com/sssw" target="_blank" class="source-card card-nike"><div class="source-info"><span class="source-name">나이키매니아</span><span class="source-desc">스니커즈/스트릿</span></div></a>
        <a href="https://eomisae.co.kr" target="_blank" class="source-card card-eomisae"><div class="source-info"><span class="source-name">어미새</span><span class="source-desc">글로벌 세일 정보</span></div></a>
        <a href="https://cafe.naver.com/dieselmania" target="_blank" class="source-card card-diesel"><div class="source-info"><span class="source-name">디젤매니아</span><span class="source-desc">남성 패션 커뮤니티</span></div></a>
        
        <div class='category-header'>🍎 Apple & Life</div>
        <a href="https://cafe.naver.com/appleiphone" target="_blank" class="source-card card-asamo"><div class="source-info"><span class="source-name">아사모</span><span class="source-desc">아이폰/아이패드 사용자</span></div></a>
        <a href="https://cafe.naver.com/inmacbook" target="_blank" class="source-card card-mac"><div class="source-info"><span class="source-name">맥쓰사</span><span class="source-desc">맥북/맥 사용자 모임</span></div></a>
        <a href="https://web.joongna.com" target="_blank" class="source-card card-joongna"><div class="source-info"><span class="source-name">중고나라</span><span class="source-desc">국내 최대 종합 장터</span></div></a>
        <a href="https://bbs.ruliweb.com/market" target="_blank" class="source-card card-ruli"><div class="source-info"><span class="source-name">루리웹</span><span class="source-desc">게임/피규어/취미</span></div></a>
        """, unsafe_allow_html=True)

# ==========================================
# 🧰 TAB 3: 도구
# ==========================================
with tab_tools:
    t1, t2 = st.columns(2)
    with t1:
        st.markdown("#### 📦 배송 조회")
        carrier = st.selectbox("택배사 선택", ["CJ대한통운", "우체국택배", "한진택배", "롯데택배", "로젠택배", "CU편의점택배", "GS25반값택배"])
        track_no = st.text_input("운송장 번호", placeholder="- 없이 숫자만 입력")
        
        if track_no:
            query = f"{carrier} {track_no}"
            encoded_query = urllib.parse.quote(query)
            st.link_button(f"{carrier} 조회하기 (네이버)", f"https://search.naver.com/search.naver?query={encoded_query}", use_container_width=True)
            st.link_button(f"{carrier} 조회하기", f"https://search.naver.com/search.naver?query={encoded_query}", use_container_width=True)
        else:
            st.info("택배사와 운송장 번호를 입력하세요.")
            
    with t2:
        st.markdown("#### 💱 관세 계산기")
        currency_mode = st.radio("통화 선택", ["🇺🇸 USD", "🇯🇵 JPY"], horizontal=True)
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
        
        st.markdown("<span style='font-size:0.8rem; color:#888;'>⚠️ 품목별 관세율은 달라질 수 있습니다. 정확한 세율은 관세청에서 확인하세요.</span>", unsafe_allow_html=True)

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

st.markdown('<div class="legal-footer">© 2026 RADAR | Global Price Intelligence</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------
# [8] 하단 고정 티커 (유지)
# ------------------------------------------------------------------
diff_usd = usd - usd_prev
diff_jpy = jpy - jpy_prev

sign_usd = "🔺" if diff_usd >= 0 else "🔻"
class_usd = "ticker-up" if diff_usd >= 0 else "ticker-down"
usd_text = f"{usd:,.0f}원 <span class='{class_usd}'>{sign_usd} {abs(diff_usd):.1f}</span>"

sign_jpy = "🔺" if diff_jpy >= 0 else "▼"
class_jpy = "ticker-up" if diff_jpy >= 0 else "ticker-down"
jpy_text = f"{jpy:,.0f}원 <span class='{class_jpy}'>{sign_jpy} {abs(diff_jpy):.1f}</span>"

us_limit_krw = usd * 200

jp_limit_jpy = 150 * (usd / (jpy / 100))
jp_limit_krw = usd * 150

# [Ticker Insight]
if diff_jpy < -5.0:
    insight_msg = f"📉 엔화 하락세 (▼{abs(diff_jpy):.1f}원)"
    insight_color = "#00E5FF"
elif diff_usd > 5.0:
    insight_msg = f"🚨 달러 상승세 (▲{diff_usd:.1f}원)"
    insight_color = "#ff4b4b"
else:
    insight_msg = "🌤️ 환율 안정세"
    insight_color = "#ddd"

ticker_content = f"""
<div class="ticker-wrap">
    <div class="ticker">
        <span class="ticker-item">USD/KRW <span class="ticker-val">{usd_text}</span></span>
        <span class="ticker-item">JPY/KRW <span class="ticker-val">{jpy_text}</span></span>
        <span class="ticker-item">미국면세 한도 <span class="ticker-val">$200 (약 {us_limit_krw/10000:.0f}만원)</span></span>
        <span class="ticker-item">일본면세 한도 <span class="ticker-val">¥{jp_limit_jpy:,.0f} (약 {jp_limit_krw/10000:.0f}만원)</span></span>
        <span class="ticker-item"><span class="ticker-val" style="color:{insight_color};">{insight_msg}</span></span>
        <span class="ticker-item">SYSTEM <span class="ticker-val" style="color:#00ff88">ONLINE 🟢</span></span>
    </div>
</div>
"""
st.markdown(ticker_content, unsafe_allow_html=True)

# ------------------------------------------------------------------
# [9] 사이드바 (포트폴리오 설명용)
# ------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 📡 RADAR System")
    st.markdown("<div style='font-size: 0.8rem; color: #888; margin-bottom: 20px;'>Global Price Intelligence Dashboard</div>", unsafe_allow_html=True)
    
    st.info("""
    **ℹ️ Project Overview**
    
    이 대시보드는 **한정판 리셀 시장**의 국가별 시세 불균형(Arbitrage)을 포착하기 위해 개발되었습니다.
    
    - **Data:** Google Sheets (Backend)
    - **Logic:** Real-time FX & Duty Calc
    - **Tech:** Python, Streamlit
    """)
    
    st.markdown("---")
    st.caption("Designed for KREAM Portfolio")
