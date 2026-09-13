graph TD
    %% Configuración Inicial
    A[Inicio: app.py] --> B(Fijar Semilla / Determinismo)
    B --> C[(Cargar Grafo OSMnx en Caché)]
    
    %% Bucle de Simulación
    C --> D{¿Juez pide nueva orden?}
    D -- Sí --> E[simulador_pedidos.py]
    E -->|Genera Origen, Destino, Pago, Surge| F[rutamonterrey.py]
    
    %% Motor de Decisión
    F -->|Calcula Ruta y Tiempos| G[Motor Lógico EPUT]
    G --> H{¿EPUT >= Umbral?}
    
    %% Bifurcación de Agentes
    H -- Sí --> I[Agente Acepta: Suma MXN, Km, actualiza Mapa]
    H -- No --> J[Agente Rechaza: Evita pérdida]
    G -->|Novato acepta siempre| K[Novato: Suma MXN, Km, actualiza Mapa]
    
    %% Interfaz y Logs
    I --> L[Actualizar Mini-Dashboard en Streamlit]
    J --> L
    K --> L
    L --> M(Guardar evento en DataFrame Pandas)
    M --> D
    
    %% Fase de Cierre y Auditoría
    D -- Fin del Turno --> N{Botón: Generar Reporte}
    N --> O[API Gemini 3.6-flash analiza telemetría]
    O --> P[Métricas: Tokens, Costo MXN y Tiempo]
    P --> Q[Guardar reporte_seed.txt Offline]
    P --> R[Exportar event_log.jsonl validado]
