import re
from typing import Dict, Any, List, Optional

from utils import now_ms, compact_text, normalize_text


STOPWORDS = {
    "a", "o", "e", "de", "do", "da", "dos", "das", "um", "uma", "uns", "umas",
    "em", "no", "na", "nos", "nas", "por", "para", "pra", "com", "sem", "que",
    "eu", "você", "vc", "ele", "ela", "eles", "elas", "me", "te", "se", "meu",
    "minha", "meus", "minhas", "seu", "sua", "seus", "suas", "isso", "isto",
    "aquele", "aquela", "aquilo", "como", "quando", "onde", "porque", "porquê",
    "foi", "era", "ser", "estar", "estou", "está", "estava", "estavam", "tem",
    "tenho", "tinha", "vai", "vou", "iria", "the", "and"
}


def tokenize(text: str) -> List[str]:
    base = normalize_text(text)
    tokens = []
    for t in base.split():
        if len(t) < 2:
            continue
        if t in STOPWORDS:
            continue
        tokens.append(t)
    return tokens


def infer_tags(text: str) -> List[str]:
    t = normalize_text(text)
    tags = set()

    tag_map = {
        "filho": ["filho", "filha", "crianca", "criança", "benjamin", "bela", "autismo", "autista"],
        "trabalho": ["trabalho", "servico", "serviço", "reuniao", "reunião", "emprego", "profissao", "profissão"],
        "emocao": ["triste", "sozinho", "sozinha", "ansioso", "ansiosa", "cansado", "cansada", "mal"],
        "relacao": ["amor", "saudade", "gosto", "te amo", "relacao", "relação", "namorada", "ciume", "ciúme"],
        "lugar": ["moro", "cidade", "vitoria", "vitória", "espirito", "espírito", "castelo", "vila velha", "parque", "praia", "mercado"],
        "planos": ["amanha", "amanhã", "hoje", "depois", "futuro", "planejo", "vou", "pretendo"],
        "interesses": ["astronomia", "ingles", "inglês", "ia", "programacao", "programação", "filosofia", "linguistica", "linguística"],
        "atividade": ["caminhando", "andando", "correndo", "dirigindo", "trabalhando", "descansando", "deitado", "passeando"]
    }

    for tag, keywords in tag_map.items():
        if any(k in t for k in keywords):
            tags.add(tag)

    return sorted(tags)


def infer_importance(text: str, kind: str = "fact") -> int:
    t = normalize_text(text)
    importance = 3

    high_signals = [
        "meu filho", "minha filha", "eu moro", "eu amo", "eu gosto",
        "amanha", "amanhã", "hoje tenho", "estou triste", "estou sozinho",
        "estou ansioso", "meu trabalho", "minha reuniao", "minha reunião"
    ]
    if any(sig in t for sig in high_signals):
        importance += 3

    if kind == "pinned":
        importance += 4
    if kind == "affective":
        importance += 3
    if kind == "narrative":
        importance += 5
    if kind == "episode":
        importance += 2
    if kind == "context":
        importance += 2

    if len(t.split()) >= 10:
        importance += 1

    return min(10, importance)


def semantic_score(memory: Dict[str, Any], query_text: str) -> float:
    query_tokens = set(tokenize(query_text))
    query_tags = set(infer_tags(query_text))

    mem_tokens = set(memory.get("tokens", []))
    mem_tags = set(memory.get("tags", []))
    importance = memory.get("importance", 3)

    token_overlap = len(query_tokens & mem_tokens)
    tag_overlap = len(query_tags & mem_tags)

    age_days = max(0.0, (now_ms() - memory["ts_ms"]) / 86400000.0)
    recency_bonus = max(0.0, 2.5 - min(age_days, 2.5))

    score = 0.0
    score += token_overlap * 3.5
    score += tag_overlap * 5.0
    score += importance * 0.9
    score += recency_bonus

    if memory.get("kind") == "affective":
        score += 1.8
    if memory.get("kind") == "narrative":
        score += 2.4

    if not query_tokens and not query_tags:
        score += 1.0

    return score


def get_semantic_memories(u: Dict[str, Any], query_text: str, limit: int = 8) -> List[Dict[str, Any]]:
    memories = u["memories"]
    if not memories:
        return []

    scored = []
    for m in memories:
        s = semantic_score(m, query_text)
        scored.append((s, m))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [m for s, m in scored if s > 0][:limit]

    if not top:
        fallback = sorted(memories, key=lambda m: (m.get("importance", 3), m["ts_ms"]), reverse=True)
        top = fallback[:limit]

    return top


def add_memory(u: Dict[str, Any], text: str, kind: str = "fact"):
    text = compact_text(text)
    if not text:
        return

    lower_existing = [m["text"].lower() for m in u["memories"]]
    if text.lower() in lower_existing:
        return

    entry = {
        "text": text,
        "kind": kind,
        "ts_ms": now_ms(),
        "tokens": tokenize(text),
        "tags": infer_tags(text),
        "importance": infer_importance(text, kind=kind)
    }

    u["memories"].append(entry)

    if len(u["memories"]) > 160:
        del u["memories"][:-160]


def add_affective_memory(
    u: Dict[str, Any],
    text: str,
    valence: str,
    intensity: int,
    tags: Optional[List[str]] = None
):
    text = compact_text(text)
    if not text:
        return

    existing = [m["text"].lower() for m in u["memories"][-30:]]
    if text.lower() in existing:
        return

    merged_tags = set(tags or [])
    merged_tags.add("relacao")
    merged_tags.add("emocao")

    entry = {
        "text": text,
        "kind": "affective",
        "valence": valence,
        "intensity": max(0, min(100, int(intensity))),
        "ts_ms": now_ms(),
        "tokens": tokenize(text),
        "tags": sorted(merged_tags),
        "importance": min(10, 5 + int(intensity) // 20)
    }

    u["memories"].append(entry)

    if len(u["memories"]) > 160:
        del u["memories"][:-160]


def get_recent_affective_memories(u: Dict[str, Any], limit: int = 6) -> List[Dict[str, Any]]:
    affective = [m for m in u["memories"] if m.get("kind") == "affective"]
    affective.sort(key=lambda m: m["ts_ms"], reverse=True)
    return affective[:limit]


def extract_memories_from_user_text(user_text: str) -> List[str]:
    t = user_text.strip()
    tl = normalize_text(t)
    found = []

    patterns = [
        r"meu filho chama ([^.,!?\n]+)",
        r"minha filha chama ([^.,!?\n]+)",
        r"eu moro em ([^.,!?\n]+)",
        r"eu trabalho com ([^.,!?\n]+)",
        r"eu gosto de ([^.,!?\n]+)",
        r"eu amo ([^.,!?\n]+)",
        r"amanha tenho ([^.,!?\n]+)",
        r"hoje tenho ([^.,!?\n]+)",
        r"eu estou em ([^.,!?\n]+)",
    ]

    for p in patterns:
        if re.search(p, tl):
            found.append(compact_text(t))

    keywords = [
        "meu filho", "minha filha", "meu trabalho", "minha reuniao", "minha reunião",
        "estou triste", "estou ansioso", "estou cansado", "estou sozinho",
        "eu gosto de", "eu amo", "vou viajar", "amanha tenho", "amanhã tenho"
    ]
    if any(k in tl for k in keywords):
        found.append(compact_text(t))

    dedup = []
    seen = set()
    for item in found:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            dedup.append(item)
    return dedup


def add_episode(
    u: Dict[str, Any],
    episode_type: str,
    summary: str,
    details: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
    importance: int = 5
):
    summary = compact_text(summary, 260)
    if not summary:
        return

    entry = {
        "ts_ms": now_ms(),
        "type": episode_type,
        "summary": summary,
        "details": details or {},
        "tags": sorted(set(tags or [])),
        "importance": max(1, min(10, int(importance)))
    }

    u["episodes"].append(entry)

    if len(u["episodes"]) > 120:
        del u["episodes"][:-120]


def get_relevant_episodes(u: Dict[str, Any], query_text: str, limit: int = 6) -> List[Dict[str, Any]]:
    query_tokens = set(tokenize(query_text))
    query_tags = set(infer_tags(query_text))

    scored = []
    for ep in u.get("episodes", []):
        summary_tokens = set(tokenize(ep.get("summary", "")))
        ep_tags = set(ep.get("tags", []))
        overlap = len(query_tokens & summary_tokens)
        tag_overlap = len(query_tags & ep_tags)
        score = overlap * 3 + tag_overlap * 5 + ep.get("importance", 5)
        scored.append((score, ep))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [ep for score, ep in scored if score > 0][:limit]

    if not top:
        fallback = sorted(u.get("episodes", []), key=lambda ep: (ep.get("importance", 5), ep["ts_ms"]), reverse=True)
        top = fallback[:limit]

    return top