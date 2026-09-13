# 🚗 DynaRoute: Data-Driven Courier Routing
**Built by team Tilines Insanos for HackMTY**

DynaRoute is a high-performance, deterministic simulation engine that replaces a courier's intuition with hard mathematical logic. It calculates the true profitability of every trip in milliseconds, optimizing earnings and reducing fuel waste.

## ⚠️ The Problem
Couriers often work 8-hour shifts and lose money without realizing it. They accept orders based on gut feeling, taking long, poorly-paid trips instead of waiting for profitable ones. This isn't just a logistics problem; it's a data analytics failure.

## 🚀 The Solution: Dynamic EPUT Engine
We built an **Earnings Per Unit of Time (EPUT)** engine that calculates real-world street distances and travel times. 
* **The Rookie Agent:** Accepts every ping, burning gas on unprofitable trips.
* **The Smart Agent (DynaRoute):** Evaluates the MXN/minute yield. 
* **🔥 Innovation (Market Adaptability):** When a surge event (like rain) hits, DynaRoute dynamically raises its acceptance threshold by 50%. It knows the market is hot, so it rejects mediocre orders to keep itself available for high-paying surge trips.

## 🗺️ System Architecture

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
