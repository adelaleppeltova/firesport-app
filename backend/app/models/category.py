from pydantic import BaseModel
from bson import ObjectId

class Category(BaseModel):
    _id: ObjectId
    category_name: str