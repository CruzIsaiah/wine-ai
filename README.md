# 🍷 WinePair AI

WinePair AI is a grounded virtual sommelier powered by Google ADK and Gemini 3.6 Flash. It combines a deterministic TF-IDF recommendation engine, a validated FastAPI service, and grounded search for wines outside the local catalog.

## 🚀 Features
- 🧠 **Content-based recommender** using TF-IDF + cosine similarity (`pandas`, `scikit-learn`)
- 🤖 **Conversational manager** built with Google ADK and Gemini
- ⚡ **FastAPI backend** for serving recommendations and agent responses
- 🌐 **ADK Web** interface for local chat and testing
- 🎨 **Presentation website** with guided taste discovery and polished recommendation cards
- 🔎 **Grounded Google Search** fallback for unknown wines
- ✅ **13 automated tests** covering ranking, API behavior, and tool handoffs

---

## 🧩 Tech Stack
| Component | Library |
|------------|----------|
| Backend API | FastAPI + Uvicorn |
| Recommender Engine | scikit-learn, pandas, numpy |
| Agent Framework | google-adk, google-genai |
| Utilities | python-dotenv, requests |

---

## ⚙️ Setup & Run

### 1️⃣ Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2️⃣ Install dependencies
```bash
pip install -r requirements.txt
```

### 3️⃣ Add your API key
Create a `.env` file in the project root:
```
GOOGLE_API_KEY=your_api_key_here
API_RATE_LIMIT_PER_MINUTE=60
```

### 4️⃣ Start the FastAPI app
```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` to use the presentation-ready website. The frontend is served by FastAPI and calls the recommendation endpoints directly.

When a title is not in the local catalog, the similar-wine finder uses grounded Google Search to identify its style and tasting profile, then recommends the closest catalog matches.

### 5️⃣ Start ADK Web

```bash
adk web --port 8001 .
```

Open `http://127.0.0.1:8001` and select the `manager` app.

The API defaults to 60 requests per minute per client. Change `API_RATE_LIMIT_PER_MINUTE` in `.env` to adjust it. Requests above the limit receive HTTP `429` and a `Retry-After` header.

---

## 🧾 Example Use
**User:** “I like Cabernet Sauvignon.”  
**System:** (backend finds similar wines via TF-IDF vectors)  
**Agent:** “You might enjoy a Merlot — smooth, fruity, and balanced like your Cabernet favorite.”

---

## 🧪 Methodology
The recommendation engine builds a weighted TF-IDF matrix from wine type, style, characteristics, grape, description, region, and country. Explicit type and geographic preferences are applied as hard filters before cosine-similarity ranking.

## Tests

```bash
python -m pytest -q
```
