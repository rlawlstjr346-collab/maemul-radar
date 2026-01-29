import streamlit as st
import urllib.parse
import requests
import re
import random
import time
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import html

# ------------------------------------------------------------------
# [1] 앱 기본 설정 (원본 유지)
# ------------------------------------------------------------------
st.set_page_config(
    page_title="매물레이더 Pro",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------------------
# [2] 데이터 관리
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
# [3] 유틸리티 함수 (로직 강화: 쉼표 데이터 쪼개기 추가)
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
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            result = response.json()[0][0][0]
            if result and result.strip(): return result
    except: pass
    return text

def get_trend_data_from_sheet(user_query, df):
    if df.empty or not user_query: return None
    user_clean = user_query.lower().replace(" ", "").strip()
    best_match = None
    min_len_diff = float('inf')
    
    date_cols = ["12월 4주", "1월 1주", "1월 2주", "1월 3주", "1월 4주"]
    
    for index, row in df.iterrows():
        try:
            k_val = row.get('키워드')
            if pd.isna(k_val): continue
            sheet_keyword = str(k_val).lower().replace(" ", "").strip()
            
            if sheet_keyword in user_clean or user_clean in sheet_keyword:
                diff = abs(len(sheet_keyword) - len(user_clean))
                if diff < min_len_diff:
                    min_len_diff = diff
                    n_val = row.get('모델명 (상세스펙/상태)')
                    
                    trend_prices = []
                    valid_dates = []
                    for col in date_cols:
                        if col in df.columns:
                            try:
                                val_s = str(row.get(col, '0')).replace(',', '').strip()
                                if 'E+' not in val_s:
                                    val = float(val_s)
                                    if val > 1:
                                        trend_prices.append(val)
                                        valid_dates.append(col)
                            except: pass
                    
                    # [핵심 수정] 시세 (5주치) 쉼표 데이터 처리
                    raw_str = str(row.get('시세 (5주치)', '')).strip()
                    raw_prices = []
                    if raw_str and 'E+' not in raw_str:
                        try:
                            # 쉼표 분리 후 000 폭탄 제거 및 리스트화
                            raw_prices = [float(p.strip()) for p in raw_str.split(',') if p.strip() and float(p.strip()) > 1]
                        except: pass
                    
                    if not raw_prices: raw_prices = trend_prices

                    best_match = { 
                        "name": n_val, 
                        "dates": valid_dates, 
                        "trend_prices": trend_prices,
                        "raw_prices": raw_prices
                    }
                    if diff == 0: return best_match
        except: continue
    return best_match

def generate_new_data():
    now = datetime.now() + timedelta(hours=9)
    return {'time': now.strftime("%Y-%m-%d %H:%M:%S")}

if 'ticker_data' not in st.session_state:
    st.session_state.ticker_data = generate_new_data()
if 'memo_pad' not in st.session_state:
    st.session_state.memo_pad = ""

# ------------------------------------------------------------------
# [4] CSS 스타일링 (원본 코드 그대로 복사)
# ------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; font-family: 'Pretendard', sans-serif; }
    [data-testid="stSidebar"] { background-color: #17191E; border-right: 1px solid #333; }
    div[data-baseweb="input"] { background-color: #262730; border: 2px solid #00ff88 !important; border-radius: 8px; box-shadow: 0 0 10px rgba(0, 255, 136, 0.15); transition: all 0.3s ease; }
    div[data-baseweb="input"]:focus-within { box-shadow: 0 0 15px rgba(0, 255, 136, 0.5); }
    .stTextInput input, .stTextArea textarea, .stNumberInput input { color: #FAFAFA; font-weight: bold; }
    div[data-testid="stLinkButton"] > a { border-radius: 10px; font-weight: 700; transition: all 0.3s ease; text-decoration: none; }
    
    div[data-testid="stLinkButton"] > a[href*="bunjang"] { border: 1px solid #FF3E3E !important; color: #FF3E3E !important; background-color: rgba(255, 62, 62, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="daangn"] { border: 1px solid #FF8A3D !important; color: #FF8A3D !important; background-color: rgba(255, 138, 61, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="joongna"] { border: 1px solid #00E676 !important; color: #00E676 !important; background-color: rgba(0, 230, 118, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="fruitsfamily"] { border: 1px solid #D500F9 !important; color: #D500F9 !important; background-color: rgba(213, 0, 249, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="ebay"] { border: 1px solid #2962FF !important; color: #2962FF !important; background-color: rgba(41, 98, 255, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="mercari"] { border: 1px solid #EEEEEE !important; color: #EEEEEE !important; background-color: rgba(238, 238, 238, 0.1); }
    
    div[data-testid="stLinkButton"] > a[href*="thecheat"] { 
        border: 2px solid #ff4b4b !important; 
        color: #ffffff !important; 
        background-color: #ff4b4b !important; 
    }
    div[data-testid="stLinkButton"] > a[href*="thecheat"]:hover { 
        background-color: #ff0000 !important; 
        box-shadow: 0 0 10px rgba(255, 0, 0, 0.5) !important;
    }
    
    div[data-testid="stLinkButton"] > a:hover { transform: translateY(-2px); opacity: 0.8; }

    .radar-wrapper { position: relative; display: inline-block; margin-right: 10px; vertical-align: middle; }
    .radar-emoji { position: relative; z-index: 2; font-size: 3rem; }
    .pulse-ring { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 100%; height: 100%; border-radius: 50%; border: 2px solid rgba(255, 255, 255, 0.7); opacity: 0; animation: pulse-ring 2s infinite; }
    @keyframes pulse-ring { 0% { width: 90%; opacity: 1; } 100% { width: 220%; opacity: 0; } }
    .title-text { font-size: 3rem; font-weight: 900; color: #FFFFFF !important; letter-spacing: -1px; }
    
    .community-link { 
        display: flex; align-items: center; padding: 10px; margin-bottom: 8px; 
        background-color: #262730; border-radius: 8px; text-decoration: none !important; 
        color: #eee !important; transition: background-color 0.2s; border: 1px solid #333;
    }
    .community-link:hover { background-color: #33343d; border-color: #555; }
    .comm-icon { font-size: 1.2rem; margin-right: 12px; min-width: 25px; text-align: center; }
    .comm-info { display: flex; flex-direction: column; }
    .comm-name { font-weight: bold; font-size: 0.95rem; }
    .comm-desc { font-size: 0.75rem; color: #aaa; margin-top: 2px; }

    .signal-banner { background: linear-gradient(90deg, #0A84FF 0%, #0055FF 100%); color: white !important; padding: 15px 20px; border-radius: 12px; margin-bottom: 25px; font-weight: bold; font-size: 1rem; display: flex; align-items: center; box-shadow: 0 4px 15px rgba(10, 132, 255, 0.3); }
    .radar-dot-strong { display: inline-block; width: 12px; height: 12px; background-color: white; border-radius: 50%; margin-right: 12px; animation: pulse-strong 1.5s infinite; }
    @keyframes pulse-strong { 0% { box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.7); } 50% { box-shadow: 0 0 0 10px rgba(255, 255, 255, 0); } 100% { box-shadow: 0 0 0 0 rgba(255, 255, 255, 0); } }
    
    .ticker-container { width: 100%; background-color: #15181E; border-bottom: 2px solid #333; margin-bottom: 20px; display: flex; flex-direction: column; }
    .ticker-line { width: 100%; overflow: hidden; white-space: nowrap; padding: 8px 0; border-bottom: 1px solid #222; }
    .ticker-move-1 { display: inline-block; padding-left: 100%; animation: ticker 200s linear infinite; }
    .ticker-move-2 { display: inline-block; padding-left: 100%; animation: ticker 250s linear infinite; }
    .ticker-line span { margin-right: 40px; font-size: 0.9rem; font-family: sans-serif; }
    .label-market { color: #ff4b4b; font-weight: 900; margin-right: 15px !important; }
    .label-radar { color: #00ff88; font-weight: 900; margin-right: 15px !important; }
    @keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-100%, 0, 0); } }
    .legal-footer { font-size: 0.75rem; color: #777; margin-top: 60px; padding: 30px 10px; border-top: 1px solid #333; text-align: center; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [5] 상단 티커 (원본 데이터 유지)
# ------------------------------------------------------------------
market_pool = ["아이폰 17 Pro", "RTX 5090", "갤럭시 S25", "PS5 Pro", "에어팟 맥스 2", "닌텐도 스위치 2", "후지필름 X100VI", "아이패드 M4", "스투시", "아크테릭스"]
radar_pool = ["리코 GR3", "치이카와", "뉴진스 굿즈", "젠틀몬스터", "요시다포터", "살로몬", "코닥 작티", "산리오", "다마고치", "티니핑"]
market_str = "".join([f"<span><span class='rank-num'>{i+1}.</span><span class='item-text'>{item}</span></span>" for i, item in enumerate(random.sample(market_pool, 10))])
radar_str = "".join([f"<span><span class='rank-num'>{i+1}.</span><span class='item-text'>{item}</span></span>" for i, item in enumerate(random.sample(radar_pool, 10))])
now_time = st.session_state.ticker_data['time']

ticker_html = f"""
<div class="ticker-container">
    <div class="ticker-line"><div class="ticker-move-1"><span class="label-market">🔥 Market Hot:</span> {market_str}</div></div>
    <div class="ticker-line" style="border-bottom: none;"><div class="ticker-move-2"><span class="label-radar">📡 Radar Top:</span> {radar_str}</div></div>
</div>
"""
st.markdown(ticker_html, unsafe_allow_html=True)

# ------------------------------------------------------------------
# [6] 사이드바 (원본 100% 복원)
# ------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 레이더 센터")
    with st.expander("👀 커뮤니티 시세비교", expanded=True):
        st.markdown("""
        <a href="http://www.slrclub.com" target="_blank" class="community-link"><div class="comm-icon">📷</div><div class="comm-info"><span class="comm-name">SLR클럽</span><span class="comm-desc">카메라/렌즈 전문</span></div></a>
        <a href="https://coolenjoy.net" target="_blank" class="community-link"><div class="comm-icon">💻</div><div class="comm-info"><span class="comm-name">쿨엔조이</span><span class="comm-desc">PC 하드웨어/부품</span></div></a>
        <a href="https://quasarzone.com" target="_blank" class="community-link"><div class="comm-icon">🔥</div><div class="comm-info"><span class="comm-name">퀘이사존</span><span class="comm-desc">게이밍 기어/PC</span></div></a>
        <a href="https://cafe.naver.com/appleiphone" target="_blank" class="community-link"><div class="comm-icon">🍎</div><div class="comm-info"><span class="comm-name">아사모</span><span class="comm-desc">아이폰/애플 기기</span></div></a>
        """, unsafe_allow_html=True)

    st.write("---")
    with st.expander("📦 배송 조회 레이더", expanded=True):
        track_no = st.text_input("운송장 번호", placeholder="- 없이 숫자만 입력")
        if track_no:
            st.link_button("🔍 택배사 자동 스캔", f"https://search.naver.com/search.naver?query=운송장번호+{track_no}", use_container_width=True)
    
    st.write("---")
    usd, jpy = get_exchange_rates()
    with st.expander("💱 관세 계산기", expanded=True):
        p_u = st.number_input("가격($)", 190)
        krw_val = p_u * usd
        st.markdown(f"**≈ {krw_val:,.0f} 원**")
        if p_u <= 200: st.success("✅ 면세 범위")
        else: st.error(f"🚨 관세 대상")
            
    st.write("---")
    st.link_button("🚨 사기피해 조회 (더치트)", "https://thecheat.co.kr", type="primary", use_container_width=True)

# ------------------------------------------------------------------
# [7] 메인 화면 (디자인 복원)
# ------------------------------------------------------------------
st.markdown("""
    <div style="text-align:center; margin-bottom:20px;">
        <div class="radar-wrapper"><span class="radar-emoji">📡</span><div class="pulse-ring"></div></div>
        <span class="title-text">매물레이더</span>
        <p style="color:#aaa; font-size:1rem; margin-top:5px;">숨어있는 꿀매물을 3단계 심층 스캔합니다.</p>
    </div>
""", unsafe_allow_html=True)

col_left, col_right = st.columns([0.6, 0.4], gap="large")

with col_left:
    st.caption(f"System Live | Last Scan: {now_time}")
    keyword = st.text_input("검색어 입력", placeholder="🔍 상품명을 입력하세요", label_visibility="collapsed")

    if keyword:
        safe_keyword = html.escape(keyword)
        eng_keyword = get_translated_keyword(keyword, 'en')
        st.markdown(f'<div class="signal-banner"><span class="radar-dot-strong"></span><span>\'{safe_keyword}\' 포착! (En: {eng_keyword})</span></div>', unsafe_allow_html=True)

        st.markdown('### 🔥 국내 메이저')
        c1, c2 = st.columns(2)
        c1.link_button("⚡ 번개장터", f"https://m.bunjang.co.kr/search/products?q={urllib.parse.quote(keyword)}", use_container_width=True)
        c2.link_button("🥕 당근마켓", f"https://www.daangn.com/search/{urllib.parse.quote(keyword)}", use_container_width=True)

        st.markdown('### ✈️ 해외 직구')
        c5, c6 = st.columns(2)
        c5.link_button("🇺🇸 eBay", f"https://www.ebay.com/sch/i.html?_nkw={urllib.parse.quote(eng_keyword)}", use_container_width=True)
        c6.link_button("🇯🇵 Mercari", f"https://jp.mercari.com/search?keyword={urllib.parse.quote(keyword)}", use_container_width=True)

with col_right:
    st.markdown("#### 📉 52주 시세 트렌드")
    df_prices = load_price_data()
    matched = get_trend_data_from_sheet(keyword, df_prices)
    
    if matched:
        st.caption(f"✅ '{matched['name']}' 데이터 확인됨")
        df_trend = pd.DataFrame({"날짜": matched["dates"], "가격": matched["trend_prices"]})
        df_dist = pd.DataFrame({"가격": matched["raw_prices"]})

        tab1, tab2 = st.tabs(["📈 시세 흐름", "📊 가격 분포도"])
        with tab1:
            if not df_trend.empty:
                st.line_chart(df_trend, x="날짜", y="가격", color="#00ff88", height=250)
                st.metric("현재 주간 평균", f"{matched['trend_prices'][-1]:,.0f}만")
        with tab2:
            if not df_dist.empty:
                chart = alt.Chart(df_dist).mark_bar(color='#0A84FF', stroke="#111").encode(
                    x=alt.X('가격:Q', bin=alt.Bin(maxbins=15), title='가격 (만원)'),
                    y=alt.Y('count()', title='매물 수'),
                    tooltip=['count()']
                ).properties(height=250).configure_view(strokeWidth=0)
                st.altair_chart(chart, use_container_width=True)
                st.caption(f"📍 평균 거래가: {df_dist['가격'].mean():,.1f}만원")

    st.markdown("#### 💬 스마트 멘트 & 메모")
    tab_m1, tab_m2, tab_memo = st.tabs(["⚡️ 퀵멘트", "💳 결제", "📝 메모"])
    with tab_m1:
        st.code("구매 가능할까요?", language="text")
    with tab_m2:
        st.code("계좌번호 알려주시면 바로 이체하겠습니다.", language="text")
    with tab_memo:
        st.session_state.memo_pad = st.text_area("메모", value=st.session_state.memo_pad, height=100, label_visibility="collapsed")

    st.markdown('<div class="side-util-header">🚨 사기꾼 판독기 (유형별)</div>', unsafe_allow_html=True)
    with st.expander("👮‍♂️ 필수 체크 (클릭해서 확인)", expanded=False):
        st.markdown('**1. 카톡 아이디 거래 유도**')
        st.markdown('"카톡으로 대화해요" → 99.9% 사기입니다. 앱 내 채팅만 이용하세요.')
        st.markdown('**2. 가짜 안전결제 링크**')
        st.markdown('http://... 로 시작하거나 도메인이 다르면 피싱 사이트입니다.')
        st.markdown('**3. 재입금 요구 (수수료 핑계)**')
        st.markdown('"수수료 안 보내서 다시 보내라" → 전형적인 3자 사기/먹튀입니다.')

st.markdown('<div class="legal-footer">본 서비스는 정보 제공 목적으로만 운영되며, 거래의 책임은 각 판매자에게 있습니다.</div>', unsafe_allow_html=True)
