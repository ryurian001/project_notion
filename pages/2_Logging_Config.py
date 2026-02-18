import streamlit as st
import os

st.title("🟦 Logging Configuration")

log_dir = st.text_input("Log Directory", value="logs")

if st.button("Apply Logging Config"):

    os.makedirs(log_dir, exist_ok=True)

    st.session_state.log_dir = log_dir
    st.success(f"✅ Log directory set to: {log_dir}")