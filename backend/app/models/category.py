from typing import Literal, Optional
from app.category_catalog import Discipline
from pydantic import BaseModel, Field, ConfigDict


class CategoryBase(BaseModel):
    name: str
    discipline: Optional[Discipline] = None
    key: Optional[str] = None
    gender: Optional[Literal["male", "female"]] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    type: Optional[Literal["individual", "team"]] = None
    age_system: Optional[Literal["general", "age_group"]] = None


class CategoryInDB(CategoryBase):
    id: str = Field(..., alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
    )
