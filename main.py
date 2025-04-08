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
    # Упрощенный и оптимизированный запрос
    query = f"""
    [out:json][timeout:25];
    area[name="{city}"][admin_level~"8|6"]->.a;
    (
        nwr["tourism"="hotel"]["name"](area.a);
        nwr["building"="hotel"]["name"](area.a);
    );
    out body center qt;
    """
    
    try:
        timeout = httpx.Timeout(30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(overpass_url, 
                                       data={"data": query},
                                       headers={'User-Agent': 'Hotels Search/1.0'})
            
            if response.status_code == 429:
                return []  # При превышении лимита возвращаем пустой список
                
            if not response.is_success:
                return []
                
            data = response.json()
            hotels = []
            
            for element in data.get("elements", [])[:20]:  # Ограничиваем количество результатов
                tags = element.get("tags", {})
                if "name" in tags:
                    hotels.append({
                        "name": tags.get("name", ""),
                        "address": tags.get("addr:street", "") or city,
                        "stars": tags.get("stars", "Нет данных"),
                        "phone": tags.get("phone", "Нет данных"),
                        "website": tags.get("website", ""),
                        "booking_url": tags.get("booking:url", "")
                    })
            
            return hotels[:10]  # Возвращаем только первые 10 отелей
                
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