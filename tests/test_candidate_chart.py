import json
import re
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from tools.chart_generator import capture_chart, generate_chart_html
from praecursor.notifications import bot_hub, telegram


def test_chart_uses_saved_levels_and_unrounded_candles():
    frame = pd.DataFrame([dict(trade_date=pd.Timestamp("2026-11-10"), open=.255, high=.261,
                               low=.254, close=.259, volume=3100)])
    company = "International Company for Financial Services & Digital Infrastructure"
    metadata = dict(company=company, latest_close=.259, next_day_target=.269, next_day_stop_loss=.244324,
                    next_day_reasons="Target placed at 0.27 and Stop Loss placed at 0.24",
                    candidate_rank=1, feature_session="2026-11-10", target_session="2026-11-11")
    html = generate_chart_html("ARAB", frame, metadata)
    data = json.loads(re.search(r'id="chart-data" type="application/json">(.*?)</script>', html)[1])
    assert data["bars"][0]["open"] == .255
    assert data["levels"] == [.259, .269, .244324]
    assert "<dd>0.2590</dd>" in html and "<dd>0.2443</dd>" in html
    assert "10 Nov 2026" in html and "11 Nov 2026" in html
    assert "Financial Services &amp; Digital Infrastructure</p>" in html
    assert "Reward / risk 0.68×" in html
    assert "Reward / risk" not in generate_chart_html("ARAB", frame, dict(metadata, next_day_stop_loss=.259))


def test_chart_capture_waits_for_the_canvas(tmp_path):
    page = Mock()
    page.locator.return_value.wait_for.side_effect = TimeoutError
    with pytest.raises(TimeoutError):
        capture_chart(page, tmp_path / "chart.html", tmp_path / "chart.png")
    page.locator.assert_called_once_with('canvas[data-rendered="true"]')
    page.screenshot.assert_not_called()


@pytest.mark.parametrize("rendered", [True, False])
def test_telegram_routes_use_renderer_even_with_legacy_png(tmp_path, monkeypatch, rendered):
    from tools import chart_generator

    directory = tmp_path / "reports" / "charts"
    directory.mkdir(parents=True)
    (directory / "EFIH_chart.png").write_bytes(b"old image")
    current = directory / "current.png"
    current.touch()
    render = Mock(return_value=current if rendered else None)
    monkeypatch.setattr(chart_generator, "render_chart_to_png", render)
    monkeypatch.setattr(telegram, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(bot_hub, "PROJECT_ROOT", tmp_path)
    client = Mock()
    client.send_photo.return_value = {"ok": True}
    pick = SimpleNamespace(symbol="EFIH", candidate_rank=1)
    result = SimpleNamespace(next_day_results=[pick])
    assert telegram.dispatch_candidate_charts(client, result, verbose=False, chat_id=1) == int(rendered)
    bot_hub.TelegramBotHub._send_symbol_chart(SimpleNamespace(client=client), 1, "efih")
    assert [call.args for call in render.call_args_list] == [("EFIH",), ("EFIH",)]
    assert [call.args[0] for call in client.send_photo.call_args_list] == ([current, current] if rendered else [])
