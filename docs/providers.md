# Provider configuration (gated capabilities)

Several capabilities are real, wired **seams** that stay honestly "not connected" until you
configure their external provider/credential. With nothing set, the app is fully functional and the
[System status panel](../apps/web/src/components/system/SystemStatusPanel.tsx) + `/api/health` report
each as not connected. Set the variables below to activate them. No vendor SDKs are required — every
external provider is called over plain HTTPS (Textract uses the already-bundled boto3).

| Capability | Activate with | Behavior when unset (honest default) |
|------------|---------------|--------------------------------------|
| **Legal e-signature** | `SIGNATURE_PROVIDER=external`, `SIGNATURE_PROVIDER_URL`, `SIGNATURE_PROVIDER_KEY` | Tamper-evident integrity seal (explicitly **not** legally binding) |
| **Cloud IDP** | `IDP_PROVIDER=textract` (+ `S3_ACCESS_KEY`/`S3_SECRET_KEY`) **or** `IDP_PROVIDER=external` + `IDP_PROVIDER_URL`/`IDP_PROVIDER_KEY` | Local deterministic extraction + Tesseract |
| **Handwriting OCR** | `HANDWRITING_PROVIDER=external`, `HANDWRITING_PROVIDER_URL`, `HANDWRITING_PROVIDER_KEY` | Standard printed-text OCR only |
| **Text-to-speech** | `TTS_PROVIDER=external`, `TTS_PROVIDER_URL`, `TTS_PROVIDER_KEY` | `GET /documents/{id}/audio` → 501 (no offline TTS engine) |
| **DRM** | `DRM_PROVIDER=external`, `DRM_PROVIDER_URL`, `DRM_PROVIDER_KEY` | `POST /documents/{id}/drm` → 501; use AES-256 Protect PDF |
| **Cloud storage** (Drive/Dropbox/Box/OneDrive/Slack) | `OAUTH_REDIRECT_BASE` + per-provider `<NAME>_CLIENT_ID` / `<NAME>_CLIENT_SECRET` (`GDRIVE_`, `DROPBOX_`, `BOX_`, `ONEDRIVE_`, `SLACK_`) | Listed as "Not configured"; connect returns 501 |
| **Multi-node presence** | `COLLAB_BACKEND=redis`, `COLLAB_REDIS_URL` | Single-node in-process presence (works out of the box) |

## Provider HTTP contracts

Each external provider is a small HTTPS service you point a URL at; the request shapes:

- **E-signature** — `POST {url}/requests` (multipart `document` + `subject`, `signers`) → `{id, status, signing_url}`; `GET {url}/requests/{id}` → `{status, signing_url}`. Webhooks to `POST /api/esign/webhook` must send `X-Signature` = HMAC-SHA256(body, `SIGNATURE_PROVIDER_KEY`).
- **IDP** — `POST {url}/analyze` (multipart `document`) → `{fields: [{key, value, confidence}]}`. (Textract uses the AWS API directly via boto3.)
- **Handwriting** — `POST {url}/recognize` (multipart `image`) → `{text}`.
- **TTS** — `POST {url}/synthesize` (JSON `{text, voice}`) → audio bytes (`Content-Type` audio/*).
- **DRM** — `POST {url}/protect` (multipart `document` + `policy`) → protected bytes.

All provider calls are authenticated with `Authorization: Bearer <KEY>` when a key is set, time out
safely, and degrade to a clean error (never crash the request).

## Not activated by configuration (still 🔒)

Native mobile **apps**, legally-binding signature **standing** (a CA / KYC / notarization vendor
account), and true multi-user **CRDT co-editing** across nodes. Their seams exist and report real
state; they require the external service/credential or legal standing to actually function.
