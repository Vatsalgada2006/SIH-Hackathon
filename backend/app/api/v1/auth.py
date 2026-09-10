from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.db.session import get_db
from app.db.models import User, Vehicle
from app.core.security import get_current_user, get_current_active_user, get_current_user_with_role
from app.core.config import settings

router = APIRouter()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# JWT settings
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithm=ALGORITHM)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """
    Government/official login (username+password)
    """
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not pwd_context.verify(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/driver/login")
async def driver_login(vehicle_id: str, password: str, db: AsyncSession = Depends(get_db)):
    """
    Driver login (vehicleId+password)
    """
    # Find vehicle by vehicle_id
    result = await db.execute(select(Vehicle).where(Vehicle.vehicle_id == vehicle_id))
    vehicle = result.scalar_one_or_none()
    
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )
    
    # In a real system, vehicles would have password hashes stored
    # For this implementation, we'll use a simple check
    # In production, you'd want to store a hashed password for the vehicle
    if vehicle.vehicle_id != password:  # Simple check for demo - NOT SECURE FOR PRODUCTION
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect vehicle ID or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create a token for the driver
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": vehicle.vehicle_id, "type": "driver"}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/vehicles/register", status_code=status.HTTP_201_CREATED)
async def register_vehicle(
    vehicle_data: dict,
    current_user: User = Depends(get_current_user_with_role(["ADMIN", "CONTROL_ROOM", "FIELD_OFFICER"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new vehicle (for government users only)
    """
    # Check if vehicle already exists
    result = await db.execute(select(Vehicle).where(Vehicle.vehicle_id == vehicle_data["vehicle_id"]))
    existing_vehicle = result.scalar_one_or_none()
    
    if existing_vehicle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vehicle with this ID already exists"
        )
    
    # Create new vehicle
    vehicle = Vehicle(
        vehicle_id=vehicle_data["vehicle_id"],
        type=vehicle_data.get("type", "CAR"),
        capacity=vehicle_data.get("capacity")
    )
    
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    
    return {
        "id": vehicle.id,
        "vehicle_id": vehicle.vehicle_id,
        "type": vehicle.type,
        "capacity": vehicle.capacity,
        "message": "Vehicle registered successfully"
    }
