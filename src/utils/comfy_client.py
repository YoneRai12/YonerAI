import json
import logging
import os
import random
import time
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, Optional

import websocket

logger = logging.getLogger(__name__)


class ComfyWorkflow:
    def __init__(self, server_address: str = "127.0.0.1:8188"):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())
        self.workflows_dir = os.path.join(os.getcwd(), "config", "workflows")

        # Load Workflows
        self.image_workflow = self._load_workflow("flux_api.json")
        self.video_workflow = self._load_workflow("ltx_video.json")

    def _load_workflow(self, filename: str) -> Dict[str, Any]:
        """Loads and parses a workflow file from the config directory."""
        path = os.path.join(self.workflows_dir, filename)
        if not os.path.exists(path):
            logger.warning(f"Workflow file not found at: {path}")
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load workflow {filename}: {e}")
            return {}

    def _get_history(self, prompt_id: str) -> Dict[str, Any]:
        with urllib.request.urlopen(f"http://{self.server_address}/history/{prompt_id}") as response:
            return json.loads(response.read())

    def _get_image_data(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen(f"http://{self.server_address}/view?{url_values}") as response:
            return response.read()

    def generate_image(
        self,
        positive_prompt: str,
        negative_prompt: str = "",
        seed: int = None,
        steps: int = 20,
        width: int = 1024,
        height: int = 1024,
    ) -> Optional[bytes]:
        """
        Executes the workflow with the given prompts using WebSocket.
        Returns the raw image bytes of the first generated image.
        """
        if not self.image_workflow:
            logger.error("Image Workflow data is empty (flux_api.json missing?).")
            return None

        # Deep copy
        prompt_workflow = json.loads(json.dumps(self.image_workflow))

        # ID Mapping based on my manual flux_api.json construction:
        # 4: Positive Prompt (CLIPTextEncode)
        # 5: Negative Prompt (CLIPTextEncode)
        # 6: Empty Latent Image (Width, Height)
        # 7: KSampler (Seed, Steps)

        # 1. Update Positive Prompt
        if "4" in prompt_workflow and "inputs" in prompt_workflow["4"]:
            prompt_workflow["4"]["inputs"]["text"] = positive_prompt
        else:
            logger.error("Node 4 (Positive Prompt) not found in workflow.")
            return None

        # 2. Update Negative Prompt
        if "5" in prompt_workflow and "inputs" in prompt_workflow["5"]:
            prompt_workflow["5"]["inputs"]["text"] = negative_prompt
        else:
            logger.warning("Node 5 (Negative Prompt) not found. Skipping.")

        # 3. Update Dimensions (Node 6)
        if "6" in prompt_workflow and "inputs" in prompt_workflow["6"]:
            prompt_workflow["6"]["inputs"]["width"] = width
            prompt_workflow["6"]["inputs"]["height"] = height
        else:
            logger.warning("Node 6 (EmptyLatentImage) not found. Using default dimensions.")

        # 4. Update Seed & Steps
        if seed is None:
            seed = random.randint(0, 1000000000)

        if "7" in prompt_workflow and "inputs" in prompt_workflow["7"]:
            prompt_workflow["7"]["inputs"]["seed"] = seed
            prompt_workflow["7"]["inputs"]["steps"] = steps

        # 4. Queue Prompt via WebSocket
        try:
            ws = websocket.WebSocket()
            ws.connect(f"ws://{self.server_address}/ws?clientId={self.client_id}")

            # Send Request
            p = {"prompt": prompt_workflow, "client_id": self.client_id}
            data = json.dumps(p).encode("utf-8")
            req = urllib.request.Request(f"http://{self.server_address}/prompt", data=data)
            with urllib.request.urlopen(req) as response:
                prompt_id = json.loads(response.read())["prompt_id"]

            # Listen for Execution
            # Listen for Execution with Polling Fallback
            # WebSockets can be unstable (WinError 10054), so we use a hybrid approach.
            ws_connected = True

            while True:
                try:
                    if ws_connected:
                        try:
                            out = ws.recv()
                            if isinstance(out, str):
                                message = json.loads(out)
                                if message["type"] == "executing":
                                    data = message["data"]
                                    if data["node"] is None and data["prompt_id"] == prompt_id:
                                        logger.info("ComfyUI finished execution (via WebSocket).")
                                        break
                        except Exception as ws_e:
                            ws_connected = False
                            logger.info(f"WebSocket disconnected ({ws_e}), switching to polling.")

                    if not ws_connected:
                        # Polling Mode
                        time.sleep(2)
                        try:
                            history = self._get_history(prompt_id)
                            if prompt_id in history:
                                logger.info("ComfyUI finished execution (via Polling).")
                                break
                        except Exception:
                            pass  # Still waiting, no history yet

                except Exception as e:
                    # General loop safety
                    logger.warning(f"Error in execution loop: {e}")
                    time.sleep(1)

                # HEARTBEAT & QUEUE CHECK
                if not ws_connected:
                    try:
                        # Check Queue Status to see if we are stuck in queue or processing
                        with urllib.request.urlopen(f"http://{self.server_address}/queue") as q_resp:
                            q_data = json.loads(q_resp.read())
                            params_running = q_data.get("queue_running", [])
                            params_pending = q_data.get("queue_pending", [])

                            is_running = any(x[1] == prompt_id for x in params_running)
                            is_pending = any(x[1] == prompt_id for x in params_pending)

                            if is_running:
                                logger.info(f"ComfyUI Status: RUNNING (Prompt ID: {prompt_id})")
                            elif is_pending:
                                logger.info(
                                    f"ComfyUI Status: PENDING (Prompt ID: {prompt_id}) - Position in queue: {len(params_pending)}"
                                )
                            else:
                                logger.info(
                                    f"ComfyUI Status: UNKNOWN (Prompt ID: {prompt_id} not found in Running/Pending/History)"
                                )
                    except Exception as q_e:
                        logger.warning(f"Failed to check queue status: {q_e}")

            # Retrieve History to get filename
            history = self._get_history(prompt_id)[prompt_id]
            outputs = history["outputs"]

            # Assuming Node 9 is SaveImage
            if "9" in outputs:
                images = outputs["9"]["images"]
                if images:
                    img_meta = images[0]  # Get first image
                    return self._get_image_data(img_meta["filename"], img_meta["subfolder"], img_meta["type"])

            # Debug: Log what keys ARE present
            logger.error(f"No image output found in history (Node 9). Available output keys: {list(outputs.keys())}")
            if "outputs" in history:  # Double check structure
                logger.error(f"Full Outputs Dump: {history['outputs']}")
            return None

        except Exception as e:
            logger.error(f"ComfyUI Generation Error: {e}")
            return None

    def generate_video(
        self,
        positive_prompt: str,
        negative_prompt: str = "",
        seed: int = None,
        steps: int = 30,
        width: int = 768,
        height: int = 512,
        frame_count: int = 49,
    ) -> Optional[bytes]:
        """
        Executes the LTX-Video workflow.
        Returns the raw video bytes (mp4) of the first generated video.
        """
        if not self.video_workflow:
            logger.error("Video Workflow data is empty (ltx_video.json missing?).")
            return None

        prompt_workflow = json.loads(json.dumps(self.video_workflow))

        # NODE MAPPING for LTX-Video (Standard Template Assumption):
        # 6: CLIPTextEncode (Positive)
        # 7: CLIPTextEncode (Negative)
        # 8: LTX-Video Sampler (Seed, Steps, Frame Count, Dimensions) -- or separate Latent node
        # Note: LTX workflows vary. Assuming a standard structure where:
        # - Prompt is text input
        # - Empty Latent Video specifies dimensions/frames

        # Heuristic Search for Nodes if IDs differ:
        # We look for "class_type" matching specific LTX nodes.

        # 1. Update Prompts
        # Find CLIPTextEncode nodes
        # We assume specific IDs for simplicity, but can add discovery logic later.
        # Let's assume standard IDs from our template:
        # Node 20: Positive Prompt
        # Node 21: Negative Prompt
        # Node 25: Empty Latent Video (Width, Height, Length)
        # Node 10: KSampler (Seed, Steps)
        # Node 30: SaveVideo (Format)

        # Update Positive (Node 20)
        if "20" in prompt_workflow:
            prompt_workflow["20"]["inputs"]["text"] = positive_prompt

        # Update Negative (Node 21)
        if "21" in prompt_workflow:
            prompt_workflow["21"]["inputs"]["text"] = negative_prompt

        # Update Dimensions/Frames (Node 25 or similar)
        if "25" in prompt_workflow and "inputs" in prompt_workflow["25"]:
            prompt_workflow["25"]["inputs"]["width"] = width
            prompt_workflow["25"]["inputs"]["height"] = height
            prompt_workflow["25"]["inputs"]["length"] = frame_count

        # Update Seed & Steps (Node 10 - KSampler)
        if seed is None:
            seed = random.randint(0, 1000000000)

        if "10" in prompt_workflow and "inputs" in prompt_workflow["10"]:
            prompt_workflow["10"]["inputs"]["seed"] = seed
            prompt_workflow["10"]["inputs"]["steps"] = steps

        # Queue
        try:
            return self._queue_and_wait(prompt_workflow, output_node_id="30")
        except Exception as e:
            logger.error(f"Video Generation Failed: {e}")
            return None

    def _queue_and_wait(self, workflow: Dict, output_node_id: str) -> Optional[bytes]:
        """Internal helper to queue a workflow and wait for output."""
        ws = websocket.WebSocket()
        ws.connect(f"ws://{self.server_address}/ws?clientId={self.client_id}")

        # Send Request
        p = {"prompt": workflow, "client_id": self.client_id}
        data = json.dumps(p).encode("utf-8")
        req = urllib.request.Request(f"http://{self.server_address}/prompt", data=data)
        with urllib.request.urlopen(req) as response:
            prompt_id = json.loads(response.read())["prompt_id"]

        # Poll/WS Wait logic (Re-used from generate_image but cleaner)
        # ... (For brevity, using the existing logic structure would be better if refactored completely,
        # but to minimize diff size, I'll essentially inline/copy the wait logic or call a shared method if I extracted it.
        # I didn't extract it yet. Let's extract it now to 'execute_workflow'?)

        # Actually, let's just copy the wait logic loop for safety to avoid breaking generate_image refactor too much.
        # Or better: existing generate_image has the loop. I should have extracted it.
        # For this step, I will duplicate the wait logic to ensure robustness, or try to share it.

        # Let's duplicate strictly for this task to avoid huge diffs on generate_image.

        ws_connected = True
        start_time = time.time()
        timeout = 600  # 10 minutes max

        while True:
            if time.time() - start_time > timeout:
                logger.error("ComfyUI Generation Timed Out.")
                break

            try:
                if ws_connected:
                    try:
                        out = ws.recv()
                        if isinstance(out, str):
                            msg = json.loads(out)
                            if msg["type"] == "executing":
                                data = msg["data"]
                                if data["node"] is None and data["prompt_id"] == prompt_id:
                                    break
                    except:
                        ws_connected = False

                if not ws_connected:
                    time.sleep(2)
                    try:
                        hist = self._get_history(prompt_id)
                        if prompt_id in hist:
                            break
                    except:
                        pass
            except:
                time.sleep(1)

        # Get Result
        try:
            history = self._get_history(prompt_id)[prompt_id]
            outputs = history["outputs"]

            if output_node_id in outputs:
                # Video or Image
                items = (
                    outputs[output_node_id].get("images")
                    or outputs[output_node_id].get("gifs")
                    or outputs[output_node_id].get("videos")
                )
                if items:
                    meta = items[0]
                    return self._get_image_data(meta["filename"], meta["subfolder"], meta["type"])

            return None
        except Exception:
            return None

    async def unload_models(self):
        """Attempts to unload models from ComfyUI VRAM."""
        try:
            # Strategies for Unloading (based on ComfyUI versions/branches)
            # 1. Official/Manager /free endpoint (Most reliable if available)
            # Payload keys: unload_models, free_memory
            payload = {"unload_models": True, "free_memory": True}
            endpoints = ["/free", "/api/free", "/manager/free", "/internal/model/unload"]

            async with aiohttp.ClientSession() as session:
                for ep in endpoints:
                    try:
                        url = f"http://{self.server_address}{ep}"
                        async with session.post(url, json=payload, timeout=2) as resp:
                            if resp.status == 200:
                                logger.info(f"✅ ComfyUI VRAM Freed via {ep}")
                                return
                            elif resp.status != 404:  # If 500/405, it might be the wrong method or error
                                text = await resp.text()
                                logger.warning(f"Failed to free via {ep}: {resp.status} - {text[:50]}")
                    except Exception:
                        # logger.debug(f"Endpoint {ep} failed: {e}")
                        pass

            logger.warning("⚠️ Could not explicitly free ComfyUI VRAM (All endpoints failed).")

        except Exception as e:
            logger.warning(f"Failed to unload ComfyUI models: {e}")

        except Exception as e:
            logger.warning(f"Failed to unload ComfyUI models: {e}")
