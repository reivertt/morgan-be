from ninja import Router, Schema
from typing import List
from api.models import Item

router = Router()

# Example router

class ItemIn(Schema):
    name: str
    price: float

class ItemOut(ItemIn):
    id: int

@router.post("/", response=ItemOut)
def create_item(request, data: ItemIn):
    obj = Item.objects.create(**data.dict())
    return ItemOut(id=obj.id, name=obj.name, price=obj.price)

@router.get("/", response=List[ItemOut])
def list_items(request):
    return [ItemOut(id=i.id, name=i.name, price=i.price) for i in Item.objects.all()]