# 🍷 WinePair AI

WinePair AI (codename: **wine-adk**) is a virtual sommelier powered by **Google ADK** and **Gemini 2.0 Flash**.  
It uses a **content-based recommendation system** to suggest wines similar to ones a user already enjoys, then delivers friendly, natural explanations through an AI sommelier agent.

---

## 🚀 Features
- 🧠 **Content-based recommender** using TF-IDF + cosine similarity (`pandas`, `scikit-learn`)
- 🤖 **Sommelier agent** built with `google-adk` + `google-generativeai`
- ⚡ **FastAPI backend** for serving recommendations and agent responses
- 🌐 **ADK Web** interface for local chat and testing

---

## 🧩 Tech Stack
| Component | Library |
|------------|----------|
| Backend API | FastAPI + Uvicorn |
| Recommender Engine | scikit-learn, pandas, numpy |
| Agent Framework | google-adk, google-generativeai |
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
```

### 4️⃣ Start the FastAPI app
```bash
uvicorn main:app --reload
```

Then open **ADK Web** in your browser if enabled in `main.py`.

---

## 🧾 Example Use
**User:** “I like Cabernet Sauvignon.”  
**System:** (backend finds similar wines via TF-IDF vectors)  
**Agent:** “You might enjoy a Merlot — smooth, fruity, and balanced like your Cabernet favorite.”

---

## 🧪 Methodology
The recommendation engine computes a **TF-IDF matrix** of all wine descriptions and uses **cosine similarity** to find wines with the most similar flavor profiles and attributes to the user’s input wine.
