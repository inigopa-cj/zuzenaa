# Diseño de la web (notas de trabajo)

Brief inferido: **panel de evaluación formativa para profesorado de FP** que gestiona clases,
roster, assignments y notas sobre Classroom 50. Audiencia: docentes y TAs; uso diario, con
mucha lectura de datos y acciones puntuales. Público adulto, contexto de aula técnica.

## Dirección estética

No usar el kit por defecto (fondo crema + serif + acento terracota; tarjetas idénticas;
eyebrows en mayúsculas; monocromo para etiquetas). En su lugar:

- **Papel técnico**: claro, aireado, tipografía humanista-mono para metadatos y una sans
  neutra para texto. Sensación de "cuaderno de laboratorio", no de SaaS genérico.
- Un único gesto memorable: **la banda de cabecera con el "pulso" de la clase** (métricas
  con una línea de acento fina), no tarjetas con sombras.
- Reglas finas y jerarquía tipográfica en lugar de bordes redondeados por todas partes.

## Tokens

- Color base: `#FBFBF9` (papel) · `#14181F` (tinta) · `#5B6472` (gris) ·
  `#1F6F5C` (acento, verde profesor) · `#B4442E` (alerta) · `#E7E4DC` (línea).
- Tipos: display y cuerpo en **"Fraunces"**? No: evitar serif-de-moda. Usar
  **"Space Grotesk"** (títulos) + **"Inter"** (texto) + **"JetBrains Mono"** (datos).
  Cargadas desde Google Fonts o, si no hay red, `system-ui` de reserva.
- Layout: navegación lateral estrecha + área principal con cabecera de clase y tablas.
  Alineación a la izquierda. Líneas < 80 caracteres.

## Principios

1. Los datos mandan: tabla y métricas antes que decoración.
2. Un acento, un lugar: el verde identifica lo activo/positivo; el rojo solo alerta.
3. Espacio en blanco como estructura; reglas finas como separadores.
4. Texto de UI en euskera/castellano, claro y en voz activa.
5. Accesible: foco visible, contraste, `prefers-reduced-motion`.
