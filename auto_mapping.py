from notion_client import Client
from dotenv import load_dotenv
import json
import datetime
import os

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = "3082f94cda9c805ea6f3c1373fec7e14"

notion = Client(auth=NOTION_TOKEN)


# 🔹 Database에서 Data Source ID 가져오기
def get_data_source_id(database_id):
    db = notion.databases.retrieve(database_id)
    data_sources = db.get("data_sources", [])
    if not data_sources:
        raise Exception("데이터베이스에 data_source가 없습니다.")
    return data_sources[0]["id"].replace("-", "")


# 🔹 타입 자동 매핑
def infer_notion_schema(value):
    if isinstance(value, bool):
        return {"checkbox": {}}
    elif isinstance(value, (int, float)):
        return {"number": {}}
    elif isinstance(value, list):
        return {"multi_select": {}}
    else:
        return {"rich_text": {}}


# 🔹 컬럼 자동 생성
def ensure_property_exists(data_source_id, prop_name, value):
    ds = notion.data_sources.retrieve(data_source_id)
    existing = ds["properties"]

    if prop_name in existing:
        return

    schema = infer_notion_schema(value)

    notion.data_sources.update(
        data_source_id=data_source_id,
        properties={prop_name: schema}
    )

    print(f"🔥 자동 생성된 컬럼: {prop_name}")


# 🔹 값 → Notion property 변환
def build_property_value(value):
    if isinstance(value, bool):
        return {"checkbox": value}
    elif isinstance(value, (int, float)):
        return {"number": value}
    elif isinstance(value, list):
        return {
            "multi_select": [{"name": str(v)} for v in value]
        }
    else:
        return {
            "rich_text": [
                {"text": {"content": str(value)}}
            ]
        }


# 🔹 자동 로깅
def auto_log(title, data_dict):
    # 0️⃣ Data Source ID 가져오기
    data_source_id = get_data_source_id(DATABASE_ID)

    # 1️⃣ 컬럼 자동 생성
    for key, value in data_dict.items():
        ensure_property_exists(data_source_id, key, value)

    # 2️⃣ property 구성
    properties = {}

    # Title 컬럼 이름은 실제 DB 첫 컬럼 이름에 맞춰야 함
    properties["이름"] = {
        "title": [{"text": {"content": title}}]
    }

    for key, value in data_dict.items():
        properties[key] = build_property_value(value)

    # 3️⃣ 페이지 생성
    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties=properties
    )

    print("🚀 Notion 자동 로깅 성공!")


# 🔹 사용 예시
experiment_data = {
    "lr": 0.001,
    "batch_size": 32,
    "optimizer": "Adam",
    "accuracy": 0.95,
    "loss": 0.045,
    "use_scheduler": True,
    "tags": ["resnet", "baseline"]
}

auto_log("ResNet_Auto_Run_01", experiment_data)
