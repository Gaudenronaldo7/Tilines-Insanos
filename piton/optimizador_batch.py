"""
Optimizador de lotes (batching) para el Agente Inteligente.

rutamonterrey.py sabe calcular la ruta entre DOS puntos sobre la red vial
real de Monterrey. Este módulo lo usa como bloque de construcción para
resolver un problema más grande: dado un conjunto de pedidos ya aceptados
("pendientes") más un pedido candidato, ¿cuál es la mejor secuencia de
recolección/entrega para TODOS ellos, y le conviene al repartidor
aceptar el candidato?

Es exactamente el mismo enfoque que routeOptimizer.ts / decisionEngine.ts
en la versión React/TypeScript del proyecto (fuerza bruta sobre las
secuencias válidas + utilidad marginal), aplicado aquí sobre distancias y
tiempos reales de la red vial en vez de estimaciones de línea recta.

No modifica rutamonterrey.py -- solo lo usa.
"""

from rutamonterrey import calcular_ruta

MAX_PEDIDOS_SIMULTANEOS = 3  # subir este número crece las permutaciones factorialmente


def _ruta_cacheada(grafo, origen, destino, cache):
    """calcular_ruta() lanza una consulta de camino más corto sobre el
    grafo real -- no es gratis. Muchas permutaciones comparten el mismo
    tramo origen->destino (solo cambia el ORDEN en que se visitan los
    puntos, no los puntos en sí), así que cachear por par (origen,
    destino) evita recalcular lo mismo cientos de veces.

    Si calcular_ruta() truena (nodo aislado tras un bloqueo, coordenada
    fuera del grafo, etc.) se trata como 'sin camino posible' (None) en
    vez de dejar que la excepción se propague y tumbe la evaluación de
    TODO el lote -- así una sola secuencia imposible simplemente se
    descarta y las demás (incluidos los otros pedidos del batch de 5)
    se siguen evaluando con normalidad.
    """
    clave = (origen, destino)
    if clave not in cache:
        try:
            cache[clave] = calcular_ruta(grafo, origen, destino)
        except Exception:
            cache[clave] = None
    return cache[clave]


def _generar_secuencias_validas(pedidos):
    """
    Todas las secuencias de paradas (recolección/entrega) que respetan
    'recoger antes de entregar' para cada pedido. Para n pedidos hay
    como máximo (2n)!/(2^n) secuencias válidas -- manejable para
    n <= MAX_PEDIDOS_SIMULTANEOS.
    """
    paradas = []
    for p in pedidos:
        paradas.append(("recoleccion", p))
        paradas.append(("entrega", p))

    secuencias = []

    def backtrack(restantes, actual, recogidos):
        if not restantes:
            secuencias.append(list(actual))
            return
        for i, parada in enumerate(restantes):
            tipo, pedido = parada
            if tipo == "entrega" and pedido["id_orden"] not in recogidos:
                continue  # no se puede entregar algo que no se ha recogido
            nuevos_recogidos = recogidos | ({pedido["id_orden"]} if tipo == "recoleccion" else set())
            backtrack(restantes[:i] + restantes[i + 1:], actual + [parada], nuevos_recogidos)

    backtrack(paradas, [], set())
    return secuencias


def _evaluar_secuencia(grafo, posicion_inicial, secuencia, costo_km, cache):
    """Recorre una secuencia de paradas sumando distancia/tiempo/ingreso.
    Devuelve None si algún tramo es físicamente imposible (p. ej. un
    bloqueo total sin ruta alterna)."""
    actual = posicion_inicial
    distancia_total = 0.0
    tiempo_total = 0.0
    tramos = []

    for tipo, pedido in secuencia:
        destino_tramo = pedido["origen"] if tipo == "recoleccion" else pedido["destino"]
        tramo = _ruta_cacheada(grafo, actual, destino_tramo, cache)
        if tramo is None:
            return None
        distancia_total += tramo["distancia_km"]
        tiempo_total += tramo["tiempo_min"]
        tramos.append((tipo, pedido, tramo))
        actual = destino_tramo

    ingreso = sum(pedido["pago_mxn"] for tipo, pedido, _ in tramos if tipo == "entrega")
    gasto_gasolina = distancia_total * costo_km
    utilidad = ingreso - gasto_gasolina

    return {
        "distancia_km": distancia_total,
        "tiempo_min": tiempo_total,
        "ingreso": ingreso,
        "utilidad": utilidad,
        "tramos": tramos,
    }


def optimizar_ruta(grafo, posicion_inicial, pedidos, costo_km, cache=None):
    """Prueba todas las secuencias válidas para 'pedidos' y devuelve la de
    mayor utilidad (ingreso - gasolina). None si ningún pedido es viable."""
    if cache is None:
        cache = {}
    if not pedidos:
        return {"distancia_km": 0.0, "tiempo_min": 0.0, "ingreso": 0.0, "utilidad": 0.0, "tramos": []}

    mejor = None
    for secuencia in _generar_secuencias_validas(pedidos):
        resultado = _evaluar_secuencia(grafo, posicion_inicial, secuencia, costo_km, cache)
        if resultado is None:
            continue
        if mejor is None or resultado["utilidad"] > mejor["utilidad"]:
            mejor = resultado
    return mejor


def evaluar_pedido_para_batch(grafo, posicion_inicial, pedidos_actuales, nuevo_pedido, costo_km,
                                umbral_tasa_reserva_hora):
    """
    Utilidad marginal: compara la mejor ruta SIN el nuevo pedido contra la
    mejor ruta CON él (mismo concepto que calculateMarginalUtility en la
    versión React). Se acepta solo si:
      1. La utilidad marginal es positiva, Y
      2. Su TASA (MXN/hora que aporta ese pedido específico) supera una
         tasa de reserva configurable.

    El punto 2 es importante: sin él, el agente aceptaría cualquier
    pedido con ganancia marginal positiva aunque sea mínima, diluyendo su
    rendimiento general por hora -- el mismo ajuste que se hizo en la
    versión React (minMarginalRatePerHour).
    """
    cache = {}
    ruta_actual = optimizar_ruta(grafo, posicion_inicial, pedidos_actuales, costo_km, cache)
    ruta_candidata = optimizar_ruta(grafo, posicion_inicial, pedidos_actuales + [nuevo_pedido], costo_km, cache)

    if ruta_actual is None or ruta_candidata is None:
        return {
            "aceptar": False, "utilidad_marginal": 0.0, "tasa_marginal_hora": 0.0,
            "tiempo_extra_min": 0.0, "distancia_extra_km": 0.0,
            "razon": "Rechazado: ruta inaccesible (bloqueo vial sin alterna).",
        }

    delta_utilidad = ruta_candidata["utilidad"] - ruta_actual["utilidad"]
    delta_tiempo = ruta_candidata["tiempo_min"] - ruta_actual["tiempo_min"]
    delta_distancia = ruta_candidata["distancia_km"] - ruta_actual["distancia_km"]

    tasa_marginal_hora = (delta_utilidad / delta_tiempo) * 60 if delta_tiempo > 0.01 else delta_utilidad * 60
    aceptar = delta_utilidad > 0 and tasa_marginal_hora >= umbral_tasa_reserva_hora

    if aceptar:
        razon = (
            f"Aceptado: utilidad marginal +{delta_utilidad:.2f} MXN por +{delta_tiempo:.1f} min "
            f"(~{tasa_marginal_hora:.0f} MXN/hora), por encima de la tasa de reserva "
            f"de {umbral_tasa_reserva_hora:.0f} MXN/hora."
        )
    elif delta_utilidad <= 0:
        razon = f"Rechazado: utilidad marginal negativa ({delta_utilidad:.2f} MXN) -- el desvío no se paga solo."
    else:
        razon = (
            f"Rechazado: aunque suma {delta_utilidad:.2f} MXN, su tasa (~{tasa_marginal_hora:.0f} MXN/hora) "
            f"queda por debajo de la tasa de reserva de {umbral_tasa_reserva_hora:.0f} MXN/hora."
        )

    return {
        "aceptar": aceptar,
        "utilidad_marginal": delta_utilidad,
        "tasa_marginal_hora": tasa_marginal_hora,
        "tiempo_extra_min": delta_tiempo,
        "distancia_extra_km": delta_distancia,
        "razon": razon,
    }
