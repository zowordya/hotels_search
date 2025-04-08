from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/search")
async def search(country: str = None, city: str = None):
    if not country or not city:
        return JSONResponse(
            status_code=400,
            content={"message": "Необходимо указать страну и город"}
        )

    try:
        query = f"""
        [out:json][timeout:25];
        area[name="{city}"]->.a;
        (
            nwr["tourism"="hotel"]["name"](area.a);
        );
        out body center;
        """
        
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": query},
                headers={'User-Agent': 'HotelSearch/1.0'}
            )
            
            if response.status_code == 200:
                data = response.json()
                hotels = []
                
                for element in data.get("elements", [])[:10]:
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

# Для Vercel
handler = app
