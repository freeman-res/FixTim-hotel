from .schemas import AgentResponse
from .state_manager import StateManager


def make_response(
    status: str, reply: str, state: dict, message: str,
    hotels: list[dict] | None = None, *,
    destinations: list[dict] | None = None,
    transport_options: list[dict] | None = None,
    weather: dict | None = None,
    warnings: list[str] | None = None,
) -> AgentResponse:
    updated_state = StateManager.add_history(state, message, reply)
    return AgentResponse(
        status=status,
        reply=reply,
        hotels=hotels or [],
        updated_state=updated_state,
        stage=updated_state.get("stage"),
        destinations=destinations or [],
        transport_options=transport_options or [],
        weather=weather,
        itinerary=updated_state.get("itinerary"),
        cart=updated_state.get("cart"),
        warnings=warnings if warnings is not None else list(updated_state.get("warnings", [])),
    )
