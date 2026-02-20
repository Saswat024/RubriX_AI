import google.generativeai as genai
import os
import json
import base64
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
from cache import generate_cache_key, get_cached_response, set_cached_response

load_dotenv(override=True)
api_key = os.getenv("GOOGLE_API_KEY")
print(f"Flowchart API Key loaded: {'YES' if api_key else 'NO'}")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")
genai.configure(api_key=api_key)


async def evaluate_flowchart(base64_image: str):
    """Evaluate flowchart using gemini-2.5-flash-lite with image input"""

    # Check cache first
    cache_key = generate_cache_key("evaluate_flowchart", base64_image)
    cached = get_cached_response("evaluate_flowchart", cache_key)
    if cached is not None:
        return cached

    system_prompt = """You are an expert flowchart evaluator with extensive knowledge of process modeling, algorithmic representation, and standard flowchart conventions (ISO 5807 and related standards). Your task is to analyze the uploaded flowchart image and provide a comprehensive, objective evaluation.
Evaluation Criteria
Assess the flowchart using these weighted rubrics (total: 100 points):

1. Start/End Presence (10 points):
Does the flowchart have a clearly marked start node?
Does it have a clearly marked end node (or multiple end nodes if appropriate)?
Are start/end nodes in the correct shape (rounded rectangles/ovals/stadium shapes)?
Are they labeled appropriately (e.g., "Start", "Begin", "End", "Stop")?

2. Decision Nodes (30 points):
Are all decision points represented using diamond shapes?
Does each decision contain a clear question or condition?
Are all branches properly labeled (e.g., "Yes/No", "True/False", specific conditions)?
Do decision diamonds have exactly two or more exit paths?
Are the branch labels positioned clearly near the arrows?

3. Completeness (30 points):
Does the flowchart capture all essential steps of the process or algorithm?
Are there any logical gaps or missing connections between steps?
Does every process lead to a subsequent action or termination?
Are there any dead ends or orphaned nodes without connections?
Does the logic flow cover all possible paths from start to end?

4. Flow Direction (20 points):
Does the flow follow a consistent direction (top-to-bottom or left-to-right preferred)?
Are arrows clearly drawn and pointing in the correct direction?
Are all shapes properly connected (no floating nodes)?
Does the visual layout avoid crossing lines where possible?
Is the flow easy to trace visually from start to end?

5. Label Clarity (10 points):
Is all text legible and appropriately sized?
Are process descriptions clear and concise?
Do labels use consistent terminology and style?
Are standard flowchart symbols used correctly (rectangles for processes, parallelograms for input/output, etc.)?

Required Output Format:-
Return your evaluation exclusively as a valid JSON object. Do not include any text, explanations, or markdown formatting outside the JSON structure:

Output Format:-
Return only a valid JSON object (no additional explanation or commentary) in this exact structure:
{
  "total_score": <integer 0-100>,
  "breakdown": [
    {
      "criterion": "Start/End Presence",
      "score": <integer 0-10>,
      "max_score": 10,
      "feedback": "<specific observations about start/end nodes in the image>"
    },
    {
      "criterion": "Decision Nodes",
      "score": <integer 0-30>,
      "max_score": 30,
      "feedback": "<specific observations about decision diamonds and branches>"
    },
    {
      "criterion": "Completeness",
      "score": <integer 0-30>,
      "max_score": 30,
      "feedback": "<specific observations about logic gaps or missing steps>"
    },
    {
      "criterion": "Flow Direction",
      "score": <integer 0-20>,
      "max_score": 20,
      "feedback": "<specific observations about arrow directions and layout>"
    },
    {
      "criterion": "Label Clarity",
      "score": <integer 0-10>,
      "max_score": 10,
      "feedback": "<specific observations about text readability and symbol usage>"
    }
  ],
  "feedback": [
    "<3-5 actionable feedback items as separate strings>"
  ]
}

Evaluation Guidelines:
Analyze the actual image carefully: Base all assessments on what you can visually observe in the uploaded flowchart
Be specific: Reference particular elements you can see (e.g., "the decision node at the top", "missing label on the right branch")
Be objective: Score based on standard flowchart conventions, not subjective preferences
Be actionable: Provide concrete suggestions that would improve the flowchart

Use emojis consistently:
✅ Correct implementations or strong elements present in the flowchart
⚠️ Errors, missing elements, or convention violations
💡 Suggestions for improvements or enhancements

Important Notes:
If the image quality is poor or elements are unclear, note this in your feedback but still provide your best assessment
Consider the context: a simple process may naturally have fewer decision nodes than a complex algorithm
Ensure your JSON is valid with proper escaping of special characters in text fields

Critical: Return ONLY the JSON object with no surrounding text, markdown code blocks, or explanatory comments.
"""

    # Decode base64 image
    image_data = base64_image.split(',')[1] if ',' in base64_image else base64_image
    image_bytes = base64.b64decode(image_data)
    image = Image.open(BytesIO(image_bytes))

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    model = genai.GenerativeModel(model_name)
    prompt = f"{system_prompt}\n\nEvaluate this flowchart based on the rubrics. Provide detailed scoring and feedback."
    response = model.generate_content([prompt, image])
    print("Raw response:", response.text)
    result = json.loads(response.text.strip().replace('```json', '').replace('```', ''))

    # Store in cache
    set_cached_response("evaluate_flowchart", cache_key, result)

    return result
