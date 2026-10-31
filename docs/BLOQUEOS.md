# Bloqueos

Formato: tarea · qué falló · salida del error · alternativa más barata.

## Tarea 3.1 · Render del diagrama Mermaid a PNG

- **Qué falló:** el agente no pudo ejecutar `npx @mermaid-js/mermaid-cli`; el entorno de ejecución bloqueó la descarga y ejecución de un paquete externo.
- **Salida:** `Permission for this action was denied ... Reason: [Code from External]`.
- **Alternativa más barata:** que un integrante ejecute el comando guardado en la cabecera de `docs/diagrama-arquitectura.mmd`, o pegue el archivo en https://mermaid.live y exporte PNG a 2000 px a `docs/evidencias/f3-01-arquitectura.png`. Otra opción es abrir `docs/diagrama-arquitectura.drawio` en draw.io y exportar PNG con el mismo nombre.
- **Pendiente:** validar que el `.mmd` renderiza y que el texto del PNG se lee.
