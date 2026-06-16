/**
 * Same-origin API proxy.
 *
 * The browser only ever talks to this app's own origin (`/api/*`); this handler
 * forwards each request to the backend (`API_PROXY_TARGET`, server-side). That keeps
 * the backend private, removes any build-time API URL from the client bundle, and
 * sidesteps CORS entirely. Bodies and responses are streamed, so multipart uploads
 * and binary downloads (export/preview) pass through untouched.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const TARGET = (process.env.API_PROXY_TARGET ?? "http://localhost:8000").replace(/\/+$/, "");

// Hop-by-hop / length headers we must not forward verbatim (the runtime recomputes them).
const STRIP_REQUEST = new Set(["host", "connection", "content-length", "transfer-encoding"]);
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

  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch (err) {
    return new Response(
      JSON.stringify({ detail: `proxy: backend unreachable at ${TARGET} (${String(err)})` }),
      { status: 502, headers: { "content-type": "application/json" } },
    );
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!STRIP_RESPONSE.has(key.toLowerCase())) responseHeaders.set(key, value);
  });

  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

export {
  handler as GET,
  handler as POST,
  handler as PUT,
  handler as PATCH,
  handler as DELETE,
};
