import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
from torchvision import datasets, transforms
from torch.utils.data import DataLoader, random_split
from tqdm.auto import tqdm
import random
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ntrain import Experiment

def set_seed(seed=777):
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
set_seed()

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(device)

# 1. 데이터셋 다운로드
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2470, 0.2435, 0.2616)),
])
train_ds = datasets.CIFAR10(root="./data", train=True, download=True, transform=transform)
test_ds = datasets.CIFAR10(root="./data", train=False, download=True, transform=transform)

# 2. 데이터 분할 (학습 80%, 검증 20%)
train_size = int(0.8 * len(train_ds))
val_size = len(train_ds) - train_size
train_ds, val_ds = random_split(train_ds, [train_size, val_size])

# 3. 데이터 로더 생성
# 🔹 ntrain으로 하이퍼파라미터 정의
exp = Experiment(
    name="ResNet18_CIFAR10",
    batch_size=128,
    epochs=1,
    lr=0.001,
    optimizer="Adam",
    weight_decay=1e-4,
)
print(exp)

batch_size = exp.hyperparams["batch_size"]
train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

# 4. 모델 정의 (ResNet18)
model = torchvision.models.resnet18(weights=torchvision.models.ResNet18_Weights.DEFAULT)
model.fc = nn.Linear(model.fc.in_features, 10)
model = model.to(device)

# 5. 손실 함수 및 옵티마이저
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=exp.hyperparams["lr"], weight_decay=exp.hyperparams["weight_decay"])

# 6. 학습 루프
num_epochs = exp.hyperparams["epochs"]

for epoch in range(num_epochs):
    model.train()
    train_loss = 0.0
    train_correct = 0
    train_total = 0
    
    progress_bar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{num_epochs}", leave=False)
    
    for images, labels in progress_bar:
        images, labels = images.to(device), labels.to(device)
        
        # 순전파
        outputs = model(images)
        loss = criterion(outputs, labels)
        
        # 역전파 및 최적화
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        train_loss += loss.item() * images.size(0)
        _, predicted = torch.max(outputs.data, 1)
        train_total += labels.size(0)
        train_correct += (predicted == labels).sum().item()
        
        progress_bar.set_postfix({
            'loss': f'{loss.item():.4f}',
            'acc': f'{100 * train_correct / train_total:.2f}%'
        })
    
    avg_train_loss = train_loss / train_total
    train_acc = 100 * train_correct / train_total
    
    # 검증
    model.eval()
    val_loss = 0.0
    val_correct = 0
    val_total = 0
    
    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)
            
            val_loss += loss.item() * images.size(0)
            _, predicted = torch.max(outputs.data, 1)
            val_total += labels.size(0)
            val_correct += (predicted == labels).sum().item()
    
    avg_val_loss = val_loss / val_total
    val_acc = 100 * val_correct / val_total
    
    print(f"Epoch {epoch+1}: Train Loss: {avg_train_loss:.4f}, Train Acc: {train_acc:.2f}%, "
          f"Val Loss: {avg_val_loss:.4f}, Val Acc: {val_acc:.2f}%")

# 7. 테스트
model.eval()
test_loss = 0.0
test_correct = 0
test_total = 0

with torch.no_grad():
    for images, labels in test_loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        loss = criterion(outputs, labels)
        
        test_loss += loss.item() * images.size(0)
        _, predicted = torch.max(outputs.data, 1)
        test_total += labels.size(0)
        test_correct += (predicted == labels).sum().item()

avg_test_loss = test_loss / test_total
test_acc = 100 * test_correct / test_total

print(f"\nTest Accuracy: {test_acc:.2f}%")

# 8. 메트릭 기록 + 저장
exp.log_metrics(
    test_accuracy=round(test_acc, 2),
    test_loss=round(avg_test_loss, 4),
)
exp.save()

# 9. 모델 저장
torch.save(model.state_dict(), "resnet18_cifar10.pth")
print("Model saved to resnet18_cifar10.pth")