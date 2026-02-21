# core/notion_logger.py

from notion_client import Client
import os


def get_client(token):
    """토큰으로 Notion 클라이언트 생성"""
    return Client(auth=token)


def infer_schema(value):
    if isinstance(value, bool):
        return {"checkbox": {}}
    elif isinstance(value, (int, float)):
        return {"number": {}}
    else:
        return {"rich_text": {}}


def ensure_properties(notion, db_id, data):
    db = notion.databases.retrieve(db_id)
    existing_props = db.get("properties", {})
    
    missing_props = {}
    for k, v in data.items():
        if k not in existing_props and k != "이름":
            missing_props[k] = infer_schema(v)
            
    if missing_props:
        notion.databases.update(
            database_id=db_id,
            properties=missing_props
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

    # 지정된 속성 이름 매핑
    key_mapping = {
        "lr": "1.lr",
        "batch_size": "2.batch_size",
        "epochs": "3.epochs",
        "accuracy": "4.accuracy",
        "loss": "5.loss"
    }

    mapped_data = {}
    for k, v in data.items():
        new_key = key_mapping.get(k, k)
        mapped_data[new_key] = v

    # 누락된 속성 한번에 추가 (속도 개선)
    ensure_properties(notion, db_id, mapped_data)

    properties = {
        "이름": {
            "title": [{"text": {"content": name}}]
        }
    }

    for k, v in mapped_data.items():
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
