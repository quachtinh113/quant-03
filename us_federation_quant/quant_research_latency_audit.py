import re
from pathlib import Path
import pandas as pd

log_path = Path("c:/Quant_03/us_federation_quant/logs/us_federation_quant.log")
if not log_path.exists():
    print("Log not found.")
    exit(0)

# Extract Ping / Latency, Reconnects, Order execution latencies, Slippage
pings = []
reconnects = []
errors_10016 = []
errors_10018 = []
circuit_breakers = []

with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        # Match Ping: XX.Xms
        m_ping = re.search(r"Ping:\s*([\d\.]+)ms", line)
        if m_ping:
            pings.append(float(m_ping.group(1)))
        
        if "reconnect" in line.lower() or "disconnected" in line.lower():
            reconnects.append(line.strip()[:120])
            
        if "10016" in line or "Invalid stops" in line:
            errors_10016.append(line.strip()[:140])
            
        if "10018" in line or "Market closed" in line:
            errors_10018.append(line.strip()[:140])
            
        if "CIRCUIT BREAKER" in line:
            circuit_breakers.append(line.strip()[:140])

p_series = pd.Series(pings) if pings else pd.Series([30.0])
print("=" * 70)
print("EXECUTION DRAG & NETWORK LATENCY METRICS")
print("=" * 70)
print(f"Total Ping samples: {len(p_series)}")
print(f"Min Ping: {p_series.min():.1f} ms")
print(f"Mean Ping: {p_series.mean():.1f} ms")
print(f"Median Ping: {p_series.median():.1f} ms")
print(f"95th percentile Ping: {p_series.quantile(0.95):.1f} ms")
print(f"Max Ping: {p_series.max():.1f} ms")
print(f"Ping spikes (> 100ms): {(p_series > 100).sum()} times")
print(f"\nReconnect / Disconnect events: {len(reconnects)}")
print(f"10016 Invalid Stops errors: {len(errors_10016)}")
print(f"10018 Market Closed skips: {len(errors_10018)}")
print(f"Circuit Breaker trigger events: {len(circuit_breakers)}")
if errors_10016:
    print("\nSample 10016 errors:")
    for e in errors_10016[-3:]:
        print("  -", e)
if circuit_breakers:
    print("\nSample Circuit Breaker events:")
    for cb in circuit_breakers[-5:]:
        print("  -", cb)
