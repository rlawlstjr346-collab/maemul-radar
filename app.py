import streamlit as st
import urllib.parse
import requests
import re
import random
import pandas as pd
import google.generativeai as genai
from datetime import datetime, timedelta
import html

# ------------------------------------------------------------------
# [AI 설정] 보안을 위해 st.secrets 방식을 사용합니다.
# ------------------------------------------------------------------
try:
    # 3,000명 규모 대응을 위한 보안 설정
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # 비용 절감을 위해 Flash 모델을 기본으로 사용합니다.
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error("설정(Secrets)에서 GEMINI_API_KEY를 찾을 수 없습니다. 관리자 페이지를 확인해주세요.")

# ------------------------------------------------------------------
# [1] 앱 기본 설정
# ------------------------------------------------------------------
st.set_page_config(page_title="매물레이더 Pro", page_icon="📡", layout="wide")

# ------------------------------------------------------------------
# [2] 데이터 관리 및 유틸리티
# ------------------------------------------------------------------
sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQS8AftSUmG9Cr7MfczpotB5hhl1DgjH4hRCgXH5R8j5hykRiEf0M9rEyEq3uj312a5RuI4zMdjI5Jr/pub?output=csv"

@st.cache_data(ttl=60)
def load_price_data():
    try:
        df = pd.read_csv(sheet_url)
        df.columns = df.columns.str.strip()
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_ai_analysis(keyword):
    prompt = f"중고거래 전문가로서 '{keyword}'의 현재 한국 중고 시세와 구매 시 주의점 2가지를 3줄로 요약해줘."
    return model.generate_content(prompt).text

def get_translated_keyword(text, target_lang='en'):
    if not re.search('[가-힣]', text): return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ko&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
        return requests.get(url, timeout=1).json()[0][0][0]
    except: return text

# ------------------------------------------------------------------
# [3] UI 스타일링
# ------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; font-family: 'Pretendard', sans-serif; }
    .ai-box { background-color: rgba(0, 255, 136, 0.05); border: 1px solid #00ff88; padding: 20px; border-radius: 15px; margin-bottom: 20px; }
    .signal-banner { background: linear-gradient(90deg, #0A84FF 0%, #0055FF 100%); color: white; padding: 15px; border-radius: 12px; margin-bottom: 20px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [4] 메인 화면
# ------------------------------------------------------------------
st.markdown('<div style="text-align:center; margin-bottom:30px;"><span style="font-size:3rem; font-weight:900;">📡 매물레이더 Pro</span></div>', unsafe_allow_html=True)

col_left, col_right = st.columns([0.6, 0.4], gap="large")

with col_left:
    keyword = st.text_input("찾으시는 물건을 입력하세요", placeholder="예: 아이폰 15 Pro", label_visibility="collapsed")

    if keyword:
        # AI 분석 가이드
        st.markdown('<div class="ai-box">', unsafe_allow_html=True)
        st.markdown('<h3 style="color:#00ff88; margin-top:0;">🤖 Gemini 실시간 전문가 분석</h3>', unsafe_allow_html=True)
        with st.spinner("AI가 분석 중입니다..."):
            try:
                st.write(get_ai_analysis(keyword))
            except: st.write("AI 분석 엔진 준비 중입니다. 잠시 후 다시 시도해주세요.")
        st.markdown('</div>', unsafe_allow_html=True)

        # 검색 링크 섹션
        encoded_kor = urllib.parse.quote(keyword)
        st.markdown(f'### 🔥 "{keyword}" 스캔 결과')
        c1, c2 = st.columns(2)
        c1.link_button("⚡ 번개장터", f"https://m.bunjang.co.kr/search/products?q={encoded_kor}", use_container_width=True)
        c2.link_button("🥕 당근마켓", f"https://www.daangn.com/search/{encoded_kor}", use_container_width=True)
        
        c3, c4 = st.columns(2)
        c3.link_button("🌵 중고나라", f"https://web.joongna.com/search?keyword={encoded_kor}", use_container_width=True)
        eng_k = get_translated_keyword(keyword, 'en')
        c4.link_button(f"🇺🇸 eBay ({eng_k})", f"https://www.ebay.com/sch/i.html?_nkw={urllib.parse.quote(eng_k)}", use_container_width=True)

with col_right:
    st.markdown("#### 📉 52주 시세 트렌드")
    df_prices = load_price_data()
    # 기존 시세 로직 유지
    st.info("좌측에 검색어를 입력하면 데이터 기반 시세가 나타납니다.")

st.markdown('<div style="text-align:center; margin-top:50px; color:#888; font-size:0.8rem;">Copyright © 2026 MaeMulRadar. 거래 책임은 본인에게 있습니다.</div>', unsafe_allow_html=True)
