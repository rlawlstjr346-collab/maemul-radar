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
# [3] 로직 (환율, 번역, 계산, 데이터 파싱)
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
        return 1450.0, 950.0

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
# [4] CSS 스타일링
# ------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; font-family: 'Pretendard', sans-serif; }
    [data-testid="stSidebar"] { background-color: #17191E; border-right: 1px solid #333; }
    div[data-baseweb="input"] { background-color: #262730; border: 2px solid #00ff88 !important; border-radius: 8px; }
    
    /* 레이더 펄스 */
    .radar-wrapper { position: relative; display: inline-block; margin-right: 10px; vertical-align: middle; }
    .radar-emoji { position: relative; z-index: 2; font-size: 3rem; }
    .pulse-ring { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 100%; height: 100%; border-radius: 50%; border: 2px solid rgba(255, 255, 255, 0.7); opacity: 0; animation: pulse-ring 2s infinite; }
    @keyframes pulse-ring { 0% { width: 90%; opacity: 1; } 100% { width: 220%; opacity: 0; } }
    .title-text { font-size: 3rem; font-weight: 900; color: #FFFFFF !important; letter-spacing: -1px; }

    /* [수정] 커뮤니티 링크: 가로 배치 안 함 -> 텍스트 부분 세로 정렬 */
    .community-link { 
        display: flex; 
        align-items: center; 
        padding: 12px; 
        margin-bottom: 8px; 
        background-color: #262730; 
        border-radius: 8px; 
        text-decoration: none !important; 
        color: #eee !important; 
        border: 1px solid #333; 
    }
    .community-link:hover { background-color: #33343d; border-color: #555; }
    
    /* 아이콘 */
    .comm-icon { 
        font-size: 1.6rem; 
        margin-right: 15px; 
        min-width: 30px; 
        text-align: center; 
    }
    
    /* 텍스트 정보 (세로 배치) */
    .comm-info { 
        display: flex; 
        flex-direction: column; /* 여기서 위아래로 쌓음 */
        justify-content: center;
        line-height: 1.3;
    }
    .comm-name { font-weight: bold; font-size: 1rem; color: #fff; }
    .comm-desc { font-size: 0.75rem; color: #aaa; font-weight: normal; }

    /* 사기 조회 박스 */
    .scam-box { border: 1px solid #ff4b4b; background-color: rgba(255, 75, 75, 0.1); padding: 12px; border-radius: 8px; margin-bottom: 8px; color: #eee; font-size: 0.9rem; }
    .scam-title { color: #ff4b4b; font-weight: bold; margin-bottom: 4px; display: block; }

    /* 티커 & 카드 */
    .ticker-wrap { position: fixed; bottom: 0; left: 0; width: 100%; overflow: hidden; height: 40px; background-color: #15181E; border-top: 1px solid #333; z-index: 999; display: flex; align-items: center; }
    .ticker { display: inline-block; white-space: nowrap; padding-left: 100%; animation: ticker 40s linear infinite; }
    .ticker-item { margin-right: 40px; font-size: 0.95rem; font-weight: bold; color: #ddd; }
    .ticker-highlight { color: #00ff88; margin-right: 5px; }
    .ticker-alert { color: #ff4b4b; margin-right: 5px; }
    @keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-100%, 0, 0); } }

    .metric-card { background-color: #1E1E1E; border: 1px solid #333; border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 10px; }
    .metric-value { font-size: 1.5rem; font-weight: 800; color: #fff; }
    .metric-sub { font-size: 0.8rem; color: #00ff88; margin-top: 5px; }
    .metric-sub-bad { font-size: 0.8rem; color: #ff4b4b; margin-top: 5px; }

    /* 버튼 스타일 */
    div[data-testid="stLinkButton"] > a { border-radius: 10px; font-weight: 700; transition: all 0.3s ease; text-decoration: none; }
    div[data-testid="stLinkButton"] > a[href*="bunjang"] { border: 1px solid #FF3E3E !important; color: #FF3E3E !important; background-color: rgba(255, 62, 62, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="daangn"] { border: 1px solid #FF8A3D !important; color: #FF8A3D !important; background-color: rgba(255, 138, 61, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="joongna"] { border: 1px solid #00E676 !important; color: #00E676 !important; background-color: rgba(0, 230, 118, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="ebay"] { border: 1px solid #2962FF !important; color: #2962FF !important; background-color: rgba(41, 98, 255, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="mercari"] { border: 1px solid #EEEEEE !important; color: #EEEEEE !important; background-color: rgba(238, 238, 238, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="thecheat"] { border: 2px solid #ff4b4b !important; color: #ffffff !important; background-color: #ff4b4b !important; }

    .signal-banner { background: linear-gradient(90deg, #0A84FF 0%, #0055FF 100%); color: white !important; padding: 15px 20px; border-radius: 12px; margin-bottom: 25px; font-weight: bold; font-size: 1rem; display: flex; align-items: center; box-shadow: 0 4px 15px rgba(10, 132, 255, 0.3); }
    .legal-footer { font-size: 0.75rem; color: #777; margin-top: 60px; padding: 30px 10px; text-align: center; margin-bottom: 50px; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [5] 메인 헤더
# ------------------------------------------------------------------
now_time = st.session_state.ticker_data['time']
usd, jpy = get_exchange_rates()

st.markdown("""
    <div style="text-align:center; margin-bottom:20px;">
        <div class="radar-wrapper"><span class="radar-emoji">📡</span><div class="pulse-ring"></div></div>
        <span class="title-text">매물레이더 Pro</span>
        <p style="color:#aaa; font-size:1rem; margin-top:5px;">숨어있는 꿀매물을 3단계 심층 스캔합니다.</p>
    </div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [6] 사이드바 (깔끔한 서랍형 정리)
# ------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 레이더 센터")
    
    # 1. 시세 교차 검증 (커뮤니티)
    with st.expander("👀 커뮤니티 시세비교", expanded=True):
        st.markdown("""
        <a href="http://www.slrclub.com" target="_blank" class="community-link"><div class="comm-icon">📷</div><div class="comm-info"><span class="comm-name">SLR클럽</span><span class="comm-desc">카메라/렌즈 전문</span></div></a>
        <a href="https://coolenjoy.net" target="_blank" class="community-link"><div class="comm-icon">💻</div><div class="comm-info"><span class="comm-name">쿨엔조이</span><span class="comm-desc">PC 하드웨어/부품</span></div></a>
        <a href="https://quasarzone.com" target="_blank" class="community-link"><div class="comm-icon">🔥</div><div class="comm-info"><span class="comm-name">퀘이사존</span><span class="comm-desc">게이밍 기어/PC</span></div></a>
        <a href="https://cafe.naver.com/appleiphone" target="_blank" class="community-link"><div class="comm-icon">🍎</div><div class="comm-info"><span class="comm-name">아사모</span><span class="comm-desc">아이폰/애플 기기</span></div></a>
        """, unsafe_allow_html=True)

    st.write("---")

    # 2. 거래 도구함 (배송 + 관세 통합)
    with st.expander("🧰 거래 도구함 (배송/관세)", expanded=False):
        tool_tab1, tool_tab2 = st.tabs(["📦 배송조회", "💱 관세계산"])
        
        with tool_tab1:
            track_no = st.text_input("운송장 번호", placeholder="- 없이 숫자만")
            if track_no:
                st.link_button("🔍 택배사 자동 스캔", f"https://search.naver.com/search.naver?query=운송장번호+{track_no}", use_container_width=True)
            else:
                st.caption("편의점 택배 바로가기")
                c1, c2 = st.columns(2)
                c1.link_button("GS반값", "https://www.cvsnet.co.kr/reservation-tracking/tracking/index.do", use_container_width=True)
                c2.link_button("CU알뜰", "https://www.cupost.co.kr/postbox/delivery/local.cupost", use_container_width=True)
        
        with tool_tab2:
            calc_tab1, calc_tab2 = st.tabs(["🇺🇸 USD", "🇯🇵 JPY"])
            with calc_tab1:
                st.caption(f"환율: {usd:,.1f}원/$")
                p_u = st.number_input("물품가격($)", 190, step=10)
                krw_val = p_u * usd
                st.markdown(f"**≈ {krw_val:,.0f} 원**")
                if p_u <= 200: st.success("✅ 면세")
                else: st.error(f"🚨 관세 대상")
            with calc_tab2:
                st.caption(f"환율: {jpy:,.1f}원/100¥")
                p_j = st.number_input("물품가격(¥)", 15000, step=1000)
                krw_val = p_j * (jpy/100)
                usd_val = krw_val / usd
                st.markdown(f"**≈ {krw_val:,.0f} 원**")
                if usd_val <= 150: st.success("✅ 면세")
                else: st.error(f"🚨 관세 대상")

    st.write("---")

    # 3. 사기 판독 센터 (더치트 버튼 통합)
    with st.expander("👮‍♂️ 사기 판독 센터", expanded=False):
        st.markdown("""
        <div class="scam-box"><span class="scam-title">🚫 카톡 유도 절대금지</span>"카톡으로 대화해요" → 99.9% 사기</div>
        <div class="scam-box"><span class="scam-title">🚫 가짜 결제창 주의</span>링크 주소(URL) 반드시 확인하세요</div>
        """, unsafe_allow_html=True)
        st.write("")
        st.link_button("👮‍♂️ 더치트 이력 조회하기", "https://thecheat.co.kr", type="primary", use_container_width=True)

# ------------------------------------------------------------------
# [7] 메인 콘텐츠
# ------------------------------------------------------------------
col_left, col_right = st.columns([0.6, 0.4], gap="large")

with col_left:
    st.caption(f"System Live | Last Scan: {now_time}")
    keyword = st.text_input("검색어 입력", placeholder="🔍 찾으시는 물건을 입력하세요 (예: 지슈라 2, 아이폰 15)", label_visibility="collapsed")

    if keyword:
        eng_keyword = get_translated_keyword(keyword, 'en')
        jp_keyword = get_translated_keyword(keyword, 'ja')
        
        safe_keyword = html.escape(keyword)
        encoded_kor = urllib.parse.quote(keyword)
        encoded_eng = urllib.parse.quote(eng_keyword)
        encoded_jp = urllib.parse.quote(jp_keyword)
        
        st.markdown(f'''
            <div class="signal-banner">
                <span class="radar-dot-strong"></span>
                <span>'{safe_keyword}' 포착! (En: {eng_keyword})</span>
            </div>
        ''', unsafe_allow_html=True)

        st.markdown('### 🔥 국내 메이저')
        c1, c2 = st.columns(2)
        c1.link_button("⚡ 번개장터", f"https://m.bunjang.co.kr/search/products?q={encoded_kor}", use_container_width=True)
        c2.link_button("🥕 당근마켓", f"https://www.daangn.com/search/{encoded_kor}", use_container_width=True)

        st.markdown('### 💎 국내 마이너')
        c3, c4 = st.columns(2)
        c3.link_button("🌵 중고나라", f"https://web.joongna.com/search?keyword={encoded_kor}", use_container_width=True)
        c4.link_button("🍇 후르츠 (패션)", f"https://fruitsfamily.com/search/{encoded_kor}", use_container_width=True)

        st.markdown('### ✈️ 해외 직구 (자동번역)')
        st.caption(f"💡 검색어가 자동으로 번역되어 연결됩니다.")
        c5, c6 = st.columns(2)
        c5.link_button(f"🇺🇸 eBay ({eng_keyword})", f"https://www.ebay.com/sch/i.html?_nkw={encoded_eng}", use_container_width=True)
        c6.link_button(f"🇯🇵 Mercari ({jp_keyword})", f"https://jp.mercari.com/search?keyword={encoded_jp}", use_container_width=True)

    else:
        st.info("👆 상품명을 입력하면 3단계 심층 스캔을 시작합니다.")

with col_right:
    st.markdown("#### 📉 52주 시세 트렌드")
    df_prices = load_price_data()
    matched = get_trend_data_from_sheet(keyword, df_prices)
    
    if matched:
        global_krw = calculate_total_import_cost(matched['global_usd'], usd)
        kr_avg = sum(matched['trend_prices'])/len(matched['trend_prices']) if matched['trend_prices'] else 0
        
        m1, m2 = st.columns(2)
        with m1:
             st.markdown(f"<div class='metric-card'><div>🇰🇷 국내 평균</div><div class='metric-value'>{kr_avg:,.1f}만</div></div>", unsafe_allow_html=True)
        with m2:
            diff_text = f"직구 {kr_avg - global_krw:,.1f}만 이득" if (kr_avg - global_krw) > 0 else "국내 구매 유리"
            sub_class = "metric-sub" if (kr_avg - global_krw) > 0 else "metric-sub-bad"
            if global_krw <= 0: 
                diff_text = "해외 데이터 없음"
                sub_class = "metric-sub"
            st.markdown(f"<div class='metric-card'><div>🌎 직구 실구매</div><div class='metric-value'>{global_krw:,.1f}만</div><div class='{sub_class}'>{diff_text}</div></div>", unsafe_allow_html=True)
        
        st.write("")

        tab_trend, tab_dist = st.tabs(["📈 시세 흐름", "📊 가격 분포도"])
        with tab_trend:
            chart_df = pd.DataFrame({"날짜": matched["dates"], "국내": matched["trend_prices"], "해외직구": [global_krw] * len(matched["dates"])})
            base = alt.Chart(chart_df).encode(x=alt.X('날짜:N', sort=None))
            charts = base.mark_line(color='#00ff88', size=3).encode(y=alt.Y('국내:Q', title='가격(만원)'))
            if global_krw > 0:
                charts += base.mark_line(color='#ff4b4b', strokeDash=[5,5]).encode(y='해외직구:Q')
            st.altair_chart(charts.properties(height=250), use_container_width=True)
        
        with tab_dist:
             dist_df = pd.DataFrame({"가격": matched["raw_prices"]})
             dist_chart = alt.Chart(dist_df).mark_bar(color='#0A84FF').encode(
                 x=alt.X('가격:Q', bin=alt.Bin(maxbins=15)), 
                 y=alt.Y('count()', axis=alt.Axis(tickMinStep=1, format='d'))
             ).properties(height=250)
             st.altair_chart(dist_chart, use_container_width=True)

    else:
        # 공백 채우기 모드 (빈 그래프)
        if not keyword:
            st.info("👇 좌측에 검색어를 입력하면 실제 시세가 표시됩니다. (아래는 예시)")
        else:
            st.warning(f"⚠️ '{keyword}' 데이터가 시트에 없습니다. (아래는 예시 기능)")

        dummy_df = pd.DataFrame({'x': range(5), 'y': [10, 12, 11, 13, 12]})
        dummy_chart = alt.Chart(dummy_df).mark_line(color='#333', strokeDash=[5,5]).encode(
            x=alt.X('x', axis=None), y=alt.Y('y', axis=None, title='시세 데이터 대기중')
        ).properties(height=250, title="데이터 대기중...")
        st.altair_chart(dummy_chart, use_container_width=True)

    # [수정] 스마트 멘트: 정중한 표현으로 전면 교체
    st.markdown("#### 💬 스마트 트레이더")
    tab_m1, tab_m2, tab_memo = st.tabs(["⚡️ 퀵멘트", "💳 결제", "📝 메모"])
    
    with tab_m1:
        quick_opt = st.radio("빠른 선택", ["👋 구매 문의", "💸 가격 제안"], label_visibility="collapsed")
        if quick_opt == "👋 구매 문의": 
            st.code("안녕하세요! 게시글 보고 연락드립니다. 구매 가능할까요?", language="text")
        else:
            nego_price = st.text_input("희망 가격 (숫자만 입력)", placeholder="예: 30000")
            if nego_price:
                try: fmt_price = f"{int(nego_price):,}"
                except: fmt_price = nego_price
                st.code(f"안녕하세요. 혹시 실례지만 {fmt_price}원에 가격조정 가능할지 여쭤보고 싶습니다. 가능하시다면 바로 구매가능합니다.", language="text")
            else:
                st.caption("☝️ 위 칸에 가격을 입력하면 멘트가 완성됩니다.")
                st.code("안녕하세요. 혹시 실례지만 [   ]원에 가격조정 가능할지 여쭤보고 싶습니다. 가능하시다면 바로 구매가능합니다.", language="text")

    with tab_m2:
            pay_opt = st.radio("거래 방식", ["💳 계좌 문의", "🤝 직거래"], horizontal=True, label_visibility="collapsed")
            if pay_opt == "💳 계좌 문의": 
                st.code("계좌결제로 하겠습니다. 계좌 부탁드립니다.", language="text")
            else: 
                st.code("직거래로 가능하신지 여쭤봅니다.", language="text")
                
    with tab_memo:
        st.session_state.memo_pad = st.text_area("메모", value=st.session_state.memo_pad, height=100, placeholder="가격 비교 메모...")

st.markdown('<div class="legal-footer">© 2026 매물레이더 Pro | Global Price Intelligence</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------
# [8] 하단 고정 티커
# ------------------------------------------------------------------
us_limit = usd * 200
jp_limit = usd * 150 
ticker_content = f"""
<div class="ticker-wrap">
    <div class="ticker">
        <span class="ticker-item"><span class="ticker-highlight">🇺🇸 USD:</span>{usd:,.0f}원</span>
        <span class="ticker-item"><span class="ticker-highlight">🇯🇵 JPY:</span>{jpy:,.0f}원</span>
        <span class="ticker-item"><span class="ticker-alert">🚨 미국 무관세:</span>{us_limit:,.0f}원($200)까지</span>
        <span class="ticker-item"><span class="ticker-alert">🚨 일본/해외 무관세:</span>{jp_limit:,.0f}원($150)까지</span>
        <span class="ticker-item" style="color:#aaa;">💡 실시간 환율 기반 직구 가이드</span>
    </div>
</div>
"""
st.markdown(ticker_content, unsafe_allow_html=True)
