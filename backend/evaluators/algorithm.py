import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from cache import generate_cache_key, get_cached_response, set_cached_response, normalize_code

load_dotenv(override=True)
api_key = os.getenv("GOOGLE_API_KEY")
print(f"Algorithm API Key loaded: {'YES' if api_key else 'NO'}")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")
genai.configure(api_key=api_key)


async def evaluate_algorithm(text: str, eval_type: str = "algorithm"):
    """Evaluate algorithm/pseudocode from parsed documents using gemini-2.5-flash"""

    # Check cache first — normalize code to match trivially different inputs
    cache_key = generate_cache_key("evaluate_algorithm", normalize_code(text), eval_type)
    cached = get_cached_response("evaluate_algorithm", cache_key)
    if cached is not None:
        return cached

    system_prompt = """You are an expert algorithm and computational thinking evaluator with deep expertise in:
- Algorithm design and analysis
- Data structures and their applications
- Computational complexity (time and space)
- Software engineering best practices
- Multiple programming paradigms and pseudocode conventions

Your task is to perform a comprehensive, language-agnostic evaluation of the provided algorithm or pseudocode.

Evaluation Criteria (Total: 100 points):

1. Correctness & Logic (35 points):
   - Does the algorithm solve the stated problem correctly?
   - Are all steps logically sound and properly sequenced?
   - Would this translate to working code without logical errors?
   - Are loop invariants and preconditions/postconditions satisfied?
   - Does it handle all required functionality?

2. Edge Case Handling & Robustness (20 points):
   - Boundary conditions (empty inputs, single elements, maximum/minimum values)
   - Input validation and error handling
   - Special cases (null, zero, negative, duplicates, overflow)
   - Prevention of runtime errors (division by zero, out of bounds, null pointer)
   - Graceful degradation for unexpected inputs

3. Clarity & Documentation (15 points):
   - Descriptive variable and function names
   - Clear structure with proper indentation
   - Logical flow that's easy to follow
   - Comments explaining non-obvious logic
   - Consistency in naming conventions and style

4. Algorithm Efficiency (20 points):
   - Time complexity analysis (Big O notation)
   - Space complexity analysis
   - Optimization opportunities identified
   - Appropriate data structure selection
   - Avoidance of redundant operations

5. Best Practices & Design (10 points):
   - Modularity and separation of concerns
   - Code reusability and maintainability
   - Adherence to SOLID principles where applicable
   - Appropriate abstraction levels
   - Scalability considerations

Required Output Format:
Return ONLY a valid JSON object with this exact structure:

{
  "total_score": <integer 0-100>,
  "breakdown": [
    {
      "criterion": "Correctness & Logic",
      "score": <integer 0-35>,
      "max_score": 35,
      "feedback": "<specific analysis with examples from the submission>"
    },
    {
      "criterion": "Edge Case Handling & Robustness",
      "score": <integer 0-20>,
      "max_score": 20,
      "feedback": "<specific analysis with examples>"
    },
    {
      "criterion": "Clarity & Documentation",
      "score": <integer 0-15>,
      "max_score": 15,
      "feedback": "<specific analysis with examples>"
    },
    {
      "criterion": "Algorithm Efficiency",
      "score": <integer 0-20>,
      "max_score": 20,
      "feedback": "<time/space complexity analysis with Big O notation>"
    },
    {
      "criterion": "Best Practices & Design",
      "score": <integer 0-10>,
      "max_score": 10,
      "feedback": "<design quality assessment>"
    }
  ],
  "feedback": [
    "<actionable improvement suggestions as separate strings, 4-6 items>"
  ],
  "complexity_analysis": {
    "time_complexity": "<Big O notation with explanation>",
    "space_complexity": "<Big O notation with explanation>",
    "optimization_suggestions": ["<suggestion 1>", "<suggestion 2>"]
  }
}

Evaluation Guidelines:
- Be language-agnostic: Evaluate logic, not syntax of any specific language
- Be specific: Reference actual patterns and logic from the submission
- Be objective: Base scores on observable qualities
- Be actionable: Provide concrete, implementable suggestions
- Use emojis consistently:
  ✅ Strengths or correct implementations
  ⚠️ Issues, errors, or areas needing attention
  💡 Optimization suggestions and enhancements
  🔍 Complexity analysis insights

CRITICAL: Return ONLY the JSON object. No markdown, no code blocks, no explanatory text before or after.
"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"{system_prompt}\n\nEvaluate this {eval_type}:\n\n{text}"
    response = model.generate_content(prompt)
    print("Raw response:", response.text)
    
    # Clean the response
    cleaned_text = response.text.strip()
    cleaned_text = cleaned_text.replace('```json', '').replace('```', '')
    result = json.loads(cleaned_text)

    # Store in cache
    set_cached_response("evaluate_algorithm", cache_key, result)

    return result
