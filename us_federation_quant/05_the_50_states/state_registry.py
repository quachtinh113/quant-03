"""
The 50 States (State Sovereignty & Strategy Pod Registry)
Coordinates 50 autonomous strategy pods.
Each state has its own asset, timeframe, and isolated capital allocation.
If any single state suffers localized losses, constitutional firewalls quarantine the damage
without threatening federal systemic solvency.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


@dataclass
class StatePod:
    """An autonomous state strategy pod."""
    state_id: str
    state_name: str
    primary_asset: str
    strategy_style: str
    timeframe: str
    allocated_capital: float
    local_drawdown: float = 0.0
    is_active: bool = True

    def update_performance(self, pnl_pct: float) -> bool:
        """Updates local performance. If local drawdown breaches -10%, activates localized quarantine."""
        if pnl_pct < 0:
            self.local_drawdown += pnl_pct
        else:
            self.local_drawdown = min(0.0, self.local_drawdown + pnl_pct)

        if self.local_drawdown <= -0.10: # Localized bankruptcy quarantine
            self.is_active = False
            return False
        return True


class StateFederationRegistry:
    """
    Registry managing all 50 sovereign states of the federation.
    """

    def __init__(self):
        self.states: Dict[str, StatePod] = {}
        self._initialize_50_states()

    def _initialize_50_states(self):
        """
        Initializes 50 distinct institutional sovereign state pods on Exness:
        1. States 01 - 10: Commodities, Energy & Crypto (10 states)
        2. States 11 - 20: Global Equity Indices (10 states)
        3. States 21 - 35: Forex Majors & Crosses (15 states)
        4. States 36 - 50: US Mega-Cap Equities (15 states)
        """
        from .base_pod import BaseStatePod

        # Category 1: Commodities, Energy & Crypto (States 01 - 10)
        commodities_crypto = [
            ("STATE_01", "State of Gold Micro-Scalp", "XAUUSDm", "Avellaneda-Stoikov Micro-Scalp", "M15", 250_000.0, 260903),
            ("STATE_02", "State of Silver Ratio Spread", "XAGUSDm", "Cointegration Pairs", "H1", 200_000.0, 260932),
            ("STATE_03", "State of WTI Crude Supply Shock", "USOILm", "Commodity Carry", "H4", 200_000.0, 260933),
            ("STATE_04", "State of Brent Crude Session", "UKOILm", "Session Breakout", "H1", 180_000.0, 260934),
            ("STATE_05", "State of Bitcoin Volatility Arb", "BTCUSDm", "Volatility Momentum (8H)", "8H", 250_000.0, 260904),
            ("STATE_06", "State of Ethereum StatArb", "ETHUSDm", "Statistical Arbitrage", "H4", 200_000.0, 260936),
            ("STATE_07", "State of Solana High-Beta", "SOLUSDm", "High-Beta Momentum", "H1", 180_000.0, 260937),
            ("STATE_08", "State of Platinum Precious Spread", "XPTUSDm", "Precious Metals Carry", "D1", 180_000.0, 260938),
            ("STATE_09", "State of Palladium Volatility Skew", "XPDUSDm", "Volatility Skew", "H4", 180_000.0, 260939),
            ("STATE_10", "State of Natural Gas Breakout", "NATGASm", "Seasonality Breakout", "D1", 200_000.0, 260940),
        ]

        # Category 2: Global Equity Indices (States 11 - 20)
        equity_indices = [
            ("STATE_11", "State of S&P 500 Factor Neutral", "US500m", "Cross-Sectional Factor Neutral", "D1", 250_000.0, 260941),
            ("STATE_12", "State of Nasdaq 100 Tech Momentum", "USTECm", "High-Beta Momentum", "H1", 250_000.0, 260902),
            ("STATE_13", "State of Dow Jones Industrial Trend", "US30m", "TSMOM Trend Following", "H4", 220_000.0, 260943),
            ("STATE_14", "State of Nikkei 225 Tokyo Session", "JP225m", "Tokyo Session Open", "M30", 200_000.0, 260944),
            ("STATE_15", "State of DAX 40 Frankfurt Open", "DE40m", "Frankfurt Breakout", "M15", 200_000.0, 260945),
            ("STATE_16", "State of FTSE 100 London Reversion", "UK100m", "Mean-Reversion", "H1", 180_000.0, 260946),
            ("STATE_17", "State of Hang Seng Liquidity Sweep", "HK50m", "Order Flow Sweep", "M15", 180_000.0, 260947),
            ("STATE_18", "State of ASX 200 Sydney Open", "AU200m", "Sydney Momentum", "H1", 180_000.0, 260948),
            ("STATE_19", "State of Euro Stoxx 50 Value Momentum", "STOXX50m", "Value Momentum", "H4", 180_000.0, 260949),
            ("STATE_20", "State of CAC 40 Paris Momentum", "FR40m", "Paris Cash Open", "H1", 180_000.0, 260950),
        ]

        # Category 3: Forex Majors & Crosses (States 21 - 35)
        forex_pairs = [
            ("STATE_21", "State of EUR/USD Macro Swing", "EURUSDm", "Macro Flow Swing", "D1", 200_000.0, 260901),
            ("STATE_22", "State of GBP/USD Liquidity Sweep", "GBPUSDm", "Order Flow Sweep", "H1", 200_000.0, 260952),
            ("STATE_23", "State of USD/JPY StatArb Carry", "USDJPYm", "Carry & Mean-Revert", "D1", 200_000.0, 260953),
            ("STATE_24", "State of AUD/USD Commodity Flow", "AUDUSDm", "Commodity Beta Flow", "D1", 180_000.0, 260954),
            ("STATE_25", "State of USD/CAD Oil Beta Neutral", "USDCADm", "Oil-Neutral Hedged", "H4", 180_000.0, 260955),
            ("STATE_26", "State of USD/CHF Safe Haven Flow", "USDCHFm", "Safe Haven Flight", "H1", 180_000.0, 260956),
            ("STATE_27", "State of NZD/USD Yield Carry", "NZDUSDm", "Yield Differential Carry", "D1", 180_000.0, 260957),
            ("STATE_28", "State of EUR/JPY Cross Volatility", "EURJPYm", "Volatility Skew", "H1", 180_000.0, 260958),
            ("STATE_29", "State of GBP/JPY Dragon Breakout", "GBPJPYm", "Dragon Trend Breakout", "H1", 200_000.0, 260959),
            ("STATE_30", "State of AUD/JPY Risk Barometer", "AUDJPYm", "Risk-On Barometer", "H4", 180_000.0, 260960),
            ("STATE_31", "State of EUR/GBP Cross Corridor", "EURGBPm", "Corridor Reversion", "H1", 180_000.0, 260961),
            ("STATE_32", "State of EUR/AUD Commodity Cross", "EURAUDm", "Cross Statistical Arb", "H4", 180_000.0, 260962),
            ("STATE_33", "State of GBP/CHF Cross Reversion", "GBPCHFm", "Mean-Reversion", "H1", 180_000.0, 260963),
            ("STATE_34", "State of CAD/JPY Energy Cross Flow", "CADJPYm", "Energy Flow Momentum", "H4", 180_000.0, 260964),
            ("STATE_35", "State of NZD/JPY Pacific Carry", "NZDJPYm", "Pacific Carry Trade", "D1", 180_000.0, 260965),
        ]

        # Category 4: US Mega-Cap Equities on Exness (States 36 - 50)
        us_equities = [
            ("STATE_36", "State of Apple Silicon Alpha", "AAPLm", "Quality Alpha Growth", "D1", 200_000.0, 260966),
            ("STATE_37", "State of Microsoft Cloud Scale", "MSFTm", "Enterprise Moat Alpha", "D1", 200_000.0, 260967),
            ("STATE_38", "State of Nvidia AI Accelerated", "NVDAm", "AI Hardware Pureplay", "H4", 250_000.0, 260968),
            ("STATE_39", "State of Alphabet Quantum Search", "GOOGm", "Ad & Search Cash Machine", "D1", 200_000.0, 260969),
            ("STATE_40", "State of Amazon Cloud & Logistics", "AMZNm", "E-Commerce Dominance", "H4", 200_000.0, 260970),
            ("STATE_41", "State of Meta Social Network Moat", "METAm", "Social Graph Engagement", "H4", 200_000.0, 260971),
            ("STATE_42", "State of Tesla Autonomous Beta", "TSLAm", "High-Beta EV Disruptor", "H1", 220_000.0, 260972),
            ("STATE_43", "State of Berkshire Value Compounder", "BRKm", "Buffett Float Compounder", "D1", 180_000.0, 260973),
            ("STATE_44", "State of JNJ Defensive Healthcare", "JNJm", "Defensive Low-Beta Yield", "D1", 180_000.0, 260974),
            ("STATE_45", "State of JPMorgan Financial Fortress", "JPMm", "Money Center Banking Net Interest", "H4", 180_000.0, 260975),
            ("STATE_46", "State of Visa Global Payments Rail", "Vm", "Network Tollbooth Alpha", "D1", 180_000.0, 260976),
            ("STATE_47", "State of Walmart Consumer Staple", "WMTm", "Non-Cyclical Consumer Cash", "D1", 180_000.0, 260977),
            ("STATE_48", "State of ExxonMobil Free Cash Flow", "XOMm", "Energy Upstream Free Cash", "D1", 180_000.0, 260978),
            ("STATE_49", "State of UnitedHealth Managed Care", "UNHm", "Health Maintenance Moat", "D1", 180_000.0, 260979),
            ("STATE_50", "State of Procter & Gamble Fortress", "PGm", "Recession-Proof Staple", "D1", 180_000.0, 260980),
        ]

        all_state_specs = commodities_crypto + equity_indices + forex_pairs + us_equities


        from .state_01_xauusd_scalp.pod import GoldScalpPod
        from .state_02_us30_hybrid.pod import US30HybridPod
        from .state_03_usdjpy_carry.pod import USDJPYCarryPod

        for sid, sname, asset, style, tf, cap, magic in all_state_specs:

            if sid == "STATE_01":
                pod = GoldScalpPod(allocated_capital=cap)
            elif sid == "STATE_02":
                pod = US30HybridPod(allocated_capital=cap)
            elif sid == "STATE_03":
                pod = USDJPYCarryPod(allocated_capital=cap)
            else:
                pod = BaseStatePod(
                    state_id=sid,
                    state_name=sname,
                    primary_asset=asset,
                    strategy_style=style,
                    timeframe=tf,
                    allocated_capital=cap
                )
            pod.magic = magic
            self.states[sid] = pod


    def get_state(self, state_id: str) -> Optional[StatePod]:
        return self.states.get(state_id)

    def get_all_active_states(self) -> List[StatePod]:
        return [s for s in self.states.values() if s.is_active]

    def quarantine_pod(self, state_id: str, reason: str = "ADMINISTRATIVE_QUARANTINE") -> bool:
        """Quarantines a state pod, blocking execution allocations."""
        pod = self.get_state(state_id)
        if pod:
            pod.is_active = False
            if hasattr(pod, "is_quarantined"):
                pod.is_quarantined = True
                pod.capital_multiplier = 0.0
            return True
        return False

    def reinstate_pod(self, state_id: str) -> bool:
        """Reinstates a quarantined state pod."""
        pod = self.get_state(state_id)
        if pod:
            if hasattr(pod, "reinstate"):
                pod.reinstate(reset_drawdown=True)
            else:
                pod.is_active = True
                pod.local_drawdown = 0.0
            return True
        return False

    def audit_cross_state_correlations(
        self,
        returns_dict: Dict[str, pd.Series],
        max_corr_threshold: float = 0.85
    ) -> Dict[str, Any]:
        """
        Audits pairwise cross-state correlations to detect redundant systemic risk clusters.
        """
        if len(returns_dict) < 2:
            return {"high_correlation_pairs": [], "status": "OPTIMAL_DIVERSIFICATION"}

        df_returns = pd.DataFrame(returns_dict)
        corr_matrix = df_returns.corr()

        high_corr_pairs: List[Dict[str, Any]] = []
        states_list = list(corr_matrix.columns)

        for i in range(len(states_list)):
            for j in range(i + 1, len(states_list)):
                s1 = states_list[i]
                s2 = states_list[j]
                c_val = float(corr_matrix.loc[s1, s2])
                if abs(c_val) > max_corr_threshold:
                    high_corr_pairs.append({
                        "state_1": s1,
                        "state_2": s2,
                        "correlation": round(c_val, 4),
                        "recommendation": "APPLY_GIVENS_ROTATION_OR_REDUCE_WEIGHT"
                    })

        return {
            "high_correlation_pairs": high_corr_pairs,
            "redundant_pairs_count": len(high_corr_pairs),
            "status": "REDUNDANT_RISK_WARNING" if high_corr_pairs else "OPTIMAL_DIVERSIFICATION"
        }

    def get_federation_summary(self) -> Dict[str, Any]:
        total_states = len(self.states)
        active_states = len(self.get_all_active_states())
        total_capital = sum(s.allocated_capital for s in self.states.values())
        return {
            "total_states": total_states,
            "active_states": active_states,
            "quarantined_states": total_states - active_states,
            "total_capital": total_capital
        }

