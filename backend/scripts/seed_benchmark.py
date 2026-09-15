"""Fill a throwaway database with realistic cards for search benchmarking (TASKS.md 5.4).

    python scripts/seed_benchmark.py --database-url postgresql+asyncpg://.../crm_bench --count 100000

Rows are inserted directly, without audit records: never point this at a real database.
The script refuses to run if the target already contains cards.
"""

import argparse
import asyncio
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from alembic import command
from alembic.config import Config
from sqlalchemy import func, insert, select, text
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.cli import TASHKENT_DISTRICTS
from app.core.enums import InterestStatus, MediaKind, Role
from app.core.security import hash_password
from app.models import District, Property, PropertyMedia, User

BATCH_SIZE = 5_000
TASHKENT = ZoneInfo("Asia/Tashkent")
AGENT_COUNT = 40

METRO = [
    "Чиланзар", "Мирзо-Улугбек", "Новза", "Миллий бог", "Бунёдкор", "Пахтакор", "Космонавтлар",
    "Ойбек", "Ташкент", "Буюк Ипак Йули", "Минор", "Бодомзор", "Юнусабад", "Шахристан", "Беруни",
    "Тинчлик", "Чорсу", "Гафур Гулом", "Алишер Навои", "Хамид Олимжон", "Пушкин", "Машинасозлар",
]  # fmt: skip
PLACES = [
    "Самарканд Дарвоза", "Мега Планет", "Некст", "Компас", "Ривьера", "Корзинка", "Макро",
    "парк Навруз", "Анхор", "Хадра", "Ц-1", "Ц-5", "Кадышева", "Госпиталь", "Алайский базар",
    "Фархадский базар", "Ипподром", "Tashkent City", "Сквер Амира Темура", "Оперный театр",
]  # fmt: skip
STREETS = [
    "Бунёдкор", "Мукимий", "Катартал", "Фаробий", "Нукус", "Шота Руставели", "Бабура",
    "Амира Темура", "Мустакиллик", "Навои", "Лабзак", "Беруни", "Қорасарой", "Богишамол",
]  # fmt: skip
FIRST_NAMES = [
    "Азиз", "Дилноза", "Шахзод", "Мадина", "Рустам", "Гульнора", "Санжар", "Нодира", "Бахтиёр",
    "Малика", "Ильдар", "Ольга", "Сергей", "Наталья", "Тимур", "Камола", "Жасур", "Екатерина",
]  # fmt: skip
LAST_NAMES = [
    "Каримов", "Юсупова", "Рахимов", "Ахмедова", "Ташкентов", "Ким", "Пак", "Иванова",
    "Садыков", "Норматова", "Хасанов", "Абдуллаева", "Петров", "Мирзаев",
]  # fmt: skip
OPERATORS = ["90", "91", "93", "94", "95", "97", "98", "99", "33", "88"]


def landmark(rng: random.Random) -> str:
    templates = [
        lambda: f"рядом с метро {rng.choice(METRO)}, дом {rng.randint(1, 120)}",
        lambda: f"ул. {rng.choice(STREETS)} {rng.randint(1, 90)}, ориентир {rng.choice(PLACES)}",
        lambda: f"{rng.choice(PLACES)}, {rng.randint(1, 16)} этаж",
        lambda: f"квартал {rng.randint(1, 30)}, напротив {rng.choice(PLACES)}",
        lambda: f"м. {rng.choice(METRO)} — {rng.randint(3, 20)} мин пешком, ул. {rng.choice(STREETS)}",
    ]
    return rng.choice(templates)()


def phone(rng: random.Random) -> str:
    digits = f"{rng.choice(OPERATORS)}{rng.randint(0, 9_999_999):07d}"
    formats = [
        f"+998 {digits[:2]} {digits[2:5]}-{digits[5:7]}-{digits[7:]}",
        f"998{digits}",
        f"({digits[:2]}) {digits[2:5]} {digits[5:7]} {digits[7:]}",
        digits,
    ]
    return rng.choice(formats)


async def seed(database_url: str, count: int, seed_value: int) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    await asyncio.to_thread(command.upgrade, config, "head")

    rng = random.Random(seed_value)
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        existing = await connection.scalar(select(func.count()).select_from(Property))
        if existing:
            raise SystemExit(
                f"Target already has {existing} cards; use an empty benchmark database"
            )

        password_hash = await hash_password("benchmark-password")
        users = [
            {
                "id": uuid.uuid4(),
                "username": f"agent{index:03d}",
                "full_name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                "password_hash": password_hash,
                "role": Role.AGENT if index else Role.HEAD,
                "is_active": rng.random() > 0.1,
            }
            for index in range(AGENT_COUNT)
        ]
        await connection.execute(insert(User), users)
        districts = [
            {"id": uuid.uuid4(), "name": name, "is_active": True} for name in TASHKENT_DISTRICTS
        ]
        await connection.execute(insert(District), districts)

    today = datetime.now(TASHKENT).date()
    started = datetime.now(UTC)
    for offset in range(0, count, BATCH_SIZE):
        cards = []
        media = []
        for _ in range(min(BATCH_SIZE, count - offset)):
            card_id = uuid.uuid4()
            creator = rng.choice(users)
            created_at = datetime.now(UTC) - timedelta(minutes=rng.randint(0, 3 * 365 * 24 * 60))
            occupied = rng.random() < 0.45
            cards.append(
                {
                    "id": card_id,
                    "request_no": str(rng.randint(1000, 999_999)) if rng.random() < 0.7 else None,
                    "district_id": rng.choice(districts)["id"],
                    "landmark": landmark(rng),
                    "owner_name": f"{rng.choice(FIRST_NAMES)}" if rng.random() < 0.6 else None,
                    "owner_phone": phone(rng),
                    "interest_status": rng.choice(list(InterestStatus)),
                    "free_until": (
                        today + timedelta(days=rng.randint(10, 400)) if rng.random() < 0.3 else None
                    ),
                    "occupied_until": (
                        today + timedelta(days=rng.randint(-200, 365)) if occupied else None
                    ),
                    "price": Decimal(rng.randint(150, 3000)) if rng.random() < 0.8 else None,
                    "note": "Хозяин на связи вечером" if rng.random() < 0.2 else None,
                    "is_deleted": rng.random() < 0.03,
                    "created_by": creator["id"],
                    "created_at": created_at,
                }
            )
            if rng.random() < 0.6:
                for sort_order in range(rng.randint(1, 6)):
                    media_id = uuid.uuid4()
                    kind = MediaKind.VIDEO if rng.random() < 0.15 else MediaKind.PHOTO
                    media.append(
                        {
                            "id": media_id,
                            "property_id": card_id,
                            "kind": kind,
                            "storage_key": f"properties/{card_id}/{media_id}.jpg",
                            "thumb_key": f"properties/{card_id}/thumbs/{media_id}.webp",
                            "original_name": f"IMG_{rng.randint(1000, 9999)}.jpg",
                            "mime_type": "image/jpeg" if kind == MediaKind.PHOTO else "video/mp4",
                            "size_bytes": rng.randint(200_000, 8_000_000),
                            "sort_order": sort_order,
                            "uploaded_by": creator["id"],
                        }
                    )
        async with engine.begin() as connection:
            await connection.execute(insert(Property), cards)
            if media:
                await connection.execute(insert(PropertyMedia), media)
        print(f"{offset + len(cards):>7} cards", flush=True)

    async with engine.connect() as connection:
        await connection.execution_options(isolation_level="AUTOCOMMIT")
        await connection.execute(text("VACUUM ANALYZE"))
    await engine.dispose()
    print(f"Done in {(datetime.now(UTC) - started).total_seconds():.0f} s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--count", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    asyncio.run(seed(args.database_url, args.count, args.seed))


if __name__ == "__main__":
    main()
