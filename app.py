import streamlit as st
import urllib.parse
import requests
import re
import random
import time
import pandas as pd
from datetime import datetime, timedelta
import html
import altair as alt   # ★ FIX: 컬러 유지용

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

def get_translated_keyword(text, target_lang='en'):
    if not re.search('[가-힣]', text): 
        return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ko&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
        response = requests.get(url, timeout=1)
        if response.status_code == 200:
            return response.json()[0][0][0]
    except:
        pass
    return text

def get_trend_data_from_sheet(user_query, df):
    if df.empty or not user_query:
        return None

    user_clean = user_query.lower().replace(" ", "").strip()

    for _, row in df.iterrows():
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
# [4] CSS (원본 그대로)
# ------------------------------------------------------------------
st.markdown("""<style>/* CSS 원본 그대로 */</style>""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [5] 상단 티커
# ------------------------------------------------------------------
market_pool = ["아이폰 15 Pro", "갤럭시 S24 울트라", "에어팟 맥스", "닌텐도 스위치", "소니 헤드폰", "PS5", "맥북프로 M3", "RTX 4070", "아이패드 에어", "스투시 후드", "나이키 덩크"]
radar_pool = ["후지필름 X100V", "리코 GR3", "치이카와", "뉴진스 포카", "젠틀몬스터", "요시다포터", "살로몬 XT-6", "코닥 작티", "산리오 키링", "다마고치", "티니핑"]

market_str = "".join([f"<span>{item}</span>" for item in random.sample(market_pool, 10)])
radar_str = "".join([f"<span>{item}</span>" for item in random.sample(radar_pool, 10)])
now_time = st.session_state.ticker_data['time']

st.markdown(f"""
<div class="ticker-container">
    <div class="ticker-line">{market_str}</div>
    <div class="ticker-line">{radar_str}</div>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [6] 메인 화면
# ------------------------------------------------------------------
col_left, col_right = st.columns([0.6, 0.4], gap="large")

with col_left:
    keyword = st.text_input("검색어 입력", placeholder="예: 아이폰15")

with col_right:
    st.markdown("#### 📉 52주 시세 트렌드")

    df_prices = load_price_data()
    matched_data = get_trend_data_from_sheet(keyword, df_prices)

    if matched_data:
        df_trend = pd.DataFrame({
            "날짜": matched_data["dates"],
            "가격(만원)": matched_data["prices"]
        })

        # ★ FIX: 컬러 유지 + 웹 안정화
        chart = (
            alt.Chart(df_trend)
            .mark_line(color="#00ff88", strokeWidth=3)
            .encode(
                x=alt.X("날짜:N", title=None),
                y=alt.Y("가격(만원):Q", title=None)
            )
            .properties(height=200)
        )

        st.altair_chart(chart, use_container_width=True)
        st.caption("※ 운영자가 직접 검수한 실거래 평균가입니다.")
    else:
        st.info("좌측에 검색어를 입력하면 시세 그래프가 나타납니다.")
