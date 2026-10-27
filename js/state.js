/** Client state aligned with AgentResponse / ChatResponse */
const state = {
  sessionId: null,
  messages: [],
  stage: "inspiration",
  status: null,
  destinations: [],
  hotels: [],
  transportOptions: [],
  itinerary: null,
  cart: null,
  warnings: [],
  selected: {
    destinationId: null,
    destinationName: null,
    hotelId: null,
    hotelName: null,
  },
  isLoading: false,
  isMock: true,
  demoBooking: null,
};

function createSessionId() {
  return "sess_" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
}

function resetState() {
  state.sessionId = null;
  state.messages = [];
  state.stage = "inspiration";
  state.status = null;
  state.destinations = [];
  state.hotels = [];
  state.transportOptions = [];
  state.itinerary = null;
  state.cart = null;
  state.warnings = [];
  state.selected = {
    destinationId: null,
    destinationName: null,
    hotelId: null,
    hotelName: null,
  };
  state.isLoading = false;
  state.demoBooking = null;
}

export { state, resetState, createSessionId };
