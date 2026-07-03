import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("📊 수정 가능한 가점 관리 대시보드")

@st.cache_data(ttl=600)
def load_data():
    base_url = "https://docs.google.com/spreadsheets/d/1tPQsHFpeMX91SlFqDlylx4ZOSGmr9tjvReXqABYqkUQ"
    csv_export_url = f"{base_url}/export?format=csv"
    return pd.read_csv(csv_export_url)

df = load_data()

st.subheader("표를 클릭하여 숫자를 직접 수정해보세요!")

# data_editor: 여기서 데이터를 직접 수정할 수 있습니다.
edited_df = st.data_editor(df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("수정된 데이터 기반 실적 확인")

# 수정된 데이터(edited_df)를 가지고 실시간으로 다시 상태 계산
def check_status(row):
    # 예시 로직: 금액이 0이면 '보충 필요', 아니면 '충족'
    if row['일용_금액'] + row['특고_금액'] == 0:
        return '⚠️ 보충 필요'
    return '✅ 충족'

# 수정된 표의 '상태' 열을 자동으로 갱신
edited_df['상태'] = edited_df.apply(check_status, axis=1)

# 결과 출력
st.dataframe(edited_df, use_container_width=True, hide_index=True)

st.info("💡 위에서 수정해도 구글 시트 파일 자체가 바뀌지는 않습니다. 확인용으로 사용하세요!")
