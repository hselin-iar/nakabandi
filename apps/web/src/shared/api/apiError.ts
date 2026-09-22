/**
 * apiError.ts — maps a server error response to a UiError.
 * DOC 3 Web App Shell: apiError(e) -> UiError { code, message, fields? }
 * `message` is already user text from the server.
 */

export interface UiError {
  code: string;
  message: string;
  fields?: Record<string, string>;
}

/** Shape of FastAPI 422 validation-error detail items. */
interface ValidationItem {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/** Shape of the API's standard error body. */
interface ApiErrorBody {
  code?: string;
  message?: string;
  detail?: string | ValidationItem[];
}

/**
 * Converts any thrown value from openapi-fetch / fetch into a UiError.
 * Handles:
 *   - 422 Unprocessable Entity with Pydantic `detail` array
 *   - Any other HTTP error with `{ code, message }` body
 *   - Network / parse failures
 */
export function apiError(e: unknown): UiError {
  if (e instanceof Response) {
    // Caller should await e.json() before passing here — but handle defensively.
    return { code: String(e.status), message: `HTTP ${e.status}` };
  }

  if (e && typeof e === "object") {
    const body = e as ApiErrorBody;

    // Pydantic 422 detail array
    if (Array.isArray(body.detail)) {
      const fields: Record<string, string> = {};
      for (const item of body.detail as ValidationItem[]) {
        const key = item.loc.slice(1).join(".");
        fields[key] = item.msg;
      }
      return {
        code: "validation_error",
        message: "Validation failed — check the highlighted fields.",
        fields,
      };
    }

    // Server-sent { code, message }
    if (typeof body.message === "string") {
      return {
        code: typeof body.code === "string" ? body.code : "error",
        message: body.message,
      };
    }

    // Fallback string detail
    if (typeof body.detail === "string") {
      return { code: "error", message: body.detail };
    }
  }

  if (e instanceof Error) {
    return { code: "network_error", message: e.message };
  }

  return { code: "unknown", message: "An unexpected error occurred." };
}
