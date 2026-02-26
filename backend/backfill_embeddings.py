import asyncio
from sqlalchemy import select
from app.db import get_db
from app.models import Concept
from app.services.llm import embed_text

async def run():
    async for db in get_db():

        res = await db.execute(select(Concept))
        concepts = res.scalars().all()

        for c in concepts:
            if c.embedding:
                continue

            text = f"""
            {c.name}
            {c.description or ""}
            {c.definition or ""}
            {c.when_to_use or ""}
            {c.pitfalls or ""}
            """

            c.embedding = embed_text(text)

        await db.commit()

asyncio.run(run())
