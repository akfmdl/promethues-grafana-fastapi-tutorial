import asyncio
import random
import time

import psutil
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

app = FastAPI(redirect_slashes=False)

# 메트릭에서 제외할 경로 목록
EXCLUDED_PATHS = ["/favicon.ico", "/docs", "/redoc", "/openapi.json", "/metrics"]

# Prometheus 메트릭 생성
REQUESTS = Counter("app_requests_total", "Total count of requests by method and path.", ["method", "path"])

RESPONSES = Counter(
    "app_responses_total",
    "Total count of responses by method, path and status codes.",
    ["method", "path", "status_code"],
)

REQUESTS_PROCESSING_TIME = Histogram(
    "app_requests_processing_time_seconds",
    "Histogram of requests processing time by path (in seconds)",
    ["method", "path"],
)

# 메모리 사용량을 모니터링하는 Gauge 메트릭
MEMORY_USAGE = Gauge("app_memory_usage_bytes", "Current memory usage of the application in bytes", ["type"])


# Prometheus 메트릭을 직접 경로로 제공
@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    method = request.method
    path = request.url.path

    # 메모리 사용량 업데이트
    process = psutil.Process()
    MEMORY_USAGE.labels(type="rss").set(process.memory_info().rss)
    MEMORY_USAGE.labels(type="vms").set(process.memory_info().vms)

    # 메트릭 수집에서 제외할 경로 체크 (모니터링에서 제외할 경로)
    if path not in EXCLUDED_PATHS:
        REQUESTS.labels(method=method, path=path).inc()

        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        status_code = response.status_code
        RESPONSES.labels(method=method, path=path, status_code=status_code).inc()
        REQUESTS_PROCESSING_TIME.labels(method=method, path=path).observe(process_time)

        return response
    else:
        return await call_next(request)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/random_sleep")
async def random_sleep():
    process_time = random.uniform(0.1, 0.5)
    await asyncio.sleep(process_time)
    return JSONResponse(content={"process_time": process_time}, status_code=200)


@app.get("/health")
async def health_check():
    return JSONResponse(content={"status": "ok"}, status_code=200)
