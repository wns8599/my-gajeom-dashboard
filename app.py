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
    PAY_MONTH: ["지급월", "吏湲됱썡"],
    DAY_AMOUNT: ["일용_금액", "?쇱슜_湲덉븸"],
    DAY_COUNT: ["일용_인원", "?쇱슜_?몄썝"],
    REPORT_AMOUNT: ["신고_금액", "?밴퀬_湲덉븸"],
    REPORT_COUNT: ["신고_인원", "?밴퀬_?몄썝"],
}

TARGET_LAG_MONTHS = 10
RECENT_OFFSET_START, RECENT_OFFSET_END = -7, -2
PREV_OFFSET_START, PREV_OFFSET_END = -13, -8

STATUS_OK = "충족"
STATUS_NEED = "보충필요"
STATUS_NODATA = "데이터부족"


st.markdown(
    """
    <style>
    .block-container {
    padding-top: 2.2rem !important;
}

* {
    word-break: break-word;
    overflow-wrap: anywhere;
    white-space: normal;
}

h1, h2, h3 {
    line-height: 1.3 !important;
    margin-top: 10px !important;
}

div[data-testid="stExpanderDetails"] {
    font-size: 12.5px !important;
}
    :root {
        --surface: #ffffff;
        --muted: #667085;
        --line: #e6e8ee;
        --ink: #1d2433;
        --green: #168a52;
        --green-bg: #eaf7ef;
        --red: #c83f3f;
        --red-bg: #ffe8e3;
        --yellow: #9a6700;
        --yellow-bg: #fff4cc;
        --gray-bg: #f2f4f7;
        --blue: #2f6fed;
        --blue-bg: #edf4ff;
    }
    .block-container {
        padding-top: 1.3rem;
        padding-bottom: 2.6rem;
    }
    .page-title {
        font-size: 28px;
        font-weight: 800;
        color: var(--ink);
        margin-bottom: 2px;
    }
    .page-subtitle {
        color: var(--muted);
        font-size: 14px;
        margin-bottom: 18px;
    }
    .recommend-card {
        border: 1px solid var(--line);
        border-radius: 14px;
        background: linear-gradient(135deg, #fff7ed 0%, #fff 54%, #eef6ff 100%);
        padding: 20px 22px;
        box-shadow: 0 10px 24px rgba(16, 24, 40, 0.08);
        margin-bottom: 14px;
    }
    .recommend-label {
        color: var(--muted);
        font-size: 13px;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .recommend-value {
        color: var(--ink);
        font-size: 30px;
        line-height: 1.1;
        font-weight: 850;
    }
    .recommend-people {
        color: var(--ink);
        font-size: 20px;
        font-weight: 800;
        margin-top: 6px;
    }
    .recommend-note {
        color: var(--muted);
        font-size: 13px;
        margin-top: 10px;
    }
    .status-card {
        border-radius: 12px;
        padding: 12px 13px 10px;
        min-height: 84px;
        border: 1px solid rgba(16, 24, 40, 0.08);
        box-shadow: 0 2px 8px rgba(16, 24, 40, 0.05);
        margin-bottom: 6px;
    }
    .card-need {
        background: var(--red-bg);
        border-color: #ffb4a8;
    }
    .card-caution {
        background: var(--yellow-bg);
        border-color: #f4d06f;
    }
    .card-ok {
        background: var(--green-bg);
        border-color: #9bd8b7;
    }
    .card-nodata {
        background: var(--gray-bg);
        border-color: #d0d5dd;
    }
    .status-title {
        color: var(--ink);
        font-size: 16px;
        line-height: 1.2;
        font-weight: 850;
        margin-bottom: 8px;
    }
    .status-row {
        display: flex;
        align-items: center;
        gap: 6px;
        color: var(--ink);
        font-size: 13px;
        line-height: 1.35;
        margin-top: 2px;
    }
    .status-number {
        font-size: 15px;
        font-weight: 850;
    }
    .section-label {
        color: var(--muted);
        font-size: 13px;
        font-weight: 800;
        margin: 12px 0 8px;
    }
    div[data-testid="stMetric"] {
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 10px 12px;
    }
    div[data-testid="stExpander"] {
        border: 0;
        background: transparent;
        box-shadow: none;
    }
    div[data-testid="stExpander"] details {
        border: 1px solid var(--line);
        border-radius: 10px;
        background: #fff;
        overflow: hidden;
    }
    div[data-testid="stExpander"] summary {
        min-height: 34px;
        font-size: 13px;
        font-weight: 750;
    }
    div[data-testid="stExpander"] summary {
        padding: 0;
    }
    div[data-testid="stExpander"] summary p {
        margin: 0;
    }
    div[data-testid="stExpander"] div[data-testid="stExpanderDetails"] {
        padding: 12px 14px 14px;
        border-top: 1px solid var(--line);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def month_label(ts: pd.Timestamp, fmt: str = "%Y-%m") -> str:
    return pd.Timestamp(ts).strftime(fmt)


def money(value) -> str:
    if pd.isna(value):
        return "-"
    return f"{int(value):,}원"


def people(value) -> str:
    if pd.isna(value):
        return "-"
    return f"{int(value):,}명"


def compact_money(value) -> str:
    if pd.isna(value):
        return "-"
    amount = int(value)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    manwon = amount // 10000
    if manwon <= 0 and amount > 0:
        manwon = 1
    return f"{sign}{manwon:,}만원"


def m(ts: pd.Timestamp, n: int) -> pd.Timestamp:
    return ts + relativedelta(months=n)


@st.cache_data(ttl=60)
def load_sheet(url: str) -> pd.DataFrame:
    csv_url = url.rstrip("/") + "/export?format=csv"
    return pd.read_csv(csv_url)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename_map = {}
    for standard_col, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = standard_col
                break
    return df.rename(columns=rename_map)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df)
    for col in RAW_COLS:
        if col not in df.columns:
            df[col] = pd.NaT if col == PAY_MONTH else 0

    df = df[RAW_COLS].copy()
    for col in RAW_COLS[1:]:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(r"[^0-9\\-]", "", regex=True),
            errors="coerce",
        ).fillna(0)

    df[PAY_MONTH] = pd.to_datetime(df[PAY_MONTH], errors="coerce")
    df = df.dropna(subset=[PAY_MONTH])
    df[PAY_MONTH] = df[PAY_MONTH].dt.to_period("M").dt.to_timestamp()
    df = df.groupby(PAY_MONTH, as_index=False)[RAW_COLS[1:]].sum().sort_values(PAY_MONTH)
    return df.reset_index(drop=True)


def window_sum(indexed: pd.DataFrame, months: pd.DatetimeIndex):
    sub = indexed.reindex(months).fillna(0)
    amount = sub[DAY_AMOUNT].sum() + sub[REPORT_AMOUNT].sum()
    count = sub[DAY_COUNT].sum() + sub[REPORT_COUNT].sum()
    return amount, count


def compute(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    indexed = df.set_index(PAY_MONTH)
    earliest = df[PAY_MONTH].min()
    rows = []

    for pay_month in df[PAY_MONTH]:
        target = m(pay_month, TARGET_LAG_MONTHS)
        recent_start = m(target, RECENT_OFFSET_START)
        recent_end = m(target, RECENT_OFFSET_END)
        prev_start = m(target, PREV_OFFSET_START)
        prev_end = m(target, PREV_OFFSET_END)

        recent_months = pd.date_range(recent_start, recent_end, freq="MS")
        prev_months = pd.date_range(prev_start, prev_end, freq="MS")

        recent_amt, recent_cnt = window_sum(indexed, recent_months)
        prev_amt, prev_cnt = window_sum(indexed, prev_months)
        data_ok = prev_start >= earliest

        if not data_ok:
            status, gap_amt, gap_cnt = STATUS_NODATA, None, None
        else:
            amt_ok = recent_amt > prev_amt
            cnt_ok = recent_cnt > prev_cnt
            status = STATUS_OK if amt_ok and cnt_ok else STATUS_NEED
            gap_amt = 0 if amt_ok else int(prev_amt - recent_amt) + 1
            gap_cnt = 0 if cnt_ok else int(prev_cnt - recent_cnt) + 1

        rows.append(
            {
                "target": target,
                "recent_start": recent_start,
                "recent_end": recent_end,
                "recent_amt": recent_amt,
                "recent_cnt": recent_cnt,
                "prev_start": prev_start,
                "prev_end": prev_end,
                "prev_amt": prev_amt,
                "prev_cnt": prev_cnt,
                "status": status,
                "gap_amt": gap_amt,
                "gap_cnt": gap_cnt,
                "recent_months": recent_months,
            }
        )

    result = pd.DataFrame(rows).drop_duplicates(subset="target").sort_values("target")
    return result.reset_index(drop=True)


def display_status(row: pd.Series) -> str:
    if row["status"] != STATUS_NEED:
        return row["status"]
    gap_amt = row["gap_amt"] if pd.notna(row["gap_amt"]) else 0
    gap_cnt = row["gap_cnt"] if pd.notna(row["gap_cnt"]) else 0
    if gap_amt <= 0 or gap_cnt <= 0:
        return "주의"
    return STATUS_NEED


def card_class(row: pd.Series) -> str:
    status = display_status(row)
    return {
        STATUS_OK: "card-ok",
        STATUS_NEED: "card-need",
        "주의": "card-caution",
        STATUS_NODATA: "card-nodata",
    }.get(status, "card-nodata")


def render_recommend_card(amount, count, target_label: str):
    st.markdown(
        f"""
        <div class="recommend-card">
            <div class="recommend-label">이번달 추천 지급</div>
            <div class="recommend-value">{compact_money(amount)}</div>
            <div class="recommend-people">{people(count)}</div>
            <div class="recommend-note">가장 가까운 목표월 : {target_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_card(row: pd.Series):
    gap_amt = row["gap_amt"] if pd.notna(row["gap_amt"]) else 0
    gap_cnt = row["gap_cnt"] if pd.notna(row["gap_cnt"]) else 0
    status = display_status(row)

    if row["status"] == STATUS_NODATA:
        icon = "⚪"
        amount_line = "자료 부족"
        count_line = "자료 부족"
    elif row["status"] == STATUS_OK:
        icon = "🟢"
        amount_line = "충족"
        count_line = "충족"
    elif status == "주의":
        icon = "🟡"
        amount_line = f"부족 {compact_money(gap_amt)}" if gap_amt > 0 else "금액 충족"
        count_line = f"부족 {people(gap_cnt)}" if gap_cnt > 0 else "인원 충족"
    else:
        icon = "🔴"
        amount_line = f"부족 {compact_money(gap_amt)}"
        count_line = f"부족 {people(gap_cnt)}"

    st.markdown(
        f"""
        <div class="status-card {card_class(row)}">
            <div class="status-title">{icon} {month_label(row["target"])}</div>
            <div class="status-row">💰 <span class="status-number">{amount_line}</span></div>
            <div class="status-row">👤 <span class="status-number">{count_line}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card_button_label(row: pd.Series) -> str:
    return "▼ 상세보기"


def render_detail(row: pd.Series):
    st.caption(
        f"비교 기간: 이전 {month_label(row['prev_start'])}~{month_label(row['prev_end'])} / "
        f"최근 {month_label(row['recent_start'])}~{month_label(row['recent_end'])}"
    )

    if row["status"] == STATUS_NODATA:
        st.info("이 목표월을 판정하려면 이전 6개월 구간 전체가 포함된 지급 데이터가 필요합니다.")
        return

    c1, c2 = st.columns(2)
    c1.markdown(
        "최근 6개월",
        f"{compact_money(row['recent_amt'])} / {people(row['recent_cnt'])}",
    )
    c2.markdown(
        "이전 6개월",
        f"{compact_money(row['prev_amt'])} / {people(row['prev_cnt'])}",
    )

    c3, c4 = st.columns(2)
    c3.markdown("부족 금액", compact_money(row["gap_amt"]))
    c4.markdown("부족 인원", people(row["gap_cnt"]))


st.markdown('<div class="page-title">조달청 가점관리 대시보드</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-subtitle">목표월별 가점 충족 여부와 부족한 금액·인원을 확인할 수 있습니다.</div>',
    unsafe_allow_html=True,
)

with st.expander("⚙ 설정", expanded=False):
    setting_cols = st.columns([3, 1, 1, 1], gap="medium")
    with setting_cols[0]:
        sheet_url = st.text_input("구글 시트 URL", value=DEFAULT_SHEET_URL)
    with setting_cols[1]:
        months_ahead = st.slider("표시 범위", 3, 18, 9)
    with setting_cols[2]:
        show_ok = st.checkbox("충족 표시", value=True)
    with setting_cols[3]:
        show_nodata = st.checkbox("데이터부족 표시", value=False)
        if st.button("새로고침", use_container_width=True):
            st.cache_data.clear()

try:
    raw_df = clean(load_sheet(sheet_url))
except Exception as exc:
    st.warning(f"구글 시트를 불러오지 못했습니다. URL과 공유 설정을 확인해주세요. ({exc})")
    st.stop()

if raw_df.empty:
    st.warning("시트에서 유효한 지급월 데이터를 찾지 못했습니다. 컬럼명과 날짜 형식을 확인해주세요.")
    st.stop()


left_col, right_col = st.columns([1, 1.35], gap="large")

with left_col:
    st.subheader("지급 실적 입력")
    st.caption("행 추가, 삭제, 숫자 수정이 가능하며 오른쪽 결과가 자동으로 갱신됩니다.")

    editable = raw_df.copy()
    editable[PAY_MONTH] = editable[PAY_MONTH].dt.strftime("%Y-%m")
    edited = st.data_editor(
        editable,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            PAY_MONTH: st.column_config.TextColumn("지급월", help="YYYY-MM 형식"),
            DAY_AMOUNT: st.column_config.NumberColumn("일용 금액", format="%d"),
            DAY_COUNT: st.column_config.NumberColumn("일용 인원", format="%d"),
            REPORT_AMOUNT: st.column_config.NumberColumn("신고 금액", format="%d"),
            REPORT_COUNT: st.column_config.NumberColumn("신고 인원", format="%d"),
        },
        height=560,
    )

    csv_bytes = edited.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "수정본 CSV 다운로드",
        csv_bytes,
        file_name="가점관리_수정본.csv",
        mime="text/csv",
        use_container_width=True,
    )


df = edited.copy()
df[PAY_MONTH] = pd.to_datetime(df[PAY_MONTH], errors="coerce")
for col in RAW_COLS[1:]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
df = df.dropna(subset=[PAY_MONTH]).sort_values(PAY_MONTH).reset_index(drop=True)
df = df.groupby(PAY_MONTH, as_index=False)[RAW_COLS[1:]].sum()

result = compute(df)
now = pd.Timestamp(datetime.now().replace(day=1))

view = result[(result["target"] >= m(now, -1)) & (result["target"] <= m(now, months_ahead))].copy()
if not show_ok:
    view = view[view["status"] != STATUS_OK]
if not show_nodata:
    view = view[view["status"] != STATUS_NODATA]


with right_col:
    st.subheader("결과 대시보드")

    urgent = result[
        (result["status"] == STATUS_NEED) & (result["target"] >= m(now, -1))
    ].sort_values("target")
    if urgent.empty:
        recommend_amount = 0
        recommend_count = 0
        recommend_target = "보충 필요 목표월 없음"
    else:
        nearest = urgent.iloc[0]
        recommend_amount = nearest["gap_amt"]
        recommend_count = nearest["gap_cnt"]
        recommend_target = month_label(nearest["target"])

    render_recommend_card(recommend_amount, recommend_count, recommend_target)
    st.divider()
    st.markdown('<div class="section-label">대상월 현황</div>', unsafe_allow_html=True)

    if view.empty:
        st.info("표시할 목표월이 없습니다. 왼쪽 설정에서 범위와 필터를 조정해주세요.")
    else:
        card_cols = st.columns(3, gap="medium")
        for idx, (_, row) in enumerate(view.iterrows()):
            with card_cols[idx % 3]:
                render_status_card(row)
                with st.expander(card_button_label(row), expanded=False):
                    render_detail(row)
