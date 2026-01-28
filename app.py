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
    if not re.search('[가-힣]', text): return text
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
st.markdown("""<style>/* 생략: 기존 CSS 그대로 */</style>""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [5~6] 상단 티커 + 사이드바
# ------------------------------------------------------------------
# ⚠️ 여긴 네 기존 코드 그대로라 생략 (실제 파일에서는 그대로 둬)

# ------------------------------------------------------------------
# [7] 메인 화면
# ------------------------------------------------------------------
col_left, col_right = st.columns([0.6, 0.4], gap="large")

with col_left:
    keyword = st.text_input(
        "검색어 입력",
        placeholder="🔍 찾으시는 물건을 입력하세요",
        label_visibility="collapsed"
    )

with col_right:
    st.markdown("#### 📉 52주 시세 트렌드")

    df_prices = load_price_data()
    matched_data = get_trend_data_from_sheet(keyword, df_prices)

    if matched_data:
        st.caption(f"✅ '{matched_data['name']}' 데이터 확인됨")

        # -------------------------
        # 1️⃣ 기존 선 그래프 (유지)
        # -------------------------
        df_trend = pd.DataFrame({
            "날짜": matched_data["dates"],
            "가격": matched_data["prices"]
        })
        st.line_chart(df_trend, x="날짜", y="가격", height=200)
        st.caption("※ 운영자가 수집한 실거래가 기준")

        # -------------------------
        # 2️⃣ 🔥 가격 분포 히스토그램
        # -------------------------
        st.markdown("#### 📊 가격 분포 (실거래 집중 구간)")

        BIN_SIZE = 50000  # 5만원 단위
        prices = pd.Series(matched_data["prices"])

        bins = range(
            int(prices.min() // BIN_SIZE * BIN_SIZE),
            int(prices.max() // BIN_SIZE * BIN_SIZE + BIN_SIZE),
            BIN_SIZE
        )

        hist = pd.cut(prices, bins=bins)
        hist_df = hist.value_counts().sort_index().reset_index()
        hist_df.columns = ["가격 구간", "매물 수"]

        st.bar_chart(hist_df, x="가격 구간", y="매물 수", height=180)

        top_bin = hist_df.iloc[hist_df["매물 수"].idxmax()]["가격 구간"]
        st.caption(f"📌 매물이 가장 많이 몰린 구간: **{top_bin}**")

    else:
        if keyword:
            st.warning("⚠️ 해당 키워드의 시세 데이터가 없습니다.")
        else:
            st.info("좌측에서 검색어를 입력하세요.")
