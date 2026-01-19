
import transformers

print(f"Transformers Version: {transformers.__version__}")
try:
    from transformers import AutoModelForTextToSpeech
    print("Direct Import: SUCCESS")
except ImportError:
    print("Direct Import: FAILED")

try:
    from transformers.models.auto import AutoModelForTextToSpeech
    print("Submodule Import: SUCCESS")
except ImportError:
    print("Submodule Import: FAILED")
