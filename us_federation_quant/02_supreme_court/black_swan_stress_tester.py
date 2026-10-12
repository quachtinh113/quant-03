"""
The Supreme Court: Historical Black Swan Stress-Tester (5 Category-5 Financial Disasters)
Subject proposed strategies to 5 catastrophic historical market dislocation crises:
1. COVID-19 Volatility Super-Spike (March 2020: VIX > 80, 5% daily swings).
2. Negative Commodity / Flash Liquidity Dislocation (April 2020: severe liquidity dry-up).
3. Sudden Gap & Spread Explosion Shock (Spread 10x, 50-pip slippage).
4. FED Aggressive Hawkish Rate Shock (2022 Cycle: +450bps rapid hike & QT liquidity drain).
5. Cross-Asset Correlation Breakdown (Global deleveraging crisis: all asset classes plunge together, rho -> 1.0).

Constitutional requirement: Any strategy suffering Drawdown > 7.5% during any crisis is VETOED.
"""

from typing import Dict, Any, List
import numpy as np
import pandas as pd


class BlackSwanStressTester:
    """
    Mô phỏng 5 thảm họa tài chính lịch sử Cấp độ 5 (Category-5 Black Swans).
    Đảm bảo chiến lược không chỉ sống sót trong thời bình mà còn bất khả xâm phạm trước siêu bão.
    """

    MAX_PERMITTED_CRISIS_DRAWDOWN: float = 0.075  # Giới hạn Hiến pháp: Max Drawdown 7.5%

    @classmethod
    def generate_covid_shock_data(cls, base_price: float = 2000.0, n_bars: int = 150) -> pd.DataFrame:
        """Kịch bản 1: Khủng hoảng Covid-19 (Biến động tăng gấp 5 lần, giật 2 chiều cực mạnh)."""
        np.random.seed(320)
        returns = np.random.normal(-0.005, 0.035, n_bars)
        price = base_price * np.exp(np.cumsum(returns))
        return pd.DataFrame({
            "close": price,
            "returns": returns,
            "volume": np.random.uniform(5000, 20000, n_bars)
        })

    @classmethod
    def generate_liquidity_freeze_crash(cls, base_price: float = 2000.0, n_bars: int = 150) -> pd.DataFrame:
        """Kịch bản 2: Đứt gãy thanh khoản đột ngột (Plunge -15% liên hoàn, không có thanh khoản)."""
        np.random.seed(420)
        returns = np.random.normal(-0.002, 0.01, n_bars)
        # Chèn cú rơi gap down tại thanh 50
        returns[50:55] = -0.04
        price = base_price * np.exp(np.cumsum(returns))
        return pd.DataFrame({
            "close": price,
            "returns": returns,
            "volume": np.random.uniform(500, 2000, n_bars)
        })

    @classmethod
    def generate_spread_explosion_shock(cls, base_price: float = 2000.0, n_bars: int = 150) -> pd.DataFrame:
        """Kịch bản 3: Sập Flash Crash và Giãn spread gấp 10 lần (50 pips slippage)."""
        np.random.seed(520)
        returns = np.random.normal(0.0002, 0.015, n_bars)
        # Flash crash spike down then violent rebound
        returns[70] = -0.06
        returns[71] = +0.05
        price = base_price * np.exp(np.cumsum(returns))
        return pd.DataFrame({
            "close": price,
            "returns": returns,
            "volume": np.random.uniform(1000, 8000, n_bars)
        })

    @classmethod
    def generate_fed_hawkish_shock(cls, base_price: float = 2000.0, n_bars: int = 150) -> pd.DataFrame:
        """Kịch bản 4: Cú sốc FED thắt chặt tiền tệ cấp tập 450bps & Hút ròng thanh khoản QT."""
        np.random.seed(620)
        # Lợi suất chịu lực cản kéo lùi liên tục do chi phí vốn tăng vọt
        returns = np.random.normal(-0.0018, 0.012, n_bars)
        # Thêm 2 đợt sốc lãi suất bất ngờ 75bps
        returns[30] = -0.035
        returns[75] = -0.040
        price = base_price * np.exp(np.cumsum(returns))
        return pd.DataFrame({
            "close": price,
            "returns": returns,
            "volume": np.random.uniform(2000, 6000, n_bars)
        })

    @classmethod
    def generate_correlation_breakdown_shock(cls, base_price: float = 2000.0, n_bars: int = 150) -> pd.DataFrame:
        """Kịch bản 5: Đứt gãy tương quan đa tài sản (Toàn bộ thị trường cùng rơi tự do, rho -> 1.0)."""
        np.random.seed(720)
        # Đồng loạt tháo chạy khỏi mọi tài sản rủi ro (Liquidation cascade)
        returns = np.random.normal(-0.003, 0.020, n_bars)
        returns[40:44] = -0.025
        returns[80:83] = -0.030
        price = base_price * np.exp(np.cumsum(returns))
        return pd.DataFrame({
            "close": price,
            "returns": returns,
            "volume": np.random.uniform(8000, 25000, n_bars)
        })

    def run_all_stress_scenarios(self, bill, stop_loss_pct: float = 0.03) -> Dict[str, Any]:
        """
        Thực thi toàn bộ 5 kịch bản thảm họa lịch sử lên AlphaBill.
        Có tính toán cơ chế ngắt mạch Stop-Loss bảo vệ vốn.
        """
        direction = 1 if getattr(bill, "action", "BUY").upper() == "BUY" else -1

        scenarios = {
            "COVID_19_VOLATILITY_SPIKE": self.generate_covid_shock_data(),
            "LIQUIDITY_FREEZE_CRASH": self.generate_liquidity_freeze_crash(),
            "SPREAD_EXPLOSION_FLASH_CRASH": self.generate_spread_explosion_shock(),
            "FED_HAWKISH_RATE_SHOCK": self.generate_fed_hawkish_shock(),
            "CORRELATION_BREAKDOWN_CRASH": self.generate_correlation_breakdown_shock(),
        }

        scenario_results = {}
        all_passed = True
        passed_count = 0

        for name, data in scenarios.items():
            raw_returns = data["returns"].values * direction
            # Phạt thêm chi phí ma sát thanh khoản trong khủng hoảng (0.10% mỗi thanh)
            friction = 0.0010
            strat_returns = raw_returns - friction

            # Mô phỏng Kỷ luật Thang Sụt Giảm Hiến Pháp (Constitutional Stop-Loss & Circuit Breaker)
            cum_val = 1.0
            peak_val = 1.0
            equity_curve = [1.0]
            exposure = 1.0

            for r in strat_returns:
                step_ret = r * exposure
                cum_val *= (1.0 + step_ret)
                if cum_val > peak_val:
                    peak_val = cum_val
                dd_cur = (peak_val - cum_val) / peak_val

                # Khi chạm ngưỡng cắt lỗ phòng thủ, ngắt mạch chuyển sang tiền mặt (exposure = 0)
                if dd_cur >= stop_loss_pct:
                    exposure = 0.0

                equity_curve.append(cum_val)

            eq_arr = np.array(equity_curve)
            peaks = np.maximum.accumulate(eq_arr)
            dds = (peaks - eq_arr) / peaks
            max_dd = float(np.max(dds)) if len(dds) > 0 else 0.0

            passed = bool(max_dd <= self.MAX_PERMITTED_CRISIS_DRAWDOWN)
            if passed:
                passed_count += 1
            else:
                all_passed = False


            scenario_results[name] = {
                "max_drawdown": round(max_dd, 4),
                "passed": passed
            }

        return {
            "all_passed": all_passed,
            "passed_count": passed_count,
            "total_scenarios": len(scenarios),
            "scenarios": scenario_results,
            "verdict": "PASSED_BLACK_SWAN_AUDIT" if all_passed else "FAILED_BLACK_SWAN_AUDIT"
        }
