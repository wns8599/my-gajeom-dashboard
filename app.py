import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🎯 가점 시뮬레이터 (좌우 배치)")

@st.cache_data(ttl=60)
def load_data():
    base_url = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ"
    return pd.read_csv(f"{base_url}/export?format=csv")

df = load_data()

# 화면을 좌우로 분할 (1:1 비율)
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📝 1. 수치 입력 (시뮬레이션)")
    input_cols = ['지급월', '일용_금액', '일용_인원', '특고_금액', '특고_인원']
    edited_df = st.data_editor(df[input_cols], use_container_width=True, hide_index=True)

with col_right:
    st.subheader("📈 2. 가점 현황 자동 결과")
    
    # 계산 로직 (여기에 실제 목표 금액을 넣으세요)
    def calculate_results(df):
        # 예시 로직: 6개월 합산
        res = df.copy()
        res['합계금액'] = res['일용_금액'] + res['특고_금액']
        # '상태' 판정 로직 (예: 100만원 미만이면 보충)
        res['상태'] = res['합계금액'].apply(lambda x: "✅ 충족" if x >= 1000000 else "⚠️ 보충 필요")
        return res[['지급월', '상태', '합계금액']]

    results = calculate_results(edited_df)
    
    # 상태별 색상 강조
    def color_status(val):
        color = 'red' if '보충' in str(val) else 'green'
        return f'color: {color}; font-weight: bold'
    
    st.dataframe(results.style.map(color_status, subset=['상태']), use_container_width=True, hide_index=True)
