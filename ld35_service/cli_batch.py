#!/usr/bin/env python3
"""
Batch processing CLI for VizuMarker using enhanced semantic engine.
Processes multiple text files and outputs .ann.json files.

Usage:
    python -m ld35_service.cli_batch input_dir output_dir [--resources resources_dir]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ld35_service.engine.sem_core import analyze_text


def sha256(text: str) -> str:
    """Calculate SHA256 hash of text"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def process_file(file_path: Path, resources_dir: Path) -> Dict[str, Any]:
    """Process a single text file and return analysis result"""
    try:
        # Read file content
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        
        # Analyze with semantic engine
        result = analyze_text(text, resources_dir)
        
        # Add file metadata
        analysis_result = {
            "source": file_path.name,
            "text_sha256": sha256(text),
            "annotations": result["annotations"],
            "metadata": result.get("metadata", {})
        }
        
        return analysis_result
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return {
            "source": file_path.name,
            "error": str(e),
            "annotations": []
        }


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Batch process text files with VizuMarker semantic engine"
    )
    parser.add_argument(
        "input_dir", 
        type=Path, 
        help="Directory containing input text files (.txt, .md)"
    )
    parser.add_argument(
        "output_dir", 
        type=Path, 
        help="Directory to write .ann.json output files"
    )
    parser.add_argument(
        "--resources", 
        type=Path, 
        default=Path("resources"),
        help="Directory containing canonical resources (default: resources/)"
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".txt", ".md"],
        help="File extensions to process (default: .txt .md)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Validate input directory
    if not args.input_dir.exists():
        print(f"Error: Input directory '{args.input_dir}' does not exist")
        return 1
        
    if not args.input_dir.is_dir():
        print(f"Error: '{args.input_dir}' is not a directory")
        return 1
    
    # Validate resources directory
    if not args.resources.exists():
        print(f"Error: Resources directory '{args.resources}' does not exist")
        return 1
        
    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find input files
    input_files = []
    for ext in args.extensions:
        input_files.extend(args.input_dir.rglob(f"*{ext}"))
    
    if not input_files:
        print(f"No files found with extensions {args.extensions} in {args.input_dir}")
        return 1
    
    if args.verbose:
        print(f"Found {len(input_files)} files to process")
        print(f"Output directory: {args.output_dir}")
        print(f"Resources directory: {args.resources}")
    
    # Process files
    processed = 0
    errors = 0
    
    for file_path in sorted(input_files):
        if args.verbose:
            print(f"Processing: {file_path}")
        
        try:
            # Process file
            result = process_file(file_path, args.resources)
            
            # Generate output filename
            output_filename = file_path.stem + ".ann.json"
            output_path = args.output_dir / output_filename
            
            # Write result
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            if "error" in result:
                errors += 1
                if args.verbose:
                    print(f"  Error: {result['error']}")
            else:
                processed += 1
                if args.verbose:
                    ann_count = len(result.get("annotations", []))
                    print(f"  Success: {ann_count} annotations found")
                    
        except Exception as e:
            errors += 1
            print(f"Failed to process {file_path}: {e}")
    
    # Summary
    print(f"\nProcessing complete:")
    print(f"  Processed: {processed} files")
    print(f"  Errors: {errors} files")
    print(f"  Output directory: {args.output_dir}")
    
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())