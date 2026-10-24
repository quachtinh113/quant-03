"""
Unit test suite for Risk Mitigation & Execution Engine Patches:
1. Index Max Lots Ceiling in base_pod.py
2. Index Hard Stop Cap (-$60 USD) in live_federation_runner.py
3. Cross-Pod Asset Deduplication filter in live_federation_runner.py
4. Two-Tier Runner dynamic trailing locking in >= $25 USD profit when profit >= $40 USD
"""

import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import importlib
_base_pod_mod = importlib.import_module("us_federation_quant.05_the_50_states.base_pod")
BaseStatePod = _base_pod_mod.BaseStatePod
INDEX_MAX_LOTS = _base_pod_mod.INDEX_MAX_LOTS


class TestRiskMitigationPatches(unittest.TestCase):

    def test_index_max_lots_carver_ceiling(self):
        """Test that INDEX_MAX_LOTS caps volume in Carver calculation."""
        class TestPod(BaseStatePod):
            def analyze_market_regime(self, df): return "NORMAL"
            def calculate_continuous_forecast(self, df): return 10.0

        for symbol, expected_cap in [("USTEC", 0.15), ("USTECm", 0.15), ("US30", 0.10), ("US500", 0.20)]:
            pod = TestPod("STATE_TEST", "Test State", symbol, "Momentum", "H1")
            res = pod.calculate_carver_target_position(cash_vol_target=100000.0, forecast=10.0, atr_price=1.0, current_position_lot=0.0)
            self.assertLessEqual(res["buffered_lots"], expected_cap)

    def test_index_max_lots_risk_parity_ceiling(self):
        """Test that INDEX_MAX_LOTS caps volume in Risk Parity calculation."""
        class TestPod(BaseStatePod):
            def analyze_market_regime(self, df): return "NORMAL"
            def calculate_continuous_forecast(self, df): return 10.0

        for symbol, expected_cap in [("USTEC", 0.15), ("US30", 0.10), ("US500", 0.20)]:
            pod = TestPod("STATE_TEST", "Test State", symbol, "Momentum", "H1")
            res = pod.calculate_risk_parity_lot(account_equity=20000.0, current_price=30000.0, atr=5.0)
            self.assertLessEqual(res, expected_cap)

    def test_enforce_index_hard_stop_cap(self):
        """Test that Index Hard Stop Cap closes positions when loss <= -$60 USD."""
        from us_federation_quant.live_federation_runner import USFederationQuantRuntime

        runner = USFederationQuantRuntime()
        runner.mt5_mgr = MagicMock()
        runner.telemetry = MagicMock()

        # Mock open positions: 1 USTEC losing -$65, 1 USTEC losing -$20
        runner.mt5_mgr.get_positions.return_value = [
            {"ticket": 1001, "symbol": "USTEC", "type": "BUY", "volume": 0.15, "profit": -65.0, "swap": 0.0, "commission": 0.0},
            {"ticket": 1002, "symbol": "USTEC", "type": "BUY", "volume": 0.15, "profit": -20.0, "swap": 0.0, "commission": 0.0},
            {"ticket": 1003, "symbol": "EURUSD", "type": "BUY", "volume": 0.14, "profit": -80.0, "swap": 0.0, "commission": 0.0},
        ]
        runner.mt5_mgr.close_position.return_value = {"success": True, "ticket": 1001}

        closed = runner.enforce_index_hard_stop_cap(max_loss_usd=60.0)
        self.assertEqual(len(closed), 1)
        runner.mt5_mgr.close_position.assert_called_once_with(ticket=1001, comment="Index HardCap 60")

    def test_two_tier_runner_trailing_lock_25usd(self):
        """Test that floating profit >= $40 USD locks in >= $25 USD profit."""
        from us_federation_quant.live_federation_runner import USFederationQuantRuntime

        runner = USFederationQuantRuntime()
        runner.mt5_mgr = MagicMock()
        runner.mt5_mgr.get_symbol_spec.return_value = {"digits": 5}

        # Mock runner position: GBPUSD BUY entry 1.33000, curr 1.33800, profit $48.00, sl 1.33000
        runner.mt5_mgr.get_positions.return_value = [
            {
                "ticket": 2001,
                "symbol": "GBPUSD",
                "type": "BUY",
                "volume": 0.07,
                "profit": 48.0,
                "sl": 1.33000,
                "price_open": 1.33000,
                "price_current": 1.33800,
            }
        ]
        runner._load_two_tier_state = MagicMock(return_value={"2001": {"tier1_closed": True}})
        runner._save_two_tier_state = MagicMock()
        runner.mt5_mgr.modify_position_sltp.return_value = {"success": True}

        res = runner.enforce_two_tier_exit_engine(min_partial_profit_usd=25.0)
        runner.mt5_mgr.modify_position_sltp.assert_called_once()
        _, kwargs = runner.mt5_mgr.modify_position_sltp.call_args
        target_sl = kwargs["sl"]
        # With entry 1.33000, curr 1.33800, lock_ratio = 25 / 48 = 0.5208 -> target_sl ~ 1.33417
        self.assertGreater(target_sl, 1.33400)
        self.assertLess(target_sl, 1.33800)


if __name__ == "__main__":
    unittest.main()
