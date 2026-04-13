from fastapi import FastAPI
from pydantic import BaseModel
from collections import defaultdict
from threading import Lock
import json
import random
import time
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from fastapi.responses import Response
import redis

r = redis.Redis(host="redis", port=6379, decode_responses=True)

app = FastAPI(title="reviewservice")

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
    review_key = f"reviews:{product_id}"
    rating_key = f"rating:{product_id}"

    current = [
        json.loads(x)
        for x in r.lrange(review_key, 0, 3)
    ]

    stats = r.hgetall(rating_key)

    total_sum = int(stats.get("sum", 0))
    total_count = int(stats.get("count", 0))

    avg = round(total_sum / total_count, 1) if total_count > 0 else 0

    return {
        "reviews": current,
        "average": avg,
        "count": total_count
    }


@app.post("/reviews/{product_id}")
def add_review(product_id: str, review: Review):
    start = time.time()

    with lock:
        rating = random_rating()
        product_name = PRODUCT_NAMES.get(product_id, product_id)

        rating_key = f"rating:{product_id}"
        review_key = f"reviews:{product_id}"

        # stats infinies persistantes
        r.hincrby(rating_key, "sum", rating)
        r.hincrby(rating_key, "count", 1)

        stats = r.hgetall(rating_key)
        avg = int(stats["sum"]) / int(stats["count"])

        # garder seulement 4 derniers commentaires
        r.lpush(review_key, json.dumps({
            "message": review.message,
            "rating": rating,
            "author": random_author(),
            "timestamp": int(time.time())
        }))
        r.ltrim(review_key, 0, 3)

        REVIEW_POSTS_TOTAL.labels(
            product_id=product_id,
            product_name=product_name
        ).inc()

        REVIEW_AVERAGE.labels(
            product_id=product_id,
            product_name=product_name
        ).set(avg)

        REVIEW_COUNT.labels(
            product_id=product_id,
            product_name=product_name
        ).set(int(stats["count"]))

        REQUEST_LATENCY.observe(time.time() - start)

        return build_response(product_id)

@app.get("/reviews/{product_id}")
def get_reviews(product_id: str):
    with lock:
        rating_key = f"rating:{product_id}"
        review_key = f"reviews:{product_id}"
        product_name = PRODUCT_NAMES.get(product_id, product_id)

        stats = r.hgetall(rating_key)

        if not stats:
            total = 0

            for _ in range(4):
                rating = random_rating()
                total += rating

                r.lpush(review_key, json.dumps({
                    "message": random.choice(sample_reviews),
                    "rating": rating,
                    "author": random_author(),
                    "timestamp": int(time.time())
                }))

            r.hset(rating_key, mapping={
                "sum": total,
                "count": 4
            })

            avg = total / 4

            REVIEW_AVERAGE.labels(
                product_id=product_id,
                product_name=product_name
            ).set(avg)

            REVIEW_COUNT.labels(
                product_id=product_id,
                product_name=product_name
            ).set(4)

        return build_response(product_id)

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
