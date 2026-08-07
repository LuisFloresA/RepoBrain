// Cliente HTTP del frontend: llamadas a la API de login.
// Demo embebida de RepoBrain (ejercita el parser de JavaScript).

const BASE_URL = "/api";

export async function login(email, password) {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Login fallido");
  }
  const { token } = await res.json();
  localStorage.setItem("repobrain_token", token);
  return token;
}

export function getAuthHeaders() {
  const token = localStorage.getItem("repobrain_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}
