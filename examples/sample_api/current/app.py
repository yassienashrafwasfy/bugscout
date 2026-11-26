"""sample_api: tiny FastAPI app with planted bugs."""
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="sample_api", version="1.0")

ITEMS = {1: {"id": 1, "name": "pen", "price": 1.5}, 2: {"id": 2, "name": "book", "price": 12.0}}


class Item(BaseModel):
    id: int
    name: str
    price: float


class Order(BaseModel):
    id: int
    total: float
    status: str


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/items/{item_id}", response_model=Item, responses={404: {"description": "not found"}})
def get_item(item_id: int):
    if item_id < 0:
        raise RuntimeError("negative id")  # PLANTED: unhandled -> HTTP 500
    if item_id not in ITEMS:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="not found")
    return ITEMS[item_id]


@app.get("/orders/{order_id}", responses={200: {"model": Order}})
def get_order(order_id: int):
    # PLANTED schema mismatch: the documented 200 response requires `total`, which is missing
    return {"id": order_id, "status": "paid"}


@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    """PLANTED destructive endpoint: must escalate."""
    ITEMS.pop(item_id, None)
    return {"deleted": item_id}
