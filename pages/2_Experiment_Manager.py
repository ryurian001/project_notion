import streamlit as st
import os
import time
import threading
from core.log_parser import parse_log
from core.runner import run_experiment
from core.notion_logger import auto_log
from core.grid_search import generate_grid

st.title("🟩 Experiment Manager")

# ----------------------
# Session State 초기화
# ----------------------
if "grid_running" not in st.session_state:
    st.session_state.grid_running = False
if "grid_process" not in st.session_state:
    st.session_state.grid_process = None
if "grid_current" not in st.session_state:
    st.session_state.grid_current = 0
if "grid_total" not in st.session_state:
    st.session_state.grid_total = 0
if "grid_output_lines" not in st.session_state:
    st.session_state.grid_output_lines = []
if "grid_stop_requested" not in st.session_state:
    st.session_state.grid_stop_requested = False
if "grid_completed_logs" not in st.session_state:
    st.session_state.grid_completed_logs = []


# ----------------------
# 로그 폴더 선택
# ----------------------
st.subheader("📂 로그 설정")

workspace = st.session_state.get("workspace", ".")

col_log1, col_log2 = st.columns(2)

with col_log1:
    log_dir_input = st.text_input("로그 폴더 (읽기)", value="logs")
    log_dir = os.path.join(workspace, log_dir_input)

with col_log2:
    save_log_dir_input = st.text_input("저장 폴더 (Grid Search 결과)", value="logs")
    save_log_dir = os.path.join(workspace, save_log_dir_input)

if not os.path.exists(log_dir):
    st.warning(f"로그 폴더가 없습니다: {log_dir}")
    st.stop()

logs = sorted(
    [f for f in os.listdir(log_dir) if f.endswith(".log")],
    reverse=True
)

if not logs:
    st.info("로그 파일이 없습니다.")
    st.stop()

selected_log = st.selectbox("📄 Select Log", logs)

# 로그에서 자동 추출 (하이퍼파라미터와 메트릭 분리)
hyperparams, latest_metrics = parse_log(os.path.join(log_dir, selected_log))

# epoch 관련 정보 제거
latest_metrics = {k: v for k, v in latest_metrics.items() if k.lower() not in ("epoch", "epochs")}

st.markdown("---")

# ----------------------
# 파라미터 설정 (단일값 / 범위)
# ----------------------
st.subheader("⚙️ 파라미터 설정")

# epoch 예외처리 안내
st.caption("ℹ️ `epochs` 파라미터는 단일값으로만 설정 가능합니다 (Grid Search 범위 불가)")

params_config = {}

for k, v in hyperparams.items():
    # epoch은 범위 선택 불가
    is_epoch = k.lower() in ("epoch", "epochs")
    is_numeric = isinstance(v, (int, float))

    st.markdown(f"**{k}**")

    if is_epoch:
        # epoch: 단일값 고정
        val = st.number_input(
            f"{k} (단일값)",
            value=float(v) if isinstance(v, (int, float)) else 5.0,
            key=f"param_{k}"
        )
        # int로 저장
        params_config[k] = {"mode": "single", "value": int(val)}

    elif is_numeric:
        col_mode, col_vals = st.columns([1, 3])

        with col_mode:
            mode = st.selectbox(
                "모드",
                ["단일값(Single)", "범위(Range)"],
                key=f"mode_{k}"
            )

        with col_vals:
            if "범위" in mode:
                c1, c2, c3 = st.columns(3)
                with c1:
                    min_val = st.number_input("Min", value=float(v), key=f"min_{k}", format="%g")
                with c2:
                    max_val = st.number_input("Max", value=float(v), key=f"max_{k}", format="%g")
                with c3:
                    # step 기본값: 현재 값의 절반 또는 1
                    default_step = abs(float(v)) / 2 if float(v) != 0 else 1.0
                    step_val = st.number_input("Step", value=default_step, key=f"step_{k}", format="%g")

                if step_val <= 0:
                    st.error("Step은 0보다 커야 합니다.")
                elif min_val > max_val:
                    st.error("Min은 Max보다 작아야 합니다.")
                else:
                    params_config[k] = {"mode": "range", "min": min_val, "max": max_val, "step": step_val}
            else:
                val = st.number_input("값", value=float(v), key=f"single_{k}", format="%g")
                # 정수 판별
                if isinstance(v, int) or (isinstance(v, float) and v == int(v)):
                    params_config[k] = {"mode": "single", "value": int(val)}
                else:
                    params_config[k] = {"mode": "single", "value": val}
    else:
        # 문자열 등 비숫자 타입: 단일값만
        val = st.text_input(f"{k}", str(v), key=f"str_{k}")
        params_config[k] = {"mode": "single", "value": val}

st.markdown("---")

# ----------------------
# Grid Search 조합 미리보기
# ----------------------
if params_config:
    grid = generate_grid(params_config)
    total_combos = len(grid)

    st.subheader(f"🔢 Grid Search 조합: **{total_combos}개**")

    with st.expander("조합 미리보기", expanded=False):
        for i, combo in enumerate(grid):
            st.text(f"[{i+1}] {combo}")
else:
    grid = []
    total_combos = 0


# ----------------------
# 백그라운드 출력 수집
# ----------------------
def collect_output(process, log_file, output_lines):
    try:
        for line in iter(process.stdout.readline, ""):
            if line:
                output_lines.append(line.rstrip("\n"))
                log_file.write(line)
                log_file.flush()
        process.stdout.close()
    except:
        pass
    finally:
        log_file.close()


# ----------------------
# 실행 버튼
# ----------------------
st.subheader("🚀 실행")

col_run, col_stop, col_notion = st.columns(3)

with col_run:
    run_clicked = st.button(
        f"▶️ Run Grid Search ({total_combos}개)",
        disabled=st.session_state.grid_running or total_combos == 0
    )

with col_stop:
    stop_clicked = st.button(
        "⛔ 중단",
        disabled=not st.session_state.grid_running
    )

with col_notion:
    notion_clicked = st.button("📤 Log to Notion")

# 실험 스크립트 안내 (Experiment Run 페이지의 설정을 따름)
if "selected_exp" not in st.session_state or not st.session_state.selected_exp:
    st.warning("⚠️ 선택된 실험 스크립트가 없습니다. 'Experiment Run' 페이지에서 먼저 스크립트를 선택해주세요.")
    st.stop()

script_name = st.session_state.selected_exp
st.info(f"📂 실행될 실험 스크립트: **{script_name}**  \n*(변경하려면 'Experiment Run' 페이지에서 재선택하세요)*")


# ----------------------
# Grid Search 실행
# ----------------------
if run_clicked and not st.session_state.grid_running:
    st.session_state.grid_running = True
    st.session_state.grid_current = 0
    st.session_state.grid_total = total_combos
    st.session_state.grid_output_lines = []
    st.session_state.grid_stop_requested = False
    st.session_state.grid_completed_logs = []
    st.session_state._grid_combos = grid
    st.session_state._grid_script = script_name
    st.session_state._grid_save_dir = save_log_dir
    st.rerun()

if stop_clicked and st.session_state.grid_running:
    st.session_state.grid_stop_requested = True
    if st.session_state.grid_process:
        st.session_state.grid_process.terminate()
    st.session_state.grid_running = False
    st.warning("⛔ Grid Search가 중단되었습니다.")


# ----------------------
# Grid Search 진행 처리
# ----------------------
if st.session_state.grid_running:
    combos = st.session_state.get("_grid_combos", [])
    current_idx = st.session_state.grid_current
    total = st.session_state.grid_total

    # 프로그레스 바
    progress = st.progress(current_idx / max(total, 1))
    status_text = st.empty()
    status_text.markdown(f"**진행: {current_idx} / {total}**")

    # 현재 프로세스 체크
    proc = st.session_state.grid_process

    if proc is not None:
        # 실행 중인 프로세스 확인
        if proc.poll() is None:
            # 아직 실행 중
            pass
        else:
            # 완료됨 → 다음으로
            token = st.session_state.get("notion_token", "")
            db_id = st.session_state.get("notion_db_id", "")
            tested = st.session_state.get("notion_tested", False)

            if token and db_id and tested and st.session_state.grid_completed_logs:
                try:
                    # 방금 끝난 로그 파싱 및 자동 기록
                    completed_log_path = st.session_state.grid_completed_logs[-1]
                    completed_log_name = os.path.basename(completed_log_path).replace(".log", "")
                    
                    hp, metrics = parse_log(completed_log_path)
                    
                    key_mapping = {
                        "timestamp": "0_timestamp",
                        "batch_size": "1_batch_size",
                        "epochs": "2_epochs",
                        "lr": "3_lr",            
                        "accuracy": "4_accuracy",            
                        "loss": "5_loss"
                    }
                    
                    edited_data = {}
                    for k, v in hp.items():
                        new_key = key_mapping.get(k.lower(), k)
                        edited_data[new_key] = v
                        
                    for k, v in metrics.items():
                        if k.lower() != "epoch":
                            new_key = key_mapping.get(k.lower(), k)
                            edited_data[new_key] = v
                            
                    auto_log(completed_log_name, edited_data, token, db_id)
                    st.toast(f"✅ {completed_log_name} Notion 로깅 완료!")
                except Exception as e:
                    st.toast(f"❌ {completed_log_name} Notion 로깅 실패: {e}")

            st.session_state.grid_current += 1
            st.session_state.grid_process = None
            current_idx = st.session_state.grid_current
            progress.progress(current_idx / max(total, 1))
            status_text.markdown(f"**진행: {current_idx} / {total}**")

    # 다음 실험 시작
    if st.session_state.grid_process is None and current_idx < total:
        if not st.session_state.grid_stop_requested:
            combo = combos[current_idx]
            st.info(f"🔄 실행 중 [{current_idx + 1}/{total}]: {combo}")

            workspace = st.session_state.get("workspace", ".")
            process, log_path, log_file = run_experiment(
                script_path=f"experiments/{st.session_state._grid_script}",
                log_dir=st.session_state._grid_save_dir,
                workspace=workspace,
                extra_args=combo
            )

            st.session_state.grid_process = process
            st.session_state.grid_completed_logs.append(log_path)

            # 출력 수집 스레드
            t = threading.Thread(
                target=collect_output,
                args=(process, log_file, st.session_state.grid_output_lines),
                daemon=True
            )
            t.start()

    elif current_idx >= total:
        st.session_state.grid_running = False
        st.session_state.grid_process = None
        st.success(f"✅ Grid Search 완료! ({total}개 실험)")
        st.balloons()

    # 터미널 출력
    st.subheader("📟 Terminal Output")
    if st.session_state.grid_output_lines:
        terminal_text = "\n".join(st.session_state.grid_output_lines[-200:])
        st.code(terminal_text, language="text")
    else:
        st.code("(대기 중...)", language="text")

    # 자동 새로고침
    if st.session_state.grid_running:
        time.sleep(1)
        st.rerun()

# ----------------------
# Notion 로깅
# ----------------------
if notion_clicked:
    token = st.session_state.get("notion_token", "")
    db_id = st.session_state.get("notion_db_id", "")
    tested = st.session_state.get("notion_tested", False)

    if not token or not db_id or not tested:
        st.error("❌ 먼저 Home 페이지에서 Notion API 연결 테스트를 완료해주세요.")
    else:
        # 단일값으로 편집된 파라미터 수집 및 이름 변환 (flet.py 로직 동일적용)
        key_mapping = {
            "timestamp": "0_timestamp",
            "batch_size": "1_batch_size",
            "epochs": "2_epochs",
            "lr": "3_lr",            
            "accuracy": "4_accuracy",            
            "loss": "5_loss"
        }

        edited_data = {}
        for k, config in params_config.items():
            if config["mode"] == "single":
                new_key = key_mapping.get(k.lower(), k)
                edited_data[new_key] = config["value"]
                
        # 메트릭 붙이기 (epoch는 제외)
        for k, v in latest_metrics.items():
            if k.lower() != "epoch":
                new_key = key_mapping.get(k.lower(), k)
                edited_data[new_key] = v

        with st.spinner("Notion에 기록 중..."):
            try:
                auto_log(
                    selected_log.replace(".log", ""),
                    edited_data,
                    token,
                    db_id
                )
                st.success("✅ Notion에 기록 완료!")
            except Exception as e:
                st.error(f"❌ Notion 기록 실패: {e}")