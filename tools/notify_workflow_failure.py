"""Send one operational alert to the configured owner, never the subscriber list."""
import html
import json
import os
from urllib.request import Request, urlopen


def failure_message(name, url):
    return f"Praecursor automation failed: {html.escape(name)}\n<a href='{html.escape(url, quote=True)}'>Open run and logs</a>"


def main():
    token, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    if not token or not chat:
        raise SystemExit("Telegram Actions secrets are missing")
    body = json.dumps(dict(chat_id=chat, parse_mode="HTML", disable_web_page_preview=True,
                          text=failure_message(os.environ["FAILED_WORKFLOW"], os.environ["FAILED_RUN_URL"]))).encode()
    request = Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body,
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            if not json.load(response).get("ok"):
                raise ValueError("Rejected alert")
    except Exception:
        # Request exceptions can contain the credential-bearing URL.
        raise SystemExit("Telegram failure alert could not be delivered") from None
    print("Owner notified")


if __name__ == "__main__":
    main()
