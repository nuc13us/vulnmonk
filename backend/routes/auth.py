from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from .. import crud, models, schemas, auth
from ..database import get_db
from typing import List
from datetime import timedelta

router = APIRouter()

# ==================== AUTH ENDPOINTS ====================

@router.post("/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(days=auth.ACCESS_TOKEN_EXPIRE_DAYS)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/auth/me", response_model=schemas.User)
def get_current_user_info(current_user: models.User = Depends(auth.get_current_user)):
    """Get current authenticated user information."""
    return current_user


@router.post("/auth/change-password")
def change_password(
    password_data: schemas.PasswordChange,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Change password for the current user."""
    if not auth.verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect old password")

    hashed_password = auth.get_password_hash(password_data.new_password)
    crud.update_user_password(db, current_user, hashed_password)
    return {"success": True, "message": "Password updated successfully"}


# ==================== USER MANAGEMENT ENDPOINTS (ADMIN ONLY) ====================

@router.get("/users/", response_model=List[schemas.User])
def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    """List all users (Admin only)."""
    return crud.get_users(db, skip=skip, limit=limit)


@router.post("/users/", response_model=schemas.User)
def create_user(
    user: schemas.UserCreate,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Create a new user (Admin only)."""
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    if user.role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")

    hashed_password = auth.get_password_hash(user.password)
    return crud.create_user(db=db, user=user, hashed_password=hashed_password)


@router.put("/users/{user_id}/role", response_model=schemas.User)
def update_user_role(
    user_id: int,
    role_data: schemas.UserUpdate,
    current_user: models.User = Depends(auth.get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Update user role (Admin only)."""
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    if role_data.role:
        if role_data.role not in ["admin", "user"]:
            raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")
        crud.update_user_role(db, user, role_data.role)

    if role_data.is_active is not None:
        crud.update_user_status(db, user, role_data.is_active)

    db.refresh(user)
    return user
