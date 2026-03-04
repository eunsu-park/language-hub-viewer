"""Gunicorn configuration for production deployment."""
from multiprocessing import cpu_count

bind = "127.0.0.1:5060"
workers = min(cpu_count(), 4)
worker_class = "sync"
timeout = 120
preload_app = True
accesslog = "-"
errorlog = "-"
loglevel = "info"
