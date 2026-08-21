import pandas as pd
import numpy as np
from pathlib import Path
import logging
import math

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

class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=500):
        super().__init__()
        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))
        pe = torch.zeros(max_len, 1, d_model)
        pe[:, 0, 0::2] = torch.sin(position * div_term)
        pe[:, 0, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe)

    def forward(self, x):
        # x shape: (seq_len, batch_size, d_model)
        x = x + self.pe[:x.size(0)]
        return x

class TemporalTransformerPredictor(nn.Module):
    def __init__(self, input_size=5, d_model=64, nhead=4, num_layers=2, dropout=0.2):
        super().__init__()
        self.input_linear = nn.Linear(input_size, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        
        encoder_layers = nn.TransformerEncoderLayer(
            d_model=d_model, 
            nhead=nhead, 
            dim_feedforward=d_model * 4, 
            dropout=dropout,
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layers, num_layers)
        
        # Output layer processing the final sequence state
        self.fc = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, 1)
        )
        
    def forward(self, x):
        # x shape: (batch_size, seq_len, input_size)
        x = self.input_linear(x) # (batch_size, seq_len, d_model)
        
        # TransformerEncoder with batch_first=True expects (batch_size, seq_len, d_model)
        # But PositionalEncoding expects (seq_len, batch_size, d_model)
        x = x.transpose(0, 1)
        x = self.pos_encoder(x)
        x = x.transpose(0, 1)
        
        out = self.transformer_encoder(x)
        
        # Use the representation of the last time step for prediction
        last_out = out[:, -1, :]
        return self.fc(last_out)

def prepare_sequence_data(df, cache, seq_length=20):
    X_seq = []
    y_seq = []
    
    # Define positive swing signals as 1, others as 0
    if "swing_score" in df.columns:
        df["target"] = (df["swing_score"] >= 60).astype(int)
    elif "next_day_score" in df.columns:
        df["target"] = (df["next_day_score"] >= 60).astype(int)
    elif "Target" in df.columns:
        df["target"] = df["Target"]
    else:
        logger.error("No valid target column found for training.")
        return None, None
    
    # Balance dataset
    pos = df[df["target"] == 1]
    neg = df[df["target"] == 0]
    
    if len(pos) == 0:
        logger.error("No positive labels found for Transformer training.")
        return None, None
        
    min_len = min(len(pos), len(neg))
    balanced_df = pd.concat([pos.sample(min_len, random_state=42), neg.sample(min_len, random_state=42)])
    balanced_df = balanced_df.sample(frac=1.0, random_state=42) # Shuffle
    
    logger.info(f"Extracting {seq_length}-day sequences for {len(balanced_df)} samples...")
    
    for _, row in balanced_df.iterrows():
        symbol = row["symbol"]
        
        if "signal_date" in row:
            signal_date = pd.to_datetime(row["signal_date"]).date()
        elif "date" in row:
            signal_date = pd.to_datetime(row["date"]).date()
        else:
            continue
            
        target = row["target"]
        
        # Load up to 60 days before to ensure we have enough trading days
        start_date = signal_date - pd.Timedelta(days=60)
        
        try:
            bars = cache.load(symbol, "yahoo_finance", start_date, signal_date)
            if len(bars) < seq_length:
                continue
                
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

def train_tft():
    if not HAS_TORCH:
        logger.error("PyTorch is not installed. Run `pip install torch` first.")
        return
        
    base_dir = Path(__file__).resolve().parents[3]
    csv_path = base_dir / "reports" / "backtest_signals.csv"
    
    # Fallback to scanner_runs table if backtest_signals doesn't exist
    db_path = base_dir / "database" / "praecursor.db"
    cache = PriceCache(database_path=str(db_path))
    
    if csv_path.exists():
        df = pd.read_csv(csv_path)
    else:
        logger.info(f"Reading directly from SQLite outcomes since {csv_path} is missing.")
        import sqlite3
        conn = sqlite3.connect(db_path)
        df = pd.read_sql("SELECT s.symbol, s.date as signal_date, o.hit_target as target FROM scanner_signals s JOIN scanner_signal_outcomes o ON s.id = o.signal_id WHERE s.symbol NOT LIKE '%.CA'", conn)
        conn.close()
    
    if len(df) == 0:
        logger.error("No historical data to train on.")
        return
        
    X, y = prepare_sequence_data(df, cache, seq_length=20)
    
    if X is None or len(X) < 50:
        logger.error("Not enough sequence data to train Transformer.")
        return
        
    logger.info(f"Prepared tensor dataset with shape {X.shape}")
    
    X_tensor = torch.tensor(X, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.float32).unsqueeze(1)
    
    dataset = TensorDataset(X_tensor, y_tensor)
    
    # 80/20 train/val split
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32)
    
    model = TemporalTransformerPredictor(input_size=5, d_model=64, nhead=4, num_layers=2)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
    
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
            model_path = base_dir / "models" / "tft_swing.pt"
            model_path.parent.mkdir(exist_ok=True)
            torch.save(model.state_dict(), str(model_path))
            
        if (epoch + 1) % 5 == 0:
            logger.info(f"Epoch {epoch+1}/{epochs} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {accuracy:.4f}")
            
    logger.info(f"PyTorch Temporal Transformer saved to {base_dir / 'models' / 'tft_swing.pt'}")

if __name__ == "__main__":
    train_tft()
