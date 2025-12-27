import urllib.request
import ssl
import time
import os
import http.client
from urllib.parse import urlparse

CHUNK_SIZE = 1024 * 256  # 256 KB

# 创建不验证 SSL 证书的上下文
ctx = ssl._create_unverified_context()


def download_speed(url: str, max_bytes=10*1024*1024):
    CHUNK = 1024 * 16              # 小块读取
    CHECK_INTERVAL = 3.0           # 每3秒检查一次
    MIN_BYTES = 3 * 1024 * 1024    # 3MB

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "speedtest/1.0"}
    )

    total_bytes = 0
    start_time = time.time()
    interval_bytes = 0
    interval_start = start_time

    with urllib.request.urlopen(req, timeout=10) as resp:
        while True:
            chunk = resp.read(CHUNK)
            if not chunk:
                break

            # 累计下载量
            total_bytes += len(chunk)
            interval_bytes += len(chunk)
            now = time.time()

            # 每CHECK_INTERVAL秒检查一次
            if now - interval_start >= CHECK_INTERVAL:
                if interval_bytes < MIN_BYTES:
                    elapsed = now - start_time
                    return {
                        "timeout": True,
                        "reason": f"Downloaded < {MIN_BYTES/(1024*1024)} MB in {CHECK_INTERVAL}s",
                        "speed": round(interval_bytes/(1024*1024)/(now - interval_start), 2),
                        "elapsed": round(elapsed, 2),
                    }
                interval_bytes = 0
                interval_start = now

            # 达到最大下载量就终止
            if total_bytes >= max_bytes:
                break

    # 下载完成（或达到 max_bytes）
    elapsed = time.time() - start_time
    final_speed = (total_bytes / (1024*1024)) / elapsed if elapsed > 0 else 0.0
    return {
        "timeout": False,
        "speed": round(final_speed, 2),
        "elapsed": round(elapsed, 2),
        "downloaded_MB": round(total_bytes / (1024*1024), 2)
    }


# 时延测试

test_latency_urls = [
    "https://www.google.com",
    "https://www.github.com",
    "https://www.youtube.com",
    "https://www.chatgpt.com",
]

DEFAULT_TIMEOUT = 8


def http_latency(url: str):
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"

    context = ssl.create_default_context()

    # ---- 读取环境变量中的代理 ----
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    http_proxy  = os.environ.get("HTTP_PROXY")  or os.environ.get("http_proxy")

    use_proxy = https_proxy if parsed.scheme == "https" else http_proxy

    start = time.time()

    try:
        if use_proxy:
            # 解析 proxy 地址
            proxy = urlparse(use_proxy)

            # 连接到代理
            conn = http.client.HTTPSConnection(
                proxy.hostname,
                proxy.port,
                timeout=8,
                context=context
            ) if parsed.scheme == "https" else http.client.HTTPConnection(
                proxy.hostname,
                proxy.port,
                timeout=8
            )

            # 为目标站点打隧道
            conn.set_tunnel(host)

        else:
            # 直连
            conn = http.client.HTTPSConnection(
                host,
                timeout=8,
                context=context
            ) if parsed.scheme == "https" else http.client.HTTPConnection(
                host,
                timeout=8
            )

        conn.request("GET", path, headers={"User-Agent": "latency-test/1.0"})
        resp = conn.getresponse()
        resp.read(1024)

        elapsed_ms = round((time.time() - start) * 1000, 2)
        conn.close()

        return True, resp.status, elapsed_ms

    except Exception as e:
        return False, None, -1
    
def test_download_speed(urls):

    print("\n---------------- Download Speed Test (MB/s) ----------------")

    avg_speed = 0.0
    counter = 0

    for name, url in urls:
        print(f"\nTesting {name}: {url}")
        try:
            result = download_speed(url)

            if result["timeout"]:
                print(f"[TIMEOUT] {result['reason']}")
                print(f"Elapsed: {result['elapsed']} s")
                print(f"Speed:   {result['speed']} MB/s")
                return False
            else:
                print(f"Time:  {result['elapsed']} s")
                print(f"Speed: {result['speed']} MB/s")
                avg_speed += result['speed']
                counter += 1

        except Exception as e:
            print(f"Failed: {e}")
            return False

    if counter > 0:
        avg_speed = round(avg_speed / counter, 2)
        print(f"\nAverage Speed: {avg_speed} MB/s")
        return avg_speed
    
def test_http_latency(urls):

    print("\n-------------------- HTTP Latency Test ---------------------")
    avg_latency = 0.0
    counter = 0

    for site in urls:
        ok, status, result = http_latency(site)
        if ok:
            print(f"\n{site:<25}  status={status}   latency={result} ms")
            avg_latency += result
            counter += 1
        else:
            print(f"\n{site:<25}  FAILED: {result}")
            return False
        
    if counter > 0:
        avg_latency = round(avg_latency / counter, 2)
        print(f"\nAverage Latency: {avg_latency} ms")
        return avg_latency