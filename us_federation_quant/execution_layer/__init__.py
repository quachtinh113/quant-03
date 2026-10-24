"""
Execution Layer package for US Federation Quant.
Provides order execution, execution algorithms, and dynamic trailing stop managers.
"""

from .trailing_stop_manager import TrailingStopManager

__all__ = ["TrailingStopManager"]
