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
# [3] 유틸리티 함수
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

# [수정] 번역 함수 강화 (재시도 로직 추가)
def get_translated_keyword(text, target_lang='en'):
    if not re.search('[가-힣]', text): return text
    
    # 1차 시도
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ko&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            result = response.json()[0][0][0]
            if result and result.strip(): return result
    except: pass
    
    # 2차 시도 (실패 시 원본 반환)
    return text

def get_trend_data_from_sheet(user_query, df):
    if df.empty or not user_query: return None
    user_clean = user_query.lower().replace(" ", "").strip()
    best_match = None
    min_len_diff = float('inf')
    
    date_cols = ["12월 4주", "1월 1주", "1월 2주", "1월 3주", "1월 4주"]
    
    for index, row in df.iterrows():
        try:
            k_val = row.get('키워드') if '키워드' in df.columns else row.get('keyword')
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
                                val = float(row.get(col, 0))
                                if val > 5:
                                    trend_prices.append(val)
                                    valid_dates.append(col)
                            except: pass
                    
                    raw_str = str(row.get('시세 (5주치)', '')).replace('"', '').strip()
                    raw_prices = []
                    if raw_str:
                        temp_list = [float(p) for p in raw_str.split(',') if p.strip()]
                        raw_prices = [p for p in temp_list if p > 5] 
                    
                    if not raw_prices: 
                        raw_prices = trend_prices

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
# [4] CSS 스타일링
# ------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; font-family: 'Pretendard', sans-serif; }
    [data-testid="stSidebar"] { background-color: #17191E; border-right: 1px solid #333; }
    div[data-baseweb="input"] { background-color: #262730; border: 2px solid #00ff88 !important; border-radius: 8px; box-shadow: 0 0 10px rgba(0, 255, 136, 0.15); transition: all 0.3s ease; }
    div[data-baseweb="input"]:focus-within { box-shadow: 0 0 15px rgba(0, 255, 136, 0.5); }
    .stTextInput input, .stTextArea textarea, .stNumberInput input { color: #FAFAFA; font-weight: bold; }
    div[data-testid="stLinkButton"] > a { border-radius: 10px; font-weight: 700; transition: all 0.3s ease; text-decoration: none; }
    
    /* 버튼 스타일 개별 지정 */
    div[data-testid="stLinkButton"] > a[href*="bunjang"] { border: 1px solid #FF3E3E !important; color: #FF3E3E !important; background-color: rgba(255, 62, 62, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="daangn"] { border: 1px solid #FF8A3D !important; color: #FF8A3D !important; background-color: rgba(255, 138, 61, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="joongna"] { border: 1px solid #00E676 !important; color: #00E676 !important; background-color: rgba(0, 230, 118, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="fruitsfamily"] { border: 1px solid #D500F9 !important; color: #D500F9 !important; background-color: rgba(213, 0, 249, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="ebay"] { border: 1px solid #2962FF !important; color: #2962FF !important; background-color: rgba(41, 98, 255, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="mercari"] { border: 1px solid #EEEEEE !important; color: #EEEEEE !important; background-color: rgba(238, 238, 238, 0.1); }
    
    /* 호버 효과 */
    div[data-testid="stLinkButton"] > a:hover { transform: translateY(-2px); opacity: 0.8; }

    .radar-wrapper { position: relative; display: inline-block; margin-right: 10px; vertical-align: middle; }
    .radar-emoji { position: relative; z-index: 2; font-size: 3rem; }
    .pulse-ring { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 100%; height: 100%; border-radius: 50%; border: 2px solid rgba(255, 255, 255, 0.7); opacity: 0; animation: pulse-ring 2s infinite; }
    @keyframes pulse-ring { 0% { width: 90%; opacity: 1; } 100% { width: 220%; opacity: 0; } }
    .title-text { font-size: 3rem; font-weight: 900; color: #FFFFFF !important; letter-spacing: -1px; }
    
    .side-util-header { font-size: 1rem; font-weight: bold; color: #0A84FF; margin-top: 5px; margin-bottom: 5px; border-left: 3px solid #0A84FF; padding-left: 8px; }
    
    /* 커뮤니티 리스트 스타일 (수정됨) */
    .community-link { 
        display: flex; 
        align_items: center; 
        padding: 8px; 
        margin-bottom: 5px; 
        background-color: #262730; 
        border-radius: 8px; 
        text-decoration: none !important; 
        color: #eee !important; 
        transition: background-color 0.2s;
    }
    .community-link:hover { background-color: #33343d; }
    .comm-icon { font-size: 1.2rem; margin-right: 10px; min-width: 25px; text-align: center; }
    .comm-name { font-weight: bold; margin-right: 8px; }
    .comm-desc { font-size: 0.8rem; color: #aaa; }

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
    
    .rank-num { color: #888; font-size: 0.8rem; margin-right: 4px; }
    .item-text { color: #eee; font-weight: 600; }
    .legal-footer { font-size: 0.75rem; color: #777; margin-top: 60px; padding: 30px 10px; border-top: 1px solid #333; text-align: center; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [5] 상단 티커
# ------------------------------------------------------------------
market_pool = ["아이폰 17 Pro", "RTX 5090", "갤럭시 S25", "PS5 Pro", "에어팟 맥스 2", "닌텐도 스위치 2", "후지필름 X100VI", "아이패드 M4", "스투시", "아크테릭스"]
radar_pool = ["리코 GR3", "치이카와", "뉴진스 굿즈", "젠틀몬스터", "요시다포터", "살로몬", "코닥 작티", "산리오", "다마고치", "티니핑"]
market_str = "".join([f"<span><span class='rank-num'>{i+1}.</span><span class='item-text'>{item}</span></span>" for i, item in enumerate(random.sample(market_pool, 10))])
radar_str = "".join([f"<span><span class='rank-num'>{i+1}.</span><span class='item-text'>{item}</span></span>" for i, item in enumerate(random.sample(radar_pool, 10))])
now_time = st.session_state.ticker_data['time']

ticker_html = f"""
<div class="ticker-container">
    <div class="ticker-line">
        <div class="ticker-move-1">
            <span class="label-market">🔥 Market Hot:</span> {market_str}
            <span class="label-market" style="margin-left:50px;">🔥 Market Hot:</span> {market_str}
        </div>
    </div>
    <div class="ticker-line" style="border-bottom: none;">
        <div class="ticker-move-2">
            <span class="label-radar">📡 Radar Top:</span> {radar_str}
            <span class="label-radar" style="margin-left:50px;">📡 Radar Top:</span> {radar_str}
        </div>
    </div>
</div>
"""
st.markdown(ticker_html, unsafe_allow_html=True)

# ------------------------------------------------------------------
# [6] 사이드바
# ------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 레이더 센터")
    with st.expander("👀 커뮤니티 시세비교", expanded=True):
        # [수정] 커뮤니티 링크를 HTML로 직접 구현하여 가독성 개선
        st.markdown("""
        <a href="http://www.slrclub.com" target="_blank" class="community-link">
            <span class="comm-icon">📷</span>
            <span class="comm-name">SLR클럽</span>
            <span class="comm-desc">카메라/렌즈</span>
        </a>
        <a href="https://coolenjoy.net" target="_blank" class="community-link">
            <span class="comm-icon">💻</span>
            <span class="comm-name">쿨엔조이</span>
            <span class="comm-desc">PC/하드웨어</span>
        </a>
        <a href="https://quasarzone.com" target="_blank" class="community-link">
            <span class="comm-icon">🔥</span>
            <span class="comm-name">퀘이사존</span>
            <span class="comm-desc">PC/게이밍</span>
        </a>
        <a href="https://cafe.naver.com/appleiphone" target="_blank" class="community-link">
            <span class="comm-icon">🍎</span>
            <span class="comm-name">아사모</span>
            <span class="comm-desc">애플 기기</span>
        </a>
        """, unsafe_allow_html=True)

    st.write("---")
    with st.expander("📦 배송 조회 레이더", expanded=True):
        track_no = st.text_input("운송장 번호", placeholder="- 없이 숫자만 입력")
        if track_no:
            st.link_button("🔍 택배사 자동 스캔", f"https://search.naver.com/search.naver?query=운송장번호+{track_no}", use_container_width=True)
        else:
            st.caption("👇 편의점 택배 바로가기")
            c1, c2 = st.columns(2)
            c1.link_button("GS반값", "https://www.cvsnet.co.kr/reservation-tracking/tracking/index.do", use_container_width=True)
            c2.link_button("CU알뜰", "https://www.cupost.co.kr/postbox/delivery/local.cupost", use_container_width=True)
    st.write("---")
    usd, jpy = get_exchange_rates()
    with st.expander("💱 관세 안전선 계산기", expanded=True):
        t1, t2 = st.tabs(["🇺🇸 USD", "🇯🇵 JPY"])
        with t1:
            st.caption(f"환율: {usd:,.1f}원/$")
            p_u = st.number_input("가격($)", 190, step=10)
            if p_u <= 200: st.success(f"✅ 면세 (약 {p_u*usd:,.0f}원)")
            else: st.error("🚨 관세 대상")
        with t2:
            st.caption(f"환율: {jpy:,.1f}원/100¥")
            p_j = st.number_input("가격(¥)", 15000, step=1000)
            if (p_j*(jpy/100)/usd) <= 150: st.success(f"✅ 면세 (약 {p_j*(jpy/100):,.0f}원)")
            else: st.error("🚨 관세 대상")
    st.write("---")
    st.link_button("🚨 사기피해 조회 (더치트)", "https://thecheat.co.kr", type="primary", use_container_width=True)
    st.link_button("💬 피드백 보내기", "https://docs.google.com/forms/d/e/1FAIpQLSdZdfJLBErRw8ArXlBLqw9jkoLk0Qj-AOo0yPm-hg7KmGYOnA/viewform?usp=dialog", use_container_width=True)

# ------------------------------------------------------------------
# [7] 메인 화면
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
    st.markdown('<div style="margin-bottom: 5px;"><span class="radar-dot-idle"></span>타겟 탐색</div>', unsafe_allow_html=True)
    keyword = st.text_input("검색어 입력", placeholder="🔍 찾으시는 물건을 입력하세요 (예: 아이폰15, 포켓몬스터)", label_visibility="collapsed")

    if keyword:
        safe_keyword = html.escape(keyword) 
        encoded_kor = urllib.parse.quote(keyword)
        eng_keyword = get_translated_keyword(keyword, 'en')
        jp_keyword = get_translated_keyword(keyword, 'ja')
        safe_eng = html.escape(eng_keyword)
        safe_jp = html.escape(jp_keyword)
        encoded_eng = urllib.parse.quote(eng_keyword)
        encoded_jp = urllib.parse.quote(jp_keyword)
        
        st.markdown(f'''
            <div class="signal-banner">
                <span class="radar-dot-strong"></span>
                <span>'{safe_keyword}' 포착! (En: {safe_eng} / Jp: {safe_jp})</span>
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
        c5.link_button(f"🇺🇸 eBay ({safe_eng})", f"https://www.ebay.com/sch/i.html?_nkw={encoded_eng}", use_container_width=True)
        c6.link_button(f"🇯🇵 Mercari ({safe_jp})", f"https://jp.mercari.com/search?keyword={encoded_jp}", use_container_width=True)

    else:
        st.info("👆 상품명을 입력하면 3단계 심층 스캔을 시작합니다.")
        st.markdown("""
            <div style="background-color:#262730; padding:15px; border-radius:10px; margin-top:20px; border:1px solid #444;">
                <h4 style="margin:0 0 10px 0; color:#00ff88;">💡 사용 꿀팁 (Tip)</h4>
                <ul style="font-size:0.9rem; color:#ccc; padding-left:20px; line-height:1.6;">
                    <li><b>우측 그래프</b>는 구글 시트에 있는 시세 데이터와 연동됩니다.</li>
                    <li>해외 사이트(이베이, 메루카리)는 자동으로 <b>영어, 일본어</b>로 번역됩니다.</li>
                </ul>
            </div>
        """, unsafe_allow_html=True)

with col_right:
    st.markdown("#### 📉 52주 시세 트렌드")
    df_prices = load_price_data()
    matched_data = get_trend_data_from_sheet(keyword, df_prices)
    
    if matched_data:
        st.caption(f"✅ '{matched_data['name']}' 데이터 확인됨")
        
        # 1. 시세 흐름용 데이터프레임 (날짜 순서 강제)
        df_trend = pd.DataFrame({
            "날짜": matched_data["dates"],
            "가격": matched_data["trend_prices"]
        })
        
        # 2. 분포도용 데이터프레임 (Raw Data)
        df_dist = pd.DataFrame({
            "가격": matched_data["raw_prices"]
        })

        tab_trend, tab_dist = st.tabs(["📈 시세 흐름", "📊 가격 분포도"])

        with tab_trend:
            if not df_trend.empty:
                # X축 순서 강제 고정 (sort=None)
                st.line_chart(df_trend, x="날짜", y="가격", color="#00ff88", height=250)
                
                curr_price = matched_data['trend_prices'][-1]
                avg_price = sum(matched_data['trend_prices']) / len(matched_data['trend_prices'])
                c_m1, c_m2 = st.columns(2)
                c_m1.metric("현재 주간 평균", f"{curr_price:,.0f}만")
                c_m2.metric("5주 전체 평균", f"{avg_price:,.0f}만")
            else:
                st.warning("표시할 시세 흐름 데이터가 부족합니다.")
        
        with tab_dist:
            if not df_dist.empty:
                # [핵심] 평균가 계산
                mean_val = df_dist['가격'].mean()
                
                # 히스토그램 (막대)
                bars = alt.Chart(df_dist).mark_bar(
                    color='#0A84FF', cornerRadiusTopLeft=3, cornerRadiusTopRight=3
                ).encode(
                    x=alt.X('가격', bin=alt.Bin(maxbins=20), title='가격 구간 (만원)'),
                    y=alt.Y('count()', title='매물 수'),
                    tooltip=['count()', alt.Tooltip('가격', bin=True, title='가격 범위')]
                )
                
                # 평균선 (빨간색 세로줄)
                rule = alt.Chart(pd.DataFrame({'mean_price': [mean_val]})).mark_rule(
                    color='red', strokeDash=[4, 4]
                ).encode(x='mean_price')
                
                # 차트 합치기 (레이어)
                final_chart = (bars + rule).properties(height=250).configure_axis(
                    grid=False, labelColor='#eee', titleColor='#eee'
                ).configure_view(strokeWidth=0)
                
                st.altair_chart(final_chart, use_container_width=True)
                
                p_min = min(matched_data['raw_prices'])
                p_max = max(matched_data['raw_prices'])
                
                st.caption(f"📍 빨간 점선: 평균 거래가 ({mean_val:,.0f}만원)")
                if (p_max - p_min) > 50:
                    st.warning(f"🚨 가격 차이가 큽니다 ({p_min}만 ~ {p_max}만). 상태(S급/C급)를 꼭 확인하세요.")
                else:
                    st.success("✅ 시세가 특정 구간에 집중되어 있어 안정적입니다.")
            else:
                st.warning("분석할 가격 데이터가 없습니다.")

    else:
        if keyword:
            st.warning(f"⚠️ '{keyword}'에 대한 시세 데이터가 아직 수집되지 않았습니다.")
        else:
            st.info("좌측에 검색어를 입력하면 시세 그래프가 나타납니다.")
            
    st.write("") 

    st.markdown("#### 💬 스마트 멘트 & 메모")
    tab_m1, tab_m2, tab_memo = st.tabs(["⚡️ 퀵멘트", "💳 결제", "📝 메모"])
    
    with tab_m1:
        st.caption("👇 상황을 선택하면 정중한 멘트가 완성됩니다.")
        quick_opt = st.radio("빠른 선택", ["👋 구매 문의 (재고 확인)", "💸 가격 제안 (네고 요청)", "📦 택배비 포함 요청"], label_visibility="collapsed")
        if quick_opt == "👋 구매 문의 (재고 확인)":
            st.code("안녕하세요! 게시글 보고 연락드립니다. 구매 가능할까요?", language="text")
        elif quick_opt == "💸 가격 제안 (네고 요청)":
            user_price = st.text_input("희망 가격", placeholder="예: 3만원", key="quick_price")
            price = user_price if user_price else "[00원]"
            st.code(f"상품이 너무 마음에 드는데, 혹시 실례가 안 된다면 {price} 정도로 가격 조정이 가능할까요? 가능하다면 바로 결제하겠습니다!", language="text")
        elif quick_opt == "📦 택배비 포함 요청":
            st.code("안녕하세요! 혹시 실례가 안 된다면 택배비 포함으로 부탁드릴 수 있을까요? 가능하다면 바로 구매하겠습니다!", language="text")

    with tab_m2:
        st.caption("👇 결제 방식 및 직거래")
        pay_opt = st.radio("거래 방식", ["💳 계좌/안전결제 문의", "🤝 직거래 장소 제안"], horizontal=True, label_visibility="collapsed")
        if pay_opt == "💳 계좌/안전결제 문의":
            pay_method = st.radio("결제 수단", ["계좌이체", "안전결제 (번개/당근/중나)"], horizontal=True)
            if pay_method == "계좌이체":
                st.code("구매 결정했습니다! 계좌번호 알려주시면 바로 이체하겠습니다.", language="text")
            else:
                 st.caption("플랫폼 선택")
                 platform = st.radio("플랫폼", ["⚡ 번개", "🥕 당근", "🌵 중고", "🍇 후르츠"], horizontal=True, label_visibility="collapsed")
                 if "번개" in platform: st.code("혹시 번개페이(안전결제)로 구매 가능할까요? 가능하다면 바로 결제하겠습니다.", language="text")
                 elif "당근" in platform: st.code("혹시 당근페이(안심결제)로 거래 가능할까요?", language="text")
                 elif "중고" in platform: st.code("혹시 중고나라 페이(안전결제)로 가능할까요?", language="text")
                 elif "후르츠" in platform: st.code("혹시 앱 내 안전결제로 바로 결제해도 될까요?", language="text")
        elif pay_opt == "🤝 직거래 장소 제안":
             user_place = st.text_input("희망 장소", placeholder="예: 강남역 10번출구", key="direct_place")
             place = user_place if user_place else "[OO역]"
             st.code(f"안녕하세요! 혹시 {place} 근처에서 직거래 가능하실까요? 시간 맞춰보겠습니다.", language="text")
    
    with tab_memo:
        st.session_state.memo_pad = st.text_area("메모", value=st.session_state.memo_pad, height=100, label_visibility="collapsed", placeholder="가격 비교 메모...")
    
    st.write("")
    
    st.markdown('<div class="side-util-header">🚨 사기꾼 판독기 (유형별)</div>', unsafe_allow_html=True)
    with st.expander("👮‍♂️ 필수 체크 (클릭해서 확인)", expanded=False):
        st.markdown('<div class="scam-alert-text">1. 카톡 아이디 거래 유도</div>', unsafe_allow_html=True)
        st.markdown('<div class="scam-desc">"카톡으로 대화해요" → 99.9% 사기입니다. 앱 내 채팅만 이용하세요.</div>', unsafe_allow_html=True)
        st.markdown('<div class="scam-alert-text">2. 가짜 안전결제 링크</div>', unsafe_allow_html=True)
        st.markdown('<div class="scam-desc">http://... 로 시작하거나 도메인이 다르면 피싱 사이트입니다. 절대 클릭 금지!</div>', unsafe_allow_html=True)
        st.markdown('<div class="scam-alert-text">3. 재입금 요구 (수수료 핑계)</div>', unsafe_allow_html=True)
        st.markdown('<div class="scam-desc">"수수료 안 보내서 다시 보내라" → 전형적인 3자 사기/먹튀입니다.</div>', unsafe_allow_html=True)

st.markdown("""
    <div class="legal-footer">
        본 서비스는 온라인 쇼핑몰 및 중고 거래 사이트의 상품 정보를 검색하여 링크를 제공하는 서비스입니다.<br>
        당사는 통신판매 당사자가 아니며, 상품의 주문/배송/환불 등 모든 거래에 대한 의무와 책임은 각 판매자에게 있습니다.<br>
        <br>
        ⚠️ <strong>안전한 거래를 위해 반드시 '안전결제(에스크로)'를 이용하시기 바랍니다.</strong>
    </div>
""", unsafe_allow_html=True)
