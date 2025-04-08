from fastapi import FastAPI
from fastapi.responses import JSONResponse
import httpx
import asyncio

app = FastAPI()

@app.get("/api/search")
async def search(country: str = None, city: str = None):
    if not country or not city:
        return JSONResponse(
            status_code=400,
            content={"message": "Необходимо указать страну и город"}
        )

    try:
        # Упрощенный запрос для Vercel
        query = f"""
        [out:json][timeout:15];
        area[name="{city}"]->.a;
        (
            node["tourism"="hotel"]["name"](area.a);
            way["tourism"="hotel"]["name"](area.a);
        );
        out body center;
        """
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            response = await client.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": query},
                headers={
                    'User-Agent': 'HotelSearch/1.0',
                    'Accept': 'application/json'
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                hotels = []
                
                for element in data.get("elements", [])[:5]:
                    tags = element.get("tags", {})
                    if "name" in tags:
                        hotels.append({
                            "name": tags.get("name", ""),
                            "address": tags.get("addr:street", "") or city,
                            "website": tags.get("website", ""),
                            "stars": tags.get("stars", "Нет данных")
                        })
                
                return {"hotels": hotels}
            
            return JSONResponse(
                status_code=404,
                content={"message": "Отели не найдены"}
            )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": str(e)}
        )

handler = app
