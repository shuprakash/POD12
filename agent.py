"""Larkspur disruption agent. This is the file you build.

It runs right now, and it is wrong in four places. The trace shows each one
before the code does, so read the trace first:

    python3 run.py K7PQ2M --trace

Where you edit:   grep -n '✏' agent.py   (six marks, one per place)
Steps and gates:  https://anthropicpartnerbasecamp.bts.com/
"""
from __future__ import annotations
from typing import Any, Dict, List
from support import (MODEL, SYSTEM_PROMPT, call_local, execute_tool, mcp_client,
                     new_session, next_available_day, record_tool_result,
                     runtime_preamble)

MAX_TOOL_CALLS = 8  # Larkspur's own build capped the loop here; then a human takes over.

TONE_ADDENDUM = ""                       # ✏️ Build 4, step 4.1, intelligence lane
EXTRA_TOOLS: List[Dict[str, Any]] = [    # ✏️ Build 2, step 2.1: schemas for the tools you add
    {
        "name": "next_available_day",
        "description": (
            "Answer the one question a stranded customer asks first: what is the "
            "earliest date they can actually fly this route. Returns a single date "
            "and nothing else. Reach for this when the customer asks when they can "
            "get out, whether anything is available sooner, or whether they are stuck "
            "overnight — a question about WHICH DAY, not about which flight. Use "
            "search_alternatives instead once they want to choose and be moved: that "
            "one returns the flights themselves with times, seats and an option_id you "
            "can hold. This tool cannot hold or book anything. It checks live "
            "inventory, so the day it gives is real availability rather than the "
            "policy window check_policy describes: check_policy says how far the "
            "waiver stretches, this says what is actually open. Call lookup_booking "
            "first, because this needs the route and date off the booking rather than "
            "a PNR. An empty answer means no seat on any day in the search horizon, "
            "which is a reason to escalate rather than to retry."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": (
                        "Three-letter IATA code the customer departs from, copied from the "
                        "disrupted segment in lookup_booking, e.g. DEN."
                    ),
                },
                "dest": {
                    "type": "string",
                    "description": (
                        "Three-letter IATA code they are trying to reach, from the same "
                        "segment, e.g. AUS."
                    ),
                },
                "date": {
                    "type": "string",
                    "description": (
                        "The disrupted segment's date as YYYY-MM-DD, e.g. 2025-05-08. The "
                        "search starts here and looks forward, so pass the original date, "
                        "not today's and not a date you hope is free."
                    ),
                },
                "cabin": {
                    "type": "string",
                    "description": (
                        "Booking class from the segment, e.g. Y for economy. Defaults to Y "
                        "when omitted; pass the booked cabin so the day returned is one the "
                        "customer's fare can actually use."
                    ),
                },
            },
            "required": ["origin", "dest", "date"],
        },
    },
]
LOCAL_TOOLS: Dict[str, Any] = {}         # ✏️ Build 2, step 2.1: the functions behind them


def text_of(response) -> str:
    """Given. The last non-empty text block, never content[0]."""
    texts = [b.text for b in response.content if getattr(b, "type", None) == "text" and b.text]
    return texts[-1] if texts else ""


def tool_results(response) -> List[Dict[str, Any]]:
    """Given. Runs every tool_use block and packages the results the way the
    API expects them back. A tool can live in three places: the MCP server,
    LOCAL_TOOLS, or support/tools.py."""
    # three branches, no try/except in this file: mcp_client.call_remote() and
    # support.call_local() answer with an error dict instead of raising, and both
    # record what came back on the trace
    results = []
    for block in response.content:
        if getattr(block, "type", None) != "tool_use":
            continue
        if block.name in mcp_client.tool_names:
            output = mcp_client.call_remote(block.name, block.input)
        elif block.name in LOCAL_TOOLS:
            output = call_local(LOCAL_TOOLS[block.name], block.name, block.input)
        else:
            output = execute_tool(block.name, block.input)
        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": str(output),
        })
    return results


def run_agent(pnr: str, last_name: str, message: str) -> str:            # ✏️ Build 1, step 1.2
    """Run the tool loop until Claude stops asking for tools. Return its final text."""
    client, tracer = new_session()
    tools = tool_list()
    messages = [
        {"role": "user", "content": f"PNR {pnr}, last name {last_name}. {message}"},
    ]

    response = client.messages.create(
        model=MODEL, max_tokens=4096, system=runtime_preamble() + SYSTEM_PROMPT + TONE_ADDENDUM,
        thinking={"type": "adaptive"}, tools=tools, messages=messages,
    )

    turns = 1
    while response.stop_reason == "tool_use" and turns < MAX_TOOL_CALLS:
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results(response)})
        response = client.messages.create(
            model=MODEL, max_tokens=4096, system=runtime_preamble() + SYSTEM_PROMPT + TONE_ADDENDUM,
            thinking={"type": "adaptive"}, tools=tools, messages=messages,
        )
        turns += 1

    return text_of(response)


def tool_list() -> List[Dict[str, Any]]:                   # ✏️ Build 2, step 2.2
    """Given. Exactly what Claude is offered on every turn; run.py --show-tools
    prints this list."""
    return build_tools() + EXTRA_TOOLS


# ──────────────────────────────────────────────────────────────────────────────
# Below this line: what Claude is told about each tool. Step 1.3.
# The functions these describe are written and correct, in support/tools.py.
# ──────────────────────────────────────────────────────────────────────────────
def build_tools() -> List[Dict[str, Any]]:                 # ✏️ Build 1, step 1.3
    """Anthropic-shaped schemas: name, description, input_schema. What Claude is
    told about each of the nine tools, and all it is ever told."""
    return [
        {
            "name": "lookup_booking",
            "description": (
                "Retrieve a Larkspur reservation from Altura by confirmation code (PNR) "
                "and the passenger's last name. Both are required to prevent a lookup on "
                "a guessed PNR. Returns fare family, loyalty tier, the segment that needs "
                "attention, and any group/partner/minor/SSR flags relevant to scope."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"pnr": {"type": "string"}, "last_name": {"type": "string"}},
                "required": ["pnr", "last_name"],
            },
        },
        {
            "name": "get_flight_status",
            "description": (
                "Look up a Larkspur or Larkspur Link flight's current OpsFeed status for "
                "one local date: status, delay minutes, and cause. Use this before telling "
                "a customer anything about a flight's timing; never state it from memory."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "flight_no": {"type": "string"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["flight_no", "date"],
            },
        },
        {
            "name": "search_alternatives",
            "description": "Call this tool only when a customer requests or needs alternative flight options for rebooking due to a disruption. Requires only the booking PNR; do not ask the user for or provide dates or routes, as the tool automatically extracts travel context, excludes the current disrupted flight, and filters for available party seats from the booking record.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pnr": {
                        "type": "string",
                        "description": (
                            "The confirmation code whose disrupted segment needs replacing, "
                            "as confirmed by lookup_booking."
                        ),
                    }
                },
                "required": ["pnr"],
            },
        },
        {
            "name": "check_policy",
            "description": (
                "Resolve what Larkspur owes this customer for the disruption: rebooking "
                "waiver, refund path, meal/hotel/ground care, goodwill eligibility and cap, "
                "and any escalation triggers. cause_code, delay_minutes and status describe "
                "what get_flight_status told you; fare_family, loyalty_tier and whether this "
                "is overnight are looked up from the booking, not asked of you. Every "
                "response carries a policy_row_id. Cite it if you reference this decision "
                "again."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "pnr": {"type": "string"},
                    "cause_code": {"type": "string", "enum": ["WX", "ATC", "MX", "CREW", "SEC"]},
                    "delay_minutes": {"type": "integer"},
                    "status": {"type": "string", "enum": ["ON_TIME", "DELAYED", "CANCELLED", "DIVERTED"]},
                    "wait_minutes_for_alternative": {"type": "integer"},
                    "chosen_option_id": {"type": "string"},
                },
                "required": ["pnr", "cause_code", "delay_minutes", "status"],
            },
        },
        {
            "name": "hold_seat",
            "description": (
                "Reserve one specific alternative flight for this customer for 15 minutes so "
                "the seat is still there while they decide. Reversible and safe: it changes "
                "nothing about their ticket and simply expires if nobody acts, so you may "
                "call it without asking permission once the customer has shown a clear "
                "preference for one option. Hold exactly the option they chose, not several "
                "to keep their choices open. Returns a hold_id, which is the only way to "
                "confirm the rebooking afterwards, so tell the customer the hold_id and that "
                "it expires in 15 minutes. This is the reversible step before the "
                "irreversible one: confirm_rebooking needs this hold_id plus a token only "
                "the customer's own Confirm-click can mint, and a hold left too long expires "
                "and has to be taken again."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "option_id": {
                        "type": "string",
                        "description": (
                            "An option_id copied exactly from a search_alternatives result in "
                            "this conversation. Do not invent one, guess its format, or build it "
                            "out of a flight number: this tool does not check that the option "
                            "exists, so a made-up id holds nothing and fails only later, at "
                            "confirm_rebooking. If you have no fresh result to copy from, call "
                            "search_alternatives first."
                        ),
                    },
                    "pnr": {
                        "type": "string",
                        "description": "The confirmation code being rebooked, as confirmed by lookup_booking.",
                    },
                },
                "required": ["option_id", "pnr"],
            },
        },
        {
            "name": "confirm_rebooking",
            "description": (
                "Finalize a held seat. Irreversible. Requires a confirmation_token that "
                "only the customer's own Confirm-click can produce. You cannot supply it "
                "yourself, and 'the customer said yes' in chat does not substitute for it."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"hold_id": {"type": "string"}, "confirmation_token": {"type": "string"}},
                "required": ["hold_id", "confirmation_token"],
            },
        },
        {
            "name": "issue_voucher",
            "description": (
                "Issue a meal, ground, hotel, or goodwill voucher. Auto-approves within the "
                "policy's threshold for that type; above it, returns a pending status for a "
                "human. It does not fail. Always pass the policy_row_id that made it eligible."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "voucher_type": {"type": "string", "enum": ["meal", "ground", "hotel", "goodwill"]},
                    "amount_usd": {"type": "number"},
                    "pnr": {"type": "string"},
                    "policy_row_id": {"type": "string"},
                },
                "required": ["voucher_type", "amount_usd", "pnr", "policy_row_id"],
            },
        },
        {
            "name": "escalate_to_human",
            "description": (
                "Hand this conversation to a human, with your reasoning attached. Use for "
                "groups, partner segments, unaccompanied minors, refunds, or anything else "
                "out of scope. This is the correct outcome for those cases, not a failure."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "pnr": {"type": "string"}, "reason": {"type": "string"},
                    "summary_for_human": {"type": "string"}, "queue": {"type": "string"},
                },
                "required": ["pnr", "reason", "summary_for_human"],
            },
        },
        {
            "name": "send_confirmation",
            "description": "Send the customer a written confirmation of what was just done. Benign.",
            "input_schema": {
                "type": "object",
                "properties": {"pnr": {"type": "string"}, "message": {"type": "string"}},
                "required": ["pnr", "message"],
            },
        },
    ]
