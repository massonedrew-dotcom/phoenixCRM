"""Administrative commands.

    python -m app.cli create-admin --username admin --full-name "Администратор"
    python -m app.cli seed-districts [--file districts.txt]

The admin password is read from the CRM_ADMIN_PASSWORD environment variable or
prompted for interactively; it is never accepted as a command-line argument.
"""

import argparse
import asyncio
import getpass
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from app.core.config import get_settings
from app.core.db import create_engine, create_sessionmaker
from app.core.errors import AppError
from app.schemas.users import UserCreate
from app.services import districts as districts_service
from app.services import users as users_service

TASHKENT_DISTRICTS = (
    "Алмазарский",
    "Бектемирский",
    "Мирабадский",
    "Мирзо-Улугбекский",
    "Сергелийский",
    "Учтепинский",
    "Чиланзарский",
    "Шайхантахурский",
    "Юнусабадский",
    "Яккасарайский",
    "Яшнабадский",
    "Янгихаётский",
)


def _read_password() -> str:
    if password := os.environ.get("CRM_ADMIN_PASSWORD"):
        return password
    first = getpass.getpass("Пароль: ")
    if first != getpass.getpass("Повторите пароль: "):
        raise SystemExit("Пароли не совпадают")
    return first


async def _create_admin(username: str, full_name: str) -> None:
    try:
        data = UserCreate(
            username=username, full_name=full_name, password=_read_password(), role="admin"
        )
    except ValidationError as exc:
        raise SystemExit(f"Некорректные данные: {exc}") from exc
    engine = create_engine(get_settings())
    try:
        async with create_sessionmaker(engine)() as session:
            user = await users_service.create_first_admin(
                session, username=data.username, full_name=data.full_name, password=data.password
            )
    except AppError as exc:
        raise SystemExit(exc.detail) from exc
    finally:
        await engine.dispose()
    print(f"Создан администратор {user.username}")


def _district_names(file: Path | None) -> Sequence[str]:
    if file is None:
        return TASHKENT_DISTRICTS
    return [line for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]


async def _seed_districts(file: Path | None) -> None:
    engine = create_engine(get_settings())
    try:
        async with create_sessionmaker(engine)() as session:
            added = await districts_service.seed_districts(session, _district_names(file))
    finally:
        await engine.dispose()
    print(f"Добавлено районов: {len(added)}")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    admin = commands.add_parser("create-admin", help="create an admin account")
    admin.add_argument("--username", required=True)
    admin.add_argument("--full-name", required=True)

    seed = commands.add_parser("seed-districts", help="add missing districts")
    seed.add_argument("--file", type=Path, help="UTF-8 text file, one district per line")

    args = parser.parse_args(argv)
    if args.command == "create-admin":
        asyncio.run(_create_admin(args.username, args.full_name))
    else:
        asyncio.run(_seed_districts(args.file))


if __name__ == "__main__":
    main(sys.argv[1:])
