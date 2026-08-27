import os
from fastapi import FastAPI
from routers import products, auth

app = FastAPI(title="Amplify Shop API Suite")

# Include Routers
app.include_router(products.router)
app.include_router(auth.router)

@app.get("/")
async def root():
    return {"status": "online", "message": "Amplify Shop API is running!"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)