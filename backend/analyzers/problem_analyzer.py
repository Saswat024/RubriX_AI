import google.generativeai as genai
import json
from . import config
from . import utils
from . import prompts
from cache import generate_cache_key, get_cached_response, set_cached_response

genai.configure(api_key=config.GOOGLE_API_KEY)


async def analyze_problem(problem_statement: str) -> dict:
    """Analyze problem statement to extract requirements and expected structure"""

    # Check cache first
    cache_key = generate_cache_key("analyze_problem", problem_statement)
    cached = get_cached_response("analyze_problem", cache_key)
    if cached is not None:
        return cached

    model = genai.GenerativeModel(config.GEMINI_MODEL)
    prompt = f"{prompts.ANALYZE_PROBLEM_PROMPT}\n\nProblem Statement:\n{problem_statement}"
    response = model.generate_content(prompt)
    print("Problem analysis response:", response.text)

    result = utils.parse_json_response(response.text)

    # Store in cache
    set_cached_response("analyze_problem", cache_key, result)

    return result
