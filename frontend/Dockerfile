FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

ARG NEXT_PUBLIC_API_URL=http://localhost:8080
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY . .
RUN npm run build

# --- Production stage ---
FROM node:20-alpine

WORKDIR /app

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/public ./public

EXPOSE 3000

# Shell form for $PORT expansion (Cloud Run injects PORT)
CMD npm run start -- -p ${PORT:-3000}
