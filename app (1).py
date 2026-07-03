import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ──────────────────────────────────────────────────────────
# 기본 설정
# ──────────────────────────────────────────────────────────
st.set_page_config(page_title="성지전력 가점 시뮬레이터", layout="wide", page_icon="🎯")

DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ"
RAW_COLS = ["지급월", "일용_금액", "일용_인원", "특고_금액", "특고_인원"]

# 대상월 = 지급월 + 이 개월수
TARGET_LAG_MONTHS = 10
# 최근 6개월 창: 대상월-7 ~ 대상월-2
RECENT_OFFSET_START, RECENT_OFFSET_END = -7, -2
# 이전 6개월 창: 대상월-13 ~ 대상월-8 (최근 창 바로 앞 6개월)
PREV_OFFSET_START, PREV_OFFSET_END = -13, -8

st.title("🎯 성지전력 가점 시뮬레이터")
st.caption(
    "대상월(=지급월+10개월) 기준, **최근 6개월 실적**이 **이전 6개월 실적**을 "
    "금액·인원 모두 초과해야 가점이 충족됩니다."
)

# ──────────────────────────────────────────────────────────
# 사이드바 설정
# ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    sheet_url = st.text_input("구글 시트 URL", value=DEFAULT_SHEET_URL)
    if st.button("🔄 시트 새로고침", use_container_width=True):
        st.cache_data.clear()
    months_ahead = st.slider("표시할 대상월 범위 (현재월 기준 +N개월)", 3, 18, 9)
    show_ok = st.checkbox("✅ 충족 항목도 표시", value=True)
    show_nodata = st.checkbox("⬜ 데이터부족 항목도 표시", value=False)
    st.divider()
    st.caption("💡 대상월/최근·이전 6개월 창은 자동 계산되며, 입력값을 수정하면 오른쪽 결과가 즉시 갱신됩니다.")


# ──────────────────────────────────────────────────────────
# 데이터 로드 & 정제
# ──────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_sheet(url: str) -> pd.DataFrame:
    csv_url = url.rstrip("/") + "/export?format=csv"
    return pd.read_csv(csv_url)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in RAW_COLS:
        if c not in df.columns:
            df[c] = pd.NaT if c == "지급월" else 0
    df = df[RAW_COLS]
    for c in RAW_COLS[1:]:
        df[c] = pd.to_numeric(
            df[c].astype(str).str.replace(r"[^0-9\-]", "", regex=True), errors="coerce"
        ).fillna(0)
    df["지급월"] = pd.to_datetime(df["지급월"], errors="coerce")
    df = df.dropna(subset=["지급월"])
    df["지급월"] = df["지급월"].dt.to_period("M").dt.to_timestamp()
    df = df.groupby("지급월", as_index=False)[RAW_COLS[1:]].sum().sort_values("지급월")
    return df.reset_index(drop=True)


try:
    raw_df = clean(load_sheet(sheet_url))
except Exception as e:
    st.error(f"구글 시트를 불러오지 못했습니다: {e}")
    st.stop()

if raw_df.empty:
    st.warning("시트에서 유효한 지급월 데이터를 찾지 못했습니다. 시트 형식을 확인해주세요.")
    st.stop()

# ──────────────────────────────────────────────────────────
# 레이아웃: 좌(입력) / 우(결과)
# ──────────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1.3], gap="large")

with col_left:
    st.subheader("📝 지급 실적 입력 · 시뮬레이션")
    st.caption("숫자를 바꾸면 오른쪽 결과가 즉시 재계산됩니다. 행 추가/삭제도 가능합니다.")

    editable = raw_df.copy()
    editable["지급월"] = editable["지급월"].dt.strftime("%Y-%m")
    edited = st.data_editor(
        editable,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "지급월": st.column_config.TextColumn("지급월", help="YYYY-MM 형식"),
            "일용_금액": st.column_config.NumberColumn("일용 금액", format="%d"),
            "일용_인원": st.column_config.NumberColumn("일용 인원", format="%d"),
            "특고_금액": st.column_config.NumberColumn("특고 금액", format="%d"),
            "특고_인원": st.column_config.NumberColumn("특고 인원", format="%d"),
        },
        height=560,
    )
    csv_bytes = edited.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ 수정본 CSV 다운로드 (구글시트에 붙여넣기용)",
        csv_bytes,
        file_name="가점관리_수정본.csv",
        mime="text/csv",
        use_container_width=True,
    )

# 편집 결과 재정제
df = edited.copy()
df["지급월"] = pd.to_datetime(df["지급월"], errors="coerce")
for c in RAW_COLS[1:]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
df = df.dropna(subset=["지급월"]).sort_values("지급월").reset_index(drop=True)
df = df.groupby("지급월", as_index=False)[RAW_COLS[1:]].sum()


# ──────────────────────────────────────────────────────────
# 로직 레이어: 대상월별 최근/이전 6개월 창 계산
# ──────────────────────────────────────────────────────────
def m(ts: pd.Timestamp, n: int) -> pd.Timestamp:
    return ts + relativedelta(months=n)


def window_sum(indexed: pd.DataFrame, months: pd.DatetimeIndex):
    sub = indexed.reindex(months).fillna(0)
    amt = sub["일용_금액"].sum() + sub["특고_금액"].sum()
    cnt = sub["일용_인원"].sum() + sub["특고_인원"].sum()
    return amt, cnt


def compute(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    indexed = df.set_index("지급월")
    earliest = df["지급월"].min()

    rows = []
    for pay in df["지급월"]:
        target = m(pay, TARGET_LAG_MONTHS)
        recent_start, recent_end = m(target, RECENT_OFFSET_START), m(target, RECENT_OFFSET_END)
        prev_start, prev_end = m(target, PREV_OFFSET_START), m(target, PREV_OFFSET_END)

        recent_months = pd.date_range(recent_start, recent_end, freq="MS")
        prev_months = pd.date_range(prev_start, prev_end, freq="MS")

        recent_amt, recent_cnt = window_sum(indexed, recent_months)
        prev_amt, prev_cnt = window_sum(indexed, prev_months)

        data_ok = prev_start >= earliest  # 이전 6개월 창 전체가 보유 데이터 범위 안에 있는지

        if not data_ok:
            status, gap_amt, gap_cnt = "데이터부족", None, None
        else:
            amt_ok = recent_amt > prev_amt
            cnt_ok = recent_cnt > prev_cnt
            status = "충족" if (amt_ok and cnt_ok) else "보충필요"
            gap_amt = 0 if amt_ok else int(prev_amt - recent_amt) + 1
            gap_cnt = 0 if cnt_ok else int(prev_cnt - recent_cnt) + 1

        rows.append(
            dict(
                target=target,
                recent_start=recent_start, recent_end=recent_end,
                recent_amt=recent_amt, recent_cnt=recent_cnt,
                prev_start=prev_start, prev_end=prev_end,
                prev_amt=prev_amt, prev_cnt=prev_cnt,
                status=status, gap_amt=gap_amt, gap_cnt=gap_cnt,
                recent_months=recent_months,
            )
        )
    res = pd.DataFrame(rows).drop_duplicates(subset="target").sort_values("target")
    return res.reset_index(drop=True)


result = compute(df)

# ──────────────────────────────────────────────────────────
# 출력 레이어: 카드 대시보드
# ──────────────────────────────────────────────────────────
now = pd.Timestamp(datetime.now().replace(day=1))
view = result[(result["target"] >= m(now, -1)) & (result["target"] <= m(now, months_ahead))].copy()
if not show_ok:
    view = view[view["status"] != "충족"]
if not show_nodata:
    view = view[view["status"] != "데이터부족"]

with col_right:
    st.subheader("📈 대상월별 가점 현황")

    urgent = result[
        (result["status"] == "보충필요") & (result["target"] >= m(now, -1))
    ].sort_values("target")

    if not urgent.empty:
        nearest = urgent.iloc[0]
        remaining_months = [mm for mm in nearest["recent_months"] if mm >= now]
        c1, c2, c3 = st.columns(3)
        c1.metric("가장 임박한 보충필요", nearest["target"].strftime("%Y년 %m월"))
        c2.metric("부족 금액", f"{nearest['gap_amt']:,}원")
        c3.metric("부족 인원", f"{nearest['gap_cnt']}명")

        if remaining_months:
            per_month = nearest["gap_amt"] / len(remaining_months)
            st.warning(
                f"⏳ **{nearest['recent_end'].strftime('%Y-%m')}**까지 남은 "
                f"**{len(remaining_months)}개월** 동안, 매월 최소 "
                f"**{per_month:,.0f}원** 이상을 추가로 지급해야 이 대상월 가점이 충족됩니다."
            )
        else:
            st.error("⚠️ 반영 가능한 남은 개월이 없어 이번 대상월은 지금부터는 충족이 불가능합니다.")
    else:
        st.success("✅ 표시 범위 내 임박한 보충필요 대상월이 없습니다.")

    st.divider()

    if view.empty:
        st.info("표시할 대상월이 없습니다. 사이드바에서 범위/필터를 조정해보세요.")

    badge_style = {
        "충족":     ("✅ 충족",      "#1e7e34", "#e6f4ea"),
        "보충필요": ("⚠️ 보충 필요", "#c0392b", "#fdecea"),
        "데이터부족": ("⬜ 데이터부족", "#666666", "#f0f0f0"),
    }

    for _, r in view.iterrows():
        label, fg, bg = badge_style[r["status"]]
        with st.container(border=True):
            top1, top2 = st.columns([3, 1])
            top1.markdown(f"**{r['target'].strftime('%Y년 %m월')}**")
            top2.markdown(
                f"<div style='text-align:right'><span style='background:{bg};color:{fg};"
                f"padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600'>{label}</span></div>",
                unsafe_allow_html=True,
            )

            if r["status"] == "데이터부족":
                st.caption("이 대상월을 판정하려면 더 과거의 지급 데이터가 필요합니다.")
                continue

            st.caption(
                f"이전 {r['prev_start'].strftime('%y-%m')} ~ {r['prev_end'].strftime('%y-%m')}  ·  "
                f"{int(r['prev_amt']):,}원 / {int(r['prev_cnt'])}명"
            )
            st.markdown(
                f"**최근 {r['recent_start'].strftime('%y-%m')} ~ {r['recent_end'].strftime('%y-%m')}  ·  "
                f"{int(r['recent_amt']):,}원 / {int(r['recent_cnt'])}명**"
            )

            if r["status"] == "보충필요":
                st.markdown(
                    f"<span style='color:#c0392b;font-weight:600'>▲ 금액 +{r['gap_amt']:,}원 · "
                    f"인원 +{r['gap_cnt']}명 필요</span>",
                    unsafe_allow_html=True,
                )
            else:
                diff_amt = int(r["recent_amt"] - r["prev_amt"])
                diff_cnt = int(r["recent_cnt"] - r["prev_cnt"])
                st.markdown(
                    f"<span style='color:#1e7e34;font-weight:600'>▲ 금액 +{diff_amt:,}원 · "
                    f"인원 +{diff_cnt}명 여유</span>",
                    unsafe_allow_html=True,
                )

# ──────────────────────────────────────────────────────────
# 하단: 전체 추이 시각화
# ──────────────────────────────────────────────────────────
st.divider()
st.subheader("📊 대상월별 부족 금액 추이")

chart_df = result[result["status"] != "데이터부족"].copy()
if not chart_df.empty:
    colors = chart_df["status"].map({"충족": "#2ecc71", "보충필요": "#e74c3c"})
    fig = go.Figure()
    fig.add_bar(
        x=chart_df["target"],
        y=chart_df["gap_amt"].fillna(0),
        marker_color=colors,
        text=chart_df["status"],
        hovertemplate="%{x|%Y-%m}<br>부족금액: %{y:,}원<extra></extra>",
    )
    fig.add_vline(x=now, line_dash="dot", line_color="gray", annotation_text="이번달")
    fig.update_layout(
        height=320,
        xaxis_title="대상월",
        yaxis_title="부족 금액 (원)",
        margin=dict(t=10, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.caption("판정 가능한 대상월 데이터가 아직 없습니다.")
