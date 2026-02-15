import streamlit as st
from notion_client import Client
from dotenv import load_dotenv
import json
import os

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = "3082f94cda9c80fe975ad738924e8df9"

notion = Client(auth=NOTION_TOKEN)


# -------------------------
# 🔹 Database에서 실제 Data Source ID 가져오기
# -------------------------
def get_data_source_id():
    db = notion.databases.retrieve(DATABASE_ID)
    data_sources = db.get("data_sources", [])
    if not data_sources:
        raise Exception("데이터베이스에 data_source가 없습니다.")
    return data_sources[0]["id"].replace("-", "")


# -------------------------
# 🔹 DB 실제 title 컬럼 이름 찾기
# -------------------------
def get_title_property(ds_id):
    ds = notion.data_sources.retrieve(ds_id)
    for name, prop in ds["properties"].items():
        if prop["type"] == "title":
            return name
    return None


# -------------------------
# 🔹 타입 판별
# -------------------------
def infer_schema(value):
    if isinstance(value, bool):
        return {"checkbox": {}}
    elif isinstance(value, (int, float)):
        return {"number": {}}
    else:
        return {"rich_text": {}}


def ensure_property(ds_id, prop_name, value):
    ds = notion.data_sources.retrieve(ds_id)

    if prop_name in ds["properties"]:
        return

    notion.data_sources.update(
        data_source_id=ds_id,
        properties={prop_name: infer_schema(value)}
    )

    st.info(f"🆕 자동 생성된 컬럼: {prop_name}")


def build_property(value):
    if isinstance(value, bool):
        return {"checkbox": value}
    elif isinstance(value, (int, float)):
        return {"number": value}
    else:
        return {"rich_text": [{"text": {"content": str(value)}}]}


# -------------------------
# Streamlit UI
# -------------------------
st.title("🚀 Notion Experiment Logger")

exp_name = st.text_input("Experiment Name")

lr = st.number_input("Learning Rate", value=0.001)
batch = st.number_input("Batch Size", value=32)
optimizer = st.text_input("Optimizer", value="Adam")

st.subheader("➕ Custom Property")

custom_key = st.text_input("Property Name (예: dropout_rate)")
custom_value = st.text_input("Property Value")

if st.button("Log to Notion"):

    data = {
        "lr": lr,
        "batch_size": batch,
        "optimizer": optimizer,
    }

    if custom_key and custom_value:
        try:
            custom_value = float(custom_value)
        except:
            pass
        data[custom_key] = custom_value

    # 🔹 실제 Data Source ID 가져오기
    ds_id = get_data_source_id()

    # 🔹 title 컬럼 자동 탐지
    title_column = get_title_property(ds_id)

    if not title_column:
        st.error("❌ Title 컬럼을 찾을 수 없음")
        st.stop()

    # 🔹 컬럼 자동 생성
    for k, v in data.items():
        ensure_property(ds_id, k, v)

    # 🔹 properties 구성
    properties = {
        title_column: {
            "title": [{"text": {"content": exp_name}}]
        }
    }

    for k, v in data.items():
        properties[k] = build_property(v)

    # 🔹 페이지 생성
    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties=properties
    )

    st.success("🔥 Notion에 자동 생성 + 저장 완료!")