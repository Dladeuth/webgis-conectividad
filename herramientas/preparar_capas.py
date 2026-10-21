"""
preparar_capas.py  -  Prepara las capas del análisis de conectividad (Norte de Bolívar) para el WebGIS.

Qué hace:
  1. Vectores (gpkg/shp en EPSG:9377) -> GeoJSON en EPSG:4326, simplificados para la web  -> data/
  2. Rásteres (GeoTIFF a 100 m)        -> imágenes WebP coloreadas en EPSG:3857 + sus límites -> img/
  3. Tablas de resultados (CSV)         -> data/manifest.json (estadísticas del "Resumen del gremio")

Cómo usarlo:
  pip install geopandas rasterio pillow pandas
  Ajuste CARPETA (raíz del proyecto R_julia_Corredores) y SALIDA (carpeta del sitio web) y ejecute:
  python preparar_capas.py
"""
import json, os, warnings
import numpy as np, pandas as pd, geopandas as gpd
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling, transform_bounds
from PIL import Image

warnings.filterwarnings("ignore")
# ======== AJUSTE ESTAS DOS RUTAS ========
CARPETA = r"C:/ruta/a/R_julia_Corredores"      # raíz con corredores_v2, circuitscape, barreras, grafos, insumos, Mapas, prioridad, fase4, fase5
SALIDA = r"C:/ruta/a/webgis-conectividad"        # carpeta del sitio (donde está index.html)
# ========================================
P1 = Z3 = Z4 = Z6 = CARPETA
OUT = SALIDA
os.makedirs(f"{OUT}/data", exist_ok=True); os.makedirs(f"{OUT}/img", exist_ok=True)
CRS = "EPSG:9377"
GREMIOS = ["interior", "frugivoro", "humedal"]; EPOCAS = ["seca", "lluviosa"]
manifest = {"rasters": {}, "stats": {}}


def rd(path, layer=None):
    g = gpd.read_file(path, layer=layer)
    if g.crs is None:
        g = g.set_crs(CRS)
    g = g.to_crs(CRS)
    g.geometry = g.geometry.force_2d()
    return g


def save(g, name, tol=0, keep=None, prec=5):
    g = g.copy()
    if keep is not None:
        g = g[keep + ["geometry"]]
    if tol:
        g.geometry = g.geometry.simplify(tol, preserve_topology=True)
    g = g[~g.geometry.is_empty & g.geometry.notna()].to_crs(4326)
    for c in g.columns:
        if c != "geometry" and g[c].dtype.kind == "f":
            g[c] = g[c].round(4)
    p = f"{OUT}/data/{name}.geojson"
    g.to_file(p, driver="GeoJSON", COORDINATE_PRECISION=prec, WRITE_BBOX="NO")
    print(f"{name}: {len(g)} feats, {os.path.getsize(p)/1e3:.0f} KB")


# ---------- Contexto ----------
save(rd(f"{Z4}/Mapas/insumos_mapa/area_estudio_corregida.gpkg"), "area_estudio", 30)
save(rd(f"{Z3}/insumos/area_estudio_buffer10km/area_estudio_buffer10km.shp"), "franja_10km", 50, keep=[])
mun = rd(f"{Z4}/Mapas/insumos_mapa/municipios_cardique.gpkg")
mun["municipio"] = mun["MPIO_CNMBR"].str.title().str.replace(" De ", " de ").str.replace(" La ", " la ").str.replace(" Del ", " del ")
mun["subregion"] = mun["ECORREGION"]
save(mun, "municipios", 40, keep=["municipio", "subregion", "MPIO_CCNCT"])
sob = rd(f"{Z4}/Mapas/insumos_mapa/nodos_sob_nuevo_2.gpkg")
save(sob, "nodos_sob", 40, keep=["nodo", "municipios", "area_ha"])
runap = rd(f"{Z3}/insumos/descargas_gee/runap_area_v2.gpkg")
runap = runap.rename(columns={"nombre_unificado": "nombre", "CATEGORIA": "categoria", "HARES": "ha"})
save(runap, "runap", 20, keep=["nombre", "categoria", "ha", "fuente"])

# ---------- Fase 2-3: nodos y enlaces por gremio ----------
for g in GREMIOS:
    n = rd(f"{Z4}/prioridad/prioridad_nodos_{g}.gpkg")
    base = gpd.read_file(f"{Z3}/grafos/nodos_grafo_{g}.gpkg", ignore_geometry=True)[["id_grafo", "area_ha", "idon_seca", "idon_lluviosa"]]
    base["id_grafo"] = base["id_grafo"].astype(int)
    n["id_grafo"] = n["id_grafo"].astype(int)
    n = n.merge(base, on="id_grafo", how="left")
    keep = ["id_grafo", "area_ha", "alta_ambas", "indice_final"] + [f"{k}_{e}" for e in EPOCAS for k in
            ["idon", "dPC", "dPCconnector", "BCPC_pct", "indice", "prioridad", "papel"]]
    save(n, f"nodos_{g}", {"interior": 50, "frugivoro": 70, "humedal": 60}[g], keep=keep, prec=4)

    e = rd(f"{Z4}/prioridad/prioridad_enlaces_{g}.gpkg", "enlaces")
    keep = ["id_enlace", "desde", "hasta", "dist_euc_m", "alta_ambas", "indice_final"] + [f"{k}_{ep}" for ep in EPOCAS for k in
            ["lcd", "corriente_max", "concentracion", "robusto", "dPC_enlace", "mejora_pct_r300", "mejora_pct_r500", "indice", "prioridad", "tipo"]]
    save(e, f"enlaces_{g}", 20, keep=keep)

# ---------- Fase 2: estrangulamientos top ----------
est = rd(f"{Z4}/Mapas/insumos_mapa/estrangulamientos_top.gpkg", "puntos")
save(est, "estrangulamientos", 0, keep=["gremio", "puesto", "corr_max", "area_ha", "id_enlace", "en_paquete", "enlace_paquete"])

# ---------- Fase 4: paquete de restauración y trampolines ----------
for lyr in ["corredores", "rutas"]:
    save(rd(f"{Z4}/Mapas/insumos_mapa/corredores_paquete.gpkg", lyr), f"paquete_{lyr}", 15)
tr = []
for g in GREMIOS:
    t = rd(f"{Z6}/fase4/trampolines_prioritarios_{g}.gpkg"); t["gremio"] = g; tr.append(t)
save(pd.concat(tr, ignore_index=True), "trampolines", 15, keep=["gremio", "epoca", "area_ha", "corriente_media"])

# tabla de restauración óptima (orden voraz) por gremio/época
rest = {}
for g in GREMIOS:
    for ep in EPOCAS:
        df = pd.read_csv(f"{Z6}/fase4/restauracion_optima_{g}_{ep}.csv")
        rest[f"{g}_{ep}"] = df.sort_values("orden_voraz").to_dict("records")
manifest["stats"]["restauracion"] = rest

# ---------- Fase 5: listas eBird de validación ----------
lv = []
for g in GREMIOS:
    t = rd(f"{Z4}/Mapas/insumos_mapa/listas_matriz.gpkg", g); lv.append(t)
lv = pd.concat(lv, ignore_index=True)
save(lv, "listas_validacion", 0, keep=["gremio", "n_listas", "n_det", "pct_det", "tercil"], prec=4)

# ---------- Estadísticas ----------
eca = pd.read_csv(f"{Z3}/grafos/resultados/eca_resumen.csv")
manifest["stats"]["eca"] = eca[eca.conversion == "c1"][["gremio", "epoca", "umbral_m", "ECA_ha", "ECA_pct"]].to_dict("records")
manifest["stats"]["validacion"] = pd.read_csv(f"{Z6}/fase5/validacion_ebird.csv").fillna("").to_dict("records")
manifest["stats"]["terciles"] = pd.read_csv(f"{Z6}/fase5/validacion_terciles.csv").to_dict("records")
manifest["stats"]["escenarios"] = pd.read_csv(f"{Z6}/fase4/escenarios_eca.csv").to_dict("records")
manifest["stats"]["curva"] = pd.read_csv(f"{Z6}/fase4/curva_rendimiento_resumen.csv").to_dict("records")
cob = pd.read_csv(f"{Z4}/Mapas/coberturas_municipio/coberturas_municipio_ha.csv", sep=";", decimal=",", encoding="utf-8-sig")
manifest["stats"]["coberturas_municipio"] = cob.to_dict("records")


# ---------- Rásteres ----------
def hex2rgb(h):
    h = h.lstrip("#"); return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def ramp(stops):
    """stops: [(valor, '#hex', alpha)] -> función numpy valor->RGBA (interpolación lineal)."""
    v = np.array([s[0] for s in stops], float)
    c = np.array([hex2rgb(s[1]) + [s[2]] for s in stops], float)
    def f(a):
        out = np.zeros(a.shape + (4,), np.uint8)
        for k in range(4):
            out[..., k] = np.interp(a, v, c[:, k]).astype(np.uint8)
        return out
    return f


def to_png(arr, src_transform, src_crs, name, colorize, mask=None, resampling=Resampling.nearest, dst_res=None, lossless=False, quality=85):
    """Reproyecta arr (2D float con NaN para vacío) a EPSG:3857 y guarda PNG coloreado."""
    h, w = arr.shape
    left, top = src_transform.c, src_transform.f
    right, bottom = left + w * src_transform.a, top + h * src_transform.e
    dt, dw, dh = calculate_default_transform(src_crs, "EPSG:3857", w, h, left, bottom, right, top, resolution=dst_res)
    dst = np.full((dh, dw), np.nan, np.float32)
    reproject(arr.astype(np.float32), dst, src_transform=src_transform, src_crs=src_crs, dst_transform=dt,
              dst_crs="EPSG:3857", resampling=resampling, src_nodata=np.nan, dst_nodata=np.nan)
    rgba = colorize(np.nan_to_num(dst, nan=0))
    rgba[np.isnan(dst)] = 0
    Image.fromarray(rgba, "RGBA").save(f"{OUT}/img/{name}.webp", "WEBP", quality=quality, lossless=lossless, method=6)
    b = (dt.c, dt.f + dh * dt.e, dt.c + dw * dt.a, dt.f)
    w_, s_, e_, n_ = transform_bounds("EPSG:3857", "EPSG:4326", *b)
    manifest["rasters"][name] = [[round(s_, 6), round(w_, 6)], [round(n_, 6), round(e_, 6)]]
    print(f"img {name}: {dw}x{dh} {os.path.getsize(f'{OUT}/img/{name}.webp')/1e3:.0f} KB")


def read(path, band=1):
    with rasterio.open(path) as r:
        a = r.read(band).astype(np.float32)
        nd = r.nodata
        if nd is not None and not np.isnan(nd):
            a[a == nd] = np.nan
        return a, r.transform, (r.crs or CRS)


# Coberturas: 10 m -> 40 m (moda) y paleta del QML
COB = {1: "#2d6a2e", 2: "#1b7f79", 3: "#3a7dc9", 4: "#8fd3c8", 5: "#9cc56b", 6: "#d9d26a", 7: "#f2e6b1", 8: "#c0392b", 9: "#e08b2e"}
with rasterio.open(f"{Z4}/Mapas/coberturas_final_corregida.tif") as r:
    a = r.read(1); tr_, crs_ = r.transform, r.crs
lut = np.zeros((256, 4), np.uint8)
for k, hx in COB.items():
    lut[k] = hex2rgb(hx) + [255]
af = a.astype(np.float32); af[a == 0] = np.nan
to_png(af, tr_, crs_, "coberturas", lambda x: lut[x.astype(np.uint8)], resampling=Resampling.mode, dst_res=40, lossless=True)
del a, af

IDON = ramp([(0, "#f5f1e6", 0), (0.05, "#f5f1e6", 200), (0.3, "#e3e7b8", 220), (0.6, "#8cc26f", 255), (0.8, "#2f8a45", 255), (1, "#0b4222", 255)])
RES = ramp([(1, "#f7f7f5", 230), (20, "#e8dcc4", 235), (50, "#f0a35e", 245), (80, "#c65a1e", 255), (100, "#5c2508", 255)])
PCT = ramp([(0, "#f7fbff", 0), (50, "#deebf7", 0), (75, "#9ecae1", 170), (90, "#3182bd", 255), (97, "#08519c", 255), (100, "#08306b", 255)])
BAR = ramp([(0, "#ffffcc", 0), (10, "#ffeda0", 0), (30, "#feb24c", 200), (60, "#f03b20", 255), (80, "#bd0026", 255), (100, "#67000d", 255)])
OMN = {1: "#8c7b6b", 2: "#efeadf", 3: "#fdae6b", 4: "#d94801"}
olut = np.zeros((256, 4), np.uint8)
for k, hx in OMN.items():
    olut[k] = hex2rgb(hx) + [0 if k == 2 else (150 if k == 1 else 255)]
COR = ramp([(0, "#08306b", 255), (250, "#2171b5", 255), (750, "#6baed6", 230), (1500, "#c6dbef", 190), (2000, "#eef4fa", 150), (2001, "#eef4fa", 0)])

pct_stats = {}
for g in GREMIOS:
    for ep in EPOCAS:
        s = f"{g}_{ep}"
        a, t, c = read(f"{Z4}/Mapas/insumos_mapa/idoneidad_{s}.tif")
        to_png(a, t, c, f"idon_{s}", IDON)
        with rasterio.open(f"{Z3}/insumos/resistencias_100m.tif") as r:
            bi = list(r.descriptions).index(f"{s}_c4") + 1
        a, t, c = read(f"{Z3}/insumos/resistencias_100m.tif", bi)
        to_png(a, t, c, f"res_{s}", RES)
        # corriente Circuitscape -> percentil (igual que mapas_3_corriente_percentil)
        a, t, c = read(f"{P1}/circuitscape/resultados/corriente_{s}_c4.tif")
        v = a[np.isfinite(a)]
        order = np.sort(v)
        p = np.full_like(a, np.nan)
        m = np.isfinite(a)
        p[m] = np.searchsorted(order, a[m], side="right") / len(order) * 100
        to_png(p, t, c, f"corr_{s}", PCT)
        a, t, c = read(f"{P1}/barreras/barrera_pct_{s}_c4_r300m.tif")
        to_png(a, t, c, f"bar_{s}", BAR)
        a, t, c = read(f"{Z4}/prioridad/omniscape_clases_{s}_c4.tif")
        to_png(a, t, c, f"omni_{s}", lambda x: olut[x.astype(np.uint8)], lossless=True)
        a, t, c = read(f"{P1}/corredores_v2/corredor_trunc_{s}_c4.tif")
        a[a < 0] = 0; a[a > 2000] = np.nan
        to_png(a, t, c, f"cor_{s}", COR)

# ---------- Fondo: departamentos IGAC alrededor del área ----------
from shapely.geometry import box
dep = gpd.read_file(f"{Z3}/insumos/Departamentos_Junio_2026.gdb", layer="Depto").to_crs(CRS)
b = rd(f"{Z4}/Mapas/insumos_mapa/area_estudio_corregida.gpkg").total_bounds
bb = box(b[0] - 1.2e5, b[1] - 1.2e5, b[2] + 1.2e5, b[3] + 1.2e5)
dep = dep[dep.intersects(bb)].copy(); dep.geometry = dep.geometry.intersection(bb)
save(dep.rename(columns={"DeNombre": "depto"}), "departamentos", 150, keep=["depto"], prec=4)

# ---------- Trampolines prioritarios (nodos del Mapa M11) ----------
TRAMP = {"interior": [26, 40, 43], "frugivoro": [10, 24, 61, 93], "humedal": [21, 44, 49]}
filas = []
for g, ids in TRAMP.items():
    n = rd(f"{Z4}/prioridad/prioridad_nodos_{g}.gpkg"); n["id_grafo"] = n["id_grafo"].astype(int)
    base = gpd.read_file(f"{Z3}/grafos/nodos_grafo_{g}.gpkg", ignore_geometry=True)[["id_grafo", "area_ha"]]
    base["id_grafo"] = base["id_grafo"].astype(int)
    t = n[n.id_grafo.isin(ids)].merge(base, on="id_grafo"); t["gremio"] = g
    t.geometry = t.geometry.representative_point(); filas.append(t)
tn = gpd.GeoDataFrame(pd.concat(filas, ignore_index=True), crs=CRS)
save(tn, "trampolines_nodos", 0, keep=["gremio", "id_grafo", "area_ha", "papel_seca", "prioridad_seca", "BCPC_pct_seca",
     "dPCconnector_seca", "papel_lluviosa", "prioridad_lluviosa", "BCPC_pct_lluviosa"])

manifest["stats"]["estrategias"] = pd.read_csv(f"{Z6}/fase4/comparacion_estrategias.csv").to_dict("records")


def limpiar(o):  # JSON no admite NaN
    if isinstance(o, float) and (o != o or o in (float("inf"), float("-inf"))): return None
    if isinstance(o, dict): return {k: limpiar(v) for k, v in o.items()}
    if isinstance(o, list): return [limpiar(v) for v in o]
    return o


json.dump(limpiar(manifest), open(f"{OUT}/data/manifest.json", "w", encoding="utf-8"), ensure_ascii=False, default=str, allow_nan=False)
print("OK")
