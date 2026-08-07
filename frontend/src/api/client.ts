export interface HealthStatus {
  status: "ok" | "degraded";
  service: string;
  environment: string;
  dependencies?: Record<string, string>;
}

export async function fetchHealth(endpoint = "/health"): Promise<HealthStatus> {
  const resp = await fetch(endpoint);
  if (!resp.ok) {
    throw new Error(`Health check ${endpoint} failed: ${resp.status}`);
  }
  return (await resp.json()) as HealthStatus;
}