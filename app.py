 import streamlit as st

import urllib.parse

import requests

import re

import random

import time

from datetime import datetime, timedelta

import html


# ------------------------------------------------------------------

# [1] 앱 기본 설정

# ------------------------------------------------------------------

st.set_page_config(

    page_title="매물레이더",

    page_icon="📡",

    layout="wide",

    initial_sidebar_state="expanded"

)


# ------------------------------------------------------------------

# [2] 세션 및 데이터 관리

# ------------------------------------------------------------------

market_pool = [

    "아이폰 15 Pro", "갤럭시 S24 울트라", "에어팟 맥스", "닌텐도 스위치 OLED", 

    "소니 WH-1000XM5", "플레이스테이션 5", "아이패드 에어 5", "애플워치 울트라 2",

    "스투시 월드투어", "아크테릭스 베타 LT", "나이키 덩크 로우 범고래", "조던 1 시카고",

    "다이슨 에어랩", "LG 스탠바이미", "후지필름 X100V", "리코 GR3",

    "샤넬 빈티지 백", "루이비통 지갑", "구찌 마몬트", "프라다 호보백",

    "롤렉스 서브마리너", "오메가 스피드마스터", "까르띠에 탱크", "헬리녹스 체어원",

    "맥북프로 M3", "갤럭시 탭 S9", "아이폰 14 미니", "보스 QC 울트라", "마샬 스탠모어"

]


radar_pool = [

    "후지필름 X100VI", "리코 GR3x HDF", "코닥 작티", "캐논 익서스 100", 

    "올림푸스 뮤2", "소니 사이버샷 T2", "산리오 키링", "치이카와 하치와레", 

    "뉴진스 혜인 포카", "세븐틴 민규 포카", "젠틀몬스터 선글라스", "메종마르지엘라 지갑",

    "요시다포터 탱커", "슈프림 캠프캡", "헌터 레인부츠", "살로몬 XT-6", 

    "아이팟 클래식 7세대", "맥북프로 M4 사전예약", "라이카 Q3", "오즈모 포켓3",

    "비비안웨스트우드 목걸이", "크롬하츠 반지", "프라이탁 하와이", "포켓몬빵 띠부씰",

    "인스타360 Ace Pro", "고프로 12", "드론 매빅3", "소니 A7C II", "망그러진곰 키링"

]


def generate_new_data():

    kst_now = datetime.now() + timedelta(hours=9)

    return {

        'market': random.sample(market_pool, 12),

        'radar': random.sample(radar_pool, 12),

        'time': kst_now.strftime("%Y-%m-%d %H:%M:%S")

    }


if 'ticker_data' not in st.session_state:

    st.session_state.ticker_data = generate_new_data()


if 'search_history' not in st.session_state:

    st.session_state.search_history = []

if 'memo_pad' not in st.session_state:

    st.session_state.memo_pad = ""


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


def get_english_keyword(text):

    if not re.search('[가-힣]', text): return text

    try:

        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ko&tl=en&dt=t&q={urllib.parse.quote(text)}"

        response = requests.get(url, timeout=1)

        if response.status_code == 200: return response.json()[0][0][0]

    except: pass

    return text


# ------------------------------------------------------------------

# [4] CSS 스타일링 (Cyber-HUD + Brand Colors)

# ------------------------------------------------------------------

st.markdown("""

<style>

    /* 기본 테마 */

    .stApp { background-color: #0E1117; color: #FAFAFA; font-family: 'Pretendard', sans-serif; }

    [data-testid="stSidebar"] { background-color: #17191E; border-right: 1px solid #333; }

    

    /* ▼▼▼ [수정됨] 입력창 스타일 (항상 초록색 테두리 + 발광) ▼▼▼ */

    div[data-baseweb="input"] {

        background-color: #262730; 

        border: 2px solid #00ff88 !important; /* 두께 2px, 항상 초록색 */

        border-radius: 8px; 

        box-shadow: 0 0 10px rgba(0, 255, 136, 0.15); /* 은은한 네온 발광 */

        transition: all 0.3s ease;

    }

    div[data-baseweb="input"]:focus-within {

        box-shadow: 0 0 15px rgba(0, 255, 136, 0.5); /* 클릭하면 더 밝게 발광 */

    }

    .stTextInput input, .stTextArea textarea, .stNumberInput input { color: #FAFAFA; font-weight: bold; }


    /* 링크 버튼 기본 스타일 */

    div[data-testid="stLinkButton"] > a {

        border-radius: 10px; font-weight: 700; transition: all 0.3s ease; text-decoration: none;

    }


    /* --- [PLATFORM BRAND COLORS] --- */

    div[data-testid="stLinkButton"] > a[href*="bunjang"] { border: 1px solid #FF3E3E !important; color: #FF3E3E !important; background-color: rgba(255, 62, 62, 0.1); }

    div[data-testid="stLinkButton"] > a[href*="bunjang"]:hover { background-color: #FF3E3E !important; color: white !important; box-shadow: 0 0 15px rgba(255, 62, 62, 0.6); }


    div[data-testid="stLinkButton"] > a[href*="daangn"] { border: 1px solid #FF8A3D !important; color: #FF8A3D !important; background-color: rgba(255, 138, 61, 0.1); }

    div[data-testid="stLinkButton"] > a[href*="daangn"]:hover { background-color: #FF8A3D !important; color: white !important; box-shadow: 0 0 15px rgba(255, 138, 61, 0.6); }


    div[data-testid="stLinkButton"] > a[href*="joongna"] { border: 1px solid #00E676 !important; color: #00E676 !important; background-color: rgba(0, 230, 118, 0.1); }

    div[data-testid="stLinkButton"] > a[href*="joongna"]:hover { background-color: #00E676 !important; color: black !important; box-shadow: 0 0 15px rgba(0, 230, 118, 0.6); }


    div[data-testid="stLinkButton"] > a[href*="fruitsfamily"] { border: 1px solid #D500F9 !important; color: #D500F9 !important; background-color: rgba(213, 0, 249, 0.1); }

    div[data-testid="stLinkButton"] > a[href*="fruitsfamily"]:hover { background-color: #D500F9 !important; color: white !important; box-shadow: 0 0 15px rgba(213, 0, 249, 0.6); }


    div[data-testid="stLinkButton"] > a[href*="ebay"] { border: 1px solid #2962FF !important; color: #2962FF !important; background-color: rgba(41, 98, 255, 0.1); }

    div[data-testid="stLinkButton"] > a[href*="ebay"]:hover { background-color: #2962FF !important; color: white !important; box-shadow: 0 0 15px rgba(41, 98, 255, 0.6); }


    div[data-testid="stLinkButton"] > a[href*="mercari"] { border: 1px solid #EEEEEE !important; color: #EEEEEE !important; background-color: rgba(238, 238, 238, 0.1); }

    div[data-testid="stLinkButton"] > a[href*="mercari"]:hover { background-color: #EEEEEE !important; color: #000000 !important; box-shadow: 0 0 15px rgba(238, 238, 238, 0.6); }


    /* 사기피해 조회 (Red Style) */

    div[data-testid="stLinkButton"] > a[href*="thecheat"] { 

        border: 1px solid #ff4b4b !important; 

        color: #ff4b4b !important; 

        background-color: rgba(255, 75, 75, 0.1) !important; 

    }

    div[data-testid="stLinkButton"] > a[href*="thecheat"]:hover { 

        background-color: #ff4b4b !important; 

        color: white !important; 

        box-shadow: 0 0 15px rgba(255, 75, 75, 0.6) !important; 

    }


    /* 재가동(Scan) 버튼 */

    div.stButton > button {

        background-color: #262730; border: 1px solid #00ff88; color: #00ff88;

        border-radius: 5px; font-size: 0.8rem; padding: 0.2rem 0.5rem; height: auto; width: 100%; transition: all 0.3s ease;

    }

    div.stButton > button:hover {

        background-color: #00ff88; color: #000000; box-shadow: 0 0 10px rgba(0, 255, 136, 0.6); border-color: #00ff88;

    }


    /* 기타 스타일 */

    button[data-baseweb="tab"] { color: #888; font-weight: bold; }

    button[data-baseweb="tab"][aria-selected="true"] { color: #00ff88 !important; background-color: transparent !important; border-bottom-color: #00ff88 !important; border-bottom-width: 3px !important; }


    .ticker-container { width: 100%; background-color: #15181E; border-bottom: 2px solid #333; margin-bottom: 20px; display: flex; flex-direction: column; }

    .ticker-line { width: 100%; overflow: hidden; white-space: nowrap; padding: 8px 0; border-bottom: 1px solid #222; }

    .ticker-move-1 { display: inline-block; padding-left: 100%; animation: ticker 200s linear infinite; }

    .ticker-move-2 { display: inline-block; padding-left: 100%; animation: ticker 250s linear infinite; }

    .ticker-line span { margin-right: 40px; font-size: 0.9rem; font-family: sans-serif; }

    .label-market { color: #ff4b4b; font-weight: 900; margin-right: 15px !important; }

    .label-radar { color: #00ff88; font-weight: 900; margin-right: 15px !important; }

    .rank-num { color: #888; font-size: 0.8rem; margin-right: 4px; }

    .item-text { color: #eee; font-weight: 600; }

    @keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-100%, 0, 0); } }


    .radar-wrapper { position: relative; display: inline-block; margin-right: 10px; vertical-align: middle; }

    .radar-emoji { position: relative; z-index: 2; font-size: 3rem; }

    .pulse-ring { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 100%; height: 100%; border-radius: 50%; border: 2px solid rgba(255, 255, 255, 0.7); opacity: 0; animation: pulse-ring 2s infinite; }

    @keyframes pulse-ring { 0% { width: 90%; opacity: 1; } 100% { width: 220%; opacity: 0; } }

    .title-text { font-size: 3rem; font-weight: 900; color: #FFFFFF !important; letter-spacing: -1px; }

    

    .radar-dot-idle { display: inline-block; width: 12px; height: 12px; background-color: #34c759; border-radius: 50%; margin-right: 8px; vertical-align: middle; animation: pulse-idle 2s infinite; }

    @keyframes pulse-idle { 0% { box-shadow: 0 0 0 0 rgba(52, 199, 89, 0.7); } 70% { box-shadow: 0 0 0 10px rgba(52, 199, 89, 0); } 100% { box-shadow: 0 0 0 0 rgba(52, 199, 89, 0); } }

    

    .signal-banner { background: linear-gradient(90deg, #0A84FF 0%, #0055FF 100%); color: white !important; padding: 15px 20px; border-radius: 12px; margin-bottom: 25px; font-weight: bold; font-size: 1rem; display: flex; align-items: center; box-shadow: 0 4px 15px rgba(10, 132, 255, 0.3); }

    .radar-dot-strong { display: inline-block; width: 12px; height: 12px; background-color: white; border-radius: 50%; margin-right: 12px; animation: pulse-strong 1.5s infinite; }

    @keyframes pulse-strong { 0% { box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.7); } 50% { box-shadow: 0 0 0 10px rgba(255, 255, 255, 0); } 100% { box-shadow: 0 0 0 0 rgba(255, 255, 255, 0); } }

    

    .guide-badge { display: inline-block; background-color: #f8f9fa !important; color: #000000 !important; font-size: 0.9rem; padding: 6px 14px; border-radius: 15px; margin-bottom: 15px; font-weight: 800; }

    .tip-banner { background-color: #1e252b; color: #4da6ff; padding: 8px 20px; border-radius: 20px; font-size: 0.9rem; font-weight: 600; text-align: center; margin: 0 auto 25px auto; width: fit-content; border: 1px solid #0A84FF; }

    .side-util-header { font-size: 1rem; font-weight: bold; color: #0A84FF; margin-top: 5px; margin-bottom: 5px; border-left: 3px solid #0A84FF; padding-left: 8px; }

    .legal-footer { font-size: 0.75rem; color: #777; margin-top: 60px; padding: 30px 10px; border-top: 1px solid #333; text-align: center; line-height: 1.6; }

    .scam-alert-text { color: #ff4b4b; font-weight: bold; font-size: 0.85rem; margin-bottom: 5px; }

    .scam-desc { color: #aaa; font-size: 0.8rem; margin-bottom: 10px; line-height: 1.4; }

</style>

""", unsafe_allow_html=True)


# ------------------------------------------------------------------

# [5] 화면 구성: 상단 티커 및 레이아웃

# ------------------------------------------------------------------

current_data = st.session_state.ticker_data

market_str = "".join([f"<span><span class='rank-num'>{i}.</span><span class='item-text'>{item}</span></span>" for i, item in enumerate(current_data['market'], 1)])

radar_str = "".join([f"<span><span class='rank-num'>{i}.</span><span class='item-text'>{item}</span></span>" for i, item in enumerate(current_data['radar'], 1)])

now_time = current_data['time']


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


# ------------------------------------------------------------------

# [6] 왼쪽 사이드바 구성

# ------------------------------------------------------------------

with st.sidebar:

    st.header("⚙️ 레이더 센터")

    

    with st.expander("👀 커뮤니티 시세비교", expanded=True):

        st.markdown("""

        - [📷 SLR클럽 (카메라)](http://www.slrclub.com)

        - [💻 쿨엔조이 (PC/IT)](https://coolenjoy.net)

        - [🔥 퀘이사존 (PC/게임)](https://quasarzone.com)

        - [🍎 아사모 (애플)](https://cafe.naver.com/appleiphone)

        """)

    

    st.write("---")


    with st.expander("📦 배송 조회 레이더", expanded=True):

        track_no = st.text_input("운송장 번호", placeholder="- 없이 숫자만 입력")

        if track_no:

            url = f"https://search.naver.com/search.naver?query=운송장번호+{track_no}"

            st.link_button("🔍 택배사 자동 스캔 (조회)", url, use_container_width=True)

        else:

            st.caption("👇 편의점 택배 바로가기")

            col_t1, col_t2 = st.columns(2)

            col_t1.link_button("GS반값", "https://www.cvsnet.co.kr/reservation-tracking/tracking/index.do", use_container_width=True)

            col_t2.link_button("CU알뜰", "https://www.cupost.co.kr/postbox/delivery/local.cupost", use_container_width=True)


    st.write("---")

    

    usd_rate, jpy_rate = get_exchange_rates()

    with st.expander("💱 관세 안전선 계산기", expanded=True):

        tab1, tab2 = st.tabs(["🇺🇸 USD", "🇯🇵 JPY"])

        with tab1:

            st.caption(f"환율: {usd_rate:,.1f}원/$")

            p_usd = st.number_input("가격($)", value=190, step=10)

            krw_val = p_usd * usd_rate

            st.write(f"🇰🇷 약 {krw_val:,.0f} 원")

            if p_usd <= 200: st.success("✅ 안전 (면세)")

            else: st.error("🚨 관세 대상")

        with tab2:

            st.caption(f"환율: {jpy_rate:,.1f}원/100¥")

            p_jpy = st.number_input("가격(¥)", value=15000, step=1000)

            krw_val_j = p_jpy * (jpy_rate/100)

            st.write(f"🇰🇷 약 {krw_val_j:,.0f} 원")

            if (p_jpy * (jpy_rate/100) / usd_rate) <= 150: st.success("✅ 안전 (면세)")

            else: st.error("🚨 관세 대상")


    st.write("---")

    st.link_button("🚨 사기피해 조회 (더치트)", "https://thecheat.co.kr", type="primary", use_container_width=True)


    st.write("---")

    st.markdown("### 📢 Beta v1.0")

    st.caption("불편한 점이나 아이디어를 남겨주세요! (2주간 운영)")

    st.link_button("💬 개발자에게 피드백 보내기", "https://docs.google.com/forms/d/e/1FAIpQLSdZdfJLBErRw8ArXlBLqw9jkoLk0Qj-AOo0yPm-hg7KmGYOnA/viewform?usp=dialog", use_container_width=True)



# ------------------------------------------------------------------

# [7] 메인 화면 및 오른쪽 컬럼 구성

# ------------------------------------------------------------------

c_main, c_memo = st.columns([0.7, 0.3], gap="large")


with c_memo:

    st.markdown('<div class="side-util-header">📝 쇼핑 메모장</div>', unsafe_allow_html=True)

    memo_val = st.text_area(

        "memo",

        value=st.session_state.memo_pad,

        height=300,

        label_visibility="collapsed",

        placeholder="[비교 메모 예시]\n\n당근 아이패드: 40만\n번장 아이패드: 35만\n\n이베이 소니렌즈: $180\n(관세 안전 확인)\n\n*이곳에 자유롭게 메모하세요."

    )

    st.session_state.memo_pad = memo_val

    

    st.write("")

    

    st.markdown('<div class="side-util-header">💬 스마트 멘트 완성</div>', unsafe_allow_html=True)

    

    tab_m1, tab_m2 = st.tabs(["⚡️ 퀵 멘트", "💳 결제/직거래"])

    

    with tab_m1:

        st.caption("👇 상황을 선택하면 정중한 멘트가 완성됩니다.")

        quick_opt = st.radio("빠른 선택", ["👋 첫 인사 (구매 가능 여부)", "💸 가격 제안 (네고 요청)", "📦 택배비 포함 요청"], label_visibility="collapsed")

        

        if quick_opt == "👋 첫 인사 (구매 가능 여부)":

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


    st.write("")


    st.markdown('<div class="side-util-header">🚨 사기꾼 판독기 (유형별)</div>', unsafe_allow_html=True)

    with st.expander("👮‍♂️ 필수 체크 (클릭해서 확인)", expanded=False):

        st.markdown('<div class="scam-alert-text">1. 카톡 아이디 거래 유도</div>', unsafe_allow_html=True)

        st.markdown('<div class="scam-desc">"카톡으로 대화해요" → 99.9% 사기입니다. 앱 내 채팅만 이용하세요.</div>', unsafe_allow_html=True)

        st.markdown('<div class="scam-alert-text">2. 가짜 안전결제 링크</div>', unsafe_allow_html=True)

        st.markdown('<div class="scam-desc">http://... 로 시작하거나 도메인이 다르면 피싱 사이트입니다. 절대 클릭 금지!</div>', unsafe_allow_html=True)

        st.markdown('<div class="scam-alert-text">3. 재입금 요구 (수수료 핑계)</div>', unsafe_allow_html=True)

        st.markdown('<div class="scam-desc">"수수료 안 보내서 다시 보내라" → 전형적인 3자 사기/먹튀입니다.</div>', unsafe_allow_html=True)

        st.markdown('<div class="scam-alert-text">4. 당근마켓 타지역 핑계</div>', unsafe_allow_html=True)

        st.markdown('<div class="scam-desc">"출장중이라 택배만 가능해요" → 직거래 회피는 의심 1순위.</div>', unsafe_allow_html=True)

        st.markdown('<div class="scam-alert-text">5. 포인트/사이트 합산 결제</div>', unsafe_allow_html=True)

        st.markdown('<div class="scam-desc">"제 사이트 포인트로 결제할게요"라며 링크 전송 → 피싱 사이트입니다.</div>', unsafe_allow_html=True)



with c_main:

    col_status, col_btn = st.columns([0.8, 0.2], vertical_alignment="bottom")

    with col_status:

        st.markdown(f"""

            <div style="text-align:right; font-family:monospace; color:#00ff88; font-size:0.85rem; margin-bottom:5px;">

                📡 System Live | Last Scan: {now_time}

            </div>

        """, unsafe_allow_html=True)

    with col_btn:

        if st.button("🔄 Scan", use_container_width=True):

            with st.spinner("📡 Scanning..."):

                time.sleep(1.2)

                st.session_state.ticker_data = generate_new_data()

                st.rerun()


    st.markdown(ticker_html, unsafe_allow_html=True)


    st.markdown("""

        <div style="text-align:center; margin-bottom:20px; margin-top:20px;">

            <div class="radar-wrapper"><span class="radar-emoji">📡</span><div class="pulse-ring"></div></div>

            <span class="title-text">매물레이더</span>

            <p style="color:#aaa; font-size:1rem; margin-top:5px;">숨어있는 꿀매물을 3단계 심층 스캔합니다.</p>

        </div>

    """, unsafe_allow_html=True)


    tips = ["💡 Tip: 일본 직구는 $150, 미국 직구는 $200까지 무관세!", "💡 Tip: 메모장에 가격을 적어두고 비교하면 편해요.", "💡 Tip: 안전결제 거부하는 판매자는 일단 의심해보세요."]

    st.markdown(f'<div class="tip-banner">{random.choice(tips)}</div>', unsafe_allow_html=True)


    # ▼▼▼ [수정됨] 안내 멘트(placeholder) 직관적으로 변경 ▼▼▼

    st.markdown('<div style="margin-bottom: 5px;"><span class="radar-dot-idle"></span>타겟 탐색</div>', unsafe_allow_html=True)

    keyword = st.text_input("검색어 입력", placeholder="🔍 여기를 클릭하여 검색하세요! (예: 아이폰 15)", label_visibility="collapsed")


    if keyword:

        # ------------------------------------------------------------------

        # [★ CCTV] 여기에 print를 넣어서 서버 로그에 찍히게 함!

        # ------------------------------------------------------------------

        print(f"🚨 [검색감지] 사용자 검색어: {keyword}")


        safe_keyword = html.escape(keyword) 

        encoded_kor = urllib.parse.quote(keyword)

        eng_keyword = get_english_keyword(keyword)

        safe_eng_keyword = html.escape(eng_keyword) 

        encoded_eng = urllib.parse.quote(eng_keyword)

        

        st.markdown(f'''

            <div class="signal-banner">

                <span class="radar-dot-strong"></span>

                <span>'{safe_keyword}' 신호 포착! (Global: {safe_eng_keyword})</span>

            </div>

        ''', unsafe_allow_html=True)


        st.markdown('<h3 style="color: #FFFFFF; margin-top: 20px;">🔥 국내 메이저</h3>', unsafe_allow_html=True)

        st.markdown('<div class="guide-badge">⚡️ 매물량 1위! 가장 먼저 확인하세요</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        col1.link_button("⚡ 번개장터", f"https://m.bunjang.co.kr/search/products?q={encoded_kor}", use_container_width=True)

        col2.link_button("🥕 당근마켓", f"https://www.daangn.com/search/{encoded_kor}", use_container_width=True)


        st.markdown('<h3 style="color: #FFFFFF; margin-top: 20px;">💎 국내 마이너</h3>', unsafe_allow_html=True)

        st.markdown('<div class="guide-badge">🏺 숨은 꿀매물 & 레어템 발굴</div>', unsafe_allow_html=True)

        col3, col4 = st.columns(2)

        col3.link_button("🌵 중고나라", f"https://web.joongna.com/search?keyword={encoded_kor}", use_container_width=True)

        col4.link_button("🍇 후르츠", f"https://fruitsfamily.com/search/{encoded_kor}", use_container_width=True)


        st.markdown('<h3 style="color: #FFFFFF; margin-top: 20px;">✈️ 해외 직구</h3>', unsafe_allow_html=True)

        st.markdown('<div class="guide-badge">🌏 국내에 없는 물건 찾기 (관세 주의)</div>', unsafe_allow_html=True)

        col5, col6 = st.columns(2)

        col5.link_button("🇺🇸 eBay", f"https://www.ebay.com/sch/i.html?_nkw={encoded_eng}", use_container_width=True)

        col6.link_button("🇯🇵 Mercari", f"https://jp.mercari.com/search?keyword={encoded_eng}", use_container_width=True)

    else:

        st.info("👆 찾으시는 매물을 입력하면 국내외 매물을 한 번에 스캔합니다.")


    st.markdown("""

        <div class="legal-footer">

            본 서비스는 온라인 쇼핑몰 및 중고 거래 사이트의 상품 정보를 검색하여 링크를 제공하는 서비스입니다.<br>

            당사는 통신판매 당사자가 아니며, 상품의 주문/배송/환불 등 모든 거래에 대한 의무와 책임은 각 판매자에게 있습니다.<br>

            <br>

            ⚠️ <strong>안전한 거래를 위해 반드시 '안전결제(에스크로)'를 이용하시기 바랍니다.</strong>

        </div>

    """, unsafe_allow_html=True) 
