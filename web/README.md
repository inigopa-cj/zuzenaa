# ZuzenAA · Web

SPA React + TypeScript + Vite. Se sirve con nginx en producción (proxy `/api` → backend) y con el servidor de Vite en desarrollo.

## Uso

```sh
npm install
npm run dev      # http://localhost:5173 (proxy /api -> VITE_API_PROXY)
npm run build    # tsc -b && vite build
npm run lint     # oxlint
```

Con Docker no hace falta instalar nada: `make dev` (web en <http://localhost:5173>) o `make up` (nginx en <http://localhost:8080>).

## Proxy de API

En desarrollo, Vite reenvía `/api/*` al backend indicado por `VITE_API_PROXY` (por defecto `http://localhost:8000`). En producción lo hace nginx a `http://backend:8000`.
