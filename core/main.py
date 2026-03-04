"""
Cloud Simulator — FastAPI entry point.

Wires the SimulationEngine, REST routes, and WebSocket endpoint.
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as rest_router, lifespan
from api.websocket import router as ws_router

app = FastAPI(
    title="Cloud Infrastructure Simulator",
    description="Event-driven cloud simulation engine with attack and defense layers.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js dev
        "http://localhost:8501",   # Streamlit
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rest_router, prefix="/simulation", tags=["Simulation"])
app.include_router(ws_router, prefix="/simulation", tags=["WebSocket"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
