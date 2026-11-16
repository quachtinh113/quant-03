import os, sys, psutil, time, json
from datetime import datetime, timezone, timedelta
sys.path.insert(0, r"C:\Quant_03")

import MetaTrader5 as mt5

def audit_all():
    results = {}
    
    # --- 1. SYSTEM & PROCESS HEALTH ---
    lock_path = r"C:\Quant_03\us_federation_quant\us_federation_quant.lock"
    results["lock_exists"] = os.path.exists(lock_path)
    
    runner_proc = None
    for p in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'memory_info']):
        try:
            cmd = " ".join(p.info['cmdline'] or [])
            if "live_federation_runner.py" in cmd:
                runner_proc = p
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
            
    if runner_proc:
        mem_mb = runner_proc.info['memory_info'].rss / (1024 * 1024)
        uptime_sec = time.time() - runner_proc.info['create_time']
        results["process"] = {
            "pid": runner_proc.pid,
            "uptime_str": str(timedelta(seconds=int(uptime_sec))),
            "memory_mb": round(mem_mb, 1),
            "status": "HEALTHY / RUNNING",
        }
    else:
        results["process"] = {"status": "NOT FOUND"}
        
    # --- 2. MT5 ACCOUNT & HEALTH ---
    if not mt5.initialize():
        results["mt5_error"] = "Failed to initialize MT5"
        print(json.dumps(results, indent=2))
        return

    terminal_info = mt5.terminal_info()
    ping = getattr(terminal_info, "ping_last", 0) / 1000.0 if terminal_info else 0.0
    results["ping_ms"] = round(ping, 1)

    acc = mt5.account_info()
    results["account"] = {
        "login": acc.login,
        "server": acc.server,
        "balance": acc.balance,
        "equity": acc.equity,
        "floating_pnl": round(acc.equity - acc.balance, 2),
    }
    
    # HWM
    hwm_path = r"C:\Quant_03\us_federation_quant\logs\high_water_mark_us_federation_quant.json"
    hwm_val = 7542.38
    if os.path.exists(hwm_path):
        try:
            with open(hwm_path, "r") as f:
                hwm_data = json.load(f)
                hwm_val = float(hwm_data.get("high_water_mark", 7542.38))
        except Exception:
            pass
    results["hwm"] = hwm_val
    dd_pct = ((acc.equity - hwm_val) / hwm_val) * 100.0 if hwm_val > 0 else 0.0
    results["drawdown_pct"] = round(dd_pct, 2)
    
    # --- 3. DEALS ATTRIBUTION (Past 24h & Post-Reload) ---
    now = datetime.now(timezone.utc)
    from_24h = now - timedelta(hours=24)
    reload_time = datetime(2026, 11, 16, 21, 57, 0, tzinfo=timezone.utc) # 04:57 GMT+7 is 21:57 UTC Nov 16
    
    deals_24h = mt5.history_deals_get(from_24h, now) or []
    closed_deals_24h = [d for d in deals_24h if d.entry in [1, 2]]
    closed_deals_post_reload = [d for d in closed_deals_24h if datetime.fromtimestamp(d.time, tz=timezone.utc) >= reload_time]
    
    pnl_24h = sum(d.profit + d.swap + d.commission for d in closed_deals_24h)
    pnl_post_reload = sum(d.profit + d.swap + d.commission for d in closed_deals_post_reload)
    
    results["pnl_24h"] = round(pnl_24h, 2)
    results["deals_count_24h"] = len(closed_deals_24h)
    results["pnl_post_reload"] = round(pnl_post_reload, 2)
    results["deals_count_post_reload"] = len(closed_deals_post_reload)
    
    # ECR distribution
    micro_wins = [d for d in closed_deals_24h if 0 < d.profit < 1.50]
    t2_wins = [d for d in closed_deals_24h if d.profit >= 4.50]
    t3_wins = [d for d in closed_deals_24h if d.profit >= 10.00]
    wins_24h = [d for d in closed_deals_24h if d.profit > 0]
    
    results["ecr_stats"] = {
        "total_wins": len(wins_24h),
        "micro_wins_under_1_50": len(micro_wins),
        "micro_win_pct": round((len(micro_wins) / max(len(wins_24h), 1)) * 100, 1),
        "t2_wins_count": len(t2_wins),
        "t3_wins_count": len(t3_wins),
    }

    # --- 4. REAL-TIME POSITION GUARD & RATCHET ---
    positions = mt5.positions_get() or []
    pos_data = []
    locked_profit_total = 0.0
    sltp_actions_executed = []
    
    current_hour_utc = now.hour
    is_golden_hour = 13 <= current_hour_utc <= 17
    t1_trigger = 4.80 if is_golden_hour else 4.00
    
    currency_exposure = {} # currency -> list of {direction, symbol, profit, is_locked}
    
    for p in positions:
        sym_info = mt5.symbol_info(p.symbol)
        pt = getattr(sym_info, "point", 0.0001) or 0.0001
        digits = getattr(sym_info, "digits", 2) or 2
        tick_sz = getattr(sym_info, "trade_tick_size", pt) or pt
        tick_val = getattr(sym_info, "trade_tick_value", 1.0) or 1.0
        val_per_price = (tick_val / tick_sz) * p.volume if tick_sz > 0 else p.volume
        pip_size = pt * 10.0 if digits in (3, 5) else pt
        min_stop_gap = max((getattr(sym_info, "spread", 2) + 2) * pt, 5 * pt)
        
        pos_dir = "BUY" if p.type == 0 else "SELL"
        profit = p.profit + p.swap + getattr(p, "commission", 0.0)
        sl = float(p.sl)
        entry = float(p.price_open)
        curr = float(p.price_current)
        
        # Check locked profit
        is_sl_in_profit = False
        locked_pnl = 0.0
        if pos_dir == "BUY" and sl > entry:
            is_sl_in_profit = True
            locked_pnl = (sl - entry) * val_per_price
        elif pos_dir == "SELL" and sl > 0 and sl < entry:
            is_sl_in_profit = True
            locked_pnl = (entry - sl) * val_per_price
            
        locked_profit_total += max(locked_pnl, 0.0)
        
        # Risk to SL
        if pos_dir == "BUY":
            loss_at_sl = (entry - sl) * val_per_price if sl > 0 else 999.0
        else:
            loss_at_sl = (sl - entry) * val_per_price if sl > 0 else 999.0
            
        # Check Ladder logic
        target_sl = sl
        tier_action = "NONE"
        if profit >= 14.50:
            tier_action = "TIER_3 (+10$ Lock)"
            dist_10usd = 10.0 / val_per_price
            calc_sl = round(entry + dist_10usd, digits) if pos_dir == "BUY" else round(entry - dist_10usd, digits)
            if pos_dir == "BUY" and calc_sl > target_sl and calc_sl < (curr - min_stop_gap):
                target_sl = calc_sl
            elif pos_dir == "SELL" and (target_sl == 0.0 or calc_sl < target_sl) and calc_sl > (curr + min_stop_gap):
                target_sl = calc_sl
        elif profit >= 8.50:
            tier_action = "TIER_2 (+4.50$ Lock)"
            dist_4_5usd = 4.50 / val_per_price
            calc_sl = round(entry + dist_4_5usd, digits) if pos_dir == "BUY" else round(entry - dist_4_5usd, digits)
            if pos_dir == "BUY" and calc_sl > target_sl and calc_sl < (curr - min_stop_gap):
                target_sl = calc_sl
            elif pos_dir == "SELL" and (target_sl == 0.0 or calc_sl < target_sl) and calc_sl > (curr + min_stop_gap):
                target_sl = calc_sl
        elif profit >= t1_trigger:
            tier_action = f"TIER_1 (+1.20$ Lock | Trig {t1_trigger})"
            dist_1_2usd = 1.20 / val_per_price
            be_offset = max(1.0 * pip_size, dist_1_2usd)
            calc_sl = round(entry + be_offset, digits) if pos_dir == "BUY" else round(entry - be_offset, digits)
            if pos_dir == "BUY" and calc_sl > target_sl and calc_sl < (curr - min_stop_gap):
                target_sl = calc_sl
            elif pos_dir == "SELL" and (target_sl == 0.0 or calc_sl < target_sl) and calc_sl > (curr + min_stop_gap):
                target_sl = calc_sl

        # If target_sl changed by more than 1.5 points, execute modification immediately!
        if abs(target_sl - sl) >= (1.5 * pt) and target_sl > 0:
            req = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": p.ticket,
                "symbol": p.symbol,
                "sl": target_sl,
                "tp": p.tp,
            }
            res = mt5.order_send(req)
            sltp_actions_executed.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "tier": tier_action,
                "old_sl": sl,
                "new_sl": target_sl,
                "retcode": getattr(res, "retcode", -1),
                "comment": getattr(res, "comment", "")
            })
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                sl = target_sl
                is_sl_in_profit = True
                if pos_dir == "BUY":
                    locked_pnl = (sl - entry) * val_per_price
                else:
                    locked_pnl = (entry - sl) * val_per_price

        # Currency breakdown
        sym_clean = p.symbol.upper().replace("M", "")
        for c in ["USD", "EUR", "GBP", "AUD", "JPY", "CHF", "CAD", "NZD"]:
            if c in sym_clean:
                # determine currency direction
                if sym_clean.startswith(c):
                    cur_dir = "LONG" if pos_dir == "BUY" else "SHORT"
                elif sym_clean.endswith(c):
                    cur_dir = "SHORT" if pos_dir == "BUY" else "LONG"
                else:
                    cur_dir = pos_dir
                currency_exposure.setdefault(c, []).append({
                    "symbol": p.symbol,
                    "cur_dir": cur_dir,
                    "ticket": p.ticket,
                    "profit": profit,
                    "is_locked": is_sl_in_profit
                })

        pos_data.append({
            "ticket": p.ticket,
            "symbol": p.symbol,
            "type": pos_dir,
            "volume": p.volume,
            "price_open": entry,
            "price_current": curr,
            "sl": sl,
            "tp": p.tp,
            "profit": round(profit, 2),
            "loss_at_sl": round(loss_at_sl, 2),
            "locked_profit": round(locked_pnl, 2) if is_sl_in_profit else 0.0,
            "is_sl_in_profit": is_sl_in_profit,
            "tier_status": tier_action,
        })
        
    results["positions"] = pos_data
    results["locked_profit_total"] = round(locked_profit_total, 2)
    results["sltp_actions_executed"] = sltp_actions_executed
    results["currency_exposure"] = currency_exposure

    # Target calculation: Net Realized 24h + Locked Profit
    effective_progress_pnl = pnl_24h + locked_profit_total
    results["effective_progress_pnl"] = round(effective_progress_pnl, 2)
    results["progress_pct_of_100usd"] = round((effective_progress_pnl / 100.0) * 100.0, 1)

    print(json.dumps(results, indent=2))
    mt5.shutdown()

if __name__ == "__main__":
    audit_all()
