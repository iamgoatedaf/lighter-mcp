"""Funds tools: transfers and withdrawals.

Gated behind ``mode == 'funds'`` AND the corresponding ``[funds]`` flag.
Both actions always go through the two-step confirmation flow regardless of
the ``require_confirmation`` setting because they move real assets.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .confirmations import ConfirmationError
from .safety import SafetyError
from .schemas import TransferInput, WithdrawInput

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP

    from .server import ServerContext


def _safety_envelope(error: SafetyError) -> dict[str, Any]:
    return {"ok": False, "error": str(error), "category": "safety"}


def _confirmation_envelope(error: ConfirmationError) -> dict[str, Any]:
    return {"ok": False, "error": str(error), "category": "confirmation"}


def register_funds_tools(app: FastMCP, ctx: ServerContext) -> None:
    safety = ctx.safety
    confirmations = ctx.confirmations

    @app.tool(
        name="lighter_funds_withdraw",
        description=(
            "Withdraw an asset off Lighter. ALWAYS uses two-step confirmation; "
            "first call returns a preview, second call with confirmation_id "
            "executes."
        ),
    )
    async def lighter_funds_withdraw(input: WithdrawInput) -> Any:
        try:
            safety.require_withdrawals_enabled()
            safety.check_withdrawal_amount_usd(input.amount)
        except SafetyError as exc:
            return _safety_envelope(exc)

        plan = {
            "action": "withdraw",
            "asset": input.asset,
            "amount": input.amount,
            "route": input.route,
            "warning": "Withdrawals are irreversible.",
        }
        canonical = {k: v for k, v in input.model_dump().items() if k != "confirmation_id"}
        if input.confirmation_id is None:
            token, expires_at = confirmations.issue(
                tool="lighter_funds_withdraw", args=canonical
            )
            return {
                "ok": True,
                "stage": "preview",
                "tool": "lighter_funds_withdraw",
                "plan": plan,
                "confirmation_id": token,
                "expires_at": expires_at,
            }
        try:
            confirmations.consume(
                tool="lighter_funds_withdraw",
                args=canonical,
                token=input.confirmation_id,
            )
        except ConfirmationError as exc:
            return _confirmation_envelope(exc)

        return await ctx.run_kit(
            tool="lighter_funds_withdraw",
            script="trade.py",
            args=[
                "funds",
                "withdraw",
                "--asset",
                input.asset,
                "--amount",
                str(input.amount),
                "--route",
                input.route,
            ],
        )

    @app.tool(
        name="lighter_funds_transfer",
        description=(
            "Move an asset between spot and perp routes on the same account. "
            "Two-step confirmation required."
        ),
    )
    async def lighter_funds_transfer(input: TransferInput) -> Any:
        try:
            safety.require_transfers_enabled()
        except SafetyError as exc:
            return _safety_envelope(exc)

        if input.from_route == input.to_route:
            return {
                "ok": False,
                "error": "from_route and to_route must differ.",
                "category": "validation",
            }

        plan = {
            "action": "transfer",
            "asset": input.asset,
            "amount": input.amount,
            "from_route": input.from_route,
            "to_route": input.to_route,
        }
        canonical = {k: v for k, v in input.model_dump().items() if k != "confirmation_id"}
        if input.confirmation_id is None:
            token, expires_at = confirmations.issue(
                tool="lighter_funds_transfer", args=canonical
            )
            return {
                "ok": True,
                "stage": "preview",
                "tool": "lighter_funds_transfer",
                "plan": plan,
                "confirmation_id": token,
                "expires_at": expires_at,
            }
        try:
            confirmations.consume(
                tool="lighter_funds_transfer",
                args=canonical,
                token=input.confirmation_id,
            )
        except ConfirmationError as exc:
            return _confirmation_envelope(exc)

        return await ctx.run_kit(
            tool="lighter_funds_transfer",
            script="trade.py",
            args=[
                "funds",
                "transfer",
                "--asset",
                input.asset,
                "--amount",
                str(input.amount),
                "--from_route",
                input.from_route,
                "--to_route",
                input.to_route,
            ],
        )
