"""
Test TrOCR models using HuggingFace dataset.
Uses Voxel51/form_understanding_in_noisy_scanned_documents_plus for test data.

Usage:
    # First, login to HuggingFace
    huggingface-cli login
    
    # Then run the test
    python test_with_huggingface_dataset.py
"""
import os
from typing import Dict, List, Tuple
from PIL import Image
import torch
from datasets import load_dataset
from tqdm import tqdm
import json
from io import BytesIO

# Import OCR engines
from ocr.ocr_engines.trocr_printed import ocr_printed_text, is_available as trocr_printed_available
from ocr.ocr_engines.trocr_handwritten import ocr_handwriting_page, is_available as trocr_handwritten_available
from ocr.ocr_engines.tesseract_multi import ocr_multilingual
from ocr.ocr_engines.ocr_selector import perform_ocr, select_ocr_engine
from ocr.preprocessing.detector import detect_text_type, TextType

# Import API functions
from ocr.extraction.extractor import perform_extraction
from ocr.verification.comparator import verify_submitted_data


def load_test_dataset(dataset_name: str = "Voxel51/form_understanding_in_noisy_scanned_documents_plus"):
    """
    Load HuggingFace dataset for testing.
    
    Args:
        dataset_name: Name of the HuggingFace dataset
    
    Returns:
        Dataset object
    """
    print(f"Loading dataset: {dataset_name}")
    print("Note: You may need to login using 'huggingface-cli login' to access this dataset")
    
    try:
        dataset = load_dataset(dataset_name)
        print(f"Dataset loaded successfully!")
        print(f"Available splits: {list(dataset.keys())}")
        return dataset
    except Exception as e:
        print(f"Error loading dataset: {e}")
        print("\nTo access this dataset:")
        print("1. Install huggingface_hub: pip install huggingface_hub")
        print("2. Login: huggingface-cli login")
        print("3. Request access to the dataset if needed")
        raise


def convert_to_pil_image(image_data) -> Image.Image:
    """
    Convert dataset image to PIL Image.
    
    Args:
        image_data: Image data from dataset (can be PIL Image, numpy array, or dict)
    
    Returns:
        PIL Image
    """
    if isinstance(image_data, Image.Image):
        return image_data.convert("RGB")
    elif hasattr(image_data, 'convert'):
        return image_data.convert("RGB")
    else:
        # Try to convert from numpy array or other formats
        try:
            import numpy as np
            if isinstance(image_data, np.ndarray):
                return Image.fromarray(image_data).convert("RGB")
        except:
            pass
        raise ValueError(f"Cannot convert image data of type {type(image_data)} to PIL Image")


def test_single_image(
    image: Image.Image,
    ground_truth: str = None,
    engine: str = "auto"
) -> Dict:
    """
    Test OCR on a single image.
    
    Args:
        image: PIL Image
        ground_truth: Ground truth text (optional)
        engine: OCR engine to use ("auto", "trocr_printed", "trocr_handwritten", "tesseract", "extraction", "verification")
    
    Returns:
        Dictionary with results
    """
    result = {
        "engine": engine,
        "text": "",
        "confidence": 0.0,
        "ground_truth": ground_truth,
        "match": False
    }
    
    try:
        if engine in ["auto", "trocr_printed", "trocr_handwritten", "tesseract"]:
            # Original OCR engines
            if engine == "auto":
                # Auto-select engine
                text_type = detect_text_type(image)
                selected_engine = select_ocr_engine(image, text_type_hint=text_type)
                ocr_result = perform_ocr(image, text_type_hint=text_type)
                result["engine"] = selected_engine
                result["text"] = ocr_result.text
                result["confidence"] = ocr_result.confidence
                result["metadata"] = ocr_result.metadata
            elif engine == "trocr_printed":
                if not trocr_printed_available():
                    result["error"] = "TrOCR printed model not available"
                    return result
                result["text"] = ocr_printed_text(image)
                result["confidence"] = 0.85  # TrOCR doesn't provide confidence
            elif engine == "trocr_handwritten":
                if not trocr_handwritten_available():
                    result["error"] = "TrOCR handwritten model not available"
                    return result
                hw_result = ocr_handwriting_page(image, use_trocr_if_available=True)
                result["text"] = hw_result.get("full_text", "")
                result["confidence"] = 0.80
                result["metadata"] = {"lines": hw_result.get("lines", [])}
            elif engine == "tesseract":
                result["text"], result["confidence"] = ocr_multilingual(image, language="eng")
        elif engine == "extraction":
            # Use extraction API
            image_bytes = BytesIO()
            image.save(image_bytes, format='PNG')
            file_bytes = image_bytes.getvalue()
            
            raw_text, fields, field_confidences, pages, tables = perform_extraction(
                file_bytes=file_bytes,
                filename="test.png",
                content_type="image/png",
                language="eng",
                run_table_ocr=True,
                enable_multistage=True,
                handwriting_mode="auto"
            )
            result["text"] = raw_text
            result["confidence"] = 0.9  # Assume high confidence for extraction
            result["fields"] = fields
            result["field_confidences"] = field_confidences
        elif engine == "verification":
            # Use verification API: extract fields, then verify with ground_truth as submitted data
            if not ground_truth:
                result["error"] = "Ground truth required for verification"
                return result
            
            image_bytes = BytesIO()
            image.save(image_bytes, format='PNG')
            file_bytes = image_bytes.getvalue()
            
            raw_text, extracted_fields, field_confidences, pages, tables = perform_extraction(
                file_bytes=file_bytes,
                filename="test.png",
                content_type="image/png",
                language="eng",
                run_table_ocr=True,
                enable_multistage=True,
                handwriting_mode="auto"
            )
            
            # Assume ground_truth is the full text, submit as {"text": ground_truth}
            submitted_data = {"text": ground_truth}
            field_results, overall_conf = verify_submitted_data(
                submitted_data=submitted_data,
                extracted_fields=extracted_fields
            )
            result["text"] = raw_text
            result["confidence"] = overall_conf
            result["field_results"] = [fr.dict() for fr in field_results]
            result["extracted_fields"] = extracted_fields
        else:
            result["error"] = f"Unknown engine: {engine}"
            return result
        
        # Compare with ground truth if available
        if ground_truth:
            from difflib import SequenceMatcher
            similarity = SequenceMatcher(
                None,
                result["text"].strip().lower(),
                ground_truth.strip().lower()
            ).ratio()
            result["similarity"] = similarity
            result["match"] = similarity >= 0.9
        
    except Exception as e:
        result["error"] = str(e)
    
    return result


def test_dataset(
    dataset,
    split: str = "test",
    max_samples: int = 100,
    engines: List[str] = ["auto", "trocr_printed", "trocr_handwritten", "tesseract", "extraction", "verification"]
) -> Dict:
    """
    Test OCR engines on dataset.
    
    Args:
        dataset: HuggingFace dataset
        split: Dataset split to use
        max_samples: Maximum number of samples to test
        engines: List of engines to test
    
    Returns:
        Dictionary with test results
    """
    if split not in dataset:
        print(f"Split '{split}' not found. Available splits: {list(dataset.keys())}")
        split = list(dataset.keys())[0]
        print(f"Using split: {split}")
    
    test_data = dataset[split]
    num_samples = min(len(test_data), max_samples)
    
    print(f"\nTesting on {num_samples} samples from '{split}' split")
    print(f"Engines to test: {engines}\n")
    
    results = {
        "engines": {engine: {"total": 0, "success": 0, "errors": 0, "similarities": []} for engine in engines},
        "samples": []
    }
    
    for i in tqdm(range(num_samples), desc="Testing"):
        try:
            sample = test_data[i]
            
            # Extract image and text from sample
            # Dataset structure may vary, adjust based on actual structure
            image_data = None
            ground_truth = None
            
            # Try common field names
            for field in ["image", "img", "image_path", "image_bytes"]:
                if field in sample:
                    image_data = sample[field]
                    break
            
            for field in ["text", "label", "ground_truth", "transcription", "text_ground_truth"]:
                if field in sample:
                    ground_truth = sample[field]
                    break
            
            if image_data is None:
                print(f"\nWarning: Could not find image in sample {i}")
                continue
            
            # Convert to PIL Image
            try:
                image = convert_to_pil_image(image_data)
            except Exception as e:
                print(f"\nWarning: Could not convert image in sample {i}: {e}")
                continue
            
            sample_result = {
                "sample_id": i,
                "ground_truth": ground_truth,
                "engine_results": {}
            }
            
            # Test each engine
            for engine in engines:
                engine_result = test_single_image(image, ground_truth, engine)
                sample_result["engine_results"][engine] = engine_result
                
                # Update statistics
                stats = results["engines"][engine]
                stats["total"] += 1
                
                if "error" in engine_result:
                    stats["errors"] += 1
                else:
                    stats["success"] += 1
                    if "similarity" in engine_result:
                        stats["similarities"].append(engine_result["similarity"])
            
            results["samples"].append(sample_result)
            
        except Exception as e:
            print(f"\nError processing sample {i}: {e}")
            continue
    
    # Calculate average similarities
    for engine in engines:
        stats = results["engines"][engine]
        if stats["similarities"]:
            stats["avg_similarity"] = sum(stats["similarities"]) / len(stats["similarities"])
        else:
            stats["avg_similarity"] = 0.0
    
    return results


def print_results(results: Dict):
    """Print test results in a readable format."""
    print("\n" + "="*80)
    print("TEST RESULTS")
    print("="*80)
    
    for engine, stats in results["engines"].items():
        print(f"\n{engine.upper()}:")
        print(f"  Total samples: {stats['total']}")
        print(f"  Successful: {stats['success']}")
        print(f"  Errors: {stats['errors']}")
        if stats['similarities']:
            print(f"  Average similarity: {stats['avg_similarity']:.3f}")
            print(f"  Best similarity: {max(stats['similarities']):.3f}")
            print(f"  Worst similarity: {min(stats['similarities']):.3f}")
    
    print("\n" + "="*80)


def save_results(results: Dict, output_file: str = "test_results.json"):
    """Save test results to JSON file."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_file}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test TrOCR models with HuggingFace dataset")
    parser.add_argument(
        "--dataset",
        type=str,
        default="Voxel51/form_understanding_in_noisy_scanned_documents_plus",
        help="HuggingFace dataset name"
    )
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        help="Dataset split to use"
    )
    parser.add_argument(
        "--max_samples",
        type=int,
        default=100,
        help="Maximum number of samples to test"
    )
    parser.add_argument(
        "--engines",
        nargs="+",
        default=["auto", "trocr_printed", "trocr_handwritten", "tesseract", "extraction", "verification"],
        help="OCR engines to test"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="test_results.json",
        help="Output file for results"
    )
    
    args = parser.parse_args()
    
    # Check if TrOCR is available
    print("Checking TrOCR availability...")
    print(f"  TrOCR Printed: {'✓' if trocr_printed_available() else '✗'}")
    print(f"  TrOCR Handwritten: {'✓' if trocr_handwritten_available() else '✗'}")
    
    if not trocr_printed_available() and not trocr_handwritten_available():
        print("\nWarning: TrOCR models not available. Install transformers and torch to use TrOCR.")
    
    # Load dataset
    try:
        dataset = load_test_dataset(args.dataset)
    except Exception as e:
        print(f"\nFailed to load dataset: {e}")
        return
    
    # Run tests
    results = test_dataset(
        dataset,
        split=args.split,
        max_samples=args.max_samples,
        engines=args.engines
    )
    
    # Print results
    print_results(results)
    
    # Save results
    save_results(results, args.output)


if __name__ == "__main__":
    main()

