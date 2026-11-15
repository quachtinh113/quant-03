"""
US Federation Quant Machine Package
Cấu trúc Quyền lực Liên bang Hoa Kỳ ứng dụng vào Hệ thống Giao dịch Định lượng Cấp Định chế.
"""

__all__ = ["FederationHub"]


def __getattr__(name):
    """Export lười để tránh vòng import (federation_hub nạp các layers, layers nạp contracts trong gói này)."""
    if name == "FederationHub":
        from .federation_hub import FederationHub
        return FederationHub
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
