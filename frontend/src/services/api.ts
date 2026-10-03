let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET")
    headers.set("X-CSRF-Token", csrf);
  const response = await fetch("/api/v1" + path, {
    ...options,
    headers,
    credentials: "include",
  });
  const data = await response.json().catch(() => ({
    error: { message: "The service returned an unreadable response." },
  }));
  if (!response.ok)
    throw new ApiError(
      data.error?.message ??
        "The service is unavailable. Check the API and worker.",
      response.status,
    );
  return data as T;
}
export function post<T>(path: string, body: unknown = {}) {
  return api<T>(path, { method: "POST", body: JSON.stringify(body) });
}
