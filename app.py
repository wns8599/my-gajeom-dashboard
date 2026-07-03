import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🎯 가점 시뮬레이터")

@st.cache_data(ttl=60)
def load_data():
    base_url = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ"
    return pd.read_csv(f"{base_url}/export?format=csv")

df = load_data()

# 숫자 데이터 정제 함수
def clean_data(df):
    cols_to_clean = ['일용_금액', '일용_인원', '특고_금액', '특고_인원']
    for col in cols_to_clean:
        df[col] = pd.to_numeric(df[col].replace(r'[\$, 원]', '', regex=True), errors='coerce').fillna(0)
    return df

df = clean_data(df)

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📝 1. 수치 입력 (시뮬레이션)")
    # 인원 포함하여 입력 컬럼 지정
    input_cols = ['지급월', '일용_금액', '일용_인원', '특고_금액', '특고_인원']
    edited_df = st.data_editor(df[input_cols], use_container_width=True, hide_index=True)

with col_right:
    st.subheader("📈 2. 가점 현황 자동 결과")
    
    res = edited_df.copy()
    # 합계 계산
    res['합계금액'] = res['일용_금액'] + res['특고_금액']
    res['합계인원'] = res['일용_인원'] + res['특고_인원']
    
    # 상태 판정 (예시 로직)
    res['상태'] = res['합계금액'].apply(lambda x: "✅ 충족" if x >= 1000000 else "⚠️ 보충 필요")
    
    def color_status(val):
        color = 'red' if '보충' in str(val) else 'green'
        return f'color: {color}; font-weight: bold'
    
    st.dataframe(
        res.style.map(color_status, subset=['상태']), 
        use_container_width=True, 
        hide_index=True
    )
