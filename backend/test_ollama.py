"""直接测试 Ollama API"""
import httpx
import json

print("测试 Ollama API...")
print("="*60)

# 1. 检查可用模型
print("\n1. 检查可用模型:")
resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
if resp.status_code == 200:
    models = [m["name"] for m in resp.json().get("models", [])]
    print(f"   可用模型：{models}")
else:
    print(f"   获取模型失败：{resp.status_code}")

# 2. 测试 /api/chat 接口
print("\n2. 测试 /api/chat 接口 (qwen3.5:2b):")
resp = httpx.post(
    "http://localhost:11434/api/chat",
    json={
        "model": "qwen3.5:2b",
        "messages": [{"role": "user", "content": "1+1 等于几？"}],
        "stream": False
    },
    timeout=30
)
print(f"   状态码：{resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"   完整响应：{json.dumps(data, ensure_ascii=False, indent=2)[:500]}")
    message = data.get("message", {})
    content = message.get("content", "")
    print(f"   回复内容：{content}")
else:
    print(f"   错误：{resp.text}")

# 3. 测试 /api/generate 接口
print("\n3. 测试 /api/generate 接口 (qwen3.5:2b):")
resp = httpx.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen3.5:2b",
        "prompt": "1+1 等于几？",
        "stream": False
    },
    timeout=30
)
print(f"   状态码：{resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    response = data.get("response", "")
    print(f"   回复内容：{response}")
    print(f"   完整响应键：{list(data.keys())}")
else:
    print(f"   错误：{resp.text}")

# 4. 测试其他模型
print("\n4. 测试 deepseek-r1:7b 模型:")
resp = httpx.post(
    "http://localhost:11434/api/chat",
    json={
        "model": "deepseek-r1:7b",
        "messages": [{"role": "user", "content": "1+1 等于几？"}],
        "stream": False
    },
    timeout=30
)
print(f"   状态码：{resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    message = data.get("message", {})
    content = message.get("content", "")
    print(f"   回复内容：{content[:200]}")
else:
    print(f"   错误：{resp.text}")

print("\n" + "="*60)
print("测试完成")
