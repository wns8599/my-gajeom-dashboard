import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🎯 가점 시뮬레이터")

# 1. 데이터 로드
@st.cache_data(ttl=60)
def load_data():
    base_url = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ"
    return pd.read_csv(f"{base_url}/export?format=csv")

df = load_data()

# 2. 좌측: 입력용 표 (지급월~합계인원만 선택)
st.subheader("📝 1. 수치 입력 (시뮬레이션)")
input_cols = ['지급월', '일용_금액', '일용_인원', '특고_금액', '특고_인원', '합계_금액', '합계_인원']
edited_df = st.data_editor(df[input_cols], use_container_width=True, hide_index=True)

# 3. 우측: 결과용 현황판 (자동 계산)
def calculate_results(df):
    # 실제 업무용 수식(6개월 합산 등)을 여기에 넣으세요
    # 예시: 임의의 로직
    res = df.copy()
    res['상태'] = "✅ 충족" # 여기에 실제 계산 로직 적용
    res['부족금액'] = 0
    return res[['지급월', '상태', '부족금액']]

st.divider()

st.subheader("📈 2. 가점 현황 자동 결과")
results = calculate_results(edited_df)
st.dataframe(results, use_container_width=True, hide_index=True)
