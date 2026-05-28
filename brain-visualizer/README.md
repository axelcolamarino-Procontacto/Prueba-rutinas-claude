# QA Agent — Brain Visualizer

Grafo 3D interactivo del conocimiento del QA Agent. Muestra en tiempo real las entidades,
relaciones y skills que el agente aprende con cada ejecución.

## Cómo correrlo

```bash
cd brain-visualizer

# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Autenticarse con Google Cloud (solo la primera vez)
gcloud auth application-default login

# 3. Arrancar el servidor
python server.py

# 4. Abrir en el browser
# http://localhost:8000
```

## Qué se ve

- **Nodos** — cada entidad que el agente conoce: campos SF, perfiles, skills, root causes
- **Aristas** — relaciones entre entidades (hidden_when, failed_because, covers, etc.)
- **Tamaño del nodo** — cuántas conexiones tiene (más conexiones = más importante)
- **Color** — tipo de entidad (ver leyenda en pantalla)
- **Nodos blancos/brillantes** — agregados en las últimas 24h
- **Partículas en las aristas** — relaciones de alta confianza (>0.8)

## Si BigQuery no está disponible

El visualizador muestra automáticamente datos de demo con un banner naranja.
Una vez que el agente ejecute sus primeros runs, los datos reales reemplazarán al demo.

## Controles

| Acción | Cómo |
|---|---|
| Rotar | Click + arrastrar |
| Zoom | Scroll |
| Pan | Click derecho + arrastrar |
| Ver detalle de nodo | Click en el nodo |
| Filtrar por proyecto | Dropdown arriba a la derecha |
| Actualizar datos | Botón "↺ Actualizar" (también auto-refresca cada 60s) |
