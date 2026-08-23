from pydantic import BaseModel, Field


class ProjectItem(BaseModel):
    name: str = ""
    description: str = ""
    tech: list[str] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    role: str = ""
    company: str = ""
    duration: str = ""


class ParsedResumeResponse(BaseModel):
    skills: list[str] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
