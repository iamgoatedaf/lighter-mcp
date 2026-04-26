# Disclaimer

This software is provided **as-is**, without warranty of any kind. It is a
community/integration toolkit for the Lighter exchange and is not affiliated
with or endorsed by Lighter unless explicitly noted in a release.

## Risk

- Trading on a perpetuals exchange is **risky** and can result in the **total
  loss of funds**, including funds from collateral, leverage, and fees.
- Live orders submitted via this server are **irreversible** once accepted by
  the exchange. There is no undo, no support escalation that can roll back
  filled trades, and no automatic stop-loss unless you wire one in yourself.
- Withdrawals are similarly **irreversible**.
- The two-step confirmation flow and configurable risk gates reduce the
  surface area for catastrophic mistakes but **do not eliminate them**. They
  rely on you reviewing previews carefully and on the underlying SDK behaving
  correctly. Bugs in this software, the agent, the kit, or the exchange can
  still cause loss.
- AI agents may misunderstand prompts. Treat their output as untrusted unless
  you have read the actual preview returned by the MCP server.

## Compliance

You are responsible for ensuring that your use of Lighter is compliant with
the laws and regulations of your jurisdiction. This toolkit does not perform
KYC/AML checks. It does not enforce trading restrictions beyond the
allowlists you put into your own config.

## Operator responsibilities

- Treat the credentials directory (`~/.lighter/lighter-agent-kit/credentials`)
  and any environment variables holding API keys as secrets.
- Review the audit log periodically and rotate keys at the first sign of
  unexpected activity.
- Keep `mode = "readonly"` (or `paper`) by default. Promote to `live`/`funds`
  only for the duration of an explicit, supervised session.
- Use Lighter testnet for any new strategy until you have walked through
  every confirmation flow with full preview output.

## No financial advice

Nothing in this repository constitutes investment, legal, tax, or financial
advice. Use at your own risk.
