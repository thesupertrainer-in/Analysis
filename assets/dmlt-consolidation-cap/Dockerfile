FROM node:22-alpine AS build

WORKDIR /app

# Copy package files for workspace install
COPY package.json package-lock.json ./
COPY app/react-ui/package.json ./app/react-ui/

# Install all dependencies (includes workspace)
RUN npm ci --ignore-scripts

# Copy all source files
COPY . .

# Build React UI and CAP production bundle
RUN npm run build

# ── Production image ──────────────────────────────────────────────────────────
FROM node:22-alpine

WORKDIR /app

# Copy production artifacts from build stage
COPY --from=build /app/package.json ./
COPY --from=build /app/package-lock.json ./
COPY --from=build /app/gen/ ./gen/
COPY --from=build /app/server.js ./
COPY --from=build /app/srv/ ./srv/
COPY --from=build /app/db/ ./db/
COPY --from=build /app/app/ ./app/

# Install production-only dependencies
RUN npm ci --omit=dev --ignore-scripts

# Expose CAP port
EXPOSE 4004

ENV PORT=4004
ENV NODE_ENV=production

CMD ["npx", "cds-serve", "--from-gen"]
