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
    # Модифицированный запрос для поиска по нескольким вариантам названий
    query = f"""
    [out:json][timeout:25];
    area["name"~"^{city}$|^{city.title()}$|^{city.upper()}$",i]["place"~"city|town|village"]->.searchArea;
    (
        way["tourism"="hotel"](area.searchArea);
        node["tourism"="hotel"](area.searchArea);
        way["building"="hotel"](area.searchArea);
        node["building"="hotel"](area.searchArea);
    );
    out body center qt;
    """
    
    try:
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(overpass_url, 
                                       data={"data": query},
                                       headers={
                                           'User-Agent': 'Hotels Search/1.0',
                                           'Accept-Language': 'en,pt'
                                       })
            
            if not response.is_success:
                # Пробуем альтернативный запрос для интернациональных названий
                alt_query = f"""
                [out:json][timeout:25];
                area["name:en"~"{city}",i]["place"~"city|town"]->.searchArea;
                (
                    nwr["tourism"="hotel"](area.searchArea);
                    nwr["building"="hotel"](area.searchArea);
                );
                out body center qt;
                """
                response = await client.post(overpass_url, 
                                           data={"data": alt_query},
                                           headers={
                                               'User-Agent': 'Hotels Search/1.0',
                                               'Accept-Language': 'en,pt'
                                           })
            
            if response.is_success:
                data = response.json()
                hotels = []
                
                for element in data.get("elements", [])[:20]:
                    tags = element.get("tags", {})
                    if "name" in tags:
                        name = tags.get("name")
                        # Проверяем различные варианты адреса
                        address = (tags.get("addr:street", "") + " " + tags.get("addr:housenumber", "")).strip()
                        if not address:
                            address = tags.get("addr:full", "") or tags.get("address", "") or city
                        
                        hotel = {
                            "name": name,
                            "address": address,
                            "stars": tags.get("stars", "Нет данных"),
                            "phone": tags.get("phone", tags.get("contact:phone", "Нет данных")),
                            "website": (
                                tags.get("website", "") or 
                                tags.get("contact:website", "") or 
                                tags.get("url", "")
                            ),
                            "booking_url": (
                                tags.get("booking:url", "") or 
                                tags.get("contact:booking", "") or 
                                tags.get("url:booking", "")
                            )
                        }
                        if any([hotel["website"], hotel["address"]]):  # Добавляем только если есть хотя бы сайт или адрес
                            hotels.append(hotel)
                
                return hotels[:10]
            
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
        
        hotels = await fetch_hotels_from_osm(country, city)
        
        return {
            "city": city.title(),
            "country": country.title(),
            "hotels": hotels
        }

    except Exception as e:
        print(f"Error in search: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": f"Ошибка сервера при поиске отелей: {str(e)}"}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)  # Убираем host и port для совместимости с Vercel