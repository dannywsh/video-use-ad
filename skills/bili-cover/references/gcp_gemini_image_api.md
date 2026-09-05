# Google Cloud Gemini image API (gcp-gemini)

Backend ID: `gcp-gemini`. Script: `skills/bili-cover/scripts/gcp_gemini_image.py`.

Cover generation uses this contract. Do not swap in AI Studio `generativelanguage.googleapis.com` or Vertex regional `projects/{id}/locations/...` URLs unless the user changes `GCP_GEMINI_IMAGE_API_ENDPOINT` / model.

## Endpoint

```
POST https://{GCP_GEMINI_IMAGE_API_ENDPOINT}/v1/publishers/google/models/{GCP_GEMINI_IMAGE_MODEL}:streamGenerateContent?key={GCP_GEMINI_IMAGE_API_KEY}
```

Defaults:

| Variable | Default |
|----------|---------|
| `GCP_GEMINI_IMAGE_API_ENDPOINT` | `aiplatform.googleapis.com` |
| `GCP_GEMINI_IMAGE_MODEL` | `gemini-3.1-flash-lite-image` |
| `GCP_GEMINI_IMAGE_SIZE` | `1K` |
| `GCP_GEMINI_IMAGE_API_KEY` | (required) |

`Content-Type: application/json`. Auth is the `key` query parameter (publisher API key), not `gcloud` ADC.

## Request body

```json
{
  "contents": [
    {
      "role": "user",
      "parts": [
        { "text": "<cover prompt>" },
        {
          "inline_data": {
            "mime_type": "image/jpeg",
            "data": "<base64>"
          }
        }
      ]
    }
  ],
  "generationConfig": {
    "temperature": 1,
    "maxOutputTokens": 32768,
    "responseModalities": ["TEXT", "IMAGE"],
    "topP": 0.95,
    "imageConfig": {
      "aspectRatio": "16:9",
      "imageSize": "1K",
      "imageOutputOptions": {
        "mimeType": "image/jpeg"
      },
      "personGeneration": "ALLOW_ALL"
    },
    "thinkingConfig": {
      "thinkingLevel": "MINIMAL"
    }
  },
  "safetySettings": [
    { "category": "HARM_CATEGORY_IMAGE_HATE", "threshold": "OFF" },
    { "category": "HARM_CATEGORY_IMAGE_DANGEROUS_CONTENT", "threshold": "OFF" },
    { "category": "HARM_CATEGORY_IMAGE_HARASSMENT", "threshold": "OFF" },
    { "category": "HARM_CATEGORY_IMAGE_SEXUALLY_EXPLICIT", "threshold": "OFF" }
  ]
}
```

### Fields

- `contents[0].role` is `user`. `parts` must not be empty.
- Text prompt is a `text` part. Reference stills are extra `inline_data` parts (`mime_type` + base64). Local files: JPEG / PNG / WEBP; max 14 images (model limit). Use `inline_data` even if some docs show `inlineData` / `fileData`.
- Cover **must** set `imageConfig.aspectRatio` to `16:9` (do not use the official sample’s `"auto"` for Bilibili covers). Supported ratios include 1:1 through 21:9; `16:9` is valid.
- `imageSize`: `1K` (default) / `2K` / `4K` via `GCP_GEMINI_IMAGE_SIZE` or `--size`.
- `imageOutputOptions.mimeType`: `image/jpeg` for `cover.jpg`.
- `personGeneration`: `ALLOW_ALL` (ACG figures / people in stills).
- `responseModalities`: both `TEXT` and `IMAGE`.
- `thinkingConfig.thinkingLevel`: `MINIMAL`.
- Image harm categories listed above stay `OFF`.

## Response

`streamGenerateContent` may return a JSON array of chunks or SSE `data:` lines. Each chunk looks like:

```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          { "text": "..." },
          {
            "inlineData": {
              "mimeType": "image/jpeg",
              "data": "<base64>"
            }
          }
        ]
      }
    }
  ]
}
```

Read `inlineData` or `inline_data`. Decode `data` and write `--output`. If no image part arrives, treat as failure and fall through to `ark-seedream`.

## CLI

```bash
python skills/bili-cover/scripts/gcp_gemini_image.py \
  --prompt "..." \
  --output /path/to/edit/cover.jpg \
  --reference-image /path/to/product.jpg \
  --aspect-ratio 16:9 \
  --size 1K
```

Repeat `--reference-image` for multiple stills. `--print-request` writes the JSON body (base64 truncated) to stdout and does not call the API.

Env lookup matches parent TTS: skill-root `.env` → cwd `.env` → process environment.
