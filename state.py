from typing import TypedDict, Annotated, Sequence, Literal
from langchain_core.messages import  SystemMessage, BaseMessage 
from operator import add as add_messages
from pydantic import BaseModel

class SupervisorState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    validator_status: str
    
    
    
class ValidationRouting(BaseModel):
    status: Literal["APPROVED", "REVISION_NEEDED"]
    reason: str
    