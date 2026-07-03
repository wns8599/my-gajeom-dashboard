import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="조달청 가점관리 대시보드", layout="wide", page_icon="bar_chart")

# --- 설정 및 스타일 ---
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ"
PAY_MONTH, DAY_AMOUNT, DAY_COUNT, REPORT_AMOUNT, REPORT_COUNT = "지급월", "일용_금액", "일용_인원", "신고_금액", "신고_인원"
RAW_COLS = [PAY_MONTH, DAY_AMOUNT, DAY_COUNT, REPORT_AMOUNT, REPORT_COUNT]
COLUMN_ALIASES = {PAY_MONTH: ["지급월"], DAY_AMOUNT: ["일용_금액"], DAY_COUNT: ["일용_인원"], REPORT_AMOUNT: ["신고_금액"], REPORT_COUNT: ["신고_인원"]}

st.markdown("""
    <style>
    .page-title { font-size: 28px; font-weight: 800; margin-bottom: 20px; }
    [data-testid="stMetricValue"] { font-size: 16px !important; }
    .status-card { border-radius: 12px; padding: 12px; border: 1px solid #ddd; margin-bottom: 10px; }
    .card-need { background: #ffe8e3; border-color: #ffb4a8; }
    .card-ok { background: #eaf7ef; border-color: #9bd8b7; }
    .detail-text { font-size: 12px; color: #666; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- 함수 정의 ---
def clean(df):
    df = df.rename(columns={a: s for s, aliases in COLUMN_ALIASES.items() for a in aliases})
    for col in RAW_COLS[1:]: df[col] = pd.to_numeric(df[col].astype(str).str.replace(r"[^0-9\-]", "", regex=True), errors="coerce").fillna(0)
    df[PAY_MONTH] = pd.to_datetime(df[PAY_MONTH], errors="coerce")
    return df.dropna(subset=[PAY_MONTH]).groupby(df[PAY_MONTH].dt.to_period("M").dt.to_timestamp(), as_index=False)[RAW_COLS[1:]].sum()

def compute(df):
    indexed = df.set_index(PAY_MONTH)
    rows = []
    for pay_month in df[PAY_MONTH]:
        target = pay_month + relativedelta(months=10)
        recent = pd.date_range(target + relativedelta(months=-7), target + relativedelta(months=-2), freq="MS")
        prev = pd.date_range(target + relativedelta(months=-13), target + relativedelta(months=-8), freq="MS")
        r_amt, r_cnt = indexed.reindex(recent).fillna(0)[[DAY_AMOUNT, REPORT_AMOUNT]].sum().sum(), indexed.reindex(recent).fillna(0)[[DAY_COUNT, REPORT_COUNT]].sum().sum()
        p_amt, p_cnt = indexed.reindex(prev).fillna(0)[[DAY_AMOUNT, REPORT_AMOUNT]].sum().sum(), indexed.reindex(prev).fillna(0)[[DAY_COUNT, REPORT_COUNT]].sum().sum()
        rows.append({"target": target, "r_start": recent[0], "r_end": recent[-1], "p_start": prev[0], "p_end": prev[-1], 
                     "gap_amt": max(0, p_amt - r_amt + 1), "gap_cnt": max(0, p_cnt - r_cnt + 1), 
                     "status": "충족" if r_amt > p_amt and r_cnt > p_cnt else "보충필요"})
    return pd.DataFrame(rows)

# --- 화면 구성 ---
st.markdown('<div class="page-title">조달청 가점관리 대시보드</div>', unsafe_allow_html=True)
sheet_url = st.text_input("구글 시트 URL", value=DEFAULT_SHEET_URL)
try:
    df = clean(pd.read_csv(sheet_url.rstrip("/") + "/export?format=csv"))
    res = compute(df)
    
    col1, col2 = st.columns([1, 2])
    with col1:
        edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        if st.button("새로고침"): st.rerun()
    with col2:
        st.subheader("대상월 현황")
        cards = st.columns(3)
        for i, (_, row) in enumerate(res.iterrows()):
            with cards[i % 3]:
                st.markdown(f'<div class="status-card {"card-need" if row["status"]=="보충필요" else "card-ok"}">'
                            f'<div>{row["target"].strftime("%Y-%m")}</div><strong>{row["status"]}</strong></div>', unsafe_allow_html=True)
                with st.expander("상세보기"):
                    st.markdown(f'<div class="detail-text">비교: {row["p_start"].strftime("%Y-%m")}~{row["p_end"].strftime("%Y-%m")} vs {row["r_start"].strftime("%Y-%m")}~{row["r_end"].strftime("%Y-%m")}</div>', unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    c1.metric("부족 금액", f"{int(row['gap_amt']//10000):,}만원")
                    c2.metric("부족 인원", f"{int(row['gap_cnt']):,}명")
except Exception as e:
    st.error(f"데이터를 불러올 수 없습니다: {e}")
