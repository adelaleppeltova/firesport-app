from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class CategoryBase(BaseModel):
    name: str
    discipline: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryInDB(CategoryBase):
    id: str = Field(..., alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
    )