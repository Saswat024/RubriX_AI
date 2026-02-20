import google.generativeai as genai
import json
from typing import Dict
from .cfg_generator import CFG, cfg_to_dict
from . import config
from . import utils
from . import prompts
from cache import generate_cache_key, get_cached_response, set_cached_response

genai.configure(api_key=config.GOOGLE_API_KEY)


async def compare_cfgs(cfg1: CFG, cfg2: CFG, problem_analysis: dict) -> dict:
    """Compare two CFGs and determine which solution is better"""
    
    # Calculate basic structural metrics
    structural_metrics = {
        'cfg1': {
            'num_nodes': len(cfg1.nodes),
            'num_edges': len(cfg1.edges),
            'complexity': cfg1.complexity,
            'num_paths': cfg1.num_paths,
            'nesting_depth': cfg1.nesting_depth
        },
        'cfg2': {
            'num_nodes': len(cfg2.nodes),
            'num_edges': len(cfg2.edges),
            'complexity': cfg2.complexity,
            'num_paths': cfg2.num_paths,
            'nesting_depth': cfg2.nesting_depth
        }
    }
    
    system_prompt = prompts.COMPARE_CFGS_PROMPT

    cfg1_dict = cfg_to_dict(cfg1)
    cfg2_dict = cfg_to_dict(cfg2)

    # Check cache first
    cache_key = generate_cache_key(
        "compare_cfgs",
        json.dumps(cfg1_dict, sort_keys=True),
        json.dumps(cfg2_dict, sort_keys=True),
        json.dumps(problem_analysis, sort_keys=True),
    )
    cached = get_cached_response("compare_cfgs", cache_key)
    if cached is not None:
        return cached

    model = genai.GenerativeModel(config.GEMINI_MODEL)
    prompt = f"""{system_prompt}

Problem Analysis:
{json.dumps(problem_analysis, indent=2)}

Solution 1 CFG:
{json.dumps(cfg1_dict, indent=2)}

Solution 2 CFG:
{json.dumps(cfg2_dict, indent=2)}

Structural Metrics:
{json.dumps(structural_metrics, indent=2)}

Compare these solutions and determine which is better."""

    response = model.generate_content(prompt)
    print("Comparison response:", response.text)
    
    result = utils.parse_json_response(response.text)

    # Store in cache
    set_cached_response("compare_cfgs", cache_key, result)

    return result
