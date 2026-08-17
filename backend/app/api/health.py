from fastapi import APIRouter

router = APIRouter(prefix="/api") #automatically appended to all URLS


@router.get("/health") # @router.get("xxxx") defines the CRUD operation and the path
def health() -> dict[str, str]:
    return {"status": "ok"}
# we msut mount this router to the app/main.py fileusing include_router(router)