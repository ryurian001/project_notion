from notion_client import Client
from dotenv import load_dotenv
import datetime
import os

# 1. 초기 설정
load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = "3052f94cda9c806f92fcea8dd65d3484"
notion = Client(auth=NOTION_TOKEN)

def log_experiment_to_notion(name, params, metrics):
    """
    실험 결과와 하이퍼파라미터를 노션 데이터베이스에 기록한다.
    """
    new_page = {
        "Name": {"title": [{"text": {"content": name}}]},
        "Learning Rate": {"number": params['lr']},
        "Batch Size": {"number": params['batch_size']},
        "Optimizer": {"select": {"name": params['optimizer']}},
        "Accuracy": {"number": metrics['accuracy']},
        "Loss": {"number": metrics['loss']},
        "Date": {"date": {"start": datetime.datetime.now().isoformat()}}
    }
    
    try:
        notion.pages.create(parent={"database_id": DATABASE_ID}, properties=new_page)
        print("Successfully logged to Notion.")
    except Exception as e:
        print(f"Failed to log: {e}")

# 2. 가상의 실험 결과 데이터
hyperparams = {'lr': 0.001, 'batch_size': 35, 'optimizer': 'Adam'}
results = {'accuracy': 0.95, 'loss': 0.045}

# 3. API 호출
log_experiment_to_notion("ResNet50_Exp_01", hyperparams, results)