from pydantic import BaseModel

class User(BaseModel):
    id: int
    login: str
    avatar_url: str