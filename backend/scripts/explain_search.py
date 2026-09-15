"""Run EXPLAIN ANALYZE on the real search statement for typical queries (TASKS.md 5.3).

    python scripts/explain_search.py --database-url postgresql+asyncpg://.../crm_bench

Fails with exit code 1 if any plan contains a sequential scan over `properties`
or a query takes longer than the 300 ms target.

Scenarios marked as majority filters (for example "has media", which keeps most of the
base) are allowed a sequential scan: the total count must read most rows anyway, and
PostgreSQL correctly prefers a scan to an index there. They must still meet the time target.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import false, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import SERVER_SETTINGS
from app.models import District, Property, User
from app.repositories.properties import SearchCriteria, build_search_statement

TARGET_MS = 300.0
TASHKENT = ZoneInfo("Asia/Tashkent")
MAJORITY_FILTERS = {"has media", "no media"}


def seq_scans(plan: dict[str, Any], relation: str = "properties") -> list[str]:
    found = []
    if plan.get("Node Type") == "Seq Scan" and plan.get("Relation Name") == relation:
        found.append(plan.get("Alias", relation))
    for child in plan.get("Plans", []):
        found.extend(seq_scans(child, relation))
    return found


async def run(database_url: str, verbose: bool) -> int:
    engine = create_async_engine(database_url, connect_args={"server_settings": SERVER_SETTINGS})
    dialect = postgresql.asyncpg.dialect(paramstyle="numeric_dollar")
    today = datetime.now(TASHKENT).date()
    failures = 0
    async with engine.connect() as connection:
        sample = (
            await connection.execute(
                select(Property.owner_phone_digits, Property.request_no, Property.code)
                .where(Property.is_deleted == false(), Property.request_no.is_not(None))
                .limit(1)
            )
        ).one()
        district_id = await connection.scalar(select(District.id).limit(1))
        realtor = (await connection.execute(select(User.id, User.full_name).limit(1))).one()

        scenarios: dict[str, dict[str, Any]] = {
            "no filters, first page": {},
            "no filters, page 20": {"page": 20},
            "phone fragment": {"q": sample.owner_phone_digits[-7:]},
            "full phone, formatted": {"q": f"+{sample.owner_phone_digits}"},
            "card code": {"q": str(sample.code)},
            "request number": {"q": sample.request_no},
            "landmark with typo": {"q": "Чилнзар"},
            "landmark two words": {"q": "Самарканд Дарвоза"},
            "common short word": {"q": "дом"},
            "metro name": {"q": "метро Ойбек"},
            "district name": {"q": "Юнусабад"},
            "realtor name": {"q": realtor.full_name.split()[-1]},
            "district + status": {"district_ids": [district_id], "statuses": ["hot"]},
            "occupied now": {"availability": "occupied"},
            "free from date": {"free_from": today + timedelta(days=30)},
            "realtor filter": {"created_by": [realtor.id]},
            "has media": {"has_media": True},
            "no media": {"has_media": False},
            "combined": {
                "q": "метро",
                "district_ids": [district_id],
                "availability": "free",
                "has_media": True,
            },
            "sort by code": {"sort": "-code"},
        }
        for name, params in scenarios.items():
            criteria = SearchCriteria(**{"today": today, "page": 1, "page_size": 50, **params})
            compiled = build_search_statement(criteria).compile(
                dialect=dialect, compile_kwargs={"render_postcompile": True}
            )
            positional = tuple(compiled.params[key] for key in compiled.positiontup or ())
            result = await connection.exec_driver_sql(
                f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {compiled}", positional
            )
            plan_json = result.scalar_one()
            plan_doc = (json.loads(plan_json) if isinstance(plan_json, str) else plan_json)[0]
            elapsed = plan_doc["Planning Time"] + plan_doc["Execution Time"]
            scans = seq_scans(plan_doc["Plan"])
            ok = (not scans or name in MAJORITY_FILTERS) and elapsed <= TARGET_MS
            failures += not ok
            status = "OK  " if ok else "FAIL"
            detail = f" seq scan: {', '.join(scans)}" if scans else ""
            print(f"{status} {elapsed:7.1f} ms  {name}{detail}")
            if verbose and not ok:
                print(json.dumps(plan_doc["Plan"], ensure_ascii=False, indent=1)[:6000])
    await engine.dispose()
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.database_url, args.verbose)))


if __name__ == "__main__":
    main()
