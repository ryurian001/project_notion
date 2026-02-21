import streamlit as st

st.set_page_config(page_title="Experiment Platform", layout="wide")

st.title("🧪 Experiment Platform")
st.markdown("---")

# ----------------------
# Notion 설정
# ----------------------
st.subheader("🔑 Notion API 설정")

if "notion_token" not in st.session_state:
    st.session_state.notion_token = ""

if "notion_db_id" not in st.session_state:
    st.session_state.notion_db_id = ""

col1, col2 = st.columns(2)

with col1:
    token = st.text_input(
        "Notion API Token",
        value=st.session_state.notion_token,
        type="password",
        placeholder="ntn_xxxxxxxxxxxx"
    )

with col2:
    db_id = st.text_input(
        "Database ID",
        value=st.session_state.notion_db_id,
        placeholder="Notion 데이터베이스 ID (URL에서 확인)"
    )

# 저장 버튼
if st.button("💾 저장"):
    st.session_state.notion_token = token
    st.session_state.notion_db_id = db_id
    st.success("✅ 설정이 저장되었습니다! (연결 테스트를 진행해주세요)")

# 연결 테스트
if st.button("🔌 연결 테스트"):
    if not token or not db_id:
        st.error("토큰과 Database ID를 먼저 입력해주세요.")
    else:
        from core.notion_logger import test_connection
        with st.spinner("연결 테스트 중... (Database 조회)"):
            success, msg, _ = test_connection(token, db_id)
        if success:
            st.success(f"✅ {msg}")
            # 성공 시 자동 저장
            st.session_state.notion_token = token
            st.session_state.notion_db_id = db_id
            st.session_state.notion_tested = True
        else:
            st.error(f"❌ 연결 실패: {msg}")
            st.session_state.notion_tested = False

st.markdown("---")

# 현재 설정 상태 표시
if st.session_state.notion_token and st.session_state.get("notion_tested", False):
    st.info(f"🟢 Notion API 설정 및 테스트 완료")
elif st.session_state.notion_token and st.session_state.notion_db_id:
    st.warning("🟡 연결 테스트를 실행하여 Notion 연결을 확인해주세요.")
else:
    st.warning("🟡 Notion API 설정이 필요합니다. 토큰과 Database ID를 입력 후 연결 테스트를 실행해주세요.")

st.markdown("---")
st.markdown("👈 **왼쪽 사이드바에서 페이지를 선택하세요.**")