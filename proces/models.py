from typing import Optional, List
from pydantic import BaseModel, field_validator
from datetime import datetime

class Borger(BaseModel):
    cpr:str
    navn:str
    oprindelsesland:Optional[str]
    findes_i_dwh:bool = False
    findes_i_momentum:bool = False
    
    @field_validator('cpr')
    @classmethod
    def validate_cpr(cls, v):
        if not v:
            raise ValueError('CPR cannot be empty')
        if len(v) != 10:
            raise ValueError('CPR must be exactly 10 digits')
        if not v.isdigit():
            raise ValueError('CPR must contain only digits')
        return v 

