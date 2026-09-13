"""
Interfaz de la app "Agente Autónomo vs. Repartidor Novato".

Motor:
  - rutamonterrey.py    -> red vial real de Monterrey (OSMnx) + regla EPUT
                            de tu compañero. Sin modificar.
  - simulador_pedidos.py -> generador de pedidos. Sin modificar.
  - optimizador_batch.py -> NUEVO: le da al Agente Inteligente la
                            capacidad de cargar varios pedidos a la vez
                            (batching) usando utilidad marginal, igual que
                            la versión React/TypeScript del proyecto
                            (routeOptimizer.ts + decisionEngine.ts), pero
                            aplicada sobre la red vial real en vez de
                            estimaciones de línea recta.

Interfaz: reorganizada para parecerse al dashboard de la versión React
(tarjetas de métricas, panel de decisión con la razón del algoritmo,
panel de "lote activo", pestañas) y con varios de sus parámetros de
medición agregados: $/hora, $/km, tasa de reserva marginal, batch rate,
tamaño promedio de lote.
"""

import time as time_lib

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

from rutamonterrey import cargar_grafo, obtener_coordenadas_ruta, bloquear_area
from simulador_pedidos import generar_orden_mock, fijar_semilla
from optimizador_batch import optimizar_ruta, evaluar_pedido_para_batch, MAX_PEDIDOS_SIMULTANEOS

st.set_page_config(layout="wide", page_title="Courier AI — Copiloto Definitivo", page_icon="🚗")

POSICION_INICIAL = (25.6714, -100.3095)  # Macroplaza — ambos agentes arrancan aquí

# ---------------------------------------------------------------------------
# Estilo: clases propias (no tocamos el DOM interno de Streamlit, así que
# no se rompe entre versiones), inspiradas en el dashboard de la versión React.
# ---------------------------------------------------------------------------
st.markdown("""
<style>
.cai-card-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 6px 0 10px 0; }
.cai-card {
    flex: 1 1 130px; display: flex; align-items: center; gap: 10px;
    background: rgba(15,23,42,0.55); border: 1px solid #1e293b;
    border-radius: 10px; padding: 10px 12px;
}
.cai-icon-box {
    width: 32px; height: 32px; border-radius: 8px; background: rgba(34,211,238,0.10);
    display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0;
}
.cai-card .cai-label { font-size: 10px; text-transform: uppercase; letter-spacing: .04em; color: #64748b; }
.cai-card .cai-value { font-size: 18px; font-weight: 700; color: #e2e8f0; font-family: ui-monospace, monospace; }
.cai-panel-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 2px; }
.cai-panel-header .cai-title { font-size: 15px; font-weight: 700; }
.cai-panel-header .cai-badge {
    font-family: ui-monospace, monospace; font-size: 11px; color: #94a3b8;
    background: rgba(30,41,59,0.6); border-radius: 6px; padding: 2px 8px;
}
.cai-footer-row { display: flex; justify-content: space-between; font-size: 11.5px; color: #64748b;
    font-family: ui-monospace, monospace; padding: 2px 2px; }
.cai-footer-row .cai-footer-value { color: #cbd5e1; }
.cai-footer-row .cai-footer-neg { color: #fb7185; }
.cai-decision {
    border-radius: 10px; padding: 14px; margin-bottom: 8px; font-family: ui-monospace, monospace;
}
.cai-decision-accept { background: rgba(16,185,129,0.08); border: 1px solid rgba(16,185,129,0.35); }
.cai-decision-reject { background: rgba(244,63,94,0.08); border: 1px solid rgba(244,63,94,0.35); }
.cai-decision-title { font-size: 15px; font-weight: 700; margin-bottom: 8px; }
.cai-decision-accept .cai-decision-title { color: #34d399; }
.cai-decision-reject .cai-decision-title { color: #fb7185; }
.cai-decision-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 12px; font-size: 12.5px; color: #cbd5e1; margin-bottom: 8px; }
.cai-decision-razon { font-size: 12.5px; color: #94a3b8; font-family: sans-serif; line-height: 1.4; }
.cai-live-badge { display:inline-flex; align-items:center; gap:6px; font-family: ui-monospace, monospace; font-size: 13px; color:#34d399; }
.cai-dot { width:8px;height:8px;border-radius:999px; background:#34d399; display:inline-block; animation: cai-pulse 1.4s ease-in-out infinite; }
@keyframes cai-pulse { 0%,100% {opacity:1;} 50% {opacity:.35;} }
.cai-batch-row { display:flex; align-items:center; gap:8px; font-family: ui-monospace, monospace; font-size: 12.5px;
    background: rgba(30,41,59,0.5); border-radius: 6px; padding: 6px 10px; margin-bottom: 4px; }
.cai-batch-badge { font-size: 10px; padding: 1px 6px; border-radius: 4px; }
.cai-batch-pickup { background: rgba(8,145,178,0.25); color: #67e8f9; }
.cai-batch-delivery { background: rgba(124,58,237,0.25); color: #c4b5fd; }
</style>
""", unsafe_allow_html=True)


def render_panel_header(titulo, entregados, ofrecidos):
    """Título del panel + insignia 'X/Y entregados', igual que en el
    dashboard de la versión React."""
    st.markdown(f"""
    <div class="cai-panel-header">
        <span class="cai-title">{titulo}</span>
        <span class="cai-badge">{entregados}/{ofrecidos} entregados</span>
    </div>
    """, unsafe_allow_html=True)


def render_metric_cards(items):
    """items: lista de (icono, etiqueta, valor) -> fila de tarjetas HTML
    con el icono en su propia cajita, como en el dashboard de referencia."""
    tarjetas = "".join(
        f'<div class="cai-card"><div class="cai-icon-box">{icono}</div>'
        f'<div><div class="cai-label">{etiqueta}</div>'
        f'<div class="cai-value">{valor}</div></div></div>'
        for icono, etiqueta, valor in items
    )
    st.markdown(f'<div class="cai-card-row">{tarjetas}</div>', unsafe_allow_html=True)


def render_footer_stats(items):
    """items: lista de (etiqueta, valor, es_negativo) -> filas delgadas de
    estadísticas secundarias (batch rate, gasto en gasolina...)."""
    filas = "".join(
        f'<div class="cai-footer-row"><span>{etiqueta}</span>'
        f'<span class="cai-footer-value{" cai-footer-neg" if es_negativo else ""}">{valor}</span></div>'
        for etiqueta, valor, es_negativo in items
    )
    st.markdown(filas, unsafe_allow_html=True)


def render_decision_panel(pedido_id, decision):
    clase = "cai-decision-accept" if decision["aceptar"] else "cai-decision-reject"
    titulo = f"✓ ACEPTAR PEDIDO #{pedido_id}" if decision["aceptar"] else f"✕ RECHAZAR PEDIDO #{pedido_id}"
    st.markdown(f"""
    <div class="cai-decision {clase}">
        <div class="cai-decision-title">{titulo}</div>
        <div class="cai-decision-grid">
            <span>Utilidad marginal</span><span>{decision['utilidad_marginal']:+.2f} MXN</span>
            <span>Tasa marginal</span><span>{decision['tasa_marginal_hora']:.0f} MXN/hora</span>
            <span>Tiempo extra</span><span>{decision['tiempo_extra_min']:+.1f} min</span>
            <span>Distancia extra</span><span>{decision['distancia_extra_km']:+.2f} km</span>
        </div>
        <div class="cai-decision-razon">{decision['razon']}</div>
    </div>
    """, unsafe_allow_html=True)


def render_batch_panel(pedidos_pendientes):
    if not pedidos_pendientes:
        st.caption("Sin pedidos en el lote activo.")
        return
    filas = ""
    for p in pedidos_pendientes:
        filas += (
            f'<div class="cai-batch-row">'
            f'<span class="cai-batch-badge cai-batch-pickup">RECOGER</span>'
            f'<span>#{p["id_orden"]}</span>'
            f'<span style="margin-left:auto;color:#94a3b8;">${p["pago_mxn"]} MXN</span>'
            f'</div>'
        )
    st.markdown(filas, unsafe_allow_html=True)
    st.caption(f"{len(pedidos_pendientes)} de {MAX_PEDIDOS_SIMULTANEOS} espacios usados")


# ---------------------------------------------------------------------------
# Carga del grafo (cacheada)
# ---------------------------------------------------------------------------
@st.cache_resource
def get_grafo():
    return cargar_grafo()


G = get_grafo()


# ---------------------------------------------------------------------------
# Estado de sesión
# ---------------------------------------------------------------------------
def _agente_vacio():
    return {
        "pos": POSICION_INICIAL,
        "ganancia": 0.0,
        "km": 0.0,
        "tiempo_min": 0.0,
        "pedidos_ofrecidos": 0,
        "pedidos_rechazados": 0,
        "pedidos_entregados": 0,
        "batches_despachados": 0,
        "suma_tamanos_batch": 0,
        "entregados_en_batch": 0,
        "pedidos_pendientes": [],
        "ruta_dibujo": None,
        "ultimo_batch": None,
    }


def inicializar_estado():
    if "agentes" not in st.session_state:
        st.session_state.agentes = {"novato": _agente_vacio(), "agente": _agente_vacio()}
    if "pedido_num" not in st.session_state:
        st.session_state.pedido_num = 0
    if "ultima_decision_agente" not in st.session_state:
        st.session_state.ultima_decision_agente = None
    if "ultimo_pedido_id" not in st.session_state:
        st.session_state.ultimo_pedido_id = None
    if "historial" not in st.session_state:
        st.session_state.historial = []
    if "lluvia_activa" not in st.session_state:
        st.session_state.lluvia_activa = False
    if "bloqueo_activo" not in st.session_state:
        st.session_state.bloqueo_activo = False


inicializar_estado()


# ---------------------------------------------------------------------------
# Lógica de negocio
# ---------------------------------------------------------------------------
def despachar_batch(nombre, grafo, costo_km):
    """Ejecuta la mejor ruta para todos los pedidos pendientes de 'nombre':
    cobra, mueve al repartidor y limpia la cola. Es el equivalente a que el
    repartidor efectivamente maneje el lote completo."""
    estado = st.session_state.agentes[nombre]
    pendientes = estado["pedidos_pendientes"]
    if not pendientes:
        return None

    resultado = optimizar_ruta(grafo, estado["pos"], pendientes, costo_km)

    if resultado is None:
        estado["pedidos_pendientes"] = []
        return {"error": "Lote inaccesible (bloqueo vial sin alterna); pedidos descartados."}

    tamano_batch = len(pendientes)
    coords = []
    for _tipo, _pedido, tramo in resultado["tramos"]:
        coords.extend(obtener_coordenadas_ruta(grafo, tramo["nodos_ruta"]))

    estado["ganancia"] += resultado["ingreso"]
    estado["km"] += resultado["distancia_km"]
    estado["tiempo_min"] += resultado["tiempo_min"]
    estado["pedidos_entregados"] += tamano_batch
    estado["batches_despachados"] += 1
    estado["suma_tamanos_batch"] += tamano_batch
    if tamano_batch > 1:
        estado["entregados_en_batch"] += tamano_batch

    ultimo_tipo, ultimo_pedido, _ = resultado["tramos"][-1]
    estado["pos"] = ultimo_pedido["destino"] if ultimo_tipo == "entrega" else ultimo_pedido["origen"]
    estado["ruta_dibujo"] = coords
    estado["ultimo_batch"] = pendientes
    estado["pedidos_pendientes"] = []

    return {"tamano_batch": tamano_batch, "ingreso": resultado["ingreso"], "distancia_km": resultado["distancia_km"]}


def procesar_pedido_novato(orden, grafo, costo_km):
    """El Novato no razona ni encadena: si el pedido es físicamente
    posible, lo despacha de inmediato, solo."""
    estado = st.session_state.agentes["novato"]
    estado["pedidos_ofrecidos"] += 1

    prueba = optimizar_ruta(grafo, estado["pos"], [orden], costo_km)
    if prueba is None:
        estado["pedidos_rechazados"] += 1
        return {"aceptada": False, "eput": 0.0, "error": "Inaccesible (montaña/bloqueo total)"}

    estado["pedidos_pendientes"] = [orden]
    despachar_batch("novato", grafo, costo_km)
    eput = orden["pago_mxn"] / prueba["tiempo_min"] if prueba["tiempo_min"] > 0 else 0
    return {"aceptada": True, "eput": round(eput, 2)}


def procesar_pedido_agente(orden, grafo, costo_km, umbral_tasa_reserva):
    """El Agente Inteligente sí encadena: evalúa la utilidad marginal de
    sumar el pedido al lote que ya trae. Si el lote está lleno, lo
    despacha primero para liberar espacio y luego re-evalúa el pedido
    nuevo contra un lote vacío."""
    estado = st.session_state.agentes["agente"]
    estado["pedidos_ofrecidos"] += 1

    if len(estado["pedidos_pendientes"]) >= MAX_PEDIDOS_SIMULTANEOS:
        despachar_batch("agente", grafo, costo_km)

    decision = evaluar_pedido_para_batch(
        grafo, estado["pos"], estado["pedidos_pendientes"], orden, costo_km, umbral_tasa_reserva
    )

    if decision["aceptar"]:
        estado["pedidos_pendientes"].append(orden)
    else:
        estado["pedidos_rechazados"] += 1

    return decision


def simular_un_pedido(costo_km, umbral_tasa_reserva):
    st.session_state.pedido_num += 1
    orden = generar_orden_mock(st.session_state.pedido_num, lluvia_activa=st.session_state.lluvia_activa)
    st.session_state.ultimo_pedido_id = orden["id_orden"]

    resultado_novato = procesar_pedido_novato(orden, G, costo_km)
    decision_agente = procesar_pedido_agente(orden, G, costo_km, umbral_tasa_reserva)
    st.session_state.ultima_decision_agente = (orden["id_orden"], decision_agente)

    st.session_state.historial.append({
        "id": orden["id_orden"], "pago_mxn": orden["pago_mxn"], "surge": orden["surge"],
        "novato_acepta": resultado_novato["aceptada"],
        "agente_acepta": decision_agente["aceptar"],
        "utilidad_marginal_agente": round(decision_agente["utilidad_marginal"], 2),
        "tasa_marginal_agente_hora": round(decision_agente["tasa_marginal_hora"], 1),
    })


def calcular_metricas(nombre_agente: str, costo_km: float) -> dict:
    estado = st.session_state.agentes[nombre_agente]
    ingreso = estado["ganancia"]
    km = estado["km"]
    tiempo_min = estado["tiempo_min"]
    gasto = km * costo_km
    neta = ingreso - gasto
    rentabilidad_km = neta / km if km > 0 else 0.0
    rentabilidad_hora = neta / (tiempo_min / 60) if tiempo_min > 0 else 0.0
    entregados = estado["pedidos_entregados"]
    batch_rate = (estado["entregados_en_batch"] / entregados * 100) if entregados > 0 else 0.0
    avg_batch = (estado["suma_tamanos_batch"] / estado["batches_despachados"]) if estado["batches_despachados"] > 0 else 0.0
    return {
        "ingreso": ingreso, "km": km, "tiempo_min": tiempo_min, "gasto": gasto, "neta": neta,
        "rentabilidad_km": rentabilidad_km, "rentabilidad_hora": rentabilidad_hora,
        "pedidos_ofrecidos": estado["pedidos_ofrecidos"], "pedidos_rechazados": estado["pedidos_rechazados"],
        "pedidos_entregados": entregados, "batch_rate": batch_rate, "avg_batch_size": avg_batch,
    }


def dibujar_mapa(nombre, color, key):
    estado = st.session_state.agentes[nombre]
    m = folium.Map(location=estado["pos"], zoom_start=13)

    if st.session_state.bloqueo_activo:
        folium.Circle(
            location=[25.6795, -100.3470], radius=400, color="red", fill=True,
            fill_color="red", fill_opacity=0.4, tooltip="Zona de Choque / Bloqueo Vial",
        ).add_to(m)

    folium.Marker(estado["pos"], tooltip="Posición actual",
                  icon=folium.Icon(color=color, icon="car", prefix="fa")).add_to(m)

    if estado["ruta_dibujo"]:
        folium.PolyLine(estado["ruta_dibujo"], color=color, weight=5, opacity=0.8).add_to(m)

    if estado["ultimo_batch"]:
        for p in estado["ultimo_batch"]:
            folium.Marker(p["origen"], tooltip=f"Recolección #{p['id_orden']}",
                          icon=folium.Icon(color="blue")).add_to(m)
            folium.Marker(p["destino"], tooltip=f"Entrega #{p['id_orden']}",
                          icon=folium.Icon(color="black")).add_to(m)

    st_folium(m, width=None, height=420, key=key, use_container_width=True)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("🚗 Courier AI")
st.sidebar.caption("Copiloto Definitivo — panel de control")

st.sidebar.header("⚙️ Parámetros del agente")
umbral_tasa_reserva = st.sidebar.slider(
    "Tasa de reserva (MXN/hora)", min_value=0, max_value=300, value=100, step=10,
    help="El Agente Inteligente solo suma un pedido a su lote si el rendimiento MARGINAL de ese "
         "pedido específico (no el pedido completo, solo lo que ese pedido agrega) supera esta tasa.",
)
costo_km = st.sidebar.slider("⛽ Costo de gasolina (MXN/km)", 1.0, 5.0, 2.0, 0.1)
st.sidebar.caption(f"📦 Capacidad máxima de lote: {MAX_PEDIDOS_SIMULTANEOS} pedidos simultáneos")

st.sidebar.divider()
st.sidebar.header("🌱 Auditoría (jueces)")
semilla_juez = st.sidebar.number_input("Semilla (seed)", min_value=1, value=42,
                                        help="Fija la semilla aleatoria para que la simulación sea replicable.")

st.sidebar.divider()
st.sidebar.header("⚡ Eventos sorpresa")

if st.sidebar.button("🌧️ Alternar lluvia (surge)", use_container_width=True):
    st.session_state.lluvia_activa = not st.session_state.lluvia_activa
    estado_clima = "ACTIVADA (tarifas altas)" if st.session_state.lluvia_activa else "DESACTIVADA"
    st.sidebar.success(f"Lluvia {estado_clima}")

etiqueta_bloqueo = "🟢 Reabrir Av. Gonzalitos" if st.session_state.bloqueo_activo else "🚧 Bloquear Av. Gonzalitos"
if st.sidebar.button(etiqueta_bloqueo, use_container_width=True):
    if not st.session_state.bloqueo_activo:
        nodos_borrados = bloquear_area(G, 25.6795, -100.3470, radio_metros=400)
        st.session_state.bloqueo_activo = True
        st.sidebar.error(f"¡Gonzalitos cerrada! {nodos_borrados} cruces eliminados.")
    else:
        get_grafo.clear()
        st.session_state.bloqueo_activo = False
        st.sidebar.success("Av. Gonzalitos reabierta (grafo recargado).")
        st.rerun()

st.sidebar.divider()
if st.sidebar.button("🔄 Reiniciar simulación total", use_container_width=True):
    fijar_semilla(semilla_juez)
    for clave in list(st.session_state.keys()):
        del st.session_state[clave]
    st.rerun()

st.sidebar.divider()
st.sidebar.header("🔑 Conexión LLM")
gemini_api_key = st.sidebar.text_input("API Key de Google Gemini", type="password",
                                        help="Obtenla gratis en Google AI Studio.")


# ---------------------------------------------------------------------------
# Encabezado
# ---------------------------------------------------------------------------
col_titulo, col_estado = st.columns([3, 1])
with col_titulo:
    st.title("🚗 Agente Autónomo vs. Repartidor Novato")
    st.caption(
        "El **Novato** acepta cualquier pedido y lo entrega solo, uno por uno. El **Agente Inteligente** "
        "puede cargar hasta " + str(MAX_PEDIDOS_SIMULTANEOS) + " pedidos a la vez y solo suma uno nuevo si "
        "su rendimiento marginal supera la tasa de reserva. Ambos usan la red vial real de Monterrey."
    )
with col_estado:
    st.markdown(
        '<div style="text-align:right;padding-top:18px;">'
        '<span class="cai-live-badge"><span class="cai-dot"></span> SIMULACIÓN ACTIVA</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="text-align:right;font-family:ui-monospace,monospace;font-size:12px;color:#64748b;">'
        f'Pedido #{st.session_state.pedido_num}</div>',
        unsafe_allow_html=True,
    )

col_btn1, col_btn2, col_btn3, col_info = st.columns([1, 1, 1, 2])
with col_btn1:
    disparar_uno = st.button("🔔 Simular 1 pedido", use_container_width=True)
with col_btn2:
    disparar_varios = st.button("⏩ Simular 5 pedidos", use_container_width=True)
with col_btn3:
    hay_pendientes = len(st.session_state.agentes["agente"]["pedidos_pendientes"]) > 0
    despachar_manual = st.button("🚚 Despachar lote", use_container_width=True, disabled=not hay_pendientes)

if disparar_uno:
    try:
        simular_un_pedido(costo_km, umbral_tasa_reserva)
    except Exception as e:
        st.error(f"No se pudo procesar el pedido (ruta imposible): {e}")

if disparar_varios:
    errores = 0
    for _ in range(5):
        try:
            simular_un_pedido(costo_km, umbral_tasa_reserva)
        except Exception:
            errores += 1
            continue  # esta ruta era imposible -- seguimos con el siguiente pedido del lote de 5
    if errores:
        st.warning(f"⚠️ {errores} de 5 pedido(s) no se pudieron procesar (ruta imposible) y se omitieron.")

if despachar_manual:
    try:
        despachar_batch("agente", G, costo_km)
    except Exception as e:
        st.error(f"No se pudo despachar el lote: {e}")

with col_info:
    if st.session_state.ultimo_pedido_id is not None:
        ultimo = st.session_state.historial[-1]
        surge_txt = " ⚡ SURGE (LLUVIA)" if st.session_state.lluvia_activa else (" ⚡ SURGE" if ultimo["surge"] else "")
        st.write(f"**Pedido #{ultimo['id']}** — pago ${ultimo['pago_mxn']} MXN{surge_txt}")
    else:
        st.info("Todavía no hay pedidos. Dale clic a 'Simular' para arrancar el turno.")

st.divider()


# ---------------------------------------------------------------------------
# Pestañas
# ---------------------------------------------------------------------------
tab_mapas, tab_comparativa, tab_historial, tab_reporte = st.tabs(
    ["🗺️ Simulación en vivo", "📊 Comparativa", "📋 Historial", "🧠 Reporte IA"]
)

with tab_mapas:
    col1, col2 = st.columns(2)

    with col1:
        m_n = calcular_metricas("novato", costo_km)
        render_panel_header("🚶 Novato (acepta todo, sin encadenar)", m_n["pedidos_entregados"], m_n["pedidos_ofrecidos"])
        render_metric_cards([
            ("💰", "Ganancia neta", f"${m_n['neta']:.2f}"),
            ("📦", "Entregados", f"{m_n['pedidos_entregados']}"),
            ("🛣️", "Km totales", f"{m_n['km']:.2f}"),
            ("⏱️", "Tiempo usado", f"{m_n['tiempo_min']:.0f} min"),
            ("📈", "$/hora", f"${m_n['rentabilidad_hora']:.2f}"),
            ("💹", "$/km", f"${m_n['rentabilidad_km']:.2f}"),
        ])
        render_footer_stats([
            ("Batch rate", f"{m_n['batch_rate']:.0f}%", False),
            (f"Gasto gasolina ({m_n['tiempo_min']:.0f} min)", f"-${m_n['gasto']:.2f}", True),
        ])
        dibujar_mapa("novato", color="red", key="mapa_novato")

    with col2:
        m_a = calcular_metricas("agente", costo_km)
        render_panel_header("🤖 Agente Inteligente (batching + tasa de reserva)", m_a["pedidos_entregados"], m_a["pedidos_ofrecidos"])
        render_metric_cards([
            ("💰", "Ganancia neta", f"${m_a['neta']:.2f}"),
            ("📦", "Entregados", f"{m_a['pedidos_entregados']}"),
            ("🛣️", "Km totales", f"{m_a['km']:.2f}"),
            ("⏱️", "Tiempo usado", f"{m_a['tiempo_min']:.0f} min"),
            ("📈", "$/hora", f"${m_a['rentabilidad_hora']:.2f}"),
            ("💹", "$/km", f"${m_a['rentabilidad_km']:.2f}"),
        ])
        render_footer_stats([
            ("Batch rate", f"{m_a['batch_rate']:.0f}% (avg {m_a['avg_batch_size']:.2f})", False),
            (f"Gasto gasolina ({m_a['tiempo_min']:.0f} min)", f"-${m_a['gasto']:.2f}", True),
        ])
        dibujar_mapa("agente", color="green", key="mapa_agente")

    st.divider()
    col_decision, col_batch = st.columns(2)
    with col_decision:
        st.markdown("##### 🧠 Decisión del agente")
        if st.session_state.ultima_decision_agente is None:
            st.caption("Esperando el primer pedido...")
        else:
            pid, decision = st.session_state.ultima_decision_agente
            render_decision_panel(pid, decision)
    with col_batch:
        st.markdown("##### 📦 Lote activo (agente)")
        render_batch_panel(st.session_state.agentes["agente"]["pedidos_pendientes"])

with tab_comparativa:
    if not st.session_state.historial:
        st.info("Simula al menos un pedido para ver la comparación entre agentes.")
    else:
        m_n = calcular_metricas("novato", costo_km)
        m_a = calcular_metricas("agente", costo_km)

        ahorro_km = m_n["km"] - m_a["km"]
        porcentaje_ahorro = (ahorro_km / m_n["km"] * 100) if m_n["km"] > 0 else 0

        st.subheader("🏆 Resumen de superioridad algorítmica")
        colA, colB, colC, colD = st.columns(4)
        colA.metric("Distancia recorrida", f"{m_a['km']:.1f} km",
                    f"-{porcentaje_ahorro:.1f}% vs Novato", delta_color="inverse")
        colB.metric("Rentabilidad", f"{m_a['rentabilidad_hora']:.2f} MXN/hora",
                    f"{m_a['rentabilidad_hora'] - m_n['rentabilidad_hora']:+.2f} vs Novato")
        colC.metric("Selectividad (EPUT marginal)", f"{m_a['pedidos_entregados']} de {m_a['pedidos_ofrecidos']}",
                    "Solo los más rentables", delta_color="off")
        colD.metric("Batch rate", f"{m_a['batch_rate']:.0f}%",
                    f"Novato: 0% (nunca encadena)", delta_color="off")

        st.caption("Estructura financiera: ¿cuánto de lo cobrado se quemó en gasolina?")
        df_finanzas = pd.DataFrame({
            "💰 Ganancia Neta (bolsillo)": [m_n["neta"], m_a["neta"]],
            "⛽ Gasto en gasolina (pérdida)": [m_n["gasto"], m_a["gasto"]],
        }, index=["Novato (acepta todo)", "Agente Inteligente"])
        st.bar_chart(df_finanzas)

        st.caption("Ganancia bruta acumulada por pedido")
        df_hist = pd.DataFrame(st.session_state.historial)
        df_hist["ganancia_novato_acum"] = df_hist.apply(
            lambda row: row["pago_mxn"] if row["novato_acepta"] else 0, axis=1
        ).cumsum()
        df_hist["ganancia_agente_acum"] = df_hist.apply(
            lambda row: row["pago_mxn"] if row["agente_acepta"] else 0, axis=1
        ).cumsum()
        st.line_chart(df_hist.set_index("id")[["ganancia_novato_acum", "ganancia_agente_acum"]])

with tab_historial:
    if not st.session_state.historial:
        st.info("Sin pedidos todavía.")
    else:
        df_hist = pd.DataFrame(st.session_state.historial)
        st.dataframe(df_hist, use_container_width=True)

        jsonl_data = df_hist.to_json(orient="records", lines=True)
        st.download_button(
            label="📥 Descargar Event Log (JSONL)", data=jsonl_data,
            file_name=f"event_log_seed_{semilla_juez}.jsonl", mime="application/jsonl",
            help="Archivo para validar con python validate_format.py",
        )

with tab_reporte:
    st.header("🧠 Razonamiento del agente (powered by Gemini)")

    if st.button("Generar Reporte de Fin de Turno", type="primary", use_container_width=True):
        if not gemini_api_key:
            st.error("¡Falta la llave! Ingresa tu API Key de Gemini en la barra lateral para continuar.")
        elif len(st.session_state.historial) == 0:
            st.warning("El historial está vacío. ¡Simula algunos pedidos primero!")
        else:
            with st.spinner("El Agente está analizando la telemetría y redactando su justificación..."):
                try:
                    import google.generativeai as genai

                    m_n = calcular_metricas("novato", costo_km)
                    m_a = calcular_metricas("agente", costo_km)

                    genai.configure(api_key=gemini_api_key)
                    modelo = genai.GenerativeModel("gemini-3.6-flash")

                    datos_novato = f"Ganancia Neta: {m_n['neta']:.2f} MXN, Km Totales: {m_n['km']:.2f}"
                    datos_agente = (
                        f"Ganancia Neta: {m_a['neta']:.2f} MXN, Km Totales: {m_a['km']:.2f}, "
                        f"Batch rate: {m_a['batch_rate']:.0f}%, Tamaño de lote promedio: {m_a['avg_batch_size']:.2f}"
                    )
                    historial_str = str(st.session_state.historial)

                    prompt = f"""
                    Actúa como el cerebro del Agente Autónomo de Ruteo.
                    Acabas de terminar un turno con este historial de pedidos: {historial_str}.
                    Tus resultados (Agente) fueron: {datos_agente}. Tu rentabilidad fue de {m_a['rentabilidad_hora']:.2f} MXN/hora.
                    Los del Novato fueron: {datos_novato}. Su rentabilidad fue de {m_n['rentabilidad_hora']:.2f} MXN/hora.

                    En 3 párrafos cortos, explica a los jueces:
                    1. Por qué tu estrategia de utilidad marginal (aceptar/rechazar) y de encadenar
                       pedidos en un mismo lote fue superior a aceptar todo uno por uno.
                    2. Cómo reaccionaste a la volatilidad (lluvia/bloqueos) si los hubo.
                    3. El impacto de tu algoritmo en la eficiencia de combustible y el desgaste del vehículo.

                    REGLAS ESTRICTAS DE FORMATO:
                    - NUNCA uses el símbolo de dólar para el dinero. Escribe la moneda como "MXN" al final de la cifra.
                    - NO uses fórmulas matemáticas ni LaTeX, escribe en texto plano o Markdown básico.

                    Tono profesional, persuasivo y directo a los jueces en primera persona.
                    """

                    start_time = time_lib.time()
                    respuesta = modelo.generate_content(prompt)
                    tiempo_segundos = time_lib.time() - start_time

                    tokens = respuesta.usage_metadata.total_token_count if hasattr(respuesta, "usage_metadata") else 450
                    costo_mxn = (tokens / 1_000_000) * 3.0

                    nombre_log = f"reporte_turno_seed_{semilla_juez}.txt"
                    with open(nombre_log, "w", encoding="utf-8") as f:
                        f.write(f"--- REPORTE SEED {semilla_juez} ---\n")
                        f.write(respuesta.text)

                    st.success("Reporte generado exitosamente con Gemini ⚡")
                    st.caption(f"⏱️ Tiempo: {tiempo_segundos:.2f}s | 🪙 Tokens: {tokens} | 💸 Costo: ${costo_mxn:.6f} MXN")
                    st.info(f"💾 Respaldado offline en: `{nombre_log}`")
                    st.write(respuesta.text)
                except Exception as e:
                    st.error(f"Error de conexión con la API: {e}")
    else:
        st.caption(
            "El dashboard comparativo (pestaña 📊 Comparativa) no depende de este reporte -- "
            "es solo un análisis narrativo extra para los jueces."
        )
