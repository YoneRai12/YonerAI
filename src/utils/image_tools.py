"""Utility helpers for image classification and OCR."""

from __future__ import annotations

import io
import logging
import os

from PIL import Image

try:
    import pytesseract
except ImportError:  # pragma: no cover - optional dependency
    pytesseract = None  # type: ignore

import numpy as np

logger = logging.getLogger(__name__)


def classify_image(data: bytes) -> str:
    """Return a simple colour-based classification label for the image."""

    with Image.open(io.BytesIO(data)) as img:
        image = img.convert("RGB")
        array = np.array(image)

    avg_color = array.mean(axis=(0, 1))
    red, green, blue = avg_color
    dominant = max((red, "赤系"), (green, "緑系"), (blue, "青系"), key=lambda item: item[0])[1]
    brightness = float(array.mean())
    mood = "明るい" if brightness > 180 else "落ち着いた" if brightness > 100 else "暗め"
    width, height = image.size
    aspect: float = width / height if height else 1
    orientation = "横長" if aspect > 1.2 else "縦長" if aspect < 0.8 else "ほぼ正方形"
    return f"推定カテゴリ: {dominant} / 雰囲気: {mood} / 形状: {orientation}"


def preprocess_image_for_ocr(data: bytes) -> list[Image.Image]:
    """
    Generate multiple preprocessed versions of the image for OCR.
    Returns a list of PIL Images (Original, Grayscale, Thresholded, etc.)
    """
    images = []

    # 1. Original (PIL)
    try:
        original = Image.open(io.BytesIO(data)).convert("RGB")
        images.append(original)
    except Exception:
        return []

    # Try to use OpenCV for advanced processing
    try:
        import cv2

        # Convert bytes to numpy array
        nparr = np.frombuffer(data, np.uint8)
        img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img_cv is None:
            raise ValueError("Failed to decode image with OpenCV")

        # Convert to Grayscale
        gray_cv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        # 2. Rescaled (x2) + Grayscale
        # Scaling up helps with small text
        scaled = cv2.resize(gray_cv, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)  # type: ignore
        images.append(Image.fromarray(scaled))

        # 3. Adaptive Thresholding (Gaussian) - Good for shadows/handwriting
        # Block size 11, C=2
        thresh_gauss = cv2.adaptiveThreshold(scaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        images.append(Image.fromarray(thresh_gauss))

        # 4. Denoised + Thresholding
        denoised = cv2.fastNlMeansDenoising(gray_cv, None, 10, 7, 21)
        scaled_denoised = cv2.resize(denoised, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)  # type: ignore
        thresh_denoised = cv2.adaptiveThreshold(
            scaled_denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        images.append(Image.fromarray(thresh_denoised))

    except ImportError:
        logger.warning("OpenCV not found. Using basic PIL preprocessing.")
        # Fallback: Basic PIL processing
        gray_pil = original.convert("L")
        # Resize x2
        width, height = gray_pil.size
        scaled = gray_pil.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
        images.append(scaled)

        # Simple Binarization
        # threshold = 128
        # binarized = scaled.point(lambda p: 255 if p > threshold else 0)
        # images.append(binarized)

    except Exception as e:
        logger.warning(f"OpenCV preprocessing failed: {e}")

    return images


def ocr_image(data: bytes) -> str:
    """Extract text using pytesseract with advanced preprocessing fallback."""
    logger.info("Starting local OCR (Tesseract)...")

    if pytesseract is None:
        raise RuntimeError("pytesseract がインストールされていません。")

    # Set Tesseract path if not in PATH
    tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        tessdata_dir = os.path.join(os.path.dirname(tesseract_path), "tessdata")
        if os.path.exists(tessdata_dir):
            os.environ["TESSDATA_PREFIX"] = tessdata_dir

    # Generate candidate images
    candidates = preprocess_image_for_ocr(data)
    if not candidates:
        return "画像の読み込みに失敗しました。"

    best_text = ""
    max_len = 0

    # Try each candidate image
    for i, img in enumerate(candidates):
        try:
            # Check available languages
            try:
                langs = pytesseract.get_languages(config="")
                if "jpn" not in langs:
                    logger.warning("Japanese language data (jpn) not found in Tesseract. OCR content may be garbage.")
                    # Fallback to eng but warn
            except Exception:
                pass

            configs = [
                r"--oem 3 --psm 6 -l jpn+eng",  # Assume block of text
                r"--oem 3 --psm 3 -l jpn+eng",  # Auto seg
                r"--oem 3 --psm 11 -l jpn+eng",  # Sparse
                r"--oem 3 --psm 6 -l jpn",  # Japanese ONLY (force)
            ]

            for config in configs:
                try:
                    text = pytesseract.image_to_string(img, config=config)
                    cleaned = text.strip()
                    # Simple heuristic: longer text is often better (unless it's noise)
                    # We could check for valid Japanese characters ratio too.
                    if len(cleaned) > max_len:
                        max_len = len(cleaned)
                        best_text = cleaned
                except pytesseract.TesseractError:
                    continue

                # If we found a good amount of text, maybe stop early?
                # For now, let's try a few combos.
                if len(best_text) > 50:
                    break

            if len(best_text) > 100:
                break

        except Exception as e:
            logger.warning(f"OCR attempt {i} failed: {e}")
            continue

    if not best_text:
        return "テキストは検出されませんでした。"

    return best_text




def _analyze_image_v2_raw(data: bytes) -> dict:
    """
    Analyze image using Google Cloud Vision API and return structured data.
    Returns a dict with keys: labels, faces, text, objects, error.
    """
    result = {"labels": [], "faces": 0, "text": "", "objects": [], "error": None, "safe_search": None}

    try:
        from google.cloud import vision
    except ImportError:
        result["error"] = "google-cloud-vision not installed"
        return result

    try:
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=data)

        response = client.annotate_image(
            {
                "image": image,
                "features": [
                    {"type": vision.Feature.Type.LABEL_DETECTION, "max_results": 10},
                    {"type": vision.Feature.Type.FACE_DETECTION, "max_results": 10},
                    {"type": vision.Feature.Type.TEXT_DETECTION, "max_results": 1},
                    {"type": vision.Feature.Type.OBJECT_LOCALIZATION, "max_results": 10},
                    {"type": vision.Feature.Type.SAFE_SEARCH_DETECTION},
                ],
            }
        )
    except Exception as e:
        logger.error(f"Vision API Error: {e}")
        # Fallback to Tesseract
        logger.info("Falling back to Tesseract OCR...")
        try:
            ocr_text = ocr_image(data)
            result["text"] = ocr_text
            result["error"] = f"Vision API failed ({e}), used Tesseract."
            return result
        except Exception as tess_err:
            result["error"] = f"Vision API & Tesseract failed: {e} / {tess_err}"
            return result

    if response.error.message:
        err_msg = response.error.message
        # Always fallback on error if possible
        logger.warning(f"Vision API returned error: {err_msg}. Falling back to Tesseract.")
        try:
            ocr_text = ocr_image(data)
            result["text"] = ocr_text
            result["error"] = f"Vision API Error ({err_msg}), used Tesseract."
            return result
        except Exception as tess_err:
            result["error"] = f"Vision API Error & Tesseract failed: {err_msg} / {tess_err}"
            return result

    # Labels
    if response.label_annotations:
        result["labels"] = [label.description for label in response.label_annotations]

    # Faces
    if response.face_annotations:
        result["faces"] = len(response.face_annotations)

    # Text
    if response.text_annotations:
        result["text"] = response.text_annotations[0].description.strip()

    # Objects
    if response.localized_object_annotations:
        result["objects"] = [o.name for o in response.localized_object_annotations]

    # Safe Search
    if response.safe_search_annotation:
        s = response.safe_search_annotation
        result["safe_search"] = {"adult": s.adult, "violence": s.violence, "racy": s.racy}

    return result


def analyze_image_structured(data: bytes) -> dict:
    """Public alias for structured analysis."""
    return _analyze_image_v2_raw(data)


def analyze_image_v2(data: bytes) -> str:
    """Legacy wrapper that returns a formatted string for the LLM."""
    data_dict = _analyze_image_v2_raw(data)

    if data_dict["error"] and not data_dict["text"]:
        return f"Error: {data_dict['error']}"

    parts = []

    if data_dict["error"]:
        parts.append(f"[Warning: {data_dict['error']}]")

    if data_dict["labels"]:
        parts.append("Labels: " + ", ".join(data_dict["labels"][:5]))

    if data_dict["objects"]:
        parts.append("Objects: " + ", ".join(data_dict["objects"][:5]))

    if data_dict["faces"] > 0:
        parts.append(f"Faces detected: {data_dict['faces']}")

    if data_dict["text"]:
        parts.append("Text: " + data_dict["text"].replace("\n", " "))

    if not parts:
        return "No significant features detected."

    return "Image contains: " + "  |  ".join(parts)


def decode_base64_image(base64_string: str) -> io.BytesIO:
    """Decode a base64 string (from API) into a BytesIO object."""
    import base64

    # Remove prefix if present (e.g., data:image/png;base64,)
    if "," in base64_string:
        base64_string = base64_string.split(",", 1)[1]

    image_data = base64.b64decode(base64_string)
    return io.BytesIO(image_data)
