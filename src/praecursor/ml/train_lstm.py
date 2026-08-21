import pandas as pd
import numpy as np
from pathlib import Path
import logging

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import TensorDataset, DataLoader
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

from praecursor.storage.price_cache import PriceCache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LSTMSequencePredictor(nn.Module):
    def __init__(self, input_size=5, hidden_size=32, num_layers=2):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden_size, 1)
        
    def forward(self, x):
        # x shape: (batch_size, sequence_length, input_size)
        out, _ = self.lstm(x)
        # We only care about the output at the last time step
        last_out = out[:, -1, :]
        return self.fc(last_out)

def prepare_sequence_data(df, cache, seq_length=20):
    X_seq = []
    y_seq = []
    
    # We define positive swing signals as 1, others as 0
    df["target"] = (df["swing_score"] >= 60).astype(int)
    
    # Balance dataset
    pos = df[df["target"] == 1]
    neg = df[df["target"] == 0]
    
    if len(pos) == 0:
        logger.error("No positive labels found for LSTM training.")
        return None, None
        
    # Undersample majority class to match minority class
    min_len = min(len(pos), len(neg))
    balanced_df = pd.concat([pos.sample(min_len, random_state=42), neg.sample(min_len, random_state=42)])
    balanced_df = balanced_df.sample(frac=1.0, random_state=42) # Shuffle
    
    logger.info(f"Extracting {seq_length}-day sequences for {len(balanced_df)} samples...")
    
    for _, row in balanced_df.iterrows():
        symbol = row["symbol"]
        signal_date = pd.to_datetime(row["signal_date"]).date()
        target = row["target"]
        
        # Load up to 60 days before to ensure we have enough trading days
        start_date = signal_date - pd.Timedelta(days=60)
        
        try:
            bars = cache.load(symbol, "yahoo_finance", start_date, signal_date)
            if len(bars) < seq_length:
                continue
                
            # Take the last `seq_length` bars up to the signal date
            seq_bars = bars[-seq_length:]
            
            # Features: Open, High, Low, Close, Volume (Normalized)
            closes = np.array([b.close for b in seq_bars])
            opens = np.array([b.open for b in seq_bars])
            highs = np.array([b.high for b in seq_bars])
            lows = np.array([b.low for b in seq_bars])
            volumes = np.array([b.volume for b in seq_bars])
            
            # Normalize everything relative to the max of the sequence to scale between 0 and 1
            max_p = max(highs.max(), 1e-5)
            max_v = max(volumes.max(), 1e-5)
            
            features = np.column_stack([
                opens / max_p,
                highs / max_p,
                lows / max_p,
                closes / max_p,
                volumes / max_v
            ])
            
            X_seq.append(features)
            y_seq.append(target)
            
        except Exception as e:
            continue
            
    if not X_seq:
        return None, None
        
    return np.array(X_seq), np.array(y_seq)

def train_lstm():
    if not HAS_TORCH:
        logger.error("PyTorch is not installed. Run `pip install torch` first.")
        return
        
    base_dir = Path(__file__).resolve().parents[3]
    csv_path = base_dir / "reports" / "backtest_signals.csv"
    
    if not csv_path.exists():
        logger.error(f"Cannot find {csv_path}. Run a backtest first.")
        return
        
    df = pd.read_csv(csv_path)
    db_path = base_dir / "database" / "praecursor.db"
    cache = PriceCache(database_path=str(db_path))
    
    X, y = prepare_sequence_data(df, cache, seq_length=20)
    
    if X is None or len(X) < 50:
        logger.error("Not enough sequence data to train LSTM.")
        return
        
    logger.info(f"Prepared tensor dataset with shape {X.shape}")
    
    # Convert to PyTorch tensors
    X_tensor = torch.tensor(X, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.float32).unsqueeze(1)
    
    dataset = TensorDataset(X_tensor, y_tensor)
    
    # 80/20 train/val split
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32)
    
    # Initialize model
    model = LSTMSequencePredictor(input_size=5, hidden_size=64, num_layers=2)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    
    epochs = 20
    best_val_loss = float('inf')
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for batch_X, batch_y in train_loader:
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * batch_X.size(0)
            
        train_loss /= len(train_loader.dataset)
        
        model.eval()
        val_loss = 0
        correct = 0
        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                val_loss += loss.item() * batch_X.size(0)
                
                preds = torch.sigmoid(outputs) >= 0.5
                correct += (preds == batch_y).sum().item()
                
        val_loss /= len(val_loader.dataset)
        accuracy = correct / len(val_loader.dataset)
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            # Save best model
            model_path = base_dir / "models" / "lstm_swing.pt"
            model_path.parent.mkdir(exist_ok=True)
            torch.save(model.state_dict(), str(model_path))
            
        if (epoch + 1) % 5 == 0:
            logger.info(f"Epoch {epoch+1}/{epochs} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {accuracy:.4f}")
            
    logger.info(f"PyTorch LSTM saved to {base_dir / 'models' / 'lstm_swing.pt'}")

if __name__ == "__main__":
    train_lstm()
