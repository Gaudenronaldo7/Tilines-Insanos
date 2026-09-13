```mermaid
graph TD
    %% Initial Configuration
    A[Start: app.py] --> B(Set Seed / Determinism)
    B --> C[(Load OSMnx Graph to Cache)]
    
    %% Simulation Loop
    C --> D{User requests new order?}
    D -- Yes --> E[simulador_pedidos.py]
    E -->|Generates Origin, Dest, Payout, Surge| F[rutamonterrey.py]
    
    %% NEW: Dynamic Decision Engine
    F -->|Calculates Route & Times| G[EPUT Decision Engine]
    G --> G2{Market Surge Active?}
    G2 -- Yes --> G3[Smart Agent: Threshold x 1.5]
    G2 -- No --> G4[Smart Agent: Normal Threshold]
    
    %% Agent Bifurcation
    G3 --> H{Yield >= Dynamic Threshold?}
    G4 --> H
    H -- Yes --> I[Smart Agent Accepts]
    H -- No --> J[Smart Agent Rejects: Avoids Loss]
    G -->|Rookie always accepts| K[Rookie Accepts]
    
    %% UI and Auditing
    I --> L[Update Streamlit Dashboard]
    J --> L
    K --> L
    L --> M[Save Event to Pandas]
    M --> N{Shift Ends: Export JSONL & Gemini Report}




