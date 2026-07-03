        return

    c1, c2 = st.columns(2)
    c1.metric(
        "최근 6개월",
        f"{money(row['recent_amt'])} / {people(row['recent_cnt'])}",
    )
    c2.metric(
        "이전 6개월",
        f"{money(row['prev_amt'])} / {people(row['prev_cnt'])}",
    )

    c3, c4 = st.columns(2)
    c3.metric("부족 금액", money(row["gap_amt"]))
    c4.metric("부족 인원", people(row["gap_cnt"]))


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


st.markdown('<div class="page-title">조달청 가점관리 대시보드</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-subtitle">목표월별 가점 충족 여부와 부족한 금액·인원을 확인할 수 있습니다.</div>',
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
