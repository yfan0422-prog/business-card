"""繁简中文转换工具 — 支持繁简一体化搜索"""
from opencc import OpenCC

# 全局单例，避免重复初始化
_s2t = None
_t2s = None


def _get_s2t():
    global _s2t
    if _s2t is None:
        _s2t = OpenCC('s2t')
    return _s2t


def _get_t2s():
    global _t2s
    if _t2s is None:
        _t2s = OpenCC('t2s')
    return _t2s


def to_simplified(text: str) -> str:
    """将文本转换为简体中文"""
    if not text:
        return text
    return _get_t2s().convert(text)


def to_traditional(text: str) -> str:
    """将文本转换为繁体中文"""
    if not text:
        return text
    return _get_s2t().convert(text)


def get_search_variants(query: str) -> list:
    """获取搜索关键词的所有繁简变体（去重）"""
    if not query or not query.strip():
        return [query]
    variants = {query.strip()}
    simp = to_simplified(query)
    if simp:
        variants.add(simp)
    trad = to_traditional(query)
    if trad:
        variants.add(trad)
    return list(variants)
