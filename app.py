import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🎯 가점 시뮬레이터 (대상월 중심)")

# 1. 데이터 로드 함수 정의
@st.cache_data(ttl=60)
def load_data():
    base_url = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ"
    return pd.read_csv(f"{base_url}/export?format=csv")

# 2. 데이터 정제 함수 정의 (여기서 먼저 정의!)
def clean_data(df):
    cols_to_clean = ['일용_금액', '일용_인원', '특고_금액', '특고_인원']
    for col in cols_to_clean:
        # 문자열 제거 후 숫자로 변환
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[\$, 원]', '', regex=True), errors='coerce').fillna(0)
    return df

# 3. 함수 호출은 정의 이후에!
df = clean_data(load_data())

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📝 1. 수치 입력 (시뮬레이션)")
    input_cols = ['지급월', '일용_금액', '일용_인원', '특고_금액', '특고_인원']
    edited_df = st.data_editor(df[input_cols], use_container_width=True, hide_index=True)

with col_right:
    st.subheader("📈 2. 가점 현황 결과 (2026-06 이후)")
    
    res = edited_df.copy()
    res['지급월_dt'] = pd.to_datetime(res['지급월'])
    target_df = res[res['지급월_dt'] >= '2026-06-01'].copy()
    
    target_df['합계금액'] = target_df['일용_금액'] + target_df['특고_금액']
    target_df['합계인원'] = target_df['일용_인원'] + target_df['특고_인원']
    # 상태 판정 (예: 합계금액 100만원 기준)
    target_df['상태'] = target_df['합계금액'].apply(lambda x: "✅ 충족" if x >= 1000000 else "⚠️ 보충 필요")
    
    def color_status(val):
        color = 'red' if '보충' in str(val) else 'green'
        return f'color: {color}; font-weight: bold'
    
    st.dataframe(
        target_df[['지급월', '합계금액', '합계인원', '상태']].style.map(color_status, subset=['상태']),
        use_container_width=True, 
        hide_index=True
    )
