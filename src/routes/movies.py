from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db, MovieModel
from database.models import CountryModel, GenreModel, ActorModel, LanguageModel
from schemas.movies import (
    MovieCreateSchema,
    MovieResponseSchema,
    MoviesListResponseSchema,
    MovieListItemSchema,
    MovieUpdateSchema,
)


router = APIRouter()


@router.get("/movies/", response_model=MoviesListResponseSchema)
async def get_movies_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    total_items_result = await db.execute(select(func.count(MovieModel.id)))
    total_items = total_items_result.scalar_one()
    total_pages = (total_items + per_page - 1) // per_page

    if page > total_pages and total_items > 0:
        raise HTTPException(status_code=404, detail="No movies found.")

    offset = (page - 1) * per_page

    query = (
        select(MovieModel)
        .options(
            selectinload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
        )
        .order_by(MovieModel.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(query)
    movies = result.scalars().unique().all()

    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")

    BASE_PATH = "/theater/movies/"

    prev_page = f"{BASE_PATH}?page={page - 1}&per_page={per_page}" if page > 1 else None
    next_page = f"{BASE_PATH}?page={page + 1}&per_page={per_page}" if page < total_pages else None

    movies_list = [MovieListItemSchema.model_validate(movie) for movie in movies]

    return MoviesListResponseSchema(
        movies=movies_list,
        prev_page=prev_page,
        next_page=next_page,
        total_pages=total_pages,
        total_items=total_items,
    )


async def get_or_create_entities(db: AsyncSession, model, names: list[str]):
    if not names:
        return []

    result = await db.execute(select(model).where(model.name.in_(names)))
    existing_entities = result.scalars().all()
    existing_names = {e.name for e in existing_entities}

    new_entities = [model(name=name) for name in names if name not in existing_names]
    if new_entities:
        db.add_all(new_entities)
        await db.flush()

    return list(existing_entities) + new_entities


@router.post("/movies/", response_model=MovieResponseSchema, status_code=201)
async def create_movie(movie: MovieCreateSchema, db: AsyncSession = Depends(get_db)):
    existing_movie_result = await db.execute(
        select(MovieModel).where(MovieModel.name == movie.name, MovieModel.date == movie.date)
    )
    if existing_movie_result.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{movie.name}' and release date '{movie.date}' already exists.",
        )

    db_country = None
    if movie.country:
        country_result = await db.execute(select(CountryModel).where(CountryModel.code == movie.country))
        db_country = country_result.scalar_one_or_none()
        if not db_country:
            db_country = CountryModel(code=movie.country)
            db.add(db_country)
            await db.flush()

    db_genres = await get_or_create_entities(db, GenreModel, movie.genres)
    db_actors = await get_or_create_entities(db, ActorModel, movie.actors)
    db_languages = await get_or_create_entities(db, LanguageModel, movie.languages)

    movie_fields = movie.model_dump(exclude={"country", "genres", "actors", "languages"})
    db_movie = MovieModel(
        **movie_fields,
        country=db_country,
        genres=db_genres,
        actors=db_actors,
        languages=db_languages,
    )
    db.add(db_movie)

    try:
        await db.commit()
        query = (
            select(MovieModel)
            .where(MovieModel.id == db_movie.id)
            .options(
                selectinload(MovieModel.country),
                selectinload(MovieModel.genres),
                selectinload(MovieModel.actors),
                selectinload(MovieModel.languages),
            )
        )
        result = await db.execute(query)
        db_movie = result.scalar_one()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return MovieResponseSchema.model_validate(db_movie)


@router.get("/movies/{movie_id}/", response_model=MovieResponseSchema)
async def get_movie_details(movie_id: int, db: AsyncSession = Depends(get_db)):
    query = select(MovieModel).where(MovieModel.id == movie_id).options(
        selectinload(MovieModel.country),
        selectinload(MovieModel.genres),
        selectinload(MovieModel.actors),
        selectinload(MovieModel.languages),
    )
    result = await db.execute(query)
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")
    return MovieResponseSchema.model_validate(movie)


@router.delete("/movies/{movie_id}/", status_code=204)
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    query = await db.execute(select(MovieModel).where(MovieModel.id == movie_id))
    movie = query.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")
    await db.delete(movie)
    await db.commit()
    return


@router.patch("/movies/{movie_id}/")
async def update_movie(
    movie_id: int,
    movie_update: MovieUpdateSchema,
    db: AsyncSession = Depends(get_db),
):
    query = select(MovieModel).where(MovieModel.id == movie_id).options(
        selectinload(MovieModel.country),
        selectinload(MovieModel.genres),
        selectinload(MovieModel.actors),
        selectinload(MovieModel.languages),
    )
    result = await db.execute(query)
    movie_obj = result.scalar_one_or_none()

    if not movie_obj:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")

    update_data = movie_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field == "score" and not (0 <= value <= 100):
            raise HTTPException(status_code=400, detail="Invalid score")
        if field in ["budget", "revenue"] and value < 0:
            raise HTTPException(status_code=400, detail="Invalid budget/revenue")
        if field not in ["country", "genres", "actors", "languages"]:
            setattr(movie_obj, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"detail": "Movie updated successfully."},
    )
