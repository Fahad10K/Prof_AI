"""
Data Models - Pydantic schemas for course structure
"""

from pydantic import BaseModel, Field
from typing import List, Optional

class SubTopic(BaseModel):
    """Defines a sub-topic within a larger learning module."""
    title: str = Field(description="The title of the sub-topic")
    content: Optional[str] = Field(None, description="Detailed generated content for this sub-topic")

class Module(BaseModel):
    """Defines a learning module or a week in the curriculum."""
    week: int = Field(description="The week number of the module")
    title: str = Field(description="The title of the module")
    sub_topics: List[SubTopic] = Field(description="A list of sub-topics covered in this module")

class CourseLMS(BaseModel):
    """The final, structured output for the entire course, ready for an LMS."""
    course_title: str = Field(description="The overall title of the course")
    modules: List[Module] = Field(description="A list of all modules in the course")