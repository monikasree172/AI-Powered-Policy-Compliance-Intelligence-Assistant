"""
Policy Document Ingestion Pipeline

Downloads NIST CSF PDF, extracts text, chunks semantically,
generates embeddings, and stores in ChromaDB.

Usage:
    python scripts/ingest.py                        # Auto-download NIST CSF
    python scripts/ingest.py --file path/to/doc.pdf # Local file
    python scripts/ingest.py --url <url>            # Custom URL
    python scripts/ingest.py --reset                # Clear DB first
"""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""  # disable GPU usage

import argparse
import io
import os
import sys
import warnings
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from shared.core.chunker import chunk_policy_document
from shared.core.vectorstore import PolicyVectorStore

DEFAULT_SOURCES = [
    {
        "url": "https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf",
        "name": "NIST CSF 2.0",
        "framework": "NIST",
    },
    {
        "url": "https://csrc.nist.gov/csrc/media/Publications/white-paper/2022/01/18/cybersecurity-framework-2-0-concept-paper/final/documents/nistvlabs-csf2.0-concept-paper.pdf",
        "name": "NIST CSF Concept Paper",
        "framework": "NIST",
    },
    {
        "url": "https://heimdalsecurity.com/blog/wp-content/uploads/NIST-Cybersecurity-Framework-Policy-Template-Guide-1.pdf",
        "name": "NIST CSF Policy Template Guide",
        "framework": "NIST",
    },
]


def download_pdf(url: str, timeout: int = 60) -> bytes:
    import requests
    import urllib3
    # Disable SSL warnings - needed for corporate/university networks with proxy certificates
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    warnings.filterwarnings("ignore")

    print(f"Downloading: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    # verify=False is required on corporate networks with SSL inspection proxies
    response = requests.get(url, headers=headers, timeout=timeout, verify=False)
    response.raise_for_status()
    print(f"Downloaded {len(response.content):,} bytes")
    return response.content


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    print(f"Extracting text from {len(reader.pages)} pages...")
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    full_text = "\n\n".join(pages)
    print(f"Extracted {len(full_text):,} characters")
    return full_text


def ingest_source(source_name: str, framework: str,
                  pdf_bytes: Optional[bytes] = None, text: Optional[str] = None,
                  vector_store: Optional[PolicyVectorStore] = None) -> int:
    if vector_store is None:
        vector_store = PolicyVectorStore()
    if text is None:
        if pdf_bytes is None:
            raise ValueError("Must provide pdf_bytes or text")
        text = extract_text_from_pdf(pdf_bytes)

    print(f"Chunking: {source_name}...")
    chunks = chunk_policy_document(text=text, source=source_name, framework=framework)
    print(f"Created {len(chunks)} chunks")
    return vector_store.add_chunks(chunks)


def main():
    parser = argparse.ArgumentParser(description="Ingest policy documents into ChromaDB")
    parser.add_argument("--url", help="URL of policy PDF")
    parser.add_argument("--file", help="Local path to policy PDF")
    parser.add_argument("--name", default="NIST CSF 2.0", help="Source name")
    parser.add_argument("--framework", default="NIST", help="Framework name")
    parser.add_argument("--reset", action="store_true", help="Clear existing documents first")
    args = parser.parse_args()

    vector_store = PolicyVectorStore()

    if args.reset:
        print("Resetting vector store...")
        vector_store.reset()

    if args.file:
        print(f"Reading local file: {args.file}")
        with open(args.file, "rb") as f:
            pdf_bytes = f.read()
        count = ingest_source(source_name=args.name, framework=args.framework,
                               pdf_bytes=pdf_bytes, vector_store=vector_store)
        print(f"\nIngestion complete. Total documents: {count}")
        return

    if args.url:
        try:
            pdf_bytes = download_pdf(args.url)
            count = ingest_source(source_name=args.name, framework=args.framework,
                                   pdf_bytes=pdf_bytes, vector_store=vector_store)
            print(f"\nIngestion complete. Total documents: {count}")
        except Exception as e:
            print(f"Failed: {e}")
            sys.exit(1)
        return

    # Try all default sources
    success = False
    for source in DEFAULT_SOURCES:
        try:
            pdf_bytes = download_pdf(source["url"])
            count = ingest_source(source_name=source["name"], framework=source["framework"],
                                   pdf_bytes=pdf_bytes, vector_store=vector_store)
            print(f"\nIngestion complete. Total documents: {count}")
            success = True
            break
        except Exception as e:
            print(f"  Failed ({source['name']}): {e}")
            continue

    if not success:
        print("\n" + "="*60)
        print("AUTO-DOWNLOAD FAILED (SSL block on your network)")
        print("="*60)
        print("\nMANUAL FIX - do ONE of these:\n")
        print("Option 1 - Download PDF manually:")
        print("  1. Open this URL in your browser:")
        print("     https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf")
        print("  2. Save it as 'nist-csf.pdf' in the pca folder")
        print("  3. Run: python scripts/ingest.py --file nist-csf.pdf")
        print("\nOption 2 - Use a text file instead:")
        print("  python scripts/ingest.py --file any_policy_document.txt")
        sys.exit(1)


if __name__ == "__main__":
    main()
