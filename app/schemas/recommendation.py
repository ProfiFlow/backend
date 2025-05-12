from pydantic import BaseModel

class Recommendation(BaseModel):
    title: str
    text: str 
