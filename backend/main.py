import logging

logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(name)s %(message)s')

logging.warning('TEST LOG: Backend successfully started and logger is working.')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth_router, athlete_router, user_router
from app.routers import competition_router
from app.api import me

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(user_router.router)
app.include_router(athlete_router.router)
app.include_router(competition_router.router)
app.include_router(me.router)

@app.get("/")
def read_root():
    return {"message": "Firesport API"}
