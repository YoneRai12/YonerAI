
import transformers
print(f"Transformers Version: {transformers.__version__}")
print("Attributes starting with AutoModel:")
for attr in dir(transformers):
    if attr.startswith("AutoModel"):
        print(attr)
