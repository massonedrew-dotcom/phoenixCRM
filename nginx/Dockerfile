# Build context is the repository root (see docker-compose.yml).
FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/50x.html /usr/share/nginx/html/50x.html
COPY --from=frontend /build/dist/ /usr/share/nginx/html/
