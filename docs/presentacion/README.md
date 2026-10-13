# Presentación de ZuzenAA

Presentación básica del proyecto: qué es, cómo funciona por dentro (arquitectura, agentes,
privacidad y calidad) y dos casos prácticos paso a paso, uno del **profesorado** y otro del
**alumnado**, con capturas y vídeos de la aplicación grabados con Playwright.

| Fichero | Qué es |
| --- | --- |
| [`presentacion.html`](presentacion.html) | La presentación lista para proyectar (27 diapositivas). Ábrela en el navegador: flechas para avanzar, `F` para pantalla completa. |
| [`presentacion.md`](presentacion.md) | El origen, en Markdown para [Marp](https://marp.app/). En GitHub se lee como documento. |
| `img/` | Capturas de cada paso (`profesor-*`, `alumno-*`). |
| `video/` | Recorridos completos en vídeo: `recorrido-profesor.webm` y `recorrido-alumno.webm`. |

Las capturas y los vídeos son del **modo demo** (datos ficticios, `docs/06-datos-de-prueba.md`):
el alumnado aparece con su seudónimo de clase y el tutor responde en modo básico (misma
estructura que con el modelo real).

## Regenerar el HTML

Tras editar `presentacion.md`:

```sh
npx -y @marp-team/marp-cli@4 presentacion.md --html --allow-local-files --no-stdin -o presentacion.html
```

`--html` es necesario para que los vídeos se incrusten en las diapositivas.
