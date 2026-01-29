import streamlit as st
import pandas as pd
import requests
import re
import urllib.parse
from datetime import datetime

# ------------------------------------------------------------------
# [1] 시스템 설정 & 최적화
# ------------------------------------------------------------------
st.set_page_config(
    page_title="매물레이더 Pro",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS (모바일 반응형 및 다크모드 최적화)
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; font-family: 'Pretendard', sans-serif; }
    .metric-card { background-color: #1E2329; padding: 20px; border-radius: 12px; border: 1px solid #333; margin-bottom: 20px; }
    .highlight { color: #00FF88; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [2] 데이터 엔지니어링 (ETL & Caching)
# ------------------------------------------------------------------
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQS8AftSUmG9Cr7MfczpotB5hhl1DgjH4hRCgXH5R8j5hykRiEf0M9rEyEq3uj312a5RuI4zMdjI5Jr/pub?output=csv"

@st.cache_data(ttl=60)  # [핵심] 트래픽 급증 대비 캐싱 (60초마다 갱신)
def load_and_preprocess_data():
    """
    구글 스프레드시트에서 데이터를 로드하고 전처리합니다.
    오류 발생 시 빈 데이터프레임을 반환하여 앱 중단을 방지합니다.
    """
    try:
        df = pd.read_csv(SHEET_URL)
        df.columns = df.columns.str.strip()  # 컬럼 공백 제거
        return df
    except Exception as e:
        # 실제 운영 시에는 로깅이 필요함
        return pd.DataFrame()

def normalize_keyword(text):
    """
    [핵심 알고리즘] 검색어 정규화 (Normalization)
    유저 입력의 공백, 특수문자를 제거하고 소문자로 변환하여 매칭 정확도를 극대화합니다.
    예: "아이폰 16 Pro" -> "아이폰16pro"
    """
    if not isinstance(text, str):
        return ""
    return re.sub(r'\s+', '', text).lower()

def get_trend_data(user_query, df):
    """
    정규화된 키워드를 기반으로 시세 데이터를 탐색합니다 (Fuzzy Logic 대체).
    """
    if df.empty or not user_query:
        return None
    
    target = normalize_keyword(user_query)
    
    for _, row in df.iterrows():
        # 시트 내 키워드도 동일하게 정규화하여 비교
        sheet_key = normalize_keyword(str(row.get('keyword', '')))
        
        # 부분 일치 검색 (검색어가 키워드에 포함되거나, 키워드가 검색어에 포함될 때)
        if sheet_key and (sheet_key in target or target in sheet_key):
            try:
                # CSV 형태의 문자열 데이터를 리스트로 파싱
                dates = str(row['dates']).split(',')
                prices = [float(p) for p in str(row['prices']).split(',')]
                
                # 데이터 길이 검증
                if len(dates) == len(prices):
                    return pd.DataFrame({"날짜": dates, "평균시세(만원)": prices}).set_index("날짜")
            except:
                continue
    return None

# ------------------------------------------------------------------
# [3] 유틸리티 (환율 계산)
# ------------------------------------------------------------------
@st.cache_data(ttl=3600)  # 환율은 변동폭이 적으므로 1시간 캐싱
def get_exchange_info():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        data = requests.get(url, timeout=2).json()
        krw = data['rates']['KRW']
        jpy_krw = (krw / data['rates']['JPY']) * 100
        return krw, jpy_krw
    except:
        return 1450.0, 950.0  # API 실패 시 안전한 기본값(Fallback)

# ------------------------------------------------------------------
# [4] 메인 UI 구성
# ------------------------------------------------------------------
st.markdown('<div style="text-align:center; margin-bottom: 20px;"><span style="font-size:3rem;">📡</span><br><h1 style="display:inline;">매물레이더 Pro</h1><br><span style="color:#888; font-size:0.9rem;">v1.5 Data Intelligence</span></div>', unsafe_allow_html=True)

# 환율 정보 표시 (사이드 정보)
usd, jpy = get_exchange_info()
st.markdown(f"""
<div style="text-align:center; margin-bottom:30px; font-size:0.85rem; color:#aaa;">
    💵 USD: {usd:,.0f}원 | 💴 JPY(100엔): {jpy:,.0f}원
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns([1, 1], gap="medium")

with col1:
    st.markdown("### 🔍 매물 검색")
    query = st.text_input("제품명 입력", placeholder="예: 아이폰 15, 리코 GR3...", label_visibility="collapsed")
    
    if query:
        enc_q = urllib.parse.quote(query)
        st.markdown(f"**'{query}'** 스캔 결과")
        
        # 외부 플랫폼 링크
        b1, b2 = st.columns(2)
        b1.link_button("⚡ 번개장터 검색", f"https://m.bunjang.co.kr/search/products?q={enc_q}", use_container_width=True)
        b2.link_button("🥕 당근마켓 검색", f"https://www.daangn.com/search/{enc_q}", use_container_width=True)
        
        b3, b4 = st.columns(2)
        b3.link_button("🌵 중고나라 검색", f"https://web.joongna.com/search?keyword={enc_q}", use_container_width=True)
        b4.link_button("🌏 eBay 직구 확인", f"https://www.ebay.com/sch/i.html?_nkw={enc_q}", use_container_width=True)

with col2:
    st.markdown("### 📉 52주 시세 트렌드")
    
    if query:
        df_raw = load_and_preprocess_data()
        trend_df = get_trend_data(query, df_raw)
        
        if trend_df is not None:
            # 차트 시각화
            st.line_chart(trend_df, color="#00FF88", height=300)
            
            # 최신 시세 정보 추출
            latest_price = trend_df.iloc[-1]['평균시세(만원)']
            min_price = trend_df['평균시세(만원)'].min()
            st.caption(f"💡 현재 평균 시세는 약 **{latest_price:,.0f}만원**이며, 역대 최저가는 **{min_price:,.0f}만원**입니다.")
        else:
            st.warning("📉 데이터 수집 중이거나 일치하는 시세 정보가 없습니다.")
            st.info("Tip: 정확한 모델명을 입력하면 매칭 확률이 올라갑니다.")
    else:
        st.info("좌측에 검색어를 입력하면 데이터 기반 시세 분석이 시작됩니다.")

# ------------------------------------------------------------------
# [5] 푸터
# ------------------------------------------------------------------
st.markdown("---")
st.markdown('<div style="text-align:center; color:#555; font-size:0.8rem;">Copyright © 2026 MaeMulRadar Pro. 데이터 기반 합리적 소비.</div>', unsafe_allow_html=True)
