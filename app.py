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
# [1] 앱 기본 설정
# ------------------------------------------------------------------
st.set_page_config(
    page_title="매물레이더 Pro",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------------------
# [2] 데이터 관리 (한글 컬럼 호환 패치)
# ------------------------------------------------------------------
sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQS8AftSUmG9Cr7MfczpotB5hhl1DgjH4hRCgXH5R8j5hykRiEf0M9rEyEq3uj312a5RuI4zMdjI5Jr/pub?output=csv"

@st.cache_data(ttl=60)
def load_price_data():
    try:
        df = pd.read_csv(sheet_url)
        df.columns = df.columns.str.strip() # 공백 제거
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
        r = requests.get(url, timeout=3).json()
        return r['rates']['KRW'], (r['rates']['KRW'] / r['rates']['JPY']) * 100
    except:
        return 1450.0, 950.0

def get_translated_keyword(text, target_lang='en'):
    if not re.search('[가-힣]', text): return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ko&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
        res = requests.get(url, timeout=1)
        if res.status_code == 200: return res.json()[0][0][0]
    except: pass
    return text

# [★핵심 수정] 한글 컬럼명('키워드', '시세') 자동 인식 로직
def get_trend_data_from_sheet(user_query, df):
    if df.empty or not user_query: return None
    
    # 1. 검색어 공백 제거 (아이폰 16 -> 아이폰16)
    user_clean = user_query.lower().replace(" ", "").strip()
    
    # 2. 엑셀 데이터 한 줄씩 스캔
    for index, row in df.iterrows():
        try:
            # [수정] 엑셀의 '키워드' 컬럼을 읽음 (없으면 'keyword' 시도)
            sheet_key_raw = row.get('키워드') if '키워드' in df.columns else row.get('keyword')
            sheet_key = str(sheet_key_raw).lower().replace(" ", "").strip()
            
            # 3. 매칭 성공 시 데이터 추출
            if sheet_key and (sheet_key in user_clean or user_clean in sheet_key):
                
                # [수정] '모델명 (상세스펙/상태)' 또는 'name' 읽기
                name_col = '모델명 (상세스펙/상태)' if '모델명 (상세스펙/상태)' in df.columns else 'name'
                item_name = row.get(name_col, '상품명 없음')

                # [수정] '시세 (5주치)' 또는 'prices' 읽기
                price_col = '시세 (5주치)' if '시세 (5주치)' in df.columns else 'prices'
                price_raw = str(row.get(price_col, '')).replace('"', '').strip()
                prices = [float(p) for p in price_raw.split(',')]
                
                # [수정] 날짜 컬럼이 없으면, 사장님 엑셀 헤더 기준으로 자동 생성
                # (엑셀에 적혀있던 12월 4주 ~ 1월 4주 패턴 적용)
                dates = ['12월 4주', '1월 1주', '1월 2주', '1월 3주', '1월 4주']
                # 만약 가격 데이터 개수가 다르면 개수만큼 자동 생성 (예: 1주전, 2주전...)
                if len(prices) != 5:
                    dates = [f"{i}주전" for i in range(len(prices), 0, -1)]

                return {
                    "name": item_name,
                    "dates": dates,
                    "prices": prices
                }
        except Exception as e:
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
# [4] CSS 스타일링 (유지)
# ------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; font-family: 'Pretendard', sans-serif; }
    [data-testid="stSidebar"] { background-color: #17191E; border-right: 1px solid #333; }
    div[data-baseweb="input"] { background-color: #262730; border: 2px solid #00ff88 !important; border-radius: 8px; }
    .stTextInput input { color: #FAFAFA; font-weight: bold; }
    div[data-testid="stLinkButton"] > a { border-radius: 10px; font-weight: 700; text-decoration: none; }
    
    /* 버튼 색상 */
    a[href*="bunjang"] { color: #FF3E3E !important; border: 1px solid #FF3E3E !important; background: rgba(255, 62, 62, 0.1); }
    a[href*="daangn"] { color: #FF8A3D !important; border: 1px solid #FF8A3D !important; background: rgba(255, 138, 61, 0.1); }
    a[href*="joongna"] { color: #00E676 !important; border: 1px solid #00E676 !important; background: rgba(0, 230, 118, 0.1); }
    a[href*="ebay"] { color: #2962FF !important; border: 1px solid #2962FF !important; background: rgba(41, 98, 255, 0.1); }
    
    .radar-wrapper { display: inline-block; margin-right: 10px; }
    .radar-emoji { font-size: 3rem; }
    .title-text { font-size: 3rem; font-weight: 900; color: white; }
    .ticker-container { background-color: #15181E; border-bottom: 2px solid #333; margin-bottom: 20px; }
    .ticker-move-1 { display: inline-block; padding-left: 100%; animation: ticker 120s linear infinite; }
    @keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-100%, 0, 0); } }
    .legal-footer { font-size: 0.75rem; color: #777; margin-top: 50px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [5] UI 구성
# ------------------------------------------------------------------
# 티커 데이터
market_pool = ["아이폰 15 Pro", "갤럭시 S24 울트라", "닌텐도 스위치", "PS5", "맥북프로 M3", "RTX 4070"]
market_str = "   ".join([f"🔥 {item}" for item in market_pool])

st.markdown(f"""
<div class="ticker-container">
    <div style="white-space: nowrap; overflow: hidden; padding: 10px 0;">
        <div class="ticker-move-1">
            <span style="color:#eee; font-weight:bold;">{market_str}   {market_str}   {market_str}</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# 사이드바
with st.sidebar:
    st.header("⚙️ 레이더 센터")
    with st.expander("👀 커뮤니티 바로가기", expanded=True):
        st.markdown("- [📷 SLR클럽](http://www.slrclub.com)\n- [🔥 퀘이사존](https://quasarzone.com)")
    st.write("---")
    usd, jpy = get_exchange_rates()
    st.markdown(f"**💵 환율 정보**\n- USD: {usd:,.0f}원\n- JPY: {jpy:,.0f}원 (100엔)")
    st.write("---")
    st.link_button("🚨 더치트 조회", "https://thecheat.co.kr", type="primary", use_container_width=True)

# 메인 헤더
st.markdown("""
    <div style="text-align:center; margin-bottom:30px;">
        <div class="radar-wrapper"><span class="radar-emoji">📡</span></div>
        <span class="title-text">매물레이더</span>
    </div>
""", unsafe_allow_html=True)

col_left, col_right = st.columns([0.6, 0.4], gap="large")

with col_left:
    keyword = st.text_input("검색어 입력", placeholder="예: 아이폰 15, 갤럭시 S24", label_visibility="collapsed")

    if keyword:
        safe_kw = html.escape(keyword)
        enc_kw = urllib.parse.quote(keyword)
        eng_kw = get_translated_keyword(keyword, 'en')
        jp_kw = get_translated_keyword(keyword, 'ja')
        
        st.success(f"📡 '{safe_kw}' 스캔 완료! (En: {eng_kw} / Jp: {jp_kw})")

        c1, c2 = st.columns(2)
        c1.link_button("⚡ 번개장터", f"https://m.bunjang.co.kr/search/products?q={enc_kw}", use_container_width=True)
        c2.link_button("🥕 당근마켓", f"https://www.daangn.com/search/{enc_kw}", use_container_width=True)
        
        c3, c4 = st.columns(2)
        c3.link_button("🌵 중고나라", f"https://web.joongna.com/search?keyword={enc_kw}", use_container_width=True)
        c4.link_button("🇺🇸 eBay", f"https://www.ebay.com/sch/i.html?_nkw={urllib.parse.quote(eng_kw)}", use_container_width=True)
    else:
        st.info("👆 상품명을 입력하면 3단계 심층 스캔을 시작합니다.")

with col_right:
    st.markdown("#### 📉 52주 시세 트렌드")
    
    # 데이터 로드 및 매칭
    df = load_price_data()
    trend_data = get_trend_data_from_sheet(keyword, df)
    
    if trend_data:
        st.caption(f"✅ 모델명: {trend_data['name']}")
        
        # 차트 데이터 생성
        chart_df = pd.DataFrame({
            "날짜": trend_data['dates'],
            "평균시세(만원)": trend_data['prices']
        })
        
        # 라인 차트 그리기
        st.line_chart(chart_df, x="날짜", y="평균시세(만원)", color="#00ff88", height=250)
        
        # 요약 정보
        last_price = trend_data['prices'][-1]
        st.markdown(f"**💰 현재 시세: {last_price:,.0f}만원**")
    else:
        if keyword:
            st.warning("📉 시세 데이터가 없습니다. (정확한 모델명을 입력해보세요)")
        else:
            st.info("검색어를 입력하면 시세 그래프가 나타납니다.")

st.markdown('<div class="legal-footer">Copyright © 2026 MaeMulRadar. All Rights Reserved.</div>', unsafe_allow_html=True)
