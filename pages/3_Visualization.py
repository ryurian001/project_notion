import streamlit as st
import os
import json
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

st.title("📊 Experiment Visualization")


# ----------------------------
# 로그 폴더 선택
# ----------------------------
st.subheader("📂 로그 폴더 선택")

default_log_dir = "logs"

# 프로젝트에 있는 폴더 목록 자동 탐색
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
all_dirs = []
for item in os.listdir(project_root):
    full_path = os.path.join(project_root, item)
    if os.path.isdir(full_path) and not item.startswith(".") and item not in ("__pycache__", "core", "experiments", "data", "ntrain"):
        all_dirs.append(item)

if not all_dirs:
    all_dirs = [default_log_dir]

selected_dir = st.selectbox("폴더 선택", sorted(all_dirs), index=0)
log_dir = os.path.join(project_root, selected_dir)

if not os.path.exists(log_dir):
    st.error(f"폴더가 존재하지 않습니다: {log_dir}")
    st.stop()


# ----------------------------
# 로그 파일 목록 + 다중 선택
# ----------------------------
log_files = sorted(
    [f for f in os.listdir(log_dir) if f.endswith(".log")],
    reverse=True
)

if not log_files:
    st.warning("로그 파일이 없습니다.")
    st.stop()

st.subheader("📋 로그 파일 선택 (다중 선택)")

selected_logs = st.multiselect(
    "비교할 로그 파일을 선택하세요",
    log_files,
    default=[log_files[0]] if log_files else []
)

if not selected_logs:
    st.info("하나 이상의 로그 파일을 선택해주세요.")
    st.stop()


# ----------------------------
# 로그 파싱 함수
# ----------------------------
def parse_log_full(path):
    """로그 파일에서 하이퍼파라미터와 메트릭 추출"""
    hyperparams = {}
    metrics = []
    start_time = None
    end_time = None

    with open(path, "r") as f:
        for line in f:
            json_start = line.find("{")
            if json_start == -1:
                continue

            json_part = line[json_start:].strip()
            try:
                data = json.loads(json_part)
            except:
                continue

            if data.get("type") == "event":
                if data.get("message") == "experiment_start":
                    start_time = datetime.fromisoformat(data["timestamp"])
                if data.get("message") == "experiment_end":
                    end_time = datetime.fromisoformat(data["timestamp"])

            if data.get("type") == "hyperparam":
                hyperparams[data["key"]] = data["value"]

            if data.get("type") == "metric":
                metrics.append(data)

    return hyperparams, metrics, start_time, end_time


# ----------------------------
# 모든 선택된 로그 파싱
# ----------------------------
all_data = {}
for log_name in selected_logs:
    path = os.path.join(log_dir, log_name)
    hyperparams, metrics, start_time, end_time = parse_log_full(path)
    all_data[log_name] = {
        "hyperparams": hyperparams,
        "metrics": metrics,
        "start_time": start_time,
        "end_time": end_time
    }


# ----------------------------
# 색상 팔레트
# ----------------------------
COLORS = [
    "#636EFA", "#EF553B", "#00CC96", "#AB63FA",
    "#FFA15A", "#19D3F3", "#FF6692", "#B6E880",
    "#FF97FF", "#FECB52"
]


# ----------------------------
# 하이퍼파라미터 표시 영역
# ----------------------------
st.subheader("⚙️ Hyperparameters")

if "selected_log_detail" not in st.session_state:
    st.session_state.selected_log_detail = None

# 선택된 로그의 하이퍼파라미터 보기 드롭다운
detail_log = st.selectbox(
    "🔍 하이퍼파라미터 상세 보기",
    ["(선택하세요)"] + selected_logs,
    key="hp_detail_select"
)

if detail_log != "(선택하세요)" and detail_log in all_data:
    hp = all_data[detail_log]["hyperparams"]
    if hp:
        cols = st.columns(min(len(hp), 4))
        for i, (k, v) in enumerate(hp.items()):
            with cols[i % len(cols)]:
                st.metric(label=k, value=v)
    else:
        st.info("하이퍼파라미터 없음")

st.markdown("---")


# ----------------------------
# Accuracy 차트 (Plotly)
# ----------------------------
st.subheader("📈 Accuracy Comparison")

fig_acc = go.Figure()

for i, log_name in enumerate(selected_logs):
    info = all_data[log_name]
    metrics = info["metrics"]
    hp = info["hyperparams"]

    if not metrics:
        continue

    df = pd.DataFrame(metrics)

    if "epoch" not in df.columns or "accuracy" not in df.columns:
        continue

    df = df.sort_values("epoch")

    # 하이퍼파라미터를 hover 텍스트로 구성
    hp_text = "<br>".join([f"{k}: {v}" for k, v in hp.items()])
    hover_template = (
        f"<b>{log_name}</b><br>"
        f"Epoch: %{{x}}<br>"
        f"Accuracy: %{{y:.4f}}<br>"
        f"<br><b>Hyperparameters:</b><br>"
        f"{hp_text}"
        f"<extra></extra>"
    )

    color = COLORS[i % len(COLORS)]

    fig_acc.add_trace(go.Scatter(
        x=df["epoch"],
        y=df["accuracy"],
        mode="lines+markers",
        name=log_name,
        line=dict(color=color, width=2),
        marker=dict(size=6),
        hovertemplate=hover_template,
        customdata=[hp] * len(df)
    ))

fig_acc.update_layout(
    xaxis_title="Epoch",
    yaxis_title="Accuracy",
    hovermode="closest",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=500,
    template="plotly_dark"
)

st.plotly_chart(fig_acc, width="stretch")


# ----------------------------
# Loss 차트 (Plotly)
# ----------------------------
st.subheader("📉 Loss Comparison")

fig_loss = go.Figure()

for i, log_name in enumerate(selected_logs):
    info = all_data[log_name]
    metrics = info["metrics"]
    hp = info["hyperparams"]

    if not metrics:
        continue

    df = pd.DataFrame(metrics)

    if "epoch" not in df.columns or "loss" not in df.columns:
        continue

    df = df.sort_values("epoch")

    hp_text = "<br>".join([f"{k}: {v}" for k, v in hp.items()])
    hover_template = (
        f"<b>{log_name}</b><br>"
        f"Epoch: %{{x}}<br>"
        f"Loss: %{{y:.4f}}<br>"
        f"<br><b>Hyperparameters:</b><br>"
        f"{hp_text}"
        f"<extra></extra>"
    )

    color = COLORS[i % len(COLORS)]

    fig_loss.add_trace(go.Scatter(
        x=df["epoch"],
        y=df["loss"],
        mode="lines+markers",
        name=log_name,
        line=dict(color=color, width=2),
        marker=dict(size=6),
        hovertemplate=hover_template,
    ))

fig_loss.update_layout(
    xaxis_title="Epoch",
    yaxis_title="Loss",
    hovermode="closest",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=500,
    template="plotly_dark"
)

st.plotly_chart(fig_loss, width="stretch")


# ----------------------------
# Best Accuracy 비교 테이블
# ----------------------------
st.subheader("🏆 Best Accuracy 비교")

comparison_data = []

for log_name in selected_logs:
    info = all_data[log_name]
    metrics = info["metrics"]
    hp = info["hyperparams"]

    if not metrics:
        continue

    df = pd.DataFrame(metrics)

    if "accuracy" not in df.columns:
        continue

    best_acc = df["accuracy"].max()
    best_epoch = int(df.loc[df["accuracy"].idxmax()]["epoch"]) if "epoch" in df.columns else "N/A"

    row = {
        "Log": log_name,
        "Best Accuracy": f"{best_acc:.4f}",
        "Best Epoch": best_epoch,
    }
    # 주요 하이퍼파라미터 추가
    for k, v in hp.items():
        if k.lower() not in ("epochs", "epoch"):
            row[k] = v

    comparison_data.append(row)

if comparison_data:
    compare_df = pd.DataFrame(comparison_data)
    st.dataframe(compare_df, width="stretch")
else:
    st.info("비교할 데이터가 없습니다.")


# ----------------------------
# 학습 시간 비교
# ----------------------------
st.subheader("⏱ Training Time 비교")

time_data = []
for log_name in selected_logs:
    info = all_data[log_name]
    if info["start_time"] and info["end_time"]:
        duration = (info["end_time"] - info["start_time"]).total_seconds()
        time_data.append({"Log": log_name, "Duration (sec)": f"{duration:.2f}"})

if time_data:
    st.dataframe(pd.DataFrame(time_data), width="stretch")
else:
    st.info("학습 시간 정보가 없습니다.")