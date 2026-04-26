---
name: lighter-kill
description: Panic button — cancel ALL open orders and flatten ALL open positions on Lighter. Two-step.
---

# /lighter-kill

You are about to flatten the user's entire Lighter account. This is a
high-risk command. Treat every step as irreversible.

Steps:

1. Call `lighter_safety_status`. If `mode` is not `live` or `funds`, stop
   and tell the user the account is in `{mode}` so there is nothing live to
   kill. Do not proceed.
2. Call `lighter_orders_open` and `lighter_account_info` so you can describe
   exactly what will be cancelled and flattened.
3. Call `lighter_live_cancel_all` **without** a `confirmation_id`. You will
   get a preview envelope with `confirmation_id`.
4. Call `lighter_live_close_all` **without** a `confirmation_id`. Use
   `with_cancel_all = true` and a conservative `slippage` (default 0.01).
   You will get a second preview envelope with its own `confirmation_id`.
5. Show the user a single combined plan:
    - "Will cancel N open orders" (list them).
    - "Will flatten M open positions" (list them with side/size).
    - Estimated slippage budget.
    - Both confirmation_ids and their expiries.
6. **Wait for the user to type the word "confirm"** (or equivalent in their
   language). Do not accept "yes", "ok", or "go" — require an explicit
   confirmation word so it cannot be triggered by accidental autocomplete.
7. On confirmation, call both tools again with the same arguments plus
   their respective `confirmation_id`s. Order: cancel_all first, then
   close_all.
8. Render the final result: how many orders cancelled, how many positions
   closed, any errors verbatim.

If any preview returns `category: "safety"`, surface the error and stop.
If the user types anything other than the explicit confirmation word, abort.
