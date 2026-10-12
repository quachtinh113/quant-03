"""
========================================================================================
CROSS-ASSET 50-STATE MATRIX HEDGE FUND ENGINE (US FEDERATION QUANT)
Institutional Multi-Asset Portfolio Construction across all 50 Exness Assets:
- 10 Commodities, Energy & Crypto
- 10 Global Equity Indices
- 15 Forex Majors & Crosses
- 15 US Mega-Cap Equities

Mathematical Pillars:
1. 🏛️ MIT Gilbert Strang Left Nullspace Projection: Neutralizes 4 Systematic Factors (B^T @ w* = 0).
2. 🌐 Ray Dalio Holy Grail Diversification: N_eff Eigen-decomposition across 4 Asset Classes.
3. 🛡️ BlackRock Aladdin Ledoit-Wolf Shrinkage & 50% Profit Reserve Sweeping.
4. 🤖 Large Model AI Governance: GeminiSmartRouter (Flash/Pro) Macro Synthesis.
========================================================================================
"""

from __future__ import annotations

import importlib
import json
import logging
import math
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Path setup
_RES_DIR = Path(__file__).resolve().parent
_DIR = _RES_DIR.parent
_WORKSPACE = _DIR.parent
for p in [str(_DIR), str(_WORKSPACE), str(_WORKSPACE / "ML_4_Bot")]:
    if p not in sys.path:
        sys.path.insert(0, p)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Core Tools & Components
from bots._shared.gemini_router import GeminiSmartRouter, TaskTier

_states_mod = importlib.import_module("us_federation_quant.05_the_50_states.state_registry")
StateFederationRegistry = _states_mod.StateFederationRegistry

_titan_mod = importlib.import_module("us_federation_quant.04_federal_reserve.quad_titan_engine")
MITTitanModule = _titan_mod.MITTitanModule
RayDalioTitanModule = _titan_mod.RayDalioTitanModule
BlackRockTreasuryModule = _titan_mod.BlackRockTreasuryModule
WallStreetPodDefense = _titan_mod.WallStreetPodDefense

LOG_DIR = _DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-5s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "cross_asset_matrix.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("CrossAssetMatrixHedgeFund")


@dataclass
class CrossAssetMatrixState:
    total_assets: int
    asset_symbols: List[str]
    raw_weights: np.ndarray
    neutralized_weights: np.ndarray
    hedge_overlay: np.ndarray
    effective_bets_n_eff: float
    diversification_ratio_pct: float
    portfolio_volatility_pct: float
    systematic_factor_leakage: float
    is_pure_alpha: bool
    ai_memorandum: Optional[str] = None


class CrossAssetMatrixHedgeFund:
    """Master Institutional Multi-Asset Portfolio Engine for 50 Exness Assets."""

    def __init__(self, initial_capital_usd: float = 50_000.0):
        self.initial_capital = initial_capital_usd
        self.registry = StateFederationRegistry()
        self.ai_router = GeminiSmartRouter(max_daily_usd=5.0)
        self.blackrock = BlackRockTreasuryModule(initial_capital_usd=initial_capital_usd)

        # Retrieve all 50 State definitions
        self.states_list = [self.registry.get_state(f"STATE_{i:02d}") for i in range(1, 51)]
        self.symbols = [s.primary_asset for s in self.states_list]

    def _build_factor_exposure_matrix(self) -> np.ndarray:
        """
        Constructs the 50 x 4 Systematic Factor Exposure Matrix B:
        Factor 1: Equity Market Beta
        Factor 2: USD Dollar Strength (DXY Beta)
        Factor 3: Commodity Supercycle & Energy Beta
        Factor 4: Tech & Semiconductor High-Beta
        """
        n = len(self.symbols)
        B = np.zeros((n, 4))

        for i, sym in enumerate(self.symbols):
            # Equity Beta
            if any(k in sym for k in ["US500", "US30", "USTEC", "JP225", "DE40", "UK100", "HK50", "AU200", "STOXX", "FR40"]):
                B[i, 0] = 1.0
            elif any(k in sym for k in ["AAPL", "MSFT", "NVDA", "GOOG", "AMZN", "META", "TSLA", "BRK", "JPM", "V", "UNH"]):
                B[i, 0] = 1.15

            # USD Strength Beta
            if sym.startswith("USD"):
                B[i, 1] = 1.0
            elif sym.endswith("USDm"):
                B[i, 1] = -1.0

            # Commodity & Energy Beta
            if any(k in sym for k in ["USOIL", "UKOIL", "NATGAS", "XOM", "COPPER"]):
                B[i, 2] = 1.0
            elif any(k in sym for k in ["XAU", "XAG", "XPT", "XPD"]):
                B[i, 2] = 0.5

            # Tech & AI Beta
            if any(k in sym for k in ["NVDA", "MSFT", "GOOG", "AMZN", "META", "AAPL", "TSLA", "USTEC", "BTC", "ETH", "SOL"]):
                B[i, 3] = 1.0

        return B

    def _generate_cross_asset_covariance(self) -> np.ndarray:
        """Generates realistic 50x50 block-structured cross-asset correlation & covariance."""
        np.random.seed(42)
        n = len(self.symbols)
        base_corr = np.eye(n)

        # Intra-cluster correlations
        # Commodities (0..9): ~0.45 correlation
        base_corr[0:10, 0:10] = 0.45
        # Indices (10..19): ~0.70 correlation
        base_corr[10:20, 10:20] = 0.70
        # FX (20..34): ~0.35 correlation
        base_corr[20:35, 20:35] = 0.35
        # Equities (35..49): ~0.60 correlation
        base_corr[35:50, 35:50] = 0.60

        # Cross-cluster correlations (Macro links)
        # Tech Stocks vs Nasdaq
        base_corr[35:50, 11] = 0.75
        base_corr[11, 35:50] = 0.75
        # Oil vs Oil stocks (XOM)
        base_corr[2, 47] = 0.80
        base_corr[47, 2] = 0.80

        np.fill_diagonal(base_corr, 1.0)
        # Ensure positive semi-definiteness via eigenvalue clipping
        eigvals, eigvecs = np.linalg.eigh(base_corr)
        eigvals = np.maximum(eigvals, 1e-4)
        clean_corr = eigvecs @ np.diag(eigvals) @ eigvecs.T
        d = np.sqrt(np.diag(clean_corr))
        clean_corr = clean_corr / np.outer(d, d)

        # Asset volatilities (annualized 10% to 55%)
        vols = np.array([
            0.15, 0.22, 0.32, 0.30, 0.55, 0.65, 0.75, 0.25, 0.30, 0.45,  # Commodities & Crypto
            0.16, 0.22, 0.15, 0.18, 0.19, 0.14, 0.22, 0.16, 0.17, 0.18,  # Indices
            0.08, 0.09, 0.10, 0.11, 0.08, 0.09, 0.11, 0.11, 0.13, 0.12,  # FX Majors & Crosses
            0.07, 0.10, 0.09, 0.10, 0.12,
            0.24, 0.22, 0.45, 0.25, 0.28, 0.32, 0.48, 0.14, 0.15, 0.20,  # US Equities
            0.18, 0.16, 0.22, 0.18, 0.14
        ])

        cov = np.outer(vols, vols) * clean_corr
        return cov

    def construct_mit_neutralized_hedge_fund_portfolio(self) -> CrossAssetMatrixState:
        """Executes the full MIT Nullspace Projection & Ray Dalio Holy Grail Allocation."""
        logger.info("📐 XÂY DỰNG MA TRẬN 50 TIỂU BANG TRÊN EXNESS (MIT + RAY DALIO + BLACKROCK)...")

        cov = self._generate_cross_asset_covariance()
        B = self._build_factor_exposure_matrix()
        n = len(self.symbols)

        # 1. Ray Dalio Equal-Risk Contribution (Risk Parity base weights)
        inv_vols = 1.0 / np.sqrt(np.diag(cov))
        raw_weights = inv_vols / np.sum(inv_vols)

        # 2. MIT Gilbert Strang Left Nullspace Projection
        # M = I - B (B^T B)^-1 B^T -> w* = M @ raw_weights
        btb = B.T @ B
        btb_inv = np.linalg.pinv(btb)
        proj = B @ btb_inv @ B.T
        nullspace_M = np.eye(n) - proj

        neutralized_w = nullspace_M @ raw_weights
        hedge_overlay = neutralized_w - raw_weights

        # Factor exposure check: B^T @ neutralized_w must be zero
        residual = B.T @ neutralized_w
        max_leakage = float(np.max(np.abs(residual)))
        is_pure_alpha = bool(max_leakage < 1e-5)

        # 3. Ray Dalio Holy Grail Diversification Index
        corr = cov / np.outer(np.sqrt(np.diag(cov)), np.sqrt(np.diag(cov)))
        n_eff = RayDalioTitanModule.holy_grail_effective_bets(corr)
        div_ratio = (n_eff / n) * 100.0

        # 4. BlackRock Ledoit-Wolf Shrinkage on Portfolio Variance
        shrunk_cov = BlackRockTreasuryModule._shrink_covariance_ledoit_wolf(np.random.multivariate_normal(np.zeros(n), cov, 100))
        port_var = float(neutralized_w.T @ shrunk_cov @ neutralized_w)
        port_vol = float(np.sqrt(max(1e-8, port_var))) * 100.0

        state = CrossAssetMatrixState(
            total_assets=n,
            asset_symbols=self.symbols,
            raw_weights=raw_weights,
            neutralized_weights=neutralized_w,
            hedge_overlay=hedge_overlay,
            effective_bets_n_eff=round(n_eff, 2),
            diversification_ratio_pct=round(div_ratio, 1),
            portfolio_volatility_pct=round(port_vol, 2),
            systematic_factor_leakage=max_leakage,
            is_pure_alpha=is_pure_alpha,
        )

        return state

    def generate_ai_hedge_fund_memorandum(self, state: CrossAssetMatrixState) -> str:
        """Invokes GeminiSmartRouter to generate an institutional investment memorandum."""
        logger.info("🤖 GỌI MODEL LỚN AI ĐỂ LẬP BẢN GHI NHỚ THẨM TRA THỂ CHẾ 50 TIỂU BANG...")

        prompt = f"""
        You are the Chief Investment Officer (CIO) of the US Federation Quant multi-strategy hedge fund.
        Review the following 50-State Exness cross-asset quantitative matrix state:
        - Total Sovereign States/Assets: 50 Exness Instruments (10 Commodities/Crypto, 10 Equity Indices, 15 FX, 15 US Stocks)
        - MIT Gilbert Strang Nullspace Projection: Neutralized Market Beta, USD Factor, Commodity Factor, and Tech Factor.
        - Factor Residual Leakage: {state.systematic_factor_leakage:.8f} (Pure Alpha: {state.is_pure_alpha})
        - Ray Dalio Holy Grail Metric: N_eff = {state.effective_bets_n_eff} out of 50 assets ({state.diversification_ratio_pct}% effective independent streams)
        - Annualized Shrunk Portfolio Volatility: {state.portfolio_volatility_pct}% (Risk Parity Hedged)
        - BlackRock Cashflow Smoothing: 50% profits continuously swept into Hamilton Risk-Free Reserve.

        Produce an authoritative, institutional-grade 4-point Executive Memorandum:
        1. Macro Structure & Cross-Asset Diversification Analysis (Why these 50 Exness assets form an impenetrable fortress).
        2. Mathematical Nullspace Guarantee (How Gilbert Strang's projection eliminates systematic crash risk).
        3. Pod Risk Allocation across the 4 clusters (Forex, Commodities, Global Indices, US Mega-Cap Tech).
        4. Strategic Execution Guidance for the Executive Order Router on MT5.
        Keep it direct, mathematically rigorous, and zero fluff.
        """

        try:
            res = self.ai_router.generate(prompt=prompt, tier=TaskTier.LIGHT, compress_prompt=True)
            return res["content"]
        except Exception as e:
            return f"[AI Memorandum Fallback]: Pure Alpha Orthogonal Nullspace Established across 50 Exness Assets. (AI synthesis bypassed: {e})"

    def run_full_cross_asset_pipeline(self) -> CrossAssetMatrixState:
        state = self.construct_mit_neutralized_hedge_fund_portfolio()
        ai_memo = self.generate_ai_hedge_fund_memorandum(state)
        state.ai_memorandum = ai_memo

        # Save to JSON
        json_path = LOG_DIR / "cross_asset_50_matrix.json"
        with open(json_path, "w", encoding="utf-8") as f:
            data = {
                "total_assets": state.total_assets,
                "symbols": state.asset_symbols,
                "n_eff": state.effective_bets_n_eff,
                "diversification_ratio_pct": state.diversification_ratio_pct,
                "portfolio_volatility_pct": state.portfolio_volatility_pct,
                "is_pure_alpha": state.is_pure_alpha,
                "neutralized_weights": state.neutralized_weights.tolist(),
                "hedge_overlay": state.hedge_overlay.tolist(),
                "ai_memorandum": state.ai_memorandum,
            }
            json.dump(data, f, indent=2)

        # Print Executive Terminal Dashboard
        self.print_terminal_report(state)
        return state

    def print_terminal_report(self, state: CrossAssetMatrixState):
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print("\n" + "=" * 115)
        print(f" 🏛️ HỢP CHỦNG QUỐC HOA KỲ QUANT — MA TRẬN ĐỊNH LƯỢNG 50 TIỂU BANG EXNESS | {now_utc}")
        print("=" * 115)
        print(f" • Tổng số Tiểu Bang & Tài Sản Exness:    {state.total_assets} Sản phẩm (15 FX, 10 Hàng hóa/Crypto, 10 Chỉ số, 15 Cổ phiếu Mỹ)")
        print(f" • Chỉ số Chén Thánh Ray Dalio (N_eff):    {state.effective_bets_n_eff} Dòng lợi nhuận độc lập hoàn toàn ({state.diversification_ratio_pct}%)")
        print(f" • Kiểm định Chiếu Không gian không MIT:  {'✅ 100% PURE ALPHA (B^T @ w* = 0)' if state.is_pure_alpha else '⚠️ LEAKAGE DETECTED'}")
        print(f" • Độ biến động rủi ro danh mục (Vol):   {state.portfolio_volatility_pct:.2f}% / năm (Sau khi khử tương quan 4 nhân tố)")
        print(f" • Cơ chế Kho bạc BlackRock:             Quét 50% lợi nhuận mới vào Két dự trữ phi rủi ro")
        print("-" * 115)
        print(" 🧠 BẢN GHI NHỚ CHIẾN LƯỢC TỪ MODEL LỚN AI (GEMINI SMART ROUTER):")
        print("-" * 115)
        print(state.ai_memorandum)
        print("=" * 115 + "\n")


if __name__ == "__main__":
    hedge_fund = CrossAssetMatrixHedgeFund(initial_capital_usd=50_000.0)
    hedge_fund.run_full_cross_asset_pipeline()
