from fastapi import FastAPI
from pydantic import BaseModel
from collections import defaultdict
from threading import Lock
import random
import time

app = FastAPI(title="reviewservice")

reviews = defaultdict(list)
lock = Lock()
MAX_REVIEWS = 4

sample_reviews = [
    "Excellent produit",
    "Très bonne qualité",
    "Livraison rapide",
    "Je recommande",
    "Bon rapport qualité/prix",
    "Top",
    "Service impeccable",
]

first_names = ["Lucas", "Emma", "Nathan", "Lina", "Hugo", "Jade"]
last_names = ["Martin", "Bernard", "Petit", "Robert", "Richard", "Durand"]


class Review(BaseModel):
    message: str


def random_author():
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def random_rating():
    return random.randint(3, 5)


@app.post("/reviews/{product_id}")
def add_review(product_id: str, review: Review):
    with lock:
        current = reviews[product_id]

        current.append({
            "message": review.message,
            "rating": random_rating(),
            "author": random_author(),
            "timestamp": int(time.time())
        })

        if len(current) > MAX_REVIEWS:
            current.pop(0)

        avg = round(sum(r["rating"] for r in current) / len(current), 1)

        return {
            "reviews": current,
            "average": avg,
            "count": len(current)
        }


@app.get("/reviews/{product_id}")
def get_reviews(product_id: str):
    with lock:
        current = reviews[product_id]

        if not current:
            for _ in range(4):
                current.append({
                    "message": random.choice(sample_reviews),
                    "rating": random_rating(),
                    "author": random_author(),
                    "timestamp": int(time.time())
                })

        avg = round(sum(r["rating"] for r in current) / len(current), 1)

        return {
            "reviews": current,
            "average": avg,
            "count": len(current)
        }
