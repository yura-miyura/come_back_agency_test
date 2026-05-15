from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app import auth as auth_helpers
from app.repositories import users as users_repo
from app.schemas import TokenOut, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate) -> UserOut:
    """Create a new user account. Returns 409 if the username is taken."""
    password_hash = auth_helpers.hash_password(payload.password)
    try:
        user = await users_repo.create_user(payload.username, password_hash)
    except users_repo.UsernameTaken:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username already taken",
        )
    return UserOut(**user)


@router.post("/login", response_model=TokenOut)
async def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenOut:
    """OAuth2 password flow: exchange username + password for a bearer JWT."""
    user = await users_repo.get_user_by_username(form.username)
    if user is None or not auth_helpers.verify_password(
        form.password, user["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
        )
    token = auth_helpers.create_access_token(subject=user["username"])
    return TokenOut(access_token=token)
