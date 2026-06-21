const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function request(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export function getRiskRegister(params = {}) {
  const qs = new URLSearchParams();
  if (params.tier) qs.set("tier", params.tier);
  if (params.offboardingGapsOnly) qs.set("offboarding_gaps_only", "true");
  if (params.department) qs.set("department", params.department);
  if (params.search) qs.set("search", params.search);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request(`/api/risk-register${suffix}`);
}

export function getUserGraph(employeeId) {
  return request(`/api/user/${encodeURIComponent(employeeId)}/graph`);
}

export function getUserRemediation(employeeId) {
  return request(`/api/user/${encodeURIComponent(employeeId)}/remediation`);
}

export function getStats() {
  return request(`/api/stats`);
}

export async function refreshData() {
  const res = await fetch(`${API_BASE}/api/refresh`, { method: "POST" });
  if (!res.ok) throw new Error("Refresh failed");
  return res.json();
}
