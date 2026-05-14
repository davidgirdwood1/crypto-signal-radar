const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function getJson(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

export function fetchSummary() {
  return getJson("/api/stats/summary");
}

export function fetchHeartbeats() {
  return getJson("/api/stats/worker-heartbeats");
}

function buildEventParams(filters, defaults = {}) {
  const params = new URLSearchParams(defaults);
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== "" && value !== null && value !== undefined) params.set(key, value);
  });
  return params;
}

export function fetchRiskBoard(filters) {
  const params = buildEventParams(filters);
  const query = params.toString();
  return getJson(`/api/tokens/risk-board${query ? `?${query}` : ""}`);
}

export function fetchClassifiedEvents(filters) {
  const params = buildEventParams(filters, { limit: "100" });
  return getJson(`/api/events/classified?${params.toString()}`);
}

export function fetchDeadLetters(limit = 50) {
  return getJson(`/api/dead-letters?limit=${limit}`);
}
