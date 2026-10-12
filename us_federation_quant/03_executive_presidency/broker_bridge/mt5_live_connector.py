"""
MetaTrader 5 Live & Paper Execution Gateway Connector.
Adheres to QuantConnect LEAN Brokerage Model specifications and AFML safety patterns.
Bridges ExecutiveOrderRouter and MT5PayloadBuilder to the MetaTrader 5 Python client API.
Provides automatic failover to MockBrokerGateway for headless CI/CD and offline paper trading.
"""

from typing import Dict, Any, List, Optional
import time
import logging

logger = logging.getLogger("MT5LiveConnector")


class MT5RetCode:
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_DONE_PARTIAL = 10010
    TRADE_RETCODE_PLACED = 10008
    TRADE_RETCODE_REQUOTE = 10004
    TRADE_RETCODE_REJECT = 10006
    TRADE_RETCODE_CONNECTION = 10031


class MT5LiveConnector:
    """
    Live/Paper Broker Gateway for MetaTrader 5.
    """

    def __init__(
        self,
        account: Optional[int] = None,
        server: Optional[str] = None,
        force_mock: bool = False
    ):
        self.account = account
        self.server = server
        self.force_mock = force_mock
        self.is_connected = False
        self.is_mock_mode = force_mock
        self._mock_positions: Dict[int, Dict[str, Any]] = {}
        self._next_ticket = 100001
        self._mock_balance = 1_000_000.0
        self._mock_equity = 1_000_000.0

        self._init_backend()

    def _init_backend(self):
        """Attempts to initialize MetaTrader5 package; falls back to MockBrokerGateway if unavailable."""
        if self.force_mock:
            self.is_mock_mode = True
            return

        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5
            # Test basic initialization without credentials (terminal already open)
            initialized = self._mt5.initialize()
            if initialized:
                self.is_connected = True
                self.is_mock_mode = False
            else:
                self.is_mock_mode = True
        except (ImportError, Exception):
            self.is_mock_mode = True

    def connect(self) -> bool:
        """Connects to broker gateway."""
        if self.is_mock_mode:
            self.is_connected = True
            return True

        if not self.is_connected and hasattr(self, "_mt5"):
            self.is_connected = bool(self._mt5.initialize())
        return self.is_connected

    def disconnect(self):
        """Closes connection with terminal."""
        if not self.is_mock_mode and hasattr(self, "_mt5"):
            try:
                self._mt5.shutdown()
            except Exception:
                pass
        self.is_connected = False

    def get_account_info(self) -> Dict[str, Any]:
        """Returns account balance, equity, and margin telemetry."""
        if self.is_mock_mode or not self.is_connected:
            return {
                "login": self.account or 9999999,
                "trade_mode": "MOCK_PAPER",
                "balance": self._mock_balance,
                "equity": self._mock_equity,
                "margin": 0.0,
                "margin_free": self._mock_equity,
                "margin_level": 0.0,
                "currency": "USD"
            }

        acc = self._mt5.account_info()
        if acc is None:
            return {"error": "ACCOUNT_INFO_UNAVAILABLE", "is_connected": False}

        return {
            "login": acc.login,
            "trade_mode": "REAL" if acc.trade_mode == 0 else "DEMO",
            "balance": acc.balance,
            "equity": acc.equity,
            "margin": acc.margin,
            "margin_free": acc.margin_free,
            "margin_level": acc.margin_level,
            "currency": acc.currency
        }

    def send_trade_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submits an MqlTradeRequest dictionary to MT5.
        """
        if not self.is_connected:
            self.connect()

        if self.is_mock_mode:
            # Deterministic simulated execution
            ticket = self._next_ticket
            self._next_ticket += 1
            executed_price = request.get("price", 2000.0)
            lots = request.get("volume", 0.01)
            symbol = request.get("symbol", "XAUUSD")
            action_type = request.get("type", 0)

            position_entry = {
                "ticket": ticket,
                "symbol": symbol,
                "type": action_type,
                "volume": lots,
                "price_open": executed_price,
                "sl": request.get("sl", 0.0),
                "tp": request.get("tp", 0.0),
                "magic": request.get("magic", 20260919),
                "comment": request.get("comment", ""),
                "time": time.time()
            }
            self._mock_positions[ticket] = position_entry

            return {
                "retcode": MT5RetCode.TRADE_RETCODE_DONE,
                "deal": ticket + 500000,
                "order": ticket,
                "volume": lots,
                "price": executed_price,
                "bid": executed_price - 0.1,
                "ask": executed_price + 0.1,
                "comment": "MOCK_ORDER_DONE",
                "request": request
            }

        # Real MT5 execution
        result = self._mt5.order_send(request)
        if result is None:
            err = self._mt5.last_error()
            return {
                "retcode": MT5RetCode.TRADE_RETCODE_REJECT,
                "error": err,
                "comment": "ORDER_SEND_FAILED_NULL"
            }

        return {
            "retcode": result.retcode,
            "deal": result.deal,
            "order": result.order,
            "volume": result.volume,
            "price": result.price,
            "bid": result.bid,
            "ask": result.ask,
            "comment": result.comment,
            "request": request
        }

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all open positions."""
        if self.is_mock_mode:
            positions = list(self._mock_positions.values())
            if symbol:
                positions = [p for p in positions if p["symbol"] == symbol]
            return positions

        raw_positions = self._mt5.positions_get(symbol=symbol) if symbol else self._mt5.positions_get()
        if raw_positions is None:
            return []

        return [p._asdict() for p in raw_positions]

    def close_position(self, ticket: int) -> bool:
        """Closes an open position by ticket."""
        if self.is_mock_mode:
            if ticket in self._mock_positions:
                del self._mock_positions[ticket]
                return True
            return False

        # In real MT5, closing requires an opposite order_send
        positions = self._mt5.positions_get(ticket=ticket)
        if not positions:
            return False
        pos = positions[0]
        close_type = 1 if pos.type == 0 else 0  # Opposite side
        tick = self._mt5.symbol_info_tick(pos.symbol)
        price = tick.bid if close_type == 1 else tick.ask

        close_req = {
            "action": 1,  # TRADE_ACTION_DEAL
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": pos.magic,
            "comment": f"CLOSE_{ticket}",
            "type_time": 0,
            "type_filling": 1
        }
        res = self._mt5.order_send(close_req)
        return res is not None and res.retcode == MT5RetCode.TRADE_RETCODE_DONE
