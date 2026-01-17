@echo off
echo [INFO] Starting vLLM (Instruct Mode)...
L:\ORADiscordBOT_Env\Scripts\python.exe -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-VL-32B-Instruct-AWQ --quantization awq --dtype half --gpu-memory-utilization 0.90 --max-model-len 2048 --enforce-eager --disable-custom-all-reduce --tensor-parallel-size 1 --port 8000 --trust-remote-code
pause
