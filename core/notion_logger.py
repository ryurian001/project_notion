# core/notion_logger.py

from notion_client import Client
import os

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATA_SOURCE_ID = os.getenv("DATA_SOURCE_ID")

notion = Client(auth=NOTION_TOKEN)


def infer_schema(value):
    if isinstance(value, bool):
        return {"checkbox": {}}
    elif isinstance(value, (int, float)):
        return {"number": {}}
    else:
        return {"rich_text": {}}


def ensure_property(prop_name, value):
    ds = notion.data_sources.retrieve(DATA_SOURCE_ID)

    if prop_name in ds["properties"]:
        return

    notion.data_sources.update(
        data_source_id=DATA_SOURCE_ID,
        properties={prop_name: infer_schema(value)}
    )


def build_property(value):
    if isinstance(value, bool):
        return {"checkbox": value}
    elif isinstance(value, (int, float)):
        return {"number": value}
    else:
        return {"rich_text": [{"text": {"content": str(value)}}]}


def auto_log(name, data):

    for k, v in data.items():
        ensure_property(k, v)

    properties = {
        "이름": {
            "title": [{"text": {"content": name}}]
        }
    }

    for k, v in data.items():
        properties[k] = build_property(v)

    notion.pages.create(
        parent={"data_source_id": DATA_SOURCE_ID},
        properties=properties
    )
