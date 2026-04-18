from pydantic import BaseModel, Field
from backend.config import OLLAMA_MODEL


class GenerateRequest(BaseModel):
    user_story: str = Field(..., min_length=20, max_length=3000,
                            description="Historia de usuario o requisito a testear")
    model: str = OLLAMA_MODEL
    context: str = Field("", max_length=1000)
    temperature: float = Field(0.25, ge=0.0, le=1.0, description="Temperatura del LLM (0.0–1.0)")
    use_rag: bool = Field(False, description="Enriquecer el prompt con contexto del corpus QA")


class GenerateResponse(BaseModel):
    test_cases: list
    edge_scenarios: list
    potential_bugs: list
    coverage_summary: dict
    raw_story: str


class AgentTrace(BaseModel):
    agent: str
    elapsed_s: float
    summary: str


class AgentGenerateRequest(BaseModel):
    user_story: str = Field(..., min_length=20, max_length=3000)
    model: str = OLLAMA_MODEL
    context: str = Field("", max_length=1000)
    temperature: float = Field(0.25, ge=0.0, le=1.0)
    use_rag: bool = False


class AgentGenerateResponse(BaseModel):
    test_cases: list
    edge_scenarios: list
    potential_bugs: list
    coverage_summary: dict
    raw_story: str
    agent_trace: list[AgentTrace]
    used_fallback: bool = False


class EvaluateRequest(BaseModel):
    requirement: str = Field(..., min_length=20, max_length=3000)
    generated_output: dict
    model: str = OLLAMA_MODEL


class EvaluateResponse(BaseModel):
    coverage: float
    relevancy: float
    consistency: float
    overall: float
    model_used: str
