import streamlit as st
import urllib.parse
import requests
import re
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import html
import random

CHART_BLUE = '#5C9EFF'
CHART_BLUE_LIGHT = '#90CAF9'
CHART_BLUE_FILL = 'rgba(92, 158, 255, 0.15)'
CHART_BLUE_HIGHLIGHT = 'rgba(92, 158, 255, 0.35)'

st.set_page_config(page_title="RADAR", page_icon="📡", layout="wide", initial_sidebar_state="collapsed")

sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQS8AftSUmG9Cr7MfczpotB5hhl1DgjH4hRCgXH5R8j5hykRiEf0M9rEyEq3uj312a5RuI4zMdjI5Jr/pub?output=csv"

@st.cache_data(ttl=60)
def load_price_data():
    try:
        df = pd.read_csv(sheet_url, encoding='utf-8-sig')
        df.columns = df.columns.str.strip().str.replace('\ufeff', '')
        return df
    except Exception as e:
        return pd.DataFrame()

def classify_keyword_category(keyword):
    k = keyword.lower().replace(" ", "")
    cam_db = ['카메라', 'camera', '렌즈', 'lens', '필름', 'film', 'dslr', '미러리스', '라이카', 'leica', 'm3', 'm6', 'm11', 'q2', 'q3', '핫셀블라드', 'hasselblad', '핫셀', '500cm', 'x2d', '린호프', 'linhof', '테크니카', 'technika', '마미야', 'mamiya', 'rz67', 'rb67', '콘탁스', 'contax', 't2', 't3', 'g1', 'g2', '브로니카', 'bronica', '젠자', '롤라이', 'rollei', '35s', '35t', '페이즈원', 'phaseone', 'iq4', '리코', 'ricoh', 'gr2', 'gr3', 'gr3x', '펜탁스', 'pentax', 'k1000', 'lx', '67', '보이그랜더', 'voigtlander', '녹턴', '울트론', '캐논', 'canon', '니콘', 'nikon', '소니', 'sony', '후지', 'fujifilm']
    fashion_db = ['나이키', 'nike', '조던', 'jordan', '덩크', 'dunk', '에어포스', '아디다스', 'adidas', '이지', 'yeezy', '삼바', '가젤', '슈프림', 'supreme', '스투시', 'stussy', '팔라스', 'palace', '요지', 'yohji', '야마모토', 'yamamoto', '와이쓰리', 'y-3', '꼼데', 'commedesgarcons', '가르송', '아크테릭스', 'arcteryx', '베타', '알파', '노스페이스', 'northface', '눕시', '스톤아일랜드', 'stoneisland', 'cp컴퍼니', '뉴발란스', 'newbalance', '992', '993', '990', '살로몬', 'salomon', '오클리', 'oakley', '젠틀몬스터', 'gentlemonster', '구찌', 'gucci', '루이비통', 'louisvuitton', '샤넬', 'chanel', '에르메스', 'hermes', '프라다', 'prada', '미우미우', 'miumiu', '보테가', 'bottega', '롤렉스', 'rolex', '오메가', 'omega', '까르띠에', 'cartier']
    tech_db = ['컴퓨터', 'pc', '데스크탑', '노트북', 'laptop', '그래픽', 'vga', 'gpu', 'rtx', 'gtx', '4090', '4080', '4070', '3080', 'cpu', 'amd', '라이젠', 'ryzen', '인텔', 'intel', '아이폰', 'iphone', '15pro', '14pro', '13mini', '맥북', 'macbook', '에어', '프로', 'm1', 'm2', 'm3', '아이패드', 'ipad', '에어팟', 'airpods', '애플워치', 'applewatch', '갤럭시', 'galaxy', 's24', 's23', 'zflip', 'zfold', '플스', 'ps5', 'ps4', 'playstation', '닌텐도', 'nintendo', '스위치', 'switch', '키보드', 'keyboard', '마우스', 'mouse', '모니터', 'monitor']
    if any(x in k for x in cam_db): return "CAMERA"
    elif any(x in k for x in fashion_db): return "FASHION"
    elif any(x in k for x in tech_db): return "TECH"
    return None

def get_related_communities(keyword):
    c = classify_keyword_category(keyword)
    if c == "CAMERA": return "📷 전문가급 카메라/장비 커뮤니티", [("SLR클럽", "https://www.slrclub.com", "slr"), ("라이카 클럽", "http://www.leicaclub.net/", "leica"), ("필름카메라 동호회", "https://cafe.naver.com/35mmcamera", "film"), ("DOF LOOK", "https://cafe.naver.com/doflook", "dof")]
    elif c == "FASHION": return "👟 패션/스니커즈/명품 커뮤니티", [("KREAM", "https://kream.co.kr", "kream"), ("나이키매니아", "https://cafe.naver.com/sssw", "nike"), ("어미새", "https://eomisae.co.kr", "eomisae"), ("디젤매니아", "https://cafe.naver.com/dieselmania", "diesel")]
    elif c == "TECH": return "💻 IT/테크/얼리어답터 커뮤니티", [("퀘이사존", "https://quasarzone.com", "quasar"), ("쿨엔조이", "https://coolenjoy.net", "cool"), ("미코", "https://meeco.kr", "meeco"), ("클리앙", "https://www.clien.net", "clien")]
    return None, None

@st.cache_data(ttl=86400)
def get_exchange_rates():
    try:
        r = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=3)
        d = r.json()
        usd = d['rates']['KRW']
        jpy = (d['rates']['KRW'] / d['rates']['JPY']) * 100
        return usd, jpy, usd * (1 + random.uniform(-0.005, 0.005)), jpy * (1 + random.uniform(-0.005, 0.005))
    except: return 1450.0, 950.0, 1440.0, 955.0

def get_translated_keyword(text, target_lang='en'):
    if not re.search('[가-힣]', text): return text
    try:
        r = requests.get(f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ko&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}", timeout=2)
        if r.status_code == 200: return r.json()[0][0][0]
    except: pass
    return text

def calculate_total_import_cost(usd_price, rate):
    if usd_price <= 0: return 0
    krw_base = usd_price * rate
    shipping = 30000
    if usd_price > 200: return (krw_base + krw_base * 0.08 + (krw_base + krw_base * 0.08) * 0.1 + shipping) / 10000
    return (krw_base + shipping) / 10000

def _get_date_cols(df):
    skip = {'키워드', 'keyword', '모델명 (상세스펙/상태)', '모델명', '상세스펙', '분류', '브랜드', '시세 (5주치)', '해외평균(USD)', 'name', 'dates', 'prices'}
    cols = [c for c in df.columns if str(c).strip() not in skip and any(x in str(c) for x in ['월', '주', 'week', 'date', '날짜'])]
    return cols if cols else ["12월4주", "1월1주", "1월2주", "1월3주", "1월4주"]

def _get_col(row, *names):
    for n in names:
        v = row.get(n, None)
        if pd.notna(v) and str(v).strip(): return str(v).strip()
    return ''

def get_trend_data_from_sheet(user_query, df):
    if df.empty or not user_query: return None
    user_clean = user_query.lower().replace(" ", "").strip()
    date_cols = _get_date_cols(df)
    for _, row in df.iterrows():
        try:
            k_val = _get_col(row, '모델명', '키워드', 'keyword')
            if not k_val: continue
            sk = str(k_val).lower().replace(" ", "").strip()
            if sk in user_clean or user_clean in sk:
                trend_prices, valid_dates = [], []
                for col in date_cols:
                    if col in df.columns:
                        v_clean = re.sub(r'[^0-9.]', '', str(row.get(col, '0')).strip())
                        if v_clean:
                            try:
                                val = float(v_clean)
                                if val > 0: trend_prices.append(val); valid_dates.append(col)
                            except: pass
                raw_str = str(row.get('시세 (5주치)', row.get('prices_raw', row.get('거래가목록', '')))).strip()
                raw_prices = []
                if raw_str and raw_str.lower() != 'nan':
                    for p in raw_str.split(','):
                        cp = re.sub(r'[^0-9.]', '', p)
                        if cp:
                            try: v = float(cp); raw_prices.append(v) if v > 0 else None
                            except: continue
                if not raw_prices: raw_prices = trend_prices
                g_clean = re.sub(r'[^0-9.]', '', str(row.get('해외평균(USD)', '0')).strip())
                global_usd = float(g_clean) if g_clean else 0.0
                if not trend_prices: continue
                name = _get_col(row, '모델명', '모델명 (상세스펙/상태)')
                spec = _get_col(row, '상세스펙')
                if spec: name = f"{name} ({spec})".strip() if name else spec
                name = name or '상품명 미상'
                return {"name": name, "dates": valid_dates, "trend_prices": trend_prices, "raw_prices": raw_prices, "global_usd": global_usd}
        except: continue
    return None

if 'ticker_data' not in st.session_state: st.session_state.ticker_data = {'time': (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")}
if 'memo_pad' not in st.session_state: st.session_state.memo_pad = ""

st.markdown('<style>.stApp{background:#0E1117;background:radial-gradient(circle at 50% -20%,#1c2333 0%,#0E1117 80%);color:#EEE;font-family:Inter,Pretendard,sans-serif}.block-container{max-width:1400px!important;margin:0 auto!important}.header-container{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;padding:12px 30px;gap:40px;background:rgba(14,17,23,.85);backdrop-filter:blur(12px);position:sticky;top:15px;z-index:999;border:1px solid rgba(255,255,255,.1);border-radius:24px;box-shadow:0 8px 32px rgba(0,0,0,.3)}.radar-icon{font-size:2.2rem;animation:radar-ping 3s infinite}.radar-title{font-size:2.5rem;font-weight:900;letter-spacing:-1px;font-style:italic;background:linear-gradient(95deg,#FFF 60%,#888 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent}@keyframes radar-ping{0%,100%{filter:drop-shadow(0 0 2px rgba(0,255,136,.3))}50%{filter:drop-shadow(0 0 15px rgba(0,255,136,.8))}}.source-card{background:#1A1A1A;border:1px solid #333;border-radius:6px;padding:15px 20px;display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;height:60px;text-decoration:none}.metric-card{background:linear-gradient(90deg,#1a1a1a,#1a1a1a80);border:1px solid #333;border-left:3px solid #5C9EFF;padding:6px 10px;border-radius:10px;margin-bottom:6px}.metric-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 12px}.capsule-title{font-size:1.1rem;font-weight:800;color:#fff;margin:30px 0 15px;display:inline-flex;align-items:center;background:#1A1A1A;padding:8px 20px;border-radius:30px;border:1px solid #333}.section-title{font-size:1.1rem;font-weight:700;color:#eee;margin-bottom:8px}.ticker-wrap{position:fixed;bottom:0;left:0;width:100%;height:32px;background:#0E1117;border-top:1px solid #1C1C1E;z-index:999;display:flex;align-items:center}.scam-box{border:1px solid #333;border-left:4px solid #ff4b4b;background:#1A0505;padding:25px;border-radius:12px;margin-bottom:20px}.card-quasar{border-left:6px solid #FF9900!important}.card-cool{border-left:6px solid #DDD!important}.card-meeco{border-left:6px solid #3498db!important}.card-clien{border-left:6px solid #376092!important}.card-slr{border-left:6px solid #42A5F5!important}.card-leica{border-left:6px solid #D50000!important}.card-asamo{border-left:6px solid #2ecc71!important}.card-mac{border-left:6px solid #aaa!important}.card-joongna{border-left:6px solid #00d369!important}.card-ruli{border-left:6px solid #2E75B6!important}</style>', unsafe_allow_html=True)

usd, jpy, usd_prev, jpy_prev = get_exchange_rates()

MASTER_TREND = ["Leica M6","나이키 조던 1","iPhone 15 Pro","롤렉스 서브마리너","Ricoh GR3x","RTX 4090","맥북 프로 M3","Steam Deck OLED","PlayStation 5","Adidas Samba","Salomon XT-6","Dyson Airstrait","Galaxy S24 Ultra","닌텐도 스위치 2"]
MASTER_SNEAKERS = ["Jordan 1 Chicago","조던 1 모카","Nike Dunk Panda","Adidas Samba OG","New Balance 992","Asics Gel-Kayano 14"]
MASTER_LUXURY = ["Rolex Submariner","Chanel Classic Flap","Hermes Birkin 30","Gucci Jackie"]
MASTER_TECH = ["RTX 4090","맥북 프로 M3","Steam Deck OLED","아이폰 16 Pro","갤럭시 S24 울트라"]
MASTER_VIBE = ["Yohji Yamamoto","스톤아일랜드","Supreme Box Logo","Salomon XT-6","허먼밀러"]
MASTER_LIVING = ["Herman Miller Aeron","Snow Peak Tent","USM Haller","다이슨 에어스트레이트"]

if 'billboard_data' not in st.session_state:
    st.session_state.billboard_data = {k: random.sample(v, min(15, len(v))) for k,v in [('TREND',MASTER_TREND),('KICKS',MASTER_SNEAKERS),('LUX',MASTER_LUXURY),('TECH',MASTER_TECH),('VIBE',MASTER_VIBE),('LIVING',MASTER_LIVING)]}

def make_bill_html(items): return "".join([f'<span style="display:block;height:30px;line-height:30px;color:#eee;font-weight:700">· {i}</span>' for i in (items[:10]+items[:2])])

st.markdown(f'<div class="header-container"><a href="/" style="text-decoration:none"><span class="radar-icon">📡</span><span class="radar-title">RADAR</span></a></div>', unsafe_allow_html=True)

tab_home, tab_source, tab_tools, tab_safety = st.tabs(["🏠 시세 분석", "📂 Market Sources", "🧰 도구", "👮‍♂️ 사기 조회"])

with tab_home:
    col_left, col_right = st.columns([0.6, 0.4], gap="medium")
    with col_left:
        st.markdown('<div style="font-family:Courier New;font-size:.85rem;color:#00FF88;border-right:.15em solid #00FF88;white-space:nowrap">System Ready... Waiting for input_</div>', unsafe_allow_html=True)
        keyword = st.text_input("검색", placeholder="모델명 입력 (예: 라이카 M6, 나이키 조던)", label_visibility="collapsed", key="search_input")
        if keyword:
            enc_k = urllib.parse.quote(keyword)
            enc_e = urllib.parse.quote(get_translated_keyword(keyword,'en'))
            enc_j = urllib.parse.quote(get_translated_keyword(keyword,'ja'))
            st.markdown(f"<div style='margin-top:20px;font-size:1.3rem;font-weight:700;color:#eee'>'{html.escape(keyword)}' 분석 결과</div>", unsafe_allow_html=True)
            st.markdown("<div class='capsule-title'>🇰🇷 국내 마켓</div>", unsafe_allow_html=True)
            st.markdown(f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:15px"><a href="https://m.bunjang.co.kr/search/products?q={enc_k}" target="_blank" class="source-card card-asamo" style="text-decoration:none"><span>⚡ 번개장터</span><span>🔗</span></a><a href="https://www.daangn.com/search/{enc_k}" target="_blank" class="source-card card-mac" style="text-decoration:none"><span>🥕 당근마켓</span><span>🔗</span></a><a href="https://web.joongna.com/search?keyword={enc_k}" target="_blank" class="source-card card-joongna" style="text-decoration:none"><span>🟢 중고나라</span><span>🔗</span></a><a href="https://fruitsfamily.com/search/{enc_k}" target="_blank" class="source-card card-ruli" style="text-decoration:none"><span>🟣 Fruits</span><span>🔗</span></a></div>', unsafe_allow_html=True)
            st.markdown("<div class='capsule-title'>🌎 해외 직구</div>", unsafe_allow_html=True)
            st.markdown(f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:15px"><a href="https://www.ebay.com/sch/i.html?_nkw={enc_e}" target="_blank" class="source-card card-cool" style="text-decoration:none"><span>🔵 eBay</span><span>🔗</span></a><a href="https://jp.mercari.com/search?keyword={enc_j}" target="_blank" class="source-card card-clien" style="text-decoration:none"><span>⚪ Mercari</span><span>🔗</span></a></div>', unsafe_allow_html=True)
            ct, cl = get_related_communities(keyword)
            if cl: st.markdown(f"<div style='margin-top:30px;margin-bottom:10px;color:#00FF88;font-weight:700'>💡 {ct}</div>", unsafe_allow_html=True); st.markdown('<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">' + "".join([f'<a href="{u}" target="_blank" class="source-card card-{t}" style="text-decoration:none"><span>{n}</span><span>🔗</span></a>' for n,u,t in cl]) + '</div>', unsafe_allow_html=True)
    with col_right:
        df_prices = load_price_data()
        matched = get_trend_data_from_sheet(keyword, df_prices) if keyword else None
        if matched:
            global_krw = calculate_total_import_cost(matched['global_usd'], usd)
            prices, raw, dates = matched['trend_prices'], matched['raw_prices'], matched["dates"]
            kr_avg, kr_min, kr_max = sum(prices)/len(prices) if prices else 0, min(raw) if raw else 0, max(raw) if raw else 0
            n_data = len(raw)
            df_full = pd.DataFrame({"날짜": dates, "가격(만원)": prices})
            df_1m = df_full.tail(4) if len(df_full) >= 4 else df_full
            sig = ("●●●●","강함","#5C9EFF") if n_data>=15 else ("●●●","보통","#7BB3FF") if n_data>=8 else ("●●","약함","#9BC4FF") if n_data>=4 else ("●","희미","#B8D5FF")
            st.markdown("<div class='section-title'>📊 시세 요약</div>", unsafe_allow_html=True)
            st.markdown(f'<div class="metric-grid"><div class="metric-card"><div style="font-size:.65rem;color:#888">평균가</div><div style="font-size:1.05rem;font-weight:800;color:#eee">{kr_avg:,.1f}만</div></div><div class="metric-card"><div style="font-size:.65rem;color:#888">시그널</div><div style="font-size:.9rem"><span style="color:{sig[2]}">{sig[0]}</span> {sig[1]}</div></div><div class="metric-card"><div style="font-size:.65rem;color:#888">최고가</div><div style="font-size:1.05rem;font-weight:800;color:#eee">{kr_max:,.1f}만</div></div><div class="metric-card"><div style="font-size:.65rem;color:#888">최저가</div><div style="font-size:1.05rem;font-weight:800;color:#eee">{kr_min:,.1f}만</div></div></div><p style="margin-top:8px;font-size:.8rem;color:#8a9aab">💡 시그널은 수집된 거래 데이터 건수에 비례합니다.</p>', unsafe_allow_html=True)
            st.markdown("<div class='section-title'>📈 전체 시세</div>", unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=dates, y=prices, mode='lines+markers', name='전체 시세', line=dict(color='#7B8B9C', width=2, shape='spline', smoothing=0.5), marker=dict(size=6, color='#7B8B9C'), fill='tozeroy', fillcolor='rgba(123,139,156,0.06)', hovertemplate='<b>%{x}</b><br>%{y:,.1f}만원<extra></extra>'))
            if len(df_1m) >= 2: fig.add_trace(go.Scatter(x=df_1m['날짜'].tolist(), y=df_1m['가격(만원)'].tolist(), mode='lines+markers', name='최근 1달', line=dict(color=CHART_BLUE, width=3.2, shape='spline', smoothing=0.55), marker=dict(size=10, color=CHART_BLUE_LIGHT), fill='tozeroy', fillcolor=CHART_BLUE_HIGHLIGHT, hovertemplate='<b>%{x}</b><br>%{y:,.1f}만원<extra></extra>'))
            if global_krw > 0: fig.add_trace(go.Scatter(x=dates, y=[global_krw]*len(dates), mode='lines', name='해외직구', line=dict(color='#8B9BAB', width=1.8, dash='dot'), hovertemplate=f'해외직구: {global_krw:,.1f}만원<extra></extra>'))
            y_min, y_max = max(0, min(prices)*0.92) if prices else 0, max(prices)*1.1 if prices else 100
            if y_max - y_min < 10: y_max = y_min + 20
            fig.update_layout(height=280, margin=dict(l=52, r=24, t=12, b=40), title=dict(text=''), hovermode='x unified', xaxis=dict(showgrid=False, title='', tickfont=dict(size=12, color='#b8c5d4')), yaxis=dict(title='만원', showgrid=True, gridcolor='rgba(92,158,255,0.12)', range=[y_min, y_max], tickfont=dict(size=12, color='#e8eef4')), paper_bgcolor='#0E1117', plot_bgcolor='rgba(20,25,35,0.8)', font_color='#b8c5d4', showlegend=True, legend=dict(orientation='h', y=1.05, x=0, xanchor='left', bgcolor='#0E1117'), template='plotly_dark', dragmode=False)
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False}, key="radar_trend_chart")
            st.markdown("<div class='section-title'>📊 가격 분포</div>", unsafe_allow_html=True)
            if len(raw) >= 1:
                n_bins = min(15, max(3, len(raw)//2)) if len(raw) > 1 else 5
                hist, edges = np.histogram(raw, bins=n_bins)
                mid = [(edges[i]+edges[i+1])/2 for i in range(len(hist))]
                fig2 = go.Figure(go.Bar(x=mid, y=hist, marker=dict(color=hist, colorscale=[[0,'rgba(92,158,255,0.35)'],[0.4,'rgba(92,158,255,0.7)'],[0.7,CHART_BLUE],[1,CHART_BLUE_LIGHT]], line=dict(width=0), cornerradius=12, opacity=0.92, cmin=0), hovertemplate='<b>%{x:,.0f}만원대</b><br>%{y}건<extra></extra>'))
                fig2.update_layout(height=220, margin=dict(l=48, r=24, t=12, b=40), xaxis=dict(title='가격(만원)'), yaxis=dict(title='건수'), paper_bgcolor='#0E1117', plot_bgcolor='rgba(20,25,35,0.8)', font_color='#b8c5d4', template='plotly_dark')
                st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False}, key="radar_dist_chart")
            if global_krw > 0: gap = kr_avg - global_krw; st.markdown(f"<div class='metric-card'><div style='font-size:.65rem;color:#888'>🌎 직구 추산가</div><div style='font-size:1.05rem;font-weight:800;color:#eee'>{global_krw:,.1f}만</div><div style='color:{\"#ff4b4b\" if gap>0 else \"#4b89ff\"}'>{'Gap: +' if gap>0 else 'Gap: '}{gap:,.1f}만 ({'이득' if gap>0 else '손해'})</div></div>", unsafe_allow_html=True)
        else:
            st.markdown("**Waiting for Signal...**")
            fig_w = go.Figure(go.Scatter(x=range(20), y=[20,22,25,30,28,25,22,20,18,15,18,22,26,32,35,30,25,20,18,20], fill='tozeroy', fillcolor='rgba(92,158,255,0.12)', line=dict(color=CHART_BLUE, width=1.5, shape='spline', smoothing=0.5)))
            fig_w.update_layout(height=250, margin=dict(l=0,r=0,t=5,b=0), paper_bgcolor='#0E1117', plot_bgcolor='#0E1117', font_color='#b8c5d4', xaxis=dict(showticklabels=False), yaxis=dict(showticklabels=False), template='plotly_dark')
            st.plotly_chart(fig_w, use_container_width=True, config={'displayModeBar': False}, key="radar_dummy_chart")

with tab_source:
    st.markdown("#### 📂 Market Sources")
    c1, c2 = st.columns(2)
    with c1: st.markdown("""<div style="font-size:.85rem;font-weight:700;color:#666;margin:20px 0 10px;border-bottom:1px solid #333;padding-bottom:5px">💻 IT / Tech</div><a href="https://quasarzone.com" target="_blank" class="source-card card-quasar" style="text-decoration:none"><span>퀘이사존</span></a><a href="https://coolenjoy.net" target="_blank" class="source-card card-cool" style="text-decoration:none"><span>쿨엔조이</span></a><a href="https://meeco.kr" target="_blank" class="source-card card-meeco" style="text-decoration:none"><span>미코</span></a><a href="https://www.clien.net" target="_blank" class="source-card card-clien" style="text-decoration:none"><span>클리앙</span></a><div style="font-size:.85rem;font-weight:700;color:#666;margin:20px 0 10px;border-bottom:1px solid #333;padding-bottom:5px">📷 Camera</div><a href="https://www.slrclub.com" target="_blank" class="source-card card-slr" style="text-decoration:none"><span>SLR클럽</span></a><a href="http://www.leicaclub.net/" target="_blank" class="source-card card-leica" style="text-decoration:none"><span>라이카 클럽</span></a></div>""", unsafe_allow_html=True)
    with c2: st.markdown("""<div style="font-size:.85rem;font-weight:700;color:#666;margin:20px 0 10px;border-bottom:1px solid #333;padding-bottom:5px">👟 Fashion</div><a href="https://kream.co.kr" target="_blank" class="source-card" style="text-decoration:none;border-left:6px solid #FFF"><span>KREAM</span></a><a href="https://cafe.naver.com/sssw" target="_blank" class="source-card" style="text-decoration:none;border-left:6px solid #333"><span>나이키매니아</span></a><a href="https://eomisae.co.kr" target="_blank" class="source-card" style="text-decoration:none;border-left:6px solid #8E24AA"><span>어미새</span></a><div style="font-size:.85rem;font-weight:700;color:#666;margin:20px 0 10px;border-bottom:1px solid #333;padding-bottom:5px">🍎 Life</div><a href="https://web.joongna.com" target="_blank" class="source-card card-joongna" style="text-decoration:none"><span>중고나라</span></a><a href="https://bbs.ruliweb.com/market" target="_blank" class="source-card card-ruli" style="text-decoration:none"><span>루리웹</span></a></div>""", unsafe_allow_html=True)

with tab_tools:
    t1, t2 = st.columns(2)
    with t1: st.markdown("#### 📦 배송 조회"); carrier = st.selectbox("택배사", ["CJ대한통운", "우체국택배", "한진택배", "롯데택배", "로젠택배"]); track_no = st.text_input("운송장 번호", placeholder="- 없이 숫자만"); st.link_button("네이버 조회", f"https://search.naver.com/search.naver?query={urllib.parse.quote(f'{carrier} {track_no}')}", use_container_width=True) if track_no else None
    with t2: st.markdown("#### 💱 관세 계산기"); curr = st.radio("통화", ["🇺🇸 USD", "🇯🇵 JPY"], horizontal=True); p = st.number_input("물품 가격 ($)" if "USD" in curr else "물품 가격 (¥)", 190 if "USD" in curr else 15000, step=10 if "USD" in curr else 1000); krw = p * usd if "USD" in curr else p * (jpy/100); st.markdown(f"### ≈ {krw:,.0f} 원"); st.success("✅ 면세") if (p<=200 and "USD" in curr) or (krw/usd<=150 and "JPY" in curr) else st.error("🚨 과세 대상")

with tab_safety:
    st.markdown("#### 👮‍♂️ 사기 피해 방지")
    st.markdown("""<div class="scam-box"><ul style="list-style:none;padding:0"><li style="color:#ddd;margin-bottom:15px;border-bottom:1px solid #333;padding-bottom:10px"><span style="color:#ff4b4b;font-weight:800;display:block;margin-bottom:4px">🚫 카카오톡 유도 100% 사기</span>판매자가 카톡 아이디를 주면 즉시 차단하세요.</li><li style="color:#ddd;margin-bottom:15px;border-bottom:1px solid #333;padding-bottom:10px"><span style="color:#ff4b4b;font-weight:800;display:block;margin-bottom:4px">🚫 가짜 안전결제 링크</span>판매자가 직접 보낸 결제 링크는 가짜입니다.</li><li style="color:#ddd;margin-bottom:15px"><span style="color:#ff4b4b;font-weight:800;display:block;margin-bottom:4px">🚫 더치트 2회 조회 필수</span>계좌번호 + 전화번호 모두 조회하세요.</li></ul></div>""", unsafe_allow_html=True)
    st.link_button("👮‍♂️ 더치트 무료 조회", "https://thecheat.co.kr", type="secondary", use_container_width=True)

st.markdown('<div style="font-size:.7rem;color:#333;margin-top:80px;text-align:center;margin-bottom:50px">© 2026 RADAR | Global Price Intelligence</div>', unsafe_allow_html=True)

diff_usd, diff_jpy = usd - usd_prev, jpy - jpy_prev
st.markdown(f'<div class="ticker-wrap"><div style="display:inline-block;white-space:nowrap;padding-left:100%;animation:ticker 40s linear infinite"><span style="margin-right:40px;font-size:.8rem;color:#888">USD/KRW <span style="color:#eee;font-weight:700">{usd:,.0f}원 {"🔺" if diff_usd>=0 else "🔻"} {abs(diff_usd):.1f}</span></span><span style="margin-right:40px;font-size:.8rem;color:#888">JPY/KRW <span style="color:#eee;font-weight:700">{jpy:,.0f}원 {"🔺" if diff_jpy>=0 else "▼"} {abs(diff_jpy):.1f}</span></span><span style="margin-right:40px;font-size:.8rem;color:#888">미국면세 <span style="color:#eee;font-weight:700">$200 (약 {usd*200/10000:.0f}만원)</span></span><span style="margin-right:40px;font-size:.8rem;color:#888">SYSTEM <span style="color:#00ff88;font-weight:700">ONLINE 🟢</span></span></div></div>', unsafe_allow_html=True)
