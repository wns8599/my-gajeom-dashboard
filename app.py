import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🎯 가점 시뮬레이터")

@st.cache_data(ttl=60)
def load_data():
    base_url = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ"
    return pd.read_csv(f"{base_url}/export?format=csv")

df = load_data()

# [중요] 엑셀에서 가져온 데이터를 계산 가능한 '진짜 숫자'로 바꾸는 과정
def clean_data(df):
    for col in ['일용_금액', '특고_금액']:
        # 쉼표(,) 제거 후 숫자로 변환, 에러 나면 0으로 처리
        df[col] = pd.to_numeric(df[col].replace(r'[\$, 원]', '', regex=True), errors='coerce').fillna(0)
    return df

df = clean_data(df)

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📝 1. 수치 입력 (시뮬레이션)")
    input_cols = ['지급월', '일용_금액', '특고_금액']
    edited_df = st.data_editor(df[input_cols], use_container_width=True, hide_index=True)

with col_right:
    st.subheader("📈 2. 가점 현황 자동 결과")
    
    # 여기서 다시 한번 숫자 처리를 확실히 해줍니다.
    res = edited_df.copy()
    res['합계금액'] = res['일용_금액'] + res['특고_금액']
    res['상태'] = res['합계금액'].apply(lambda x: "✅ 충족" if x >= 1000000 else "⚠️ 보충 필요")
    
    def color_status(val):
        color = 'red' if '보충' in str(val) else 'green'
        return f'color: {color}; font-weight: bold'
    
    st.dataframe(res.style.map(color_status, subset=['상태']), use_container_width=True, hide_index=True)
