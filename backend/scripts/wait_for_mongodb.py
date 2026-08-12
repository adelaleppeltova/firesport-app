#!/usr/bin/env python3
"""
Script pro čekání na MongoDB připojení.
"""
import sys
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

MONGO_URL = "mongodb://mongo:27017"
MAX_RETRIES = 30
RETRY_DELAY = 1


async def wait_for_mongo():
    """Čéká dokud není MongoDB připravena."""
    client = None
    for attempt in range(MAX_RETRIES):
        try:
            client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
            # Zkus ping
            await client.admin.command('ping')
            print("✓ MongoDB je připravena!")
            return True
        except Exception as e:
            attempt_num = attempt + 1
            print(f"⏳ Pokus {attempt_num}/{MAX_RETRIES}: Čekání na MongoDB... ({e})")
            await asyncio.sleep(RETRY_DELAY)
        finally:
            if client:
                client.close()
    
    print(f"✗ MongoDB se nepodařilo připojit po {MAX_RETRIES} pokusech")
    return False


if __name__ == "__main__":
    result = asyncio.run(wait_for_mongo())
    sys.exit(0 if result else 1)
