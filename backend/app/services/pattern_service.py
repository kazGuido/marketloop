from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Pattern
from app.models.enums import PatternStatus
from app.services.technical import HarmonicProjection


async def upsert_pending_pattern(session: AsyncSession, projection: HarmonicProjection) -> Pattern:
    result = await session.execute(select(Pattern).where(Pattern.source_key == projection.source_key))
    pattern = result.scalar_one_or_none()
    if pattern is None:
        pattern = Pattern(
            source_key=projection.source_key,
            symbol=projection.symbol,
            pattern_type=projection.pattern_type,
            direction=projection.direction,
            timeframe=projection.timeframe,
            coords=projection.coords,
            prz_upper=projection.prz_upper,
            prz_lower=projection.prz_lower,
            status=PatternStatus.PENDING,
        )
        session.add(pattern)
    elif pattern.status == PatternStatus.PENDING:
        pattern.coords = projection.coords
        pattern.prz_upper = projection.prz_upper
        pattern.prz_lower = projection.prz_lower
    await session.commit()
    await session.refresh(pattern)
    return pattern


async def pending_patterns(session: AsyncSession) -> list[Pattern]:
    result = await session.execute(select(Pattern).where(Pattern.status == PatternStatus.PENDING))
    return list(result.scalars().all())


async def active_patterns(session: AsyncSession) -> list[Pattern]:
    result = await session.execute(select(Pattern).where(Pattern.status == PatternStatus.ACTIVE))
    return list(result.scalars().all())
