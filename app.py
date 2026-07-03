import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide")
st.title("📊 가점 관리 실시간 통합 대시보드")

# 1. 데이터 로드 (구글 시트 연동)
@st.cache_data(ttl=600)
def load_data():
    base_url = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ"
    return pd.read_csv(f"{base_url}/export?format=csv")

df = load_data()
df['지급월'] = pd.to_datetime(df['지급월'])

# 2. 기간 구분 (오늘 기준 최근 6개월 / 그 이전)
today = datetime.now()
limit_date = today - pd.DateOffset(months=6)

recent_df = df[df['지급월'] >= limit_date].copy()
past_df = df[df['지급월'] < limit_date].copy()

# 3. 레이아웃
st.subheader("⚠️ 최근 6개월 집중 관리 (수정 및 시뮬레이션)")
# 직접 수정 가능하게 data_editor 제공
edited_recent = st.data_editor(recent_df, use_container_width=True, hide_index=True)

st.divider()

st.subheader("📋 전체 이력 현황 (참조용)")
st.dataframe(past_df, use_container_width=True, hide_index=True)

# 4. 시뮬레이션 결과 (보충 필요 항목 강조)
st.sidebar.header("💡 수정 제안")
needs_action = edited_recent[edited_recent['상태'] == '⚠️ 보충 필요']
if not needs_action.empty:
    st.sidebar.error(f"보충 필요한 달: {len(needs_action)}개")
    st.sidebar.table(needs_action[['지급월', '부족 금액']])
