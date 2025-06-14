from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import difflib
import base64
import pytesseract
from PIL import Image
from io import BytesIO

# Load JSON data
with open("course_content.json", "r", encoding="utf-8") as f:
    course_data = json.load(f)

with open("discourse_posts.json", "r", encoding="utf-8") as f:
    discourse_data = json.load(f)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str
    image_base64: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    references: Dict[str, str]
    links: Dict[str, str] = {}

def search_json_for_answer(json_data: Any, question: str) -> List[str]:
    matches = []
    threshold = 0.5

    def recursive_search(item):
        if isinstance(item, dict):
            for k, v in item.items():
                combined = f"{k}: {v}"
                score = difflib.SequenceMatcher(None, question.lower(), combined.lower()).ratio()
                if score > threshold:
                    matches.append(combined)
                recursive_search(v)
        elif isinstance(item, list):
            for subitem in item:
                recursive_search(subitem)
        elif isinstance(item, str):
            score = difflib.SequenceMatcher(None, question.lower(), item.lower()).ratio()
            if score > threshold:
                matches.append(item)

    recursive_search(json_data)
    return matches

@app.get("/")
async def root():
    return {"message": "Virtual TA is running"}

@app.post("/api/", response_model=QueryResponse)
async def answer_question(query: QueryRequest):
    question = query.question.strip()

    if query.image_base64:
        try:
            image_data = base64.b64decode(query.image_base64)
            image = Image.open(BytesIO(image_data))
            extracted_text = pytesseract.image_to_string(image)
            question += " " + extracted_text
        except Exception as e:
            print("OCR error:", e)

    course_matches = search_json_for_answer(course_data, question)
    if course_matches:
        return QueryResponse(
            answer=course_matches[0],
            references={"source": "course_content.json"},
            links={"source": "course_content.json"},
        )

    discourse_matches = search_json_for_answer(discourse_data, question)
    if discourse_matches:
        best_match = discourse_matches[0]
        for post in discourse_data:
            if post["excerpt"] in best_match:
                return QueryResponse(
                    answer=post["excerpt"],
                    references={post["title"]: post["url"]},
                    links={post["title"]: post["url"]},
                )

    return QueryResponse(
        answer="Sorry, I couldn't find an answer based on the available data.",
        references={},
        links={}
    )
