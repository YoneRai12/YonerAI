import time
import sys
import os
import contextlib
import io

# Add project root to sys.path
sys.path.append(os.getcwd())

def benchmark_import(module_name):
    start = time.time()
    try:
        # Redirect stdout/stderr to suppress library noise
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            __import__(module_name)
    except Exception as e:
        print(f"Error importing {module_name}: {e}")
        return
    end = time.time()
    print(f"Import {module_name}: {end - start:.4f} seconds")

if __name__ == "__main__":
    print("--- Benchmark Start ---")
    benchmark_import("aiohttp")
    benchmark_import("src.utils.llm_client")
    benchmark_import("src.cogs.tools.registry")
    benchmark_import("src.cogs.handlers.tool_selector")
    benchmark_import("src.cogs.handlers.chat_handler")
    benchmark_import("src.cogs.tools.tool_handler") 
    print("--- Benchmark End ---")
