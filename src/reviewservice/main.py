from fastapi import FastAPI
from pydantic import BaseModel
from collections import defaultdict
from threading import Lock
import random
import time

app = FastAPI(title="reviewservice")

reviews = defaultdict(list)
lock = Lock()

sample_reviews = [
    "Excellent produit 🔥",
    "Très bonne qualité",
    "Livraison rapide",
    "Je recommande",
    "Bon rapport qualité/prix",
    "Top 👍",
    "Service impeccable",
]

class Review(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reviews/{product_id}")
def add_review(product_id: str, review: Review):
    with lock:
        reviews[product_id].append({
            "message": review.message,
            "timestamp": int(time.time())
        })

        # garder max 50 reviews
        reviews[product_id] = reviews[product_id][-50:]

    return {"status": "added"}


@app.get("/reviews/{product_id}")
def get_reviews(product_id: str):
    with lock:
        existing = reviews[product_id]

        # seed auto si vide (super pour démo)
        if not existing:
            existing.extend([
                {
                    "message": random.choice(sample_reviews),
                    "timestamp": int(time.time())
                }
                for _ in range(random.randint(3, 5))
            ])

        return {
            "reviews": [r["message"] for r in existing[-10:]]
        }
