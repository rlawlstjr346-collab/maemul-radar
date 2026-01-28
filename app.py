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
# [★ ADMIN] 시세 데이터 (여기에 데이터를 추가하면 검색시 자동으로 뜹니다)
# ------------------------------------------------------------------
admin_trend_data = {
    "아이폰": { # 검색어에 '아이폰'이 들어가면 이 데이터가 뜸
        "name": "Apple 아이폰 15 Pro (256GB)",
        "dates": ["12월 4주", "1월 1주", "1월 2주", "1월 3주", "1월 4주"],
        "prices": [115, 112, 110, 108, 105]
    },
    "갤럭시": {
        "name": "Samsung 갤럭시 S24 울트라",
        "dates": ["12월 4주", "1월 1주", "1월 2주", "1월 3주", "1월 4주"],
        "prices": [130, 128, 125, 120, 118]
    },
    "4070": {
        "name": "NVIDIA RTX 4070 Ti Super",
        "dates": ["12월 4주", "1월 1주", "1월 2주", "1월 3주", "1월 4주"],
        "prices": [120, 119, 119, 115, 112]
    },
    "포켓몬": {
        "name": "포켓몬카드 (미개봉 박스)",
        "dates": ["12월 4주", "1월 1주", "1월 2주", "1월 3주", "1월 4주"],
        "prices": [5, 5.5, 6, 5.8, 6.2]
    }
}

# ------------------------------------------------------------------
# [2] 데이터 생성 및 세션 관리
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

def get_translated_keyword(text, target_lang='en'):
    if not re.search('[가-힣]', text): return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ko&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
        response = requests.get(url, timeout=1)
        if response.status_code == 200: return response.json()[0][0][0]
    except: pass
    return text

# 그래프용 데이터 매칭 함수
def get_trend_data_by_keyword(keyword):
    if not keyword: return None
    # 검색어에 Admin 데이터 키워드가 포함되어 있는지 확인 (예: "아이폰 15" 검색 -> "아이폰" 데이터 매칭)
    for key in admin_trend_data.keys():
        if key in keyword or keyword in key:
            return admin_trend_data[key]
    return None

# ------------------------------------------------------------------
# [4] CSS 스타일링 (Original Cyber-HUD 복구 완료)
# ------------------------------------------------------------------
st.markdown("""
<style>
    /* 기본 테마 */
    .stApp { background-color: #0E1117; color: #FAFAFA; font-family: 'Pretendard', sans-serif; }
    [data-testid="stSidebar"] { background-color: #17191E; border-right: 1px solid #333; }
    
    /* 입력창 스타일 */
    div[data-baseweb="input"] {
        background-color: #262730; 
        border: 2px solid #00ff88 !important;
        border-radius: 8px; 
        box-shadow: 0 0 10px rgba(0, 255, 136, 0.15);
        transition: all 0.3s ease;
    }
    div[data-baseweb="input"]:focus-within { box-shadow: 0 0 15px rgba(0, 255, 136, 0.5); }
    .stTextInput input, .stTextArea textarea, .stNumberInput input { color: #FAFAFA; font-weight: bold; }

    /* 링크 버튼 */
    div[data-testid="stLinkButton"] > a { border-radius: 10px; font-weight: 700; transition: all 0.3s ease; text-decoration: none; }
    
    /* 플랫폼별 컬러 */
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

    /* 티커 */
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

    .title-text { font-size: 2.5rem; font-weight: 900; color: #FFFFFF !important; letter-spacing: -1px; }
    .side-util-header { font-size: 1rem; font-weight: bold; color: #0A84FF; margin-top: 5px; margin-bottom: 5px; border-left: 3px solid #0A84FF; padding-left: 8px; }
    
    .signal-banner { background: linear-gradient(90deg, #0A84FF 0%, #0055FF 100%); color: white !important; padding: 15px 20px; border-radius: 12px; margin-bottom: 25px; font-weight: bold; font-size: 1rem; display: flex; align-items: center; box-shadow: 0 4px 15px rgba(10, 132, 255, 0.3); }
    .guide-badge { display: inline-block; background-color: #f8f9fa !important; color: #000000 !important; font-size: 0.9rem; padding: 6px 14px; border-radius: 15px; margin-bottom: 15px; font-weight: 800; }
    
    /* 카드형 컨테이너 스타일 */
    .dashboard-card { background-color: #17191E; border-radius: 12px; border: 1px solid #333; padding: 20px; height: 100%; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [5] 상단 티커
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
st.markdown(ticker_html, unsafe_allow_html=True)

# ------------------------------------------------------------------
# [6] 사이드바 (도구 모음 - 적정가 판독기 삭제됨)
# ------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 레이더 센터")
    
    # 환율 계산기
    usd_rate, jpy_rate = get_exchange_rates()
    with st.expander("💱 직구 안전선 계산기", expanded=True):
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
    st.link_button("💬 피드백 보내기", "https://docs.google.com/forms/d/e/1FAIpQLSdZdfJLBErRw8ArXlBLqw9jkoLk0Qj-AOo0yPm-hg7KmGYOnA/viewform?usp=dialog", use_container_width=True)

# ------------------------------------------------------------------
# [7] 메인 대시보드 레이아웃 (Left: Search / Right: Info)
# ------------------------------------------------------------------
col_left, col_right = st.columns([0.6, 0.4], gap="large")

# --------------------- [좌측: 검색 및 실행] ---------------------
with col_left:
    st.markdown('<span class="title-text">매물레이더</span> <span style="font-size:1.5rem;">Pro</span>', unsafe_allow_html=True)
    st.caption(f"System Live | Last Scan: {now_time}")
    
    st.markdown('<div style="margin-bottom: 5px;"><span class="radar-dot-idle"></span>타겟 탐색</div>', unsafe_allow_html=True)
    keyword = st.text_input("검색어 입력", placeholder="🔍 찾으시는 물건을 입력하세요 (예: 아이폰15, 포켓몬스터)", label_visibility="collapsed")

    if keyword:
        # [CCTV]
        print(f"🚨 [검색감지] 사용자 검색어: {keyword}")

        safe_keyword = html.escape(keyword) 
        encoded_kor = urllib.parse.quote(keyword)
        
        # 언어 변환
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
        # [수정완료] 링크 삭제함, 버튼만 남김
        c1.link_button("⚡ 번개장터", f"https://m.bunjang.co.kr/search/products?q={encoded_kor}", use_container_width=True)
        c2.link_button("🥕 당근마켓", f"https://www.daangn.com/search/{encoded_kor}", use_container_width=True)

        st.markdown('### 💎 국내 마이너')
        c3, c4 = st.columns(2)
        c3.link_button("🌵 중고나라", f"https://web.joongna.com/search?keyword={encoded_kor}", use_container_width=True)
        c4.link_button("🍇 후르츠 (패션)", f"https://fruitsfamily.com/search/{encoded_kor}", use_container_width=True)

        st.markdown('### ✈️ 해외 직구 (자동번역)')
        c5, c6 = st.columns(2)
        c5.link_button(f"🇺🇸 eBay ({safe_eng})", f"https://www.ebay.com/sch/i.html?_nkw={encoded_eng}", use_container_width=True)
        c6.link_button(f"🇯🇵 Mercari ({safe_jp})", f"https://jp.mercari.com/search?keyword={encoded_jp}", use_container_width=True)

    else:
        st.info("👆 상품명을 입력하면 3단계 심층 스캔을 시작합니다.")
        st.markdown("""
            <div style="background-color:#262730; padding:15px; border-radius:10px; margin-top:20px; border:1px solid #444;">
                <h4 style="margin:0 0 10px 0; color:#00ff88;">💡 사용 꿀팁 (Tip)</h4>
                <ul style="font-size:0.9rem; color:#ccc; padding-left:20px; line-height:1.6;">
                    <li><b>우측 그래프</b>는 검색어와 일치하는 데이터가 있을 때만 자동 표시됩니다.</li>
                    <li>해외 사이트(메루카리)는 자동으로 <b>일본어로 번역</b>됩니다.</li>
                </ul>
            </div>
        """, unsafe_allow_html=True)

# --------------------- [우측: 정보 및 도구] ---------------------
with col_right:
    # 1. 시세 그래프 (검색어 연동 자동화)
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.markdown("#### 📉 52주 시세 트렌드")
    
    # [핵심 기능] 검색어에 따라 자동으로 데이터 매칭
    matched_data = get_trend_data_by_keyword(keyword)
    
    if matched_data:
        # 데이터가 있으면 그래프 그림
        st.caption(f"✅ '{matched_data['name']}' 데이터 확인됨")
        df_trend = pd.DataFrame({
            "날짜": matched_data["dates"],
            "가격(만원)": matched_data["prices"]
        })
        st.line_chart(df_trend, x="날짜", y="가격(만원)", color="#00ff88", height=200)
        st.caption("※ 운영자가 직접 검수한 실거래 평균가입니다.")
    else:
        # 데이터가 없으면 안내 메시지
        if keyword:
            st.warning(f"⚠️ '{keyword}'에 대한 시세 데이터가 아직 수집되지 않았습니다.")
            st.caption("운영자가 확인 후 업데이트 예정입니다.")
        else:
            st.info("좌측에 검색어를 입력하면 시세 그래프가 나타납니다.")
            st.caption("(예: 아이폰, 갤럭시, 4070, 포켓몬)")
            
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.write("") # 간격

    # 2. 스마트 멘트 & 메모장
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.markdown("#### 💬 스마트 멘트 & 메모")
    
    tab_m1, tab_m2, tab_memo = st.tabs(["⚡️ 퀵멘트", "💳 결제", "📝 메모"])
    
    with tab_m1:
        opt = st.radio("상황 선택", ["구매 가능?", "네고 요청", "택포 요청"], label_visibility="collapsed")
        if opt == "구매 가능?": st.code("안녕하세요! 게시글 보고 연락드립니다. 구매 가능할까요?", language="text")
        elif opt == "네고 요청": 
            p = st.text_input("희망가", placeholder="예: 3만원", key="p1")
            st.code(f"혹시 실례가 안 된다면 {p if p else '00'}원 정도로 네고 가능할까요? 바로 입금하겠습니다!", language="text")
        elif opt == "택포 요청": st.code("혹시 택배비 포함으로 부탁드려도 될까요?", language="text")

    with tab_m2:
        pay = st.radio("결제", ["계좌요청", "안전결제"], label_visibility="collapsed", horizontal=True)
        if pay == "계좌요청": st.code("계좌 알려주시면 바로 이체하겠습니다.", language="text")
        else: st.code("혹시 번개페이/안전결제로 가능할까요?", language="text")
    
    with tab_memo:
        st.session_state.memo_pad = st.text_area("메모", st.session_state.memo_pad, height=100, label_visibility="collapsed", placeholder="가격 비교 메모...")
    
    st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("""
    <div class="legal-footer">
        본 서비스는 링크를 제공하는 중개 서비스이며, 실제 거래의 책임은 각 판매자에게 있습니다.<br>
        안전한 거래를 위해 반드시 <strong>안전결제(에스크로)</strong>를 이용하세요.
    </div>
""", unsafe_allow_html=True)
