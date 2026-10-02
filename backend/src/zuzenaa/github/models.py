"""Pydantic models for the GitHub/CLI layer.

They mirror only the fields we consume; unknown fields are ignored so a newer
CLI version doesn't break parsing.
"""

from pydantic import BaseModel, ConfigDict, Field


class ClassroomTeam(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    slug: str


class Classroom(BaseModel):
    model_config = ConfigDict(extra="ignore")

    short_name: str
    name: str
    term: str | None = None
    active: bool = True
    team: ClassroomTeam | None = None


class TemplateRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    owner: str
    repo: str
    branch: str | None = None


class AssignmentTest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    type: str
    points: int = 0
    setup: str | None = None
    run: str | None = None
    timeout: int | None = None
    comparison: str | None = None
    expected: str | None = None
    exit_code: int | None = Field(default=None, alias="exit-code")


class Assignment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    slug: str
    name: str
    description: str | None = None
    mode: str = "individual"
    autograder: str = "default"
    template: TemplateRef | None = None
    tests: list[AssignmentTest] = Field(default_factory=list)
    feedback_pr: bool = False
    submission_mode: str | None = None
    due: str | None = None
    available_from: str | None = None
    locked: bool = Field(default=False, validation_alias="locked")
    closed: bool = False
    max_group_size: int | None = None


class Student(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    username: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    section: str | None = None
    github_id: int | None = None
    role: str | None = None




class Org(BaseModel):
    model_config = ConfigDict(extra="ignore")

    login: str
    avatar_url: str | None = None
    description: str | None = None


class TemplateRepo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    owner: str
    name: str
    full_name: str
    private: bool = False
    default_branch: str = "main"
    description: str | None = None

