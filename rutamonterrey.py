"""
Calcula distancia y tiempo estimado de ruta entre dos coordenadas
en el área metropolitana de Monterrey, usando la red vial real de
OpenStreetMap (vía OSMnx). También contiene la regla de decisión
EPUT (pesos por minuto) que usa el Agente Inteligente para aceptar
o rechazar pedidos.

Requiere: pip install osmnx
Probado con osmnx 2.1.1
"""

import os
import osmnx as ox

# --- Configuración ---
# OJO: este bbox debe cubrir la MISMA zona donde simulador_pedidos.py
# genera pedidos. Monterrey, San Pedro y Guadalupe son municipios
# separados en OpenStreetMap, así que ox.graph_from_place("Monterrey...")
# por sí solo NO incluye San Pedro ni Guadalupe y dejaba pedidos ahí
# sin cobertura real de calles. Por eso usamos graph_from_bbox.
LAT_MIN, LAT_MAX = 25.6000, 25.7500
LON_MIN, LON_MAX = -100.4000, -100.2000

RUTA_CACHE = "monterrey_metro_drive.graphml"  # nombre nuevo: no reutilices un caché viejo de graph_from_place
VELOCIDAD_FALLBACK_KPH = 30  # para calles sin límite de velocidad etiquetado en OSM


def cargar_grafo(forzar_descarga: bool = False):
    """
    Carga el grafo vial (tipo 'drive') del área metropolitana de Monterrey
    (el bbox de arriba, que coincide con simulador_pedidos.py).

    Si ya existe una copia en caché local, la usa directamente (rápido,
    y sirve como respaldo si se cae el internet del evento). Si no,
    la descarga de OpenStreetMap, le agrega velocidad y tiempo de
    viaje a cada arista, y la guarda en caché para la próxima vez.
    """
    if not forzar_descarga and os.path.exists(RUTA_CACHE):
        print(f"Cargando grafo desde caché: {RUTA_CACHE}")
        return ox.load_graphml(RUTA_CACHE)

    print("Descargando red vial de OpenStreetMap (zona metropolitana)...")
    bbox = (LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)  # (left, bottom, right, top)
    grafo = ox.graph_from_bbox(bbox, network_type="drive")
    grafo = ox.add_edge_speeds(grafo, fallback=VELOCIDAD_FALLBACK_KPH)
    grafo = ox.add_edge_travel_times(grafo)

    ox.save_graphml(grafo, RUTA_CACHE)
    print(f"Grafo guardado en caché: {RUTA_CACHE}")
    return grafo


def calcular_ruta(grafo, origen: tuple, destino: tuple, criterio: str = "travel_time"):
    """
    Calcula la ruta entre dos coordenadas (lat, lon).

    criterio:
        "travel_time" -> ruta más rápida (recomendado para el motor EPUT)
        "length"      -> ruta más corta en distancia

    Devuelve un dict con distancia_km, tiempo_min y los nodos de la ruta,
    o None si no existe camino entre los dos puntos (p. ej. si una
    avenida clave está bloqueada/eliminada del grafo).
    """
    nodo_origen = ox.nearest_nodes(grafo, X=origen[1], Y=origen[0])
    nodo_destino = ox.nearest_nodes(grafo, X=destino[1], Y=destino[0])

    ruta = ox.shortest_path(grafo, nodo_origen, nodo_destino, weight=criterio)
    if ruta is None:
        return None

    tramos = ox.routing.route_to_gdf(grafo, ruta, weight=criterio)

    return {
        "nodos_ruta": ruta,
        "distancia_km": round(tramos["length"].sum() / 1000, 3),
        "tiempo_min": round(tramos["travel_time"].sum() / 60, 2),
    }


def evaluar_orden(orden, ubicacion_actual, grafo, umbral_eput=2.5):
    """
    Decide si conviene aceptar 'orden' desde 'ubicacion_actual'.

    EPUT = pago_mxn / minutos_totales (ir a recoger + entregar).
    umbral_eput=0 acepta cualquier pedido físicamente posible, sin
    razonar si conviene (así es como app.py modela al Novato).
    """
    # 1. Calcular tiempo hacia el restaurante (recolección)
    ruta_rec = calcular_ruta(grafo, ubicacion_actual, orden["origen"])
    if not ruta_rec:
        return False, 0

    # 2. Calcular tiempo hacia el cliente (entrega)
    ruta_ent = calcular_ruta(grafo, orden["origen"], orden["destino"])
    if not ruta_ent:
        return False, 0

    tiempo_total_min = ruta_rec["tiempo_min"] + ruta_ent["tiempo_min"]

    # 3. Calcular EPUT (pesos por minuto)
    eput = orden["pago_mxn"] / tiempo_total_min if tiempo_total_min > 0 else 0

    # 4. Decisión: ¿Supera nuestro criterio de parada óptima?
    aceptada = eput >= umbral_eput
    return aceptada, eput


def obtener_coordenadas_ruta(grafo, ruta_nodos):
    """
    Convierte una lista de nodos de OSMnx en una lista de coordenadas (lat, lon)
    para poder dibujarlas en el mapa de Folium.
    """
    coordenadas = []
    for nodo in ruta_nodos:
        lat = grafo.nodes[nodo]['y']
        lon = grafo.nodes[nodo]['x']
        coordenadas.append((lat, lon))
    return coordenadas


if __name__ == "__main__":
    G = cargar_grafo()

    # Ejemplo: Macroplaza -> Parque Fundidora
    origen = (25.6714, -100.3095)
    destino = (25.6797, -100.2833)

    resultado = calcular_ruta(G, origen, destino, criterio="travel_time")

    if resultado is None:
        print("No se encontró una ruta entre esos dos puntos.")
    else:
        print(f"Distancia: {resultado['distancia_km']} km")
        print(f"Tiempo estimado: {resultado['tiempo_min']} min")

import math

def bloquear_area(grafo, lat, lon, radio_metros=300):
    """
    Simula un choque/cierre vial eliminando temporalmente los nodos 
    del grafo que estén dentro de un radio específico.
    """
    radio_grados = radio_metros / 111000  # Conversión rápida metros a grados
    nodos_a_eliminar = []
    
    for nodo, datos in grafo.nodes(data=True):
        if math.hypot(datos['x'] - lon, datos['y'] - lat) < radio_grados:
            nodos_a_eliminar.append(nodo)
            
    grafo.remove_nodes_from(nodos_a_eliminar)
    return len(nodos_a_eliminar)