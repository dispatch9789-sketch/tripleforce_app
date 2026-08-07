"""Gunicorn production configuration for Triple Force Logistic LLC."""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = 4
worker_class = "sync"
timeout = 120
keepalive = 5
errorlog = "-"
accesslog = "-"
loglevel = "info"
capture_output = True
enable_stdio_inheritance = True
