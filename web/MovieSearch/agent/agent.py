import re
import json

from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

from .llm import build_chat_model
from .tools import movie_hybrid_search, start_search_trace, stop_search_trace


SYSTEM_PROMPT = """你是 MovieTOMT DeepAgent，一个用于“想不起电影名”场景的电影剧本检索主协调器。

你只能基于 movie_hybrid_search 工具或系统提供的 evidence 片段回答，不要编造数据库中没有的信息。

你的职责不是机械地每轮给答案，而是管理一个多轮找电影流程：
1. 理解当前用户消息，并结合当前会话历史整理已知线索。
2. 线索含糊时，优先委托 clue_extractor 分析线索是否足够。
3. 线索足够时，必须委托 movie_retriever 规划检索表达并执行检索；你自己没有直接检索工具。
4. 拿到候选片段后，委托 candidate_verifier 对照用户线索验证候选是否匹配。
5. 如果候选不充分或存在冲突，不要硬答；追问一个最有区分度的问题。
6. 如果用户否认某个候选，要在后续判断中排除它，并继续追问或检索。
7. 如果候选可信，给出最可能电影名、匹配依据和 evidence 片段。
8. 回答要简洁，使用中文。
"""


SUBAGENTS = [
    {
        "name": "clue_extractor",
        "description": "从用户的自然语言描述和对话历史中提取电影线索，判断线索是否足够检索，适合在用户描述含糊、追问、否认候选或补充线索时调用。",
        "system_prompt": """你是电影线索提取子 Agent。

任务：
1. 从用户消息和对话历史中提取结构化线索。
2. 区分确定线索、不确定线索、排除条件和用户否认。
3. 判断当前线索是否足够进入检索。
4. 如果线索不足，提出一个最有区分度的追问。

输出使用中文，尽量采用下面结构：
- 确定线索：
- 不确定线索：
- 排除条件：
- 是否足够检索：是/否
- 建议追问：

不要编造用户没有说过的电影信息。
""",
        "tools": [],
    },
    {
        "name": "movie_retriever",
        "description": "根据已整理的电影线索设计检索表达，并调用 movie_hybrid_search 获取候选电影片段。",
        "system_prompt": """你是电影检索子 Agent。

任务：
1. 将结构化线索改写成适合混合检索的中文检索 query。
2. 优先保留人物身份、关键情节、场景、关系、主题、年代/地区限制。
3. 调用 movie_hybrid_search 获取候选片段。
4. 返回检索 query、候选电影名、候选片段 id 和摘要。

不要做最终判断；最终判断交给 candidate_verifier。
""",
        "tools": [movie_hybrid_search],
    },
    {
        "name": "candidate_verifier",
        "description": "对照用户线索验证候选电影和片段是否匹配，识别缺失线索、冲突线索和置信度，适合在已有候选 evidence 后调用。",
        "system_prompt": """你是候选验证子 Agent。

任务：
1. 对每个候选电影片段逐条对照用户线索。
2. 标出 matched_clues、missing_clues、conflicts。
3. 给出 high / medium / low 置信度。
4. 如果没有高置信候选，给出一个最值得追问的问题。

输出使用中文，尽量采用下面结构：
- 最佳候选：
- 置信度：
- 匹配线索：
- 缺失线索：
- 冲突线索：
- 是否建议追问：
- 建议追问：

不要仅凭常识判断，必须依据候选片段内容。
""",
        "tools": [],
    },
]


class MovieSearchAgent:
    def __init__(self):
        self.checkpointer = InMemorySaver()
        self.thread_states = {}
        self.agent = None

    def _get_agent(self):
        if self.agent is None:
            self.agent = create_deep_agent(
                model=build_chat_model(),
                tools=[],
                subagents=SUBAGENTS,
                system_prompt=SYSTEM_PROMPT,
                checkpointer=self.checkpointer,
            )
        return self.agent

    def ask(self, question, max_results=5, thread_id=None):
        thread_id = thread_id or "default"
        clue_state = self._update_clue_state(thread_id, question)
        clue_state_text = self._format_clue_state(clue_state)
        prompt = f"""用户问题：
{question}

请作为 MovieTOMT 主协调器处理这一轮请求。你可以根据需要委托 clue_extractor、movie_retriever、candidate_verifier。
请参考当前会话中前面的对话历史理解代词、省略信息、用户否认和补充线索。
你自己不能直接检索；如果需要候选片段，必须调用 movie_retriever 子 Agent。
movie_retriever 子 Agent 是唯一拥有 movie_hybrid_search 工具的角色。

当前显式线索状态：
{clue_state_text}

请基于 movie_retriever 返回的候选片段和 candidate_verifier 的验证结果回答。不要编造片段中没有的信息。
"""
        token = start_search_trace()
        try:
            result = self._get_agent().invoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config={"configurable": {"thread_id": thread_id}},
            )
            search_events = stop_search_trace(token)
        except Exception:
            stop_search_trace(token)
            raise

        evidence = self._extract_evidence_from_search_events(search_events, max_results, clue_state)
        candidate_review = self._review_candidates_with_llm(evidence, clue_state, question)
        return {
            "answer": result["messages"][-1].content,
            "evidence": evidence,
            "clue_state": clue_state,
            "candidate_review": candidate_review,
        }

    def _default_clue_state(self):
        return {
            "confirmed_clues": [],
            "uncertain_clues": [],
            "excluded_titles": [],
            "negative_feedback": [],
            "last_candidates": [],
            "turn_count": 0,
        }

    def _update_clue_state(self, thread_id, question):
        state = self.thread_states.setdefault(thread_id, self._default_clue_state())
        state["turn_count"] += 1

        negative_patterns = ["不是", "不对", "不是这个", "不应该是", "排除", "错了", "不太像"]
        if any(pattern in question for pattern in negative_patterns):
            state["negative_feedback"].append(question)
            for title in state.get("last_candidates", []):
                self._append_unique(state["excluded_titles"], title)
            for title in self._extract_titles(question):
                self._append_unique(state["excluded_titles"], title)

        for clue in self._extract_clues(question):
            if clue["uncertain"]:
                self._append_unique(state["uncertain_clues"], clue["text"])
            else:
                self._append_unique(state["confirmed_clues"], clue["text"])

        return state

    def _extract_titles(self, text):
        titles = re.findall(r"《([^》]+)》", text)
        return [title.strip() for title in titles if title.strip()]

    def _extract_clues(self, text):
        normalized = re.sub(r"[，。！？；、,.!?;]", " ", text)
        chunks = [chunk.strip() for chunk in re.split(r"\s+", normalized) if chunk.strip()]
        stop_words = {
            "帮我找",
            "找一个",
            "找一部",
            "电影",
            "片段",
            "这个",
            "那个",
            "还有",
            "应该是",
            "好像",
            "可能",
            "记得",
            "不是",
            "不对",
        }
        clues = []
        for chunk in chunks:
            if len(chunk) < 2 or chunk in stop_words:
                continue
            if any(negative in chunk for negative in ("不是这个", "不是那个", "不对", "错了")):
                continue
            if chunk.startswith(("帮我", "请你")):
                continue
            uncertain = any(marker in chunk for marker in ("好像", "可能", "大概", "应该"))
            cleaned = chunk.replace("好像", "").replace("可能", "").replace("大概", "").replace("应该", "")
            cleaned = cleaned.replace("不是这个", "").replace("不是那个", "").replace("不对", "").replace("错了", "")
            cleaned = cleaned.strip()
            if len(cleaned) >= 2 and cleaned not in stop_words:
                clues.append({"text": cleaned[:80], "uncertain": uncertain})
        return clues[:12]

    def _append_unique(self, items, value):
        if value and value not in items:
            items.append(value)

    def _build_search_query(self, question, clue_state):
        parts = clue_state.get("confirmed_clues", [])[-12:]
        parts += clue_state.get("uncertain_clues", [])[-6:]
        parts.append(question)
        return "\n".join(parts)

    def _extract_evidence_from_search_events(self, search_events, max_results, clue_state):
        excluded = set(clue_state.get("excluded_titles", []))
        evidence = []
        seen = set()
        for event in reversed(search_events or []):
            for item in event.get("results", []):
                item_id = item.get("id")
                if item_id in seen or item.get("movie_title") in excluded:
                    continue
                seen.add(item_id)
                evidence.append(item)
                if len(evidence) >= max_results:
                    return evidence
        return evidence

    def _review_candidates(self, evidence, clue_state):
        confirmed = clue_state.get("confirmed_clues", [])
        uncertain = clue_state.get("uncertain_clues", [])
        excluded = set(clue_state.get("excluded_titles", []))
        reviews = []
        for item in evidence:
            text = f"{item.get('movie_title', '')} {item.get('summary', '')} {item.get('script', '')}"
            matched = [clue for clue in confirmed + uncertain if clue and clue in text]
            missing = [clue for clue in confirmed if clue and clue not in text][:8]
            conflicts = []
            if item.get("movie_title") in excluded:
                conflicts.append("用户已排除该候选")

            if conflicts:
                confidence = "low"
            elif len(matched) >= 3:
                confidence = "high"
            elif len(matched) >= 1:
                confidence = "medium"
            else:
                confidence = "low"

            reviews.append(
                {
                    "movie_title": item.get("movie_title"),
                    "segment_index": item.get("segment_index"),
                    "confidence": confidence,
                    "matched_clues": matched[:8],
                    "missing_clues": missing,
                    "conflicts": conflicts,
                }
            )

        clue_state["last_candidates"] = []
        for item in evidence:
            self._append_unique(clue_state["last_candidates"], item.get("movie_title"))

        should_ask = not reviews or all(item["confidence"] == "low" for item in reviews)
        followup_question = ""
        if should_ask:
            followup_question = "你还记得更多区分性线索吗，比如国家/年代、主角身份、一个具体场景或结局？"

        return {
            "candidates": reviews,
            "should_ask_followup": should_ask,
            "followup_question": followup_question,
        }

    def _review_candidates_with_llm(self, evidence, clue_state, question):
        if not evidence:
            return {
                "candidates": [],
                "should_ask_followup": True,
                "followup_question": "你还记得更多区分性线索吗，比如国家/年代、主角身份、一个具体场景或结局？",
                "review_source": "llm",
            }

        prompt = f"""你是候选电影验证器。请基于用户问题、线索状态和候选 evidence，判断每个候选是否匹配。

要求：
1. 只能依据 evidence 内容和线索状态判断，不要使用数据库外的信息。
2. confidence 只能是 high、medium、low。
3. matched_clues 写出语义匹配的线索，不要求逐字相同。
4. missing_clues 写出用户提到但 evidence 没体现的关键线索。
5. conflicts 写出明确冲突；没有冲突用空数组。
6. 如果没有 high 或 medium 候选，should_ask_followup 为 true，并给出一个最有区分度的追问。
7. 只输出 JSON，不要输出解释文字。

JSON 格式：
{{
  "candidates": [
    {{
      "movie_title": "电影名",
      "segment_index": 1,
      "confidence": "high",
      "matched_clues": ["..."],
      "missing_clues": ["..."],
      "conflicts": ["..."]
    }}
  ],
  "should_ask_followup": false,
  "followup_question": ""
}}

用户问题：
{question}

线索状态：
{self._format_clue_state(clue_state)}

候选 evidence：
{self._format_evidence(evidence)}
"""
        try:
            response = build_chat_model().invoke([{"role": "user", "content": prompt}])
            content = response.content if hasattr(response, "content") else str(response)
            review = self._parse_json_object(content)
            review["review_source"] = "llm"
            return review
        except Exception:
            fallback = self._review_candidates(evidence, clue_state)
            fallback["review_source"] = "local_fallback"
            return fallback

    def _parse_json_object(self, text):
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.S)
            if not match:
                raise
            return json.loads(match.group(0))

    def _format_clue_state(self, clue_state):
        return "\n".join(
            [
                f"- 确定线索：{', '.join(clue_state.get('confirmed_clues', [])[-12:]) or '暂无'}",
                f"- 不确定线索：{', '.join(clue_state.get('uncertain_clues', [])[-8:]) or '暂无'}",
                f"- 排除候选：{', '.join(clue_state.get('excluded_titles', [])) or '暂无'}",
                f"- 用户否认：{'; '.join(clue_state.get('negative_feedback', [])[-3:]) or '暂无'}",
            ]
        )

    def _format_candidate_review(self, candidate_review):
        candidates = candidate_review.get("candidates", [])
        if not candidates:
            return "暂无候选。"
        lines = []
        for item in candidates:
            lines.append(
                "\n".join(
                    [
                        f"- {item['movie_title']} segment {item['segment_index']}",
                        f"  置信度：{item['confidence']}",
                        f"  匹配线索：{', '.join(item['matched_clues']) or '暂无'}",
                        f"  缺失线索：{', '.join(item['missing_clues']) or '暂无'}",
                        f"  冲突线索：{', '.join(item['conflicts']) or '暂无'}",
                    ]
                )
            )
        return "\n".join(lines)

    def _format_evidence(self, evidence):
        if not evidence:
            return "未检索到相关片段。"

        lines = []
        for index, item in enumerate(evidence, start=1):
            lines.append(
                "\n".join(
                    [
                        f"[{index}] {item['movie_title']} segment {item['segment_index']} ({item['id']})",
                        f"summary: {item['summary']}",
                        f"script_excerpt: {item['script']}",
                    ]
                )
            )
        return "\n\n".join(lines)


movie_search_agent = MovieSearchAgent()
