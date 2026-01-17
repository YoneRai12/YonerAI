import logging
import sys
import traceback

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("VERIFY")

print("--- ORA BOT TTS VERIFICATION ---")

try:
    import transformers
    print(f"Transformers version: {transformers.__version__}")
    
    print("\n--- ENVIRONMENT STATUS ---")
    try:
        from transformers import AutoProcessor
        print("AutoProcessor: OK")
    except Exception:
        print("AutoProcessor: FAILED")
        traceback.print_exc()

    try:
        from transformers import AutoModelForTextToSpeech
        print("AutoModelForTextToSpeech: OK")
    except Exception:
        print("AutoModelForTextToSpeech: FAILED")
        traceback.print_exc()
            
    try:
        import accelerate
        print(f"Accelerate version: {accelerate.__version__}")
    except ImportError:
        print("Accelerate: MISSING")

    print("\n--- VERSION CHECK ---")
    if transformers.__version__.startswith("4.45") or transformers.__version__.startswith("4.46") or transformers.__version__.startswith("4.47"):
        print("Incompatibility Risk: HIGH (Versions 4.45-4.47 are problematic)")
    else:
        print("Incompatibility Risk: LOW")

except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    traceback.print_exc()

print("--- VERIFICATION END ---")
