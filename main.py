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
    # Оптимизированный запрос
    query = f"""
    [out:json][timeout:90];
    area["name"~"{city}",i]["place"~"city|town"]->.searchArea;
    (
        way["tourism"="hotel"](area.searchArea);
        node["tourism"="hotel"](area.searchArea);
        way["building"="hotel"](area.searchArea);
        node["building"="hotel"](area.searchArea);
    );
    out body center qt;
    """
    
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            try:
                response = await client.post(overpass_url, data={"data": query})
                
                if response.status_code == 429:
                    print("Rate limit hit, waiting...")
                    await asyncio.sleep(5)
                    response = await client.post(overpass_url, data={"data": query})
                
                response.raise_for_status()
                data = response.json()
                
                if not data.get("elements"):
                    # Пробуем альтернативный запрос без area
                    alt_query = f"""
                    [out:json][timeout:90];
                    (
                        way["tourism"="hotel"]["name"~".",i](area:{city});
                        node["tourism"="hotel"]["name"~".",i](area:{city});
                    );
                    out body center qt;
                    """
                    response = await client.post(overpass_url, data={"data": alt_query})
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
                            "phone": tags.get("phone", tags.get("contact:phone", "Нет данных")),
                            "website": tags.get("website", tags.get("contact:website", "")),
                            "booking_url": tags.get("booking:url", tags.get("contact:booking", ""))
                        }
                        if not hotel["address"].strip():
                            hotel["address"] = tags.get("addr:full", city)
                        hotels.append(hotel)
                
                return hotels
                
            except httpx.TimeoutException:
                print("Timeout error")
                return []
            except httpx.RequestError as e:
                print(f"Request error: {e}")
                return []
                
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
        country = country.strip().lower()
        city = city.strip().lower()
        
        print(f"Searching for hotels in {city}, {country}")
        
        hotels = await fetch_hotels_from_osm(country, city)
        
        if not hotels:
            # Пробуем поиск только по городу
            hotels = await fetch_hotels_from_osm("", city)
        
        if not hotels:
            return JSONResponse(
                status_code=404,
                content={
                    "message": f"Отели в городе {city.title()} не найдены",
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
    uvicorn.run(app)  # Убираем host и port для совместимости с Vercel