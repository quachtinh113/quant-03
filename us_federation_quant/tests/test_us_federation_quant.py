"""
Automated Unit & Integration Test Suite for US Federation Quant Architecture (us_federation_quant)
Validates Constitution, Congress Alpha, Supreme Court (with Trial Ledger & Black Swan Stress-Tester),
Executive Presidency, Federal Reserve, and 50 States.
"""

import os
import pytest
import numpy as np
import pandas as pd

from us_federation_quant.federation_hub import FederationHub
import importlib

_house_mod = importlib.import_module("us_federation_quant.01_congress_alpha.house_of_representatives.micro_features")
HouseOfRepresentatives = _house_mod.HouseOfRepresentatives

_senate_mod = importlib.import_module("us_federation_quant.01_congress_alpha.senate_macro.macro_regime")
SenateMacro = _senate_mod.SenateMacro

_congress_mod = importlib.import_module("us_federation_quant.01_congress_alpha.legislative_bills.bill_builder")
Congress = _congress_mod.Congress

_court_mod = importlib.import_module("us_federation_quant.02_supreme_court.cryptographic_warrant")
SupremeCourt = _court_mod.SupremeCourt
JudicialVetoError = _court_mod.JudicialVetoError

_dsr_mod = importlib.import_module("us_federation_quant.02_supreme_court.deflated_sharpe_test")
compute_dsr_and_psr = _dsr_mod.compute_dsr_and_psr

_ledger_mod = importlib.import_module("us_federation_quant.02_supreme_court.trial_ledger")
ImmutableTrialLedger = _ledger_mod.ImmutableTrialLedger

_vault_mod = importlib.import_module("us_federation_quant.02_supreme_court.cold_storage_vault")
ColdStorageOOSVault = _vault_mod.ColdStorageOOSVault

_swan_mod = importlib.import_module("us_federation_quant.02_supreme_court.black_swan_stress_tester")
BlackSwanStressTester = _swan_mod.BlackSwanStressTester

_exec_mod = importlib.import_module("us_federation_quant.03_executive_presidency.order_router.router")
ExecutiveOrderRouter = _exec_mod.ExecutiveOrderRouter
ExecutiveUnauthorizedError = _exec_mod.ExecutiveUnauthorizedError

_nf_mod = importlib.import_module("us_federation_quant.03_executive_presidency.nuclear_football_hardstop")
NuclearFootball = _nf_mod.NuclearFootball

_as_mod = importlib.import_module("us_federation_quant.03_executive_presidency.avellaneda_stoikov.engine")
AvellanedaStoikovEngine = _as_mod.AvellanedaStoikovEngine

_fed_mod = importlib.import_module("us_federation_quant.04_federal_reserve.dynamic_qe_qt_allocator")
FederalReserveAllocator = _fed_mod.FederalReserveAllocator

_cov_mod = importlib.import_module("us_federation_quant.04_federal_reserve.interest_rate_matrix")
ledoit_wolf_covariance_shrinkage = _cov_mod.ledoit_wolf_covariance_shrinkage

_states_mod = importlib.import_module("us_federation_quant.05_the_50_states.state_registry")
StateFederationRegistry = _states_mod.StateFederationRegistry


@pytest.fixture
def bullish_market_data():
    """Generates synthetic bullish market data for testing."""
    np.random.seed(101)
    n = 300
    returns = np.random.normal(0.001, 0.005, n)
    price = 2000.0 * np.exp(np.cumsum(returns))
    return pd.DataFrame({
        "open": price * 0.999,
        "high": price * 1.002,
        "low": price * 0.998,
        "close": price,
        "returns": returns,
        "volume": np.random.uniform(2000, 8000, n)
    })


def test_the_constitution_articles_exist():
    """Test 1: Articles 1 & 2 of the Constitution exist and are readable."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    art1_path = os.path.join(base_dir, "00_the_constitution", "article_1_max_drawdown.yaml")
    if not os.path.exists(art1_path):
        art1_path = os.path.join(base_dir, "us_federation_quant", "00_the_constitution", "article_1_max_drawdown.yaml")
    art2_path = os.path.join(base_dir, "00_the_constitution", "article_2_var_limits.yaml")
    if not os.path.exists(art2_path):
        art2_path = os.path.join(base_dir, "us_federation_quant", "00_the_constitution", "article_2_var_limits.yaml")
    assert os.path.exists(art1_path)
    assert os.path.exists(art2_path)


def test_congress_bicameral_voting(bullish_market_data):
    """Test 2: Congress House (Micro) & Senate (Macro) votes."""
    bill = Congress.deliberate_and_vote("XAUUSD", bullish_market_data, proposed_lots=5.0)
    assert bill.target_asset == "XAUUSD"
    assert bill.house_yes_votes > 0
    assert bill.senate_yes_votes > 0
    assert isinstance(bill.passed_bicameral, bool)


def test_immutable_trial_ledger_tracks_n():
    """Test 3: Immutable Trial Ledger logs experiments and prevents N-count tampering."""
    test_ledger_path = os.path.join(os.path.dirname(__file__), "test_ledger.jsonl")
    ledger = ImmutableTrialLedger(ledger_file_path=test_ledger_path)
    ledger.reset_ledger_for_testing()

    assert ledger.get_trial_count_for_asset("XAUUSD") == 1 # default base
    
    # Record 3 trials
    ledger.record_trial("researcher_01", "XAUUSD", "mean_reversion_fast", {"param": 10})
    ledger.record_trial("researcher_01", "XAUUSD", "mean_reversion_slow", {"param": 20})
    count = ledger.record_trial("researcher_01", "XAUUSD", "momentum_breakout", {"param": 50})
    
    assert count == 3
    assert ledger.get_trial_count_for_asset("XAUUSD") == 3
    ledger.reset_ledger_for_testing()


def test_cold_storage_vault_integrity():
    """Test 4: Cold Storage OOS Vault loads certified benchmark data."""
    vault = ColdStorageOOSVault()
    data = vault.load_oos_benchmark("XAUUSD")
    assert "close" in data.columns
    assert "returns" in data.columns
    assert len(data) >= 300


def test_black_swan_stress_tester():
    """Test 5: Black Swan Stress Tester generates crisis regimes and checks drawdown ceilings."""
    tester = BlackSwanStressTester()
    covid_df = tester.generate_covid_shock_data()
    assert len(covid_df) == 150
    assert np.std(covid_df["returns"]) > 0.02 # Confirms extreme volatility regime

    class MockBill:
        action = "BUY"

    report = tester.run_all_stress_scenarios(MockBill())
    assert "scenarios" in report
    assert "COVID_19_VOLATILITY_SPIKE" in report["scenarios"]
    assert "LIQUIDITY_FREEZE_CRASH" in report["scenarios"]


def test_supreme_court_dsr_and_warrant(bullish_market_data):
    """Test 6: Supreme Court blind trial, DSR check with ledger, and cryptographic warrant issuance."""
    bill = Congress.deliberate_and_vote("XAUUSD", bullish_market_data, proposed_lots=5.0)
    court = SupremeCourt(secret_key="TEST_SEAL")
    warrant = court.adjudicate_bill(bill, max_lots=5.0)
    assert warrant.verify_token("TEST_SEAL") is True
    assert warrant.verify_token("FAKE_KEY") is False
    assert warrant.authorized_lots == 5.0
    assert warrant.trials_count >= 1


def test_supreme_court_judicial_veto():
    """Test 7: Supreme Court exercises Judicial Veto on failing models."""
    court = SupremeCourt(secret_key="TEST_SEAL", min_dsr=0.9999) # Unattainable DSR
    class MockFailingBill:
        bill_id = "BILL_FAIL"
        target_asset = "XAUUSD"
        action = "SELL"
    with pytest.raises(JudicialVetoError):
        court.adjudicate_bill(MockFailingBill())


def test_executive_avellaneda_stoikov_and_order_routing(bullish_market_data):
    """Test 8: Avellaneda-Stoikov reservation pricing and order router slicing."""
    as_engine = AvellanedaStoikovEngine()
    quotes = as_engine.calculate_quotes(mid_price=2000.0, inventory_q=2.0, volatility_sigma=0.01)
    assert quotes["reservation_price"] < 2000.0 # Long inventory reduces reservation price
    assert quotes["optimal_ask"] > quotes["optimal_bid"]

    court = SupremeCourt(secret_key="TEST_SEAL")
    bill = Congress.deliberate_and_vote("XAUUSD", bullish_market_data, proposed_lots=5.0)
    warrant = court.adjudicate_bill(bill, max_lots=5.0)

    router = ExecutiveOrderRouter(secret_key="TEST_SEAL")
    slices = router.route_execution(warrant=warrant, market_mid_price=2000.0, fed_quota=4.0, slices=4)
    assert len(slices) == 4
    assert sum(s.lots for s in slices) == 4.0


def test_executive_nuclear_football_circuit_breaker():
    """Test 9: Nuclear Football hard-stop stops all trading and requires congressional waiver."""
    nf = NuclearFootball(kill_threshold=-0.075)
    assert nf.is_detonated is False
    detonated = nf.check_portfolio_drawdown(-0.08) # Exceeds -7.5%
    assert detonated is True
    assert nf.is_detonated is True

    # Attempt execution during hard-stop
    router = ExecutiveOrderRouter(secret_key="TEST_SEAL")
    router.nuclear_football = nf
    class MockWarrant:
        def verify_token(self, k): return True
    with pytest.raises(ExecutiveUnauthorizedError):
        router.route_execution(MockWarrant())

    # Congressional waiver resets
    assert nf.reset_with_congressional_waiver("WRONG_CODE") is False
    assert nf.reset_with_congressional_waiver("CONGRESSIONAL_JOINT_RESOLUTION_RESTORE") is True
    assert nf.is_detonated is False


def test_federal_reserve_qe_qt_and_ledoit_wolf():
    """Test 10: Federal Reserve QE/QT policy stance & Ledoit-Wolf shrinkage."""
    fed = FederalReserveAllocator(base_total_capital=10_000_000.0)
    
    # Stress test: high volatility triggers QT
    qt_stance = fed.determine_policy_stance(market_volatility=0.035)
    assert qt_stance["policy"] == "QT_QUANTITATIVE_TIGHTENING"
    assert qt_stance["quota_multiplier"] == 0.5

    # Calm market triggers QE
    qe_stance = fed.determine_policy_stance(market_volatility=0.008, avg_pod_sharpe=2.0)
    assert qe_stance["policy"] == "QE_QUANTITATIVE_EASING"
    assert qe_stance["quota_multiplier"] == 1.25

    # Ledoit-Wolf covariance shrinkage
    np.random.seed(42)
    sample_returns = pd.DataFrame(np.random.normal(0, 0.01, (100, 4)), columns=["P1", "P2", "P3", "P4"])
    quotas = fed.allocate_state_quotas(sample_returns)
    assert len(quotas) == 4
    assert abs(sum(quotas.values()) - 10_000_000.0) < 1.0


def test_50_states_sovereignty_and_quarantine():
    """Test 11: 50 State pods registry and localized bankruptcy quarantine."""
    registry = StateFederationRegistry()
    summary = registry.get_federation_summary()
    assert summary["total_states"] == 50
    assert summary["active_states"] == 50

    state_01 = registry.get_state("STATE_01")
    assert state_01 is not None
    assert state_01.primary_asset in ("XAUUSD", "XAUUSDm")

    # Simulate localized disaster in State 01 (-12% drawdown)
    active = state_01.update_performance(-0.12)
    assert active is False
    assert state_01.is_active is False

    # Check that quarantine isolates State 01 while other 49 states remain operational
    summary_after = registry.get_federation_summary()
    assert summary_after["active_states"] == 49
    assert summary_after["quarantined_states"] == 1


def test_federation_master_lifecycle_end_to_end(bullish_market_data):
    """Test 12: Full End-to-End Constitutional Lifecycle via FederationHub."""
    hub = FederationHub(secret_key="E2E_FEDERATION_SEAL")
    result = hub.process_order_lifecycle(
        asset="XAUUSD",
        market_data_df=bullish_market_data,
        proposed_lots=5.0,
        current_volatility=0.009
    )

    assert result["status"] == "EXECUTED"
    assert "bill_id" in result
    assert "warrant_id" in result
    assert result["micro_orders_count"] == 5
    assert result["fed_policy"] == "QE_QUANTITATIVE_EASING"


def test_quad_titan_engine_pillars():
    """Test 13: Quad-Titan Quantitative Foundation (MIT - Wall Street - Ray Dalio - BlackRock)."""
    import importlib
    mod = importlib.import_module("us_federation_quant.04_federal_reserve.quad_titan_engine")
    QuadTitanEngine = mod.QuadTitanEngine

    engine = QuadTitanEngine(initial_capital_usd=10_000.0)
    current_weights = np.array([0.2, 0.2, 0.2, 0.2, 0.2])
    returns_history = np.random.normal(0.001, 0.01, (50, 5))

    audit = engine.execute_quad_audit(
        current_equity=11_000.0,
        portfolio_drawdown=-0.01,
        current_weights=current_weights,
        returns_history=returns_history,
        growth_indicator=0.6,
        inflation_indicator=-0.1,
    )

    assert audit["status"] == "APPROVED"
    assert audit["nuclear_football_triggered"] is False

    # 1. MIT Pillar verification
    assert audit["mit_quantitative"]["is_strictly_factor_neutral"] is True
    assert "variance_ratio" in audit["mit_quantitative"]

    # 2. Wall Street Pillar verification
    assert audit["wall_street_defense"]["pod_status"] == "NORMAL_ACTIVE"
    assert audit["wall_street_defense"]["capital_multiplier"] == 1.0

    # 3. Ray Dalio Pillar verification
    assert "Goldilocks" in audit["ray_dalio_macro"]["regime"]
    assert audit["ray_dalio_macro"]["holy_grail_n_eff"] >= 1.0

    # 4. BlackRock Pillar verification (Cashflow sweep 50% profit to reserve)
    # Profit was $1,000 -> 50% = $500 swept. Initial reserve = $2,000 -> Total reserve = $2,500
    assert audit["blackrock_treasury"]["risk_free_reserve_usd"] == 2500.0
    assert audit["blackrock_treasury"]["cashflow_sweep_usd"] == 500.0


def test_elite_purified_whitelist_mode():
    """Test 14: Elite Purified Portfolio whitelist mode (19 active states, 31 quarantined)."""
    registry = StateFederationRegistry(elite_mode=True)
    active = registry.get_all_active_states()
    assert len(active) == 19
    summary = registry.get_federation_summary()
    assert summary["active_states"] == 19
    assert summary["quarantined_states"] == 31

    # Verify that blacklisted high-drawdown states are disabled
    assert registry.get_state("STATE_05").is_active is False # BTC
    assert registry.get_state("STATE_06").is_active is False # ETH
    assert registry.get_state("STATE_07").is_active is False # SOL
    assert registry.get_state("STATE_04").is_active is False # UKOIL
    assert registry.get_state("STATE_42").is_active is False # TSLA

    # Verify elite Forex & Indices are active
    assert registry.get_state("STATE_21").is_active is True # EURUSD
    assert registry.get_state("STATE_22").is_active is True # GBPUSD
    assert registry.get_state("STATE_26").is_active is True # USDCHF
    assert registry.get_state("STATE_12").is_active is True # USTEC
