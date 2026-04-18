# PNG Generator Cell – Backend Scripts

## Purpose

Execution scripts for the **PNG Generator Cell** backend — Stable Diffusion text-to-image pipeline with background removal and prompt enhancement utilities.

## Content Index

| File | Description |
|------|-------------|
| [`__init__.py`](./__init__.py) | Package marker |
| [`main.py`](./main.py) | `PngGeneratorCell` BaseCell + `execute_cell()` wrapper — `generate` and `removeBackground` actions, SD API integration |
| [`background_removal.py`](./background_removal.py) | Background removal logic using rembg — processes generated PNG to remove background |
| [`prompt_enhancement.py`](./prompt_enhancement.py) | LLM-based prompt enhancement — improves SD prompts for better image quality |
| [`fallback_utils.py`](./fallback_utils.py) | Fallback utilities — handles SD API unavailability with placeholder/error responses |

## Related

- [`../`](../) — PNG Generator Cell backend root
