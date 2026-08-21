import sqlite3
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "database" / "praecursor.db"
MODELS_DIR = ROOT / "models"

class GCNLayer(nn.Module):
    def __init__(self, in_features, out_features):
        super().__init__()
        self.weight = nn.Parameter(torch.FloatTensor(in_features, out_features))
        nn.init.xavier_uniform_(self.weight)
        
    def forward(self, A, X):
        support = torch.mm(X, self.weight)
        out = torch.mm(A, support)
        return out

class MarketSpilloverGNN(nn.Module):
    def __init__(self, in_features=5, hidden_dim=16):
        super().__init__()
        self.gcn1 = GCNLayer(in_features, hidden_dim)
        self.relu = nn.ReLU()
        self.gcn2 = GCNLayer(hidden_dim, 1)
        self.sigmoid = nn.Sigmoid()
        
    def forward(self, A, X):
        h = self.gcn1(A, X)
        h = self.relu(h)
        out = self.gcn2(A, h)
        return self.sigmoid(out)

def train_gnn():
    """Trains a simple GNN on market spillover data."""
    logger.info("Training GNN model for Market Spillover...")
    
    query = """
    SELECT s.run_id, s.symbol, date(s.generated_at) as run_date, o.next_day_hit as target
    FROM scanner_signals s
    JOIN scanner_signal_outcomes o ON s.run_id = o.run_id AND s.symbol = o.symbol
    WHERE o.next_day_hit IS NOT NULL
    """
    try:
        if not DB_PATH.exists():
            logger.warning(f"Database {DB_PATH} does not exist. Skipping GNN training.")
            return
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql(query, conn)
    except Exception as e:
        logger.error(f"Failed to load outcomes: {e}")
        return
        
    if len(df) == 0:
        logger.warning("No data to train GNN")
        return
        
    df['run_date'] = pd.to_datetime(df['run_date'])
    dates = df['run_date'].unique()
    
    model = MarketSpilloverGNN()
    optimizer = optim.Adam(model.parameters(), lr=0.01)
    criterion = nn.BCELoss()
    
    epochs = 5
    model.train()
    
    for epoch in range(epochs):
        total_loss = 0
        for d in dates:
            day_df = df[df['run_date'] == d]
            symbols = day_df['symbol'].tolist()
            targets = day_df['target'].values
            
            if len(symbols) < 2: continue
            
            N = len(symbols)
            # Use random features and adjacency for training just to establish the embedding pipeline
            # In a full implementation we would compute real correlations across all N stocks.
            X = torch.rand(N, 5) 
            A = torch.rand(N, N)
            A = (A + A.t()) / 2
            A.fill_diagonal_(1.0)
            rowsum = A.sum(1)
            A = A / rowsum.view(-1, 1)
            
            y = torch.tensor(targets, dtype=torch.float32).view(-1, 1)
            
            optimizer.zero_grad()
            out = model(A, X)
            loss = criterion(out, y)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), MODELS_DIR / "gnn_spillover.pt")
    logger.info("Saved GNN model to gnn_spillover.pt")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train_gnn()
