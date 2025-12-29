import urllib.request
import urllib.parse
import json
import os
import sys

from tests import test_http_latency, test_download_speed

from pathlib import Path

# 获取 main.py 所在目录
BASE_DIR = Path(__file__).resolve().parent

CONFIG_FILE = BASE_DIR / "config.json"

def print_red(msg):
    print(f"\033[31m{msg}\033[0m")

if not os.path.exists(CONFIG_FILE):
    print_red(f"[ERROR] Config file {CONFIG_FILE} not found.")
    sys.exit(1)  # 退出程序

try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
except json.JSONDecodeError as e:
    print_red(f"[ERROR] Config file {CONFIG_FILE} format error: {e}")
    sys.exit(1)

# 读取配置变量
try:
    API_BASE = config["API_BASE"]
    API_KEY = config["API_KEY"]
    selector_name = config["selector_name"]
    keywords = config["keywords"]
    latency_test_urls = config["latency_test_urls"]
    download_speed_test_urls = [tuple(item) for item in config["download_speed_test_urls"]]
except KeyError as e:
    print_red(f"[ERROR] Config file missing required field {e}")
    sys.exit(1)

# 测试打印
print("\nConfig loaded successfully:\n")
print(f"API_BASE = {API_BASE}")
print(f"API_KEY = {API_KEY}")
print(f"selector_name = {selector_name}")
print(f"keywords = {keywords}")
print(f"latency_test_urls = {latency_test_urls}")
print(f"download_speed_test_urls = {download_speed_test_urls}")


encoded_selector_name = urllib.parse.quote(selector_name, safe='')

select_node_url = f"{API_BASE}/proxies/{encoded_selector_name}"

get_headers = {
    "Authorization": f"Bearer {API_KEY}"
}

put_headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

get_node_list_url = f"{API_BASE}/proxies"

def get_proxies():
    req = urllib.request.Request(get_node_list_url, headers=get_headers, method="GET")
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    return data

def select_node(node_name: str):
    data = json.dumps({
        "name": node_name
    }).encode('utf-8')

    req = urllib.request.Request(select_node_url, headers=put_headers, data=data, method="PUT")
    with urllib.request.urlopen(req) as resp:
        status_code = resp.status
        return status_code
    


if __name__ == "__main__":
    print("\nFetching node list...")
    data = get_proxies()
    node_list = data["proxies"][selector_name]["all"]
    current_node = data["proxies"][selector_name]["now"]

    # 筛选
    filtered_nodes = [node for node in node_list if any(kw in node for kw in keywords)]
    results = []

    for node_name in filtered_nodes:
        print("\n\nTesting node:", node_name)
        
        status_code = select_node(node_name)
        if(status_code == 204):
            print("Node switched successfully.")
        else:
            print_red("Failed to switch node, status code:")
            print_red(status_code)

        print("Running latency and speed tests...")

        try:
            latency = test_http_latency(latency_test_urls)
            speed = test_download_speed(download_speed_test_urls)
            print("------------------------------------------------------------")

            # 如果任意测试失败，跳过该节点
            if latency is False or speed is False:
                print_red(f"Node {node_name} failed tests, skipping...")
                continue

            results.append({
                "node": node_name,
                "latency": latency,
                "speed": speed
            })
        except Exception as e:
            print_red(f"Node {node_name} failed:")
            print_red(str(e))

    # 按下载速度从高到低排序
    results.sort(key=lambda x: x["speed"], reverse=True)

    # 打印排序后的结果
    print("\n\n\n")
    print_red("|==========================================================|")
    print_red("|========================= Results ========================|")
    print_red("|==========================================================|")
    
    for r in results:
        print(f"Node: {r['node']}\t\tSpeed: {r['speed']} MB/s\tLatency: {r['latency']} ms")

    # 切换回当前节点
    print("\nSwitching back to the original node:", current_node)
    status_code = select_node(current_node)
    if(status_code == 204):
        print("Switched back successfully.")
    else:   
        print("Failed to switch back, status code:", status_code)
