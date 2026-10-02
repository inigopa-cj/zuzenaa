# 04 · Autenticación (GitHub OAuth)

ZuzenAA usa **GitHub OAuth App** para autenticar al profesorado. El flujo ya está
implementado; solo falta crear la OAuth App y poner las credenciales.

> Guía completa de puesta en marcha (entorno, arranque, producción): `docs/05-guia-configuracion.md`.
> La OAuth App se crea en la **cuenta personal** del administrador (Developer settings), no en la organización.

## Flujo

1. La persona pulsa **Iniciar sesión** → `GET /auth/login`.
2. El backend crea un `state` (anti-CSRF, guardado en BD con caducidad de 10 min) y redirige a GitHub.
3. GitHub pide autorización con los scopes configurados y vuelve a `/auth/callback`.
4. El backend valida el `state`, canjea el `code` por un token, lee el usuario (`/user`),
   **cifra el token** (Fernet derivado de `ZUZENAA_SECRET_KEY`) y crea una **sesión**.
5. Se emite la cookie `zuzenaa_session` (`httponly`, `SameSite=Lax`) y redirige a la web.
6. `GET /auth/me` devuelve la identidad; `POST /auth/logout` cierra la sesión.

El token se resuelve **por petición** (`api/deps.py: get_github_token`): sesión si existe; si no,
`ZUZENAA_GITHUB_TOKEN` **solo si** `ZUZENAA_ALLOW_ENV_TOKEN=true` (atajo local).

## Crear la OAuth App (manual, una vez)

1. GitHub → **Settings → Developer settings → OAuth Apps → New OAuth App**.
2. Rellena:
   - **Application name**: `ZuzenAA` (o el que quieras).
   - **Homepage URL**: `http://localhost:8080` (en producción, la URL pública de la web).
   - **Authorization callback URL**: `http://localhost:8000/auth/callback`
     (en producción, `https://<tu-dominio>/auth/callback` — debe coincidir con `ZUZENAA_BACKEND_URL`).
3. **Generate a new client secret**.
4. Copia el **Client ID** y el **Client Secret** a `.env`:

```sh
ZUZENAA_GITHUB_OAUTH_CLIENT_ID=Iv1.xxxxxxxxxxxxxxxx
ZUZENAA_GITHUB_OAUTH_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ZUZENAA_SECRET_KEY=<una cadena aleatoria larga>   # clave de cifrado; NO la cambies a mitad de curso
ZUZENAA_BACKEND_URL=http://localhost:8000
ZUZENAA_FRONTEND_URL=http://localhost:8080
```

5. Reinicia el backend (`make up` o `make dev`).

## Scopes

Por defecto: `repo workflow read:org admin:org` — los mismos que pide `gh teacher login`.
`admin:org` es necesario para gestionar organización, equipos y reglas.

> **Nota de gobernanza:** son scopes clásicos amplios. Es aceptable para el MVP, pero si el
> centro lo cuestiona, la alternativa es una **GitHub App** (permisos finos), que aún requiere
> un *spike* porque `gh teacher` espera un token de usuario con scopes clásicos.

## Estado y diagnóstico

- `GET /auth/status` → `{oauth_configured, env_token_allowed, scopes, callback_url}`. La web lo usa
  para mostrar **"OAuth sin configurar"** en vez de un enlace de login roto.
- Si `/auth/login` responde **503**, faltan `ZUZENAA_GITHUB_OAUTH_CLIENT_ID` o `_SECRET`.
- Si el callback falla con `state inválido`, el enlace caducó (10 min) o se abrió en otro navegador.

## Producción (servidor del centro)

- Pon `ZUZENAA_FRONTEND_URL`/`ZUZENAA_BACKEND_URL` con las URLs públicas (HTTPS).
- Actualiza la **callback URL** de la OAuth App al dominio real.
- Define `ZUZENAA_COOKIE_SECURE=true` (solo con HTTPS).
- Genera una `ZUZENAA_SECRET_KEY` fuerte y **no** la cambies: rotarla invalida los tokens
  cifrados (habría que volver a iniciar sesión).

## Alternativa local sin OAuth

Para desarrollo, puedes evitar la OAuth App con el atajo:

```sh
ZUZENAA_ALLOW_ENV_TOKEN=true
ZUZENAA_GITHUB_TOKEN=<gh auth token>
```

La web funciona igual, pero no hay identidad de usuario (sin sesión, sin `/auth/me`). No lo uses
en producción.
