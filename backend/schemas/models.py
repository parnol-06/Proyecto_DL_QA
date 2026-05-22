from pydantic import BaseModel, Field
from backend.config import OLLAMA_MODEL


class GenerateRequest(BaseModel):
    user_story: str = Field(..., min_length=20, max_length=3000,
                            description="User story or requirement to test")
    model: str = OLLAMA_MODEL
    context: str = Field("", max_length=1000)
    temperature: float = Field(0.25, ge=0.0, le=1.0, description="LLM temperature (0.0–1.0)")
    use_rag: bool = Field(False, description="Enrich the prompt with context from the QA corpus")
    categories: list[str] = Field(default_factory=list, description="Categories to generate; empty = all")
    tc_count: int = Field(10, ge=1, le=50, description="Number of test cases to generate")
    edge_count: int = Field(4, ge=0, le=20, description="Number of edge scenarios to generate")
    bug_count: int = Field(3, ge=0, le=20, description="Number of potential bugs to generate")


class GenerateResponse(BaseModel):
    test_cases: list
    edge_scenarios: list
    potential_bugs: list
    coverage_summary: dict
    raw_story: str
    generation_trace_id: str = Field("", description="Opik trace_id — pass it in EvaluateRequest.source_generation_trace_id")


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
    categories: list[str] = Field(default_factory=list)
    tc_count: int = Field(10, ge=1, le=50)
    edge_count: int = Field(4, ge=0, le=20)
    bug_count: int = Field(3, ge=0, le=20)


class AgentGenerateResponse(BaseModel):
    test_cases: list
    edge_scenarios: list
    potential_bugs: list
    coverage_summary: dict
    raw_story: str
    agent_trace: list[AgentTrace]
    used_fallback: bool = False
    optimizer_output: dict = Field(default_factory=dict)
    generation_trace_id: str = Field("", description="Opik trace_id — pass it in EvaluateRequest.source_generation_trace_id")


class RegenerateTCRequest(BaseModel):
    tc_id: str
    user_story: str = Field(..., min_length=20, max_length=3000)
    model: str = OLLAMA_MODEL
    temperature: float = Field(0.25, ge=0.0, le=1.0)
    category: str = ""
    context: str = Field("", max_length=1000)


class EvaluateRequest(BaseModel):
    requirement: str = Field(..., min_length=20, max_length=3000)
    generated_output: dict
    model: str = OLLAMA_MODEL
    eval_model: str = Field("", description="Model for GEval evaluation (should differ from generation model to avoid bias)")
    source_generation_trace_id: str = Field(
        "",
        description="Opik trace_id of the generation that produced these cases — enables Generate → Evaluate correlation",
    )


class EvaluateResponse(BaseModel):
    coverage: float
    relevancy: float
    consistency: float
    specificity: float = 0.0
    nonfunctional_balance: float = 0.0
    overall: float
    model_used: str
    evaluation_trace_id: str = Field("", description="Opik trace_id of this evaluation")
