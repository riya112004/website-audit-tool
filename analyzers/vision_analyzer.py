import os
import json
import base64
import httpx

VISION_PROMPT = """Analyze this website screenshot strictly from a UI design perspective.

Evaluate:
1. Visual hierarchy
2. Typography
3. Color consistency
4. Spacing
5. Alignment
6. Component consistency
7. CTA visibility
8. Card design
9. Image quality
10. Overall visual polish

For every problem return a JSON array of objects with these fields:
- issue (string): Short issue name
- severity (string): critical/high/medium/low/info
- evidence (string): What you observed
- recommendation (string): How to fix

Return ONLY valid JSON array. Do not include any explanation outside the JSON.
Do not judge SEO or website functionality. Only analyze visible UI."""


def _get_api_config() -> dict:
    """Get Vision API config from environment variables.
    Supports OpenAI GPT-4V format. Returns {api_key, api_url, model} or empty dict."""
    api_key = os.environ.get("VISION_API_KEY", "")
    api_url = os.environ.get("VISION_API_URL", "https://api.openai.com/v1/chat/completions")
    model = os.environ.get("VISION_MODEL", "gpt-4o")
    if not api_key:
        return {}
    return {"api_key": api_key, "api_url": api_url, "model": model}


def _encode_image(image_path: str) -> str:
    """Encode image to base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _call_vision_api(image_path: str, config: dict) -> list[dict]:
    """Call Vision LLM API with screenshot. Returns list of findings."""
    b64_image = _encode_image(image_path)

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": config["model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64_image}",
                            "detail": "high",
                        },
                    },
                ],
            }
        ],
        "max_tokens": 2000,
        "temperature": 0.3,
    }

    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(config["api_url"], headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                if content.endswith("```"):
                    content = content[:-3]
            findings = json.loads(content)
            if isinstance(findings, list):
                return findings
            return []
    except Exception as e:
        print(f"[vision_analyzer] API error: {e}")
        return []


def analyze_visual(scan_id: int, pages: list[dict], ux_data: dict) -> list[dict]:
    """Analyze screenshots using Vision LLM. Returns list of findings.

    If VISION_API_KEY is not set, returns empty list (graceful degradation).
    """
    config = _get_api_config()
    if not config:
        print("[vision_analyzer] No VISION_API_KEY set, skipping visual analysis")
        return []

    findings = []

    pages_to_analyze = [
        p for p in pages
        if p.get("status_code") and 200 <= p["status_code"] < 400
    ][:5]

    for page in pages_to_analyze:
        page_data = ux_data.get(page["url"], {})
        screenshot_path = page_data.get("screenshot_path")

        if not screenshot_path or not os.path.exists(screenshot_path):
            continue

        vision_findings = _call_vision_api(screenshot_path, config)

        for vf in vision_findings:
            findings.append({
                "check_name": f"vision_{vf.get('issue', 'unknown').lower().replace(' ', '_')}",
                "severity": vf.get("severity", "info"),
                "message": f"{vf.get('issue', 'Visual issue')}: {vf.get('evidence', '')} — {page['url']}",
                "page_url": page["url"],
                "page_id": page["id"],
                "evidence": vf.get("evidence", ""),
                "recommendation": vf.get("recommendation", ""),
                "source": "vision_llm",
            })

    return findings
