from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from databases import Database

DATABASE_URL = "sqlite:///./test.db"

database = Database(DATABASE_URL)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    is_manager = Column(Boolean, default=False)

class ReimbursementRequest(Base):
    __tablename__ = "requests"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String)
    amount = Column(Integer)
    status = Column(String, default="Pending")
    user_id = Column(Integer)

Base.metadata.create_all(bind=engine)

class ReimbursementRequestCreate(BaseModel):
    description: str
    amount: int

class UserCreate(BaseModel):
    username: str
    password: str
    is_manager: bool = False

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/users/", response_model=UserCreate)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(username=user.username, password=user.password, is_manager=user.is_manager)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if user is None or user.password != form_data.password:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    return {"access_token": user.username, "token_type": "bearer"}

@app.post("/requests/", response_model=ReimbursementRequestCreate)
async def create_request(request: ReimbursementRequestCreate, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == token).first()
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid user")
    db_request = ReimbursementRequest(**request.dict(), user_id=user.id)
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    return db_request

@app.get("/requests/")
async def read_requests(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == token).first()
    if not user.is_manager:
        raise HTTPException(status_code=403, detail="Not authorized")
    return db.query(ReimbursementRequest).all()

@app.post("/requests/{request_id}/approve")
async def approve_request(request_id: int, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == token).first()
    if not user.is_manager:
        raise HTTPException(status_code=403, detail="Not authorized")
    request = db.query(ReimbursementRequest).filter(ReimbursementRequest.id == request_id).first()
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    request.status = "Approved"
    db.commit()
    db.refresh(request)
    return request

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
