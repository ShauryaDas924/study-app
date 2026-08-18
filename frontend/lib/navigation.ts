const DEFAULT_AUTH_DESTINATION = "/dashboard";

export function getSafeInternalPath(
  raw: string | null,
  origin: string,
  fallback = DEFAULT_AUTH_DESTINATION
): string {
  if (
    !raw ||
    !raw.startsWith("/") ||
    raw.startsWith("//") ||
    raw.includes("\\")
  ) {
    return fallback;
  }

  try {
    const resolved = new URL(raw, origin);
    if (resolved.origin !== origin) return fallback;
    return `${resolved.pathname}${resolved.search}${resolved.hash}`;
  } catch {
    return fallback;
  }
}
