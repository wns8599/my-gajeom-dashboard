import math
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dateutil.relativedelta import relativedelta
from plotly.subplots import make_subplots

# ──────────────────────────────────────────────────────────
# 기본 설정
# ──────────────────────────────────────────────────────────
st.set_page_config(page_title="성지전력 가점 시뮬레이터", layout="wide", page_icon="🎯")

DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ"
RAW_COLS = ["지급월", "일용_금액", "일용_인원", "특고_금액", "특고_인원"]

TARGET_LAG_MONTHS = 10          # 대상월 = 지급월 + 10개월
RECENT_OFFSET_START, RECENT_OFFSET_END = -7, -2    # 최근 6개월 창
PREV_OFFSET_START, PREV_OFFSET_END = -13, -8       # 이전 6개월 창 (최근 창 직전 6개월)

C_OK, C_OK_BG = "#16a34a", "#e7f6ec"
C_BAD, C_BAD_BG = "#dc2626", "#fdecec"
C_MUTE, C_MUTE_BG = "#64748b", "#eef1f4"
C_PREV, C_RECENT = "#94a3b8", "#2563eb"

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.6rem;}
    .hero-card {
        border-radius: 18px; padding: 26px 30px; margin-bottom: 6px;
        border: 1px solid rgba(0,0,0,0.06);
    }
    .hero-badge {
        display:inline-block; padding: 4px 14px; border-radius: 999px;
        font-size: 13px; font-weight: 700; letter-spacing: .2px;
    }
    .hero-title {font-size: 26px; font-weight: 800; margin: 4px 0 2px 0;}
    .hero-sub {font-size: 14px; opacity: .75; margin-bottom: 14px;}
    .period-banner {
        border-radius: 12px; padding: 14px 18px; font-size: 15.5px;
        font-weight: 600; margin: 14px 0 4px 0;
    }
    .plan-chip {
        border-radius: 10px; padding: 10px 12px; text-align:center;
        border: 1px solid rgba(0,0,0,0.08); background: rgba(37,99,235,0.05);
    }
    .plan-chip-locked {
        border-radius: 10px; padding: 10px 12px; text-align:center;
        border: 1px dashed rgba(0,0,0,0.15); background: rgba(100,116,139,0.06); opacity:.7;
    }
    .plan-month {font-size: 12.5px; opacity:.7; font-weight:600;}
    .plan-amt {font-size: 15px; font-weight: 800; margin-top:2px;}
    .plan-cnt {font-size: 12px; opacity:.75;}
    .kpi-row {display:flex; gap:14px; margin: 6px 0 18px 0;}
    .kpi-tile {
        flex:1; border-radius: 14px; padding: 16px 20px;
        border: 1px solid rgba(0,0,0,0.06);
    }
    .kpi-label {font-size: 13px; font-weight: 700; opacity:.7; margin-bottom:4px;}
    .kpi-value {font-size: 40px; font-weight: 900; line-height:1.1;}
    .kpi-unit {font-size: 16px; font-weight: 700; margin-left:2px;}
    </style>
    """,
    unsafe_allow_html=True,
)

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
    months_ahead = st.slider("전체 현황 표시 범위 (현재월 기준 +N개월)", 3, 18, 9)
    show_ok = st.checkbox("✅ 충족 항목도 표시", value=True)
    show_nodata = st.checkbox("⬜ 데이터부족 항목도 표시", value=False)
    st.divider()
    st.caption("💡 왼쪽 표의 숫자를 바꾸면 상단 실행계획과 카드가 즉시 재계산됩니다.")


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
# 로직 함수
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

        data_ok = prev_start >= earliest

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


def build_plan(row, now):
    """gap을 아직 지나지 않은 달에 균등 배분한 월별 실행계획."""
    remaining = [mm for mm in row["recent_months"] if mm >= now]
    passed = [mm for mm in row["recent_months"] if mm < now]
    if not remaining or row["gap_amt"] is None or row["gap_amt"] <= 0:
        return remaining, passed, []
    n = len(remaining)
    base_amt, rem_amt = divmod(int(row["gap_amt"]), n)
    base_cnt, rem_cnt = divmod(int(row["gap_cnt"]), n)
    plan = []
    for i, mm in enumerate(remaining):
        amt_i = base_amt + (rem_amt if i == n - 1 else 0)
        cnt_i = base_cnt + (1 if i < rem_cnt else 0)
        plan.append((mm, amt_i, cnt_i))
    return remaining, passed, plan


# ──────────────────────────────────────────────────────────
# 레이아웃 뼈대 먼저 잡기 (히어로 자리 예약 → 나중에 채움)
# ──────────────────────────────────────────────────────────
hero_slot = st.container()
st.divider()

col_left, col_right = st.columns([1, 1.25], gap="large")

with col_left:
    st.subheader("📝 지급 실적 입력 · 시뮬레이션")
    st.caption("숫자를 바꾸면 위 실행계획과 오른쪽 카드가 즉시 재계산됩니다.")

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
        height=520,
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

result = compute(df)
now = pd.Timestamp(datetime.now().replace(day=1))

# ──────────────────────────────────────────────────────────
# 오른쪽: 전체 현황 카드
# ──────────────────────────────────────────────────────────
view = result[(result["target"] >= m(now, -1)) & (result["target"] <= m(now, months_ahead))].copy()
if not show_ok:
    view = view[view["status"] != "충족"]
if not show_nodata:
    view = view[view["status"] != "데이터부족"]

badge_style = {
    "충족":       ("✅ 충족", C_OK, C_OK_BG),
    "보충필요":   ("⚠️ 보충 필요", C_BAD, C_BAD_BG),
    "데이터부족": ("⬜ 데이터부족", C_MUTE, C_MUTE_BG),
}

with col_right:
    st.subheader("📋 대상월별 전체 현황")
    if view.empty:
        st.info("표시할 대상월이 없습니다. 사이드바에서 범위/필터를 조정해보세요.")
    for _, r in view.iterrows():
        label, fg, bg = badge_style[r["status"]]
        with st.container(border=True):
            top1, top2 = st.columns([3, 1])
            top1.markdown(f"**{r['target'].strftime('%Y년 %m월')}**")
            top2.markdown(
                f"<div style='text-align:right'><span style='background:{bg};color:{fg};"
                f"padding:2px 10px;border-radius:12px;font-size:12px;font-weight:700'>{label}</span></div>",
                unsafe_allow_html=True,
            )
            if r["status"] == "데이터부족":
                st.caption("판정에 필요한 과거 데이터가 부족합니다.")
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
                    f"<span style='color:{C_BAD};font-weight:700'>▲ 금액 +{r['gap_amt']:,}원 · "
                    f"인원 +{r['gap_cnt']}명 필요</span>",
                    unsafe_allow_html=True,
                )
            else:
                diff_amt = int(r["recent_amt"] - r["prev_amt"])
                diff_cnt = int(r["recent_cnt"] - r["prev_cnt"])
                st.markdown(
                    f"<span style='color:{C_OK};font-weight:700'>▲ 금액 +{diff_amt:,}원 · "
                    f"인원 +{diff_cnt}명 여유</span>",
                    unsafe_allow_html=True,
                )

# ──────────────────────────────────────────────────────────
# 히어로: 선택한 대상월 실행계획 (자리는 위, 렌더는 데이터 계산 후)
# ──────────────────────────────────────────────────────────
TIMELINE_COLORS = {
    "이전 6개월 (비교 기준)": C_PREV,
    "최근 6개월 · 확정": "#0ea5e9",
    "최근 6개월 · 추가 필요": C_BAD,
    "최근 6개월 · 충족(여유)": C_OK,
}


def build_timeline_df(r, now, plan):
    plan_map = {mm: (amt, cnt) for mm, amt, cnt in plan}
    items = []
    for mm in pd.date_range(r["prev_start"], r["prev_end"], freq="MS"):
        items.append(dict(
            Start=mm, Finish=m(mm, 1), Phase="이전 6개월 (비교 기준)", Label=mm.strftime("%y-%m"),
        ))
    for mm in r["recent_months"]:
        if mm < now:
            phase, label = "최근 6개월 · 확정", mm.strftime("%y-%m")
        elif mm in plan_map:
            amt, _ = plan_map[mm]
            phase = "최근 6개월 · 추가 필요"
            label = f"{mm.strftime('%y-%m')}  +{amt:,}원"
        else:
            phase = "최근 6개월 · 충족(여유)" if r["status"] == "충족" else "최근 6개월 · 확정"
            label = mm.strftime("%y-%m")
        items.append(dict(Start=mm, Finish=m(mm, 1), Phase=phase, Label=label))
    return pd.DataFrame(items)


with hero_slot:
    st.subheader("🧭 실행 계획: 이 대상월에 가점을 받으려면")

    selectable = result[result["target"] >= m(now, -1)].copy()
    if selectable.empty:
        st.info("표시할 대상월 데이터가 없습니다.")
    else:
        options = list(selectable["target"])
        urgent_first = selectable[selectable["status"] == "보충필요"]
        default_target = urgent_first["target"].iloc[0] if not urgent_first.empty else options[0]
        sel = st.selectbox(
            "확인할 대상월 선택",
            options=options,
            index=options.index(default_target),
            format_func=lambda d: d.strftime("%Y년 %m월"),
        )
        r = selectable[selectable["target"] == sel].iloc[0]

        if r["status"] == "데이터부족":
            st.warning("이 대상월은 판정에 필요한 과거 지급 데이터가 부족합니다. (더 이전 지급월 데이터를 입력해주세요)")
        else:
            label, fg, bg = badge_style[r["status"]]
            hero_bg = C_OK_BG if r["status"] == "충족" else C_BAD_BG
            st.markdown(
                f"""
                <div class="hero-card" style="background:{hero_bg};">
                    <span class="hero-badge" style="background:{fg};color:white;">{label}</span>
                    <div class="hero-title">{r['target'].strftime('%Y년 %m월')} 가점 요건</div>
                    <div class="hero-sub">
                        이전 6개월 {r['prev_start'].strftime('%Y-%m')} ~ {r['prev_end'].strftime('%Y-%m')}
                        &nbsp;vs&nbsp;
                        최근 6개월 {r['recent_start'].strftime('%Y-%m')} ~ {r['recent_end'].strftime('%Y-%m')}
                    </div>
                """,
                unsafe_allow_html=True,
            )

            remaining, passed, plan = build_plan(r, now)

            # ── KPI 큰 숫자 타일 ──────────────────────────
            if r["status"] == "충족":
                diff_amt = int(r["recent_amt"] - r["prev_amt"])
                diff_cnt = int(r["recent_cnt"] - r["prev_cnt"])
                st.markdown(
                    f"""<div class="kpi-row">
                    <div class="kpi-tile" style="background:{C_OK_BG};">
                        <div class="kpi-label" style="color:{C_OK};">여유 금액</div>
                        <div class="kpi-value" style="color:{C_OK};">+{diff_amt:,}<span class="kpi-unit">원</span></div>
                    </div>
                    <div class="kpi-tile" style="background:{C_OK_BG};">
                        <div class="kpi-label" style="color:{C_OK};">여유 인원</div>
                        <div class="kpi-value" style="color:{C_OK};">+{diff_cnt}<span class="kpi-unit">명</span></div>
                    </div>
                    </div>""",
                    unsafe_allow_html=True,
                )
            elif not remaining:
                st.markdown(
                    f"<div class='period-banner' style='background:{C_BAD_BG};color:{C_BAD};'>"
                    f"⚠️ 최근 6개월 창이 이미 모두 지나가, 지금부터는 이 대상월의 가점을 채울 수 없습니다.</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""<div class="kpi-row">
                    <div class="kpi-tile" style="background:{C_BAD_BG};">
                        <div class="kpi-label" style="color:{C_BAD};">부족 금액</div>
                        <div class="kpi-value" style="color:{C_BAD};">{r['gap_amt']:,}<span class="kpi-unit">원</span></div>
                    </div>
                    <div class="kpi-tile" style="background:{C_BAD_BG};">
                        <div class="kpi-label" style="color:{C_BAD};">부족 인원</div>
                        <div class="kpi-value" style="color:{C_BAD};">{r['gap_cnt']}<span class="kpi-unit">명</span></div>
                    </div>
                    <div class="kpi-tile" style="background:{C_MUTE_BG};">
                        <div class="kpi-label" style="color:{C_MUTE};">채워야 할 기간</div>
                        <div class="kpi-value" style="color:{C_MUTE};font-size:24px;">
                            {remaining[0].strftime('%Y.%m')} ~ {remaining[-1].strftime('%Y.%m')}
                        </div>
                    </div>
                    </div>""",
                    unsafe_allow_html=True,
                )

            # ── 이전 vs 최근 막대 비교 (한눈에 높이 차이로 보기) ──
            comp = make_subplots(rows=1, cols=2, subplot_titles=("금액 비교", "인원 비교"))
            bar_colors = [C_PREV, C_OK if r["status"] == "충족" else C_BAD]
            comp.add_trace(go.Bar(
                x=["이전 6개월", "최근 6개월"], y=[r["prev_amt"], r["recent_amt"]],
                marker_color=bar_colors,
                text=[f"{int(r['prev_amt']):,}원", f"{int(r['recent_amt']):,}원"],
                textposition="outside", textfont_size=13, showlegend=False,
            ), row=1, col=1)
            comp.add_trace(go.Bar(
                x=["이전 6개월", "최근 6개월"], y=[r["prev_cnt"], r["recent_cnt"]],
                marker_color=bar_colors,
                text=[f"{int(r['prev_cnt'])}명", f"{int(r['recent_cnt'])}명"],
                textposition="outside", textfont_size=13, showlegend=False,
            ), row=1, col=2)
            comp.update_yaxes(visible=False, showgrid=False)
            comp.update_layout(height=230, margin=dict(t=36, b=10, l=10, r=10))
            st.plotly_chart(comp, use_container_width=True)

            # ── 12개월 캘린더 타임라인 (색만 봐도 언제~언제인지 파악) ──
            st.markdown("**기간 타임라인** (회색=이전 6개월 · 파랑=최근 6개월 확정분 · 빨강=지금부터 채워야 할 달)")
            tdf = build_timeline_df(r, now, plan)
            fig_t = px.timeline(
                tdf, x_start="Start", x_end="Finish", y=["기간"] * len(tdf),
                color="Phase", color_discrete_map=TIMELINE_COLORS, text="Label",
            )
            fig_t.update_yaxes(visible=False, showgrid=False)
            fig_t.update_xaxes(title=None)
            fig_t.add_vline(x=now, line_dash="dot", line_color="black", annotation_text="오늘", annotation_position="top")
            fig_t.update_traces(textposition="inside", insidetextanchor="middle", textfont_size=11)
            fig_t.update_layout(
                height=130, margin=dict(t=10, b=10, l=10, r=10),
                legend=dict(orientation="h", y=-0.5, title=None),
            )
            st.plotly_chart(fig_t, use_container_width=True)

            if remaining and r["status"] != "충족":
                st.markdown(
                    f"<div class='period-banner' style='background:{C_BAD_BG};color:{C_BAD};'>"
                    f"📅 <b>{remaining[0].strftime('%Y년 %m월')} ~ {remaining[-1].strftime('%Y년 %m월')}</b> 기간 동안, "
                    f"총 <b>{r['gap_amt']:,}원 · {r['gap_cnt']}명</b>을 추가로 채워야 "
                    f"<b>{r['target'].strftime('%Y년 %m월')}</b> 가점이 충족됩니다.</div>",
                    unsafe_allow_html=True,
                )
                with st.expander("📋 월별 상세 수치 보기 (균등 배분 기준 · 특정 달에 몰아 넣어도 무방)"):
                    chip_cols = st.columns(min(len(passed) + len(plan), 6) or 1)
                    all_items = [(mm, None, None, True) for mm in passed] + [
                        (mm, amt, cnt, False) for mm, amt, cnt in plan
                    ]
                    for i, (mm, amt, cnt, locked) in enumerate(all_items):
                        col = chip_cols[i % len(chip_cols)]
                        with col:
                            if locked:
                                st.markdown(
                                    f"<div class='plan-chip-locked'>"
                                    f"<div class='plan-month'>{mm.strftime('%Y-%m')}</div>"
                                    f"<div class='plan-amt'>확정</div>"
                                    f"<div class='plan-cnt'>지난 달</div></div>",
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.markdown(
                                    f"<div class='plan-chip'>"
                                    f"<div class='plan-month'>{mm.strftime('%Y-%m')}</div>"
                                    f"<div class='plan-amt'>+{amt:,}원</div>"
                                    f"<div class='plan-cnt'>+{cnt}명</div></div>",
                                    unsafe_allow_html=True,
                                )

            st.markdown("</div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────
# 하단: 전체 추이 시각화
# ──────────────────────────────────────────────────────────
st.divider()
st.subheader("📊 대상월별 부족 금액 추이")

chart_df = result[result["status"] != "데이터부족"].copy()
if not chart_df.empty:
    colors = chart_df["status"].map({"충족": C_OK, "보충필요": C_BAD})
    fig2 = go.Figure()
    fig2.add_bar(
        x=chart_df["target"],
        y=chart_df["gap_amt"].fillna(0),
        marker_color=colors,
        text=chart_df["status"],
        hovertemplate="%{x|%Y-%m}<br>부족금액: %{y:,}원<extra></extra>",
    )
    fig2.add_vline(x=now, line_dash="dot", line_color="gray", annotation_text="이번달")
    fig2.update_layout(
        height=320,
        xaxis_title="대상월",
        yaxis_title="부족 금액 (원)",
        margin=dict(t=10, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.caption("판정 가능한 대상월 데이터가 아직 없습니다.")
