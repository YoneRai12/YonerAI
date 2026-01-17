
try:
    from transformers import AutoModelForTextToSpeech
    print("SUCCESS: AutoModelForTextToSpeech imported.")
except ImportError:
    try:
        from transformers import AutoModelForTextToWaveform as AutoModelForTextToSpeech
        print("SUCCESS: AutoModelForTextToWaveform imported (as fallback).")
    except ImportError as e:
        print(f"FAILURE: Both imports failed. {e}")
        exit(1)
