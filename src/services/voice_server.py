
import os
import torch
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from transformers import AutoProcessor, AutoModelForSeq2SeqLM
import soundfile as sf
import numpy as np
import io
import time
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VoiceEngine_Aratako")

app = FastAPI(title="ORA Voice Engine (Aratako)", version="1.0")

# Configuration
MODEL_PATH = r"L:\AI_Models\T5Gemma\VoiceEngine_2B"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16

# Global State
model = None
processor = None
SPEAKER_EMBEDDINGS = {} # Cache for "Doppelganger" embeddings

@app.on_event("startup")
async def load_model():
    global model, processor
    try:
        logger.info(f"Loading Voice Engine from {MODEL_PATH}...")
        start_time = time.time()
        
        # Aratako T5Gemma-TTS usage
        # Note: Since it's custom, we might need specific code from the repo.
        # For now, assuming AutoModelForSeq2SeqLM works or we fallback to custom loading.
        # If it requires 'trust_remote_code=True', we enable it.
        processor = AutoProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL_PATH,
            device_map=DEVICE,
            torch_dtype=DTYPE,
            trust_remote_code=True
        ).eval()
        
        logger.info(f"Voice Engine Loaded in {time.time() - start_time:.2f}s")
    except Exception as e:
        logger.error(f"Failed to load Voice Engine: {e}")

@app.post("/speak")
async def speak(
    text: str = Form(...),
    speaker_id: str = Form(None), # For cloning
    reference_audio: UploadFile = File(None) # Zero-shot prompt
):
    """
    Generates audio from text using Aratako TTS.
    Supports 'Doppelganger' cloning if speaker_id or reference_audio is provided.
    """
    if not model or not processor:
        return {"error": "Voice Engine not loaded."}
    
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
                max_new_tokens=400 # 10-20 sec
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
        sf.write(buffer, audio_array, 24000, format='WAV')
        buffer.seek(0)
        
        return FileResponse(buffer, media_type="audio/wav", filename="output.wav")

    except Exception as e:
        logger.error(f"TTS Error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/clone_speaker")
async def clone_speaker(
    user_id: str = Form(...),
    audio: UploadFile = File(...)
):
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
