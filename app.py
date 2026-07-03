import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("📊 실시간 가점 현황판")

@st.cache_data(ttl=600)
def load_data():
    # 1. 시트 URL (뒤에 있는 /edit... 부분까지 다 지우고 아래처럼 수정)
    base_url = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ"
    csv_export_url = f"{base_url}/export?format=csv"
    return pd.read_csv(csv_export_url)

try:
    df = load_data()
    
    # 2. 상태별 색상 강조 (데이터가 깨끗할 때 더 잘 작동)
    def color_status(val):
        color = 'red' if '보충' in str(val) else 'green'
        return f'color: {color}; font-weight: bold'

    st.dataframe(
        df.style.map(color_status, subset=['상태']),
        use_container_width=True,
        hide_index=True
    )
except Exception as e:
    st.error(f"데이터를 불러올 수 없습니다: {e}")
