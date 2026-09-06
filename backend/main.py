from fastapi import FastAPI

app = FastAPI(
    title="Antarctic Navigation Decision Support System",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "message": "Antarctic Navigation Backend is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }