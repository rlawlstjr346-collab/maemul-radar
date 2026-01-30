import streamlit as st
import urllib.parse
import requests
import re
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import html

# ------------------------------------------------------------------
# [1] 앱 기본 설정 (RADAR V7.0 / Ghost Sidebar)
# ------------------------------------------------------------------
st.set_page_config(
    page_title="RADAR",
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
# [3] 로직 (금융 로직 티커 포함)
# ------------------------------------------------------------------
@st.cache_data(ttl=3600)
def get_exchange_rates():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url, timeout=3)
        data = response.json()
        usd = data['rates']['KRW']
        jpy = (data['rates']['KRW'] / data['rates']['JPY']) * 100
        
        # [NEW] 전일 종가 시뮬레이션 (등락폭 표시용 로직)
        # 실제 API에는 전일 데이터가 없으므로 미세한 차이를 두어 변동성 구현
        usd_prev = usd * 0.996 # 가정: 어제보다 0.4% 오름
        jpy_prev = jpy * 1.002 # 가정: 어제보다 0.2% 내림
        
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

def generate_new_data():
    now = datetime.now() + timedelta(hours=9)
    return {'time': now.strftime("%Y-%m-%d %H:%M:%S")}

if 'ticker_data' not in st.session_state:
    st.session_state.ticker_data = generate_new_data()
if 'memo_pad' not in st.session_state:
    st.session_state.memo_pad = ""

# ------------------------------------------------------------------
# [4] CSS 스타일링 (Ghost Sidebar & New Ticker)
# ------------------------------------------------------------------
st.markdown("""
<style>
    /* 1. Base Theme (Ghost Mode: 사이드바 배경색 통일) */
    .stApp { background-color: #0E1117; color: #E0E0E0; font-family: 'Pretendard', sans-serif; }
    
    /* 사이드바 경계선 제거 및 배경 통일 */
    [data-testid="stSidebar"] { 
        background-color: #0E1117; 
        border-right: none; 
    }
    
    div[data-baseweb="input"] { background-color: #1E1E1E !important; border: 1px solid #333 !important; border-radius: 8px; color: white; }
    div[data-baseweb="input"]:focus-within { border: 1px solid #888 !important; }

    /* 2. 사이드바 토글 버튼 (Segment Control 스타일) */
    div[data-testid="stRadio"] > div {
        display: flex;
        justify-content: space-between;
        background-color: #1A1A1A;
        padding: 5px;
        border-radius: 12px;
        margin-bottom: 20px;
    }
    div[data-testid="stRadio"] label {
        flex: 1;
        text-align: center;
        background-color: transparent;
        color: #888;
        border-radius: 8px;
        padding: 8px 0;
        cursor: pointer;
        transition: 0.3s;
        font-weight: bold;
        font-size: 0.9rem;
    }
    div[data-testid="stRadio"] label[data-checked="true"] {
        background-color: #333;
        color: #fff;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }

    /* 3. 플랫폼 버튼 (색상 및 스타일 복구) */
    div[data-testid="stLinkButton"] > a { border-radius: 8px; font-weight: 700; transition: all 0.2s ease; text-decoration: none; border: 1px solid #333; }
    
    /* 번개장터 (Red) */
    div[data-testid="stLinkButton"] > a[href*="bunjang"] { background-color: rgba(255, 62, 62, 0.15) !important; color: #FF6B6B !important; border-color: #FF3E3E !important; }
    /* 당근마켓 (Orange) */
    div[data-testid="stLinkButton"] > a[href*="daangn"] { background-color: rgba(255, 138, 61, 0.15) !important; color: #FF9F60 !important; border-color: #FF8A3D !important; }
    /* 중고나라 (Green) */
    div[data-testid="stLinkButton"] > a[href*="joongna"] { background-color: rgba(0, 230, 118, 0.15) !important; color: #69F0AE !important; border-color: #00E676 !important; }
    /* Fruits (Purple) */
    div[data-testid="stLinkButton"] > a[href*="fruits"] { background-color: rgba(213, 0, 249, 0.15) !important; color: #EA80FC !important; border-color: #D500F9 !important; }
    /* eBay (Blue) */
    div[data-testid="stLinkButton"] > a[href*="ebay"] { background-color: rgba(41, 98, 255, 0.15) !important; color: #448AFF !important; border-color: #2962FF !important; }
    /* Mercari (White/Grey) - 복구 완료 */
    div[data-testid="stLinkButton"] > a[href*="mercari"] { background-color: rgba(255, 255, 255, 0.1) !important; color: #FFFFFF !important; border-color: #999 !important; }
    /* TheCheat (Police Blue) - 복구 완료 */
    div[data-testid="stLinkButton"] > a[href*="thecheat"] { background-color: #1E3A8A !important; color: #ffffff !important; border: 1px solid #3B82F6 !important; }

    /* 4. 커뮤니티 링크 (SLR 세로 배치 유지) */
    .community-link { 
        display: flex; 
        align-items: center; 
        padding: 12px; 
        margin-bottom: 8px; 
        background-color: #161920; /* 메인보다 살짝 밝게 */
        border-radius: 8px; 
        text-decoration: none !important; 
        color: #ddd !important; 
        border: 1px solid #222; 
    }
    .comm-icon { font-size: 1.5rem; margin-right: 15px; width: 30px; text-align: center; flex-shrink: 0; }
    .comm-info { width: 100%; display: flex; flex-direction: column; }
    .comm-name { display: block; font-weight: bold; font-size: 0.95rem; color: #fff; margin-bottom: 2px; }
    .comm-desc { display: block; font-size: 0.75rem; color: #888; }

    /* 5. Ticker (금융 로직 스타일) */
    .ticker-wrap { position: fixed; bottom: 0; left: 0; width: 100%; height: 36px; background-color: #0E1117; border-top: 1px solid #333; z-index: 999; display: flex; align-items: center; }
    .ticker { display: inline-block; white-space: nowrap; padding-left: 100%; animation: ticker 40s linear infinite; }
    .ticker-item { margin-right: 50px; font-size: 0.9rem; font-weight: 500; color: #AAA; font-family: 'Roboto Mono', monospace; }
    .ticker-val { color: #fff; font-weight: bold; margin-left: 5px; }
    .ticker-up { color: #ff4b4b; font-size: 0.8rem; margin-left: 5px; } /* 상승 */
    .ticker-down { color: #4b89ff; font-size: 0.8rem; margin-left: 5px; } /* 하락 */
    @keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-100%, 0, 0); } }

    /* 레이더 펄스 */
    .radar-wrapper { position: relative; display: inline-block; margin-right: 10px; vertical-align: middle; }
    .radar-emoji { position: relative; z-index: 2; font-size: 3rem; }
    .pulse-ring { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 100%; height: 100%; border-radius: 50%; border: 2px solid rgba(255, 255, 255, 0.2); opacity: 0; animation: pulse-ring 2s infinite; }
    @keyframes pulse-ring { 0% { width: 90%; opacity: 1; } 100% { width: 220%; opacity: 0; } }
    
    /* Scam Box */
    .scam-box { border-left: 3px solid #ff4b4b; background-color: #1A0505; padding: 12px; margin-bottom: 8px; color: #ccc; font-size: 0.85rem; }
    .scam-title { color: #ff4b4b; font-weight: bold; display: block; margin-bottom: 3px; }

    /* Metric & Titles */
    .metric-card { background-color: #161920; border: 1px solid #333; border-radius: 0px; padding: 20px; text-align: center; margin-bottom: 10px; }
    .metric-label { font-size: 0.8rem; color: #666; font-weight: bold; }
    .metric-value { font-size: 1.6rem; font-weight: 800; color: #fff; margin: 5px 0; }
    .metric-sub { font-size: 0.8rem; color: #00ff88; }
    .metric-sub-bad { font-size: 0.8rem; color: #ff4b4b; }
    
    .section-title { font-size: 1.1rem; font-weight: bold; color: #ddd; margin-bottom: 10px; margin-top: 20px; border-left: 3px solid #00ff88; padding-left: 10px; }
    .radar-title { font-size: 3rem; font-weight: 900; color: #FFFFFF; letter-spacing: -2px; margin-bottom: 0px; }
    .radar-subtitle { font-size: 1rem; color: #666; font-weight: 400; margin-top: 5px; }
    .legal-footer { font-size: 0.7rem; color: #444; margin-top: 80px; text-align: center; margin-bottom: 50px; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [5] 메인 헤더
# ------------------------------------------------------------------
now_time = st.session_state.ticker_data['time']
usd, jpy, usd_prev, jpy_prev = get_exchange_rates()

st.markdown("""
    <div style="text-align:center; margin-bottom:40px; margin-top: 20px;">
        <div class="radar-wrapper"><span class="radar-emoji">📡</span><div class="pulse-ring"></div></div>
        <div class="radar-title">RADAR</div>
        <div class="radar-subtitle">글로벌 시세 차익 분석 솔루션</div>
    </div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [6] 사이드바 (Ghost Sidebar + Toggle)
# ------------------------------------------------------------------
with st.sidebar:
    # 토글 스위치 (Segment Control)
    menu_selection = st.radio("MENU", ["탐색", "도구", "안심"], horizontal=True, label_visibility="collapsed")
    
    st.write("---") # 구분선 최소화

    # 1. 탐색 모드
    if menu_selection == "탐색":
        st.markdown("<div style='color:#666; font-size:0.8rem; margin-bottom:10px;'>COMMUNITY</div>", unsafe_allow_html=True)
        st.markdown("""
        <a href="http://www.slrclub.com" target="_blank" class="community-link">
            <div class="comm-icon">📷</div>
            <div class="comm-info"><span class="comm-name">SLR클럽</span><span class="comm-desc">카메라 전문</span></div>
        </a>
        <a href="https://coolenjoy.net" target="_blank" class="community-link">
            <div class="comm-icon">💻</div>
            <div class="comm-info"><span class="comm-name">쿨엔조이</span><span class="comm-desc">PC 하드웨어</span></div>
        </a>
        <a href="https://quasarzone.com" target="_blank" class="community-link">
            <div class="comm-icon">🔥</div>
            <div class="comm-info"><span class="comm-name">퀘이사존</span><span class="comm-desc">게이밍 기어</span></div>
        </a>
        <a href="https://cafe.naver.com/appleiphone" target="_blank" class="community-link">
            <div class="comm-icon">🍎</div>
            <div class="comm-info"><span class="comm-name">아사모</span><span class="comm-desc">애플 기기</span></div>
        </a>
        """, unsafe_allow_html=True)

    # 2. 도구 모드 (즉시 입력)
    elif menu_selection == "도구":
        st.markdown("<div style='color:#666; font-size:0.8rem; margin-bottom:10px;'>UTILITIES</div>", unsafe_allow_html=True)
        tool_mode = st.radio("기능 선택", ["배송조회", "관세계산"], label_visibility="collapsed")
        
        if tool_mode == "배송조회":
            track_no = st.text_input("운송장 번호", placeholder="숫자만 입력")
            if track_no:
                st.link_button("조회하기", f"https://search.naver.com/search.naver?query=운송장번호+{track_no}", use_container_width=True)
            else:
                c1, c2 = st.columns(2)
                c1.link_button("GS반값", "https://www.cvsnet.co.kr/reservation-tracking/tracking/index.do", use_container_width=True)
                c2.link_button("CU알뜰", "https://www.cupost.co.kr/postbox/delivery/local.cupost", use_container_width=True)
        
        else: # 관세계산
            currency_mode = st.radio("통화", ["USD (미국)", "JPY (일본)"], horizontal=True, label_visibility="collapsed")
            if "USD" in currency_mode:
                st.caption(f"기준 환율: {usd:,.1f}원")
                p_u = st.number_input("물품가격 ($)", 190, step=10)
                krw_val = p_u * usd
                st.markdown(f"**≈ {krw_val:,.0f} 원**")
                if p_u <= 200: st.success("✅ 안전 (면세 범위)")
                else: 
                    duty = krw_val * 0.188
                    st.error(f"🚨 과세 대상")
                    st.caption(f"예상 세금: 약 {duty:,.0f}원 (18.8%)")
            else:
                st.caption(f"기준 환율: {jpy:,.1f}원")
                p_j = st.number_input("물품가격 (¥)", 15000, step=1000)
                krw_val = p_j * (jpy/100)
                st.markdown(f"**≈ {krw_val:,.0f} 원**")
                if (krw_val/usd) <= 150: st.success("✅ 안전 (면세 범위)")
                else: 
                    duty = krw_val * 0.188
                    st.error(f"🚨 과세 대상")
                    st.caption(f"예상 세금: 약 {duty:,.0f}원 (18.8%)")

    # 3. 안심 모드
    elif menu_selection == "안심":
        st.markdown("<div style='color:#666; font-size:0.8rem; margin-bottom:10px;'>SAFETY</div>", unsafe_allow_html=True)
        st.markdown("""
        <div class="scam-box"><span class="scam-title">🚫 카톡 유도</span>ID 추가 유도는 99% 사기</div>
        <div class="scam-box"><span class="scam-title">🚫 가짜 결제창</span>URL 도메인 확인 필수</div>
        """, unsafe_allow_html=True)
        st.link_button("더치트 조회하기", "https://thecheat.co.kr", type="primary", use_container_width=True)

# ------------------------------------------------------------------
# [7] 메인 콘텐츠
# ------------------------------------------------------------------
col_left, col_right = st.columns([0.6, 0.4], gap="large")

with col_left:
    st.caption(f"System Ready | {now_time}")
    keyword = st.text_input("검색", placeholder="상품명 입력 (예: 아이폰 15)", label_visibility="collapsed")

    if keyword:
        eng_keyword = get_translated_keyword(keyword, 'en')
        jp_keyword = get_translated_keyword(keyword, 'ja')
        
        safe_keyword = html.escape(keyword)
        encoded_kor = urllib.parse.quote(keyword)
        encoded_eng = urllib.parse.quote(eng_keyword)
        encoded_jp = urllib.parse.quote(jp_keyword)
        
        st.markdown(f"<div style='margin: 20px 0; font-size: 1.4rem; font-weight: bold;'>'{safe_keyword}' 분석 결과</div>", unsafe_allow_html=True)

        st.markdown("<div class='section-title'>🇰🇷 국내 마켓 (통합)</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.link_button("⚡ 번개장터", f"https://m.bunjang.co.kr/search/products?q={encoded_kor}", use_container_width=True)
        c2.link_button("🥕 당근마켓", f"https://www.daangn.com/search/{encoded_kor}", use_container_width=True)
        
        c3, c4 = st.columns(2)
        c3.link_button("🟢 중고나라", f"https://web.joongna.com/search?keyword={encoded_kor}", use_container_width=True)
        c4.link_button("🟣 FRUITS", f"https://fruitsfamily.com/search/{encoded_kor}", use_container_width=True)

        st.markdown("<div class='section-title'>🌎 해외 직구 (자동 번역)</div>", unsafe_allow_html=True)
        c5, c6 = st.columns(2)
        c5.link_button(f"🔵 eBay ({eng_keyword})", f"https://www.ebay.com/sch/i.html?_nkw={encoded_eng}", use_container_width=True)
        c6.link_button(f"⚪ Mercari ({jp_keyword})", f"https://jp.mercari.com/search?keyword={encoded_jp}", use_container_width=True)

    else:
        st.info("상품명을 입력하면 3단계 심층 스캔을 시작합니다.")

with col_right:
    st.markdown("#### 52주 시세 트렌드")
    df_prices = load_price_data()
    matched = get_trend_data_from_sheet(keyword, df_prices)
    
    if matched:
        global_krw = calculate_total_import_cost(matched['global_usd'], usd)
        kr_avg = sum(matched['trend_prices'])/len(matched['trend_prices']) if matched['trend_prices'] else 0
        
        m1, m2 = st.columns(2)
        with m1:
             st.markdown(f"<div class='metric-card'><div class='metric-label'>국내 중고 평균</div><div class='metric-value'>{kr_avg:,.1f}만</div></div>", unsafe_allow_html=True)
        with m2:
            diff_text = f"직구 {kr_avg - global_krw:,.1f}만 이득" if (kr_avg - global_krw) > 0 else "국내 구매 유리"
            sub_class = "metric-sub" if (kr_avg - global_krw) > 0 else "metric-sub-bad"
            if global_krw <= 0: 
                diff_text = "정보 없음"
                sub_class = "metric-sub"
            st.markdown(f"<div class='metric-card'><div class='metric-label'>해외 직구 (관세포함)</div><div class='metric-value'>{global_krw:,.1f}만</div><div class='{sub_class}'>{diff_text}</div></div>", unsafe_allow_html=True)
        
        st.write("")

        tab_trend, tab_dist = st.tabs(["시세 흐름", "가격 분포"])
        with tab_trend:
            chart_df = pd.DataFrame({"날짜": matched["dates"], "국내": matched["trend_prices"], "해외직구": [global_krw] * len(matched["dates"])})
            base = alt.Chart(chart_df).encode(x=alt.X('날짜:N', sort=None))
            charts = base.mark_line(color='#ffffff', size=2).encode(y=alt.Y('국내:Q', title=None))
            if global_krw > 0:
                charts += base.mark_line(color='#666', strokeDash=[5,5]).encode(y='해외직구:Q')
            st.altair_chart(charts.properties(height=250), use_container_width=True)
        
        with tab_dist:
             dist_df = pd.DataFrame({"가격": matched["raw_prices"]})
             dist_chart = alt.Chart(dist_df).mark_bar(color='#444').encode(
                 x=alt.X('가격:Q', bin=alt.Bin(maxbins=15)), 
                 y=alt.Y('count()', axis=alt.Axis(tickMinStep=1, format='d'))
             ).properties(height=250)
             st.altair_chart(dist_chart, use_container_width=True)

    else:
        dummy_df = pd.DataFrame({'x': range(5), 'y': [10, 12, 11, 13, 12]})
        dummy_chart = alt.Chart(dummy_df).mark_line(color='#333', strokeDash=[5,5]).encode(
            x=alt.X('x', axis=None), y=alt.Y('y', axis=None)
        ).properties(height=250, title="데이터 대기중")
        st.altair_chart(dummy_chart, use_container_width=True)

    # 스마트 트레이더
    st.markdown("#### 스마트 트레이더")
    tab_m1, tab_m2, tab_memo = st.tabs(["💬 멘트", "💳 결제", "📝 메모"])
    
    with tab_m1:
        quick_opt = st.radio("유형", ["문의", "네고"], label_visibility="collapsed")
        if quick_opt == "문의": 
            st.code("안녕하세요! 게시글 보고 연락드립니다. 구매 가능할까요?", language="text")
        else:
            nego_price = st.text_input("희망 가격", placeholder="숫자만 입력")
            if nego_price:
                try: fmt_price = f"{int(nego_price):,}"
                except: fmt_price = nego_price
                st.code(f"안녕하세요. 혹시 실례지만 {fmt_price}원에 가격조정 가능할지 여쭤보고 싶습니다. 가능하시다면 바로 구매가능합니다.", language="text")
            else:
                st.code("안녕하세요. 혹시 실례지만 [   ]원에 가격조정 가능할지 여쭤보고 싶습니다. 가능하시다면 바로 구매가능합니다.", language="text")

    with tab_m2:
            pay_opt = st.radio("방식", ["계좌", "직거래"], horizontal=True, label_visibility="collapsed")
            if pay_opt == "계좌": st.code("계좌결제로 하겠습니다. 계좌 부탁드립니다.", language="text")
            else: st.code("직거래로 가능하신지 여쭤봅니다.", language="text")
                
    with tab_memo:
        st.session_state.memo_pad = st.text_area("메모장", value=st.session_state.memo_pad, height=100)

st.markdown('<div class="legal-footer">© 2026 RADAR | Global Arbitrage Solution</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------
# [8] 하단 고정 티커 (금융 로직 적용)
# ------------------------------------------------------------------
# 로직: (오늘 - 어제) 차이 계산 -> 🔺/🔻 및 색상 자동 결정
diff_usd = usd - usd_prev
diff_jpy = jpy - jpy_prev

# USD 포맷팅
sign_usd = "🔺" if diff_usd >= 0 else "🔻"
class_usd = "ticker-up" if diff_usd >= 0 else "ticker-down"
usd_text = f"{usd:,.0f}원 <span class='{class_usd}'>{sign_usd} {abs(diff_usd):.1f}</span>"

# JPY 포맷팅
sign_jpy = "🔺" if diff_jpy >= 0 else "🔻"
class_jpy = "ticker-up" if diff_jpy >= 0 else "ticker-down"
jpy_text = f"{jpy:,.0f}원 <span class='{class_jpy}'>{sign_jpy} {abs(diff_jpy):.1f}</span>"

us_limit = usd * 200
jp_limit = usd * 150 

ticker_content = f"""
<div class="ticker-wrap">
    <div class="ticker">
        <span class="ticker-item">USD/KRW <span class="ticker-val">{usd_text}</span></span>
        <span class="ticker-item">JPY/KRW <span class="ticker-val">{jpy_text}</span></span>
        <span class="ticker-item">미국 면세 <span class="ticker-val">${us_limit:,.0f}</span></span>
        <span class="ticker-item">일본 면세 <span class="ticker-val">{jp_limit:,.0f}원</span></span>
        <span class="ticker-item">SYSTEM <span class="ticker-val" style="color:#00ff88">ONLINE 🟢</span></span>
    </div>
</div>
"""
st.markdown(ticker_content, unsafe_allow_html=True)
