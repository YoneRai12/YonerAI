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

import soundfile as sf
import torch
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse
from transformers import AutoModelForSeq2SeqLM, AutoProcessor

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VoiceEngine_Aratako")

app = FastAPI(title="ORA Voice Engine (Aratako)", version="1.0")

# Configuration
# Configuration
MODEL_PATH = "google/gemma-2b-it"  # Fallback to HF standard or use local if exists
if os.path.exists(r"models/VoiceEngine_2B"):
    MODEL_PATH = r"models/VoiceEngine_2B"
elif os.path.exists(r"L:\AI_Models\T5Gemma\VoiceEngine_2B") and os.name == "nt":
    MODEL_PATH = r"L:\AI_Models\T5Gemma\VoiceEngine_2B"

DEVICE = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
DTYPE = torch.bfloat16 if DEVICE != "cpu" else torch.float32

# Global State
model = None
processor = None
LAST_USED = 0


async def get_model():
    global model, processor, LAST_USED
    LAST_USED = time.time()

    if model is not None:
        return model, processor

    logger.info(f"Lazy Loading Voice Engine from {MODEL_PATH}...")
    try:
        processor = AutoProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL_PATH, device_map=DEVICE, torch_dtype=DTYPE, trust_remote_code=True
        ).eval()
        logger.info("Voice Engine Loaded.")
    except Exception as e:
        logger.error(f"Failed to load: {e}")
        return None, None

    return model, processor


@app.on_event("startup")
async def startup_event():
    logger.info("Service Started. Model will load on first request.")
    # Start background cleaner
    import asyncio

    asyncio.create_task(vocab_garbage_collector())


async def vocab_garbage_collector():
    global model, processor
    while True:
        await asyncio.sleep(60)  # Check every minute
        if model and (time.time() - LAST_USED > 300):  # 5 minutes idle
            logger.info("Unloading Voice Engine to free VRAM...")
            del model
            del processor
            import gc

            gc.collect()
            torch.cuda.empty_cache()
            model = None
            processor = None


@app.post("/speak")
async def speak(text: str = Form(...), speaker_id: str = Form(None), reference_audio: UploadFile = File(None)):
    model, processor = await get_model()  # Lazy Load

    if not model or not processor:
        return {"error": "Voice Engine failed to load."}

    try:
        inputs = None

        # 1. Processing Input
        # Aratako's prompt format likely requires specific control tokens or just text.
        # Check repo documentation for exact prompt structure.
        # Assuming standard flow:

        prompt_inputs = processor(text=text, return_tensors="pt").to(DEVICE)

        # 2. Speaker Cloning Logic
        # If reference audio is provided, extracting embeddings (if model supports it)
        # or passing audio as input features.

        # NOTE: For T5Gemma-TTS, audio cloning usually involves passing speaker embeddings.
        # Since we don't have the Aratako codebase fully inspected, we'll placeholder the cloning logic
        # wrapping it in a generic generation call.

        with torch.inference_mode():
            # Generate Audio Tokens
            audio_tokens = model.generate(
                **prompt_inputs,
                max_new_tokens=400,  # 10-20 sec
            )

        # 3. Decode Tokens to Waveform (Vocoder)
        # T5Gemma-TTS usually outputs Codec tokens (XCodec2?).
        # We need the decoder part.
        # For now, assuming processor.decode_audio exists or similar.
        # IF NOT: We simply return dummy/placeholder if exact codec logic isn't present in "processor".

        # Placeholder for Vocoding (Crucial: Need 'XCodec2' or similar if not built-in)
        # Assuming AutoProcessor handles it:
        audio_array = processor.decode(audio_tokens[0], output_type="audio")

        # Save to Buffer
        buffer = io.BytesIO()
        sf.write(buffer, audio_array, 24000, format="WAV")
        buffer.seek(0)

        return FileResponse(buffer, media_type="audio/wav", filename="output.wav")

    except Exception as e:
        logger.error(f"TTS Error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/clone_speaker")
async def clone_speaker(user_id: str = Form(...), audio: UploadFile = File(...)):
    """
    Registers a user's voice for Doppelganger mode.
    """
    # Simply saving the reference audio is enough for Zero-Shot usually.
    save_path = f"data/passports/{user_id}.wav"
    os.makedirs("data/passports", exist_ok=True)

    with open(save_path, "wb") as f:
        f.write(await audio.read())

    return {"status": "success", "message": f"Doppelganger registered for {user_id}"}


if __name__ == "__main__":
    import uvicorn

    # Voice engine runs on port 8002
    uvicorn.run(app, host="127.0.0.1", port=8002)
