import streamlit as st
import urllib.parse
import requests
import re
import random
import time
import pandas as pd
from datetime import datetime, timedelta
import html

# ------------------------------------------------------------------
# [1] 앱 기본 설정 (Wide Mode)
# ------------------------------------------------------------------
st.set_page_config(
    page_title="매물레이더 Pro",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------------------
# [2] 데이터 관리 (구글 스프레드시트 연동)
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
# [3] 유틸리티 함수 (검색 로직 강화)
# ------------------------------------------------------------------
@st.cache_data(ttl=3600)
def get_exchange_rates():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url, timeout=3)
        data = response.json()
        return data['rates']['KRW'], (data['rates']['KRW'] / data['rates']['JPY']) * 100
    except:
        return 1450.0, 950.0

def get_translated_keyword(text, target_lang='en'):
    if not re.search('[가-힣]', text): return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ko&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
        response = requests.get(url, timeout=1)
        if response.status_code == 200: return response.json()[0][0][0]
    except: pass
    return text

def get_trend_data_from_sheet(user_query, df):
    if df.empty or not user_query: return None
    user_clean = user_query.lower().replace(" ", "").strip()
    for index, row in df.iterrows():
        try:
            sheet_keyword = str(row['keyword']).lower().replace(" ", "").strip()
            if sheet_keyword in user_clean or user_clean in sheet_keyword:
                return {
                    "name": row['name'],
                    "dates": str(row['dates']).split(','),
                    "prices": [float(p) for p in str(row['prices']).split(',')]
                }
        except:
            continue
    return None

def generate_new_data():
    now = datetime.now() + timedelta(hours=9)
    return {'time': now.strftime("%Y-%m-%d %H:%M:%S")}

if 'ticker_data' not in st.session_state:
    st.session_state.ticker_data = generate_new_data()
if 'memo_pad' not in st.session_state:
    st.session_state.memo_pad = ""

# ------------------------------------------------------------------
# [4] CSS 스타일링 (절대 유지)
# ------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; font-family: 'Pretendard', sans-serif; }
    [data-testid="stSidebar"] { background-color: #17191E; border-right: 1px solid #333; }
    
    div[data-baseweb="input"] {
        background-color: #262730; border: 2px solid #00ff88 !important; border-radius: 8px; 
        box-shadow: 0 0 10px rgba(0, 255, 136, 0.15); transition: all 0.3s ease;
    }
    div[data-baseweb="input"]:focus-within { box-shadow: 0 0 15px rgba(0, 255, 136, 0.5); }
    .stTextInput input, .stTextArea textarea, .stNumberInput input { color: #FAFAFA; font-weight: bold; }

    div[data-testid="stLinkButton"] > a { border-radius: 10px; font-weight: 700; transition: all 0.3s ease; text-decoration: none; }
    div[data-testid="stLinkButton"] > a[href*="bunjang"] { border: 1px solid #FF3E3E !important; color: #FF3E3E !important; background-color: rgba(255, 62, 62, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="bunjang"]:hover { background-color: #FF3E3E !important; color: white !important; }
    div[data-testid="stLinkButton"] > a[href*="daangn"] { border: 1px solid #FF8A3D !important; color: #FF8A3D !important; background-color: rgba(255, 138, 61, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="daangn"]:hover { background-color: #FF8A3D !important; color: white !important; }
    div[data-testid="stLinkButton"] > a[href*="joongna"] { border: 1px solid #00E676 !important; color: #00E676 !important; background-color: rgba(0, 230, 118, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="joongna"]:hover { background-color: #00E676 !important; color: black !important; }
    
    div[data-testid="stLinkButton"] > a[href*="fruitsfamily"] { border: 1px solid #D500F9 !important; color: #D500F9 !important; background-color: rgba(213, 0, 249, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="fruitsfamily"]:hover { background-color: #D500F9 !important; color: white !important; }
    
    div[data-testid="stLinkButton"] > a[href*="ebay"] { border: 1px solid #2962FF !important; color: #2962FF !important; background-color: rgba(41, 98, 255, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="ebay"]:hover { background-color: #2962FF !important; color: white !important; }
    div[data-testid="stLinkButton"] > a[href*="mercari"] { border: 1px solid #EEEEEE !important; color: #EEEEEE !important; background-color: rgba(238, 238, 238, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="mercari"]:hover { background-color: #EEEEEE !important; color: #000000 !important; }
    div[data-testid="stLinkButton"] > a[href*="thecheat"] { border: 1px solid #ff4b4b !important; color: #ff4b4b !important; background-color: rgba(255, 75, 75, 0.1) !important; }
    div[data-testid="stLinkButton"] > a[href*="thecheat"]:hover { background-color: #ff4b4b !important; color: white !important; }

    .radar-wrapper { position: relative; display: inline-block; margin-right: 10px; vertical-align: middle; }
    .radar-emoji { position: relative; z-index: 2; font-size: 3rem; }
    .pulse-ring { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 100%; height: 100%; border-radius: 50%; border: 2px solid rgba(255, 255, 255, 0.7); opacity: 0; animation: pulse-ring 2s infinite; }
    @keyframes pulse-ring { 0% { width: 90%; opacity: 1; } 100% { width: 220%; opacity: 0; } }
    .title-text { font-size: 3rem; font-weight: 900; color: #FFFFFF !important; letter-spacing: -1px; }

    .side-util-header { font-size: 1rem; font-weight: bold; color: #0A84FF; margin-top: 5px; margin-bottom: 5px; border-left: 3px solid #0A84FF; padding-left: 8px; }
    .signal-banner { background: linear-gradient(90deg, #0A84FF 0%, #0055FF 100%); color: white !important; padding: 15px 20px; border-radius: 12px; margin-bottom: 25px; font-weight: bold; font-size: 1rem; display: flex; align-items: center; box-shadow: 0 4px 15px rgba(10, 132, 255, 0.3); }
    .radar-dot-strong { display: inline-block; width: 12px; height: 12px; background-color: white; border-radius: 50%; margin-right: 12px; animation: pulse-strong 1.5s infinite; }
    .radar-dot-idle { display: inline-block; width: 12px; height: 12px; background-color: #34c759; border-radius: 50%; margin-right: 8px; vertical-align: middle; animation: pulse-idle 2s infinite; }

    .ticker-container { width: 100%; background-color: #15181E; border-bottom: 2px solid #333; margin-bottom: 20px; display: flex; flex-direction: column; }
    .ticker-line { width: 100%; overflow: hidden; white-space: nowrap; padding: 8px 0; border-bottom: 1px solid #222; }
    .ticker-move-1 { display: inline-block; padding-left: 100%; animation: ticker 200s linear infinite; }
    .ticker-move-2 { display: inline-block; padding-left: 100%; animation: ticker 250s linear infinite; }
    @keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-100%, 0, 0); } }

    /* 푸터 스타일 절대 유지 */
    .legal-footer { font-size: 0.75rem; color: #777; margin-top: 60px; padding: 30px 10px; border-top: 1px solid #333; text-align: center; line-height: 1.6; }
    .scam-alert-text { color: #ff4b4b; font-weight: bold; font-size: 0.85rem; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [5] 상단 티커 (절대 유지)
# ------------------------------------------------------------------
market_pool = ["아이폰 15 Pro", "갤럭시 S24 울트라", "에어팟 맥스", "닌텐도 스위치", "소니 헤드폰", "PS5", "맥북프로 M3", "RTX 4070", "아이패드 에어", "스투시 후드", "나이키 덩크"]
radar_pool = ["후지필름 X100V", "리코 GR3", "치이카와", "뉴진스 포카", "젠틀몬스터", "요시다포터", "살로몬 XT-6", "코닥 작티", "산리오 키링", "다마고치", "티니핑"]

market_str = "".join([f"<span><span style='color:#ff4b4b; font-weight:900;'>{i+1}.</span> {item}</span>" for i, item in enumerate(random.sample(market_pool, 10))])
radar_str = "".join([f"<span><span style='color:#00ff88; font-weight:900;'>{i+1}.</span> {item}</span>" for i, item in enumerate(random.sample(radar_pool, 10))])

ticker_html = f"""
<div class="ticker-container">
    <div class="ticker-line">
        <div class="ticker-move-1">🔥 Market Hot: {market_str} 🔥 Market Hot: {market_str}</div>
    </div>
    <div class="ticker-line" style="border-bottom: none;">
        <div class="ticker-move-2">📡 Radar Top: {radar_str} 📡 Radar Top: {radar_str}</div>
    </div>
</div>
"""
st.markdown(ticker_html, unsafe_allow_html=True)

# ------------------------------------------------------------------
# [6] 사이드바 (절대 유지)
# ------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 레이더 센터")
    with st.expander("👀 커뮤니티 시세비교", expanded=True):
        st.markdown("- [📷 SLR클럽](http://www.slrclub.com)\n- [💻 쿨엔조이](https://coolenjoy.net)\n- [🔥 퀘이사존](https://quasarzone.com)\n- [🍎 아사모](https://cafe.naver.com/appleiphone)")
    
    track_no = st.text_input("운송장 번호", placeholder="- 없이 숫자만 입력")
    if track_no:
        st.link_button("🔍 택배사 자동 스캔", f"https://search.naver.com/search.naver?query=운송장번호+{track_no}", use_container_width=True)

    usd_rate, jpy_rate = get_exchange_rates()
    with st.expander("💱 관세 계산기", expanded=True):
        p_usd = st.number_input("가격($)", value=190)
        st.write(f"🇰🇷 약 {p_usd * usd_rate:,.0f} 원")

    st.link_button("🚨 사기피해 조회 (더치트)", "https://thecheat.co.kr", type="primary", use_container_width=True)

# ------------------------------------------------------------------
# [7] 메인 화면 (절대 유지)
# ------------------------------------------------------------------
st.markdown("""
    <div style="text-align:center; margin-bottom:20px;">
        <div class="radar-wrapper"><span class="radar-emoji">📡</span><div class="pulse-ring"></div></div>
        <span class="title-text">매물레이더</span>
    </div>
""", unsafe_allow_html=True)

col_left, col_right = st.columns([0.6, 0.4], gap="large")

with col_left:
    keyword = st.text_input("검색어 입력", placeholder="🔍 찾으시는 물건을 입력하세요", label_visibility="collapsed")
    if keyword:
        safe_keyword = html.escape(keyword)
        st.markdown(f'<div class="signal-banner"><span class="radar-dot-strong"></span>\'{safe_keyword}\' 포착!</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.link_button("⚡ 번개장터", f"https://m.bunjang.co.kr/search/products?q={urllib.parse.quote(keyword)}", use_container_width=True)
        c2.link_button("🥕 당근마켓", f"https://www.daangn.com/search/{urllib.parse.quote(keyword)}", use_container_width=True)
        
        c3, c4 = st.columns(2)
        c3.link_button("🌵 중고나라", f"https://web.joongna.com/search?keyword={urllib.parse.quote(keyword)}", use_container_width=True)
        c4.link_button("🍇 후르츠 (패션)", f"https://fruitsfamily.com/search/{urllib.parse.quote(keyword)}", use_container_width=True)

with col_right:
    st.markdown("#### 📉 52주 시세 트렌드")
    df_prices = load_price_data()
    matched_data = get_trend_data_from_sheet(keyword, df_prices)
    if matched_data:
        df_trend = pd.DataFrame({"날짜": matched_data["dates"], "가격(만원)": matched_data["prices"]})
        st.line_chart(df_trend, x="날짜", y="가격(만원)", color="#00ff88", height=200)
    else:
        st.info("검색어를 입력하면 시세 그래프가 나타납니다.")

# ------------------------------------------------------------------
# [8] 하단 푸터 및 저작권 (사장님 요청 반영: 반투명 & 중앙 하단)
# ------------------------------------------------------------------
st.markdown("""<br><br><br><br>""", unsafe_allow_html=True)
st.markdown(f"""
    <div style="text-align:center; padding:30px; border-top:1px solid #333; color:rgba(250,250,250,0.4); font-size:0.8rem; line-height:1.8;">
        본 서비스는 온라인 중고 거래 사이트의 정보를 검색하여 링크를 제공하는 서비스입니다.<br>
        모든 거래의 책임은 판매자에게 있으며, 안전한 거래를 위해 반드시 '안전결제'를 이용하시기 바랍니다.<br>
        <p style="font-weight:bold; color:rgba(0, 255, 136, 0.5); font-size:0.9rem; margin-top:15px;">
            Copyright © 2026 매물레이더(MaeMulRadar). All Rights Reserved.
        </p>
        <p style="font-size:0.65rem; opacity:0.6;">데이터 및 디자인 무단 복제·재배포 금지</p>
    </div>
""", unsafe_allow_html=True)
