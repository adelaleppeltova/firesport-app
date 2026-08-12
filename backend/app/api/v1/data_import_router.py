"""
Router pro import dat - API endpoint pro nahrávání souborů.
"""
import logging
from fastapi import APIRouter, File, UploadFile, HTTPException
import json
from app.models.admin import DataImportResponse
from app.services.data_import import DataImporter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data", tags=["data"])


@router.post("/import", response_model=DataImportResponse)
async def import_json_endpoint(file: UploadFile = File(...)):
    """
    Importuje JSON soubor do databáze.
    
    Očekávaný formát:
    ```json
    {
        "competition": {
            "name": "Český pohár",
            "place": "Budíkovice",
            "date": "2025-05-04",
            "type": "běh na 100m s překážkami",
            "league": "Český pohár",
            "categories": [
                {
                    "name": "Ženy",
                    "results": [...]
                }
            ]
        }
    }
    ```
    
    Returns:
        - athletes_created: počet nových atlet
        - athletes_skipped: počet existujících atlet
        - competitions_created: počet nových soutěží
        - categories_created: počet nových kategorií
        - results_created: počet importovaných výsledků
        - errors: seznam chyb (pokud nějaké byly)
    """
    try:
        # Kontrola typu souboru
        if not file.filename.endswith('.json'):
            raise HTTPException(
                status_code=400,
                detail="Soubor musí být JSON (*.json)"
            )
        
        # Čtení obsahu souboru
        content = await file.read()
        data = json.loads(content.decode('utf-8'))
        
        # Import dat
        importer = DataImporter()
        stats = await importer.import_from_dict(data)
        
        return {
            "success": True,
            "message": "Import dokončen",
            "data": stats
        }
        
    except json.JSONDecodeError:
        logger.error("JSON parse error")
        raise HTTPException(
            status_code=400,
            detail="Neplatný JSON formát"
        )
    except Exception as e:
        logger.error(f"Import error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chyba při importu: {str(e)}"
        )


@router.post("/import/raw", response_model=DataImportResponse)
async def import_raw_json(data: dict):
    """
    Importuje data přímo z JSON těla requestu.
    
    Užitečné pro testování nebo programatický import.
    """
    try:
        importer = DataImporter()
        stats = await importer.import_from_dict(data)
        
        return {
            "success": True,
            "message": "Import dokončen",
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Import error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chyba při importu: {str(e)}"
        )
