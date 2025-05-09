from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from ..database import get_db
from ..database.user import User
import logging

router = APIRouter(prefix="", tags=["debug"])
logger = logging.getLogger(__name__)

@router.get("/users", summary="Get all users")
async def get_all_users(db: AsyncSession = Depends(get_db)):
    try:
        # Асинхронный запрос к БД
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        if not users:
            return {"message": "No users found"}
            
        return {
            "count": len(users),
            "users": users
        }
        
    except Exception as e:
        logger.error(f"Database error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )