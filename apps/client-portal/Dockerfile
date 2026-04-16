FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
COPY apps ./apps
RUN npm install

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build --workspace=@oficina/client-portal

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/apps/client-portal/.next/standalone ./
COPY --from=builder /app/apps/client-portal/.next/static ./apps/client-portal/.next/static
COPY --from=builder /app/apps/client-portal/public ./apps/client-portal/public
EXPOSE 3000
CMD ["node", "apps/client-portal/server.js"]
