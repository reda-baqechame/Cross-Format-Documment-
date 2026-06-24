/**
 * Same-origin API proxy.
 *
 * The browser only ever talks to this app's own origin (`/api/*`); this handler
 * forwards each request to the backend (`API_PROXY_TARGET`, server-side). That keeps
 * the backend private, removes any build-time API URL from the client bundle, and
 * sidesteps CORS entirely.
 *
 * Production notes:
 * - The request body is **streamed** (`duplex: "half"`), not buffered. Buffering via
 *   `req.arrayBuffer()` trips Next's in-handler body size limit (~1 MB) and large uploads
 *   fail; streaming pipes the body straight through, so uploads up to MAX_UPLOAD_MB work.
 *   Responses are streamed too, for binary downloads (export/preview).
 * - Upstream calls have a timeout so a hung backend yields a clear 504, not a stuck tab.
 */

import { resolveApiProxyTarget } from "@/lib/proxy-target";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const TARGET = resolveApiProxyTarget();
const UPSTREAM_TIMEOUT_MS = Number(process.env.API_PROXY_TIMEOUT_MS ?? 60_000);

// In split-service Railway, fail loudly if prod is about to proxy to localhost.
// In the recommended single-service container, localhost/127.0.0.1 is the correct in-container API.
if (
  process.env.NODE_ENV === "production" &&
  process.env.DOCOS_RAILWAY_TOPOLOGY === "split" &&
  /^https?:\/\/(localhost|127\.0\.0\.1)\b/.test(TARGET)
) {
  console.warn(
    `[api-proxy] API_PROXY_TARGET is "${TARGET}" in production — on Railway this is NOT ` +
      "the API service. Set API_PROXY_TARGET to the API's private host, e.g. " +
      "http://${{api.RAILWAY_PRIVATE_DOMAIN}}:${{api.PORT}}",
  );
}

// Hop-by-hop / length headers we must not forward verbatim (the runtime recomputes them).
// `expect` is included because undici's fetch rejects an `Expect: 100-continue` header
// (NotSupportedError) — some clients/edges add it for larger uploads, which would
// otherwise fail the request.
const STRIP_REQUEST = new Set([
  "host",
  "connection",
  "content-length",
  "transfer-encoding",
  "expect",
]);
const STRIP_RESPONSE = new Set([
  "content-encoding",
  "content-length",
  "transfer-encoding",
  "connection",
]);

async function handler(req: Request, ctx: { params: { path?: string[] } }): Promise<Response> {
  const path = (ctx.params.path ?? []).join("/");
  const search = new URL(req.url).search;
  const target = `${TARGET}/${path}${search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!STRIP_REQUEST.has(key.toLowerCase())) headers.set(key, value);
  });

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const init: RequestInit & { duplex?: "half" } = {
    method: req.method,
    headers,
    redirect: "manual",
  };
  if (hasBody) {
    init.body = req.body;
    init.duplex = "half"; // required when streaming a request body in Node fetch
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);
  init.signal = controller.signal;

  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch (err) {
    const timedOut = err instanceof Error && err.name === "AbortError";
    const status = timedOut ? 504 : 502;
    const cause = err instanceof Error && err.cause ? ` cause=${String(err.cause)}` : "";
    const detail = timedOut
      ? `proxy: backend timed out after ${UPSTREAM_TIMEOUT_MS}ms at ${TARGET}`
      : `proxy: backend unreachable at ${TARGET} (${String(err)}${cause})`;
    return new Response(JSON.stringify({ detail }), {
      status,
      headers: { "content-type": "application/json" },
    });
  } finally {
    clearTimeout(timer);
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    // `Set-Cookie` is handled separately below — Headers.forEach folds multiple
    // cookies into one comma-joined string, which corrupts them.
    if (key.toLowerCase() === "set-cookie") return;
    if (!STRIP_RESPONSE.has(key.toLowerCase())) responseHeaders.set(key, value);
  });

  // Forward each Set-Cookie individually so the anonymous-session cookie (`docos_sid`)
  // reaches the browser intact. Without this the backend re-mints a session on every
  // request and the document owner never matches → 404 on every edit (you can open the
  // app but "can't modify anything"). `getSetCookie` is the WHATWG/undici API that
  // preserves separate cookie headers.
  const setCookies =
    typeof upstream.headers.getSetCookie === "function"
      ? upstream.headers.getSetCookie()
      : [];
  for (const cookie of setCookies) {
    responseHeaders.append("set-cookie", cookie);
  }

  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export {
  handler as GET,
  handler as POST,
  handler as PUT,
  handler as PATCH,
  handler as DELETE,
};
