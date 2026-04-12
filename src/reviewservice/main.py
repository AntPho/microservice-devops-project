from fastapi import FastAPI
from pydantic import BaseModel
from collections import defaultdict
from threading import Lock
import random
import time
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from fastapi.responses import Response

app = FastAPI(title="reviewservice")

# seulement les 4 derniers commentaires
reviews = defaultdict(list)

# stats globales infinies
rating_stats = defaultdict(lambda: {"sum": 0, "count": 0})

lock = Lock()
DISPLAY_LIMIT = 4

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

REVIEW_POSTS_TOTAL = Counter(
    "review_posts_total",
    "Total reviews submitted",
    ["product_id","product_name"]
)

REVIEW_AVERAGE = Gauge(
    "review_average_rating",
    "Average rating per product",
    ["product_id","product_name"]
)

REVIEW_COUNT = Gauge(
    "review_count",
    "Total number of ratings per product",
    ["product_id","product_name"]
)

REQUEST_LATENCY = Histogram(
    "review_request_latency_seconds",
    "Latency of review API"
)

PRODUCT_NAMES = {
    "OLJCESPC7Z": "Sunglasses",
    "66VCHSJNUP": "Tank Top",
    "1YMWWN1N4O": "Watch",
    "2ZYFJ3GM2N": "Hairdryer",
    "L9ECAV7KIM": "Loafers",
    "0PUK6V6EV0": "Candle Holder",
    "LS4PSXUNUM": "Salt & Pepper Shakers",
    "9SIQT8TOJO": "Bamboo Glass Jar",
    "6E92ZMYYFZ": "Mug",
    "PATATE1": "Grosse Patate",
}

class Review(BaseModel):
    message: str


def random_author():
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def random_rating():
    return random.randint(3, 5)


def build_response(product_id):
    current = reviews[product_id]
    stats = rating_stats[product_id]

    avg = round(stats["sum"] / stats["count"], 1) if stats["count"] > 0 else 0

    return {
        "reviews": current,
        "average": avg,
        "count": stats["count"]
    }


@app.post("/reviews/{product_id}")
def add_review(product_id: str, review: Review):
    start = time.time()
    with lock:
        rating = random_rating()

        # update stats infinies
        rating_stats[product_id]["sum"] += rating
        rating_stats[product_id]["count"] += 1

        # seulement les 4 derniers commentaires
        current = reviews[product_id]
        current.append({
            "message": review.message,
            "rating": rating,
            "author": random_author(),
            "timestamp": int(time.time())
        })

        if len(current) > DISPLAY_LIMIT:
            current.pop(0)

        product_name = PRODUCT_NAMES.get(product_id, product_id)

        REVIEW_POSTS_TOTAL.labels(
          product_id=product_id,
          product_name=product_name
        ).inc()

        avg = rating_stats[product_id]["sum"] / rating_stats[product_id]["count"]

        REVIEW_AVERAGE.labels(
            product_id=product_id,
            product_name=product_name
        ).set(avg)

        REVIEW_COUNT.labels(
            product_id=product_id,
            product_name=product_name
        ).set(rating_stats[product_id]["count"])

        REQUEST_LATENCY.observe(time.time() - start)
        
        return build_response(product_id)


@app.get("/reviews/{product_id}")
def get_reviews(product_id: str):
    with lock:
        current = reviews[product_id]

        # seed initial uniquement si aucune stat
        if rating_stats[product_id]["count"] == 0:
            for _ in range(4):
                rating = random_rating()

                rating_stats[product_id]["sum"] += rating
                rating_stats[product_id]["count"] += 1

                current.append({
                    "message": random.choice(sample_reviews),
                    "rating": rating,
                    "author": random_author(),
                    "timestamp": int(time.time())
                })

        return build_response(product_id)

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
