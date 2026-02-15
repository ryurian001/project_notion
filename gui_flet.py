import flet as ft
import subprocess
import sys
import os
import re
import threading
from tkinter import Tk, filedialog
from notion_client import Client
from dotenv import load_dotenv
from extract_params import extract_hyperparams, extract_metrics

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


def pick_file_dialog():
    """tkinter로 파일 선택 대화상자를 열고 경로를 반환"""
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    filepath = filedialog.askopenfilename(
        title="학습 스크립트 선택",
        filetypes=[("Python Files", "*.py")],
    )
    root.destroy()
    return filepath if filepath else None


# -------------------------
# 🔹 Flet 앱
# -------------------------
def main(page: ft.Page):
    page.title = "Notion Experiment Logger"
    page.window.width = 620
    page.window.height = 900
    page.padding = 30
    page.scroll = ft.ScrollMode.AUTO
    page.theme_mode = ft.ThemeMode.LIGHT

    # 🔹 상태/로그
    status_text = ft.Text(value="", size=14, weight=ft.FontWeight.BOLD)
    log_output = ft.TextField(
        label="학습 출력 로그",
        multiline=True,
        min_lines=6,
        max_lines=12,
        read_only=True,
        value="",
        visible=False,
    )

    # 🔹 진행률 표시
    progress_bar = ft.ProgressBar(width=500, value=0, visible=False, color=ft.Colors.BLUE_600)
    progress_text = ft.Text(value="", size=13, visible=False)

    # 🔹 파일 경로
    file_path_text = ft.Text(value="선택된 파일 없음", size=13, color=ft.Colors.GREY_600, italic=True)
    selected_file = {"path": None}
    running_proc = {"proc": None}  # 실행 중인 프로세스 참조

    # 🔹 기본 입력 필드
    exp_name_field = ft.TextField(label="Experiment Name", hint_text="예: ResNet50_Exp_01")
    lr_field = ft.TextField(label="Learning Rate", value="0.001", keyboard_type=ft.KeyboardType.NUMBER)
    batch_field = ft.TextField(label="Batch Size", value="32", keyboard_type=ft.KeyboardType.NUMBER)
    optimizer_field = ft.TextField(label="Optimizer", value="Adam")

    # 🔹 추가 하이퍼파라미터 영역
    extra_hp_rows = ft.Column(spacing=6)

    # 🔹 메트릭 필드
    accuracy_field = ft.TextField(label="Accuracy", hint_text="자동 추출됨", keyboard_type=ft.KeyboardType.NUMBER)
    loss_field = ft.TextField(label="Loss", hint_text="자동 추출됨", keyboard_type=ft.KeyboardType.NUMBER)
    extra_metric_rows = ft.Column(spacing=6)

    BASE_FIELD_MAP = {
        "batch_size": batch_field,
        "lr": lr_field,
        "learning_rate": lr_field,
        "optimizer": optimizer_field,
    }

    # -------------------------
    # 동적 행 추가 헬퍼
    # -------------------------
    def _add_dynamic_row(container, key_label, val_label, key_hint, val_hint, key_val="", val_val="", number_keyboard=False):
        key_field = ft.TextField(label=key_label, hint_text=key_hint, value=key_val, expand=True)
        kw = {"keyboard_type": ft.KeyboardType.NUMBER} if number_keyboard else {}
        value_field = ft.TextField(label=val_label, hint_text=val_hint, value=str(val_val), expand=True, **kw)

        row = ft.Row(spacing=8)

        def delete_row(e):
            container.controls.remove(row)
            page.update()

        delete_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.RED_400,
            tooltip="삭제",
            on_click=delete_row,
        )

        row.controls = [key_field, value_field, delete_btn]
        row.data = {"key_field": key_field, "value_field": value_field}
        container.controls.append(row)
        return row

    def add_custom_hp(e):
        _add_dynamic_row(extra_hp_rows, "속성 이름", "값", "예: dropout_rate", "값 입력")
        page.update()

    def add_custom_metric(e):
        _add_dynamic_row(extra_metric_rows, "메트릭 이름", "값", "예: f1_score", "예: 0.92", number_keyboard=True)
        page.update()

    # -------------------------
    # 🔹 파일 선택 → 하이퍼파라미터 자동 채움
    # -------------------------
    def on_pick_file(e):
        filepath = pick_file_dialog()
        if not filepath:
            return

        selected_file["path"] = filepath
        file_path_text.value = f"📄 {os.path.basename(filepath)}"
        file_path_text.color = ft.Colors.BLUE_700
        file_path_text.italic = False

        try:
            hp = extract_hyperparams(filepath)

            for key, field in BASE_FIELD_MAP.items():
                if key in hp:
                    field.value = str(hp.pop(key))

            if not exp_name_field.value.strip():
                basename = os.path.splitext(os.path.basename(filepath))[0]
                exp_name_field.value = basename

            extra_hp_rows.controls.clear()
            for k, v in hp.items():
                _add_dynamic_row(extra_hp_rows, "속성 이름", "값", "", "", key_val=k, val_val=v)

            total = len(BASE_FIELD_MAP) + len(hp)
            status_text.value = f"✅ 하이퍼파라미터 자동 추출 완료! ({total}개)"
            status_text.color = ft.Colors.GREEN_700

        except Exception as ex:
            status_text.value = f"❌ 파싱 오류: {ex}"
            status_text.color = ft.Colors.RED_700

        page.update()

    # -------------------------
    # 🔹 학습 실행 + 메트릭 추출
    # -------------------------
    def run_and_log(e):
        filepath = selected_file.get("path")
        if not filepath:
            status_text.value = "⚠️ 먼저 학습 파일을 선택해주세요."
            status_text.color = ft.Colors.ORANGE_700
            page.update()
            return

        exp_name = exp_name_field.value.strip()
        if not exp_name:
            status_text.value = "⚠️ Experiment Name을 입력해주세요."
            status_text.color = ft.Colors.ORANGE_700
            page.update()
            return

        run_btn.disabled = True
        log_btn.disabled = True
        stop_btn.visible = True
        status_text.value = "⏳ 학습 스크립트 실행 중..."
        status_text.color = ft.Colors.BLUE_700
        log_output.value = ""
        log_output.visible = True
        progress_bar.visible = True
        progress_bar.value = 0
        progress_bar.color = ft.Colors.BLUE_600
        progress_text.visible = True
        progress_text.value = "준비 중..."
        page.update()

        def _execute():
            all_output = []
            try:
                script_dir = os.path.dirname(os.path.abspath(filepath))
                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"

                proc = subprocess.Popen(
                    [sys.executable, "-u", filepath],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=script_dir,
                    env=env,
                    bufsize=1,
                )
                running_proc["proc"] = proc

                num_epochs = None  # AST에서 추출 시도
                try:
                    hp = extract_hyperparams(filepath)
                    for k in ("num_epochs", "epochs"):
                        if k in hp:
                            num_epochs = int(hp[k])
                            break
                except Exception:
                    pass

                current_epoch = 0
                last_epoch_line = ""

                for line in proc.stdout:
                    line = line.rstrip()
                    all_output.append(line)

                    # 로그 창 업데이트 (마지막 20줄만)
                    display_lines = all_output[-20:]
                    log_output.value = "\n".join(display_lines)

                    # Epoch 진행률 파싱: "Epoch 3/10: ..." 또는 "Epoch 3: ..."
                    epoch_match = re.search(r"Epoch\s+(\d+)(?:/(\d+))?", line)
                    if epoch_match:
                        current_epoch = int(epoch_match.group(1))
                        if epoch_match.group(2):
                            num_epochs = int(epoch_match.group(2))
                        last_epoch_line = line

                        if num_epochs and num_epochs > 0:
                            progress_bar.value = current_epoch / num_epochs
                            progress_text.value = f"Epoch {current_epoch}/{num_epochs}"
                        else:
                            progress_text.value = f"Epoch {current_epoch}"

                    page.update()

                proc.wait()
                stdout = "\n".join(all_output)

                if proc.returncode != 0:
                    status_text.value = f"❌ 스크립트 실행 실패 (exit code: {proc.returncode})"
                    status_text.color = ft.Colors.RED_700
                    progress_bar.color = ft.Colors.RED_600
                    run_btn.disabled = False
                    log_btn.disabled = False
                    page.update()
                    return

                # 진행바 완료
                progress_bar.value = 1.0
                progress_bar.color = ft.Colors.GREEN_600
                progress_text.value = "학습 완료!"

                metrics = extract_metrics(stdout)

                if "test_accuracy" in metrics:
                    accuracy_field.value = str(metrics["test_accuracy"])
                elif "final_val_acc" in metrics:
                    accuracy_field.value = str(metrics["final_val_acc"])

                if "test_loss" in metrics:
                    loss_field.value = str(metrics["test_loss"])
                elif "final_val_loss" in metrics:
                    loss_field.value = str(metrics["final_val_loss"])

                extra_metric_rows.controls.clear()
                metric_skip = {"test_accuracy", "test_loss"}
                for k, v in metrics.items():
                    if k not in metric_skip:
                        _add_dynamic_row(extra_metric_rows, "메트릭", "값", "", "",
                                         key_val=k, val_val=round(v, 4), number_keyboard=True)

                status_text.value = "✅ 학습 완료! 메트릭 추출됨. 'Log to Notion'을 눌러 기록하세요."
                status_text.color = ft.Colors.GREEN_700

            except Exception as ex:
                status_text.value = f"❌ 실행 오류: {ex}"
                status_text.color = ft.Colors.RED_700
            finally:
                running_proc["proc"] = None
                stop_btn.visible = False
                run_btn.disabled = False
                log_btn.disabled = False
                page.update()

        thread = threading.Thread(target=_execute, daemon=True)
        thread.start()

    # -------------------------
    # 🔹 Notion에 기록
    # -------------------------
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
                "1_batch_size": float(batch_field.value),
                "2_lr": float(lr_field.value),
                "3_optimizer": optimizer_field.value.strip(),
            }

            for row in extra_hp_rows.controls:
                k = row.data["key_field"].value.strip()
                v = row.data["value_field"].value.strip()
                if k and v:
                    try:
                        v = float(v)
                    except ValueError:
                        pass
                    data[k] = v

            if accuracy_field.value and accuracy_field.value.strip():
                data["4_accuracy"] = float(accuracy_field.value)
            if loss_field.value and loss_field.value.strip():
                data["5_loss"] = float(loss_field.value)

            for row in extra_metric_rows.controls:
                k = row.data["key_field"].value.strip()
                v = row.data["value_field"].value.strip()
                if k and v:
                    try:
                        v = float(v)
                    except ValueError:
                        pass
                    data[k] = v

            ds_id = get_data_source_id()
            title_column = get_title_property(ds_id)

            if not title_column:
                status_text.value = "❌ Title 컬럼을 찾을 수 없음"
                status_text.color = ft.Colors.RED_700
                page.update()
                return

            for k, v in data.items():
                ensure_property(ds_id, k, v)

            properties = {
                title_column: {
                    "title": [{"text": {"content": exp_name}}]
                }
            }
            for k, v in data.items():
                properties[k] = build_property(v)

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

    # -------------------------
    # 🔹 버튼들
    # -------------------------
    pick_btn = ft.Button(
        "📂 학습 파일 선택 (.py)",
        on_click=on_pick_file,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.PURPLE_600,
        width=250,
    )

    run_btn = ft.Button(
        "▶ 학습 실행 + 메트릭 추출",
        on_click=run_and_log,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.ORANGE_700,
        width=250,
    )

    def stop_training(e):
        proc = running_proc.get("proc")
        if proc and proc.poll() is None:
            proc.terminate()
            status_text.value = "⏹️ 학습이 중단되었습니다."
            status_text.color = ft.Colors.ORANGE_700
            progress_bar.color = ft.Colors.ORANGE_600
            progress_text.value = "중단됨"
            page.update()

    stop_btn = ft.Button(
        "⏹ 학습 중단",
        on_click=stop_training,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.RED_600,
        width=150,
        visible=False,
    )

    add_hp_btn = ft.Button(
        "➕ 속성 추가",
        on_click=add_custom_hp,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.GREEN_600,
    )

    add_metric_btn = ft.Button(
        "➕ 메트릭 추가",
        on_click=add_custom_metric,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.TEAL_600,
    )

    log_btn = ft.Button(
        "🔥 Log to Notion",
        on_click=log_to_notion,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.BLUE_600,
        width=500,
        height=48,
    )

    # -------------------------
    # 🔹 페이지 구성
    # -------------------------
    page.add(
        ft.Text("🚀 Notion Experiment Logger", size=24, weight=ft.FontWeight.BOLD),
        ft.Divider(height=10),

        # 파일 선택 영역
        ft.Container(
            content=ft.Column([
                ft.Row([pick_btn, run_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=12),
                stop_btn,
                file_path_text,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
            padding=12,
            border_radius=8,
            bgcolor=ft.Colors.GREY_100,
        ),
        ft.Divider(height=16),

        # 하이퍼파라미터
        ft.Text("⚙️ Hyperparameters", size=16, weight=ft.FontWeight.BOLD),
        exp_name_field,
        lr_field,
        batch_field,
        optimizer_field,
        ft.Row([
            ft.Text("➕ Custom Properties", size=14, weight=ft.FontWeight.BOLD),
            add_hp_btn,
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        extra_hp_rows,
        ft.Divider(height=16),

        # 메트릭
        ft.Text("📊 Metrics (학습 결과)", size=16, weight=ft.FontWeight.BOLD),
        accuracy_field,
        loss_field,
        ft.Row([
            ft.Text("➕ Custom Metrics", size=14, weight=ft.FontWeight.BOLD),
            add_metric_btn,
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        extra_metric_rows,
        ft.Divider(height=16),

        # 학습 진행 상황
        progress_bar,
        progress_text,
        log_output,
        ft.Divider(height=16),

        # Notion 기록
        log_btn,
        status_text,
    )


if __name__ == "__main__":
    ft.app(main)
