#!/usr/bin/env python3
import sys
import os
import torch
from diffusers import StableDiffusionPipeline

print("🔍 Testing SD Container")

# Detect GPU
if not torch.cuda.is_available():
    print("❌ CUDA not available")
    sys.exit(1)

device_name = torch.cuda.get_device_name(0)
device_count = torch.cuda.get_device_count()
vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9

print(f"  Device: NVIDIA {device_name}")
print(f"  VRAM: {vram_gb:.1f}GB")
print(f"  Device Count: {device_count}")

# Create output directory
os.makedirs("/app/outputs", exist_ok=True)

# Load model
print("📥 Loading model...")
try:
    pipe = StableDiffusionPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=torch.float16,
        safety_checker=None
    )
    pipe = pipe.to("cuda")
except Exception as e:
    print(f"❌ Model loading failed: {e}")
    sys.exit(1)

# Generate image
print("🎨 Generating image...")
try:
    with torch.no_grad():
        image = pipe("a beautiful medieval sword", height=512, width=512).images[0]
except Exception as e:
    print(f"❌ Generation failed: {e}")
    sys.exit(1)

# Save and report
output_path = "/app/outputs/test.png"
image.save(output_path)

print(f"✅ Success! Image shape: {image.size}")
print(f"📁 Saved to {output_path}")
