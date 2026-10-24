FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run typecheck && npm run build
ENV NODE_ENV=production
EXPOSE 3000
CMD ["npm","run","start"]
