import json
import uuid
import websocket
import urllib.request
import urllib.parse
import random
import os
import io
import asyncio
import logging
from typing import Optional, Dict, List, Any

import time
import logging

logger = logging.getLogger(__name__)


class ComfyWorkflow:
    def __init__(self, server_address: str = "127.0.0.1:8188"):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())
        self.workflow_path = os.path.join(os.getcwd(), "flux_api.json")
        self.workflow_data = self._load_workflow()

    def _load_workflow(self) -> Dict[str, Any]:
        """Loads and parses the flux_api.json workflow."""
        if not os.path.exists(self.workflow_path):
            logger.error(f"Workflow file not found at: {self.workflow_path}")
            return {}
        try:
            with open(self.workflow_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load workflow: {e}")
            return {}

    def _get_history(self, prompt_id: str) -> Dict[str, Any]:
        with urllib.request.urlopen(f"http://{self.server_address}/history/{prompt_id}") as response:
            return json.loads(response.read())

    def _get_image_data(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen(f"http://{self.server_address}/view?{url_values}") as response:
            return response.read()

    def generate_image(self, positive_prompt: str, negative_prompt: str = "", seed: int = None, steps: int = 20) -> Optional[bytes]:
        """
        Executes the workflow with the given prompts using WebSocket.
        Returns the raw image bytes of the first generated image.
        """
        if not self.workflow_data:
            logger.error("Workflow data is empty.")
            return None

        # Deep copy to avoid mutating the base template permanently
        prompt_workflow = json.loads(json.dumps(self.workflow_data))

        # ID Mapping based on my manual flux_api.json construction:
        # 4: Positive Prompt (CLIPTextEncode)
        # 5: Negative Prompt (CLIPTextEncode)
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

        # 3. Update Seed & Steps
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
            data = json.dumps(p).encode('utf-8')
            req = urllib.request.Request(f"http://{self.server_address}/prompt", data=data)
            with urllib.request.urlopen(req) as response:
                 prompt_id = json.loads(response.read())['prompt_id']

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
                                if message['type'] == 'executing':
                                    data = message['data']
                                    if data['node'] is None and data['prompt_id'] == prompt_id:
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
                            pass # Still waiting, no history yet
                            
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
                            params_running = q_data.get('queue_running', [])
                            params_pending = q_data.get('queue_pending', [])
                            
                            is_running = any(x[1] == prompt_id for x in params_running)
                            is_pending = any(x[1] == prompt_id for x in params_pending)
                            
                            if is_running:
                                logger.info(f"ComfyUI Status: RUNNING (Prompt ID: {prompt_id})")
                            elif is_pending:
                                logger.info(f"ComfyUI Status: PENDING (Prompt ID: {prompt_id}) - Position in queue: {len(params_pending)}")
                            else:
                                logger.info(f"ComfyUI Status: UNKNOWN (Prompt ID: {prompt_id} not found in Running/Pending/History)")
                    except Exception as q_e:
                        logger.warning(f"Failed to check queue status: {q_e}")
            
            # Retrieve History to get filename
            history = self._get_history(prompt_id)[prompt_id]
            outputs = history['outputs']
            
            # Assuming Node 9 is SaveImage
            if "9" in outputs:
                images = outputs["9"]["images"]
                if images:
                    img_meta = images[0] # Get first image
                    return self._get_image_data(img_meta['filename'], img_meta['subfolder'], img_meta['type'])
            
            # Debug: Log what keys ARE present
            logger.error(f"No image output found in history (Node 9). Available output keys: {list(outputs.keys())}")
            if "outputs" in history: # Double check structure
                 logger.error(f"Full Outputs Dump: {history['outputs']}")
            return None

        except Exception as e:
            logger.error(f"ComfyUI Generation Error: {e}")
            return None
