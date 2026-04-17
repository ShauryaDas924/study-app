from redis import Redis
from rq import Queue

redis_conn = Redis(host="localhost", port=6379, db=0)
concept_queue = Queue("concept-extraction", connection=redis_conn)
