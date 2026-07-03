import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("📊 실시간 가점 현황판")

# 1. 구글 스프레드시트에서 데이터를 실시간으로 가져오는 함수
@st.cache_data(ttl=600) # 10분마다 새로고침
def load_data():
    sheet_url = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ/edit?gid=0#gid=0"
    csv_export_url = sheet_url.replace('/edit#gid=', '/export?format=csv&gid=')
    return pd.read_csv(csv_export_url)

try:
    df = load_data()
    
    # 2. 상태별 색상 강조
    def color_status(val):
        color = 'red' if '보충' in str(val) else 'green'
        return f'color: {color}; font-weight: bold'

    st.dataframe(
        df.style.map(color_status, subset=['상태']),
        use_container_width=True,
        hide_index=True
    )
except Exception as e:
    st.error("데이터를 불러올 수 없습니다. 구글 시트 공유 설정을 확인해주세요.")
