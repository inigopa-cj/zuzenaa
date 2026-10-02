# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# deps: dependencias (capa cacheable)
# ---------------------------------------------------------------------------
FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---------------------------------------------------------------------------
# dev: servidor de Vite con recarga en caliente
# ---------------------------------------------------------------------------
FROM deps AS dev
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# ---------------------------------------------------------------------------
# build: compila la SPA
# ---------------------------------------------------------------------------
FROM deps AS build
COPY . .
RUN npm run build

# ---------------------------------------------------------------------------
# runtime: nginx sirviendo la SPA y proxy /api -> backend
# ---------------------------------------------------------------------------
FROM nginx:1.29-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
