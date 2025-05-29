import json
import re
import ollama
from jsonschema import validate, ValidationError
import bleach
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from json_repair import repair_json

# Configure logging
logger = logging.getLogger(__name__)

ALLOWED_TAGS = ["p", "br", "ul", "li", "strong", "em", "b", "i", "h1", "h2", "h3", "ol"]
ALLOWED_ATTRIBUTES = {
    "*": ["class"],
    "a": ["href", "title"],
}


@dataclass
class LessonPlanConfig:
    """Configuration for lesson plan generation"""

    model_name: str = "gemma3:1b-it-qat"
    max_retries: int = 3
    timeout: int = 120
    temperature: float = 0.7


def sanitize_text(text: str) -> str:
    """Enhanced text sanitization with more allowed tags"""
    if not isinstance(text, str):
        return str(text)
    return bleach.clean(
        text, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True
    )


SCHEMA = {
    "type": "object",
    "required": [
        "objectives",
        "teaching_materials",
        "reference_materials",
        "introduction",
        "lesson_development",
        "conclusion",
        "recapitulation",
        "evaluation",
        "teacher_evaluation",
        "homework",
    ],
    "properties": {
        "objectives": {"type": "string", "minLength": 10, "maxLength": 2000},
        "teaching_materials": {
            "type": ["string", "object", "array"],
            "minLength": 5,
            "maxLength": 1000,
        },
        "reference_materials": {
            "type": ["string", "array"],
            "minLength": 5,
            "maxLength": 1000,
        },
        "introduction": {
            "type": ["string", "object"],
            "minLength": 20,
            "maxLength": 1500,
        },
        "lesson_development": {
            "type": ["string", "object"],
            "minLength": 50,
            "maxLength": 5000,
        },
        "conclusion": {"type": "string", "minLength": 20, "maxLength": 1500},
        "recapitulation": {"type": "string", "minLength": 10, "maxLength": 1000},
        "evaluation": {"type": "string", "minLength": 10, "maxLength": 1000},
        "teacher_evaluation": {"type": "string", "minLength": 10, "maxLength": 1000},
        "homework": {"type": "string", "minLength": 5, "maxLength": 1000},
    },
    "additionalProperties": False,
}


def clean_invalid_json_chars(content: str) -> str:
    logger.debug(f"Raw input content: {repr(content)}")
    content = content.replace("\ufeff", "").strip()
    patterns = [
        (r"```json\s*(.*?)\s*```", r"\1"),
        (r"```\s*(.*?)\s*```", r"\1"),
        (r"`(.*?)`", r"\1"),
    ]
    for pattern, replacement in patterns:
        if re.search(pattern, content, re.DOTALL):
            content = re.sub(pattern, replacement, content, flags=re.DOTALL).strip()
            break
    try:
        cleaned = repair_json(content)
        json.loads(cleaned)
        logger.debug(f"Cleaned content: {repr(cleaned)}")
        return cleaned.strip()
    except Exception as e:
        logger.error(f"JSON repair failed: {e}")
        raise ValueError(f"Unable to clean JSON: {e}")


def generate_lesson_plan(
    prompt: str, config: Optional[LessonPlanConfig] = None
) -> Dict[str, Any]:
    """Generate lesson plan with enhanced error handling, normalization, and retries"""
    if config is None:
        config = LessonPlanConfig()

    last_error = None

    for attempt in range(config.max_retries):
        try:
            logger.info(
                f"Generating lesson plan - attempt {attempt + 1}/{config.max_retries}"
            )
            response = ollama.chat(
                model=config.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": config.temperature, "timeout": config.timeout},
            )
            content = response["message"]["content"]
            logger.debug(f"Raw AI response: {repr(content)}")

            if not content or len(content.strip()) < 50:
                raise ValueError("AI returned insufficient content")

            clean_content = clean_invalid_json_chars(content)
            logger.debug(f"Cleaned JSON: {repr(clean_content)}")

            parsed = json.loads(clean_content)
            normalized = normalize_ai_response(parsed)
            logger.debug(f"Normalized JSON: {repr(normalized)}")

            validate(instance=normalized, schema=SCHEMA)
            logger.info("Successfully generated and validated lesson plan")
            return normalized

        except json.JSONDecodeError as je:
            last_error = je
            logger.warning(f"JSON decode error on attempt {attempt + 1}: {je}")
            logger.debug(f"Raw content: {repr(content)}")
            logger.debug(f"Cleaned content: {repr(clean_content)}")
        except ValidationError as ve:
            last_error = ve
            logger.warning(f"Schema validation failed on attempt {attempt + 1}: {ve}")
            logger.debug(f"Parsed JSON: {repr(parsed)}")
            logger.debug(
                f"Normalized JSON: {repr(normalized) if 'normalized' in locals() else 'Not normalized'}"
            )
        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")

        if attempt < config.max_retries - 1:
            import time

            time.sleep(2**attempt)  # Exponential backoff

    error_msg = (
        f"Failed to generate valid lesson plan after {config.max_retries} attempts"
    )
    logger.error(error_msg)
    raise ValueError(error_msg) from last_error


BASE_PROMPT = """
You are an experienced Zambian teacher with expertise in curriculum development.

Generate a lesson plan as a SINGLE VALID JSON object with exactly these fields:
{fields}

CRITICAL INSTRUCTIONS:
1. Return ONLY one valid JSON object, no extra text, markdown, or multiple objects.
2. Use standard ASCII double quotes (") only.
3. Use EXACT field names as listed (e.g., 'objectives', not 'objective').
4. All values must be strings, not objects or arrays. Combine nested content into a single string with spaces instead of newlines.
5. Ensure all string values are properly escaped and meet length requirements (e.g., objectives: 10-2000 characters).
6. Make content specific to Zambian educational context.
7. For "lesson_development", include step-by-step teaching activities, expected student responses, interaction methods, and assessment checkpoints as a single string.

Lesson Parameters:
{details}

Example JSON structure:
{{
  "objectives": "Students will understand the process of respiration.",
  "teaching_materials": "Chalkboard, markers, respiration diagram",
  "reference_materials": "Zambian Grade 8 Science Textbook",
  "introduction": "Discuss breathing with a Think-Pair-Share activity.",
  "lesson_development": "Step 1: Explain respiration (10 min). Step 2: Show diagram (15 min).",
  "conclusion": "Summarize the role of oxygen in respiration.",
  "recapitulation": "Ask students to explain respiration.",
  "evaluation": "Quiz on respiration components.",
  "teacher_evaluation": "Reflect on student engagement.",
  "homework": "Draw a respiration diagram."
}}
"""


def build_prompt(lesson_data: Dict[str, Any]) -> str:
    """Build enhanced prompt with better formatting"""
    required_fields = [
        "objectives",
        "teaching_materials",
        "reference_materials",
        "introduction",
        "lesson_development",
        "conclusion",
        "recapitulation",
        "evaluation",
        "teacher_evaluation",
        "homework",
    ]

    fields = "\n".join([f"  - {field}" for field in required_fields])

    details = []
    for key, value in lesson_data.items():
        if value:
            details.append(f"  - {key.replace('_', ' ').title()}: {value}")

    details_str = "\n".join(details)

    return BASE_PROMPT.format(fields=fields, details=details_str)


def normalize_ai_response(ai_response: Dict[str, Any]) -> Dict[str, str]:
    """Normalize AI response to match schema, flattening nested structures and mapping keys."""
    if not isinstance(ai_response, dict):
        logger.error(f"AI response is not a dictionary: {ai_response}")
        raise ValueError("AI response must be a dictionary")

    normalized = {}
    key_map = {
        "objective": "objectives",
        "objectives": "objectives",
        "learning_objectives": "objectives",
        "lesson_objectives": "objectives",
        "teaching_materials": "teaching_materials",
        "materials": "teaching_materials",
        "resources": "teaching_materials",
        "reference_materials": "reference_materials",
        "references": "reference_materials",
        "bibliography": "reference_materials",
        "introduction": "introduction",
        "lesson_development": "lesson_development",
        "development": "lesson_development",
        "main_lesson": "lesson_development",
        "conclusion": "conclusion",
        "summary": "conclusion",
        "recapulation": "recapitulation",
        "recapitulation": "recapitulation",
        "recap": "recapitulation",
        "review": "recapitulation",
        "evaluation": "evaluation",
        "assessment": "evaluation",
        "teacher_evaluation": "teacher_evaluation",
        "reflection": "teacher_evaluation",
        "homework": "homework",
        "assignment": "homework",
        "home_work": "homework",
    }

    def flatten_value(value: Any) -> str:
        """Convert nested structures or lists to a string."""
        if isinstance(value, (dict, list)):
            try:
                # Pretty-print nested structures as a string
                return json.dumps(value, ensure_ascii=False).replace("\n", " ").strip()
            except Exception as e:
                logger.warning(
                    f"Failed to serialize value to JSON: {value}, error: {e}"
                )
                return str(value).replace("\n", " ").strip()
        return str(value).replace("\n", " ").strip()

    # Map AI keys to schema keys and flatten values
    for ai_key, value in ai_response.items():
        model_key = key_map.get(ai_key.lower(), None)
        if model_key:
            normalized[model_key] = flatten_value(value)
        else:
            logger.warning(f"Unexpected key '{ai_key}' in AI response, ignoring")

    # Ensure all required fields are present
    required_fields = [
        "objectives",
        "teaching_materials",
        "reference_materials",
        "introduction",
        "lesson_development",
        "conclusion",
        "recapitulation",
        "evaluation",
        "teacher_evaluation",
        "homework",
    ]
    for field in required_fields:
        if field not in normalized:
            normalized[field] = ""
            logger.warning(f"Missing required field '{field}', setting to empty string")

    logger.debug(f"Normalized response: {normalized}")
    return normalized
