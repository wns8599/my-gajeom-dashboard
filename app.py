import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")
st.title("📊 가점 관리 대시보드 (기간별 현황)")

@st.cache_data(ttl=600)
def load_data():
    base_url = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ"
    csv_export_url = f"{base_url}/export?format=csv"
    return pd.read_csv(csv_export_url)

df = load_data()
df['지급월'] = pd.to_datetime(df['지급월']) # 날짜 형식 변환

# 날짜 기준 구분
today = datetime.now()
recent_df = df[df['지급월'] >= (today - pd.DateOffset(months=6))]
past_df = df[df['지급월'] < (today - pd.DateOffset(months=6))]

col1, col2 = st.columns(2)

with col1:
    st.subheader("🕒 최근 6개월")
    for _, row in recent_df.iterrows():
        # 상태에 따라 카드 색상 및 강조
        color = "red" if "보충" in str(row['상태']) else "green"
        with st.container(border=True):
            st.markdown(f"### {row['지급월'].strftime('%Y-%m')}")
            st.markdown(f":{color}[상태: {row['상태']}]")
            if "보충" in str(row['상태']):
                st.error(f"⚠️ 수정 필요: {row['부족 금액']}")

with col2:
    st.subheader("⏳ 이전 6개월")
    for _, row in past_df.iterrows():
        with st.container(border=True):
            st.write(f"**{row['지급월'].strftime('%Y-%m')}** | 상태: {row['상태']}")
