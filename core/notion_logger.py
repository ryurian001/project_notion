# core/notion_logger.py

from notion_client import Client
import os


def get_client(token):
    """토큰으로 Notion 클라이언트 생성"""
    return Client(auth=token)


def resolve_data_source_id(token, database_id):
    """
    데이터베이스 ID에서 Data Source ID를 조회.
    databases.retrieve() → data_source 필드 추출.
    """
    notion = get_client(token)
    db = notion.databases.retrieve(database_id)

    # data_source 필드에서 ID 추출
    ds = db.get("data_source")
    if ds and isinstance(ds, dict) and "id" in ds:
        return ds["id"]

    # data_source_id 필드 직접 확인
    if "data_source_id" in db:
        return db["data_source_id"]

    # fallback: database_id 그대로 사용
    return database_id


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


def auto_log(name, data, token, ds_id):
    """Notion에 실험 결과 기록 (토큰/Data Source ID를 외부에서 전달)"""
    notion = get_client(token)

    for k, v in data.items():
        ensure_property(notion, ds_id, k, v)

    properties = {
        "이름": {
            "title": [{"text": {"content": name}}]
        }
    }

    for k, v in data.items():
        properties[k] = build_property(v)

    notion.pages.create(
        parent={"data_source_id": ds_id},
        properties=properties
    )


def test_connection(token, database_id):
    """Notion 연결 테스트 + Data Source ID 반환"""
    try:
        notion = get_client(token)
        # DB 조회 테스트
        notion.databases.retrieve(database_id)
        # Data Source ID 조회
        ds_id = resolve_data_source_id(token, database_id)
        return True, f"연결 성공! (Data Source ID: {ds_id[:8]}...)", ds_id
    except Exception as e:
        return False, str(e), None
