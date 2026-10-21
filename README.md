# Conectividad aviar del Norte de Bolívar · WebGIS

Visor web de resultados del análisis de conectividad ecológica funcional para aves (gremios de interior de bosque seco, frugívoras y humedales) en los 21 municipios de la jurisdicción CARDIQUE y el Distrito de Cartagena.

Elaboró: Dioser Ladeuth Narváez, 2026.

---

## 1. Cómo funciona un WebGIS como este

Un WebGIS sencillo tiene tres piezas, y todas son archivos normales:

| Pieza | Qué es | En esta carpeta |
|---|---|---|
| **Página** | Un archivo HTML con la librería **Leaflet**, que dibuja el mapa en el navegador | `index.html` |
| **Datos vectoriales** | Capas en **GeoJSON**, EPSG:4326 (lat/lon) | `data/*.geojson` |
| **Rásteres** | Imágenes ya coloreadas (WebP) y las coordenadas de sus esquinas | `img/*.webp` + `data/manifest.json` |

No hay servidor de mapas ni base de datos. Por eso se puede publicar gratis en **GitHub Pages**: el navegador descarga los archivos y Leaflet los dibuja.

```
webgis-conectividad/
├── index.html                ← el visor
├── data/                     ← capas GeoJSON + manifest.json (esquinas de rásteres y estadísticas)
├── img/                      ← rásteres en WebP (idoneidad, resistencia, corriente, etc.)
├── herramientas/
│   └── preparar_capas.py     ← regenera data/ e img/ a partir de las salidas del análisis
└── aprende/
    └── ejemplo_minimo.html   ← un WebGIS de 60 líneas para practicar
```

---

## 2. Publicarlo gratis en GitHub Pages (sin instalar nada)

1. Cree una cuenta en <https://github.com> (gratis).
2. Botón **New repository** → nombre `webgis-conectividad` → **Public** → *Create repository*.
3. En el repositorio vacío: **uploading an existing file** (o *Add file → Upload files*). Arrastre **el contenido** de esta carpeta (`index.html`, `data`, `img`, `herramientas`, `aprende`, `README.md`). Espere a que suban todos y pulse **Commit changes**.
   - La carga por la web admite hasta 100 archivos por vez y 25 MB por archivo; este visor cumple ambos límites.
4. **Settings → Pages** → en *Build and deployment*: *Source* = **Deploy from a branch**, *Branch* = **main** y carpeta **/(root)** → **Save**.
5. En 1–3 minutos aparece el enlace: `https://SU-USUARIO.github.io/webgis-conectividad/`.

> **Importante:** con cuenta gratuita el repositorio debe ser público. Cualquiera podrá ver y descargar las capas de `data/` e `img/`. Si la SOB aún no autoriza la difusión de resultados, espere antes de publicar.

**Para actualizar:** suba de nuevo los archivos cambiados (*Add file → Upload files*); el enlace se mantiene.

---

## 3. Probarlo en su computador

Abrir `index.html` con doble clic **no funciona**: el navegador bloquea la lectura de archivos locales (`fetch`). Use un servidor local; Python ya lo trae:

```bash
cd ruta/a/webgis-conectividad
python -m http.server 8000
```

Luego abra <http://localhost:8000> (el visor) o <http://localhost:8000/aprende/ejemplo_minimo.html> (el ejemplo).

---

## 4. Ruta de aprendizaje sugerida

1. **Ejemplo mínimo** (`aprende/ejemplo_minimo.html`). Léalo de arriba a abajo; cada bloque está numerado y comentado: crear el mapa, mapa base, capa GeoJSON con popup, puntos con color por atributo y un ráster como imagen. Cambie colores, el zoom o la capa y recargue.
2. **Tutoriales oficiales de Leaflet**: <https://leafletjs.com/examples.html> (empiece por *Quick Start* y *Using GeoJSON with Leaflet*).
3. **El visor completo** (`index.html`). Busque estas partes, todas marcadas con comentarios `/* ---------- ... ---------- */`:
   - `GREMIOS`, `TIPOS`, `PAPEL`: nombres y colores.
   - `BASES`: mapas base (IGAC, satelital, OpenStreetMap).
   - `RASTERS`: capas ráster y sus leyendas.
   - `ctxDefs` y `gremioDefs`: cómo se carga y simboliza cada capa vectorial.
   - `renderResumen`: la pestaña de resumen (tablas y gráfico ECA).

---

## 5. Preparar o actualizar las capas

### Opción A: desde QGIS (una capa a la vez)

- **Vectores:** clic derecho en la capa → *Exportar → Guardar objetos como…* → Formato **GeoJSON**, SRC **EPSG:4326**. En *Opciones de capa* ponga `COORDINATE_PRECISION = 5`. Si pesa más de 2–3 MB, simplifique antes (*Vectorial → Herramientas de geometría → Simplificar*, 30–70 m en EPSG:9377).
- **Rásteres:** Leaflet muestra imágenes, no GeoTIFF. Aplique su estilo (QML), luego *Ráster → Conversión → Convertir mapa a ráster* (resolución de 100 m), reproyecte a **EPSG:3857** y exporte como PNG o WebP. Las esquinas van en `data/manifest.json` como `[[sur, oeste], [norte, este]]` en grados.

### Opción B: todo de una vez con el script

`herramientas/preparar_capas.py` regenera **todas** las capas con las mismas reglas que se usaron para el visor (reproyección, simplificación, paletas de los QML, percentiles de corriente, estadísticas).

```bash
pip install geopandas rasterio pillow pandas
```

Abra el script y ajuste las dos rutas del inicio:

```python
CARPETA = r"C:/ruta/a/R_julia_Corredores"   # raíz del proyecto (corredores_v2, circuitscape, barreras, grafos, insumos, Mapas, prioridad, fase4, fase5)
SALIDA  = r"C:/ruta/a/webgis-conectividad"   # esta carpeta
```

```bash
python herramientas/preparar_capas.py
```

Si alguna subcarpeta está en otro lugar, corrija la ruta en la línea correspondiente del script (todas usan `CARPETA`).

---

## 6. Agregar una capa nueva al visor

Ejemplo: una capa de puntos `data/mis_puntos.geojson`.

1. En `index.html`, dentro de `ctxDefs`, agregue:
   ```js
   puntos: async () => L.geoJSON(await getJSON("mis_puntos.geojson"), {
     pointToLayer: (f, ll) => L.circleMarker(ll, { radius: 6, color: "#333", fillColor: "#ffcc00", fillOpacity: 1 }),
     onEachFeature: (f, l) => l.bindPopup(f.properties.nombre)
   }),
   ```
2. En el objeto `S.v` agregue `puntos: false` (o `true` para que inicie encendida).
3. En `buildPanel`, dentro del grupo *Contexto territorial*, agregue:
   ```js
   ${rowCheck("puntos", "Mis puntos", "Descripción corta")}
   ```
4. (Opcional) En `renderLegend` agregue su entrada de leyenda.

---

## 7. Fuentes, licencias y atribuciones

- **Mapa base OpenStreetMap:** © colaboradores de OpenStreetMap (ODbL). La atribución debe quedar visible; el visor la muestra abajo a la derecha. Uso moderado según la política de teselas de OSM.
- **Satelital Esri World Imagery:** © Esri y proveedores. Se usa con atribución visible. Para un uso formal o de mucho tráfico, Esri pide una cuenta de ArcGIS Location Platform (tiene nivel gratuito) y una clave de API.
- **Fondo cartográfico:** departamentos IGAC (2026). Límites municipales CARDIQUE (DANE, 2020). Áreas protegidas RUNAP y CARDIQUE.
- **Librerías:** Leaflet 1.9.4 (BSD-2) y proj4js 2.9.2 (MIT), cargadas desde jsDelivr.

*Nota.* Elaboración propia. Datos en MAGNA-SIRGAS Origen Nacional (EPSG:9377); visualización en Web Mercator (EPSG:3857).
