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

def get_translated_keyword(text, target_lang='en'):
    if not re.search('[가-힣]', text): return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ko&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            result = response.json()[0][0][0]
            if result and result.strip(): return result
    except: pass
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
# ... 기존 CSS 그대로 유지 ...

# ------------------------------------------------------------------
# [5] 상단 티커
# ------------------------------------------------------------------
# ... 기존 티커 코드 그대로 유지 ...

# ------------------------------------------------------------------
# [6] 사이드바
# ------------------------------------------------------------------
# ... 기존 사이드바 코드 그대로 유지 ...

# ------------------------------------------------------------------
# [7] 메인 화면
# ------------------------------------------------------------------
# ... 검색어 입력 및 국내/해외 링크 등 기존 코드 그대로 유지 ...

with col_right:
    st.markdown("#### 📉 52주 시세 트렌드")
    df_prices = load_price_data()
    matched_data = get_trend_data_from_sheet(keyword, df_prices)
    
    if matched_data:
        st.caption(f"✅ '{matched_data['name']}' 데이터 확인됨")
        
        df_trend = pd.DataFrame({
            "날짜": matched_data["dates"],
            "가격": matched_data["trend_prices"]
        })
        
        df_dist = pd.DataFrame({
            "가격": matched_data["raw_prices"]
        })

        # 🔹 여기서 가격 분포 정상화 처리 (안전하게 추가)
        df_dist['가격'] = pd.to_numeric(df_dist['가격'], errors='coerce')
        df_dist = df_dist.dropna(subset=['가격'])

        tab_trend, tab_dist = st.tabs(["📈 시세 흐름", "📊 가격 분포도"])

        with tab_trend:
            if not df_trend.empty:
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
                mean_val = df_dist['가격'].mean()
                bars = alt.Chart(df_dist).mark_bar(
                    color='#0A84FF', cornerRadiusTopLeft=3, cornerRadiusTopRight=3
                ).encode(
                    x=alt.X('가격:Q', bin=alt.Bin(maxbins=20), title='가격 구간 (만원)'),
                    y=alt.Y('count()', title='매물 수'),
                    tooltip=[alt.Tooltip('count()', title='매물 수')]
                )

                rule = alt.Chart(pd.DataFrame({'mean_price': [mean_val]})).mark_rule(
                    color='red', strokeDash=[4, 4]
                ).encode(x='mean_price:Q')

                final_chart = (bars + rule).properties(height=250).configure_axis(
                    grid=False, labelColor='#eee', titleColor='#eee'
                ).configure_view(strokeWidth=0)

                st.altair_chart(final_chart, use_container_width=True)
                p_min = df_dist['가격'].min()
                p_max = df_dist['가격'].max()

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
