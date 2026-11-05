
function normalizeHotels(list) {
  return list.map((hotel) => ({
    ...hotel,
    id: hotel.hotel_id || hotel.id,
    hotel_id: hotel.hotel_id || hotel.id,
    price_total: hotel.total_price ?? hotel.price_total ??
      (typeof hotel.price === "number" ? hotel.price : null),
  }));
}

function applyServerResponse(state, data) {
  if (data.session_id) state.sessionId = data.session_id;
  if (state.demoBooking && data.state &&
      data.state.demo_booking_id !== state.demoBooking.booking_id) {
    state.demoBooking = null;
  }
  if (data.status) state.status = data.status;
  const trip = data.state?.trip || null;
  if (trip) state.trip = trip;
  const selected = data.state?.selected || null;
  const cityChanged = trip?.city && state.selected?.destinationName &&
    trip.city !== state.selected.destinationName;

  if (Array.isArray(data.destinations) && data.destinations.length) {
    state.destinations = data.destinations;
  } else if (data.status === "no_results" && data.state?.last_intent === "inspiration") {
    state.destinations = [];
  }
  if (Array.isArray(data.hotels) && data.hotels.length) {
    state.hotels = normalizeHotels(data.hotels);
  } else if (cityChanged || (data.status === "no_results" &&
             data.state?.last_intent === "hotel_search")) {
    state.hotels = [];
  }
  if (Array.isArray(data.transport_options) && data.transport_options.length) {
    state.transportOptions = data.transport_options;
  } else if (data.state?.last_intent === "trip_search") {
    state.transportOptions = [];
  }
  if ("itinerary" in data) state.itinerary = data.itinerary;
  if ("cart" in data) state.cart = data.cart;
  if (Array.isArray(data.warnings)) {
    state.warnings = data.warnings.map((warning) =>
      typeof warning === "string" ? { level: "info", text: warning } : warning);
  }
  if (trip) {
    state.selected.destinationId = trip.destination_id || null;
    state.selected.destinationName = trip.city || null;
  }
  if (selected) {
    state.selected.hotelId = selected.hotel_offer_id || null;
    state.selected.hotelName = selected.hotel_name || null;
    state.selected.transportId = selected.outbound_transport_id || null;
    state.selected.returnTransportId = selected.return_transport_id || null;
  } else if (cityChanged) {
    state.selected.hotelId = null;
    state.selected.hotelName = null;
    state.selected.transportId = null;
    state.selected.returnTransportId = null;
  }
  if (["inspiration", "destinations", "hotels", "itinerary", "checkout"].includes(data.stage)) {
    state.stage = data.stage;
  }

  if (data.cart?.items?.length) return "cart";
  if (data.itinerary?.legs?.length || data.transport_options?.length) return "itinerary";
  if (data.hotels?.length) return "hotels";
  if (data.destinations?.length) return "destinations";
  return null;
}

export { applyServerResponse };
