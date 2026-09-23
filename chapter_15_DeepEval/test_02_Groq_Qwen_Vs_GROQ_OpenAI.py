"""Compare two Groq models on the same question, scored by a judge.

    deepeval test run test_02_Groq_Qwen_Vs_GROQ_OpenAI.py

Flow:
  1. Send the question to each model under test.
  2. Capture the raw answer.
  3. Hand input + answer + context to DeepEval.
  4. openai/gpt-oss-120b as judge -> scores AnswerRelevancy + Hallucination.

A caveat the results depend on: gpt-oss-120b is both a contestant and the
judge, so one of the two answers is marked by its own model. Self-preference is
a measured effect in LLM-as-judge setups, not a hypothetical one. Read a narrow
gpt-oss win as no result; a gpt-oss *loss* is the trustworthy signal, because a
model rarely marks itself down by accident. Point the judge at an uninvolved
model to remove the doubt entirely.
"""

import os

import pytest
from dotenv import load_dotenv
from openai import OpenAI

from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric, HallucinationMetric
from deepeval.test_case import LLMTestCase

MODELS_UNDER_TEST = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b"]
JUDGE_MODEL = "openai/gpt-oss-120b"

load_dotenv()

# Groq speaks the OpenAI API, so the official openai SDK works unchanged: just
# point base_url at Groq. The key is read from LOCAL_MODEL_API_KEY, which is
# the name set-local-model uses for an OpenAI-compatible endpoint - not
# OPENAI_API_KEY, which deepeval reserves for real OpenAI. `deepeval diagnose`
# prints which name is winning if this ever goes wrong.
groq = OpenAI(
    api_key=os.environ["LOCAL_MODEL_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)

QUESTION = "What is 2+2? Reply with just the number."
GROUNDING = ["Basic arithmetic fact: 2 + 2 = 4"]


def llm_response(model: str, question: str) -> str:
    """Ask one model one question and return its raw answer text."""
    response = groq.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": question}],
        # temperature=0 keeps the answer stable so the score below is
        # reproducible. The judge is still non-deterministic; this only
        # pins the thing under test.
        temperature=0,
        # Required, not a nicety. Groq meters the output tokens a request
        # *could* produce, not what it does produce, and qwen3.8-27b's free
        # tier allows 1000 per minute. Left unset, Groq assumes the model's
        # default ceiling (~1062) and returns 429 before generating a token.
        max_tokens=256,
    )
    return (response.choices[0].message.content or "").strip()


@pytest.mark.parametrize("model", MODELS_UNDER_TEST)
def test_model_answers_without_hallucinating(model: str) -> None:
    # Called inside the test, not at module level. At module level this fires
    # during pytest collection, so a rate limit or an outage reads as a broken
    # file rather than a failing test.
    answer = llm_response(model, QUESTION)
    print(f"\n[Groq {model}] -> {answer!r}\n")

    case = LLMTestCase(
        input=QUESTION,
        actual_output=answer,
        expected_output="4",
        # HallucinationMetric scores actual_output against this grounding text.
        context=GROUNDING,
    )

    metrics = [
        AnswerRelevancyMetric(threshold=0.8, model=JUDGE_MODEL),
        # 0.7, not 0.3. DeepEval 4.x flipped this metric: 1 is now a pass and
        # threshold is the MINIMUM passing score, where it used to be the
        # maximum tolerated proportion of violations. Left at 0.3 the gate
        # passes almost anything, which is worse than having no gate.
        HallucinationMetric(threshold=0.7, model=JUDGE_MODEL),
    ]
    assert_test(case, metrics)
