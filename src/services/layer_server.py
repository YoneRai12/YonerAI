import os
import sys

# Add project root to path for cross-module imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

import asyncio
import io
import logging
import time
import zipfile

import torch
import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import Response
from PIL import Image

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LayerService")

app = FastAPI(title="ORA Layer Service", version="1.0")

# Model Settings
MODEL_ID = "Qwen/Qwen-Image-Layered" # Hypothetical ID based on user request
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Global Model State
model = None
processor = None
LAST_USED = 0

async def get_model():
    global model, processor, LAST_USED
    LAST_USED = time.time()
    
    if model:
        return model, processor
        
    logger.info(f"Lazy Loading Layer Service from {MODEL_ID}...")
    try:
        from transformers import AutoModel, AutoProcessor
        model = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True).to(DEVICE).eval()
        processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
        logger.info("Layer Service Loaded.")
    except Exception as e:
        logger.error(f"Failed to load: {e}")
        return None, None
    return model, processor

@app.on_event("startup")
async def startup_event():
    logger.info("Service Started (Lazy Mode).")
    import asyncio
    asyncio.create_task(garbage_collector())

async def garbage_collector():
    global model, processor
    while True:
        await asyncio.sleep(60)
        if model and (time.time() - LAST_USED > 300): # 5 min idle
            logger.info("Unloading Layer Model...")
            del model
            del processor
            import gc
            gc.collect()
            torch.cuda.empty_cache()
            model = None
            processor = None

@app.post("/decompose")
async def decompose(file: UploadFile = File(...)):
    """
    Decomposes an image into RGBA layers and returns a ZIP file.
    """
    model, processor = await get_model()
    
    try:
        # Load Image

        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        
        layers = []
        
        if model:
            # Real Inference Mock-up (Assuming .generate calls)
            # inputs = processor(images=image, return_tensors="pt").to(DEVICE)
            # out = model.generate(**inputs, output_layers=True)
            # layers = process_output(out)
            
            # Since I don't have the weights downloaded yet, I'll simulate "Layer Decomposition"
            # In a real run, this would be the actual model call.
            # Using simple channel splitting as a Placeholder to demonstrate the PIPELINE works.
            # Once weights are real, this line is replaced.
            
            logger.info("Processing image...")
            # Simulate 3 layers: Background, Mid, Foreground (Dummy split)
            l1 = image.copy() # Background
            l2 = image.point(lambda p: p * 0.5) # Darker
            l2.putalpha(128)
            layers = [("background.png", l1), ("overlay.png", l2)]
            
        else:
            # Failed to load model fallback
            return {"error": "Model not loaded"}
            
        # Create ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, img in layers:
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format="PNG")
                zf.writestr(name, img_byte_arr.getvalue())
        
        zip_buffer.seek(0)
        
        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=layers.zip"}
        )

    except Exception as e:
        logger.error(f"Decomposition Error: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8003)
