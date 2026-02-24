# core/notion_logger.py

from notion_client import Client
import os


def get_client(token):
    """토큰으로 Notion 클라이언트 생성"""
    return Client(auth=token)


def get_data_source_id(notion, db_id):
    db = notion.databases.retrieve(db_id)
    data_sources = db.get("data_sources", [])
    if not data_sources:
        raise Exception("데이터베이스에 data_source가 없습니다.")
    return data_sources[0]["id"].replace("-", "")

def get_title_property(notion, ds_id):
    ds = notion.data_sources.retrieve(ds_id)
    for name, prop in ds["properties"].items():
        if prop["type"] == "title":
            return name
    return None

def infer_schema(value):
    if isinstance(value, bool):
        return {"checkbox": {}}
    elif isinstance(value, (int, float)):
        return {"number": {}}
    else:
        return {"rich_text": {}}

def ensure_property(notion, ds_id, prop_name, value):
    ds = notion.data_sources.retrieve(ds_id)
    if prop_name in ds["properties"]:
        return
    notion.data_sources.update(
        data_source_id=ds_id,
        properties={prop_name: infer_schema(value)}
    )

def build_property(value):
    if isinstance(value, bool):
        return {"checkbox": value}
    elif isinstance(value, (int, float)):
        return {"number": value}
    else:
        return {"rich_text": [{"text": {"content": str(value)}}]}

def auto_log(name, data, token, db_id):
    """Notion에 실험 결과 기록"""
    notion = get_client(token)

    ds_id = get_data_source_id(notion, db_id)
    title_column = get_title_property(notion, ds_id)

    if not title_column:
        raise Exception("Title 컬럼을 찾을 수 없음")

    for k, v in data.items():
        ensure_property(notion, ds_id, k, v)

    properties = {
        title_column: {
            "title": [{"text": {"content": name}}]
        }
    }

    for k, v in data.items():
        properties[k] = build_property(v)

    notion.pages.create(
        parent={"database_id": db_id},
        properties=properties
    )

def test_connection(token, database_id):
    """Notion 연결 테스트"""
    try:
        notion = get_client(token)
        # DB 조회 테스트
        notion.databases.retrieve(database_id)
        return True, f"연결 성공! (Database 조회 완료)", database_id
    except Exception as e:
        return False, str(e), None
