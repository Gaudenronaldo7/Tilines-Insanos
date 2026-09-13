```mermaid
graph TD
    %% Initial Configuration
    A[Start: app.py] --> B(Set Seed / Determinism)
    B --> C[(Load OSMnx Graph to Cache)]
    
    %% Simulation Loop
    C --> D{User requests new order?}
    D -- Yes --> E[simulador_pedidos.py]
    E -->|Generates Origin, Dest, Payout, Surge| F[rutamonterrey.py]
    
    %% Decision Engine
    F -->|Calculates Route & Times| G[EPUT Decision Engine]
    G --> H{EPUT >= Threshold?}
    
    %% Agent Bifurcation
    H -- Yes --> I[Smart Agent Accepts: Adds MXN, Km, Updates Map]
    H -- No --> J[Smart Agent Rejects: Avoids Loss]
    G -->|Rookie always accepts| K[Rookie: Adds MXN, Km, Updates Map]
    
    %% UI and Logging
    I --> L[Update Streamlit Mini-Dashboard]
    J --> L
    K --> L
    L --> M(Save Event in Pandas DataFrame)
    M --> D
    
    %% Auditing and Closing Phase
    D -- End of Shift --> N{Button: Generate Report}
    N --> O[Gemini 3.6-flash API Analyzes Telemetry]
    O --> P[Metrics: Tokens, MXN Cost, Time]
    P --> Q[Save reporte_seed.txt Offline]
    P --> R[Export validated event_log.jsonl]
