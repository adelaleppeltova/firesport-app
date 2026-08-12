# Architektura aplikace

Tento dokument popisuje současnou M0 baseline projektu firesport-app.

## Přehled

```text
React frontend
    ↓ HTTP / REST
nginx
    ↓ /v1/
FastAPI backend
    ↓
MongoDB
```

React aplikace používá REST API backendu pro autentizaci, práci se závodníky, soutěžemi, výsledky, importem a analytickými výstupy. Backend vedle aplikačních služeb obsahuje ML část pro detekci neobvyklých výkonů pomocí Isolation Forest.

## Backend

Backend je aplikace ve FastAPI. Hlavní adresáře v `backend/app` jsou:

- `api` – HTTP routery a endpointy API pod prefixem `/v1`,
- `models` – datové a validační modely používané API a službami,
- `services` – aplikační logika pro autentizaci, závodníky, soutěže, výsledky, import a analytické výstupy,
- `db` – připojení k MongoDB a databázová inicializace,
- `ml` – konfigurace a výpočet detekce anomálií pomocí Isolation Forest,
- `tests` – backendové testy spouštěné pomocí pytest.

## Frontend

Frontend je jednostránková React aplikace s routováním přes React Router. Hlavní části v `frontend/src` jsou:

- `pages` – jednotlivé obrazovky aplikace,
- `components` – sdílené i doménové UI komponenty,
- `layouts` – rozložení veřejné a přihlášené části aplikace,
- `api` – Axios klient a API helpery,
- `hooks` – vlastní React hooky pro načítání dat a stav,
- `context` – sdílený kontext, zejména autentizace,
- `assets` – styly a obrazové prostředky,
- `utils` – pomocné frontendové funkce.

## Runtime / Docker architecture

Docker image frontendu používá multi-stage build. V první stage s Node.js 20 se pomocí `npm ci` nainstalují závislosti a `npm run build` vytvoří produkční statické soubory. Runtime stage používá nginx a Node.js ani npm už neobsahuje.

Nginx servíruje React build na portu 80 kontejneru, který Docker Compose mapuje na `http://localhost:3000`. Pro React Router používá SPA fallback na `index.html`. Požadavky na `/v1/` proxyuje na službu `backend` na portu 8000, takže frontend používá relativní API URL.

FastAPI backend je dostupný také přímo na `http://localhost:8000`, poskytuje REST API a komunikuje s MongoDB přes interní Docker síť. Swagger dokumentace je dostupná na `http://localhost:8000/docs`.

## Testing and CI

- Backend má 102 testů spouštěných příkazem `python -m pytest app/tests` s Pythonem 3.12.
- Frontend má současný základní test spouštěný neinteraktivně příkazem `CI=true npm test -- --watchAll=false` s Node.js 20.
- Produkční frontend build se ověřuje příkazem `npm run build`.
- GitHub Actions při pushi a pull requestu paralelně spouští backendové testy a frontendový job obsahující instalaci, test a produkční build.
