from celery import Celery
from src.config import settings

celery = Celery("rootsignal", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.task_serializer = "json"
celery.conf.result_serializer = "json"
celery.conf.accept_content = ["json"]
celery.autodiscover_tasks(["src.tasks"])
