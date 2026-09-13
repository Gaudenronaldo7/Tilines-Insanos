import random
import time

# --- Bounding Box Aproximado ---
LAT_MIN, LAT_MAX = 25.6000, 25.7500
LON_MIN, LON_MAX = -100.4000, -100.2000

# NUEVO: Función para fijar el determinismo
def fijar_semilla(semilla):
    random.seed(semilla)

def generar_orden_mock(id_orden, lluvia_activa=False):
    """
    Genera un 'ping' de la aplicación con origen, destino y pago.
    """
    origen = (random.uniform(LAT_MIN, LAT_MAX), random.uniform(LON_MIN, LON_MAX))
    destino = (random.uniform(LAT_MIN, LAT_MAX), random.uniform(LON_MIN, LON_MAX))
    
    pago_base = random.randint(30, 120) 
    
    # Si hay lluvia, el algoritmo del juez fuerza el Surge
    if lluvia_activa:
        surge_multiplier = random.uniform(1.5, 2.5)
    else:
        # 20% de probabilidad normal
        surge_multiplier = random.choice([1.0, 1.0, 1.0, 1.0, 1.5]) 
    
    return {
        "id_orden": id_orden,
        "origen": origen,
        "destino": destino,
        "pago_mxn": round(pago_base * surge_multiplier, 2),
        "surge": surge_multiplier > 1.0,
        "timestamp": time.time()
    }

def iniciar_stream(cantidad_pedidos=10):
    """
    Simula un flujo constante de pedidos cayendo en la app.
    """
    print("Iniciando turno del repartidor... Esperando pings.")
    ordenes = []
    for i in range(cantidad_pedidos):
        nueva_orden = generar_orden_mock(i + 1)
        ordenes.append(nueva_orden)
        # En la demo real, aquí pausarías con time.sleep(1) para simular el paso del tiempo
    return ordenes

if __name__ == "__main__":
    pedidos = iniciar_stream(3)
    for p in pedidos:
        print(f"Ping #{p['id_orden']} | Pago: ${p['pago_mxn']} | Surge: {p['surge']}")
        