export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const apiBase = import.meta.env.VITE_API_URL || "";

export async function api(path: string, options: RequestInit = {}) {
  let response: Response;
  try {
    response = await fetch(apiBase + path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(sessionStorage.getItem("api-key")
          ? { "X-API-Key": sessionStorage.getItem("api-key")! }
          : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new Error(
      "Unable to connect to the payment service. Please try again shortly.",
    );
  }

  const text = await response.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    if (!response.ok) {
      throw new Error(
        `API connection failed (HTTP ${response.status}). The payment service is temporarily unavailable. Please retry.`,
      );
    }
    throw new Error(
      "The payment service returned an invalid response. Please retry or contact your workspace administrator.",
    );
  }
  if (!response.ok) {
    const detail = data && typeof data === "object" ? data.detail : undefined;
    throw new ApiError(
      typeof detail === "string"
        ? detail
        : `Request failed (HTTP ${response.status}). Please check your payment details and try again.`,
      response.status,
    );
  }
  if (!data || typeof data !== "object") {
    throw new Error(
      "The payment service returned an unexpected response. Please retry or contact your workspace administrator.",
    );
  }
  return data;
}
