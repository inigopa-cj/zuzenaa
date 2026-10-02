# Política de seguridad

ZuzenAA trata datos sensibles: **tokens de GitHub** y **código del alumnado**. Si encuentras
una vulnerabilidad, te pedimos divulgación responsable.

## Cómo reportar

- Usa **GitHub → Security → Report a vulnerability** (Security Advisory privado) del repositorio.
- **No** abras un issue público para un problema de seguridad.
- Incluye: descripción, pasos para reproducirlo, impacto y, si puedes, una propuesta de arreglo.

Responderemos lo antes posible e intentaremos acordar contigo una fecha de publicación antes de
hacer público el fallo.

## Versiones soportadas

Solo la rama **`main`** recibe correcciones de seguridad.

## Alcance (ejemplos)

- Fuga o exposición del token de GitHub (en reposo o en tránsito).
- Saltarse la autorización de lectura de feedback (que un alumno vea lo de otro).
- Inyección en rutas de disco / ejecución de comandos a través de datos de Classroom 50.
- SSRF o filtración de secretos en el contexto que se envía al proveedor LLM.

## Cómo protegemos los datos

- El token de GitHub se **cifra en reposo** (Fernet derivado de `ZUZENAA_SECRET_KEY`) y se
  resuelve por petición.
- La lectura del histórico está **autorizada**: cada alumno ve solo lo suyo; el profesorado de la
  clase puede ver a cualquiera.
- La clave del proveedor LLM vive **solo en el servidor**; nunca se escribe en los repos de
  alumnos.
- El feedback **no se publica** en GitHub; vive únicamente en esta plataforma.
- No se versionan `.env`, repos descargados, snapshots ni volcados de base de datos.
