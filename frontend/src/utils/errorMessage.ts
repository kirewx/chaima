/**
 * Extract a human-readable message from an API error (axios).
 *
 * Handles the shapes FastAPI actually returns in `detail`:
 * - a plain string,
 * - a 422 validation error: an array of `{ msg, loc, ... }` objects,
 * - an object with a `message` field (used by e.g. the receive endpoint),
 * plus a generic fallback for anything else.
 *
 * Never returns an object, so the result is always safe to render as a
 * React child (raw objects as children crash the render tree).
 */
interface ValidationItem {
  msg?: string;
  loc?: (string | number)[];
}

export function errorMessage(err: unknown, fallback = "Something went wrong."): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } } | null | undefined)
    ?.response?.data?.detail;

  if (typeof detail === "string" && detail) return detail;

  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => {
        const item = d as ValidationItem;
        if (!item?.msg) return null;
        const field = Array.isArray(item.loc)
          ? item.loc.filter((p) => p !== "body").join(".")
          : "";
        return field ? `${field}: ${item.msg}` : item.msg;
      })
      .filter((m): m is string => !!m);
    if (msgs.length) return msgs.join("; ");
  }

  if (detail && typeof detail === "object") {
    const msg = (detail as { message?: unknown }).message;
    if (typeof msg === "string" && msg) return msg;
  }

  if (err instanceof Error && err.message) return err.message;
  return fallback;
}
