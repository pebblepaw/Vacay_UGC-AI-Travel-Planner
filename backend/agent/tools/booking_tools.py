"""Tools for booking workflows.

These tools are declared for LLM planning/tool-calling. Execution is handled by
backend.agent.nodes.booking_tool_executor so we can read/write graph state.
"""

from langchain_core.tools import tool


@tool
def find_booking_options(
    booking_type: str,
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = "",
    adults: int = 1,
    budget_limit: float = 0.0,
    provider_hint: str = "trip.com",
    max_results: int = 5,
) -> str:
    """Find ticket/hotel options using browser-use exploration.

    Args:
        booking_type: flight/train/hotel/attraction
        origin: origin city/station
        destination: destination city/station
        departure_date: YYYY-MM-DD
        return_date: optional YYYY-MM-DD
        adults: number of adults
        budget_limit: 0 means no budget cap
        provider_hint: provider preference, e.g. trip.com
        max_results: maximum options to return
    """
    return "find_booking_options called"


@tool
def select_booking_option(option_id: str, notes: str = "") -> str:
    """Select one offer from the latest discovered options.

    Args:
        option_id: ID from find_booking_options result
        notes: optional user constraints/instructions
    """
    return f"select_booking_option called with {option_id}"


@tool
def proceed_checkout(
    traveler_name: str,
    traveler_email: str,
    traveler_phone: str = "",
    traveler_gender: str = "",
    traveler_birth_date: str = "",
    traveler_nationality: str = "",
    traveler_doc_type: str = "",
    traveler_doc_number: str = "",
    traveler_doc_expiry: str = "",
    headless: bool = True,
    allow_empty_traveler: bool = False,
) -> str:
    """Navigate to provider checkout and fill forms until confirmation page.

    IMPORTANT: this tool should stop before final payment click.

    Args:
        traveler_name: passenger/guest full name
        traveler_email: email for booking contact
        traveler_phone: optional phone number
        traveler_gender: passenger gender (male/female/other)
        traveler_birth_date: YYYY-MM-DD
        traveler_nationality: nationality (e.g. China)
        traveler_doc_type: passport/id
        traveler_doc_number: document number
        traveler_doc_expiry: YYYY-MM-DD
        headless: run browser headless or visible
        allow_empty_traveler: allow opening the form without requiring traveler info
    """
    return "proceed_checkout called"
