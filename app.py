import streamlit as st
import urllib.parse
import requests
import re
import random
import pandas as pd
import altair as alt
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# [1] 앱 기본 설정
# ------------------------------------------------------------------
st.set_page_config(
    page_title="매물레이더 Pro",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
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
# [3] 로직 (방탄 파싱 + 글로벌 계산)
# ------------------------------------------------------------------
@st.cache_data(ttl=3600)
def get_exchange_rates():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url, timeout=3)
        data = response.json()
        usd = data['rates']['KRW']
        jpy = (data['rates']['KRW'] / data['rates']['JPY']) * 100
        return usd, jpy
    except:
        return 1400.0, 930.0

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
                            try:
                                v_val = float(v_clean)
                                if v_val > 0: 
                                    trend_prices.append(v_val)
                                    valid_dates.append(col)
                            except: pass
                
                raw_str = str(row.get('시세 (5주치)', '')).strip()
                raw_prices = []
                if raw_str and raw_str.lower() != 'nan':
                    for p in raw_str.split(','):
                        clean_p = re.sub(r'[^0-9.]', '', p)
                        if clean_p:
                            try:
                                val = float(clean_p)
                                if val > 0: raw_prices.append(val)
                            except: continue
                if not raw_prices: raw_prices = trend_prices

                g_raw = str(row.get('해외평균(USD)', '0')).strip()
                g_clean = re.sub(r'[^0-9.]', '', g_raw)
                global_usd = float(g_clean) if g_clean else 0.0

                if not trend_prices: continue

                return {
                    "name": row.get('모델명 (상세스펙/상태)', '상품명 미상'),
                    "dates": valid_dates,
                    "trend_prices": trend_prices,
                    "raw_prices": raw_prices,
                    "global_usd": global_usd
                }
        except: continue
    return None

if 'memo_pad' not in st.session_state:
    st.session_state.memo_pad = ""

# ------------------------------------------------------------------
# [4] 스타일링 (애니메이션, 버튼 컬러, 다크 모드)
# ------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; font-family: 'Pretendard', sans-serif; }
    [data-testid="stSidebar"] { background-color: #17191E; border-right: 1px solid #333; }
    div[data-baseweb="input"] { background-color: #262730; border: 2px solid #00ff88 !important; border-radius: 8px; }
    
    /* 레이더 펄스 애니메이션 복구 */
    .radar-wrapper { position: relative; display: inline-block; margin-right: 10px; vertical-align: middle; }
    .radar-emoji { position: relative; z-index: 2; font-size: 3rem; }
    .pulse-ring { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 100%; height: 100%; border-radius: 50%; border: 2px solid rgba(0, 255, 136, 0.7); opacity: 0; animation: pulse-ring 2s infinite; }
    @keyframes pulse-ring { 0% { width: 90%; opacity: 1; } 100% { width: 220%; opacity: 0; } }
    .title-text { font-size: 3rem; font-weight: 900; color: #FFFFFF !important; letter-spacing: -1px; }

    /* 바로가기 버튼 컬러 복구 */
    div[data-testid="stLinkButton"] > a { border-radius: 10px; font-weight: 700; transition: all 0.3s ease; text-decoration: none; }
    div[data-testid="stLinkButton"] > a[href*="bunjang"] { border: 1px solid #FF3E3E !important; color: #FF3E3E !important; background-color: rgba(255, 62, 62, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="daangn"] { border: 1px solid #FF8A3D !important; color: #FF8A3D !important; background-color: rgba(255, 138, 61, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="ebay"] { border: 1px solid #2962FF !important; color: #2962FF !important; background-color: rgba(41, 98, 255, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="thecheat"] { border: 2px solid #ff4b4b !important; color: #ffffff !important; background-color: #ff4b4b !important; }

    /* 티커 애니메이션 */
    .ticker-container { width: 100%; background-color: #15181E; border-bottom: 2px solid #333; margin-bottom: 20px; overflow: hidden; white-space: nowrap; }
    .ticker-move { display: inline-block; padding-left: 100%; animation: ticker 100s linear infinite; }
    @keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-100%, 0, 0); } }

    /* Metric Card (KREAM Style) */
    .metric-card { background-color: #1E1E1E; border: 1px solid #333; border-radius: 12px; padding: 20px; text-align: center; }
    .metric-value { font-size: 1.5rem; font-weight: 800; color: #fff; }
    .metric-sub { font-size: 0.8rem; color: #00ff88; margin-top: 5px; }
    .metric-sub-bad { font-size: 0.8rem; color: #ff4b4b; margin-top: 5px; }
    
    .community-link { display: flex; align-items: center; padding: 10px; margin-bottom: 8px; background-color: #262730; border-radius: 8px; text-decoration: none !important; color: #eee !important; border: 1px solid #333; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [5] 메인 레이아웃 (애니메이션 타이틀 + 티커)
# ------------------------------------------------------------------
market_items = ["아이폰 17 Pro", "RTX 5090", "갤럭시 S25", "PS5 Pro", "에어팟 맥스 2", "닌텐도 스위치 2", "지슈라 2", "라이카 Q3"]
ticker_str = " | ".join([f"🔥 Hot: {item}" for item in market_items])

st.markdown(f"""
<div style="text-align:center; margin-bottom:20px;">
    <div class="radar-wrapper"><span class="radar-emoji">📡</span><div class="pulse-ring"></div></div>
    <span class="title-text">매물레이더 Pro</span>
</div>
<div class="ticker-container"><div class="ticker-move">{ticker_str}</div></div>
""", unsafe_allow_html=True)

usd_rate, jpy_rate = get_exchange_rates()

# ------------------------------------------------------------------
# [6] 사이드바 (커뮤니티 + 배송조회 복구)
# ------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 레이더 센터")
    with st.expander("👀 커뮤니티 시세비교", expanded=True):
        st.markdown('<a href="http://www.slrclub.com" target="_blank" class="community-link">📷 SLR클럽</a>', unsafe_allow_html=True)
        st.markdown('<a href="https://coolenjoy.net" target="_blank" class="community-link">💻 쿨엔조이</a>', unsafe_allow_html=True)
        st.markdown('<a href="https://quasarzone.com" target="_blank" class="community-link">🔥 퀘이사존</a>', unsafe_allow_html=True)
        st.markdown('<a href="https://cafe.naver.com/appleiphone" target="_blank" class="community-link">🍎 아사모</a>', unsafe_allow_html=True)
    
    st.write("---")
    with st.expander("📦 배송 조회", expanded=True):
        track_no = st.text_input("운송장 번호", placeholder="- 없이 숫자만")
        if track_no: st.link_button("🔍 택배사 자동 스캔", f"https://search.naver.com/search.naver?query=운송장번호+{track_no}", use_container_width=True)

    st.write("---")
    st.info(f"💱 실시간 환율\n- USD: {usd_rate:,.1f}원\n- JPY: {jpy_rate:,.1f}원")
    st.link_button("🚨 사기피해 조회 (더치트)", "https://thecheat.co.kr", type="primary", use_container_width=True)

# ------------------------------------------------------------------
# [7] 메인 콘텐츠
# ------------------------------------------------------------------
col_main, col_sub = st.columns([0.6, 0.4], gap="large")

with col_main:
    keyword = st.text_input("검색어 입력", placeholder="🔍 상품명을 입력하세요 (예: 지슈라 2, 아이폰 15)", label_visibility="collapsed")
    if keyword:
        eng_keyword = get_translated_keyword(keyword, 'en')
        st.caption(f"검색어: {keyword} (Global: {eng_keyword})")
        
        btn_cols = st.columns(3)
        btn_cols[0].link_button("⚡ 번개장터", f"https://m.bunjang.co.kr/search/products?q={keyword}", use_container_width=True)
        btn_cols[1].link_button("🥕 당근마켓", f"https://www.daangn.com/search/{keyword}", use_container_width=True)
        btn_cols[2].link_button("📦 eBay(직구)", f"https://www.ebay.com/sch/i.html?_nkw={eng_keyword}", use_container_width=True)

with col_sub:
    df_raw = load_price_data()
    matched = get_trend_data_from_sheet(keyword, df_raw)
    
    if matched:
        st.markdown(f"#### 📉 {matched['name']} 분석")
        
        # 1. KREAM Style 메트릭
        global_krw = calculate_total_import_cost(matched['global_usd'], usd_rate)
        kr_avg = sum(matched['trend_prices'])/len(matched['trend_prices']) if matched['trend_prices'] else 0
        
        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f"<div class='metric-card'><div>🇰🇷 국내 중고</div><div class='metric-value'>{kr_avg:,.1f}만</div></div>", unsafe_allow_html=True)
        with m2:
            diff_text = f"직구 {kr_avg - global_krw:,.1f}만 이득" if (kr_avg - global_krw) > 0 else "국내 구매 추천"
            sub_class = "metric-sub" if (kr_avg - global_krw) > 0 else "metric-sub-bad"
            if global_krw <= 0: diff_text = "해외 데이터 없음"
            st.markdown(f"<div class='metric-card'><div>🌎 직구 실구매</div><div class='metric-value'>{global_krw:,.1f}만</div><div class='{sub_class}'>{diff_text}</div></div>", unsafe_allow_html=True)

        st.write("") 

        # 2. 그래프 영역
        t_flow, t_dist = st.tabs(["📈 통합 시세", "📊 매물 분포"])
        with t_flow:
            chart_df = pd.DataFrame({"주차": matched["dates"], "국내": matched["trend_prices"], "해외직구": [global_krw] * len(matched["dates"])})
            base = alt.Chart(chart_df).encode(x=alt.X('주차:N', sort=None))
            charts = base.mark_line(color='#00ff88', size=3).encode(y=alt.Y('국내:Q', title='가격(만원)'))
            if global_krw > 0:
                charts += base.mark_line(color='#ff4b4b', strokeDash=[5,5]).encode(y='해외직구:Q')
            st.altair_chart(charts.properties(height=250), use_container_width=True)

        with t_dist:
            dist_df = pd.DataFrame({"가격": matched["raw_prices"]})
            dist_chart = alt.Chart(dist_df).mark_bar(color='#0A84FF').encode(x=alt.X('가격:Q', bin=alt.Bin(maxbins=12)), y='count()').properties(height=250)
            st.altair_chart(dist_chart, use_container_width=True)

        # 3. [복구 완료] 스마트 멘트 & 메모장
        st.markdown("#### 💬 스마트 메모")
        tab_m1, tab_m2, tab_memo = st.tabs(["⚡️ 퀵멘트", "💳 결제", "📝 메모"])
        with tab_m1: st.code("네고 가능한가요? 바로 쿨거래 하겠습니다.", language="text")
        with tab_m2: st.code("계좌번호 주시면 입금하고 주소 남기겠습니다.", language="text")
        with tab_memo: st.session_state.memo_pad = st.text_area("가격 기록용", value=st.session_state.memo_pad, height=100)

    elif keyword:
        st.warning("📡 데이터 분석 중... (시트에 없는 모델입니다)")

st.markdown('<div style="text-align:center; color:#444; margin-top:60px;">© 2026 매물레이더 Pro | Global Price Intelligence</div>', unsafe_allow_html=True)
