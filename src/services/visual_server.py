import io
import logging
import time

import torch
from fastapi import FastAPI, File, Form, UploadFile
from PIL import Image
from transformers import AutoModelForCausalLM, AutoProcessor

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VisualCortex")

app = FastAPI(title="ORA Visual Cortex", version="1.0")

# Configuration
MODEL_PATH = r"L:\AI_Models\T5Gemma\VisualCortex_4B"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16

# Global Model State
model = None
processor = None


@app.on_event("startup")
async def load_model():
    global model, processor
    try:
        logger.info(f"Loading Visual Cortex from {MODEL_PATH}...")
        start_time = time.time()

        processor = AutoProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH, device_map=DEVICE, torch_dtype=DTYPE, trust_remote_code=True
        ).eval()

        logger.info(f"Visual Cortex Loaded in {time.time() - start_time:.2f}s")
    except Exception as e:
        logger.error(f"Failed to load Visual Cortex: {e}")
        # Build dummy for testing if actual weights fail (e.g. during download)
        # model = "DUMMY"


@app.post("/analyze")
async def analyze_image(file: UploadFile = File(...), prompt: str = Form("Describe this image in detail.")):
    """
    Analyzes an image using T5Gemma 2 4B.
    """
    if not model or not processor:
        return {"error": "Visual Cortex model not loaded."}

    try:
        # Load Image
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data)).convert("RGB")

        # Prepare Inputs
        # Note: T5Gemma 2 usage might vary slightly based on "Aratako" vs "Google" implementation details.
        # Assuming standard Paligemma/Florence/T5Gemma prompting style if applicable.
        # For general multimodal:
        inputs = processor(text=prompt, images=image, return_tensors="pt").to(DEVICE)

        # Improvements: Add generation config for JSON/OCR if needed
        with torch.inference_mode():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False,  # Deterministic for OCR/Description
            )

        # Decode
        result_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

        # Specific T5Gemma Cleanup (Input echo removal often needed)
        if result_text.startswith(prompt):
            result_text = result_text[len(prompt) :].strip()

        return {"status": "success", "analysis": result_text}

    except Exception as e:
        logger.error(f"Inference Error: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn

    # visual cortex runs on port 8004
    uvicorn.run(app, host="127.0.0.1", port=8004)
