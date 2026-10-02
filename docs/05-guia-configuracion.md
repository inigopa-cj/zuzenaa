# 05 · Guía de configuración (puesta en marcha)

Guía paso a paso para dejar ZuzenAA funcionando: variables de entorno, **OAuth App de
GitHub** (y **dónde** se crea), arranque con Docker, primer login y despliegue en producción.

> La autenticación en detalle (flujo, endpoints, seguridad) está en `docs/04-autenticacion.md`.
> Aquí nos centramos en **configurarlo todo desde cero**.

## 0. Quién hace qué

- **Administrador/a** (quien despliega ZuzenAA, normalmente un profesor): crea la OAuth App
  **una sola vez**, rellena `.env` y arranca el servidor.
- **Cada usuario** (profesorado o alumnado): solo pulsa **Iniciar sesión** y autoriza. **No crea
  ninguna app**.

**Dónde va la OAuth App:** en la **cuenta personal** de GitHub del administrador
(*Settings → Developer settings → OAuth Apps*). **No** se crea en la organización: las
organizaciones tienen *GitHub Apps*, no OAuth Apps. La organización solo entra si tiene activadas
las **restricciones de OAuth Apps**, para **aprobar** la app (ver paso 3.5).

---

## 1. Requisitos previos

| Necesitas | Detalle |
| --- | --- |
| Docker + Docker Compose | Todo el proyecto está dockerizado. |
| Cuenta de GitHub del admin | Con acceso a la organización del centro. |
| Organización de GitHub | En plan **Team o Enterprise** (lo exige Classroom 50; gratis para docentes verificados con GitHub Education). |
| Classroom 50 ya preparado | La organización debe tener su `classroom50` inicializado y sus clases/assignments. ZuzenAA **solo lee**. |

No hace falta instalar `git`, `gh` ni Python en tu máquina: la imagen del backend ya trae `git`, el
CLI `gh` y las extensiones `gh-teacher`/`gh-student` (versión fija).

---

## 2. Variables de entorno

```sh
cp .env.example .env
```

Edita `.env` (nunca lo subas al repositorio):

```sh
# --- Base de datos (la usa docker-compose) ---
POSTGRES_USER=zuzenaa
POSTGRES_PASSWORD=una-contraseña-larga
POSTGRES_DB=zuzenaa

# --- Backend ---
# Clave de servidor: cifra los tokens de GitHub y firma el state de OAuth.
# Genera una fuerte y NO la cambies a mitad de curso (rotarla invalida tokens y sesiones).
ZUZENAA_SECRET_KEY=<aleatoria-larga>
ZUZENAA_BACKEND_URL=http://localhost:8000
ZUZENAA_FRONTEND_URL=http://localhost:8080

# --- GitHub OAuth App (se rellena en el paso 3) ---
ZUZENAA_GITHUB_OAUTH_CLIENT_ID=
ZUZENAA_GITHUB_OAUTH_CLIENT_SECRET=

# --- Web de Classroom 50 para los enlaces profundos (solo si es self-hosted) ---
ZUZENAA_CLASSROOM50_URL=https://classroom50.org

# --- Agente ---
ZUZENAA_LLM_PROVIDER=mock        # mock por defecto (sin clave). Real: más adelante.
```

Generar la clave secreta:

```sh
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
# o: openssl rand -base64 48
```

| Variable | Para qué |
| --- | --- |
| `ZUZENAA_SECRET_KEY` | Cifra en reposo el token de GitHub y firma el `state` de OAuth. **Estable y secreta.** |
| `ZUZENAA_BACKEND_URL` | Base del backend; define la **callback URL** (`<backend>/auth/callback`). |
| `ZUZENAA_FRONTEND_URL` | A dónde redirige tras el login. |
| `ZUZENAA_CLASSROOM50_URL` | Base de la web de Classroom 50 para los enlaces «Ver en Classroom 50». |
| `ZUZENAA_ALLOW_ENV_TOKEN` + `ZUZENAA_GITHUB_TOKEN` | Atajo local **sin identidad de usuario** (ver §8). |

---

## 3. Crear la OAuth App de GitHub

### 3.1 Abre el formulario correcto

Inicia sesión en GitHub con la **cuenta del administrador** y ve a:

**Settings (de tu cuenta, no de la org) → Developer settings → OAuth Apps → New OAuth App**
Atajo: <https://github.com/settings/developers> → *OAuth Apps* → *New OAuth App*.

> ¿Por qué en tu cuenta y no en la organización? Porque ZuzenAA actúa **en nombre de cada
> usuario** con **su** token; la app es la que identifica a ZuzenAA ante GitHub. Las OAuth Apps
> pertenecen a cuentas personales. Si la organización restringe apps de terceros, se aprueba aparte
> (paso 3.5).

### 3.2 Rellena el formulario

| Campo | Valor (desarrollo local) | Valor (producción) |
| --- | --- | --- |
| **Application name** | `ZuzenAA` | `ZuzenAA` |
| **Homepage URL** | `http://localhost:8080` | URL pública de la web |
| **Authorization callback URL** | `http://localhost:8000/auth/callback` | `https://<tu-dominio>/auth/callback` |

La **callback URL** debe coincidir **exactamente** con `ZUZENAA_BACKEND_URL` + `/auth/callback`.

### 3.3 Genera el client secret

Pulsa **Generate a new client secret** y cópialo (solo se muestra una vez).

### 3.4 Rellena `.env`

```sh
ZUZENAA_GITHUB_OAUTH_CLIENT_ID=Iv1.xxxxxxxxxxxxxxxx
ZUZENAA_GITHUB_OAUTH_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3.5 (Solo si la organización restringe apps)

Si la org impide que apps de terceros accedan a sus datos, un **owner de la organización** debe
aprobar la app:

**Organización → Settings → Third-party Access → OAuth app policy** → aprueba `ZuzenAA`.

(Un mismo OAuth App sirve para toda la org y todos los usuarios; cada persona la autoriza la
primera vez que entra.)

---

## 4. Arrancar

```sh
make up        # construye y arranca db + backend + web
```

- Web: <http://localhost:8080> · API: <http://localhost:8000/health>
- La primera construcción tarda un poco (instala `gh`, extensiones y dependencias).

Comprueba que la configuración se ha leído:

```sh
curl -s http://localhost:8000/auth/status
# {"oauth_configured":true, "env_token_allowed":false, ..., "classroom50_url":"https://classroom50.org"}
```

Si `oauth_configured` es `false`, faltan el Client ID o el Secret en `.env` (reinicia el backend
tras editar `.env`: `docker compose up -d --build backend` o `make up`).

---

## 5. Primer login

1. Abre la web y pulsa **Iniciar sesión**.
2. GitHub te pedirá autorizar ZuzenAA con los scopes `repo workflow read:org admin:org`.
3. Vuelves a la web ya autenticado (cookie `zuzenaa_session`).

Verifica: `curl -s http://localhost:8000/auth/me` debe devolver tu login (con la cookie de sesión
del navegador) y la cabecera superior mostrará tu usuario.

---

## 6. Uso diario (profesorado)

1. Elige la **organización** en el panel lateral (sale de tus orgs de GitHub).
2. Elige una **clase** → un **assignment**.
3. **Descargar repos** (clona al servidor los repos de los alumnos del roster).
4. **Analizar** (individual o todos) y consultar **histórico y progreso** por alumno.
5. Los enlaces **«Ver en Classroom 50»** abren la clase/assignment/assignment correspondiente en
   `classroom50.org`.

El alumnado entra con su propia cuenta y ve **solo lo suyo** en **Mis clases** (lo que el
profesorado ya haya descargado/analizado).

---

## 7. Producción (servidor del centro)

1. Sirve todo bajo **un dominio HTTPS** (recomendado): nginx puede servir la web en `/` y hacer
   proxy de `/api` y `/auth` al backend. Así la cookie de sesión es *same-origin*.
2. Ajusta en `.env`:
   ```sh
   ZUZENAA_BACKEND_URL=https://<tu-dominio>
   ZUZENAA_FRONTEND_URL=https://<tu-dominio>
   ZUZENAA_COOKIE_SECURE=true
   ZUZENAA_SECRET_KEY=<fuerte y estable>
   ```
3. Actualiza la **callback URL** de la OAuth App a `https://<tu-dominio>/auth/callback`.
4. Mantén el volumen `data` (repos y snapshots) respaldado.

---

## 8. Alternativa sin OAuth (un solo operador)

Si el servidor lo usa **una sola persona** y no necesitas identidad por usuario, puedes evitar la
OAuth App:

```sh
ZUZENAA_ALLOW_ENV_TOKEN=true
ZUZENAA_GITHUB_TOKEN=<gh auth token>
```

No hay sesión ni `/auth/me`: todo se ejecuta como esa cuenta. **No lo uses en producción** con
alumnado, porque la superficie alumno (`/me`) necesita sesión real.

---

## 9. Diagnóstico de problemas

| Síntoma | Causa / arreglo |
| --- | --- |
| `GET /auth/login` responde **503** | Faltan `ZUZENAA_GITHUB_OAUTH_CLIENT_ID` o `_SECRET`, o no reiniciaste el backend. |
| `auth/status` → `oauth_configured:false` | Igual que arriba. |
| Callback con **state inválido o caducado** | El enlace caducó (10 min) o se abrió en otro navegador. Reintenta el login. |
| `No se pudo completar...` al leer orgs/clases | Token sin acceso a la org: aprueba la OAuth App (§3.5) o tu cuenta no es miembro/owner. |
| Un alumno ve la plataforma vacía | Aún no se ha descargado/analizado su entrega (el descubrimiento sale de la BD). |
| Errores de `gh teacher` en el backend | La org debe estar preparada en Classroom 50 y tu token tener acceso (plan Team/Enterprise). |

---

## 10. Resumen en una imagen

```
[Admin]  GitHub personal ──crea──> OAuth App ──usa──> ZuzenAA (.env)
   │                                                     │
   └─ org Classroom 50 (autoridad de clases)             │
                                                         ▼
[Usuario] web ──> "Iniciar sesión" ──> GitHub (autoriza) ──> sesión ZuzenAA
```
