import flet as ft
from notion_client import Client
from dotenv import load_dotenv
import os

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

notion = Client(auth=NOTION_TOKEN)


# -------------------------
# 🔹 Notion API 함수들
# -------------------------
def get_data_source_id():
    db = notion.databases.retrieve(DATABASE_ID)
    data_sources = db.get("data_sources", [])
    if not data_sources:
        raise Exception("데이터베이스에 data_source가 없습니다.")
    return data_sources[0]["id"].replace("-", "")


def get_title_property(ds_id):
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


def ensure_property(ds_id, prop_name, value):
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


# -------------------------
# 🔹 Flet 앱
# -------------------------
def main(page: ft.Page):
    page.title = "Notion Experiment Logger"
    page.window.width = 560
    page.window.height = 650
    page.padding = 30
    page.scroll = ft.ScrollMode.AUTO
    page.theme_mode = ft.ThemeMode.LIGHT

    # 🔹 상태 메시지 표시용
    status_text = ft.Text(value="", size=14, weight=ft.FontWeight.BOLD)

    # 🔹 기본 입력 필드
    exp_name_field = ft.TextField(label="Experiment Name", hint_text="예: ResNet50_Exp_01")
    lr_field = ft.TextField(label="Learning Rate", value="0.001", keyboard_type=ft.KeyboardType.NUMBER)
    batch_field = ft.TextField(label="Batch Size", value="32", keyboard_type=ft.KeyboardType.NUMBER)
    optimizer_field = ft.TextField(label="Optimizer", value="Adam")

    # 🔹 커스텀 속성 관리
    custom_rows = ft.Column(spacing=6)

    def add_custom_prop(e):
        key_field = ft.TextField(label="속성 이름", hint_text="예: dropout_rate", expand=True)
        value_field = ft.TextField(label="값", hint_text="값 입력", expand=True)

        row = ft.Row(spacing=8)

        def delete_row(e):
            custom_rows.controls.remove(row)
            page.update()

        delete_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.RED_400,
            tooltip="삭제",
            on_click=delete_row,
        )

        row.controls = [key_field, value_field, delete_btn]
        row.data = {"key_field": key_field, "value_field": value_field}

        custom_rows.controls.append(row)
        page.update()

    # 🔹 Log to Notion 처리
    def log_to_notion(e):
        exp_name = exp_name_field.value.strip()
        if not exp_name:
            status_text.value = "⚠️ Experiment Name을 입력해주세요."
            status_text.color = ft.Colors.ORANGE_700
            page.update()
            return

        status_text.value = "⏳ Notion에 기록 중..."
        status_text.color = ft.Colors.BLUE_700
        log_btn.disabled = True
        page.update()

        try:
            data = {
                "batch_size": float(batch_field.value),
                "optimizer": optimizer_field.value.strip(),
                "lr": float(lr_field.value),
            }

            # 🔹 커스텀 속성들 추가
            for row in custom_rows.controls:
                k = row.data["key_field"].value.strip()
                v = row.data["value_field"].value.strip()
                if k and v:
                    try:
                        v = float(v)
                    except ValueError:
                        pass
                    data[k] = v

            # 🔹 Data Source ID
            ds_id = get_data_source_id()

            # 🔹 title 컬럼 탐지
            title_column = get_title_property(ds_id)
            if not title_column:
                status_text.value = "❌ Title 컬럼을 찾을 수 없음"
                status_text.color = ft.Colors.RED_700
                page.update()
                return

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

            status_text.value = "🔥 Notion에 자동 생성 + 저장 완료!"
            status_text.color = ft.Colors.GREEN_700

        except Exception as ex:
            status_text.value = f"❌ 오류: {ex}"
            status_text.color = ft.Colors.RED_700

        finally:
            log_btn.disabled = False
            page.update()

    # 🔹 버튼들
    add_btn = ft.Button(
        "➕ 속성 추가",
        on_click=add_custom_prop,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.GREEN_600,
    )

    log_btn = ft.Button(
        "🔥 Log to Notion",
        on_click=log_to_notion,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.BLUE_600,
        width=500,
        height=48,
    )

    # 🔹 페이지 구성
    page.add(
        ft.Text("🚀 Notion Experiment Logger", size=24, weight=ft.FontWeight.BOLD),
        ft.Divider(height=10),
        exp_name_field,
        lr_field,
        batch_field,
        optimizer_field,
        ft.Divider(height=20),
        ft.Row([
            ft.Text("➕ Custom Properties", size=16, weight=ft.FontWeight.BOLD),
            add_btn,
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        custom_rows,
        ft.Divider(height=20),
        log_btn,
        status_text,
    )


if __name__ == "__main__":
    ft.app(main)
