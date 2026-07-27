import os
from typing import Dict, List, Optional
from urllib.parse import quote_plus
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import Dict, List, Optional
from pydantic import BaseModel
import asyncio
import json
from bson import json_util # Helps serialize MongoDB ObjectIds to JSON
from sse_starlette.sse import EventSourceResponse

# Load variables from .env file locally
load_dotenv()

app = FastAPI(title="Amplify Shop API Suite")

# Read MongoDB configuration from environment variables
USERNAME = os.getenv("MONGO_USERNAME", "")
PASSWORD = os.getenv("MONGO_PASSWORD", "")
CLUSTER = os.getenv("MONGO_CLUSTER", "")
DB_NAME = os.getenv("DB_NAME", "ecommerce_db")

MONGO_URI = f"mongodb+srv://{quote_plus(USERNAME)}:{quote_plus(PASSWORD)}@{CLUSTER}/{DB_NAME}?retryWrites=true&w=majority"

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
products_col = db["products"]

# --- PYDANTIC SCHEMAS ---
class ProductSchema(BaseModel):
    id: int
    name: str
    price: float
    discountPrice: Optional[float] = None
    stock: int
    category: str
    rating: float
    reviewCount: int
    isFeatured: bool
    isNewArrival: bool
    imageUrl: str
    galleryImages: List[str]
    desc: str
    tags: List[str]
    specifications: Dict[str, str]

# Schema for updating a product (all fields optional for partial updates)
class ProductUpdateSchema(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    discountPrice: Optional[float] = None
    stock: Optional[int] = None
    category: Optional[str] = None
    rating: Optional[float] = None
    reviewCount: Optional[int] = None
    isFeatured: Optional[bool] = None
    isNewArrival: Optional[bool] = None
    imageUrl: Optional[str] = None
    galleryImages: Optional[List[str]] = None
    desc: Optional[str] = None
    tags: Optional[List[str]] = None
    specifications: Optional[Dict[str, str]] = None

# Schema for bulk deletion request
class BulkDeleteSchema(BaseModel):
    product_ids: List[int]

    # --- API ENDPOINTS ---

# ==========================================
# 1. Root
# ==========================================

@app.get("/")
async def root():
    return {"status": "online", "message": "E-Commerce API is running!"}

# ==========================================
# 2. FETCH PRODUCTS 
# ==========================================

@app.get("/api/products", response_model=List[ProductSchema])
async def get_products(
    category: Optional[str] = None, featured: Optional[bool] = None
):
    query = {}
    if category:
        query["category"] = category
    if featured is not None:
        query["isFeatured"] = featured

    cursor = products_col.find(query, {"_id": 0})
    return await cursor.to_list(length=100)

# ==========================================
# 3. FETCH PRODUCT BY ID 
# ==========================================

@app.get("/api/products/{product_id}", response_model=ProductSchema)
async def get_product_by_id(product_id: int):
    product = await products_col.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

# ==========================================
# 4. UPDATE PRODUCT BY ID 
# ==========================================
@app.patch("/api/products/{product_id}", response_model=Dict[str, str])
async def update_product(product_id: int, update_data: ProductUpdateSchema):
    # Filter out fields that were not provided in the request
    fields_to_update = {
        k: v for k, v in update_data.model_dump().items() if v is not None
    }

    if not fields_to_update:
        raise HTTPException(
            status_code=400, detail="No fields provided to update"
        )

    result = await products_col.update_one(
        {"id": product_id}, {"$set": fields_to_update}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")

    return {"message": f"Product {product_id} updated successfully"}


# ==========================================
# 5. DELETE PRODUCT BY ID 
# ==========================================
@app.delete("/api/products/{product_id}", response_model=Dict[str, str])
async def delete_product(product_id: int):
    result = await products_col.delete_one({"id": product_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")

    return {"message": f"Product {product_id} deleted successfully"}


# ==========================================
# 3. BULK ADD PRODUCTS
# ==========================================
@app.post("/api/products/bulk", response_model=Dict[str, str])
async def create_products_bulk(products: List[ProductSchema]):
    if not products:
        raise HTTPException(status_code=400, detail="Product list is empty")

    product_dicts = [p.model_dump() for p in products]
    incoming_ids = [p["id"] for p in product_dicts]

    # Check for duplicate IDs in database
    existing = await products_col.find(
        {"id": {"$in": incoming_ids}}, {"id": 1}
    ).to_list(length=len(incoming_ids))
    if existing:
        existing_ids = [doc["id"] for doc in existing]
        raise HTTPException(
            status_code=400,
            detail=f"Products with these IDs already exist: {existing_ids}",
        )

    # Insert all products in a single database operation
    result = await products_col.insert_many(product_dicts)
    return {
        "message": f"Successfully inserted {len(result.inserted_ids)} products"
    }


# ==========================================
# 6. BULK DELETE PRODUCTS
# ==========================================
@app.delete("/api/products/bulk", response_model=Dict[str, str])
async def delete_products_bulk(payload: BulkDeleteSchema):
    if not payload.product_ids:
        raise HTTPException(
            status_code=400, detail="Product ID list is empty"
        )

    # Delete all documents matching the provided ID array
    result = await products_col.delete_many(
        {"id": {"$in": payload.product_ids}}
    )

    return {
        "message": f"Successfully deleted {result.deleted_count} products"
    }

# ==========================================
# 7. REAL-TIME PRODUCTS STREAM (SSE)
# ==========================================
@app.get("/api/product/stream")
async def stream_products():
    """
    Establishes an SSE connection. Listens to MongoDB Change Streams
    and pushes updates to the client in real-time.
    """
    async def event_generator():
        # Pipeline to watch for specific operations (insert, update, delete)
        pipeline = [{"$match": {"operationType": {"$in": ["insert", "update", "delete"]}}}]
        
        try:
            # full_document="updateLookup" fetches the whole document even on updates
            async with products_col.watch(pipeline, full_document="updateLookup") as stream:
                print("SSE Client connected to MongoDB Change Stream.")
                
                # We use a while loop with a timeout to allow the server to send periodic "ping" 
                # events. This prevents Render/Load Balancers from killing idle connections.
                while True:
                    # Wait for a database change, or timeout after 15 seconds to send a keep-alive ping
                    change = await stream.try_next()
                    
                    if change is not None:
                        # A real database change happened!
                        operation = change["operationType"]
                        
                        # Use bson.json_util.dumps to safely convert MongoDB ObjectIds to JSON strings
                        doc = json.loads(json_util.dumps(change.get("fullDocument", {})))
                        
                        # Prepare payload based on operation
                        payload = {
                            "operation": operation,
                            "product_id": doc.get("id") if operation != "delete" else change["documentKey"].get("id"),
                            "data": doc if operation != "delete" else None
                        }
                        
                        # Yield the event to the client
                        yield {
                            "event": "product_update",
                            "data": json.dumps(payload)
                        }
                    else:
                        # No changes happened in this tick. Send a ping to keep connection alive.
                        yield {
                            "event": "ping",
                            "data": "keep-alive"
                        }
                        await asyncio.sleep(15)
                        
        except asyncio.CancelledError:
            print("SSE Client disconnected.")
            
    return EventSourceResponse(event_generator())

# Run handler for local execution and cloud dynamic porting
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)