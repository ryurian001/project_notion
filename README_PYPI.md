# Lablogger

ML/DL 프로젝트를 위한 간단한 실험 로거입니다. JSON 포맷으로 하이퍼파라미터, 메트릭, 이벤트를 기록합니다.

## 설치

```bash
pip install lablogger
```

## 기본 사용법

```python
from lablogger import ExperimentLogger

# 로거 초기화
logger = ExperimentLogger()

# 하이퍼파라미터 기록
logger.log_config({
    "learning_rate": 0.001,
    "batch_size": 32,
    "epochs": 100
})

# 메트릭 기록
logger.log_metric(epoch=1, loss=0.5, accuracy=0.95)
logger.log_metric(epoch=2, loss=0.3, accuracy=0.97)

# 커스텀 이벤트 기록
logger.log_event("model_checkpoint_saved")

# 실험 종료
logger.end()
```

## 로그 포맷

모든 로그는 JSON 형식으로 기록됩니다:

```json
{"type": "hyperparam", "key": "learning_rate", "value": 0.001}
{"type": "metric", "timestamp": "2026-02-24T10:30:00.123456", "epoch": 1, "loss": 0.5, "accuracy": 0.95}
{"type": "event", "message": "experiment_start", "timestamp": "2026-02-24T10:30:00.123456"}
```

## 기능

- **하이퍼파라미터 기록**: `log_config(config_dict)` - 실험 설정 저장
- **메트릭 기록**: `log_metric(**kwargs)` - 학습 메트릭 저장
- **이벤트 기록**: `log_event(message)` - 커스텀 이벤트 저장
- **타임스탐프**: 자동으로 메트릭과 이벤트에 타임스탐프 추가
- **JSON 출력**: 구조화된 로깅으로 분석 및 파싱 용이

## 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 참고

## 기여

버그 리포트 및 기능 요청은 GitHub 이슈를 통해 제출해주세요.
