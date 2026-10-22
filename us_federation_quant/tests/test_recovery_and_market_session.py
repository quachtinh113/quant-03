"""
Test Suite: MT5 Connection Recovery, Market Session Gatekeeper, and Error Handling
"""

import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from datetime import datetime, timezone

from us_federation_quant.core.mt5_connection_manager import MT5ConnectionManager


class TestRecoveryAndMarketSession(unittest.TestCase):
    def setUp(self):
        self.mgr = MT5ConnectionManager()

    @patch("us_federation_quant.core.mt5_connection_manager.mt5")
    def test_market_session_blocks_non_full_access(self, mock_mt5):
        """Verify is_market_open returns False when trade_mode is not FULL (e.g. CLOSEONLY or DISABLED)."""
        mock_mt5.SYMBOL_TRADE_MODE_FULL = 4
        mock_mt5.SYMBOL_TRADE_MODE_DISABLED = 0
        mock_mt5.SYMBOL_TRADE_MODE_CLOSEONLY = 3

        # Case 1: Symbol has trade_mode = CLOSEONLY (3) -> Market closed for new orders
        mock_info = MagicMock()
        mock_info.trade_mode = 3
        mock_mt5.symbol_info.return_value = mock_info
        
        with patch.object(self.mgr, "ensure_connected", return_value=True):
            self.assertFalse(self.mgr.is_market_open("USTEC"))

        # Case 2: Symbol has trade_mode = FULL (4) with fresh tick -> Open
        mock_info.trade_mode = 4
        mock_tick = MagicMock()
        mock_tick.time = datetime.now(timezone.utc).timestamp()
        mock_mt5.symbol_info_tick.return_value = mock_tick
        with patch.object(self.mgr, "ensure_connected", return_value=True):
            self.assertTrue(self.mgr.is_market_open("USTEC"))

    @patch("us_federation_quant.core.mt5_connection_manager.mt5")
    def test_open_market_order_handles_market_closed_10018(self, mock_mt5):
        """Verify retcode 10018 (MARKET_CLOSED) returns clean rejection without raising exceptions."""
        mock_mt5.TRADE_RETCODE_DONE = 10009
        mock_res = MagicMock()
        mock_res.retcode = 10018
        mock_res.comment = "Market is closed"
        mock_mt5.order_send.return_value = mock_res

        with patch.object(self.mgr, "ensure_connected", return_value=True), \
             patch.object(self.mgr, "is_market_open", return_value=True), \
             patch.object(self.mgr, "get_symbol_spec", return_value={"digits": 2, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01}), \
             patch.object(self.mgr, "get_tick", return_value={"ask": 20000.0, "bid": 19999.0}):
            
            res = self.mgr.open_market_order("USTEC", "BUY", 0.10)
            self.assertFalse(res["success"])
            self.assertEqual(res["retcode"], 10018)
            self.assertEqual(res["state"], "REJECTED")


if __name__ == "__main__":
    unittest.main()
