from __future__ import annotations

from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..order_router.router import MicroOrderSlice


class MT5TradeAction:
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 6
    TRADE_ACTION_MODIFY = 7
    TRADE_ACTION_REMOVE = 8


class MT5OrderType:
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3


class MT5OrderTime:
    ORDER_TIME_GTC = 0
    ORDER_TIME_DAY = 1
    ORDER_TIME_SPECIFIED = 2


class MT5OrderFilling:
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2


class MT5PayloadBuilder:
    """
    Constructs and validates MT5 MqlTradeRequest dictionaries.
    """

    def __init__(
        self,
        default_magic: int = 20260919,
        default_deviation_points: int = 15,
        default_filling_type: int = MT5OrderFilling.ORDER_FILLING_IOC,
        min_lot_size: float = 0.01,
        lot_step: float = 0.01
    ):
        self.default_magic = default_magic
        self.default_deviation_points = default_deviation_points
        self.default_filling_type = default_filling_type
        self.min_lot_size = min_lot_size
        self.lot_step = lot_step

    def build_trade_request(
        self,
        slice_order: MicroOrderSlice,
        sl_price: float = 0.0,
        tp_price: float = 0.0,
        deviation_points: Optional[int] = None,
        magic_number: Optional[int] = None,
        is_limit_order: bool = False
    ) -> Dict[str, Any]:
        """
        Builds a single MqlTradeRequest payload dictionary from a MicroOrderSlice.
        """
        # Determine MT5 order type
        is_buy = slice_order.action.upper() == "BUY"
        if is_limit_order or "LIMIT" in slice_order.order_type:
            order_type = MT5OrderType.ORDER_TYPE_BUY_LIMIT if is_buy else MT5OrderType.ORDER_TYPE_SELL_LIMIT
            trade_action = MT5TradeAction.TRADE_ACTION_PENDING
        else:
            order_type = MT5OrderType.ORDER_TYPE_BUY if is_buy else MT5OrderType.ORDER_TYPE_SELL
            trade_action = MT5TradeAction.TRADE_ACTION_DEAL

        # Volume quantization to lot step
        volume = max(self.min_lot_size, round(slice_order.lots, 2))

        if getattr(slice_order, "client_order_id", None):
            comment = str(slice_order.client_order_id)[:31]
        else:
            comment = f"FED_{slice_order.slice_index}/{slice_order.total_slices}_{slice_order.order_type[:10]}"[:31]

        request = {
            "action": trade_action,
            "symbol": slice_order.asset,
            "volume": volume,
            "type": order_type,
            "price": round(slice_order.target_price, 5),
            "sl": round(sl_price, 5) if sl_price > 0 else 0.0,
            "tp": round(tp_price, 5) if tp_price > 0 else 0.0,
            "deviation": deviation_points if deviation_points is not None else self.default_deviation_points,
            "magic": magic_number if magic_number is not None else self.default_magic,
            "comment": comment,
            "type_time": MT5OrderTime.ORDER_TIME_GTC,
            "type_filling": self.default_filling_type
        }

        return request

    def build_batch_requests(
        self,
        slice_orders: List[MicroOrderSlice],
        sl_price: float = 0.0,
        tp_price: float = 0.0,
        deviation_points: Optional[int] = None,
        magic_number: Optional[int] = None,
        is_limit_order: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Constructs a batch of MT5 MqlTradeRequest payloads for all child slices.
        """
        batch: List[Dict[str, Any]] = []
        for s in slice_orders:
            req = self.build_trade_request(
                slice_order=s,
                sl_price=sl_price,
                tp_price=tp_price,
                deviation_points=deviation_points,
                magic_number=magic_number,
                is_limit_order=is_limit_order
            )
            batch.append(req)
        return batch

    def validate_trade_request(self, request: Dict[str, Any]) -> bool:
        """
        Validates the schema and safety thresholds of an MT5 trade request.
        """
        required_keys = ["action", "symbol", "volume", "type", "price", "deviation", "magic"]
        for k in required_keys:
            if k not in request:
                return False

        if not isinstance(request["symbol"], str) or len(request["symbol"]) == 0:
            return False

        if request["volume"] < self.min_lot_size:
            return False

        if request["price"] <= 0:
            return False

        if request["type"] not in [
            MT5OrderType.ORDER_TYPE_BUY,
            MT5OrderType.ORDER_TYPE_SELL,
            MT5OrderType.ORDER_TYPE_BUY_LIMIT,
            MT5OrderType.ORDER_TYPE_SELL_LIMIT
        ]:
            return False

        return True
