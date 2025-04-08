from http.client import HTTPResponse
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

app = FastAPI()

@app.get("/api/search")
async def search(country: str = None, city: str = None):
    if not country or not city:
        return JSONResponse(
            status_code=400,
            content={"message": "Необходимо указать страну и город"}
        )

    try:
        # Простой запрос для тестирования
        query = f"""
        [out:json][timeout:25];
        area[name="{city}"]->.searchArea;
        (
          node["tourism"="hotel"](area.searchArea);
          way["tourism"="hotel"](area.searchArea);
        );
        out body;
        """
        
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": query},
                headers={
                    'User-Agent': 'Hotel Search Bot/1.0',
                    'Accept': 'application/json'
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                hotels = []
                
                for element in data.get("elements", [])[:5]:  # Ограничиваем до 5 отелей для теста
                    tags = element.get("tags", {})
                    if "name" in tags:
                        hotels.append({
                            "name": tags.get("name", ""),
                            "address": tags.get("addr:street", ""),
                            "website": tags.get("website", ""),
                            "stars": "Нет данных",
                        })
                
                return {
                    "city": city,
                    "country": country,
                    "hotels": hotels
                }
            
            return JSONResponse(
                status_code=404,
                content={"message": "Отели не найдены"}
            )

    except Exception as e:
        print(f"Error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": "Ошибка сервера"}
        )
