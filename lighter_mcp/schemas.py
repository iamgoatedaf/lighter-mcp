"""Pydantic schemas for MCP tool inputs.

Schemas mirror the kit's CLI flags but use natural Python types and clear
descriptions so they render well in MCP tool catalogs (Cursor, Claude, etc.).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Side = Literal["buy", "sell", "long", "short"]
MarginMode = Literal["cross", "isolated"]
Resolution = Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

# Strict character set for any user-supplied identifier that ends up on a
# subprocess argv. We allow uppercase alphanumerics plus '_', '-', '.', '/'
# with a length cap. This blocks shell metacharacters and CLI flag injection
# (e.g. ``--side=long``) at the schema layer before we ever construct argv.
_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9._/-]{0,31}$")
_ASSET_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,15}$")


def _validate_symbol(v: str) -> str:
    v = v.strip().upper()
    if not _SYMBOL_RE.match(v):
        raise ValueError(
            "symbol must match [A-Z0-9][A-Z0-9._/-]{0,31}; "
            "got something with disallowed characters or wrong length"
        )
    return v


def _validate_asset(v: str) -> str:
    v = v.strip().upper()
    if not _ASSET_RE.match(v):
        raise ValueError(
            "asset must match [A-Z0-9][A-Z0-9._-]{0,15}; "
            "got something with disallowed characters or wrong length"
        )
    return v


def _validate_optional_symbol(v: str | None) -> str | None:
    if v is None:
        return None
    return _validate_symbol(v)


class _SymbolMixin(BaseModel):
    symbol: str = Field(
        ...,
        description="Symbol like BTC, ETH, SOL for perps; or ETH/USDC for spot.",
    )

    @field_validator("symbol")
    @classmethod
    def _norm_symbol(cls, v: str) -> str:
        return _validate_symbol(v)


# ----- Read-only tools -----------------------------------------------------


class MarketListInput(BaseModel):
    market_type: Literal["perp", "spot"] | None = Field(
        default=None, description="Filter by market type."
    )
    search: str | None = Field(
        default=None, description="Case-insensitive symbol substring filter."
    )


class SymbolInput(_SymbolMixin):
    pass


class MarketBookInput(_SymbolMixin):
    limit: int = Field(default=10, ge=1, le=200, description="Levels per side.")


class MarketTradesInput(_SymbolMixin):
    limit: int = Field(default=50, ge=1, le=500)


class MarketCandlesInput(_SymbolMixin):
    resolution: Resolution = Field(default="1h")
    count_back: int = Field(default=100, ge=1, le=1000)


class MarketStatsInput(BaseModel):
    symbol: str | None = Field(default=None)

    @field_validator("symbol")
    @classmethod
    def _v(cls, v: str | None) -> str | None:
        return _validate_optional_symbol(v)


class MarketFundingInput(_SymbolMixin):
    pass


class AccountInfoInput(BaseModel):
    account_index: int | None = Field(
        default=None,
        description="If omitted, uses the configured account from credentials.",
    )


class PortfolioPerformanceInput(BaseModel):
    resolution: Resolution = Field(default="1h")


class OrdersOpenInput(BaseModel):
    symbol: str | None = Field(default=None)

    @field_validator("symbol")
    @classmethod
    def _v(cls, v: str | None) -> str | None:
        return _validate_optional_symbol(v)


# ----- Paper trading -------------------------------------------------------


class PaperOrderMarketInput(_SymbolMixin):
    side: Side
    amount: float = Field(..., gt=0, description="Base-asset amount.")


class PaperOrderIocInput(_SymbolMixin):
    side: Side
    amount: float = Field(..., gt=0)
    price: float = Field(..., gt=0, description="Limit price for IOC.")


class PaperPositionsInput(BaseModel):
    symbol: str | None = Field(default=None)
    no_refresh: bool = Field(
        default=False,
        description="Use cached marks instead of refreshing snapshots.",
    )

    @field_validator("symbol")
    @classmethod
    def _v(cls, v: str | None) -> str | None:
        return _validate_optional_symbol(v)


class PaperTradesInput(BaseModel):
    symbol: str | None = Field(default=None)
    limit: int = Field(default=50, ge=1, le=500)

    @field_validator("symbol")
    @classmethod
    def _v(cls, v: str | None) -> str | None:
        return _validate_optional_symbol(v)


class PaperLiquidationInput(_SymbolMixin):
    no_refresh: bool = Field(default=False)


PaperTier = Literal[
    "standard",
    "premium",
    "premium_1",
    "premium_2",
    "premium_3",
    "premium_4",
    "premium_5",
    "premium_6",
    "premium_7",
]


class PaperSetTierInput(BaseModel):
    tier: PaperTier = Field(
        ...,
        description="Fee tier: standard, premium, premium_1 .. premium_7",
    )


class PaperInitInput(BaseModel):
    collateral: float | None = Field(
        default=None,
        gt=0,
        description="Starting USDC collateral. Defaults to the kit's value (10000) if unset.",
    )
    tier: PaperTier | None = Field(
        default=None,
        description="Fee tier. Defaults to the kit's value (premium) if unset.",
    )


class PaperResetInput(BaseModel):
    collateral: float | None = Field(
        default=None,
        gt=0,
        description="New starting USDC collateral. Defaults to the kit's value if unset.",
    )
    tier: PaperTier | None = Field(
        default=None,
        description="Fee tier. Defaults to the kit's value if unset.",
    )

    @field_validator("tier")
    @classmethod
    def _v(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-z][a-z0-9_]{0,31}$", v):
            raise ValueError("tier must match [a-z][a-z0-9_]{0,31}")
        return v


# ----- Live trading -------------------------------------------------------

_CONF_DESCR = (
    "Token returned by an earlier preview call. Omit on the first call to "
    "receive a preview; include it (with otherwise identical arguments) to "
    "execute. Required for high-risk actions when require_confirmation=true."
)


class LimitOrderInput(_SymbolMixin):
    side: Side
    amount: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    reduce_only: bool = False
    post_only: bool = False
    confirmation_id: str | None = Field(default=None, description=_CONF_DESCR)


class MarketOrderInput(_SymbolMixin):
    side: Side
    amount: float = Field(..., gt=0)
    slippage: float | None = Field(
        default=None,
        ge=0,
        le=0.5,
        description="Slippage budget as fraction (default 0.01 = 1%).",
    )
    confirmation_id: str | None = Field(default=None, description=_CONF_DESCR)


class ModifyOrderInput(_SymbolMixin):
    order_index: int
    price: float = Field(..., gt=0)
    amount: float = Field(..., gt=0)
    confirmation_id: str | None = Field(default=None, description=_CONF_DESCR)


class CancelOrderInput(_SymbolMixin):
    order_index: int


class CancelAllInput(BaseModel):
    confirmation_id: str | None = Field(default=None, description=_CONF_DESCR)


class CloseAllInput(BaseModel):
    slippage: float | None = Field(default=None, ge=0, le=0.5)
    with_cancel_all: bool = False
    confirmation_id: str | None = Field(default=None, description=_CONF_DESCR)


class SetLeverageInput(_SymbolMixin):
    leverage: int = Field(..., ge=1, le=100)
    margin_mode: MarginMode | None = None
    confirmation_id: str | None = Field(default=None, description=_CONF_DESCR)


class AdjustMarginInput(_SymbolMixin):
    amount: float = Field(..., gt=0)
    direction: Literal["add", "remove"]
    confirmation_id: str | None = Field(default=None, description=_CONF_DESCR)


class WithdrawInput(BaseModel):
    asset: str = Field(..., description="Asset symbol, e.g. USDC, ETH.")
    amount: float = Field(..., gt=0)
    route: Literal["perp", "spot"] = "perp"
    confirmation_id: str | None = Field(default=None, description=_CONF_DESCR)

    @field_validator("asset")
    @classmethod
    def _v(cls, v: str) -> str:
        return _validate_asset(v)


class TransferInput(BaseModel):
    asset: str
    amount: float = Field(..., gt=0)
    from_route: Literal["perp", "spot"]
    to_route: Literal["perp", "spot"]
    confirmation_id: str | None = Field(default=None, description=_CONF_DESCR)

    @field_validator("asset")
    @classmethod
    def _v(cls, v: str) -> str:
        return _validate_asset(v)


# ----- Confirmations ------------------------------------------------------


class ConfirmInput(BaseModel):
    confirmation_id: str = Field(
        ...,
        description=(
            "Confirmation id returned by the preview call. The user must "
            "explicitly include it to authorize execution."
        ),
    )
