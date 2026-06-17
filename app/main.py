from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, bookings, properties
from app.core.config import get_settings
from app.core.redis import close_redis

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: could run migrations, warm caches, etc.
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting up")
    yield
    # Shutdown: close connections, flush logs
    await close_redis()
    print(f"🛑 {settings.APP_NAME} shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router,       prefix=settings.API_V1_PREFIX)
app.include_router(properties.router, prefix=settings.API_V1_PREFIX)
app.include_router(bookings.router,   prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME}
