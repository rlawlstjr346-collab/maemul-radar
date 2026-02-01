"""
RADAR 메인 코드 백업 | 2025.01.31
- 구글 시트 새 형식 (분류/브랜드/모델명/상세스펙) 지원
- 시그널 설명 추가
- 그래프 UX 개선
- Plotly legend bgcolor 수정
"""

"""
RADAR 메인 코드 백업 | 2025.01.31
- 구글 시트 새 형식 (분류/브랜드/모델명/상세스펙) 지원
- 시그널 설명 추가, 그래프 UX 개선
"""
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

# ------------------------------------------------------------------
# [1] 앱 기본 설정 (RADAR V15.0: Pro Dashboard Cards)
# ------------------------------------------------------------------
st.set_page_config(
    page_title="RADAR",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ------------------------------------------------------------------
# [2] 데이터 로드
# ------------------------------------------------------------------
sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQS8AftSUmG9Cr7MfczpotB5hhl1DgjH4hRCgXH5R8j5hykRiEf0M9rEyEq3uj312a5RuI4zMdjI5Jr/pub?output=csv"

@st.cache_data(ttl=60)
def load_price_data():
    try:
        df = pd.read_csv(sheet_url, encoding='utf-8-sig')
        df.columns = df.columns.str.strip().str.replace('\ufeff', '')
        return df
    except Exception as e:
        return pd.DataFrame()

# ------------------------------------------------------------------
# [3] 로직 (키워드 엔진 V2 + 시트 매칭)
# ------------------------------------------------------------------
def _get_date_cols(df):
    skip = {'키워드', 'keyword', '모델명 (상세스펙/상태)', '모델명', '상세스펙', '분류', '브랜드', '시세 (5주치)', '해외평균(USD)', 'name', 'dates', 'prices'}
    date_cols = [c for c in df.columns if str(c).strip() not in skip and any(x in str(c) for x in ['월', '주', 'week', 'date', '날짜'])]
    return date_cols if date_cols else ["12월4주", "1월1주", "1월2주", "1월3주", "1월4주"]

def _get_col(row, *names):
    """컬럼명 유연 매칭"""
    for n in names:
        v = row.get(n, None)
        if pd.notna(v) and str(v).strip():
            return str(v).strip()
    return ''

def get_trend_data_from_sheet(user_query, df):
    if df.empty or not user_query: return None
    user_clean = user_query.lower().replace(" ", "").strip()
    date_cols = _get_date_cols(df)
    for _, row in df.iterrows():
        try:
            k_val = _get_col(row, '모델명', '키워드', 'keyword')
            if not k_val: continue
            sheet_keyword = str(k_val).lower().replace(" ", "").strip()
            if sheet_keyword in user_clean or user_clean in sheet_keyword:
                trend_prices = []
                valid_dates = []
                for col in date_cols:
                    if col in df.columns:
                        v_raw = str(row.get(col, '0')).strip()
                        v_clean = re.sub(r'[^0-9.]', '', v_raw)
                        if v_clean:
                            try:
                                val = float(v_clean)
                                if val > 0:
                                    trend_prices.append(val)
                                    valid_dates.append(col)
                            except: pass
                raw_str = str(row.get('시세 (5주치)', row.get('prices_raw', row.get('거래가목록', '')))).strip()
                raw_prices = []
                if raw_str and raw_str.lower() != 'nan':
                    for p in raw_str.split(','):
                        clean_p = re.sub(r'[^0-9.]', '', p)
                        if clean_p:
                            try: val = float(clean_p); raw_prices.append(val) if val > 0 else None
                            except: continue
                if not raw_prices: raw_prices = trend_prices
                g_raw = str(row.get('해외평균(USD)', '0')).strip()
                g_clean = re.sub(r'[^0-9.]', '', g_raw)
                global_usd = float(g_clean) if g_clean else 0.0
                if not trend_prices: continue
                name = _get_col(row, '모델명', '모델명 (상세스펙/상태)')
                spec = _get_col(row, '상세스펙')
                if spec:
                    name = f"{name} ({spec})".strip() if name else spec
                name = name or '상품명 미상'
                return {"name": name, "dates": valid_dates, "trend_prices": trend_prices, "raw_prices": raw_prices, "global_usd": global_usd}
        except: continue
    return None

# ... (나머지 코드는 radar.py와 동일)
# 전체 코드는 /Users/cactus/Desktop/radar.py 참조

