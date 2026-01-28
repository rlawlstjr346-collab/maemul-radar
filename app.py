import streamlit as st
import urllib.parse
import requests
import re
import random
import time
import pandas as pd
import google.generativeai as genai  # [AI 추가]
from datetime import datetime, timedelta
import html

# ------------------------------------------------------------------
# [AI 설정] Gemini 1.5 Pro 엔진 도킹
# ------------------------------------------------------------------
# 사장님의 API 키를 여기에 입력하세요
genai.configure(api_key="YOUR_API_KEY_HERE")
model = genai.GenerativeModel('gemini-1.5-pro')

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
# [4] CSS 스타일링
# ------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; font-family: 'Pretendard', sans-serif; }
    [data-testid="stSidebar"] { background-color: #17191E; border-right: 1px solid #333; }
    div[data-baseweb="input"] {
        background-color: #262730; border: 2px solid #00ff88 !important; border-radius: 8px; 
        box-shadow: 0 0 10px rgba(0, 255, 136, 0.15); transition: all 0.3s ease;
    }
    .stTextInput input { color: #FAFAFA; font-weight: bold; }
    div[data-testid="stLinkButton"] > a { border-radius: 10px; font-weight: 700; transition: all 0.3s ease; text-decoration: none; }
    .signal-banner { background: linear-gradient(90deg, #0A84FF 0%, #0055FF 100%); color: white !important; padding: 15px 20px; border-radius: 12px; margin-bottom: 25px; font-weight: bold; display: flex; align-items: center; }
    .ai-box { background-color: rgba(0, 255, 136, 0.05); border: 1px solid #00ff88; padding: 20px; border-radius: 15px; margin: 20px 0; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [5] 상단 티커
# ------------------------------------------------------------------
market_pool = ["아이폰 15 Pro", "갤럭시 S24 울트라", "에어팟 맥스", "닌텐도 스위치", "소니 헤드폰", "PS5"]
radar_pool = ["후지필름 X100V", "리코 GR3", "치이카와", "뉴진스 포카", "젠틀몬스터"]

market_str = "".join([f"<span>{item}</span>" for item in random.sample(market_pool, 5)])
now_time = st.session_state.ticker_data['time']
st.markdown(f'<div class="ticker-container"><div class="ticker-line"><div class="ticker-move-1">{market_str}</div></div></div>', unsafe_allow_html=True)

# ------------------------------------------------------------------
# [6] 사이드바 (원본 기능 전체 포함)
# ------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 레이더 센터")
    usd_rate, jpy_rate = get_exchange_rates()
    st.write(f"💵 환율: {usd_rate:,.1f}원")
    st.link_button("🚨 사기피해 조회 (더치트)", "https://thecheat.co.kr", type="primary", use_container_width=True)

# ------------------------------------------------------------------
# [7] 메인 화면
# ------------------------------------------------------------------
st.markdown('<div style="text-align:center;"><span style="font-size:3rem;">📡</span><br><span style="font-size:3rem; font-weight:900;">매물레이더</span></div>', unsafe_allow_html=True)

col_left, col_right = st.columns([0.6, 0.4], gap="large")

with col_left:
    keyword = st.text_input("검색어 입력", placeholder="🔍 찾으시는 물건을 입력하세요", label_visibility="collapsed")

    if keyword:
        # [AI 분석 섹션 - 가장 먼저 출력하여 체류시간 확보]
        st.markdown('<div class="ai-box">', unsafe_allow_html=True)
        st.markdown('<h3 style="color:#00ff88; margin-top:0;">🤖 Gemini Pro 실시간 매물 분석</h3>', unsafe_allow_html=True)
        with st.spinner("Gemini Pro가 시장 데이터를 정밀 스캔 중입니다..."):
            try:
                prompt = f"중고거래 전문가로서 '{keyword}'의 현재 한국 중고 시세와 구매 시 반드시 체크해야 할 주의점을 3줄로 전문성 있게 요약해줘."
                response = model.generate_content(prompt)
                st.write(response.text)
            except:
                st.write("AI 엔진 연결 중입니다. 잠시 후 다시 시도해주세요.")
        st.markdown('</div>', unsafe_allow_html=True)

        # 기존 검색 결과 섹션
        encoded_kor = urllib.parse.quote(keyword)
        st.markdown(f'### 🔥 "{keyword}" 스캔 결과')
        c1, c2 = st.columns(2)
        c1.link_button("⚡ 번개장터", f"https://m.bunjang.co.kr/search/products?q={encoded_kor}", use_container_width=True)
        c2.link_button("🥕 당근마켓", f"https://www.daangn.com/search/{encoded_kor}", use_container_width=True)
        
        # 해외 직구 섹션
        eng_keyword = get_translated_keyword(keyword, 'en')
        encoded_eng = urllib.parse.quote(eng_keyword)
        st.markdown(f'### ✈️ 해외 직구 (Auto: {eng_keyword})')
        c5, c6 = st.columns(2)
        c5.link_button(f"🇺🇸 eBay", f"https://www.ebay.com/sch/i.html?_nkw={encoded_eng}", use_container_width=True)

with col_right:
    st.markdown("#### 📉 52주 시세 트렌드")
    df_prices = load_price_data()
    matched_data = get_trend_data_from_sheet(keyword, df_prices)
    
    if matched_data:
        df_trend = pd.DataFrame({"날짜": matched_data["dates"], "가격(만원)": matched_data["prices"]})
        st.line_chart(df_trend, x="날짜", y="가격(만원)", color="#00ff88")
    else:
        st.info("좌측에 검색어를 입력하면 데이터 기반 시세가 나타납니다.")

# [8] 하단 푸터
st.markdown('<div class="legal-footer">Copyright © 2026 매물레이더(MaeMulRadar). All Rights Reserved.</div>', unsafe_allow_html=True)
