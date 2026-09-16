import os
import json
import re
from typing import List, Dict, Optional
from dataclasses import dataclass
import pytesseract
from PIL import Image
from PyPDF2 import PdfReader
from docx import Document


WHATSAPP_IOS_PATTERN = re.compile(
    r"^\[(?P<timestamp>[^\]]+)\]\s*(?P<speaker>[^:]+):\s*(?P<text>.*)$"
)

@dataclass
class Chunk:
    text: str
    speaker: Optional[str] = None
    source_ref: str = ""
    metadata: Optional[Dict] = None

def normalize(file_path: str, file_type: str) -> List[Chunk]:
    if file_type == ".txt":
        return chunk_whatsapp(file_path)
    elif file_type == ".pdf":
        return extract_pdf_text(file_path)
    elif file_type in [".png", ".jpg"]:
        return extract_image_text(file_path)
    elif file_type == ".docx":
        return extract_docx_text(file_path)
    elif file_type == ".json":
        return parse_discord_json(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

def chunk_whatsapp(file_path: str) -> List[Chunk]:
    chunks = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line or not line.startswith("["):
                continue
            match = WHATSAPP_IOS_PATTERN.match(line)
            if match:
                speaker = match.group("speaker").strip()
                text = match.group("text").strip()
                chunks.append(
                    Chunk(
                        text=text,
                        speaker=speaker,
                        source_ref=f"{os.path.basename(file_path)}:{line_number}",
                    )
                )
    return chunks

def extract_pdf_text(file_path: str) -> List[Chunk]:
    chunks = []
    with open(file_path, "rb") as f:
        reader = PdfReader(f)
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if text:
                chunks.append(
                    Chunk(
                        text=text,
                        source_ref=f"{os.path.basename(file_path)}:page-{page_number}",
                    )
                )
    return chunks

def extract_image_text(file_path: str) -> List[Chunk]:
    text = pytesseract.image_to_string(Image.open(file_path))
    return [Chunk(text=text, source_ref=f"{os.path.basename(file_path)}:image")]

def extract_docx_text(file_path: str) -> List[Chunk]:
    doc = Document(file_path)
    chunks = [
        Chunk(
            text=paragraph.text,
            source_ref=f"{os.path.basename(file_path)}:paragraph-{index}",
        )
        for index, paragraph in enumerate(doc.paragraphs, start=1)
        if paragraph.text.strip()
    ]
    return chunks

def parse_discord_json(file_path: str) -> List[Chunk]:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    chunks = []
    for index, message in enumerate(data.get("messages", []), start=1):
        chunks.append(Chunk(
            text=message.get("content", ""),
            speaker=message.get("author", {}).get("name", None),
            source_ref=f"{os.path.basename(file_path)}:message-{index}",
        ))
    return chunks
