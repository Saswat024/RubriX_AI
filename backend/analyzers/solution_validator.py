import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from analyzers import config
from cache import generate_cache_key, get_cached_response, set_cached_response

load_dotenv(override=True)
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")
genai.configure(api_key=api_key)


async def validate_solution_relevance(user_cfg: dict, problem_statement: str) -> dict:
    """Validate that the user's solution is relevant to the problem statement"""

    system_prompt = """You are an expert algorithm analyst. Your task is to determine if a user's solution (represented as a CFG) is attempting to solve the stated problem.

Analyze the CFG node labels, operations, and control flow to identify what algorithm the user implemented.

Common algorithm patterns to recognize:
- Factorial: multiplication loop/recursion, typically multiplying result by decreasing/increasing counter
- GCD (Greatest Common Divisor): modulo operations, Euclidean algorithm pattern, two inputs
- Fibonacci: addition pattern, two previous values tracking
- Sorting: comparison and swap operations, nested loops
- Search: comparison with target, binary division or linear scan
- Prime check: divisibility testing, loop up to sqrt(n)
- Sum/Average: accumulator pattern, single loop
- Palindrome: comparison from both ends, reverse checking

Return ONLY a valid JSON object:
{
  "is_relevant": true/false,
  "detected_algorithm": "name of algorithm detected in user's solution",
  "expected_algorithm": "algorithm required by problem statement",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation of why solution matches or doesn't match"
}

CRITICAL:
- If the detected algorithm is completely different from what's required, set is_relevant to false
- Minor variations in approach (iterative vs recursive) should still be considered relevant
- Focus on the core algorithm, not implementation details
- Be strict: GCD is NOT factorial, sorting is NOT searching, etc.
"""

    try:
        # Check cache first
        cache_key = generate_cache_key(
            "validate_solution_relevance",
            json.dumps(user_cfg, sort_keys=True),
            problem_statement,
        )
        cached = get_cached_response("validate_solution_relevance", cache_key)
        if cached is not None:
            return cached

        model = genai.GenerativeModel(config.GEMINI_MODEL)
        prompt = f"""{system_prompt}

Problem Statement:
{problem_statement}

User's CFG:
{json.dumps(user_cfg, indent=2)}

Determine if the user's solution is relevant to the problem."""

        response = model.generate_content(prompt)
        print("Solution validation response:", response.text)

        # Clean and parse response
        response_text = response.text.strip()
        response_text = response_text.replace("```json", "").replace("```", "").strip()

        result = json.loads(response_text)

        # Validate required fields
        if "is_relevant" not in result:
            result["is_relevant"] = True  # Default to true if unclear
        if "detected_algorithm" not in result:
            result["detected_algorithm"] = "unknown"
        if "expected_algorithm" not in result:
            result["expected_algorithm"] = "unknown"
        if "confidence" not in result:
            result["confidence"] = 0.5
        if "reasoning" not in result:
            result["reasoning"] = "Unable to determine"

        # Store in cache before returning
        set_cached_response("validate_solution_relevance", cache_key, result)

        return result

    except json.JSONDecodeError as e:
        print(f"JSON parsing error in validate_solution_relevance: {e}")
        print(f"Response text: {response.text}")
        # Default to allowing the solution if validation fails
        return {
            "is_relevant": True,
            "detected_algorithm": "unknown",
            "expected_algorithm": "unknown",
            "confidence": 0.0,
            "reasoning": "Validation error - defaulting to allow evaluation",
        }
    except Exception as e:
        print(f"Error in validate_solution_relevance: {e}")
        import traceback

        traceback.print_exc()
        raise
