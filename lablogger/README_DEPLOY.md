# Lablogger 패키지 배포 가이드

## 1. 사전 준비

### PyPI 계정 생성
- [PyPI 공식 사이트](https://pypi.org)에서 계정 생성
- 이메일 인증 완료

### 필요 패키지 설치
```bash
pip install build twine
```

## 2. 배포 준비

### setup.py 수정
[setup.py](../setup.py) 파일에서 다음 정보를 업데이트하세요:
- `author`: 개발자 이름
- `author_email`: 개발자 이메일
- `url`: GitHub 저장소 URL

### 버전 업데이트
- [__init__.py](__init__.py)의 `__version__` 업데이트
- [setup.py](../setup.py)의 `version` 업데이트

## 3. 배포 절차

### 1단계: 빌드
```bash
python -m build
```

### 2단계: PyPI 테스트 (선택사항이지만 권장)
```bash
# TestPyPI에 업로드 (첫 배포 시 권장)
twine upload --repository testpypi dist/*
```

### 3단계: PyPI에 배포
```bash
twine upload dist/*
```

## 4. 배포 후 확인

### 설치 테스트
```bash
pip install lablogger
```

### 사용 예제
```python
from lablogger import ExperimentLogger

logger = ExperimentLogger()
logger.log_config({"lr": 0.001, "batch_size": 32})
logger.log_metric(epoch=1, loss=0.5, accuracy=0.95)
logger.end()
```

## 문제 해결

### 인증 오류
- `~/.pypirc` 파일 확인
- 또는 배포 시마다 PyPI 토큰 입력

### 버전 충돌
- PyPI 웹사이트에서 기존 버전 확인
- setup.py의 버전을 더 높게 설정

## 추가 리소스
- [Python Packaging Guide](https://packaging.python.org/)
- [Twine 문서](https://twine.readthedocs.io/)
