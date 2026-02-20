import google.generativeai as genai
import json
from .cfg_generator import CFG, CFGNode, cfg_to_dict
from . import config
from . import utils
from . import prompts
from cache import generate_cache_key, get_cached_response, set_cached_response

genai.configure(api_key=config.GOOGLE_API_KEY)


def validate_canonical_cfg(result: dict) -> dict:
    """Validate and ensure canonical CFG has required fields"""
    if "nodes" not in result:
        result["nodes"] = []
    if "edges" not in result:
        result["edges"] = []
    if "complexity" not in result:
        result["complexity"] = 1
    if "num_paths" not in result:
        result["num_paths"] = 1
    if "nesting_depth" not in result:
        result["nesting_depth"] = 0
    if "time_complexity" not in result:
        result["time_complexity"] = "O(n)"
    if "space_complexity" not in result:
        result["space_complexity"] = "O(1)"
    if "canonical_patterns" not in result:
        result["canonical_patterns"] = []

    return result


def validate_similarity_result(result: dict) -> dict:
    """Validate and ensure similarity result has required fields"""
    if "total_score" not in result:
        result["total_score"] = 0

    if "breakdown" not in result:
        result["breakdown"] = {}

    # Ensure all breakdown categories exist
    default_categories = {
        "structural_similarity": {"score": 0, "feedback": "Not evaluated"},
        "control_flow_coverage": {"score": 0, "feedback": "Not evaluated"},
        "correctness": {"score": 0, "feedback": "Not evaluated"},
        "efficiency": {"score": 0, "feedback": "Not evaluated"},
    }

    for category, default_value in default_categories.items():
        if category not in result["breakdown"]:
            result["breakdown"][category] = default_value
        elif "score" not in result["breakdown"][category]:
            result["breakdown"][category]["score"] = 0
        elif "feedback" not in result["breakdown"][category]:
            result["breakdown"][category]["feedback"] = ""

    if "differences" not in result:
        result["differences"] = []
    if "missing_paths" not in result:
        result["missing_paths"] = []
    if "extra_paths" not in result:
        result["extra_paths"] = []
    if "recommendations" not in result:
        result["recommendations"] = []

    return result


async def canonicalize_cfg(cfg: CFG, problem_statement: str) -> dict:
    """Convert CFG to canonical base-level representation"""

    try:
        cfg_dict = cfg_to_dict(cfg)

        # Check cache first
        cache_key = generate_cache_key("canonicalize_cfg", json.dumps(cfg_dict, sort_keys=True), problem_statement)
        cached = get_cached_response("canonicalize_cfg", cache_key)
        if cached is not None:
            return cached

        model = genai.GenerativeModel(config.GEMINI_MODEL)
        prompt = f"""{prompts.CANONICALIZE_CFG_PROMPT}

Problem Statement:
{problem_statement}

Original CFG to Canonicalize:
{json.dumps(cfg_dict, indent=2)}

Generate the canonical base-level CFG that captures the essential algorithmic structure."""

        response = model.generate_content(prompt)
        print("Canonical CFG response:", response.text)

        # Clean and parse response
        result = utils.parse_json_response(response.text)

        # Validate and ensure required fields
        result = validate_canonical_cfg(result)

        # Store in cache
        set_cached_response("canonicalize_cfg", cache_key, result)

        return result

    except json.JSONDecodeError as e:
        print(f"JSON parsing error in canonicalize_cfg: {e}")
        print(f"Response text: {response.text}")
        # Return a minimal valid canonical CFG
        return {
            "nodes": cfg_dict.get("nodes", []),
            "edges": cfg_dict.get("edges", []),
            "complexity": cfg_dict.get("complexity", 1),
            "num_paths": cfg_dict.get("num_paths", 1),
            "nesting_depth": cfg_dict.get("nesting_depth", 0),
            "time_complexity": "O(n)",
            "space_complexity": "O(1)",
            "canonical_patterns": ["unknown"],
        }
    except Exception as e:
        print(f"Error in canonicalize_cfg: {e}")
        import traceback

        traceback.print_exc()
        raise


async def calculate_cfg_similarity(user_cfg: dict, reference_cfg: dict, problem_statement: str = None) -> dict:
    """Calculate structural similarity between user CFG and reference CFG"""

    # Check cache first
    cache_key = generate_cache_key(
        "calculate_cfg_similarity",
        json.dumps(user_cfg, sort_keys=True),
        json.dumps(reference_cfg, sort_keys=True),
        str(problem_statement),
    )
    cached = get_cached_response("calculate_cfg_similarity", cache_key)
    if cached is not None:
        return cached

    try:
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        problem_context = f"\n\nProblem Statement:\n{problem_statement}\n" if problem_statement else ""
        prompt = f"""{prompts.CALCULATE_SIMILARITY_PROMPT}
{problem_context}
Reference CFG (canonical base-level):
{json.dumps(reference_cfg, indent=2)}

User's CFG:
{json.dumps(user_cfg, indent=2)}

FIRST: Verify the user's solution is relevant to the problem. If not, return score 0 with explanation.
THEN: Evaluate how well the user's solution matches the canonical structure."""

        response = model.generate_content(prompt)
        print("Similarity calculation response:", response.text)

        # Clean and parse response
        result = utils.parse_json_response(response.text)

        # Validate and ensure required fields
        result = validate_similarity_result(result)

        # Store in cache
        set_cached_response("calculate_cfg_similarity", cache_key, result)

        return result

    except json.JSONDecodeError as e:
        print(f"JSON parsing error in calculate_cfg_similarity: {e}")
        print(f"Response text: {response.text}")
        # Return a default similarity result
        return {
            "total_score": 50,
            "breakdown": {
                "structural_similarity": {
                    "score": 20,
                    "feedback": "Unable to evaluate due to parsing error",
                },
                "control_flow_coverage": {
                    "score": 15,
                    "feedback": "Unable to evaluate due to parsing error",
                },
                "correctness": {
                    "score": 10,
                    "feedback": "Unable to evaluate due to parsing error",
                },
                "efficiency": {
                    "score": 5,
                    "feedback": "Unable to evaluate due to parsing error",
                },
            },
            "differences": ["Evaluation incomplete due to technical error"],
            "missing_paths": [],
            "extra_paths": [],
            "recommendations": ["Please try submitting again"],
        }
    except Exception as e:
        print(f"Error in calculate_cfg_similarity: {e}")
        import traceback

        traceback.print_exc()
        raise
