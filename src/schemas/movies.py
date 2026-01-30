from datetime import date
from pydantic import BaseModel, Field
from typing import List, Optional


# ---------- LIST ITEM ----------

class MovieListItemSchema(BaseModel):
    id: int
    name: str
    date: date
    score: Optional[int]

    model_config = {"from_attributes": True}


# ---------- DETAILS ----------

class MovieDetailsSchema(BaseModel):
    id: int
    name: str
    description: Optional[str]
    date: date
    score: Optional[int]
    budget: Optional[int]
    revenue: Optional[int]

    country: Optional[str]
    genres: List[str]
    actors: List[str]
    languages: List[str]

    model_config = {"from_attributes": True}


# ---------- CREATE ----------

class MovieCreateSchema(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    date: date
    score: Optional[int] = Field(None, ge=0, le=100)
    budget: Optional[int] = Field(None, ge=0)
    revenue: Optional[int] = Field(None, ge=0)

    country: Optional[str] = None
    genres: List[str] = []
    actors: List[str] = []
    languages: List[str] = []


# ---------- UPDATE ----------

class MovieUpdateSchema(BaseModel):
    name: Optional[str]
    description: Optional[str]
    date: Optional[date]
    score: Optional[int] = Field(None, ge=0, le=100)
    budget: Optional[int] = Field(None, ge=0)
    revenue: Optional[int] = Field(None, ge=0)

    country: Optional[str]
    genres: Optional[List[str]]
    actors: Optional[List[str]]
    languages: Optional[List[str]]


# ---------- LIST RESPONSE ----------

class MoviesListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int
