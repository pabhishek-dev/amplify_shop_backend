from fastapi import APIRouter, HTTPException
from typing import Dict, List, Optional
import asyncio
import json
from bson import json_util
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from database import products_col
from schemas import ProductSchema, ProductUpdateSchema, BulkDeleteSchema

router = APIRouter(prefix="/api", tags=["Products"])

@router.get("/products", response_model=List[ProductSchema])
async def get_products(category: Optional[str] = None, featured: Optional[bool] = None):
    query = {}
    if category:
        query["category"] = category
    if featured is not None:
        query["isFeatured"] = featured

    cursor = products_col.find(query, {"_id": 0})
    return await cursor.to_list(length=100)

@router.get("/products/{product_id}", response_model=ProductSchema)
async def get_product_by_id(product_id: int):
    product = await products_col.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.patch("/products/{product_id}", response_model=Dict[str, str])
async def update_product(product_id: int, update_data: ProductUpdateSchema):
    fields_to_update = {k: v for k, v in update_data.model_dump().items() if v is not None}
    if not fields_to_update:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    result = await products_col.update_one({"id": product_id}, {"$set": fields_to_update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")

    return {"message": f"Product {product_id} updated successfully"}

@router.delete("/api/products/{product_id}", response_model=Dict[str, str], include_in_schema=False)
@router.delete("/products/{product_id}", response_model=Dict[str, str])
async def delete_product(product_id: int):
    result = await products_col.delete_one({"id": product_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": f"Product {product_id} deleted successfully"}

@router.post("/products/bulk", response_model=Dict[str, str])
async def create_products_bulk(products: List[ProductSchema]):
    if not products:
        raise HTTPException(status_code=400, detail="Product list is empty")

    product_dicts = [p.model_dump() for p in products]
    incoming_ids = [p["id"] for p in product_dicts]

    existing = await products_col.find({"id": {"$in": incoming_ids}}, {"id": 1}).to_list(length=len(incoming_ids))
    if existing:
        existing_ids = [doc["id"] for doc in existing]
        raise HTTPException(status_code=400, detail=f"Products with these IDs already exist: {existing_ids}")

    result = await products_col.insert_many(product_dicts)
    return {"message": f"Successfully inserted {len(result.inserted_ids)} products"}

@router.delete("/products/bulk", response_model=Dict[str, str])
async def delete_products_bulk(payload: BulkDeleteSchema):
    if not payload.product_ids:
        raise HTTPException(status_code=400, detail="Product ID list is empty")

    result = await products_col.delete_many({"id": {"$in": payload.product_ids}})
    return {"message": f"Successfully deleted {result.deleted_count} products"}

@router.get("/product/stream")
async def stream_products():
    async def event_generator():
        try:
            cursor = products_col.find({}, {"_id": 0})
            initial_products = await cursor.to_list(length=1000)
            initial_payload = {
                "action": "initial",
                "products": json.loads(json_util.dumps(initial_products)),
            }
            yield {"event": "product_update", "data": json.dumps(initial_payload)}

            pipeline = [{"$match": {"operationType": {"$in": ["insert", "update", "delete"]}}}]
            async with products_col.watch(pipeline, full_document="updateLookup") as stream:
                async for change in stream:
                    operation = change["operationType"]
                    doc = json.loads(json_util.dumps(change.get("fullDocument", {})))
                    update_payload = {
                        "action": operation,
                        "product": doc if operation != "delete" else None,
                        "productId": doc.get("id") if operation != "delete" else change["documentKey"].get("id"),
                    }
                    yield {"event": "product_update", "data": json.dumps(update_payload)}
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(
        event_generator(),
        ping=15,
        ping_message_factory=lambda: ServerSentEvent(**{"comment": "keep-alive"}),
    )