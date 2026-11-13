from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, String, Integer, Boolean, DateTime, ARRAY, Index, select, update, func, text as sql_text
from typing import Optional, List
from app.config import config
from app.models import Profile

DATABASE_URL = config.database_url.get_secret_value()

# Сколько разных пользователей должны пожаловаться, чтобы анкета пропала из поиска
REPORTS_TO_HIDE = 5

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class UserTable(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    name: Mapped[str] = mapped_column(String(15), nullable=True)
    age: Mapped[int] = mapped_column(Integer, nullable=True)
    city: Mapped[str] = mapped_column(String(50), nullable=True)
    text: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)
    gender: Mapped[str] = mapped_column(String(10), nullable=True)
    target_gender: Mapped[str] = mapped_column(String(10), nullable=True)
    media: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    premium: Mapped[bool] = mapped_column(Boolean, default=False)

class ReactionTable(Base):
    __tablename__ = "reactions"
    __table_args__ = (Index("ix_reactions_pair", "from_id", "to_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    from_id: Mapped[int] = mapped_column(BigInteger)
    to_id: Mapped[int] = mapped_column(BigInteger, index=True)
    is_like: Mapped[bool] = mapped_column(Boolean)
    message: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)

class ReportTable(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    from_id: Mapped[int] = mapped_column(BigInteger)
    to_id: Mapped[int] = mapped_column(BigInteger, index=True)
    reason: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

# create_all не трогает уже существующие таблицы, поэтому новые колонки и индексы догоняем вручную
MIGRATIONS = [
    "ALTER TABLE reactions ADD COLUMN IF NOT EXISTS message VARCHAR(400)",
    "CREATE INDEX IF NOT EXISTS ix_reactions_pair ON reactions (from_id, to_id)",
    "CREATE INDEX IF NOT EXISTS ix_reactions_to_id ON reactions (to_id)",
]


# Анкеты, на которые пожаловались REPORTS_TO_HIDE разных людей
def hidden_users_query():
    return (
        select(ReportTable.to_id)
        .group_by(ReportTable.to_id)
        .having(func.count(func.distinct(ReportTable.from_id)) >= REPORTS_TO_HIDE)
    )

async def get_reaction(session: AsyncSession, from_id: int, to_id: int) -> Optional[ReactionTable]:
    result = await session.execute(
        select(ReactionTable)
        .where(ReactionTable.from_id == from_id, ReactionTable.to_id == to_id)
        .order_by(ReactionTable.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for statement in MIGRATIONS:
            await conn.execute(sql_text(statement))

async def save_profile(profile_data: dict):
    # exclude_unset: при редактировании одного поля остальные не затираются дефолтами
    profile_dict = Profile(**profile_data).model_dump(exclude_unset=True)
    async with async_session() as session:
        user = await session.get(UserTable, profile_dict["id"])
        if user:
            for key, value in profile_dict.items():
                setattr(user, key, value)
        else:
            session.add(UserTable(**profile_dict))
        await session.commit()

async def get_profile(user_id: int) -> Optional[Profile]:
    async with async_session() as session:
        user = await session.get(UserTable, user_id)
        return Profile.model_validate(user, from_attributes=True) if user else None

async def profile_exists(user_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(UserTable.id).where(UserTable.id == user_id))
        return result.scalar_one_or_none() is not None

async def toggle_active(user_id: int, status: bool):
    async with async_session() as session:
        await session.execute(update(UserTable).where(UserTable.id == user_id).values(active=status))
        await session.commit()

async def update_username(user_id: int, username: Optional[str]):
    async with async_session() as session:
        await session.execute(update(UserTable).where(UserTable.id == user_id).values(username=username))
        await session.commit()

async def get_match_candidates(user_id: int, gender: str, target_gender: str, age: int, limit: int = 15):
    seen_query = select(ReactionTable.to_id).where(ReactionTable.from_id == user_id)
    query = (
        select(UserTable)
        .where(
            UserTable.id != user_id,
            UserTable.active == True,
            UserTable.gender == target_gender,
            UserTable.target_gender == gender,
            func.abs(UserTable.age - age) <= 3,
            ~UserTable.id.in_(seen_query),
            ~UserTable.id.in_(hidden_users_query())
        )
        .order_by(func.abs(UserTable.age - age).asc(), func.random())
        .limit(limit)
    )
    async with async_session() as session:
        return (await session.execute(query)).scalars().all()

async def get_incoming_likes(user_id: int):
    my_reactions_query = select(ReactionTable.to_id).where(ReactionTable.from_id == user_id)
    liked_me_query = select(ReactionTable.from_id).where(ReactionTable.to_id == user_id, ReactionTable.is_like == True)
    query = select(UserTable).where(
        UserTable.id.in_(liked_me_query),
        UserTable.active == True,
        ~UserTable.id.in_(my_reactions_query),
        ~UserTable.id.in_(hidden_users_query())
    )
    async with async_session() as session:
        return (await session.execute(query)).scalars().all()

async def add_reaction(from_id: int, to_id: int, is_like: bool, message: Optional[str] = None):
    async with async_session() as session:
        reaction = await get_reaction(session, from_id, to_id)
        if reaction:
            reaction.is_like = is_like
            reaction.message = message
        else:
            session.add(ReactionTable(from_id=from_id, to_id=to_id, is_like=is_like, message=message))
        await session.commit()

async def has_liked(from_id: int, to_id: int) -> bool:
    async with async_session() as session:
        reaction = await get_reaction(session, from_id, to_id)
        return reaction is not None and reaction.is_like

async def get_like_message(from_id: int, to_id: int) -> Optional[str]:
    async with async_session() as session:
        reaction = await get_reaction(session, from_id, to_id)
        return reaction.message if reaction and reaction.is_like else None

async def add_report(from_id: int, to_id: int, reason: str) -> int:
    """Сохраняет жалобу и возвращает число разных пользователей, пожаловавшихся на анкету."""
    async with async_session() as session:
        session.add(ReportTable(from_id=from_id, to_id=to_id, reason=reason))
        await session.commit()
        result = await session.execute(
            select(func.count(func.distinct(ReportTable.from_id))).where(ReportTable.to_id == to_id)
        )
        return result.scalar_one()
