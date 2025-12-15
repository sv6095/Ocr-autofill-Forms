"""
One-time script to download and cache TrOCR models locally.

Run this script once before deploying to production with offline mode enabled.
This will download all required TrOCR models to the local cache.

Usage:
    python scripts/cache_trocr_models.py

Or from the Backend directory:
    python -m scripts.cache_trocr_models
"""
import sys
import os
from pathlib import Path

# Add parent directory to path to import app config
sys.path.insert(0, str(Path(__file__).parent.parent))

def cache_trocr_models():
    """Download and cache all TrOCR models locally."""
    print("=" * 60)
    print("TrOCR Model Caching Script")
    print("=" * 60)
    print("\nThis script will download TrOCR models from Hugging Face")
    print("and cache them locally for offline use.\n")
    
    try:
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        print("✓ Transformers and PyTorch libraries found\n")
    except ImportError as e:
        print(f"✗ Error: Required libraries not installed: {e}")
        print("\nPlease install required dependencies:")
        print("  pip install torch transformers")
        return False
    
    models = [
        {
            "name": "microsoft/trocr-small-printed",
            "description": "TrOCR Printed Text Model"
        },
        {
            "name": "microsoft/trocr-base-handwritten",
            "description": "TrOCR Handwritten Text Model"
        }
    ]
    
    success_count = 0
    failed_models = []
    
    for model_info in models:
        model_name = model_info["name"]
        description = model_info["description"]
        
        print(f"\n{'=' * 60}")
        print(f"Downloading: {description}")
        print(f"Model: {model_name}")
        print(f"{'=' * 60}")
        
        try:
            # Download processor
            print(f"  → Downloading processor...")
            processor = TrOCRProcessor.from_pretrained(model_name)
            print(f"  ✓ Processor cached successfully")
            
            # Download model
            print(f"  → Downloading model...")
            model = VisionEncoderDecoderModel.from_pretrained(model_name)
            print(f"  ✓ Model cached successfully")
            
            # Get model info
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            print(f"  → Model will run on: {device}")
            
            success_count += 1
            print(f"  ✓ {description} - COMPLETE\n")
            
        except Exception as e:
            print(f"  ✗ Failed to download {description}: {e}")
            failed_models.append(model_name)
            import traceback
            print(f"\n  Error details:")
            print(f"  {traceback.format_exc()}\n")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Successfully cached: {success_count}/{len(models)} models")
    
    if failed_models:
        print(f"\nFailed models:")
        for model in failed_models:
            print(f"  - {model}")
        print("\nPlease check your internet connection and try again.")
        return False
    else:
        print("\n✓ All models cached successfully!")
        print("\nYou can now enable offline mode by setting:")
        print("  export TRANSFORMERS_OFFLINE=1")
        print("\nOr in Windows:")
        print("  set TRANSFORMERS_OFFLINE=1")
        print("\nThe models are cached in:")
        cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
        print(f"  {cache_dir}")
        return True

if __name__ == "__main__":
    success = cache_trocr_models()
    sys.exit(0 if success else 1)

