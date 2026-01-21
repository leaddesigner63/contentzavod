export const DEFAULT_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type ApiError = {
  message: string;
  status?: number;
};

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
  baseUrl: string = DEFAULT_API_BASE_URL
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${baseUrl}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const text = await response.text();
    throw {
      message: text || response.statusText,
      status: response.status,
    } as ApiError;
  }

  if (response.status === 204) {
    return null as T;
  }

  return (await response.json()) as T;
}

export function parseCsv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
