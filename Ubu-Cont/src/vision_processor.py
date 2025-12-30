import os
import base64
import json
import logging
from PIL import Image
import io
import numpy as np
import openai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VisionProcessor:
    def __init__(self, api_key=None, model_name="qwen/qwen-2.5-vl-72b-instruct", **kwargs):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.model_name = model_name
        self.client = None
        
        if self.api_key:
            import httpx
            self.client = openai.OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.api_key,
                http_client=httpx.Client(proxy=None)
            )
        else:
            logger.warning("No OpenRouter API key provided. Vision features will strictly fail or mock.")

    def analyze(self, frame):
        """
        Analyze frame and return list of UI elements.
        frame: OpenCV BGR image (numpy array)
        """
        if frame is None or not self.client:
            return AnalysisResult([], 0)
            
        # Convert BGR (OpenCV) to RGB (PIL) -> JPEG bytes -> Base64
        image = Image.fromarray(frame[:, :, ::-1])
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=70) # Compress slightly for speed
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        try:
            # Prompt engineering for UI element detection
            # We ask the VLM to identify clickable elements and return a JSON list
            prompt = """
            Analyze this UI screenshot. Identify interactable elements (buttons, links, inputs).
            Return a JSON object with this structure:
            {
                "elements": [
                    {"label": "name", "box_2d": [ymin, xmin, ymax, xmax]}
                ],
                "scroll_position": 0.0
            }
            Coordinates should be normalized 0-1000.
            "label" should be short and descriptive (e.g. "Login Button", "Search Bar").
            """
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{img_str}"
                                }
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"} # Some models support this, others might need text parsing
            )
            
            content = response.choices[0].message.content
            logger.info(f"VLM Response: {content[:100]}...")
            
            # Simple parsing (assuming model returns JSON markdown or raw JSON)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                 content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content)
            
            elements = []
            width, height = image.size
            
            for item in data.get("elements", []):
                label = item.get("label", "unknown")
                # Normalize coordinates (ymin, xmin, ymax, xmax) 0-1000 -> absolute pixels
                # Be careful with coordinate order, varies by model. 
                # QwenVL usually uses [ymin, xmin, ymax, xmax] in 0-1000 space
                
                box = item.get("box_2d", [0,0,0,0])
                if len(box) == 4:
                    # Assuming [ymin, xmin, ymax, xmax]
                    y1, x1, y2, x2 = box
                    
                    # Convert to 0-1 float
                    y1 /= 1000.0
                    x1 /= 1000.0
                    y2 /= 1000.0
                    x2 /= 1000.0
                    
                    abs_x = x1 * width
                    abs_y = y1 * height
                    abs_w = (x2 - x1) * width
                    abs_h = (y2 - y1) * height
                    
                    elements.append(UIElement(
                        label=label,
                        confidence=1.0,
                        x=abs_x,
                        y=abs_y,
                        w=abs_w,
                        h=abs_h
                    ))
            
            scroll_pos = data.get("scroll_position", 0.0)
            return AnalysisResult(elements, scroll_pos)
            
        except Exception as e:
            logger.error(f"Vision API error: {e}")
            return AnalysisResult([], 0)

class AnalysisResult:
    def __init__(self, elements, scroll_position):
        self.elements = elements
        self.scroll_position = scroll_position

class UIElement:
    def __init__(self, label, confidence, x, y, w, h):
        self.label = label
        self.confidence = confidence
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.center_x = x + w/2
        self.center_y = y + h/2
