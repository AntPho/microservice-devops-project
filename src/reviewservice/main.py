from fastapi import FastAPI
from pydantic import BaseModel
from threading import Lock
import random
import time
import json
import redis

from prometheus_client import Counter, Gauge, Histogram, generate_latest
from fastapi.responses import Response

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

REVIEW_POSTS_TOTAL = Counter(
    "review_posts_total",
    "Total reviews submitted",
    ["product_id", "product_name"]
)

REVIEW_AVERAGE = Gauge(
    "review_average_rating",
    "Average rating per product",
    ["product_id", "product_name"]
)

REVIEW_COUNT = Gauge(
    "review_count",
    "Total number of ratings per product",
    ["product_id", "product_name"]
)

REQUEST_LATENCY = Histogram(
    "review_request_latency_seconds",
    "Latency of review API"
)


class Review(BaseModel):
    message: str


def random_author():
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def random_rating():
    return random.randint(3, 5)


def sync_metrics(product_id: str):
    product_name = PRODUCT_NAMES.get(product_id, product_id)

    stats = r.hgetall(f"rating:{product_id}")
    count = int(stats.get("count", 0))
    total = int(stats.get("sum", 0))

    if count == 0:
        return

    avg = total / count

    REVIEW_AVERAGE.labels(
        product_id=product_id,
        product_name=product_name
    ).set(avg)

    REVIEW_COUNT.labels(
        product_id=product_id,
        product_name=product_name
    ).set(count)


def build_response(product_id):
    stats = r.hgetall(f"rating:{product_id}")
    review_list = r.lrange(f"reviews:{product_id}", 0, DISPLAY_LIMIT - 1)

    count = int(stats.get("count", 0))
    total = int(stats.get("sum", 0))
    avg = round(total / count, 1) if count > 0 else 0

    parsed_reviews = [json.loads(x) for x in review_list]

    return {
        "reviews": parsed_reviews,
        "average": avg,
        "count": count
    }


@app.on_event("startup")
def load_metrics_from_redis():
    for key in r.scan_iter("rating:*"):
        product_id = key.split(":")[1]
        sync_metrics(product_id)


@app.post("/reviews/{product_id}")
def add_review(product_id: str, review: Review):
    start = time.time()

    with lock:
        rating = random_rating()
        product_name = PRODUCT_NAMES.get(product_id, product_id)

        # Persist stats
        stats_key = f"rating:{product_id}"
        r.hincrby(stats_key, "sum", rating)
        r.hincrby(stats_key, "count", 1)

        # Persist latest 4 reviews
        review_key = f"reviews:{product_id}"
        r.lpush(review_key, json.dumps({
            "message": review.message,
            "rating": rating,
            "author": random_author(),
            "timestamp": int(time.time())
        }))
        r.ltrim(review_key, 0, DISPLAY_LIMIT - 1)

        # Prometheus metrics
        REVIEW_POSTS_TOTAL.labels(
            product_id=product_id,
            product_name=product_name
        ).inc()

        sync_metrics(product_id)

        REQUEST_LATENCY.observe(time.time() - start)

        return build_response(product_id)


@app.get("/reviews/{product_id}")
def get_reviews(product_id: str):
    with lock:
        stats = r.hgetall(f"rating:{product_id}")

        # Seed automatique si produit jamais vu
        if not stats:
            for _ in range(4):
                rating = random_rating()

                stats_key = f"rating:{product_id}"
                r.hincrby(stats_key, "sum", rating)
                r.hincrby(stats_key, "count", 1)

                review_key = f"reviews:{product_id}"
                r.rpush(review_key, json.dumps({
                    "message": random.choice(sample_reviews),
                    "rating": rating,
                    "author": random_author(),
                    "timestamp": int(time.time())
                }))

            sync_metrics(product_id)

        return build_response(product_id)


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
