from fastapi import FastAPI
from pydantic import BaseModel
from collections import defaultdict
import random

app = FastAPI()

reviews = defaultdict(list)

sample_reviews = [
    "Excellent produit 🔥",
    "Très bonne qualité",
    "Livraison rapide",
    "Je recommande",
    "Bon rapport qualité/prix"
]

class Review(BaseModel):
    message: str

@app.post("/reviews/{product_id}")
def add_review(product_id: str, review: Review):
    reviews[product_id].append(review.message)
    return {"status": "added"}

@app.get("/reviews/{product_id}")
def get_reviews(product_id: str):
    return {"reviews": reviews[product_id][-10:]}
