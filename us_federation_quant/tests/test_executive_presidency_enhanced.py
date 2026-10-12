"""
Enhanced Unit Tests for Khối Hành Pháp (The Executive Presidency):
1. Avellaneda-Stoikov Microstructure Quoting with Order Flow Imbalance (OFI).
2. Almgren-Chriss (2000) Optimal Liquidation Trajectory.
3. VWAP Profile Intraday Liquidity Slicing (U-shaped Volume Smile).
4. Market Impact & Kyle's Lambda Slippage Estimation.
5. Executive Order Router Multi-Strategy Execution (TWAP, VWAP, Almgren-Chriss).
6. MT5 MqlTradeRequest Payload Formatting & Validation.
"""

import importlib
import pytest

_exec_mod = importlib.import_module("us_federation_quant.03_executive_presidency")
AvellanedaStoikovEngine = _exec_mod.AvellanedaStoikovEngine
AlmgrenChrissExecutor = _exec_mod.AlmgrenChrissExecutor
VWAPProfileSlicer = _exec_mod.VWAPProfileSlicer
SlippageImpactModel = _exec_mod.SlippageImpactModel
ExecutiveOrderRouter = _exec_mod.ExecutiveOrderRouter
ExecutiveUnauthorizedError = _exec_mod.ExecutiveUnauthorizedError
MicroOrderSlice = _exec_mod.MicroOrderSlice
MT5PayloadBuilder = _exec_mod.MT5PayloadBuilder
MT5TradeAction = _exec_mod.MT5TradeAction
MT5OrderType = _exec_mod.MT5OrderType

_court_mod = importlib.import_module("us_federation_quant.02_supreme_court")
SupremeCourt = _court_mod.SupremeCourt
JudicialWarrant = _court_mod.JudicialWarrant

_bills_mod = importlib.import_module("us_federation_quant.01_congress_alpha.legislative_bills.bill_builder")
AlphaBill = _bills_mod.AlphaBill




# ---------------------------------------------------------
# 1. Avellaneda-Stoikov with Order Flow Imbalance Tests
# ---------------------------------------------------------

def test_avellaneda_stoikov_order_flow_imbalance():
    """
    Test that OFI dynamically skews the reservation price:
    - Positive OFI (buyer pressure) shifts reservation price upwards.
    - Negative OFI (seller pressure) shifts reservation price downwards.
    - Non-zero OFI widens the spread to compensate for adverse selection risk.
    """
    engine = AvellanedaStoikovEngine(gamma=0.1, kappa=1.5, ofi_sensitivity=0.3)
    mid = 2000.0
    vol = 0.015

    # Neutral OFI (baseline)
    quote_neutral = engine.calculate_quotes(mid_price=mid, inventory_q=0.0, volatility_sigma=vol, order_flow_imbalance=0.0)
    # Positive OFI (+0.8 buyer dominance)
    quote_bullish = engine.calculate_quotes(mid_price=mid, inventory_q=0.0, volatility_sigma=vol, order_flow_imbalance=0.8)
    # Negative OFI (-0.8 seller dominance)
    quote_bearish = engine.calculate_quotes(mid_price=mid, inventory_q=0.0, volatility_sigma=vol, order_flow_imbalance=-0.8)

    # Bullish OFI should result in higher reservation price than neutral
    assert quote_bullish["reservation_price"] > quote_neutral["reservation_price"]
    # Bearish OFI should result in lower reservation price than neutral
    assert quote_bearish["reservation_price"] < quote_neutral["reservation_price"]

    # Adverse selection: both +0.8 and -0.8 OFI should have wider spreads than neutral
    assert quote_bullish["spread"] > quote_neutral["spread"]
    assert quote_bearish["spread"] > quote_neutral["spread"]


# ---------------------------------------------------------
# 2. Almgren-Chriss Optimal Trajectory Tests
# ---------------------------------------------------------

def test_almgren_chriss_trajectory():
    """
    Test Almgren-Chriss liquidation trajectory:
    - Slices sum up exactly to initial inventory (total_lots).
    - Higher risk aversion produces more aggressive front-loading.
    """
    total_lots = 10.0
    n_slices = 5

    # Low risk aversion (near TWAP)
    executor_neutral = AlmgrenChrissExecutor(risk_aversion_lambda=1e-8, temp_impact_eta=1e-2)
    traj_neutral = executor_neutral.calculate_trajectory(total_lots=total_lots, volatility_sigma=0.01, n_slices=n_slices)

    # High risk aversion (urgent liquidation, kappa >> 1)
    executor_averse = AlmgrenChrissExecutor(risk_aversion_lambda=100.0, temp_impact_eta=1e-2)
    traj_averse = executor_averse.calculate_trajectory(total_lots=total_lots, volatility_sigma=0.2, n_slices=n_slices)

    # Exact lot conservation
    sum_neutral = round(sum(s["slice_lots"] for s in traj_neutral), 2)
    sum_averse = round(sum(s["slice_lots"] for s in traj_averse), 2)
    assert sum_neutral == total_lots
    assert sum_averse == total_lots

    # High risk aversion should execute more lots in step 1 than low risk aversion
    assert traj_averse[0]["slice_lots"] > traj_neutral[0]["slice_lots"]
    # Final slice in high risk aversion should be smaller than in low risk aversion
    assert traj_averse[-1]["slice_lots"] <= traj_neutral[-1]["slice_lots"]


# ---------------------------------------------------------
# 3. VWAP U-Curve Liquidity Slicing Tests
# ---------------------------------------------------------

def test_vwap_u_curve_slicing():
    """
    Test VWAP U-curve profile:
    - Slices sum to total_lots.
    - Slices at open (first) and close (last) are larger than midday (middle).
    """
    slicer = VWAPProfileSlicer(curvature=2.5, base_liquidity_floor=0.4)
    total_lots = 7.5
    n_slices = 5

    slices = slicer.slice_order(total_lots=total_lots, n_slices=n_slices)
    assert len(slices) == n_slices

    total_sliced = round(sum(s["slice_lots"] for s in slices), 2)
    assert total_sliced == total_lots

    # U-shape verification: first slice (open) and last slice (close) > middle slice (midday)
    mid_idx = n_slices // 2
    assert slices[0]["slice_lots"] > slices[mid_idx]["slice_lots"]
    assert slices[-1]["slice_lots"] > slices[mid_idx]["slice_lots"]


# ---------------------------------------------------------
# 4. Market Impact & Slippage Model Tests
# ---------------------------------------------------------

def test_slippage_impact_model():
    """
    Test Kyle's lambda & Square-Root market impact model:
    - Impact increases with order volume.
    - Exceeds ADV cap flag triggers when participation is too high.
    """
    model = SlippageImpactModel(temp_coefficient=0.5, perm_coefficient=0.1, adv_participation_cap=0.05)

    # Small order (1.0 lot out of 10,000 ADV)
    small_impact = model.estimate_impact(order_lots=1.0, mid_price=2000.0, daily_adv_lots=10000.0, execution_window_fraction=0.1)
    assert small_impact["total_impact_bps"] > 0
    assert small_impact["exceeds_adv_cap"] is False

    # Huge order (100.0 lots out of 1,000 ADV window) -> participation = 10% > 5% cap
    huge_impact = model.estimate_impact(order_lots=100.0, mid_price=2000.0, daily_adv_lots=10000.0, execution_window_fraction=0.1)
    assert huge_impact["total_impact_bps"] > small_impact["total_impact_bps"]
    assert huge_impact["exceeds_adv_cap"] is True
    assert huge_impact["total_slippage_cost"] > small_impact["total_slippage_cost"]


# ---------------------------------------------------------
# 5. Order Router Multi-Strategy & Security Tests
# ---------------------------------------------------------

def test_executive_router_multi_strategy_execution():
    """
    Test ExecutiveOrderRouter executing TWAP, VWAP, and Almgren-Chriss strategies
    under authentic Judicial Warrant authorization.
    """
    secret_key = "TOP_SECRET_SCOTUS_KEY"
    court = SupremeCourt(secret_key=secret_key)
    router = ExecutiveOrderRouter(secret_key=secret_key)

    dummy_bill = AlphaBill(
        bill_id="BILL-EXEC-001",
        target_asset="XAUUSD",
        action="BUY",
        target_lots=6.0,
        house_yes_votes=390,
        senate_yes_votes=90,
        micro_score=0.85,
        variance_ratio=1.40,
        regime="MOMENTUM_TREND",
        timestamp=2000.0,
        passed_bicameral=True
    )

    warrant = court.adjudicate_bill(dummy_bill, max_lots=6.0)
    assert warrant.verify_token(secret_key) is True



    # 1. TWAP routing
    twap_slices = router.route_execution(
        warrant=warrant,
        market_mid_price=2050.0,
        slices=3,
        execution_strategy="TWAP"
    )
    assert len(twap_slices) == 3
    assert round(sum(s.lots for s in twap_slices), 2) == 6.0
    assert all(s.order_type == "LIMIT_SKEWED_TWAP" for s in twap_slices)

    # 2. VWAP routing
    vwap_slices = router.route_execution(
        warrant=warrant,
        market_mid_price=2050.0,
        slices=5,
        execution_strategy="VWAP"
    )
    assert len(vwap_slices) == 5
    assert round(sum(s.lots for s in vwap_slices), 2) == 6.0
    assert all(s.order_type == "LIMIT_SKEWED_VWAP" for s in vwap_slices)

    # 3. Almgren-Chriss routing
    ac_slices = router.route_execution(
        warrant=warrant,
        market_mid_price=2050.0,
        slices=4,
        execution_strategy="ALMGREN_CHRISS"
    )
    assert len(ac_slices) == 4
    assert round(sum(s.lots for s in ac_slices), 2) == 6.0
    assert all(s.order_type == "LIMIT_SKEWED_ALMGREN_CHRISS" for s in ac_slices)

    # 4. Routed history inspection
    assert len(router.routed_history) == 3
    assert "impact_analysis" in router.routed_history[-1]


# ---------------------------------------------------------
# 6. MT5 Payload Builder & Translation Tests
# ---------------------------------------------------------

def test_mt5_payload_builder():
    """
    Test converting MicroOrderSlices into standard MT5 MqlTradeRequest payloads.
    """
    builder = MT5PayloadBuilder(default_magic=999888, default_deviation_points=20)

    slice_order = MicroOrderSlice(
        slice_index=1,
        total_slices=4,
        asset="XAUUSD",
        action="BUY",
        lots=1.5,
        target_price=2051.25,
        order_type="LIMIT_SKEWED_VWAP"
    )

    req = builder.build_trade_request(
        slice_order=slice_order,
        sl_price=2030.0,
        tp_price=2090.0
    )

    assert req["symbol"] == "XAUUSD"
    assert req["volume"] == 1.5
    assert req["price"] == 2051.25
    assert req["sl"] == 2030.0
    assert req["tp"] == 2090.0
    assert req["deviation"] == 20
    assert req["magic"] == 999888
    assert req["action"] == MT5TradeAction.TRADE_ACTION_PENDING
    assert req["type"] == MT5OrderType.ORDER_TYPE_BUY_LIMIT
    assert "FED_1/4" in req["comment"]

    # Validate schema
    assert builder.validate_trade_request(req) is True

    # Invalid request should fail validation
    invalid_req = dict(req)
    invalid_req["volume"] = 0.001  # below min lot 0.01
    assert builder.validate_trade_request(invalid_req) is False
