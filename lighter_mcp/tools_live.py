"""Live trading MCP tools.

Each write tool runs through:
    1. ``Safety`` validation (mode, allowlist, leverage cap, notional caps).
    2. Optional two-step confirmation via ``ConfirmationStore``.
    3. ``KitRunner`` invocation of ``trade.py``.
    4. ``AuditLog`` envelope including the canonical args and confirmation id.

A failed gate or a missing confirmation always returns a structured payload
(no exceptions cross the MCP boundary) so the caller can render the preview
to the user and re-issue the call with the token.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .confirmations import ConfirmationError
from .runner import RunnerError
from .safety import SafetyError
from .schemas import (
    AdjustMarginInput,
    CancelAllInput,
    CancelOrderInput,
    CloseAllInput,
    LimitOrderInput,
    MarketOrderInput,
    ModifyOrderInput,
    SetLeverageInput,
)

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP

    from .server import ServerContext


def _safety_envelope(error: SafetyError) -> dict[str, Any]:
    return {"ok": False, "error": str(error), "category": "safety"}


def _confirmation_envelope(error: ConfirmationError) -> dict[str, Any]:
    return {"ok": False, "error": str(error), "category": "confirmation"}


def _preview_envelope(
    *, tool: str, plan: dict[str, Any], confirmation_id: str, expires_at: float
) -> dict[str, Any]:
    return {
        "ok": True,
        "stage": "preview",
        "tool": tool,
        "plan": plan,
        "confirmation_id": confirmation_id,
        "expires_at": expires_at,
        "next": (
            "Show this plan to the user. To execute, call the same tool with the "
            "same arguments and confirmation_id set to the value above."
        ),
    }


async def _estimate_notional_usd(
    ctx: ServerContext, *, symbol: str, amount: float, price_hint: float | None
) -> float | None:
    """Best-effort notional estimate for risk gates.

    Uses ``price_hint`` when provided (e.g. limit orders). Otherwise queries
    market_stats to grab a recent price. Returns ``None`` if no price is
    available; callers must decide whether that's a hard block or a soft skip.
    """
    if price_hint is not None:
        return abs(amount * price_hint)
    try:
        result = await ctx.runner.run("query.py", ["market", "stats", "--symbol", symbol])
    except RunnerError:
        return None
    data = result.data
    candidates = data if isinstance(data, list) else [data]
    for entry in candidates:
        if not isinstance(entry, dict):
            continue
        for key in ("last_trade_price", "mark_price", "index_price", "price"):
            value = entry.get(key)
            if isinstance(value, (int, float)) and value > 0:
                return abs(amount * float(value))
    return None


def register_live_tools(app: FastMCP, ctx: ServerContext) -> None:
    safety = ctx.safety
    confirmations = ctx.confirmations
    require_confirmation = ctx.config.live.require_confirmation

    def _maybe_preview(
        *, tool: str, args_dict: dict[str, Any], confirmation_id: str | None, plan: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Return a preview envelope if confirmation is required and missing.

        Otherwise validate the supplied confirmation_id (raising ConfirmationError
        on mismatch) and return None to signal the caller may proceed.
        """
        canonical = {k: v for k, v in args_dict.items() if k != "confirmation_id"}
        if not require_confirmation:
            return None
        if confirmation_id is None:
            token, expires_at = confirmations.issue(tool=tool, args=canonical)
            return _preview_envelope(
                tool=tool, plan=plan, confirmation_id=token, expires_at=expires_at
            )
        confirmations.consume(tool=tool, args=canonical, token=confirmation_id)
        return None

    # ------------------------------------------------------------------
    # order limit
    # ------------------------------------------------------------------
    @app.tool(
        name="lighter_live_limit_order",
        description=(
            "Place a live limit order on Lighter. First call returns a preview "
            "and confirmation_id; second call (with the same args plus the id) "
            "executes."
        ),
    )
    async def lighter_live_limit_order(input: LimitOrderInput) -> Any:
        try:
            safety.require_live_enabled()
            safety.check_symbol_allowed(input.symbol)
            notional = abs(input.amount * input.price)
            safety.check_order_notional(notional)
            safety.check_daily_room(notional)
        except SafetyError as exc:
            return _safety_envelope(exc)

        plan = {
            "action": "place_limit_order",
            "symbol": input.symbol,
            "side": input.side,
            "amount": input.amount,
            "price": input.price,
            "estimated_notional_usd": notional,
            "reduce_only": input.reduce_only,
            "post_only": input.post_only,
        }
        try:
            preview = _maybe_preview(
                tool="lighter_live_limit_order",
                args_dict=input.model_dump(),
                confirmation_id=input.confirmation_id,
                plan=plan,
            )
        except ConfirmationError as exc:
            return _confirmation_envelope(exc)
        if preview is not None:
            return preview

        argv = [
            "order",
            "limit",
            input.symbol,
            "--side",
            input.side,
            "--amount",
            str(input.amount),
            "--price",
            str(input.price),
        ]
        if input.reduce_only:
            argv.append("--reduce_only")
        if input.post_only:
            argv.append("--post_only")
        result = await ctx.run_kit(
            tool="lighter_live_limit_order", script="trade.py", args=argv
        )
        if isinstance(result, dict) and "error" not in result:
            safety.record_executed_notional(notional)
        return result

    # ------------------------------------------------------------------
    # order market
    # ------------------------------------------------------------------
    @app.tool(
        name="lighter_live_market_order",
        description=(
            "Place a live market order with a slippage budget. Two-step "
            "confirmation when require_confirmation=true."
        ),
    )
    async def lighter_live_market_order(input: MarketOrderInput) -> Any:
        try:
            safety.require_live_enabled()
            safety.check_symbol_allowed(input.symbol)
        except SafetyError as exc:
            return _safety_envelope(exc)

        notional = await _estimate_notional_usd(
            ctx, symbol=input.symbol, amount=input.amount, price_hint=None
        )
        if notional is None:
            return {
                "ok": False,
                "category": "safety",
                "error": (
                    "Cannot estimate notional for market order: price feed unavailable. "
                    "Refusing to place order without a notional check (fail-closed)."
                ),
            }
        try:
            safety.check_order_notional(notional)
            safety.check_daily_room(notional)
        except SafetyError as exc:
            return _safety_envelope(exc)

        plan = {
            "action": "place_market_order",
            "symbol": input.symbol,
            "side": input.side,
            "amount": input.amount,
            "slippage": input.slippage if input.slippage is not None else 0.01,
            "estimated_notional_usd": notional,
        }
        try:
            preview = _maybe_preview(
                tool="lighter_live_market_order",
                args_dict=input.model_dump(),
                confirmation_id=input.confirmation_id,
                plan=plan,
            )
        except ConfirmationError as exc:
            return _confirmation_envelope(exc)
        if preview is not None:
            return preview

        argv = [
            "order",
            "market",
            input.symbol,
            "--side",
            input.side,
            "--amount",
            str(input.amount),
        ]
        if input.slippage is not None:
            argv += ["--slippage", str(input.slippage)]
        result = await ctx.run_kit(
            tool="lighter_live_market_order", script="trade.py", args=argv
        )
        if isinstance(result, dict) and "error" not in result:
            safety.record_executed_notional(notional)
        return result

    # ------------------------------------------------------------------
    # order modify
    # ------------------------------------------------------------------
    @app.tool(
        name="lighter_live_modify_order",
        description="Modify an open order's price and/or amount. Confirmation required.",
    )
    async def lighter_live_modify_order(input: ModifyOrderInput) -> Any:
        # We can't know the previous order's notional without an extra round-trip
        # to the kit, so we treat the *new* notional as fully fresh exposure for
        # both per-order and daily caps. This may double-count vs the original
        # order but it's the conservative (fail-closed) default. The day's
        # rolling cap therefore correctly limits how much ammo a modify can add.
        try:
            safety.require_live_enabled()
            safety.check_symbol_allowed(input.symbol)
            notional = abs(input.amount * input.price)
            safety.check_order_notional(notional)
            safety.check_daily_room(notional)
        except SafetyError as exc:
            return _safety_envelope(exc)

        plan = {
            "action": "modify_order",
            "symbol": input.symbol,
            "order_index": input.order_index,
            "new_price": input.price,
            "new_amount": input.amount,
            "estimated_notional_usd": notional,
        }
        try:
            preview = _maybe_preview(
                tool="lighter_live_modify_order",
                args_dict=input.model_dump(),
                confirmation_id=input.confirmation_id,
                plan=plan,
            )
        except ConfirmationError as exc:
            return _confirmation_envelope(exc)
        if preview is not None:
            return preview

        result = await ctx.run_kit(
            tool="lighter_live_modify_order",
            script="trade.py",
            args=[
                "order",
                "modify",
                input.symbol,
                "--order_index",
                str(input.order_index),
                "--price",
                str(input.price),
                "--amount",
                str(input.amount),
            ],
        )
        if isinstance(result, dict) and "error" not in result:
            safety.record_executed_notional(notional)
        return result

    # ------------------------------------------------------------------
    # order cancel (single)
    # ------------------------------------------------------------------
    @app.tool(
        name="lighter_live_cancel_order",
        description="Cancel a single open order. Low-risk; no confirmation required.",
    )
    async def lighter_live_cancel_order(input: CancelOrderInput) -> Any:
        try:
            safety.require_live_enabled()
            safety.check_symbol_allowed(input.symbol)
        except SafetyError as exc:
            return _safety_envelope(exc)
        return await ctx.run_kit(
            tool="lighter_live_cancel_order",
            script="trade.py",
            args=[
                "order",
                "cancel",
                input.symbol,
                "--order_index",
                str(input.order_index),
            ],
        )

    # ------------------------------------------------------------------
    # order cancel_all
    # ------------------------------------------------------------------
    @app.tool(
        name="lighter_live_cancel_all",
        description="Cancel every open order across all markets. Confirmation required.",
    )
    async def lighter_live_cancel_all(input: CancelAllInput) -> Any:
        try:
            safety.require_live_enabled()
        except SafetyError as exc:
            return _safety_envelope(exc)

        plan = {
            "action": "cancel_all_orders",
            "scope": "all markets",
            "warning": "TP/SL bracket orders will also be cancelled.",
        }
        try:
            preview = _maybe_preview(
                tool="lighter_live_cancel_all",
                args_dict=input.model_dump(),
                confirmation_id=input.confirmation_id,
                plan=plan,
            )
        except ConfirmationError as exc:
            return _confirmation_envelope(exc)
        if preview is not None:
            return preview

        return await ctx.run_kit(
            tool="lighter_live_cancel_all",
            script="trade.py",
            args=["order", "cancel_all"],
        )

    # ------------------------------------------------------------------
    # order close_all (uses kit's --preview for the plan body)
    # ------------------------------------------------------------------
    @app.tool(
        name="lighter_live_close_all",
        description=(
            "Flatten every open position via reduce-only market orders. ALWAYS "
            "previewed first using the kit's own --preview path. Confirmation "
            "required to execute."
        ),
    )
    async def lighter_live_close_all(input: CloseAllInput) -> Any:
        try:
            safety.require_live_enabled()
        except SafetyError as exc:
            return _safety_envelope(exc)

        preview_argv = ["order", "close_all", "--preview"]
        if input.slippage is not None:
            preview_argv += ["--slippage", str(input.slippage)]
        if input.with_cancel_all:
            preview_argv.append("--with_cancel_all")
        kit_preview = await ctx.run_kit(
            tool="lighter_live_close_all_preview",
            script="trade.py",
            args=preview_argv,
        )
        if isinstance(kit_preview, dict) and "error" in kit_preview and "preview" not in kit_preview:
            return kit_preview

        plan = {
            "action": "close_all_positions",
            "with_cancel_all": input.with_cancel_all,
            "slippage": input.slippage if input.slippage is not None else 0.01,
            "kit_preview": kit_preview,
        }
        try:
            preview = _maybe_preview(
                tool="lighter_live_close_all",
                args_dict=input.model_dump(),
                confirmation_id=input.confirmation_id,
                plan=plan,
            )
        except ConfirmationError as exc:
            return _confirmation_envelope(exc)
        if preview is not None:
            return preview

        argv = ["order", "close_all"]
        if input.slippage is not None:
            argv += ["--slippage", str(input.slippage)]
        if input.with_cancel_all:
            argv.append("--with_cancel_all")
        return await ctx.run_kit(
            tool="lighter_live_close_all", script="trade.py", args=argv
        )

    # ------------------------------------------------------------------
    # position leverage
    # ------------------------------------------------------------------
    @app.tool(
        name="lighter_live_set_leverage",
        description="Set leverage for a perp market. Confirmation required.",
    )
    async def lighter_live_set_leverage(input: SetLeverageInput) -> Any:
        try:
            safety.require_live_enabled()
            safety.check_symbol_allowed(input.symbol)
            safety.check_leverage(input.leverage)
        except SafetyError as exc:
            return _safety_envelope(exc)

        plan = {
            "action": "set_leverage",
            "symbol": input.symbol,
            "leverage": input.leverage,
            "margin_mode": input.margin_mode or "cross",
        }
        try:
            preview = _maybe_preview(
                tool="lighter_live_set_leverage",
                args_dict=input.model_dump(),
                confirmation_id=input.confirmation_id,
                plan=plan,
            )
        except ConfirmationError as exc:
            return _confirmation_envelope(exc)
        if preview is not None:
            return preview

        argv = [
            "position",
            "leverage",
            input.symbol,
            "--leverage",
            str(input.leverage),
        ]
        if input.margin_mode:
            argv += ["--margin_mode", input.margin_mode]
        return await ctx.run_kit(
            tool="lighter_live_set_leverage", script="trade.py", args=argv
        )

    # ------------------------------------------------------------------
    # position margin
    # ------------------------------------------------------------------
    @app.tool(
        name="lighter_live_adjust_margin",
        description=(
            "Add or remove isolated margin collateral for a perp market. "
            "Confirmation required."
        ),
    )
    async def lighter_live_adjust_margin(input: AdjustMarginInput) -> Any:
        try:
            safety.require_live_enabled()
            safety.check_symbol_allowed(input.symbol)
        except SafetyError as exc:
            return _safety_envelope(exc)

        plan = {
            "action": "adjust_margin",
            "symbol": input.symbol,
            "amount": input.amount,
            "direction": input.direction,
        }
        try:
            preview = _maybe_preview(
                tool="lighter_live_adjust_margin",
                args_dict=input.model_dump(),
                confirmation_id=input.confirmation_id,
                plan=plan,
            )
        except ConfirmationError as exc:
            return _confirmation_envelope(exc)
        if preview is not None:
            return preview

        return await ctx.run_kit(
            tool="lighter_live_adjust_margin",
            script="trade.py",
            args=[
                "position",
                "margin",
                input.symbol,
                "--amount",
                str(input.amount),
                "--direction",
                input.direction,
            ],
        )
