"""AI 服务：通过 ollama Python 库调用本地大模型"""
import json
import logging
import time
import re

logger = logging.getLogger(__name__)

OLLAMA_MODEL = "qwen3.5:2b"  # 默认模型
FALLBACK_MODELS = ["qwen3:4b", "qwen2.5:7b", "llama3.2:3b", "deepseek-r1:7b"]

AVAILABLE_MODEL = None

# 技术栈列表
TECH_STACKS = [
    "Python", "Java", "Go", "C/C++", "Rust", "JavaScript", "TypeScript",
    "C#", "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R",
    "React", "Vue", "Angular", "HTML/CSS", "小程序", "Node.js",
    "Django", "Flask", "FastAPI", "Spring Boot", "Express", "Gin",
    "AI 大模型", "机器学习", "深度学习", "NLP", "计算机视觉",
    "数据分析", "数据挖掘", "推荐系统",
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
    "Docker", "Kubernetes", "Linux", "Nginx", "DevOps", "CI/CD",
    "TCP/IP", "HTTP", "网络安全", "密码学",
    "算法", "数据结构", "操作系统", "分布式系统", "微服务",
    "区块链", "嵌入式", "游戏开发", "测试", "其他",
]

DIFFICULTY_LEVELS = ["简单", "中等", "困难"]


def _check_available_model():
    """检查 Ollama 中可用的模型"""
    global AVAILABLE_MODEL
    
    if AVAILABLE_MODEL:
        return AVAILABLE_MODEL
    
    # 懒加载 ollama 库，避免后端启动时因 ollama 不可用而崩溃
    try:
        from ollama import list as ollama_list
    except ImportError:
        logger.warning("ollama 库未安装，AI 功能不可用")
        AVAILABLE_MODEL = None
        return None
    
    try:
        models_response = ollama_list()
        models = [m.model for m in models_response.get("models", [])]
        logger.info(f"Ollama 可用模型：{models}")
        
        # 优先使用默认模型
        if OLLAMA_MODEL in models:
            AVAILABLE_MODEL = OLLAMA_MODEL
        else:
            # 尝试备用模型
            for fallback in FALLBACK_MODELS:
                if fallback in models:
                    AVAILABLE_MODEL = fallback
                    logger.warning(f"默认模型 {OLLAMA_MODEL} 不可用，使用备用模型：{fallback}")
                    break
        
        if not AVAILABLE_MODEL:
            logger.warning(f"未找到可用模型，AI 分析功能不可用")
            return None
        
        return AVAILABLE_MODEL
    except Exception as e:
        logger.warning(f"检查 Ollama 模型失败：{e}")
        AVAILABLE_MODEL = None
        return None


def analyze_question(question: str, answer: str = "", question_num: int = 0) -> dict:
    """
    通过大模型分析题目，返回技术栈和难度
    返回格式：{"tech_stack": "Python", "difficulty": 1}
    difficulty: 1=简单，2=中等，3=困难
    """
    if not question.strip():
        return {"tech_stack": "其他", "difficulty": 1}

    prompt = f"""请分析以下编程题目，判断它的技术栈分类和难度等级。

题目：{question}
答案：{answer if answer else '无'}

可选的技术栈分类（只能选一个最相关的）：
{', '.join(TECH_STACKS)}

可选的难度等级：
1 = 简单（基础概念、语法题）
2 = 中等（需要一定理解、应用场景）
3 = 困难（复杂原理、底层机制、综合应用）

请严格按照以下 JSON 格式返回，不要有其他内容：
{{"tech_stack": "技术栈名称", "difficulty": 1}}

只返回 JSON，不要解释。"""

    start_time = time.time()
    
    model_name = _check_available_model()
    if not model_name:
        logger.warning("无法获取可用模型，跳过 AI 分析")
        return {"tech_stack": "其他", "difficulty": 1}
    
    # 懒加载 chat 函数
    try:
        from ollama import chat
    except ImportError:
        logger.warning("ollama 库未安装，AI 功能不可用")
        return {"tech_stack": "其他", "difficulty": 1}
    
    max_retries = 3
    for retry in range(max_retries):
        try:
            response = chat(
                model=model_name,
                messages=[
                    {"role": "system", "content": "你是一个编程题目分析助手，只返回 JSON 格式的结果。"},
                    {"role": "user", "content": prompt}
                ],
                stream=False,
            )
            print(response)
            elapsed = time.time() - start_time
            response_text = (response.message.content or "").strip()
            
            logger.info(f"AI 响应时间：{elapsed:.2f}秒")
            
            if not response_text:
                if retry < max_retries - 1:
                    logger.warning(f"AI 返回空内容，第 {retry + 1} 次重试...")
                    time.sleep(1)
                    continue
                else:
                    logger.error("AI 多次返回空内容，使用默认值")
                    return {"tech_stack": "其他", "difficulty": 1}
            
            # 解析 JSON
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            response_text = response_text.strip()
            
            json_match = re.search(r'\{[^}]*"tech_stack"[^}]*"difficulty"[^}]*\}', response_text)
            if json_match:
                response_text = json_match.group(0)
            
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON 解析失败：{e}")
                if retry < max_retries - 1:
                    logger.warning(f"第 {retry + 1} 次重试...")
                    time.sleep(1)
                    continue
                else:
                    return _fallback_parse(response_text)
            
            tech_stack = result.get("tech_stack", "其他")
            if tech_stack not in TECH_STACKS:
                tech_stack = _fuzzy_match_tech_stack(tech_stack)
            
            difficulty = result.get("difficulty", 1)
            if difficulty not in [1, 2, 3]:
                difficulty = 1
            
            logger.info(f"分析结果：技术栈={tech_stack}, 难度={difficulty}")
            return {"tech_stack": tech_stack, "difficulty": difficulty}
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"请求异常：{e}")
            if retry < max_retries - 1:
                logger.warning(f"第 {retry + 1} 次重试...")
                time.sleep(1)
                continue
            return {"tech_stack": "其他", "difficulty": 1}
    
    return {"tech_stack": "其他", "difficulty": 1}


def analyze_batch(questions: list) -> list:
    """批量分析题目"""
    logger.info(f"开始 AI 批量分析，题目总数：{len(questions)}")
    
    results = []
    for i, q in enumerate(questions, 1):
        result = analyze_question(
            q.get("question", ""), 
            q.get("answer", ""),
            question_num=i
        )
        results.append(result)
    
    logger.info(f"AI 批量分析完成，共 {len(results)} 道题")
    return results


def _fuzzy_match_tech_stack(tech_stack: str) -> str:
    """模糊匹配技术栈"""
    if not tech_stack:
        return "其他"
    
    tech_stack_lower = tech_stack.lower()
    
    for ts in TECH_STACKS:
        if ts.lower() in tech_stack_lower or tech_stack_lower in ts.lower():
            return ts
    
    keyword_map = {
        "python": "Python", "java": "Java", "go": "Go", "golang": "Go",
        "c++": "C/C++", "c": "C/C++", "rust": "Rust",
        "js": "JavaScript", "javascript": "JavaScript",
        "ts": "TypeScript", "typescript": "TypeScript",
        "react": "React", "vue": "Vue", "angular": "Angular",
        "node": "Node.js", "nodejs": "Node.js",
        "django": "Django", "flask": "Flask", "fastapi": "FastAPI",
        "spring": "Spring Boot",
        "mysql": "MySQL", "postgres": "PostgreSQL", "mongodb": "MongoDB",
        "redis": "Redis", "docker": "Docker",
        "k8s": "Kubernetes", "kubernetes": "Kubernetes", "linux": "Linux",
        "ai": "AI 大模型", "大模型": "AI 大模型", "llm": "AI 大模型",
        "ml": "机器学习", "机器学习": "机器学习",
        "深度学习": "深度学习", "dl": "深度学习",
    }
    
    for keyword, ts in keyword_map.items():
        if keyword in tech_stack_lower:
            return ts
    
    return "其他"


def _fallback_parse(text: str) -> dict:
    """从 AI 回复文本中尝试提取技术栈和难度"""
    result = {"tech_stack": "其他", "difficulty": 1}
    
    difficulty_patterns = [
        r'难度["\s]*[:：]?["\s]*(\d)',
        r'difficulty["\s]*[:：]?["\s]*(\d)',
        r'(简单|中等|困难)',
    ]
    
    for pattern in difficulty_patterns:
        match = re.search(pattern, text)
        if match:
            val = match.group(1)
            if val in ['1', '2', '3']:
                result["difficulty"] = int(val)
                break
            elif val == '简单':
                result["difficulty"] = 1
                break
            elif val == '中等':
                result["difficulty"] = 2
                break
            elif val == '困难':
                result["difficulty"] = 3
                break
    
    for ts in TECH_STACKS:
        if ts in text:
            result["tech_stack"] = ts
            break
    
    logger.info(f"降级解析结果：技术栈={result['tech_stack']}, 难度={result['difficulty']}")
    return result


def generate_quiz_questions(questions: list) -> list:
    """
    使用大模型为题目生成答题选项和解析
    questions: 题目对象列表
    返回：[{"id": 1, "question": "...", "options": [...], "correct_answer": "...", "explanation": "..."}, ...]
    """
    from ..schemas.public_question import QuizQuestion
    
    quiz_questions = []
    
    for q in questions:
        question_text = q.title if hasattr(q, 'title') else q.content
        answer = q.answer if hasattr(q, 'answer') else ""
        question_id = q.id if hasattr(q, 'id') else 0
        tech_stack = q.tech_stack if hasattr(q, 'tech_stack') else ""
        difficulty = q.difficulty if hasattr(q, 'difficulty') else 1
        
        prompt = f"""请为以下编程题目生成 4 个选择题选项（其中 1 个正确答案，3 个干扰项），并给出简要解析。

题目：{question_text}
正确答案：{answer if answer else '无'}

请按以下 JSON 格式返回：
{{
  "options": ["选项 A", "选项 B", "选项 C", "选项 D"],
  "correct_answer": "正确选项的完整内容",
  "explanation": "简要解析"
}}

只返回 JSON，不要解释。"""
        
        logger.info(f"生成题目 {question_id} 的选项...")
        
        try:
            model_name = _check_available_model()
            if not model_name:
                # 降级：不生成选项
                quiz_questions.append(QuizQuestion(
                    id=question_id,
                    question=question_text,
                    options=[answer] if answer else [],
                    correct_answer=answer,
                    explanation="",
                    tech_stack=tech_stack,
                    difficulty=difficulty,
                ))
                continue
            
            # 懒加载 chat 函数
            try:
                from ollama import chat
            except ImportError:
                quiz_questions.append(QuizQuestion(
                    id=question_id,
                    question=question_text,
                    options=[answer] if answer else [],
                    correct_answer=answer,
                    explanation="",
                    tech_stack=tech_stack,
                    difficulty=difficulty,
                ))
                continue
            
            response = chat(
                model=model_name,
                messages=[
                    {"role": "system", "content": "你是一个编程题目生成助手，只返回 JSON 格式的结果。"},
                    {"role": "user", "content": prompt}
                ],
                stream=False,
            )
            
            response_text = (response.message.content or "").strip()
            logger.info(f"AI 回复：{response_text[:100]}...")
            
            # 解析 JSON
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            response_text = response_text.strip()
            
            json_match = re.search(r'\{[^}]*"options"[^}]*"correct_answer"[^}]*"explanation"[^}]*\}', response_text)
            if json_match:
                response_text = json_match.group(0)
            
            try:
                result = json.loads(response_text)
                options = result.get("options", [])
                correct_answer = result.get("correct_answer", answer)
                explanation = result.get("explanation", "")
            except json.JSONDecodeError:
                # 降级处理
                options = [answer] if answer else []
                correct_answer = answer
                explanation = ""
            
            quiz_questions.append(QuizQuestion(
                id=question_id,
                question=question_text,
                options=options,
                correct_answer=correct_answer,
                explanation=explanation,
                tech_stack=tech_stack,
                difficulty=difficulty,
            ))
            
        except Exception as e:
            logger.error(f"生成失败：{e}，使用降级方案")
            quiz_questions.append(QuizQuestion(
                id=question_id,
                question=question_text,
                options=[answer] if answer else [],
                correct_answer=answer,
                explanation="",
                tech_stack=tech_stack,
                difficulty=difficulty,
            ))
    
    return quiz_questions

