"""
========================================================================================
DYNAMIC TRAILING STOP MANAGER (CHANDELIER EXIT / ATR)
Continuously monitors open profitable positions and dynamically ratchets Stop Loss
behind the market price based on H1 Average True Range (ATR14).
Prevents premature profit-taking while safeguarding capital from trend reversals.
========================================================================================
"""

import MetaTrader5 as mt5
import pandas as pd
import logging

logger = logging.getLogger("TrailingStopManager")


class TrailingStopManager:
    def __init__(self, atr_period: int = 14, atr_multiplier: float = 2.0, min_modification_points: int = 25):
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.min_modification_points = min_modification_points

    def _calculate_h1_atr(self, symbol: str) -> float:
        """Tính toán Average True Range (ATR) trên khung H1."""
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, self.atr_period + 1)
        if rates is None or len(rates) < self.atr_period:
            return 0.0

        df = pd.DataFrame(rates)
        df['tr0'] = abs(df['high'] - df['low'])
        df['tr1'] = abs(df['high'] - df['close'].shift(1))
        df['tr2'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)

        atr = float(df['tr'].dropna().mean())
        return atr

    def update_trailing_stops(self):
        """Quét toàn bộ vị thế đang có lãi và dời SL theo Chandelier Exit (ATR)."""
        positions = mt5.positions_get()
        if positions is None or len(positions) == 0:
            return

        for pos in positions:
            # Chỉ xử lý các lệnh đang có lợi nhuận dương
            if pos.profit <= 0:
                continue

            symbol = pos.symbol
            ticket = pos.ticket
            current_sl = float(pos.sl)
            order_type = pos.type

            s_info = mt5.symbol_info(symbol)
            if s_info is None:
                continue

            point = float(s_info.point)
            digits = int(s_info.digits)
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                continue

            current_price = tick.bid if order_type == mt5.ORDER_TYPE_BUY else tick.ask

            atr = self._calculate_h1_atr(symbol)
            if atr == 0.0:
                continue

            # Tính toán Stop Loss mới dựa trên Chandelier Exit
            if order_type == mt5.ORDER_TYPE_BUY:
                # Lệnh BUY: SL mới dời lên (Bám gót giá hiện tại trừ đi biên độ ATR)
                new_sl = current_price - (self.atr_multiplier * atr)
                new_sl = round(new_sl, digits)

                # Chỉ dời lên, không bao giờ lùi SL. Và phải lớn hơn SL cũ + buffer points
                if new_sl > current_sl and (new_sl - current_sl) >= (self.min_modification_points * point):
                    self._modify_sltp(ticket, symbol, new_sl, pos.tp, "BUY")

            elif order_type == mt5.ORDER_TYPE_SELL:
                # Lệnh SELL: SL mới dời xuống (Bám gót giá hiện tại cộng thêm biên độ ATR)
                new_sl = current_price + (self.atr_multiplier * atr)
                new_sl = round(new_sl, digits)

                # SL cũ = 0.0 (chưa cài) HOẶC SL mới phải thấp hơn SL cũ - buffer points
                if current_sl == 0.0 or (new_sl < current_sl and (current_sl - new_sl) >= (self.min_modification_points * point)):
                    self._modify_sltp(ticket, symbol, new_sl, pos.tp, "SELL")

    def _modify_sltp(self, ticket: int, symbol: str, new_sl: float, current_tp: float, type_str: str):
        """Gửi lệnh cập nhật SL/TP xuống MT5 Broker."""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": symbol,
            "sl": new_sl,
            "tp": current_tp,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"📈 [TRAILING STOP] Cập nhật SL lệnh {type_str} #{ticket} ({symbol}) -> {new_sl}")
        else:
            comment = result.comment if result else "Unknown"
            logger.error(f"❌ [TRAILING STOP] Lỗi dời SL lệnh #{ticket}: {comment}")
