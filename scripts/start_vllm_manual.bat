@echo off
echo Starting vLLM in WSL...
wsl -d Ubuntu-22.04 nohup python3 -m vllm.entrypoints.openai.api_server --model mistralai/Pixtral-12B-2409 --max-model-len 8192 --enforce-eager --disable-custom-all-reduce --tensor-parallel-size 1 --port 8001 --trust-remote-code > vllm.log 2>&1 &
echo vLLM started on port 8001. Check vllm.log for details.
pause
