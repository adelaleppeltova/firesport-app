from pydantic import BaseModel, Field
from bson import ObjectId

class CategoryBase(BaseModel):
    category_name: str


class CategoryCreate(CategoryBase):
    pass

class CategoryInDB(CategoryBase):
    id: str = Field(..., alias="_id")

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        arbitrary_types_allowed = True


