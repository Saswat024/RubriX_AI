import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from cache import generate_cache_key, get_cached_response, set_cached_response, normalize_code

load_dotenv(override=True)
api_key = os.getenv("GOOGLE_API_KEY")
print(f"Pseudocode API Key loaded: {'YES' if api_key else 'NO'}")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")
genai.configure(api_key=api_key)


async def evaluate_pseudocode(code: str):
    """Evaluate pseudocode using gemini-2.5-flash-lite"""

    # Check cache first — normalize code to match trivially different inputs
    cache_key = generate_cache_key("evaluate_pseudocode", normalize_code(code))
    cached = get_cached_response("evaluate_pseudocode", cache_key)
    if cached is not None:
        return cached

    system_prompt = """You are an expert pseudocode evaluator with deep knowledge of algorithms, data structures, and software engineering best practices. Your task is to rigorously evaluate the provided pseudocode against specific criteria and return a structured assessment.:
Evaluation Criteria:-
Assess the pseudocode using these weighted rubrics (total: 100 points):
1. Correctness (50 points):
Does the logic accurately implement the intended algorithm or task?
Are all steps logically sound and in the correct sequence?
Would this pseudocode translate into working code without logical errors?
Are variable assignments, conditions, and operations correct?

2. Edge Case Handling (20 points):
Does it account for boundary conditions (empty inputs, single elements, maximum values)?
Does it validate inputs and handle invalid/unexpected data gracefully?
Are special cases like zero, null, negative values, or duplicates addressed?
Does it prevent potential runtime errors (division by zero, array out of bounds, etc.)?

3. Clarity (15 points):
Are variable and function names descriptive and meaningful?
Is the structure easy to follow with proper indentation and formatting?
Are control flow statements (if/else, loops) clearly organized?
Is the overall logic readable by someone unfamiliar with the code?

4. Complexity (15 points):
Is the time complexity appropriate for the problem?
Is the space complexity optimized or reasonable?
Are there unnecessary redundant operations or inefficient patterns?
Could the algorithm be simplified without sacrificing correctness?

Required Output Format
Return your evaluation exclusively as a valid JSON object with no additional text, markdown formatting, or explanation outside the JSON structure:
{
  "total_score": <integer 0-100>,
  "breakdown": [
    {
      "criterion": "Correctness",
      "score": <integer 0-50>,
      "max_score": 50,
      "feedback": "<specific explanation with examples from the pseudocode>"
    },
    {
      "criterion": "Edge Case Handling",
      "score": <integer 0-20>,
      "max_score": 20,
      "feedback": "<specific explanation with examples>"
    },
    {
      "criterion": "Clarity",
      "score": <integer 0-15>,
      "max_score": 15,
      "feedback": "<specific explanation with examples>"
    },
    {
      "criterion": "Complexity",
      "score": <integer 0-15>,
      "max_score": 15,
      "feedback": "<specific explanation with time/space complexity analysis>"
    }
  ],
  "feedback": [
    "<3-5 actionable feedback items as separate strings>"
  ]
}
Evaluation Guidelines

Be specific: Reference actual lines or patterns from the pseudocode in your feedback
Be objective: Base scores on observable qualities, not assumptions
Be actionable: In the feedback array, provide concrete suggestions for improvement
Use emojis consistently:

✅ Strengths or correct implementations
⚠️ Issues, errors, or weaknesses that need attention
💡 Suggestions for enhancements or optimizations


Important: Return ONLY the JSON object. Do not include any text before or after the JSON, no markdown code blocks, and no explanatory prose.
"""

    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    prompt = f"{system_prompt}\n\nEvaluate this pseudocode based on the rubrics:\n\n{code}"
    response = model.generate_content(prompt)
    print("Raw response:", response.text)
    result = json.loads(response.text.strip().replace('```json', '').replace('```', ''))

    # Store in cache
    set_cached_response("evaluate_pseudocode", cache_key, result)

    return result

