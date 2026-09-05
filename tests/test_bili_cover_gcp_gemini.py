import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "bili-cover" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import gcp_gemini_image as G  # noqa: E402


class BuildRequestTests(unittest.TestCase):
    def test_cover_defaults_lock_16x9_jpeg(self):
        body = G.build_request("生成一张用于 B站视频封面的图")
        cfg = body["generationConfig"]
        image_cfg = cfg["imageConfig"]
        self.assertEqual(cfg["responseModalities"], ["TEXT", "IMAGE"])
        self.assertEqual(image_cfg["aspectRatio"], "16:9")
        self.assertEqual(image_cfg["imageSize"], "1K")
        self.assertEqual(image_cfg["imageOutputOptions"]["mimeType"], "image/jpeg")
        self.assertEqual(image_cfg["personGeneration"], "ALLOW_ALL")
        self.assertEqual(cfg["thinkingConfig"]["thinkingLevel"], "MINIMAL")
        self.assertEqual(body["contents"][0]["role"], "user")
        self.assertEqual(body["contents"][0]["parts"][0]["text"], "生成一张用于 B站视频封面的图")
        categories = [item["category"] for item in body["safetySettings"]]
        self.assertIn("HARM_CATEGORY_IMAGE_HATE", categories)

    def test_rejects_unknown_aspect_ratio(self):
        with self.assertRaises(ValueError):
            G.build_request("x", aspect_ratio="7:3")


class StreamParseTests(unittest.TestCase):
    def test_json_array_inline_data(self):
        raw = json.dumps(
            [
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": "ok"},
                                    {
                                        "inlineData": {
                                            "mimeType": "image/jpeg",
                                            "data": "aGVsbG8=",
                                        }
                                    },
                                ]
                            }
                        }
                    ]
                }
            ]
        )
        images = G.parse_stream_images(raw)
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0][1], b"hello")

    def test_sse_snake_case(self):
        raw = (
            "data: "
            + json.dumps(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "inline_data": {
                                            "mime_type": "image/jpeg",
                                            "data": "Ynk=",
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            )
        )
        images = G.parse_stream_images(raw)
        self.assertEqual(images[0][1], b"by")


class UrlTests(unittest.TestCase):
    def test_publisher_stream_url(self):
        url = G.request_url(
            "aiplatform.googleapis.com",
            "gemini-3.1-flash-lite-image",
            "secret-key",
        )
        self.assertTrue(
            url.startswith(
                "https://aiplatform.googleapis.com/v1/publishers/google/models/"
                "gemini-3.1-flash-lite-image:streamGenerateContent?key="
            )
        )


if __name__ == "__main__":
    unittest.main()
