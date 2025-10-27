from fastapi import FastAPI
from pymongo import MongoClient
from pydantic import BaseModel
from bson import ObjectId
from typing import Optional
from app.routers import athlete_router
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth_router
import os



app = FastAPI()


app.include_router(athlete_router.router)
app.include_router(auth_router.router) 

@app.get("/")
def root():
    return {"message": "Welcome to the FireSport API!"}


FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
