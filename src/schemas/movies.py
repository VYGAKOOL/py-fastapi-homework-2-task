import datetime
from datetime import date, timedelta
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from database.models import MovieStatusEnum


class CountrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: Optional[str]


class GenreSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ActorSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class LanguageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class MovieBaseSchema(BaseModel):
    name: str = Field(max_length=255)
    date: date
    score: float = Field(ge=0, le=100)
    overview: str | None = None
    status: MovieStatusEnum = Field(default="Released")
    budget: float = Field(default=0, ge=0)
    revenue: float = Field(default=0, ge=0)
    country: str | None = None
    genres: list[str] = Field(default_factory=list)
    actors: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)

    @field_validator("date")
    def validate_release_date(cls, release_date: date) -> date:
        if release_date > date.today() + timedelta(days=365):
            raise ValueError("Release date cannot be more than one year in the future")
        return release_date


class MovieCreateSchema(MovieBaseSchema):
    pass


class MovieResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    date: date
    score: float
    overview: str | None = None
    status: MovieStatusEnum
    budget: float
    revenue: float
    country: CountrySchema | None = None
    genres: list[GenreSchema] = Field(default_factory=list)
    actors: list[ActorSchema] = Field(default_factory=list)
    languages: list[LanguageSchema] = Field(default_factory=list)


class MovieListItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    date: date
    score: float
    overview: Optional[str]


class MoviesListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int


class MovieUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str | None = None
    date: datetime.date | None = None
    score: float | None = None
    overview: str | None = None
    status: MovieStatusEnum | None = None
    budget: float | None = None
    revenue: float | None = None
