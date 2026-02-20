import flet as ft
import json
import subprocess
import sys
import os
import re
import threading

from notion_client import Client
from dotenv import load_dotenv
from extract_params import extract_hyperparams, extract_metrics
from core.log_parsers import parse_log, detect_log_type

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
    file_path_field = ft.TextField(
        label="학습 파일 경로 (.py)",
        hint_text="예: /home/user/train.py 또는 C:\\projects\\train.py",
        expand=True,
    )
    selected_file = {"path": None}
    running_proc = {"proc": None}  # 실행 중인 프로세스 참조

    # 🔹 Flet FilePicker (데스크톱 모드용)
    file_picker = ft.FilePicker()

    # 🔹 기본 입력 필드
    exp_name_field = ft.TextField(label="Experiment Name", hint_text="예: ResNet50_Exp_01")
    batch_field = ft.TextField(label="Batch Size", value="32", keyboard_type=ft.KeyboardType.NUMBER)
    lr_field = ft.TextField(label="Learning Rate", value="0.001", keyboard_type=ft.KeyboardType.NUMBER)
    epochs_field = ft.TextField(label="Epochs", value="10", keyboard_type=ft.KeyboardType.NUMBER)
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
        "num_epochs": epochs_field,
        "epochs": epochs_field,
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
    # 🔹 외부 로그 임포트 UI 요소
    # -------------------------
    log_path_field = ft.TextField(
        label="로그 디렉토리 경로",
        hint_text="예: ./wandb/run-xxx-abc123 또는 ./runs/exp1",
        expand=True,
    )
    log_type_dropdown = ft.Dropdown(
        label="로그 타입",
        value="auto",
        width=160,
        options=[
            ft.dropdown.Option("auto", "Auto Detect"),
            ft.dropdown.Option("wandb", "WandB"),
            ft.dropdown.Option("tensorboard", "TensorBoard"),
        ],
    )

    def on_import_log(e):
        """외부 로그 파일(WandB/TensorBoard)을 파싱하여 GUI 필드에 채움"""
        log_path = log_path_field.value.strip() if log_path_field.value else ""
        if not log_path:
            status_text.value = "⚠️ 로그 디렉토리 경로를 입력해주세요."
            status_text.color = ft.Colors.ORANGE_700
            page.update()
            return

        if not os.path.exists(log_path):
            status_text.value = f"❌ 경로를 찾을 수 없습니다: {log_path}"
            status_text.color = ft.Colors.RED_700
            page.update()
            return

        status_text.value = "⏳ 로그 파싱 중..."
        status_text.color = ft.Colors.BLUE_700
        page.update()

        try:
            log_type = log_type_dropdown.value
            result = parse_log(log_path, log_type if log_type != "auto" else None)

            hp = result.get("hyperparams", {})
            metrics = result.get("metrics", {})
            name = result.get("name", "")

            # Experiment Name 채우기
            if name and not exp_name_field.value.strip():
                exp_name_field.value = name

            # 기본 하이퍼파라미터 필드 매핑
            hp_lower = {k.lower(): (k, v) for k, v in hp.items()}
            for known_key, field in BASE_FIELD_MAP.items():
                if known_key in hp_lower:
                    orig_key, val = hp_lower[known_key]
                    field.value = str(val)
                    del hp[orig_key]

            # 남은 하이퍼파라미터 → 동적 행
            extra_hp_rows.controls.clear()
            for k, v in hp.items():
                _add_dynamic_row(extra_hp_rows, "속성 이름", "값", "", "",
                                 key_val=k, val_val=v)

            # 기본 메트릭 필드 매핑
            metric_lower = {k.lower(): (k, v) for k, v in metrics.items()}
            for acc_key in ("accuracy", "test_accuracy", "val_accuracy", "eval_accuracy", "acc"):
                if acc_key in metric_lower:
                    orig_key, val = metric_lower[acc_key]
                    accuracy_field.value = str(round(val, 4) if isinstance(val, float) else val)
                    del metrics[orig_key]
                    break

            for loss_key in ("loss", "test_loss", "val_loss", "eval_loss"):
                if loss_key in metric_lower:
                    orig_key, val = metric_lower[loss_key]
                    loss_field.value = str(round(val, 4) if isinstance(val, float) else val)
                    del metrics[orig_key]
                    break

            # 남은 메트릭 → 동적 행
            extra_metric_rows.controls.clear()
            for k, v in metrics.items():
                _add_dynamic_row(extra_metric_rows, "메트릭", "값", "", "",
                                 key_val=k,
                                 val_val=round(v, 4) if isinstance(v, float) else v,
                                 number_keyboard=True)

            detected = detect_log_type(log_path) or "unknown"
            total_hp = len(BASE_FIELD_MAP) + len(extra_hp_rows.controls)
            total_m = (1 if accuracy_field.value else 0) + (1 if loss_field.value else 0) + len(extra_metric_rows.controls)
            status_text.value = (
                f"✅ [{detected.upper()}] 로그 임포트 완료! "
                f"(HP: {total_hp}개, Metrics: {total_m}개) "
                f"'Log to Notion'을 눌러 기록하세요."
            )
            status_text.color = ft.Colors.GREEN_700

        except ImportError as ie:
            status_text.value = f"❌ 패키지 필요: {ie}"
            status_text.color = ft.Colors.RED_700
        except Exception as ex:
            status_text.value = f"❌ 로그 파싱 오류: {ex}"
            status_text.color = ft.Colors.RED_700

        page.update()

    import_log_btn = ft.ElevatedButton(
        "📂 로그 임포트",
        on_click=on_import_log,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.INDIGO_600,
        width=180,
    )

    # -------------------------
    # 🔹 파일 찾아보기 (데스크톱 모드에서만 동작)
    # -------------------------
    async def on_browse_file(e):
        try:
            files = await file_picker.pick_files(
                dialog_title="학습 스크립트 선택",
                allowed_extensions=["py"],
                file_type=ft.FilePickerFileType.CUSTOM,
                allow_multiple=False,
            )
            if files and files[0].path:
                file_path_field.value = files[0].path
                page.update()
        except Exception:
            pass  # 웹 모드 등에서 실패 시 무시

    # -------------------------
    # 🔹 파일 로드 → 하이퍼파라미터 자동 채움
    # -------------------------
    def on_load_file(e):
        filepath = file_path_field.value.strip() if file_path_field.value else ""
        if not filepath:
            status_text.value = "⚠️ 파일 경로를 입력해주세요."
            status_text.color = ft.Colors.ORANGE_700
            page.update()
            return

        if not os.path.isfile(filepath):
            status_text.value = f"❌ 파일을 찾을 수 없습니다: {filepath}"
            status_text.color = ft.Colors.RED_700
            page.update()
            return

        selected_file["path"] = filepath

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

                # 🔹 experiment_result.json 우선, 없으면 stdout 파싱
                json_path = os.path.join(script_dir, "experiment_result.json")
                if os.path.exists(json_path):
                    with open(json_path, "r", encoding="utf-8") as f:
                        exp_data = json.load(f)

                    hp = exp_data.get("hyperparams", {})
                    metrics = exp_data.get("metrics", {})

                    # 하이퍼파라미터 필드 갱신
                    if "batch_size" in hp:
                        batch_field.value = str(hp["batch_size"])
                    if "lr" in hp:
                        lr_field.value = str(hp["lr"])
                    if "epochs" in hp:
                        epochs_field.value = str(hp["epochs"])
                    if "optimizer" in hp:
                        optimizer_field.value = str(hp["optimizer"])
                    if not exp_name_field.value.strip() and "name" in exp_data:
                        exp_name_field.value = exp_data["name"]

                    # 커스텀 하이퍼파라미터
                    skip_hp = {"batch_size", "lr", "epochs", "optimizer"}
                    extra_hp_rows.controls.clear()
                    for k, v in hp.items():
                        if k not in skip_hp:
                            _add_dynamic_row(extra_hp_rows, "속성 이름", "값", "", "",
                                             key_val=k, val_val=v)
                else:
                    metrics = extract_metrics(stdout)

                # 메트릭 필드 채우기
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
                                         key_val=k, val_val=round(v, 4) if isinstance(v, float) else v,
                                         number_keyboard=True)

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
                "2_epochs": int(float(epochs_field.value)),
                "3_lr": float(lr_field.value),
                "4_optimizer": optimizer_field.value.strip(),
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
                data["5_accuracy"] = float(accuracy_field.value)
            if loss_field.value and loss_field.value.strip():
                data["6_loss"] = float(loss_field.value)

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
    browse_btn = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN,
        icon_color=ft.Colors.PURPLE_600,
        tooltip="파일 찾아보기",
        on_click=on_browse_file,
    )

    load_btn = ft.ElevatedButton(
        "� 파일 로드 + 파라미터 추출",
        on_click=on_load_file,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.PURPLE_600,
        width=250,
    )

    run_btn = ft.ElevatedButton(
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

    stop_btn = ft.ElevatedButton(
        "⏹ 학습 중단",
        on_click=stop_training,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.RED_600,
        width=150,
        visible=False,
    )

    add_hp_btn = ft.ElevatedButton(
        "➕ 속성 추가",
        on_click=add_custom_hp,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.GREEN_600,
    )

    add_metric_btn = ft.ElevatedButton(
        "➕ 메트릭 추가",
        on_click=add_custom_metric,
        color=ft.Colors.WHITE,
        bgcolor=ft.Colors.TEAL_600,
    )

    log_btn = ft.ElevatedButton(
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
                ft.Row([file_path_field, browse_btn], spacing=8),
                ft.Row([load_btn, run_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=12),
                stop_btn,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
            padding=12,
            border_radius=8,
            bgcolor=ft.Colors.GREY_100,
        ),
        ft.Divider(height=16),

        # 외부 로그 임포트 영역
        ft.Text("📂 외부 로그 임포트 (WandB / TensorBoard)", size=16, weight=ft.FontWeight.BOLD),
        ft.Container(
            content=ft.Column([
                ft.Row([log_path_field, log_type_dropdown], spacing=8),
                ft.Row([import_log_btn], alignment=ft.MainAxisAlignment.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
            padding=12,
            border_radius=8,
            bgcolor=ft.Colors.INDIGO_50,
        ),
        ft.Divider(height=16),

        # 하이퍼파라미터
        ft.Text("⚙️ Hyperparameters", size=16, weight=ft.FontWeight.BOLD),
        exp_name_field,
        batch_field,
        epochs_field,
        lr_field,
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
    ft.run(main)
