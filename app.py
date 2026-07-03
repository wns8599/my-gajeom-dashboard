import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

st.set_page_config(
    page_title="조달청 가점관리 대시보드",
    layout="wide",
    page_icon="bar_chart",
    initial_sidebar_state="collapsed",
)

DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ"

PAY_MONTH = "지급월"
DAY_AMOUNT = "일용_금액"
DAY_COUNT = "일용_인원"
REPORT_AMOUNT = "신고_금액"
REPORT_COUNT = "신고_인원"
RAW_COLS = [PAY_MONTH, DAY_AMOUNT, DAY_COUNT, REPORT_AMOUNT, REPORT_COUNT]

COLUMN_ALIASES = {
    PAY_MONTH: ["지급월"],
    DAY_AMOUNT: ["일용_금액"],
    DAY_COUNT: ["일용_인원"],
    REPORT_AMOUNT: ["신고_금액"],
    REPORT_COUNT: ["신고_인원"],
}

TARGET_LAG_MONTHS = 10
RECENT_OFFSET_START, RECENT_OFFSET_END = -7, -2
PREV_OFFSET_START, PREV_OFFSET_END = -13, -8
STATUS_OK, STATUS_NEED, STATUS_NODATA = "충족", "보충필요", "데이터부족"

st.markdown(
    """
    <style>
    .page-title { font-size: 28px; font-weight: 800; color: #1d2433; margin-bottom: 20px; }
    [data-testid="stMetricValue"] { font-size: 16px !important; }
    .status-card { border-radius: 12px; padding: 12px; border: 1px solid rgba(16, 24, 40, 0.08); margin-bottom: 10px; }
    .card-need { background: #ffe8e3; border-color: #ffb4a8; }
    .card-ok { background: #eaf7ef; border-color: #9bd8b7; }
    .card-caution { background: #fff4cc; border-color: #f4d06f; }
    .card-nodata { background: #f2f4f7; border-color: #d0d5dd; }
    .detail-text { font-size: 12px; color: #667085; margin-bottom: 4px; }
    </style>
    """,
    unsafe_allow_html=True,
)

def month_label(ts): return pd.Timestamp(ts).strftime("%Y-%m")
def compact_money(value): 
    if pd.isna(value): return "-"
    return f"{int(abs(value)//10000):,}만원"
def people(value): return "-" if pd.isna(value) else f"{int(value):,}명"
def m(ts, n): return ts + relativedelta(months=n)

@st.cache_data(ttl=60)
def load_sheet(url): return pd.read_csv(url.rstrip("/") + "/export?format=csv")

def clean(df):
    df = df.copy()
    rename_map = {a: s for s, aliases in COLUMN_ALIASES.items() for a in aliases}
    df = df.rename(columns=rename_map)
    for col in RAW_COLS[1:]: df[col] = pd.to_numeric(df[col].astype(str).str.replace(r"[^0-9\-]", "", regex=True), errors="coerce").fillna(0)
    df[PAY_MONTH] = pd.to_datetime(df[PAY_MONTH], errors="coerce")
    return df.dropna(subset=[PAY_MONTH]).groupby(df[PAY_MONTH].dt.to_period("M").dt.to_timestamp(), as_index=False)[RAW_COLS[1:]].sum()

def compute(df):
    indexed = df.set_index(PAY_MONTH)
    earliest = df[PAY_MONTH].min()
    rows = []
    for pay_month in df[PAY_MONTH]:
        target = m(pay_month, TARGET_LAG_MONTHS)
        recent_months = pd.date_range(m(target, RECENT_OFFSET_START), m(target, RECENT_OFFSET_END), freq="MS")
        prev_months = pd.date_range(m(target, PREV_OFFSET_START), m(target, PREV_OFFSET_END), freq="MS")
        
        recent_amt = indexed.reindex(recent_months).fillna(0)[[DAY_AMOUNT, REPORT_AMOUNT]].sum().sum()
        recent_cnt = indexed.reindex(recent_months).fillna(0)[[DAY_COUNT, REPORT_COUNT]].sum().sum()
        prev_amt = indexed.reindex(prev_months).fillna(0)[[DAY_AMOUNT, REPORT_AMOUNT]].sum().sum()
        prev_cnt = indexed.reindex(prev_months).fillna(0)[[DAY_COUNT, REPORT_COUNT]].sum().sum()
        
        data_ok = prev_months[0] >= earliest
        status = STATUS_NODATA if not data_ok else (STATUS_OK if recent_amt > prev_amt and recent_cnt > prev_cnt else STATUS_NEED)
        rows.append({"target": target, "recent_start": recent_months[0], "recent_end": recent_months[-1], "recent_amt": recent_amt, "recent_cnt": recent_cnt, 
                     "prev_start": prev_months[0], "prev_end": prev_months[-1], "prev_amt": prev_amt, "prev_cnt": prev_cnt, "status": status, 
                     "gap_amt": max(0, prev_amt - recent_amt + 1), "gap_cnt": max(0, prev_cnt - recent_cnt + 1)})
    return pd.DataFrame(rows)

# UI
st.markdown('<div class="page-title">조달청 가점관리 대시보드</div>', unsafe_allow_html=True)
with st.expander("⚙ 설정"):
    sheet_url = st.text_input("구글 시트 URL", value=DEFAULT_SHEET_URL)
    months_ahead = st.slider("표시 범위", 3, 18, 9)

raw_df = clean(load_sheet(sheet_url))
result = compute(raw_df)
now = pd.Timestamp(datetime.now().replace(day=1))
view = result[(result["target"] >= m(now, -1)) & (result["target"] <= m(now, months_ahead))]

col1, col2 = st.columns([1, 1.5], gap="large")
with col1:
    edited = st.data_editor(raw_df.copy(), num_rows="dynamic", use_container_width=True)
with col2:
    st.subheader("대상월 현황")
    cols = st.columns(3)
    for i, (_, row) in enumerate(view.iterrows()):
        with cols[i % 3]:
            st.markdown(f'<div class="status-card {"card-need" if row["status"]==STATUS_NEED else "card-ok"}"><div>{month_label(row["target"])}</div><strong>{row["status"]}</strong></div>', unsafe_allow_html=True)
            with st.expander("상세보기"):
                st.markdown(f'<div class="detail-text">이전: {month_label(row["prev_start"])}~{month_label(row["prev_end"])}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="detail-text">최근: {month_label(row["recent_start"])}~{month_label(row["recent_end"])}</div>', unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                c1.metric("부족 금액", compact_money(row["gap_amt"]))
                c2.metric("부족 인원", people(row["gap_cnt"]))
