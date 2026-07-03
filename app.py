import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")
st.title("🎯 가점 시뮬레이터 (대상월 중심)")

@st.cache_data(ttl=60)
def load_data():
    base_url = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ"
    return pd.read_csv(f"{base_url}/export?format=csv")

df = clean_data(load_data()) # 앞서 만든 clean_data 함수 사용

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📝 1. 수치 입력 (지급월별)")
    input_cols = ['지급월', '일용_금액', '일용_인원', '특고_금액', '특고_인원']
    edited_df = st.data_editor(df[input_cols], use_container_width=True, hide_index=True)

with col_right:
    st.subheader("📈 2. 대상월 가점 현황 결과")
    
    # 1. 입력받은 데이터를 기반으로 '대상월' 계산 로직
    # 예: 2026년 6월부터 시작하는 가점 현황 로직 적용
    res = edited_df.copy()
    
    # 대상월 기준: 2026년 6월 이후 데이터만 필터링
    res['지급월_dt'] = pd.to_datetime(res['지급월'])
    target_df = res[res['지급월_dt'] >= '2026-06-01'].copy()
    
    # 2. 로직 적용 (대상월 현황 계산)
    target_df['합계금액'] = target_df['일용_금액'] + target_df['특고_금액']
    target_df['합계인원'] = target_df['일용_인원'] + target_df['특고_인원']
    target_df['상태'] = target_df['합계금액'].apply(lambda x: "✅ 충족" if x >= 1000000 else "⚠️ 보충 필요")
    
    def color_status(val):
        color = 'red' if '보충' in str(val) else 'green'
        return f'color: {color}; font-weight: bold'
    
    st.dataframe(
        target_df[['지급월', '합계금액', '합계인원', '상태']].style.map(color_status, subset=['상태']),
        use_container_width=True, 
        hide_index=True
    )
