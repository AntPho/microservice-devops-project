from fastapi import FastAPI
from pydantic import BaseModel
from threading import Lock
import random
import time
import json
import redis

from prometheus_client import Counter, Gauge, Histogram, generate_latest
from fastapi.responses import Response

app = FastAPI(title="reviewservice")

# 🔗 Connexion Redis
r = redis.Redis(host="redis-cart", port=6379, decode_responses=True)

lock = Lock()
DISPLAY_LIMIT = 4

# 📊 Prometheus metrics
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

# 📦 Produits
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

# 🎲 Génération de données
first_names = ["Lucas", "Emma", "Nathan", "Lina", "Hugo", "Jade"]
last_names = ["Martin", "Bernard", "Petit", "Robert", "Richard", "Durand"]

sample_reviews = [
    "Excellent produit",
    "Très bonne qualité",
    "Livraison rapide",
    "Je recommande",
    "Bon rapport qualité/prix",
    "Top",
    "Service impeccable",
]

class Review(BaseModel):
    message: str


def random_author():
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def random_rating():
    return random.randint(3, 5)


# 🔄 Construction réponse depuis Redis uniquement
def build_response(product_id: str):
    review_key = f"reviews:{product_id}"
    rating_key = f"rating:{product_id}"

    redis_reviews = r.lrange(review_key, 0, -1)
    reviews_list = [json.loads(r) for r in redis_reviews]

    stats = r.hgetall(rating_key)

    if stats and "sum" in stats and "count" in stats:
        avg = int(stats["sum"]) / int(stats["count"])
        count = int(stats["count"])
    else:
        avg = 0
        count = 0

    return {
        "reviews": reviews_list,
        "average": round(avg, 1),
        "count": count
    }


# ➕ Ajouter review
@app.post("/reviews/{product_id}")
def add_review(product_id: str, review: Review):
    start = time.time()

    with lock:
        rating = random_rating()

        product_name = PRODUCT_NAMES.get(product_id, product_id)

        review_data = {
            "message": review.message,
            "rating": rating,
            "author": random_author(),
            "timestamp": int(time.time())
        }

        review_key = f"reviews:{product_id}"
        rating_key = f"rating:{product_id}"

        # 📌 Stockage Redis
        r.lpush(review_key, json.dumps(review_data))
        r.ltrim(review_key, 0, DISPLAY_LIMIT - 1)

        r.hincrby(rating_key, "sum", rating)
        r.hincrby(rating_key, "count", 1)

        # 📊 Calcul stats
        stats = r.hgetall(rating_key)
        avg = int(stats["sum"]) / int(stats["count"])
        count = int(stats["count"])

        # 📊 Metrics Prometheus
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
        ).set(count)

        REQUEST_LATENCY.observe(time.time() - start)

        return build_response(product_id)


# 📖 Lire reviews
@app.get("/reviews/{product_id}")
def get_reviews(product_id: str):
    with lock:
        review_key = f"reviews:{product_id}"
        rating_key = f"rating:{product_id}"

        # 🔥 Seed si vide
        if not r.exists(rating_key):
            for _ in range(4):
                rating = random_rating()

                review_data = {
                    "message": random.choice(sample_reviews),
                    "rating": rating,
                    "author": random_author(),
                    "timestamp": int(time.time())
                }

                r.lpush(review_key, json.dumps(review_data))
                r.ltrim(review_key, 0, DISPLAY_LIMIT - 1)

                r.hincrby(rating_key, "sum", rating)
                r.hincrby(rating_key, "count", 1)

        return build_response(product_id)


# 📈 Metrics endpoint
@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
