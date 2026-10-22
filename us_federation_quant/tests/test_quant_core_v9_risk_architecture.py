import time
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from us_federation_quant.institutional_governance_rules import check_factor_limits
import importlib
_ks_mod = importlib.import_module("us_federation_quant.06_the_fourth_estate.federal_master_kill_switch")
FederalMasterKillSwitch = _ks_mod.FederalMasterKillSwitch
FederalCircuitBreakerActive = _ks_mod.FederalCircuitBreakerActive
from us_federation_quant.live_federation_runner import USFederationQuantRuntime


def test_check_factor_limits_jpy_cluster():
    """Test JPY cluster risk prevention (max 1 JPY position)."""
    # 0 JPY position -> Allow
    open_pos_0 = [{"symbol": "EURUSD", "profit": 10.0}]
    assert check_factor_limits("USDJPY", open_pos_0) is True

    # 1 JPY position -> Reject any new JPY
    open_pos_1 = [{"symbol": "USDJPY", "profit": -15.0}]
    assert check_factor_limits("EURJPY", open_pos_1) is False
    assert check_factor_limits("GBPJPY", open_pos_1) is False
    assert check_factor_limits("CADJPYm", open_pos_1) is False

    # Non-JPY pair should still pass
    assert check_factor_limits("EURGBP", open_pos_1) is True


def test_check_factor_limits_usd_cluster():
    """Test USD cluster risk prevention (max 2 USD positions)."""
    open_pos_1 = [{"symbol": "EURUSD", "profit": 5.0}]
    assert check_factor_limits("USDCAD", open_pos_1) is True

    # 2 USD positions -> Reject new USD
    open_pos_2 = [{"symbol": "EURUSD", "profit": 5.0}, {"symbol": "USDCAD", "profit": 12.0}]
    assert check_factor_limits("GBPUSD", open_pos_2) is False
    assert check_factor_limits("USDCHF", open_pos_2) is False

    # Non-USD pair should still pass
    assert check_factor_limits("EURGBP", open_pos_2) is True


def test_calculate_risk_adjusted_lot():
    """Test Volatility ATR Dollar Sizing formula and index capping."""
    runtime = USFederationQuantRuntime(initial_capital_usd=10_000.0)

    # Mock mt5.symbol_info for EURUSD
    mock_eurusd = MagicMock()
    mock_eurusd.trade_tick_value = 1.0
    mock_eurusd.trade_tick_size = 0.00001
    mock_eurusd.point = 0.00001
    mock_eurusd.volume_min = 0.01
    mock_eurusd.volume_max = 200.0
    mock_eurusd.volume_step = 0.01

    with patch("MetaTrader5.symbol_info", return_value=mock_eurusd):
        # sl_points = 300 (30 pips). Risk = $35.
        # Dollar risk per lot = 300 * 1.0 = $300.
        # Raw lot = 35 / 300 = 0.1166... -> rounded to 0.12
        lot = runtime.calculate_risk_adjusted_lot("EURUSD", sl_points=300.0, max_risk_usd=35.0)
        assert lot == 0.12

    # Mock mt5.symbol_info for USTEC (Index hard cap between 0.01 and 0.03)
    mock_ustec = MagicMock()
    mock_ustec.trade_tick_value = 0.01
    mock_ustec.trade_tick_size = 0.01
    mock_ustec.point = 0.01
    mock_ustec.volume_min = 0.01
    mock_ustec.volume_max = 500.0
    mock_ustec.volume_step = 0.01

    with patch("MetaTrader5.symbol_info", return_value=mock_ustec):
        # Even if raw lot is large, indices must be capped at 0.03
        lot_idx = runtime.calculate_risk_adjusted_lot("USTEC", sl_points=100.0, max_risk_usd=35.0)
        assert 0.01 <= lot_idx <= 0.03


def test_soft_derisking_protocol():
    """Test that apply_soft_derisking does NOT close positions at market, and protects profits."""
    kill_switch = FederalMasterKillSwitch()

    active_positions = [
        # Profitable BUY
        {"ticket": 1001, "symbol": "EURUSD", "type": "BUY", "price_open": 1.10000, "profit": 50.0},
        # Profitable SELL
        {"ticket": 1002, "symbol": "GBPUSD", "type": "SELL", "price_open": 1.30000, "profit": 35.0},
        # Loss BUY
        {"ticket": 1003, "symbol": "USDJPY", "type": "BUY", "price_open": 155.000, "profit": -45.0},
    ]

    mock_broker = MagicMock()
    mock_broker.get_symbol_spec.side_effect = lambda s: {
        "point": 0.00001 if "USD" in s and "JPY" not in s else 0.001,
        "digits": 5 if "USD" in s and "JPY" not in s else 3,
    }

    results = kill_switch.apply_soft_derisking(active_positions, broker_connector=mock_broker)

    # 1. System freeze flag engaged for 24 hours
    assert kill_switch.freeze_until > time.time() + 86000.0
    assert kill_switch.is_locked is True

    # 2. Orders should be locked in for profitable positions
    # BUY ticket 1001: open 1.10000 + 15 * 0.00001 = 1.10015
    assert results[0]["action"] == "LOCK_IN_BREAKEVEN_BUFFER"
    assert results[0]["new_sl"] == 1.10015
    mock_broker.modify_position_sltp.assert_any_call(ticket=1001, sl=1.10015)

    # SELL ticket 1002: open 1.30000 - 15 * 0.00001 = 1.29985
    assert results[1]["action"] == "LOCK_IN_BREAKEVEN_BUFFER"
    assert results[1]["new_sl"] == 1.29985
    mock_broker.modify_position_sltp.assert_any_call(ticket=1002, sl=1.29985)

    # Loss ticket 1003: Retained original SL, NOT closed
    assert results[2]["action"] == "RETAIN_ORIGINAL_SL"
    assert mock_broker.close_position.call_count == 0
    assert mock_broker.close_all_positions.call_count == 0

    # 3. verify_order_permission raises FederalCircuitBreakerActive due to 24h freeze
    with pytest.raises(FederalCircuitBreakerActive):
        kill_switch.verify_order_permission()
