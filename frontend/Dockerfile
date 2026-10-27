FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
COPY . .
# Install, build and prune in one layer so removed optional packages are not left
# inside a lower Docker layer of the shipped image.
RUN npm ci --no-audit --no-fund \
    && npm run typecheck \
    && npm run build \
    && npm prune --omit=dev --omit=optional --no-audit --no-fund \
    && node scripts/verify-production-dependencies.mjs
ENV NODE_ENV=production
EXPOSE 3000
CMD ["npm","run","start"]
