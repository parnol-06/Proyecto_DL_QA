"""
llm_service.py — LLM generation service (Ollama).

Called from within root_trace() contexts owned by generate routes.
Produces child spans:

generate_test_cases()
├── rag_pipeline (optional)
│   ├── embedding_generation
│   └── chromadb_query
├── prompt_compilation
├── ollama_chat (llm_span)
└── llm_json_parse

stream_generate_test_cases()
├── rag_pipeline (optional)
│   ├── embedding_generation
│   └── chromadb_query
├── ollama_stream (llm_span) ← tracks TTFT + chunk count
└── llm_json_parse
"""

import asyncio
import json
import logging
import re
import time

import ollama

from backend.config import OLLAMA_HOST, OLLAMA_TEMPERATURE, OLLAMA_CONTEXT_SIZE
from backend.observability import tracer
from backend.schemas.models import GenerateRequest, GenerateResponse

_ollama = ollama.Client(host=OLLAMA_HOST)

logger = logging.getLogger(__name__)

_llm_semaphore = asyncio.Semaphore(1)


def _calc_num_predict(tc_count: int, edge_count: int, bug_count: int) -> int:
    return max(4096, tc_count * 280 + edge_count * 120 + bug_count * 160 + 1000)


SYSTEM_PROMPT = """You are a senior QA engineer EXPERT with 15 years of experience. Your job is to be EXTREMELY DETAILED and thorough.

MANDATORY INSTRUCTION #1: YOUR ENTIRE RESPONSE MUST BE EXCLUSIVELY IN ENGLISH. ABSOLUTELY NOTHING IN ANY OTHER LANGUAGE.
MANDATORY INSTRUCTION #2: YOU MUST GENERATE EXACTLY THE NUMBER OF CASES SPECIFIED IN THE PROMPT. NO MORE, NO LESS.
MANDATORY INSTRUCTION #3: YOU MUST FOLLOW THE CATEGORY DISTRIBUTION FROM THE PROMPT. THE "category" FIELD MUST MATCH EXACTLY THE ASSIGNED CATEGORY.
MANDATORY INSTRUCTION #4: EACH TEST CASE MUST HAVE AT LEAST 5 DETAILED STEPS.
MANDATORY INSTRUCTION #5: DO NOT GENERATE ONLY BASIC FUNCTIONAL CASES. YOU MUST COVER ALL INDICATED TEST TYPES.
MANDATORY INSTRUCTION #6: EACH STEP MUST BE SPECIFIC, NOT GENERIC.
MANDATORY INSTRUCTION #7: NON-FUNCTIONAL CASES (PERFORMANCE, SECURITY, USABILITY) MUST HAVE QUANTIFIABLE AND MEASURABLE CONDITIONS AND RESULTS. NOT GENERIC.
MANDATORY INSTRUCTION #8: FOR PERFORMANCE CASES ALWAYS SPECIFY MAXIMUM TIMES, LOAD AND CONCRETE NUMBER OF USERS.
MANDATORY INSTRUCTION #9: CLEARLY DIFFERENTIATE FUNCTIONAL FROM NON-FUNCTIONAL CASES. NEVER MIX THEM.

Given a user story or requirement, you MUST respond ONLY with a valid JSON object.
No markdown formatting, no explanations, just the raw JSON.

The JSON structure must be:
{
  "test_cases": [
    {
      "id": "TC-001",
      "title": "string",
      "category": "happy_path | edge_case | negative | security | performance | usability | compatibility",
      "priority": "high | medium | low",
      "preconditions": ["string"],
      "steps": ["string"],
      "expected_result": "string",
      "test_type": "functional | non_functional | integration | ui | api | database | performance | security"
    }
  ],
  "edge_scenarios": [
    {
      "id": "ES-001",
      "scenario": "string",
      "risk_level": "high | medium | low",
      "description": "string"
    }
  ],
  "potential_bugs": [
    {
      "id": "BUG-001",
      "title": "string",
      "area": "string",
      "likelihood": "high | medium | low",
      "description": "string",
      "suggested_test": "string"
    }
  ],
  "coverage_summary": {
    "total_test_cases": 0,
    "categories_covered": ["string"],
    "estimated_coverage_percent": 0,
    "missing_areas": ["string"]
  }
}"""


def _distribute_categories(tc_count: int, categories: list) -> list[tuple[str, int]]:
    n = len(categories)
    if n == 0:
        return []
    base, rem = divmod(tc_count, n)
    return [(cat, base + (1 if i < rem else 0)) for i, cat in enumerate(categories)]


def _build_prompt(req: GenerateRequest, rag_context: str = "") -> str:
    rag_section = (
        f"\n\nQA KNOWLEDGE BASE CONTEXT (use this information to enrich the test cases):\n"
        f"{rag_context}\n"
        if rag_context else ""
    )
    cats = getattr(req, "categories", [])
    all_cats = ["happy_path", "edge_case", "negative", "security", "performance", "usability", "compatibility"]
    active_cats = cats if cats else all_cats

    tc_count   = getattr(req, "tc_count",   10)
    edge_count = getattr(req, "edge_count",  4)
    bug_count  = getattr(req, "bug_count",   3)

    dist = _distribute_categories(tc_count, active_cats)
    dist_lines = "\n".join(f"  - {cat}: {count} case{'s' if count != 1 else ''}" for cat, count in dist)

    return f"""User Story / Requirement:
{req.user_story}

Additional context:
{req.context if req.context else 'None'}
{rag_section}
MANDATORY INSTRUCTION: THE ENTIRE RESPONSE MUST BE 100% IN ENGLISH.

EXACT DISTRIBUTION OF TEST CASES TO GENERATE (total: {tc_count}):
{dist_lines}

DISTRIBUTION RULES:
- Generate EXACTLY {tc_count} test cases in total.
- Generate EXACTLY the indicated number for EACH category, no more, no less.
- The "category" field of each case MUST be exactly one of: {", ".join(active_cats)}
- Generate cases in distribution order: first all "{dist[0][0]}" cases, then the next category, etc.

EDGE SCENARIOS: Generate EXACTLY {edge_count} edge scenarios (array "edge_scenarios").
POTENTIAL BUGS: Generate EXACTLY {bug_count} potential bugs (array "potential_bugs").

EACH NON-FUNCTIONAL CASE MUST HAVE CONCRETE AND MEASURABLE NUMERICAL VALUES.
EACH CASE MUST HAVE AT MINIMUM 5 DETAILED AND SPECIFIC STEPS.
Remember: respond ONLY with the raw JSON object, without any other text."""


def _parse_llm_output(content: str) -> dict:
    with tracer.parse_span(len(content)) as s:
        json_match = re.search(r"\{[\s\S]*\}", content)
        if not json_match:
            tracer.update_span(s, output={"success": False, "reason": "no_json_found"})
            raise ValueError("Model did not return a valid JSON response")

        raw = json_match.group()
        result: dict | None = None

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            pass

        if result is None:
            try:
                from json_repair import repair_json
                repaired = repair_json(raw, return_objects=True)
                if isinstance(repaired, dict):
                    result = repaired
            except Exception:
                pass

        if result is None:
            try:
                fixed = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', raw)
                fixed = fixed.replace("'", '"')
                result = json.loads(fixed)
            except json.JSONDecodeError as err:
                tracer.update_span(s, output={"success": False, "reason": str(err)[:200]})
                logger.error("Irreparable JSON | error=%s | fragment=%s", err, raw[:300])
                raise

        tracer.update_span(s, output={
            "success": True,
            "tc_count": len(result.get("test_cases", [])),
            "has_edge_scenarios": bool(result.get("edge_scenarios")),
            "has_bugs": bool(result.get("potential_bugs")),
        })
        return result


def _build_response(data: dict, raw_story: str) -> GenerateResponse:
    test_cases = data.get("test_cases", [])

    covered_cats = list({tc.get("category") for tc in test_cases if tc.get("category")})
    all_expected_cats = {"happy_path", "edge_case", "negative", "security", "performance", "usability", "compatibility"}
    coverage_pct = round((len(covered_cats) / len(all_expected_cats)) * 100, 2) if all_expected_cats else 0
    missing_cats = list(all_expected_cats - set(covered_cats))

    default_coverage = {
        "total_test_cases": len(test_cases),
        "categories_covered": covered_cats,
        "estimated_coverage_percent": coverage_pct,
        "missing_areas": missing_cats,
    }

    coverage = data.get("coverage_summary") or default_coverage
    coverage["total_test_cases"] = len(test_cases)
    coverage["categories_covered"] = covered_cats
    coverage["estimated_coverage_percent"] = coverage_pct
    coverage["missing_areas"] = missing_cats

    return GenerateResponse(
        test_cases=test_cases,
        edge_scenarios=data.get("edge_scenarios", []),
        potential_bugs=data.get("potential_bugs", []),
        coverage_summary=coverage,
        raw_story=raw_story,
    )


def _call_ollama_with_span(model: str, messages: list, options: dict, prompt_for_tokens: str = "") -> str:
    """
    Blocking Ollama chat call wrapped in an llm_span.
    Runs in main thread or thread executor — ContextVars propagate in both cases.
    """
    system_content = messages[0].get("content", "") if messages and messages[0].get("role") == "system" else ""
    user_content = messages[-1].get("content", "") if messages else prompt_for_tokens

    with tracer.llm_span(
        "ollama_chat",
        model=model,
        system_prompt=system_content,
        user_prompt=user_content,
        temperature=options.get("temperature", OLLAMA_TEMPERATURE),
        num_ctx=options.get("num_ctx", OLLAMA_CONTEXT_SIZE),
        num_predict=options.get("num_predict", 4096),
    ) as s:
        t0 = time.monotonic()
        response = _ollama.chat(model=model, messages=messages, options=options)
        elapsed_ms = round((time.monotonic() - t0) * 1000)
        content = response["message"]["content"]

        output_tokens = tracer.estimate_tokens(content)
        input_tokens = tracer.estimate_tokens(system_content + user_content)
        tracer.update_span(
            s,
            output={"response_preview": content[:400]},
            metadata={
                "response_chars": len(content),
                "inference_time_ms": elapsed_ms,
                "tokens_output_estimated": output_tokens,
                "tokens_input_estimated": input_tokens,
                "usage": {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
            },
        )
        logger.info(
            "Ollama call complete",
            extra={
                "model": model,
                "inference_time_ms": elapsed_ms,
                "response_chars": len(content),
                "tokens_in_estimated": input_tokens,
                "tokens_out_estimated": output_tokens,
            },
        )
        return content


async def stream_generate_test_cases(req: GenerateRequest):
    """
    Async generator SSE.
    Tracks TTFT (time-to-first-token) and chunk count.
    """
    rag_context = ""
    if req.use_rag:
        try:
            from backend.services.rag_service import semantic_search
            with tracer.rag_span(req.user_story) as s:
                rag_context = semantic_search(req.user_story)
                tracer.update_span(
                    s,
                    output={"context_chars": len(rag_context), "has_context": bool(rag_context)},
                )
            if rag_context:
                logger.info("RAG: context retrieved (%d chars)", len(rag_context))
        except Exception as exc:
            logger.warning("RAG unavailable: %s", exc)

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    prompt = _build_prompt(req, rag_context)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]
    num_predict = _calc_num_predict(req.tc_count, req.edge_count, req.bug_count)
    num_ctx     = max(OLLAMA_CONTEXT_SIZE, num_predict + 3000)
    options = {"temperature": req.temperature, "num_ctx": num_ctx, "top_p": 0.7, "num_predict": num_predict}

    def _stream_sync() -> None:
        buf = []
        input_tokens = tracer.estimate_tokens(SYSTEM_PROMPT + prompt)
        ttft_ms: float = 0.0
        chunk_count: int = 0

        with tracer.llm_span(
            "ollama_stream",
            model=req.model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=req.temperature,
            num_ctx=num_ctx,
            num_predict=num_predict,
        ) as s:
            try:
                t0 = time.monotonic()
                for chunk in _ollama.chat(model=req.model, messages=messages,
                                         options=options, stream=True):
                    token = chunk["message"]["content"]
                    buf.append(token)
                    if not ttft_ms and token:
                        ttft_ms = round((time.monotonic() - t0) * 1000)
                    chunk_count += 1
                    loop.call_soon_threadsafe(queue.put_nowait, {"token": token})

                elapsed = round((time.monotonic() - t0) * 1000)
                accumulated = "".join(buf)
                output_tokens = tracer.estimate_tokens(accumulated)
                tracer.update_span(
                    s,
                    output={"response_preview": accumulated[:300]},
                    metadata={
                        "response_chars": len(accumulated),
                        "inference_time_ms": elapsed,
                        "ttft_ms": ttft_ms,
                        "chunks_received": chunk_count,
                        "tokens_output_estimated": output_tokens,
                        "tokens_input_estimated": input_tokens,
                        "usage": {
                            "prompt_tokens": input_tokens,
                            "completion_tokens": output_tokens,
                            "total_tokens": input_tokens + output_tokens,
                        },
                    },
                )
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"done": True, "accumulated": accumulated, "elapsed": elapsed, "ttft_ms": ttft_ms},
                )
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, {"error": str(exc)})

    async with _llm_semaphore:
        logger.info("Starting stream | model=%s | rag=%s", req.model, bool(rag_context))
        loop.run_in_executor(None, _stream_sync)

        accumulated = ""
        elapsed = 0.0

        while True:
            item = await queue.get()

            if "token" in item:
                accumulated += item["token"]
                yield f"data: {json.dumps({'token': item['token']})}\n\n"

            elif "error" in item:
                logger.error("Ollama stream error: %s", item["error"])
                yield f"data: {json.dumps({'error': item['error']})}\n\n"
                break

            elif "done" in item:
                accumulated = item["accumulated"]
                elapsed = item["elapsed"]
                logger.info("Stream complete | model=%s | time=%.2fms | ttft=%.2fms",
                            req.model, elapsed, item.get("ttft_ms", 0))
                break

    try:
        data = _parse_llm_output(accumulated)
        result = _build_response(data, req.user_story)
        result_dict = result.model_dump()
        for tc in result_dict.get("test_cases") or []:
            yield f"data: {json.dumps({'case': tc})}\n\n"
        yield f"data: {json.dumps({'result': result_dict})}\n\n"
    except Exception as e:
        logger.error("Stream parse error | %s", str(e))
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


async def generate_test_cases(req: GenerateRequest) -> GenerateResponse:
    """
    Non-streaming generation. Called from within a root_trace() in the generate route.
    Creates child spans that attach to the parent trace automatically.
    """
    rag_context = ""
    if req.use_rag:
        try:
            from backend.services.rag_service import semantic_search
            with tracer.rag_span(req.user_story) as s:
                rag_context = semantic_search(req.user_story)
                tracer.update_span(
                    s,
                    output={"context_chars": len(rag_context), "has_context": bool(rag_context)},
                )
        except Exception as exc:
            logger.warning("RAG unavailable: %s", exc)

    cats = getattr(req, "categories", []) or []
    with tracer.prompt_span(req.tc_count, cats, len(rag_context)) as ps:
        prompt = _build_prompt(req, rag_context)
        tracer.update_span(ps, output={
            "prompt_chars": len(prompt),
            "prompt_tokens_est": tracer.estimate_tokens(prompt),
            "rag_chars": len(rag_context),
        })

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    num_predict = _calc_num_predict(req.tc_count, req.edge_count, req.bug_count)
    num_ctx     = max(OLLAMA_CONTEXT_SIZE, num_predict + 3000)
    options = {"temperature": req.temperature, "num_ctx": num_ctx, "top_p": 0.7, "num_predict": num_predict}

    async with _llm_semaphore:
        logger.info("Starting generation | model=%s | rag=%s", req.model, bool(rag_context))
        t0 = time.monotonic()

        loop = asyncio.get_running_loop()
        content = await loop.run_in_executor(
            None,
            lambda: _call_ollama_with_span(req.model, messages, options, prompt),
        )

        logger.info("Response received | model=%s | time=%.2fs", req.model, time.monotonic() - t0)

    data = _parse_llm_output(content)
    return _build_response(data, req.user_story)
