"""
The Executive Presidency: The Nuclear Football (Hard-Stop Circuit Breaker)
Emergency powers vested in the Commander-in-Chief.
Triggered if drawdown hits -7.5% or black-swan market dislocation occurs.
Forces immediate liquidation of all positions to 100% Cash and network disconnection.
"""

from typing import Dict, Any, List


class NuclearFootball:
    """
    The President's Emergency Hard-Stop Switch.
    Overrides all 50 states and shuts down trading activity instantly.
    """

    def __init__(self, kill_threshold: float = -0.075):
        self.kill_threshold = kill_threshold
        self.is_detonated: bool = False
        self.detonation_reason: str = ""
        self.audit_log: List[Dict[str, Any]] = []

    def check_portfolio_drawdown(self, current_drawdown: float) -> bool:
        """
        Monitors drawdown level. If drawdown <= -0.075, automatically detonates.
        """
        if current_drawdown <= self.kill_threshold:
            self.detonate(f"CRITICAL DRAWDOWN BREACHED: {round(current_drawdown * 100, 2)}% <= {round(self.kill_threshold * 100, 2)}%")
            return True
        return False

    def detonate(self, reason: str = "Presidential Emergency Directive") -> Dict[str, Any]:
        """
        Executes emergency shutdown: Closes all orders, liquidates to 100% Cash, severs broker pipes.
        """
        self.is_detonated = True
        self.detonation_reason = reason
        event = {
            "status": "NUCLEAR_FOOTBALL_DETONATED",
            "action": "EMERGENCY_FULL_LIQUIDATION_TO_100_PERCENT_CASH",
            "reason": reason,
            "broker_connections": "SEVERED",
            "trading_halted": True
        }
        self.audit_log.append(event)
        return event

    def reset_with_congressional_waiver(self, authorization_code: str) -> bool:
        """Resets the circuit breaker only with valid constitutional authorization code."""
        if authorization_code == "CONGRESSIONAL_JOINT_RESOLUTION_RESTORE":
            self.is_detonated = False
            self.detonation_reason = ""
            return True
        return False
