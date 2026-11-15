"""Golden G1 (Bước 5a): scan_and_route_state_proposals xuyên suốt, gồm toàn bộ khối sizing nằm inline.

Đóng băng: kết quả, THỨ TỰ và tham số các lời gọi (get_rates, get_tick, issue_direct_warrant, verify_order_clearance,
normalize_lot, create_order, open_market_order, revoke), cùng log. Chỉ dùng test double; không gửi lệnh thật.
Cố định: đồng hồ (datetime.now), time.time, np.random.normal, MetaTrader5.*, hub, mgr, ML, risk desk.
Sinh fixture từ mã TRƯỚC khi chuyển:  GENERATE_GOLDEN=1 python -m pytest us_federation_quant/tests/test_golden_scan_pipeline.py
"""
import json
import logging
import os
from datetime import datetime as _real_dt, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import MetaTrader5 as _mt5
import numpy as np
import pandas as pd
import pytest

from us_federation_quant.Document.live_federation_runner import USFederationQuantRuntime as RT

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "scan_pipeline.json")
RUNNER = "us_federation_quant.Document.live_federation_runner"
L5 = "us_federation_quant.layers.l5_execution"
UTC = timezone.utc
WED_1530 = _real_dt(2026, 11, 11, 15, 30, tzinfo=UTC)


class _Cap(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.rows = []

    def emit(self, r):
        self.rows.append([r.levelname, r.getMessage()])


def _df(n=60, lo=1.10, hi=1.11, width=0.0010):
    close = np.linspace(lo, hi, n)
    return pd.DataFrame({"open": close, "high": close + width, "low": close - width, "close": close})


def _info(**kw):
    d = dict(trade_mode=_mt5.SYMBOL_TRADE_MODE_FULL, point=0.00001, digits=5, trade_stops_level=10, spread=15,
             trade_tick_size=0.00001, trade_tick_value=1.0, volume_min=0.01, volume_max=100.0, volume_step=0.01)
    d.update(kw)
    return SimpleNamespace(**d)


def _scan(*, when=WED_1530, asset="EURUSD", state_id="STATE_21", action="BUY", target_lots=0.10, forecast=12.0,
          buffered=False, valid=True, df="default", tick="default", existing_pos=(), all_positions=(),
          info="default", ml=None, risk_desk="pass", warrant_ok=True, exec_result="ok", exec_raises=None,
          symbol_state=None, pod_loss=None, equity=10_000.0, session_start=None, no_states=False,
          attrs=None, filters=None, deals_none=True, resolve=lambda s: s if s.endswith("m") else s + "m", normalize="round2"):
    r = RT(initial_capital_usd=9000.0)
    for k, v in (attrs or {}).items():
        setattr(r, k, v)
    if symbol_state:
        r.symbol_state = {k: dict(v) for k, v in symbol_state.items()}
    if session_start is not None:
        r.session_day = when.strftime("%Y-%m-%d")
        r.session_start_equity = session_start
    if pod_loss is not None:
        r.session_day = when.strftime("%Y-%m-%d")   # tránh bị xóa pod_session_pnl khi sang phiên mới
        r.session_start_equity = equity
        r.pod_session_pnl[state_id] = pod_loss

    pod = SimpleNamespace(state_id=state_id, state_name="Pod " + state_id, primary_asset=asset, timeframe="H1", magic=777)
    proposal = SimpleNamespace(is_buffered=buffered, action=action, is_valid=valid, target_lots=target_lots,
                               carver_forecast=forecast, rationale="why", raw_lots=target_lots)
    pod.generate_trade_proposal = MagicMock(return_value=proposal)

    events = []
    hub = MagicMock()
    hub.states_registry.get_all_active_states.return_value = [] if no_states else [pod]
    hub.fed.allocate_carver_state_quotas.return_value = {
        "quotas": {state_id: 1.0}, "cash_vol_targets": {state_id: 123.0}, "idm": 1.2, "policy": "EASING"}
    warrant = SimpleNamespace(warrant_id="W-1", revoke=MagicMock())
    warrant.revoke.side_effect = lambda **kw: events.append(["revoke", kw])
    hub.court.issue_direct_warrant.side_effect = lambda **kw: (events.append(["issue_warrant", kw]) or warrant)
    hub.court.verify_warrant.return_value = warrant_ok

    def _clear(order_lots, asset_notional):
        events.append(["clearance", {"order_lots": order_lots, "asset_notional": asset_notional}])
        if risk_desk == "raises":
            raise RuntimeError("risk desk veto")
        return order_lots * 0.5 if risk_desk == "half" else order_lots

    hub.central_risk_desk.verify_order_clearance.side_effect = _clear
    r.hub = hub

    mgr = MagicMock()
    mgr.resolve_symbol.side_effect = resolve
    mgr.is_market_open.return_value = True
    mgr.get_positions.side_effect = lambda magic=None, symbol=None: (
        [dict(p) for p in existing_pos] if (magic is not None or symbol is not None) else [dict(p) for p in all_positions])
    mgr.get_rates.side_effect = lambda sym, tf, count=100: (events.append(["get_rates", [sym, tf, count]]) or
                                                          (_df() if isinstance(df, str) else df))
    mgr.get_tick.side_effect = lambda sym: (events.append(["get_tick", sym]) or (
        {"ask": 1.1052, "bid": 1.1050} if tick == "default" else tick))
    mgr.normalize_lot.side_effect = lambda sym, lot: (events.append(["normalize_lot", [sym, lot]]) or
                                                      (round(lot, 2) if normalize == "round2" else normalize(lot)))
    order_state = MagicMock()
    order_state.transition_to.side_effect = lambda st, **kw: events.append(["transition", str(getattr(st, "name", st)), kw])
    mgr.state_machine.create_order.side_effect = lambda **kw: (events.append(["create_order", kw]) or order_state)

    def _open(**kw):
        events.append(["open_market_order", kw])
        if exec_raises:
            raise exec_raises
        return {"success": True, "ticket": 9001, "price": 1.1053} if exec_result == "ok" else exec_result

    mgr.open_market_order.side_effect = _open
    r.mt5_mgr = mgr

    if ml is None:
        r.ml_service = None
    else:
        svc = MagicMock()
        if ml == "raises":
            svc.predict_latest_bar.side_effect = RuntimeError("ml down")
        else:
            svc.predict_latest_bar.return_value = SimpleNamespace(**ml)
        r.ml_service = svc

    for name, val in (filters or {}).items():
        setattr(r, name, lambda *a, _v=val, **k: _v)

    class _FDT(_real_dt):
        @classmethod
        def now(cls, tz=None):
            return when

    cap = _Cap()
    lg = logging.getLogger("USFederationQuant")
    lg.addHandler(cap)
    old = lg.level
    lg.setLevel(logging.DEBUG)
    info_obj = _info() if info == "default" else info
    try:
        with patch(f"{RUNNER}.datetime", _FDT), patch("time.time", return_value=when.timestamp()), \
             patch("numpy.random.normal", side_effect=lambda *a, **k: np.zeros(a[2])), \
             patch("MetaTrader5.symbol_info", return_value=info_obj), \
             patch("MetaTrader5.history_deals_get", return_value=None if deals_none else ()), \
             patch("MetaTrader5.copy_rates_from_pos", return_value=None), \
             patch(f"{L5}.generate_client_order_id", lambda sid, act: f"CID-{sid}-{act}-0123456789ABCDEF0123456789"):
            res = r.scan_and_route_state_proposals(account_equity=equity)
    finally:
        lg.removeHandler(cap)
        lg.setLevel(old)
    return {"result": res, "events": events, "generate_calls": len(pod.generate_trade_proposal.call_args_list),
            "verify_warrant_calls": hub.court.verify_warrant.call_count, "logs": cap.rows}


IDX = dict(df=_df(60, 19900.0, 20000.0, 15.0), tick={"ask": 20010.0, "bid": 20000.0},
           info=_info(trade_tick_size=0.01, trade_tick_value=0.01, point=0.01, digits=2, spread=30))


def _current():
    o = {}
    fx = dict(asset="EURUSD")
    # ---------------- preamble (trả về sớm, không tới pod)
    o["pre_no_active_states"] = _scan(no_states=True)
    o["pre_monday_open_curfew"] = _scan(when=_real_dt(2026, 11, 9, 0, 30, tzinfo=UTC))
    o["pre_friday_lock_1930"] = _scan(when=_real_dt(2026, 11, 6, 19, 30, tzinfo=UTC))
    o["pre_weekend_curfew_saturday"] = _scan(when=_real_dt(2026, 11, 7, 12, 0, tzinfo=UTC))
    o["pre_toxic_hour_23"] = _scan(when=_real_dt(2026, 11, 11, 23, 10, tzinfo=UTC))
    o["pre_account_drawdown_breaker"] = _scan(equity=9_700.0, session_start=10_000.0)
    o["pre_pod_loss_breaker"] = _scan(pod_loss=-200.0)
    # ---------------- bộ lọc trước sizing
    o["f_eliminated_pod"] = _scan(state_id="STATE_01")
    o["f_hk50_skipped"] = _scan(asset="HK50")
    o["f_blacklist_equity"] = _scan(asset="BAC")
    o["f_market_closed"] = _scan(attrs=None, info=_info(trade_mode=3))
    o["f_gbp_cluster_cap"] = _scan(asset="GBPUSD", all_positions=[{"symbol": "GBPUSDm", "ticket": 1, "type": "BUY", "volume": 0.1},
                                                              {"symbol": "EURGBPm", "ticket": 2, "type": "SELL", "volume": 0.1}])
    o["f_index_outside_session"] = _scan(asset="USTEC", when=_real_dt(2026, 11, 11, 12, 0, tzinfo=UTC))
    o["f_index_nyse_blackout_1430"] = _scan(asset="USTEC", when=_real_dt(2026, 11, 11, 14, 30, tzinfo=UTC))
    o["f_equity_opening_bell"] = _scan(asset="AAPL", when=_real_dt(2026, 11, 11, 13, 40, tzinfo=UTC))
    o["f_df_too_short"] = _scan(df=_df(10))
    o["f_df_none"] = _scan(df=None)
    o["f_buffered"] = _scan(buffered=True)
    o["f_hold_action"] = _scan(action="HOLD")
    o["f_invalid_proposal"] = _scan(valid=False)
    o["f_zero_target_lots"] = _scan(target_lots=0.0)
    o["f_existing_position_skips"] = _scan(existing_pos=[{"volume": 0.1, "type": "BUY", "ticket": 5}])
    o["f_cooldown_veto"] = _scan(symbol_state={"EURUSD": {"last_exit_ts": WED_1530.timestamp() - 100}})
    o["f_equity_low_conviction"] = _scan(asset="AAPL", forecast=5.0)
    o["f_equity_trend_filter_buy"] = _scan(asset="AAPL", forecast=15.0, df=_df(lo=1.11, hi=1.10))
    o["f_eurgbp_filter_denies"] = _scan(asset="EURGBP", filters={"check_eurgbp_d1_ema200_filter": False})
    o["f_jpy_filter_denies"] = _scan(asset="USDJPY", filters={"check_jpy_macro_trend_filter": False})
    o["f_index_cap_reached"] = _scan(asset="US30", when=WED_1530, all_positions=[
        {"symbol": "US30m", "ticket": 3, "type": "BUY", "volume": 0.5}], **IDX)
    o["f_scotus_veto"] = _scan(warrant_ok=False)
    o["f_dedup_same_direction"] = _scan(all_positions=[{"symbol": "EURUSDm", "ticket": 4, "type": "BUY", "volume": 0.1}])
    o["f_factor_limit_usd"] = _scan(all_positions=[{"symbol": "GBPUSDm", "ticket": 6, "type": "SELL", "volume": 0.1},
                                                  {"symbol": "USDCADm", "ticket": 7, "type": "SELL", "volume": 0.1}])
    o["f_ml_veto"] = _scan(ml=dict(is_approved=False, win_probability=0.3, prob_threshold=0.48, kelly_multiplier=0.5))
    # ---------------- sizing + vào lệnh
    o["s_fx_buy_tick_ask"] = _scan()
    o["s_fx_sell_tick_bid"] = _scan(action="SELL")
    o["s_price_from_close_no_tick"] = _scan(tick=None)
    o["s_price_from_close_zero_ask"] = _scan(tick={"ask": 0, "bid": 1.1})
    o["s_atr_zero_fallback_pct"] = _scan(df=_df(15, 1.1, 1.1, 0.0))
    o["s_atr_nan_short_window"] = _scan(df=_df(15))
    o["s_index_ustec_cap60_clip"] = _scan(asset="USTEC", when=WED_1530, **IDX)
    o["s_elite_booster_gbpusd"] = _scan(asset="GBPUSD")
    o["s_elite_us30_is_index_no_booster"] = _scan(asset="US30", **IDX)
    o["s_ml_scale_up_clamped_1p25"] = _scan(ml=dict(is_approved=True, win_probability=0.7, prob_threshold=0.48, kelly_multiplier=1.5))
    o["s_ml_scale_down_clamped_0p70"] = _scan(ml=dict(is_approved=True, win_probability=0.6, prob_threshold=0.48, kelly_multiplier=0.4))
    o["s_ml_kelly_zero_no_scale"] = _scan(ml=dict(is_approved=True, win_probability=0.6, prob_threshold=0.48, kelly_multiplier=0.0))
    o["s_ml_exception_skipped"] = _scan(ml="raises")
    o["s_risk_desk_scales_half"] = _scan(risk_desk="half")
    o["s_risk_desk_raises"] = _scan(risk_desk="raises")
    o["s_normalize_lot_changes"] = _scan(normalize=lambda lot: round(lot * 0.5, 2))
    o["s_sl_floor_150_points_wide_stops"] = _scan(info=_info(trade_stops_level=500, spread=100))
    o["s_attrs_override_caps"] = _scan(attrs={"MAX_HARD_RISK_USD": 5.0})
    o["s_custom_digits_info"] = _scan(info=_info(digits=3, point=0.001, trade_tick_size=0.001))
    o["e_broker_rejects"] = _scan(exec_result={"success": False, "error": "No money", "retcode": 10019})
    o["e_broker_market_closed_10018"] = _scan(exec_result={"success": False, "error": "closed", "retcode": 10018})
    o["e_open_order_raises"] = _scan(exec_raises=RuntimeError("ipc down"))
    return o


def test_generate_or_match_golden():
    current = json.loads(json.dumps(_current(), sort_keys=True, default=str))
    if os.environ.get("GENERATE_GOLDEN") == "1":
        os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
        json.dump(current, open(GOLDEN, "w", encoding="utf-8"), indent=1, ensure_ascii=False, sort_keys=True)
        pytest.skip("golden đã được sinh")
    golden = json.load(open(GOLDEN, encoding="utf-8"))
    for k in golden:
        assert current[k] == golden[k], f"golden lệch ở: {k}"
    assert set(current) == set(golden)
