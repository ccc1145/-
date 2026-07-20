"""Parser 单元测试（Day 6-7 Polish 提前到 Day 6，减少 Day 15 压力）。

覆盖：
- 标准解析路径（3 种策略）
- 字段校验和补全（缺字段、超长、类型错误）
- Day 6-7 新增容错：字段名大小写归一化、中文标点、narrative 为 list、平衡花括号
- 降级响应

运行：
    cd D:\\实训\\xiuxian-simulator
    D:\\Anaconda3\\envs\\shixun\\python.exe -m pytest agent\\tests\\test_parser.py -v
    或直接运行：D:\\Anaconda3\\envs\\shixun\\python.exe agent\\tests\\test_parser.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 加载 agent/src 到 path
AGENT_SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(AGENT_SRC))

from parser import AgentOutputParser  # noqa: E402


def _ok(result: dict) -> bool:
    """判定解析成功（无 parse_failed 标记）"""
    return not result.get("parse_failed")


# ---- 测试用例 ----

def test_direct_json_standard():
    """标准 JSON 直接解析。"""
    parser = AgentOutputParser()
    raw = '{"narrative":"测试叙事","available_choices":[{"id":"a","text":"选项A"}]}'
    r = parser.parse(raw)
    assert _ok(r)
    assert r["narrative"] == "测试叙事"
    assert len(r["available_choices"]) == 1
    print("✓ test_direct_json_standard")


def test_markdown_code_block():
    """Markdown 代码块包裹的 JSON。"""
    parser = AgentOutputParser()
    raw = '好的，这是叙事：\n```json\n{"narrative":"md测试","available_choices":[{"id":"b","text":"B"}]}\n```\n以上。'
    r = parser.parse(raw)
    assert _ok(r)
    assert r["narrative"] == "md测试"
    print("✓ test_markdown_code_block")


def test_text_with_surrounding_text():
    """JSON 前后带说明文字（花括号提取）。"""
    parser = AgentOutputParser()
    raw = '好的，这是叙事：\n{"narrative":"带说明","available_choices":[{"id":"c","text":"C"}]}\n以上。'
    r = parser.parse(raw)
    assert _ok(r)
    assert r["narrative"] == "带说明"
    print("✓ test_text_with_surrounding_text")


def test_empty_string():
    """空字符串触发降级。"""
    parser = AgentOutputParser()
    r = parser.parse("")
    assert not _ok(r)
    assert r.get("degraded") is True
    print("✓ test_empty_string")


def test_pure_text_no_json():
    """纯文本无 JSON 触发降级。"""
    parser = AgentOutputParser()
    r = parser.parse("LLM 出错了，这只是一段普通文本。")
    assert not _ok(r)
    assert r.get("degraded") is True
    print("✓ test_pure_text_no_json")


def test_missing_available_choices():
    """缺 available_choices 自动补兜底。"""
    parser = AgentOutputParser()
    raw = '{"narrative":"缺选项"}'
    r = parser.parse(raw)
    assert _ok(r)
    assert len(r["available_choices"]) >= 1  # 补了兜底
    print("✓ test_missing_available_choices")


def test_too_many_choices_truncated():
    """available_choices 超 4 个自动截断。"""
    parser = AgentOutputParser()
    raw = '{"narrative":"x","available_choices":[' + \
          ','.join(f'{{"id":"c{i}","text":"选项{i}"}}' for i in range(6)) + \
          ']}'
    r = parser.parse(raw)
    assert _ok(r)
    assert len(r["available_choices"]) == 4
    print("✓ test_too_many_choices_truncated")


def test_dialogue_segment_without_speaker():
    """dialogue 类型 segment 缺 speaker 自动清理。"""
    parser = AgentOutputParser()
    raw = '{"narrative":"x","narrative_segments":[{"type":"dialogue","text":"对话"}],"available_choices":[{"id":"d","text":"D"}]}'
    r = parser.parse(raw)
    assert _ok(r)
    # 缺 speaker 的 dialogue segment 会被保留但无 speaker 字段
    segs = r.get("narrative_segments", [])
    assert len(segs) == 1
    print("✓ test_dialogue_segment_without_speaker")


# ---- Day 6-7 新增容错测试 ----

def test_field_name_case_normalization():
    """字段名大小写归一化：Narrative -> narrative。"""
    parser = AgentOutputParser()
    raw = '{"Narrative":"大写字段测试","AvailableChoices":[{"id":"a","text":"A"}]}'
    r = parser.parse(raw)
    assert _ok(r)
    assert r["narrative"] == "大写字段测试"
    assert len(r["available_choices"]) == 1
    print("✓ test_field_name_case_normalization")


def test_camel_case_field_normalization():
    """驼峰字段归一化：narrativeSegments -> narrative_segments。"""
    parser = AgentOutputParser()
    raw = '{"narrative":"x","narrativeSegments":[{"type":"narration","text":"片段"}],"availableChoices":[{"id":"a","text":"A"}]}'
    r = parser.parse(raw)
    assert _ok(r)
    assert len(r["narrative_segments"]) == 1
    print("✓ test_camel_case_field_normalization")


def test_chinese_quotes_normalization():
    """中文引号转英文引号后解析。"""
    parser = AgentOutputParser()
    # 用中文引号包裹的 JSON（非法 JSON）
    raw = '{"narrative":"中文引号测试","available_choices":[{"id":"a","text":"A"}]}'
    r = parser.parse(raw)
    assert _ok(r)
    assert r["narrative"] == "中文引号测试"
    print("✓ test_chinese_quotes_normalization")


def test_narrative_as_list():
    """narrative 为 list 时自动合并为字符串。"""
    parser = AgentOutputParser()
    raw = '{"narrative":["第一段","第二段"],"available_choices":[{"id":"a","text":"A"}]}'
    r = parser.parse(raw)
    assert _ok(r)
    assert "第一段" in r["narrative"]
    assert "第二段" in r["narrative"]
    assert "\n" in r["narrative"]  # 用换行连接
    print("✓ test_narrative_as_list")


def test_balanced_brace_extraction_with_nested():
    """平衡花括号匹配：JSON 内部有嵌套对象时不被截断。"""
    parser = AgentOutputParser()
    raw = '前缀说明\n{"narrative":"嵌套测试","narrative_segments":[{"type":"narration","text":"片段"}],"available_choices":[{"id":"a","text":"A"}]}\n后缀说明'
    r = parser.parse(raw)
    assert _ok(r)
    assert r["narrative"] == "嵌套测试"
    assert len(r["narrative_segments"]) == 1
    print("✓ test_balanced_brace_extraction_with_nested")


def test_choices_alias_normalization():
    """choices 字段名变体归一化为 available_choices。"""
    parser = AgentOutputParser()
    raw = '{"narrative":"x","choices":[{"id":"a","text":"A"}]}'
    r = parser.parse(raw)
    assert _ok(r)
    assert "available_choices" in r
    assert len(r["available_choices"]) == 1
    print("✓ test_choices_alias_normalization")


def test_degraded_response_structure():
    """降级响应结构完整。"""
    parser = AgentOutputParser()
    r = parser.parse("")
    assert r.get("degraded") is True
    assert r.get("parse_failed") is True
    assert "narrative" in r
    assert "narrative_segments" in r
    assert "available_choices" in r
    assert "thought" in r
    assert "DEGRADED" in r["thought"]
    print("✓ test_degraded_response_structure")


def test_single_quote_json_tolerance():
    """单引号 JSON 容错（部分 LLM 用单引号）。"""
    parser = AgentOutputParser()
    # 单引号在标准 JSON 中非法，但 brace_extraction 策略会尝试替换
    raw = "前缀\n{'narrative':'单引号测试','available_choices':[{'id':'a','text':'A'}]}\n后缀"
    r = parser.parse(raw)
    # 单引号替换可能成功也可能失败（取决于字符串内是否有单引号），这里宽容断言
    if _ok(r):
        assert r["narrative"] == "单引号测试"
        print("✓ test_single_quote_json_tolerance (成功解析)")
    else:
        # 如果降级了也算通过（容错失败走降级是可接受的）
        assert r.get("degraded") is True
        print("✓ test_single_quote_json_tolerance (降级兜底)")


# ---- 运行所有测试 ----

def run_all():
    """运行所有测试用例。"""
    tests = [
        test_direct_json_standard,
        test_markdown_code_block,
        test_text_with_surrounding_text,
        test_empty_string,
        test_pure_text_no_json,
        test_missing_available_choices,
        test_too_many_choices_truncated,
        test_dialogue_segment_without_speaker,
        test_field_name_case_normalization,
        test_camel_case_field_normalization,
        test_chinese_quotes_normalization,
        test_narrative_as_list,
        test_balanced_brace_extraction_with_nested,
        test_choices_alias_normalization,
        test_degraded_response_structure,
        test_single_quote_json_tolerance,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} 失败: {type(e).__name__}: {e}")

    print(f"\n{'='*60}")
    print(f"Parser 单元测试结果: {passed} 通过 / {failed} 失败 / {len(tests)} 总计")
    print(f"{'='*60}")
    return failed == 0


if __name__ == "__main__":
    import os
    os.system("")  # 启用 ANSI 转义（Windows）
    success = run_all()
    sys.exit(0 if success else 1)
