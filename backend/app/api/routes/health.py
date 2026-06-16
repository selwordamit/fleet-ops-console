from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """Liveness probe used by Docker/compose; intentionally unlogged (high frequency)."""
    return {"status": "ok"}
