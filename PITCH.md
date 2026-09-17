# PITCH.md

Six lines and a lever. Your words. The last two are scored.

Built: A disruption-care agent for Larkspur Airlines that autonomously handles passenger rebooking.
Does: Looks up bookings, checks policies, finds alternative flights, and issues vouchers or holds seats.
Number: Resolves 5 different disruption scenarios.
Guardrail: The `confirm_rebooking` tool requires a confirmation token that only the customer's click can produce.
Next: Adding support for multi-passenger bookings and native capacity checks.
Still broken: The agent currently only checks alternative dates for a single passenger, requiring workarounds for groups.
Lever: intelligence

## Priya asked

Costs: The cost is driven by the total input/output tokens and the number of API turns per conversation.
Wrong: We look at the wire trace, checking exactly what data the tools returned (like the `check_policy` result).
Runs it: The `run_agent` loop controls execution and loops until the model stops asking for tools.
Left out: Unaccompanied minors, large groups, and partner flights are left out of scope and escalated to a human.
