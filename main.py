from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import httpx
import asyncio
from typing import Optional

app = FastAPI()

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=".")
app.mount("/static", StaticFiles(directory="."), name="static")

@app.on_event("startup")
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hotels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            address TEXT NOT NULL,
            rating REAL CHECK(rating BETWEEN 0 AND 5)
        )
    ''')
    conn.commit()
    # Добавляем тестовые данные
    cursor.executemany('''
        INSERT INTO hotels (name, city, address, rating)
        VALUES (?, ?, ?, ?)
    ''', [
        ("Grand Hotel", "Paris", "123 Rue de Paris", 4.8),
        ("Sunset Resort", "Barcelona", "456 Avenida del Sol", 4.5),
        ("Mountain Lodge", "Zermatt", "789 Alpine Way", 4.2)
    ])
    conn.commit()
    conn.close()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

async def fetch_hotels_from_osm(country: str, city: str) -> list:
    overpass_url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:60];
    area["name"~"{city}",i]["admin_level"~"8|6|4"]->.searchArea;
    (
        nwr["tourism"="hotel"](area.searchArea);
        nwr["building"="hotel"](area.searchArea);
    );
    out body center qt;
    """
    
    try:
        await asyncio.sleep(1)  # Добавляем задержку между запросами
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(overpass_url, data={"data": query})
            
            if response.status_code == 429:
                await asyncio.sleep(5)  # Ждем подольше при ошибке 429
                response = await client.post(overpass_url, data={"data": query})
            
            response.raise_for_status()
            data = response.json()
            
            hotels = []
            for element in data.get("elements", []):
                tags = element.get("tags", {})
                if "name" in tags:
                    hotel = {
                        "name": tags.get("name", ""),
                        "address": tags.get("addr:street", "") + " " + tags.get("addr:housenumber", ""),
                        "stars": tags.get("stars", "Нет данных"),
                        "phone": tags.get("phone", "Нет данных"),
                        "website": tags.get("website", ""),
                        "booking_url": tags.get("booking:url", "")
                    }
                    # Очищаем пустые значения
                    if not hotel["address"].strip():
                        hotel["address"] = tags.get("addr:full", city)
                    if not hotel["website"].strip():
                        hotel["website"] = tags.get("contact:website", "")
                    hotels.append(hotel)
            
            return hotels
            
    except Exception as e:
        print(f"Error in fetch_hotels_from_osm: {str(e)}")
        return []

@app.get("/api/search")
async def search(country: str = None, city: str = None):
    if not country or not city:
        return JSONResponse(
            status_code=400,
            content={"message": "Необходимо указать страну и город"}
        )

    try:
        # Нормализуем названия
        country = country.strip().lower()
        city = city.strip().lower()
        
        # Добавляем альтернативные названия городов
        city_alternatives = {
            "porto": ["porto", "oporto"],
            # Добавьте другие альтернативы при необходимости
        }
        
        hotels = []
        for city_variant in city_alternatives.get(city, [city]):
            hotels = await fetch_hotels_from_osm(country, city_variant)
            if hotels:
                break
                
        if not hotels:
            return JSONResponse(
                status_code=404,
                content={
                    "message": f"Отели в городе {city.title()}, {country.title()} не найдены",
                    "hotels": []
                }
            )

        return {
            "city": city.title(),
            "country": country.title(),
            "hotels": hotels
        }

    except Exception as e:
        print(f"Error in search: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": "Ошибка сервера при поиске отелей"}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)