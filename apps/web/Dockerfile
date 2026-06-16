# Production image for the Next.js web app.
# NOTE: build with the repository root as the context so the pnpm workspace
# (and the @docos/shared-types package) resolves:
#   docker build -f apps/web/Dockerfile -t docos-web .
FROM node:20-slim AS build
RUN corepack enable
WORKDIR /repo
COPY . .
RUN pnpm install --frozen-lockfile && pnpm --filter @docos/web build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN useradd --create-home --uid 10001 web
# Next standalone output: a self-contained server + traced node_modules.
COPY --from=build --chown=web /repo/apps/web/.next/standalone ./
COPY --from=build --chown=web /repo/apps/web/.next/static ./apps/web/.next/static
USER web
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
