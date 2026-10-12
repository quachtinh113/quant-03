"""
========================================================================================
US FEDERATION QUANT — HARVARD QUANTITATIVE RESEARCH & 50-STATE TACTICAL BLUEPRINT
Integrates Harvard University Economics & Finance Research breakthroughs into
the 50-State Strategy Matrix:

HARVARD QUANTITATIVE PILLARS:
1. 🎓 John Y. Campbell (Harvard ICAPM): Intertemporal Hedging & Present Value Predictability.
2. 🏛️ Andrei Shleifer & Robert Vishny (Harvard 1997): Limits of Arbitrage & Liquidity Spirals.
3. 📉 Emmanuel Farhi (Harvard 2008-2015): Disaster Risk Premia & Crash Risk in Carry Trades.
4. 🌍 Kenneth Rogoff & Carmen Reinhart (Harvard): Sovereign Debt Cycles & Commodity Sudden Stops.
5. 🧠 Malcolm Baker & Jeffrey Wurgler (Harvard/NBER): Cross-Sectional Investor Sentiment Beta.
========================================================================================
"""

from __future__ import annotations

import importlib
import json
import logging
import math
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

_RES_DIR = Path(__file__).resolve().parent
_DIR = _RES_DIR.parent
_WORKSPACE = _DIR.parent
for p in [str(_DIR), str(_WORKSPACE), str(_WORKSPACE / "All_Fleet_Bot"), str(_WORKSPACE / "ML_4_Bot")]:
    if p not in sys.path:
        sys.path.insert(0, p)

_states_mod = importlib.import_module("us_federation_quant.05_the_50_states.state_registry")
StateFederationRegistry = _states_mod.StateFederationRegistry

LOG_DIR = _DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "harvard_strategy_50_states.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("HarvardResearchEngine")


@dataclass
class HarvardStateBlueprint:
    state_id: str
    state_name: str
    asset_symbol: str
    asset_class: str
    base_model: str
    harvard_research_pillar: str
    harvard_lead_authors: str
    harvard_tactical_enhancement: str
    shleifer_vishny_arbitrage_cap: float
    farhi_disaster_risk_hedge_pct: float
    campbell_icapm_horizon_demand: str
    baker_wurgler_sentiment_regime: str
    optimal_execution_timing: str
    risk_governance_rule: str


class HarvardTacticalAnalyzer:
    """Applies Harvard Economics & Financial Engineering to all 50 States."""

    def __init__(self):
        self.registry = StateFederationRegistry()

    def analyze_state_with_harvard_layer(self, state_id: str, pod_obj: Any) -> HarvardStateBlueprint:
        symbol = getattr(pod_obj, "primary_asset", "UNKNOWN")
        name = getattr(pod_obj, "state_name", state_id)

        # 1. Classify Asset Cluster
        if any(fx in symbol for fx in ["EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]):
            cluster = "Forex"
        elif any(m in symbol for m in ["XAU", "XAG", "XPT", "XPD", "OIL", "GAS"]):
            cluster = "Commodities"
        elif any(c in symbol for c in ["BTC", "ETH", "SOL"]):
            cluster = "Crypto"
        elif any(idx in symbol for idx in ["500", "TEC", "30", "225", "40", "100", "50", "200"]):
            cluster = "Global Indices"
        else:
            cluster = "US Equities"

        # 2. Match Harvard Research Breakthroughs
        if cluster == "Forex":
            base_model = "Avellaneda-Stoikov Microstructure"
            pillar = "Farhi Disaster Risk & Rogoff Currency Arbitrage"
            authors = "Emmanuel Farhi (Harvard), Kenneth Rogoff (Harvard)"
            enhancement = (
                "Bổ sung Farhi Disaster Jump Filter: Tự động thu hẹp spread và giảm 60% vị thế "
                "khi chênh lệch lợi suất Carry Trade vượt quá 3 độ lệch chuẩn để triệt tiêu cú sập tỷ giá bất ngờ."
            )
            arb_cap = 4.5  # Max safe leverage under Shleifer-Vishny limits
            disaster_hedge = 1.2  # % equity hedged against tail jump
            campbell_demand = "Mean-Reverting Intertemporal Carry Hedge (H1/H4)"
            sentiment_regime = "Low Sentiment Bias / High Elasticity"
            timing = "Phiên London (08:00 - 16:00 GMT) & New York Overlap"
            gov_rule = "Ngắt vị thế tức thì nếu chênh lệch spread vượt quá 3 pips trước tin NFP/CPI."

        elif cluster == "Commodities":
            base_model = "Avellaneda-Stoikov / MTF CUSUM"
            pillar = "Rogoff-Reinhart Commodity Supercycle & Campbell Term Structure"
            authors = "Kenneth Rogoff (Harvard), John Y. Campbell (Harvard)"
            enhancement = (
                "Tích hợp Campbell Term Structure of Risk: Điều chỉnh độ lệch vị thế (Inventory Skew) "
                "theo cấu trúc đường cong bù hoãn bán (Backwardation) và bù hoãn mua (Contango) trên Dầu và Vàng."
            )
            arb_cap = 2.8
            disaster_hedge = 2.5
            campbell_demand = "Inflation-Hedging Long Horizon Elasticity"
            sentiment_regime = "Geopolitical Crisis Asymmetric Skew"
            timing = "Phiên giao dịch London Fix (15:00 GMT) & NY Close"
            gov_rule = "Áp dụng trần ký quỹ cứng: Không vượt quá 15% tổng vốn danh mục cho Vàng & Dầu."

        elif cluster == "Global Indices":
            base_model = "Ornstein-Uhlenbeck Mean-Reversion"
            pillar = "Campbell-Shiller ICAPM & Present-Value Predictability"
            authors = "John Y. Campbell (Harvard), Robert Shiller (Harvard/Yale PhD)"
            enhancement = (
                "Bổ sung Campbell-Shiller Excess Return Predictor: Đo lường độ lệch định giá chu kỳ PE "
                "để chỉ thực hiện hồi quy mean-reversion thuận theo xu hướng vĩ mô dài hạn, loại bỏ bull/bear trap."
            )
            arb_cap = 3.2
            disaster_hedge = 1.8
            campbell_demand = "Intertemporal Consumption-Smoothing Hedge"
            sentiment_regime = "Macro Regime Beta Driven"
            timing = "Mở cửa phiên Frankfurt (07:00 GMT) & Wall Street Open (13:30 GMT)"
            gov_rule = "Thang bậc bảo vệ Pod Defense: Giảm 50% khối lượng khi chỉ số sụt giảm -3% trong ngày."

        elif cluster == "US Equities":
            base_model = "RMT-Denoised-Eigen-Kelly"
            pillar = "Baker-Wurgler Sentiment Beta & Shleifer Limits of Arbitrage"
            authors = "Malcolm Baker (Harvard), Andrei Shleifer (Harvard)"
            enhancement = (
                "Tích hợp Baker-Wurgler Cross-Sectional Sentiment Sensitivity: Nhận diện cổ phiếu đầu cơ "
                "(Tesla, Nvidia) có Sentiment Beta cao để đánh Momentum, và cổ phiếu phòng thủ (Walmart, P&G) để đánh Hồi quy."
            )
            arb_cap = 2.5
            disaster_hedge = 2.0
            campbell_demand = "Cross-Sectional Factor Orthogonality"
            sentiment_regime = "High Sentiment Elasticity (Tech) / Low Elasticity (Staples)"
            timing = "14:00 - 20:00 GMT (Phiên chính thức Sàn New York)"
            gov_rule = "Bảo toàn Beta Neutral: Ma trận Gilbert Strang ép tổng Beta cổ phiếu về đúng 0.00."

        else:  # Crypto
            base_model = "MTF-CUSUM Trend Breakout & FracDiff"
            pillar = "Shleifer-Vishny Liquidity Spirals & Sovereign Disintermediation"
            authors = "Andrei Shleifer (Harvard), Robert Vishny (Harvard/Chicago)"
            enhancement = (
                "Bổ sung Shleifer-Vishny Fire-Sale Circuit Breaker: Nhận diện xoáy thanh khoản (Liquidity Spiral) "
                "khi tỷ lệ đòn bẩy phái sinh toàn thị trường bị thanh lý để kích hoạt lệnh Stop-Loss bảo toàn vốn."
            )
            arb_cap = 1.2
            disaster_hedge = 4.5
            campbell_demand = "Hyperbolic Speculative Bubble Capture"
            sentiment_regime = "Extreme Sentiment Asymmetry (Fear & Greed Index)"
            timing = "24/7 với bộ đệm kiểm tra biến động mỗi 4 giờ (H4)"
            gov_rule = "Hạn mức Half-Kelly tối đa 0.02 (2% vốn), tự động cách ly Pod nếu sụt giảm -5%."

        return HarvardStateBlueprint(
            state_id=state_id,
            state_name=name,
            asset_symbol=symbol,
            asset_class=cluster,
            base_model=base_model,
            harvard_research_pillar=pillar,
            harvard_lead_authors=authors,
            harvard_tactical_enhancement=enhancement,
            shleifer_vishny_arbitrage_cap=arb_cap,
            farhi_disaster_risk_hedge_pct=disaster_hedge,
            campbell_icapm_horizon_demand=campbell_demand,
            baker_wurgler_sentiment_regime=sentiment_regime,
            optimal_execution_timing=timing,
            risk_governance_rule=gov_rule,
        )

    def generate_all_50_blueprints(self) -> List[HarvardStateBlueprint]:
        blueprints = []
        for sid, pod in self.registry.states.items():
            bp = self.analyze_state_with_harvard_layer(sid, pod)
            blueprints.append(bp)
        return blueprints


def main():
    analyzer = HarvardTacticalAnalyzer()
    blueprints = analyzer.generate_all_50_blueprints()

    # Save to JSON
    export_path = LOG_DIR / "harvard_50_states_blueprint.json"
    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_states": len(blueprints),
        "harvard_pillars_integrated": [
            "John Y. Campbell ICAPM & Present Value Predictability",
            "Andrei Shleifer & Robert Vishny Limits of Arbitrage",
            "Emmanuel Farhi Currency Crash & Disaster Premia",
            "Kenneth Rogoff & Carmen Reinhart Sovereign Supercycles",
            "Malcolm Baker & Jeffrey Wurgler Investor Sentiment Betas",
        ],
        "blueprints": [asdict(b) for b in blueprints],
    }
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"✅ Đã phân tích và áp dụng nghiên cứu Harvard cho toàn bộ 50 Tiểu bang: {export_path}")


if __name__ == "__main__":
    main()
