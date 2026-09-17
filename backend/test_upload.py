"""测试文件上传解析的完整过程"""
import httpx

# 1. 登录获取 token
print("="*70)
print("步骤 1: 登录获取 token")
print("="*70)
login_resp = httpx.post("http://127.0.0.1:8000/api/auth/login", 
                        json={"code": "test123", "nickname": "测试用户"})
token = login_resp.json()["token"]
print(f"Token: {token[:50]}...\n")

# 2. 上传文件
print("="*70)
print("步骤 2: 上传 Markdown 文件")
print("="*70)
headers = {"Authorization": f"Bearer {token}"}

with open("test_sample.md", "rb") as f:
    files = {"file": ("test_sample.md", f, "text/markdown")}
    upload_resp = httpx.post("http://127.0.0.1:8000/api/questions/upload", 
                             headers=headers, files=files, timeout=120)

if upload_resp.status_code == 200:
    result = upload_resp.json()
    print(f"\n解析结果：")
    print(f"  文件名：{result['filename']}")
    print(f"  题目数量：{len(result['items'])}")
    for i, item in enumerate(result['items'], 1):
        print(f"\n  题目 #{i}:")
        print(f"    Q: {item['question'][:80]}...")
        print(f"    A: {item['answer'][:60]}...")
        print(f"    技术栈：{item['tech_stack']}")
        print(f"    难度：{item['difficulty']}")
else:
    print(f"上传失败：{upload_resp.status_code}")
    print(upload_resp.text)
