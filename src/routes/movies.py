from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from database.models import (
    MovieModel,
    CountryModel,
    GenreModel,
    ActorModel,
    LanguageModel,
)
from schemas.movies import (
    MovieCreateSchema,
    MovieDetailsSchema,
    MoviesListResponseSchema,
    MovieListItemSchema,
    MovieUpdateSchema,
)

router = APIRouter(prefix="/movies", tags=["Movies"])


@router.get("/", response_model=MoviesListResponseSchema)
async def get_movies_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    total_items = await db.scalar(select(func.count(MovieModel.id)))
    total_pages = (total_items + per_page - 1) // per_page

    if total_items == 0 or page > total_pages:
        raise HTTPException(status_code=404, detail="No movies found.")

    offset = (page - 1) * per_page

    movies = (
        await db.scalars(
            select(MovieModel)
            .order_by(MovieModel.id.desc())
            .offset(offset)
            .limit(per_page)
        )
    ).all()

    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")

    base_path = "/api/v1/movies/"

    return MoviesListResponseSchema(
        movies=[MovieListItemSchema.model_validate(m) for m in movies],
        prev_page=(
            f"{base_path}?page={page - 1}&per_page={per_page}"
            if page > 1
            else None
        ),
        next_page=(
            f"{base_path}?page={page + 1}&per_page={per_page}"
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )


async def get_or_create_entities(
    db: AsyncSession,
    model,
    names: list[str],
):
    if not names:
        return []

    existing = (
        await db.scalars(select(model).where(model.name.in_(names)))
    ).all()

    existing_names = {e.name for e in existing}
    new_entities = [model(name=name) for name in names if name not in existing_names]

    if new_entities:
        db.add_all(new_entities)
        await db.flush()

    return existing + new_entities


@router.post("/", response_model=MovieDetailsSchema, status_code=201)
async def create_movie(
    movie: MovieCreateSchema,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(
        select(MovieModel).where(
            MovieModel.name == movie.name,
            MovieModel.date == movie.date,
        )
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A movie with the name '{movie.name}' "
                f"and release date '{movie.date}' already exists."
            ),
        )

    country = None
    if movie.country:
        country = await db.scalar(
            select(CountryModel).where(CountryModel.code == movie.country)
        )
        if not country:
            country = CountryModel(code=movie.country)
            db.add(country)
            await db.flush()

    genres = await get_or_create_entities(db, GenreModel, movie.genres)
    actors = await get_or_create_entities(db, ActorModel, movie.actors)
    languages = await get_or_create_entities(db, LanguageModel, movie.languages)

    data = movie.model_dump(
        exclude={"country", "genres", "actors", "languages"}
    )

    db_movie = MovieModel(
        **data,
        country=country,
        genres=genres,
        actors=actors,
        languages=languages,
    )

    db.add(db_movie)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    await db.refresh(db_movie)
    return db_movie


@router.get("/{movie_id}/", response_model=MovieDetailsSchema)
async def get_movie_details(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    movie = await db.scalar(
        select(MovieModel)
        .where(MovieModel.id == movie_id)
        .options(
            selectinload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
        )
    )

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found.",
        )

    return movie


@router.delete("/{movie_id}/", status_code=204)
async def delete_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found.",
        )

    await db.delete(movie)
    await db.commit()


@router.patch("/{movie_id}/")
async def update_movie(
    movie_id: int,
    movie_update: MovieUpdateSchema,
    db: AsyncSession = Depends(get_db),
):
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found.",
        )

    for field, value in movie_update.model_dump(exclude_unset=True).items():
        setattr(movie, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return {"detail": "Movie updated successfully."}
