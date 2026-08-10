# Frontend de RepoBrain (React + Vite) servido con nginx.
# Multi-stage: build de estáticos + imagen de runtime nginx no-root/cmd.

# ---------- Stage 1: build ----------
FROM node:24-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build

# ---------- Stage 2: nginx ----------
FROM nginx:1.27-alpine AS runtime

RUN addgroup -S appuser \
    && adduser -S -G appuser appuser \
    && chown -R appuser:appuser /var/cache/nginx

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx-main.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# nginx maestro como usuario no-root (necesario en nginx para reescribir head)
USER appuser

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]