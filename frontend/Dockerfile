# syntax=docker/dockerfile:1

# ---------- builder：构建静态资源（构建脚本内含 tsc --noEmit） ----------
FROM node:22-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---------- runtime：nginx 托管 dist + 反代 /api ----------
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD ["wget", "-qO-", "http://127.0.0.1/"]
