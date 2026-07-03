import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🎯 가점 시뮬레이터")

# 1. 데이터 로드 (구글 시트 연동)
@st.cache_data(ttl=60)
def load_data():
    base_url = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ"
    return pd.read_csv(f"{base_url}/export?format=csv")

df = load_data()

# 2. 좌측 입력 데이터 수정
st.subheader("📝 데이터 입력 및 수정 (시뮬레이션)")
edited_df = st.data_editor(df, use_container_width=True, hide_index=True)

# 3. 우측 가점 현황 자동 계산 로직 (수정된 edited_df를 바탕으로 계산)
def calculate_gajeom(df):
    results = []
    # 예시: 매달 6개월치 합산 로직 (사용자님의 실제 가점 현황 수식 적용 가능)
    for i in range(len(df)):
        # 최근 6개월 합계 계산 예시
        recent_6m = df.iloc[max(0, i-5):i+1]
        amt_sum = recent_6m['일용_금액'].sum() + recent_6m['특고_금액'].sum()
        
        status = "✅ 충족" if amt_sum >= 2000000 else "❌ 부족" # 예시 조건
        results.append({
            "대상월": df.iloc[i]['지급월'],
            "상태": status,
            "부족금액": max(0, 2000000 - amt_sum)
        })
    return pd.DataFrame(results)

# 4. 화면 출력 (분할)
col1, col2 = st.columns([2, 1])

with col1:
    st.info("데이터를 수정하면 자동으로 오른쪽 현황판이 변합니다.")
    
with col2:
    st.subheader("📈 가점 현황 실시간 결과")
    gajeom_results = calculate_gajeom(edited_df)
    st.dataframe(gajeom_results, use_container_width=True, hide_index=True)
