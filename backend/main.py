import logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')

# Vypnout DEBUG logy z knihoven
logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("motor").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logging.warning('TEST LOG: Backend successfully started and logger is working.')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1  import auth_router, athlete_router, result_router
from app.api.v1 import competition_router, me_router, data_import_router
from app.api.v1 import admin_router, athlete_anomalies_router, ml_router
from app.db.database import ensure_indexes

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://dayana-nondefensible-felinely.ngrok-free.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/v1")
app.include_router(athlete_router.router, prefix="/v1")
app.include_router(competition_router.router, prefix="/v1")
app.include_router(result_router.router, prefix="/v1")
app.include_router(me_router.router, prefix="/v1")
app.include_router(data_import_router.router, prefix="/v1")
app.include_router(admin_router.router, prefix="/v1")
app.include_router(ml_router.router, prefix="/v1")
app.include_router(athlete_anomalies_router.router, prefix="/v1")


@app.on_event("startup")
async def startup_event():
    await ensure_indexes()

@app.get("/")
def read_root():
    return {"message": "Firesport API"}
