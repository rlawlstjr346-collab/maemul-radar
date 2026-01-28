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
    page_title="매물레이더 - 중고시세 통합검색",
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
# [3] 유틸리티 함수 (번역 기능 강화)
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

# [NEW] 번역 함수 업그레이드 (타겟 언어 지정 가능)
def get_translated_keyword(text, target_lang='en'):
    if not re.search('[가-힣]', text): return text
    try:
        # target_lang: 'en'은 영어, 'ja'는 일본어
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ko&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
        response = requests.get(url, timeout=1)
        if response.status_code == 200: return response.json()[0][0][0]
    except: pass
    return text

# ------------------------------------------------------------------
# [4] CSS 스타일링
# ------------------------------------------------------------------
st.markdown("""
<style>
    /* 기본 테마 */
    .stApp { background-color: #0E1117; color: #FAFAFA; font-family: 'Pretendard', sans-serif; }
    [data-testid="stSidebar"] { background-color: #17191E; border-right: 1px solid #333; }
    
    div[data-baseweb="input"] {
        background-color: #262730; 
        border: 2px solid #00ff88 !important;
        border-radius: 8px; 
        box-shadow: 0 0 10px rgba(0, 255, 136, 0.15);
        transition: all 0.3s ease;
    }
    div[data-baseweb="input"]:focus-within {
        box-shadow: 0 0 15px rgba(0, 255, 136, 0.5);
    }
    .stTextInput input, .stTextArea textarea, .stNumberInput input { color: #FAFAFA; font-weight: bold; }

    /* 링크 버튼 스타일 */
    div[data-testid="stLinkButton"] > a {
        border-radius: 10px; font-weight: 700; transition: all 0.3s ease; text-decoration: none;
    }
    
    /* 각 플랫폼별 컬러 */
    div[data-testid="stLinkButton"] > a[href*="bunjang"] { border: 1px solid #FF3E3E !important; color: #FF3E3E !important; background-color: rgba(255, 62, 62, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="bunjang"]:hover { background-color: #FF3E3E !important; color: white !important; }

    div[data-testid="stLinkButton"] > a[href*="daangn"] { border: 1px solid #FF8A3D !important; color: #FF8A3D !important; background-color: rgba(255, 138, 61, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="daangn"]:hover { background-color: #FF8A3D !important; color: white !important; }

    div[data-testid="stLinkButton"] > a[href*="joongna"] { border: 1px solid #00E676 !important; color: #00E676 !important; background-color: rgba(0, 230, 118, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="joongna"]:hover { background-color: #00E676 !important; color: black !important; }

    div[data-testid="stLinkButton"] > a[href*="ebay"] { border: 1px solid #2962FF !important; color: #2962FF !important; background-color: rgba(41, 98, 255, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="ebay"]:hover { background-color: #2962FF !important; color: white !important; }

    div[data-testid="stLinkButton"] > a[href*="mercari"] { border: 1px solid #D500F9 !important; color: #D500F9 !important; background-color: rgba(213, 0, 249, 0.1); }
    div[data-testid="stLinkButton"] > a[href*="mercari"]:hover { background-color: #D500F9 !important; color: white !important; }

    /* 적정가 게이지 스타일 */
    .price-gauge-container { background-color: #1E1E1E; padding: 15px; border-radius: 10px; border: 1px solid #333; margin-bottom: 20px; }
    .gauge-bar { height: 10px; width: 100%; background: linear-gradient(90deg, #00ff88 0%, #ffff00 50%, #ff0000 100%); border-radius: 5px; position: relative; margin-top: 10px; }
    .gauge-marker { position: absolute; top: -5px; width: 4px; height: 20px; background-color: white; border: 1px solid black; transform: translateX(-50%); }
    .verdict-text { font-size: 1.2rem; font-weight: bold; text-align: center; margin-top: 10px; }
    
    .ticker-container { width: 100%; background-color: #15181E; border-bottom: 2px solid #333; margin-bottom: 20px; display: flex; flex-direction: column; }
    .ticker-line { width: 100%; overflow: hidden; white-space: nowrap; padding: 8px 0; border-bottom: 1px solid #222; }
    .ticker-move-1 { display: inline-block; padding-left: 100%; animation: ticker 200s linear infinite; }
    .ticker-move-2 { display: inline-block; padding-left: 100%; animation: ticker 250s linear infinite; }
    .ticker-line span { margin-right: 40px; font-size: 0.9rem; font-family: sans-serif; }
    .label-market { color: #ff4b4b; font-weight: 900; margin-right: 15px !important; }
    .label-radar { color: #00ff88; font-weight: 900; margin-right: 15px !important; }
    @keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-100%, 0, 0); } }

    .radar-wrapper { position: relative; display: inline-block; margin-right: 10px; vertical-align: middle; }
    .radar-emoji { position: relative; z-index: 2; font-size: 3rem; }
    .pulse-ring { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 100%; height: 100%; border-radius: 50%; border: 2px solid rgba(255, 255, 255, 0.7); opacity: 0; animation: pulse-ring 2s infinite; }
    @keyframes pulse-ring { 0% { width: 90%; opacity: 1; } 100% { width: 220%; opacity: 0; } }
    .title-text { font-size: 3rem; font-weight: 900; color: #FFFFFF !important; letter-spacing: -1px; }

    .side-util-header { font-size: 1rem; font-weight: bold; color: #00ff88; margin-top: 10px; margin-bottom: 10px; border-left: 3px solid #00ff88; padding-left: 8px; }
    .small-link { font-size: 0.8rem; color: #888; text-decoration: none; margin-left: 5px; }
    .small-link:hover { color: #00ff88; }
    
    .legal-footer { font-size: 0.75rem; color: #777; margin-top: 60px; padding: 30px 10px; border-top: 1px solid #333; text-align: center; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# [5] 상단 티커
# ------------------------------------------------------------------
current_data = st.session_state.ticker_data
market_str = "".join([f"<span><span style='color:#888;margin-right:4px;'>{i}.</span><span style='color:#eee;font-weight:600;'>{item}</span></span>" for i, item in enumerate(current_data['market'], 1)])
radar_str = "".join([f"<span><span style='color:#888;margin-right:4px;'>{i}.</span><span style='color:#eee;font-weight:600;'>{item}</span></span>" for i, item in enumerate(current_data['radar'], 1)])
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
# [6] 사이드바 (기능 대폭 추가)
# ------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 레이더 센터")
    
    # [NEW] 적정가 판독기 (피드백 반영)
    st.markdown('<div class="side-util-header">⚖️ 적정가 판독기 (Beta)</div>', unsafe_allow_html=True)
    with st.expander("📊 가격 분석하려면 클릭", expanded=True):
        st.caption("최근 거래된 최고가/최저가를 입력하면 현재 매물의 가성비를 분석해줍니다.")
        in_high = st.number_input("최근 본 최고가", value=0, step=1000)
        in_low = st.number_input("최근 본 최저가", value=0, step=1000)
        in_current = st.number_input("현재 판매자 가격", value=0, step=1000)
        
        if in_high > 0 and in_low > 0 and in_current > 0:
            if in_high <= in_low:
                st.error("최고가가 최저가보다 낮을 수 없습니다.")
            else:
                # 위치 계산 (0~100%)
                position = (in_current - in_low) / (in_high - in_low) * 100
                if position < 0: position = 0
                if position > 100: position = 100
                
                # 판독 결과
                verdict = ""
                color = ""
                if position <= 20:
                    verdict = "🔥 강력 추천 (매우 쌈)"
                    color = "#00ff88"
                elif position <= 50:
                    verdict = "✅ 적정 가격 (평균 이하)"
                    color = "#ffff00"
                elif position <= 80:
                    verdict = "🤔 조금 비쌈 (평균 이상)"
                    color = "#ffaa00"
                else:
                    verdict = "🚨 비추천 (너무 비쌈)"
                    color = "#ff4b4b"
                
                st.markdown(f"""
                    <div class="price-gauge-container">
                        <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:#aaa;">
                            <span>Low {in_low:,}</span>
                            <span>High {in_high:,}</span>
                        </div>
                        <div class="gauge-bar">
                            <div class="gauge-marker" style="left: {position}%;"></div>
                        </div>
                        <div class="verdict-text" style="color:{color};">{verdict}</div>
                        <div style="text-align:center; margin-top:5px; font-size:0.9rem;">현재: {in_current:,}원</div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("가격을 입력하면 분석이 시작됩니다.")

    st.write("---")
    
    # 환율 계산기
    usd_rate, jpy_rate = get_exchange_rates()
    with st.expander("💱 직구 안전선 계산기", expanded=False):
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
    st.caption("거래 전 계좌/전화번호 조회 필수!")
    
    st.write("---")
    st.link_button("💬 피드백 보내기", "https://docs.google.com/forms/d/e/1FAIpQLSdZdfJLBErRw8ArXlBLqw9jkoLk0Qj-AOo0yPm-hg7KmGYOnA/viewform?usp=dialog", use_container_width=True)

# ------------------------------------------------------------------
# [7] 메인 화면
# ------------------------------------------------------------------
c_main, c_memo = st.columns([0.7, 0.3], gap="large")

with c_memo:
    st.markdown('<div class="side-util-header">📝 쇼핑 메모장</div>', unsafe_allow_html=True)
    memo_val = st.text_area(
        "memo",
        value=st.session_state.memo_pad,
        height=300,
        label_visibility="collapsed",
        placeholder="[시세 기록용]\n\n최저가: 35만\n적정가: 38만\n\n*검색한 시세를 여기에 적어두고\n왼쪽 '적정가 판독기'에 입력해보세요!"
    )
    st.session_state.memo_pad = memo_val

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

    st.markdown('<div style="margin-bottom: 5px;"><span class="radar-dot-idle"></span>타겟 탐색</div>', unsafe_allow_html=True)
    keyword = st.text_input("검색어 입력", placeholder="🔍 찾으시는 물건을 입력하세요 (예: 아이폰15, 포켓몬스터)", label_visibility="collapsed")

    if keyword:
        # [CCTV] 검색어 로그
        print(f"🚨 [검색감지] 사용자 검색어: {keyword}")

        safe_keyword = html.escape(keyword) 
        encoded_kor = urllib.parse.quote(keyword)
        
        # [NEW] 언어별 번역 (영어 / 일본어)
        eng_keyword = get_translated_keyword(keyword, 'en')
        jp_keyword = get_translated_keyword(keyword, 'ja') # 일본어 번역
        
        safe_eng = html.escape(eng_keyword)
        safe_jp = html.escape(jp_keyword)
        
        encoded_eng = urllib.parse.quote(eng_keyword)
        encoded_jp = urllib.parse.quote(jp_keyword)
        
        st.markdown(f'''
            <div class="signal-banner">
                <span class="radar-dot-strong"></span>
                <span>'{safe_keyword}' 신호 포착! (En: {safe_eng} / Jp: {safe_jp})</span>
            </div>
        ''', unsafe_allow_html=True)

        st.markdown('<h3 style="color: #FFFFFF; margin-top: 20px;">🔥 국내 메이저 (실거래 확인)</h3>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.link_button("⚡ 번개장터 검색", f"https://m.bunjang.co.kr/search/products?q={encoded_kor}", use_container_width=True)
            st.markdown(f"<div style='text-align:right;'><a href='https://m.bunjang.co.kr/search/products?q={encoded_kor}&status=SOLDOUT' target='_blank' class='small-link'>✅ 판매완료(시세) 보기</a></div>", unsafe_allow_html=True)
        with col2:
            st.link_button("🥕 당근마켓 검색", f"https://www.daangn.com/search/{encoded_kor}", use_container_width=True)
            st.markdown(f"<div style='text-align:right;'><a href='https://www.daangn.com/search/{encoded_kor}' target='_blank' class='small-link'>✅ 중고거래 내역 보기</a></div>", unsafe_allow_html=True)

        st.markdown('<h3 style="color: #FFFFFF; margin-top: 20px;">💎 국내 마이너 & 커뮤니티</h3>', unsafe_allow_html=True)
        col3, col4 = st.columns(2)
        with col3:
            st.link_button("🌵 중고나라 검색", f"https://web.joongna.com/search?keyword={encoded_kor}", use_container_width=True)
            st.markdown(f"<div style='text-align:right;'><a href='https://web.joongna.com/search?keyword={encoded_kor}&sold=true' target='_blank' class='small-link'>✅ 판완 내역 확인</a></div>", unsafe_allow_html=True)
        with col4:
            st.link_button("🍇 후르츠 (패션)", f"https://fruitsfamily.com/search/{encoded_kor}", use_container_width=True)

        st.markdown('<h3 style="color: #FFFFFF; margin-top: 20px;">✈️ 해외 직구 (자동 번역)</h3>', unsafe_allow_html=True)
        st.caption(f"💡 해외 사이트는 자동으로 번역된 키워드로 검색합니다.")
        col5, col6 = st.columns(2)
        
        with col5:
            # 이베이는 영어로
            st.link_button(f"🇺🇸 eBay (검색어: {safe_eng})", f"https://www.ebay.com/sch/i.html?_nkw={encoded_eng}", use_container_width=True)
            st.markdown(f"<div style='text-align:right;'><a href='https://www.ebay.com/sch/i.html?_nkw={encoded_eng}&LH_Sold=1&LH_Complete=1' target='_blank' class='small-link'>✅ Sold Items (시세)</a></div>", unsafe_allow_html=True)
        
        with col6:
            # [핵심] 메루카리는 일본어로!
            st.link_button(f"🇯🇵 Mercari (검색어: {safe_jp})", f"https://jp.mercari.com/search?keyword={encoded_jp}", use_container_width=True)
            st.markdown(f"<div style='text-align:right;'><a href='https://jp.mercari.com/search?keyword={encoded_jp}&status=sold_out' target='_blank' class='small-link'>✅ 売り切れ (판매된 가격)</a></div>", unsafe_allow_html=True)

    else:
        st.info("👆 찾으시는 매물을 입력하면 국내외 매물을 한 번에 스캔합니다.")
        st.markdown("""
            <div style="background-color:#262730; padding:15px; border-radius:10px; margin-top:20px; border:1px solid #444;">
                <h4 style="margin:0 0 10px 0; color:#00ff88;">💡 사용 꿀팁 (Tip)</h4>
                <ul style="font-size:0.9rem; color:#ccc; padding-left:20px; line-height:1.6;">
                    <li>왼쪽 사이드바의 <b>[적정가 판독기]</b>를 열어보세요. 시세 호구 방지 가능!</li>
                    <li>해외 사이트(메루카리 등)는 자동으로 <b>일본어로 번역</b>되어 검색됩니다.</li>
                    <li>각 버튼 아래 <b>'✅ 판매완료 보기'</b>를 누르면 과거 시세를 알 수 있습니다.</li>
                </ul>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("""
        <div class="legal-footer">
            본 서비스는 링크를 제공하는 중개 서비스이며, 실제 거래의 책임은 각 판매자에게 있습니다.<br>
            안전한 거래를 위해 반드시 <strong>안전결제(에스크로)</strong>를 이용하세요.
        </div>
    """, unsafe_allow_html=True)
