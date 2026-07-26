import csv
import random
from datetime import datetime, timedelta

stocks = [
    ("COMI", "Commercial International Bank", 100.0),
    ("HRHO", "EFG Holding", 20.0),
    ("SWDY", "Elsewedy Electric", 27.0),
    ("ETEL", "Telecom Egypt", 33.0),
]

days = 60

with open("data/raw/sample.csv", "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)

    writer.writerow([
        "Symbol",
        "Company",
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ])

    start = datetime(2026, 5, 1)

    for symbol, company, price in stocks:
        current = price

        for i in range(days):
            date = start + timedelta(days=i)

            # Skip weekends
            if date.weekday() >= 5:
                continue

            open_price = current
            close_price = round(open_price * (1 + random.uniform(-0.02, 0.02)), 2)
            high = round(max(open_price, close_price) * (1 + random.uniform(0, 0.01)), 2)
            low = round(min(open_price, close_price) * (1 - random.uniform(0, 0.01)), 2)
            volume = random.randint(1_000_000, 5_000_000)

            writer.writerow([
                symbol,
                company,
                date.strftime("%Y-%m-%d"),
                round(open_price, 2),
                high,
                low,
                close_price,
                volume,
            ])

            current = close_price

print("sample.csv generated successfully.")