from fastapi import FastAPI
from api.app.routes.epcis import compliance
from api.app.routes import trace
from app.routes.epcis import epcis
from app.routes.gdst import gdst
from api.app.routes.epcis import events
from app.core.auth import create_access_token
from datetime import timedelta

app = FastAPI(title="Starfish Hedera Traceability API", version="1.0.0", root_path="/api/v1",
              docs_url="/swagger", 
              redoc_url="/redoc")

app.include_router(gdst.router)
app.include_router(epcis.router)
app.include_router(trace.router)

@app.post("/login")
def login(username: str, role: str = "reader"):
    token = create_access_token({"sub": username, "role": role}, timedelta(minutes=60))
    return {"access_token": token, "token_type": "bearer"}

@app.get("/health")
def health():
    return {"status": "ok"}
