# Telegram Alerts

Praecursor-EGX can send scanner summaries to Telegram.

## Setup

Create a Telegram bot using BotFather, then get:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Save them locally in PowerShell:

```powershell
setx TELEGRAM_BOT_TOKEN "your-bot-token"
setx TELEGRAM_CHAT_ID "your-chat-id"
```

Close and reopen PowerShell.

Check:

```powershell
python -c "import os; print('OK' if os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID') else 'MISSING')"
```

## Send a test message

```powershell
python tools/send_telegram_report.py --message "Praecursor test"
```

## Send scanner summary

```powershell
python tools/send_telegram_report.py --run-scanner
```

## Dry run

Print message without sending:

```powershell
python tools/send_telegram_report.py --run-scanner --dry-run
```

## Send report files too

```powershell
python tools/send_telegram_report.py --run-scanner --send-files
```

Secrets are read from environment variables and are never stored in Git.
