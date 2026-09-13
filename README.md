# DynaRoute: Data-Driven Courier Routing
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
flowchart TD
    A["App arranca"] --> B["Se carga el grafo vial de Monterrey<br/>(cacheado con st.cache_resource)"]
    B --> C{"Acción del usuario"}
    C -->|"Simular 1 pedido"| D["Generar 1 pedido"]
    C -->|"Simular 5 pedidos"| E["Generar pedidos uno por uno<br/>(try/except: si uno falla, sigue con el resto)"]
    C -->|"Despachar lote"| F["Despachar manualmente el lote<br/>pendiente del Agente"]

    D --> N
    E --> N

    subgraph N ["Por cada pedido nuevo"]
        direction LR

        subgraph NOV ["🚶 Novato"]
            N1["¿Existe ruta física<br/>hasta origen y destino?"] -->|"No"| N2["Rechazar:<br/>inaccesible"]
            N1 -->|"Sí"| N3["Despachar YA, solo<br/>(sin encadenar)"]
            N3 --> N4["+ganancia, +km, +tiempo"]
        end

        subgraph AGT ["🤖 Agente Inteligente"]
            A1{"¿Lote lleno?<br/>(3/3 pedidos)"} -->|"Sí"| A2["Auto-despachar<br/>el lote actual primero"]
            A1 -->|"No"| A3
            A2 --> A3["optimizar_ruta(lote actual)<br/>vs<br/>optimizar_ruta(lote + candidato)"]
            A3 --> A4["Δ Utilidad = ingreso extra − gasolina extra<br/>Tasa marginal = Δ Utilidad / Δ tiempo × 60"]
            A4 --> A5{"Δ Utilidad > 0 Y<br/>tasa ≥ tasa de reserva?"}
            A5 -->|"Sí"| A6["Sumar al lote pendiente<br/>(no se despacha todavía)"]
            A5 -->|"No"| A7["Rechazar + razón en texto"]
        end
    end

    N4 --> H
    A6 --> H
    A7 --> H
    F --> H

    H["Actualizar métricas:<br/>$/hora, $/km, batch rate,<br/>tamaño de lote promedio"] --> I
    I["Renderizar dashboard:<br/>mapas en vivo · panel de decisión ·<br/>panel de lote activo · comparativa · historial"]
