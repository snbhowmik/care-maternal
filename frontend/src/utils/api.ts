/**
 * Staff API client for care_maternal. Uses the host's staff token (localStorage) and
 * the host's API base URL. The patient portal is a separate demo page in the backend.
 */
const BASE_PATH = "/api/care_maternal";
const STAFF_TOKEN_KEY = "care_access_token";

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, data: unknown) {
    super(`Request failed (${status})`);
    this.status = status;
    this.data = data;
  }
}

function apiBase(): string {
  return (window as unknown as { CARE_API_URL?: string }).CARE_API_URL ?? "";
}

export async function request<T>(
  path: string,
  method: "GET" | "POST" = "GET",
  body?: unknown,
): Promise<T> {
  const token = localStorage.getItem(STAFF_TOKEN_KEY);
  const res = await fetch(`${apiBase()}${BASE_PATH}${path}`, {
    method,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data && typeof data === "object" && "detail" in data ? String(data.detail) : "";
    throw new ApiError(res.status, detail ? { detail } : data);
  }
  return data as T;
}

/** The hospital the staff member is working in, from the /facility/<id>/... URL. */
export function currentFacilityId(): string {
  return window.location.pathname.match(/\/facility\/([^/]+)/)?.[1] ?? "";
}

/** Turns an ApiError into a short message a nurse can read. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const d = err.data as { detail?: string } | null;
    if (err.status === 404) return "Patient not found or not visible to you.";
    if (err.status === 403) return d?.detail ?? "You do not have permission for this action.";
    if (d?.detail) return d.detail;
    return "Something went wrong. Please try again.";
  }
  return "Network error. Check the connection and try again.";
}
