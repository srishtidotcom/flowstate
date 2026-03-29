Now I have everything I need. Here's the complete step-by-step guide:

Running Flowstate with a WhatsApp chat.txt
⚠️ One important thing to know first — chat format
The normalizer only handles the iOS WhatsApp export format, where each line starts with [:

Code
[12/03/2024, 09:14:32] Alice: Can you finish the slides by Friday?
[12/03/2024, 09:15:01] Bob: Yes, I'll send them over by EOD Thursday.
If you exported from Android, the format is different (DD/MM/YYYY, HH:MM - Name: message) and the parser will skip every line and return zero chunks. You'd need to convert it first or tweak the parser. iOS export = works as-is.

Step 1 — One-time setup (only needed the first time)
bash
cd /path/to/flowstate

# Create your .env from the template
cp .env.example .env

# Create Python virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
Step 2 — Start infrastructure (Redis + PostgreSQL + ChromaDB)
bash
# From the repo root, in a terminal you can leave running
docker compose -f docker/docker-compose.yml up -d
Verify it's up:

bash
docker compose -f docker/docker-compose.yml ps
You should see postgres, chromadb, and redis all showing running.

Step 3 — Start Ollama with the Mistral model
In a new terminal:

bash
# Start the Ollama server (runs in foreground)
ollama serve
In a second new terminal, pull the model (only needed once):

bash
ollama pull mistral
Verify it works:

bash
curl http://localhost:11434/api/tags
# Should list "mistral" in the models array
Step 4 — Start the FastAPI backend
In a new terminal (with venv activated):

bash
cd /path/to/flowstate
source venv/bin/activate
uvicorn backend.api.main:app --port 8001 --reload
Verify:

bash
curl http://localhost:8001/
# Should return: {"status":"Flowstate is running"}
Step 5 — Start the worker
In a new terminal (with venv activated):

bash
cd /path/to/flowstate
source venv/bin/activate
python -m backend.worker
You should see:

Code
Worker is listening for jobs...
Step 6 — Upload your chat.txt and watch it process
bash
curl -X POST http://localhost:8001/upload \
  -F "file=@/path/to/your/chat.txt" \
  -F "team_id=my-team"
You'll get back:

JSON
{"job_id": "abc-123-...", "status": "queued", "filename": "chat.txt"}
Switch to the worker terminal — within seconds you'll see the output:

Code
Processing job: abc-123-...
Got 47 chunks
Extracted 5 tasks:
  - Finish the slides | owner: Bob | deadline: Thursday | confidence: 0.92
  - Review the budget doc | owner: Alice | deadline: null | confidence: 0.78
  ...
All 5 terminal windows at a glance
Terminal	Command	Purpose
1	docker compose -f docker/docker-compose.yml up -d	Infrastructure (Redis, DB)
2	ollama serve	LLM inference server
3	uvicorn backend.api.main:app --port 8001 --reload	FastAPI API
4	python -m backend.worker	Async job processor
5	curl -X POST ...	Your upload command
Quick smoke-test without the full stack (no Docker, no Ollama)
If you just want to test the WhatsApp parser in isolation without any services running:

Python
# run from repo root with venv active: python /tmp/test_parse.py
import sys
sys.path.insert(0, ".")
from backend.preprocessing.normalizer import normalize

chunks = normalize("/path/to/your/chat.txt", ".txt")
print(f"Parsed {len(chunks)} messages")
for c in chunks[:5]:
    print(f"  [{c.speaker}]: {c.text}")
This lets you confirm your chat.txt is in the right format and is being parsed correctly before firing up all the services.