# Firesport App

Webová aplikace pro správu, prohlížení a analýzu výsledků v požárním sportu. Projekt kombinuje FastAPI backend, React frontend a MongoDB databázi.

## Co aplikace aktuálně umí

- evidenci soutěží, kategorií, závodníků a výsledků,
- vyhledávání a filtrování závodníků a soutěží,
- detail závodníka včetně přehledu výkonů, vývoje po sezónách a stability výkonu,
- detail soutěže a výsledků podle kategorií,
- registraci, přihlášení a propojení uživatele se závodníkem,
- administraci importu JSON dat a ruční kontrolu párování výsledků,
- základní analytiku nad výsledky včetně detekce anomálií.

## Architektura

### Backend

Backend je postavený na **FastAPI** a poskytuje REST API pro práci s uživateli, závodníky, soutěžemi, výsledky, importem dat a analytickými výstupy.

### Frontend

Frontend je vytvořený v **Reactu**. Používá **React Router**, **TanStack Query**, **Axios** a **Recharts** pro zobrazení dat a grafů.

### Databáze

Data jsou uložená v **MongoDB**. Při spuštění přes Docker Compose se databáze naplní JSON soubory ze složky [`data`](/Users/adelaleppeltova/firesport-app/data).

## Spuštění

Nejjednodušší způsob je přes Docker Compose:

```bash
docker compose up --build
```

Po spuštění bude dostupné:

- frontend: [http://localhost:3000](http://localhost:3000)
- backend API: [http://localhost:8000](http://localhost:8000)
- Swagger dokumentace: [http://localhost:8000/docs](http://localhost:8000/docs)

## Struktura projektu

- [`backend`](/Users/adelaleppeltova/firesport-app/backend) - FastAPI aplikace, API routery, služby a import dat
- [`frontend`](/Users/adelaleppeltova/firesport-app/frontend) - React aplikace a uživatelské rozhraní
- [`data`](/Users/adelaleppeltova/firesport-app/data) - zdrojová JSON data pro import
- [`docs/screenshots`](/Users/adelaleppeltova/firesport-app/docs/screenshots) - screenshoty aplikace

## Screenshoty

Sem doplnit aktuální screenshoty aplikace.
