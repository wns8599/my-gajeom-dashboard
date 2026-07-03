import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from dateutil.relativedelta import relativedelta


st.set_page_config(
    page_title="퇴직공제 가점관리 대시보드",
    layout="wide",
    page_icon="bar_chart",
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
    :root {
        --surface: #ffffff;
        --muted: #667085;
        --line: #e6e8ee;
        --ink: #1d2433;
        --green: #168a52;
        --green-bg: #eaf7ef;
        --red: #c83f3f;
        --red-bg: #fff0ee;
        --gray-bg: #f4f6f8;
    }
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2.6rem;
    }
    .page-title {
        font-size: 30px;
        font-weight: 800;
        color: var(--ink);
        margin-bottom: 2px;
    }
    .page-subtitle {
        color: var(--muted);
        font-size: 14px;
        margin-bottom: 20px;
    }
    .kpi-card {
        min-height: 112px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--surface);
        padding: 16px 16px 14px;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }
    .kpi-label {
        color: var(--muted);
        font-size: 13px;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .kpi-value {
        color: var(--ink);
        font-size: 25px;
        line-height: 1.1;
        font-weight: 850;
    }
    .kpi-note {
        color: var(--muted);
        font-size: 12px;
        margin-top: 8px;
    }
    div[data-testid="stExpander"] details {
        border: 1px solid var(--line);
        border-radius: 8px;
        background: #fff;
        overflow: hidden;
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


def render_kpi_card(label: str, value: str, note: str = ""):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card_label(row: pd.Series) -> str:
    status = row["status"]
    target = month_label(row["target"])
    recent = f"{money(row['recent_amt'])} / {people(row['recent_cnt'])}"

    if status == STATUS_NEED:
        focus = f"부족 {money(row['gap_amt'])} · {people(row['gap_cnt'])}"
    elif status == STATUS_OK:
        diff_amt = int(row["recent_amt"] - row["prev_amt"])
        diff_cnt = int(row["recent_cnt"] - row["prev_cnt"])
        focus = f"여유 {money(diff_amt)} · {people(diff_cnt)}"
    else:
        focus = "과거 자료 필요"

    return f"{target}  |  {status}\n{focus}\n최근 {recent}"


def render_detail(row: pd.Series):
    if row["status"] == STATUS_NODATA:
        st.caption("이 목표월을 판정하려면 이전 6개월 구간 전체가 포함된 지급 데이터가 필요합니다.")
        return

    c1, c2 = st.columns(2)
    c1.metric(
        f"이전 {month_label(row['prev_start'])}~{month_label(row['prev_end'])}",
        f"{money(row['prev_amt'])} / {people(row['prev_cnt'])}",
    )
    c2.metric(
        f"최근 {month_label(row['recent_start'])}~{month_label(row['recent_end'])}",
        f"{money(row['recent_amt'])} / {people(row['recent_cnt'])}",
    )

    if row["status"] == STATUS_NEED:
        st.error(f"추가 필요: 금액 {money(row['gap_amt'])}, 인원 {people(row['gap_cnt'])}")
    else:
        st.success("금액과 인원이 모두 이전 6개월 실적을 초과했습니다.")


with st.sidebar:
    st.header("설정")
    sheet_url = st.text_input("구글 시트 URL", value=DEFAULT_SHEET_URL)
    if st.button("시트 새로고침", use_container_width=True):
        st.cache_data.clear()
    months_ahead = st.slider("표시할 목표월 범위", 3, 18, 9)
    show_ok = st.checkbox("충족 항목 표시", value=True)
    show_nodata = st.checkbox("데이터부족 항목 표시", value=False)
    st.divider()
    st.caption("지급월을 수정하면 목표월별 최근/이전 6개월 비교 결과가 즉시 다시 계산됩니다.")


st.markdown('<div class="page-title">퇴직공제 가점관리 대시보드</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-subtitle">목표월은 지급월 + 10개월 기준이며, 최근 6개월 실적이 이전 6개월 실적을 금액과 인원 모두 초과해야 충족됩니다.</div>',
    unsafe_allow_html=True,
)

try:
    raw_df = clean(load_sheet(sheet_url))
except Exception as exc:
    st.error(f"구글 시트를 불러오지 못했습니다. URL과 공유 설정을 확인해주세요. ({exc})")
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

    measurable = view[view["status"] != STATUS_NODATA].copy()
    need_rows = measurable[measurable["status"] == STATUS_NEED]
    ok_rows = measurable[measurable["status"] == STATUS_OK]
    total_gap_amt = int(need_rows["gap_amt"].fillna(0).sum()) if not need_rows.empty else 0
    total_count = len(measurable)
    fulfill_rate = (len(ok_rows) / total_count * 100) if total_count else 0

    urgent = result[
        (result["status"] == STATUS_NEED) & (result["target"] >= m(now, -1))
    ].sort_values("target")
    if urgent.empty:
        target_note = "보충 필요 목표월 없음"
        target_value = "-"
    else:
        nearest = urgent.iloc[0]
        target_value = month_label(nearest["target"])
        target_note = f"부족 {money(nearest['gap_amt'])}, {people(nearest['gap_cnt'])}"

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_kpi_card("보충건수", f"{len(need_rows):,}건", "표시 범위 기준")
    with k2:
        render_kpi_card("총 부족금액", money(total_gap_amt), "보충필요 합계")
    with k3:
        render_kpi_card("이번달 목표", target_value, target_note)
    with k4:
        render_kpi_card("충족률", f"{fulfill_rate:.0f}%", f"{len(ok_rows):,}/{total_count:,}건 충족")

    st.divider()

    if not urgent.empty:
        nearest = urgent.iloc[0]
        remaining_months = [month for month in nearest["recent_months"] if month >= now]
        if remaining_months:
            per_month = nearest["gap_amt"] / len(remaining_months)
            st.warning(
                f"{month_label(nearest['recent_end'])}까지 남은 {len(remaining_months)}개월 동안 "
                f"월 평균 {per_month:,.0f}원 이상 추가 지급하면 {month_label(nearest['target'])} 목표월을 충족할 수 있습니다."
            )
        else:
            st.error("반영 가능한 남은 개월이 없어 가장 가까운 목표월은 현재 지급분만으로 충족하기 어렵습니다.")
    else:
        st.success("표시 범위 안에 보충이 필요한 목표월이 없습니다.")

    if view.empty:
        st.info("표시할 목표월이 없습니다. 왼쪽 설정에서 범위와 필터를 조정해주세요.")
    else:
        card_cols = st.columns(4, gap="small")
        for idx, (_, row) in enumerate(view.iterrows()):
            with card_cols[idx % 4]:
                with st.expander(card_label(row), expanded=False):
                    render_detail(row)


st.divider()
st.subheader("목표월별 부족금액 추이")

chart_df = result[result["status"] != STATUS_NODATA].copy()
if not chart_df.empty:
    colors = chart_df["status"].map({STATUS_OK: "#168a52", STATUS_NEED: "#c83f3f"})
    fig = go.Figure()
    fig.add_bar(
        x=chart_df["target"],
        y=chart_df["gap_amt"].fillna(0),
        marker_color=colors,
        text=chart_df["status"],
        hovertemplate="%{x|%Y-%m}<br>부족금액: %{y:,}원<extra></extra>",
    )
    fig.add_vline(x=now, line_dash="dot", line_color="#667085", annotation_text="이번달")
    fig.update_layout(
        height=320,
        xaxis_title="목표월",
        yaxis_title="부족금액(원)",
        margin=dict(t=10, b=10, l=10, r=10),
        showlegend=False,
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.caption("판정 가능한 목표월 데이터가 아직 없습니다.")
