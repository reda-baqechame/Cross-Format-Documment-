/**
 * Resolve the backend URL for the server-side /api proxy.
 *
 * Railway: set on the **web** service —
 *   API_PROXY_TARGET=http://${{api.RAILWAY_PRIVATE_DOMAIN}}:${{api.PORT}}
 * (replace `api` with your backend service name.)
 */

function stripTrailingSlash(url: string): string {
  return url.replace(/\/+$/, "");
}

export function resolveApiProxyTarget(): string {
  const explicit =
    process.env.API_PROXY_TARGET ??
    process.env.API_INTERNAL_URL ??
    process.env.RAILWAY_API_URL;
  if (explicit) return stripTrailingSlash(explicit);

  const privateDomain = process.env.API_RAILWAY_PRIVATE_DOMAIN;
  if (privateDomain) {
    const port = process.env.API_PORT ?? "8000";
    return `http://${privateDomain}:${port}`;
  }

  return "http://localhost:8000";
}
