# Proofline console (Next.js) image.
#
# The build context is the repository ROOT, not this directory: the console is an npm
# workspace that imports `@proofline/api-client` from `packages/`, so the install has to run
# at the workspace root with the whole tree present.
#
# `NEXT_PUBLIC_*` values are build arguments rather than runtime environment because Next.js
# inlines them into the browser bundle at build time. A runtime-only variable would leave the
# deployed bundle pointing at whatever was set when the image was built, which is exactly the
# class of bug that produces a frontend calling the wrong API in front of an audience.

FROM node:22-alpine AS workspace

WORKDIR /repo
ENV NEXT_TELEMETRY_DISABLED=1

# Dependencies first, so editing application source does not invalidate the install layer.
COPY package.json package-lock.json ./
COPY apps ./apps
COPY packages ./packages
RUN npm ci --no-audit --no-fund

# Source and the public build-time configuration.
COPY . .

ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8011/api/v1
ARG NEXT_PUBLIC_DEMO_MODE=true
ARG NEXT_PUBLIC_DEMO_ACTOR_ID=
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_DEMO_MODE=$NEXT_PUBLIC_DEMO_MODE \
    NEXT_PUBLIC_DEMO_ACTOR_ID=$NEXT_PUBLIC_DEMO_ACTOR_ID

RUN npm run console:build

# The runtime stage carries the same tree because `next start` needs `node_modules` (this
# project does not use the `standalone` output). It is a local demonstration image, not a
# publication target, so image size is traded for a build that cannot differ from what was
# just built.
FROM node:22-alpine AS runtime

WORKDIR /repo
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

COPY --from=workspace /repo /repo

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

# The console's own `start` script pins port 3001 for host development; inside the image the
# port is chosen here so the container and the Compose port mapping agree.
CMD ["sh", "-c", "cd apps/console && npx next start -p 3000"]
