#!/usr/bin/env python3
"""
内容配置校验脚本
功能：校验 content/ 目录下所有 YAML 配置文件的格式和逻辑正确性
用法：python validate_content.py [--path ../content] [--verbose]
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


# ============================================================
# 颜色输出
# ============================================================
class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def green(text: str) -> str:
    return f"{Color.GREEN}{text}{Color.RESET}"


def red(text: str) -> str:
    return f"{Color.RED}{text}{Color.RESET}"


def yellow(text: str) -> str:
    return f"{Color.YELLOW}{text}{Color.RESET}"


def blue(text: str) -> str:
    return f"{Color.BLUE}{text}{Color.RESET}"


def bold(text: str) -> str:
    return f"{Color.BOLD}{text}{Color.RESET}"


# ============================================================
# 错误收集
# ============================================================
class ValidationError:
    """校验错误"""

    def __init__(self, file_path: str, field: str, message: str, severity: str = "error"):
        self.file_path = file_path
        self.field = field
        self.message = message
        self.severity = severity  # error / warning

    def __str__(self):
        prefix = red("[错误]") if self.severity == "error" else yellow("[警告]")
        return f"{prefix} {self.file_path}\n        字段: {self.field}\n        原因: {self.message}"


class ValidationResult:
    """校验结果"""

    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []

    def add_error(self, file_path: str, field: str, message: str):
        self.errors.append(ValidationError(file_path, field, message, "error"))

    def add_warning(self, file_path: str, field: str, message: str):
        self.warnings.append(ValidationError(file_path, field, message, "warning"))

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        total = len(self.errors) + len(self.warnings)
        if total == 0:
            return green("✓ 所有文件校验通过！")
        parts = []
        if self.errors:
            parts.append(red(f"✗ {len(self.errors)} 个错误"))
        if self.warnings:
            parts.append(yellow(f"⚠ {len(self.warnings)} 个警告"))
        return " | ".join(parts)


# ============================================================
# YAML 读取
# ============================================================
def load_yaml(file_path: str) -> Tuple[Optional[Any], Optional[str]]:
    """读取 YAML 文件，返回 (数据, 错误信息)"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            return None, "文件为空"
        if not isinstance(data, (dict, list)):
            return None, "YAML 根节点必须是字典或列表"
        return data, None
    except yaml.YAMLError as e:
        return None, f"YAML 语法错误: {e}"
    except FileNotFoundError:
        return None, "文件不存在"
    except Exception as e:
        return None, f"读取失败: {e}"


# ============================================================
# 校验器
# ============================================================
class ContentValidator:
    """内容配置校验器"""

    def __init__(self, content_dir: str, verbose: bool = False):
        self.content_dir = Path(content_dir)
        self.verbose = verbose
        self.result = ValidationResult()

        # 加载 JSON Schema
        self.schemas = {}
        schema_dir = self.content_dir / "schema"
        for schema_file in schema_dir.glob("*.json"):
            try:
                with open(schema_file, "r", encoding="utf-8") as f:
                    self.schemas[schema_file.stem] = json.load(f)
            except Exception as e:
                self.result.add_error(str(schema_file), "schema", f"无法加载 JSON Schema: {e}")

    # ----- 通用校验 -----
    def _check_required_fields(self, data: dict, required: List[str], file_path: str, prefix: str = "") -> bool:
        """检查必填字段"""
        ok = True
        for field in required:
            full_field = f"{prefix}.{field}" if prefix else field
            if field not in data or data[field] is None:
                self.result.add_error(file_path, full_field, f"缺少必填字段 '{field}'")
                ok = False
        return ok

    def _check_type(self, data: dict, field: str, expected_type: type, file_path: str, prefix: str = "") -> bool:
        """检查字段类型"""
        if field not in data:
            return True
        value = data[field]
        full_field = f"{prefix}.{field}" if prefix else field
        if not isinstance(value, expected_type):
            self.result.add_error(file_path, full_field, f"类型错误: 期望 {expected_type.__name__}, 实际 {type(value).__name__}")
            return False
        return True

    def _check_enum(self, data: dict, field: str, allowed: List[str], file_path: str, prefix: str = "") -> bool:
        """检查枚举值"""
        if field not in data:
            return True
        value = data[field]
        full_field = f"{prefix}.{field}" if prefix else field
        if value not in allowed:
            self.result.add_error(file_path, full_field, f"值 '{value}' 不在允许范围 [{', '.join(allowed)}]")
            return False
        return True

    # ----- NPC 校验 -----
    def validate_npc(self, file_path: str) -> None:
        """校验 NPC 角色卡"""
        data, error = load_yaml(file_path)
        if error:
            self.result.add_error(file_path, "root", error)
            return

        fn = Path(file_path).name

        # 必填字段
        required = ["npc_id", "name", "description", "personality", "initial_state", "knowledge"]
        self._check_required_fields(data, required, fn)

        # npc_id 格式
        if "npc_id" in data and not isinstance(data["npc_id"], str):
            self.result.add_error(fn, "npc_id", "npc_id 必须是字符串")

        # personality 子字段
        if "personality" in data and isinstance(data["personality"], dict):
            p = data["personality"]
            self._check_required_fields(p, ["traits", "speaking_style"], fn, "personality")
            self._check_type(p, "traits", list, fn, "personality")
            if "traits" in p and isinstance(p["traits"], list) and len(p["traits"]) == 0:
                self.result.add_error(fn, "personality.traits", "traits 不能为空")

        # initial_state 子字段
        if "initial_state" in data and isinstance(data["initial_state"], dict):
            s = data["initial_state"]
            self._check_required_fields(s, ["affinity", "location"], fn, "initial_state")
            if "affinity" in s:
                if not isinstance(s["affinity"], (int, float)):
                    self.result.add_error(fn, "initial_state.affinity", "affinity 必须是数字")
                elif s["affinity"] < -100 or s["affinity"] > 100:
                    self.result.add_error(fn, "initial_state.affinity", f"affinity 超出范围: {s['affinity']}（应为 -100 ~ 100）")

        # knowledge 非空
        if "knowledge" in data:
            if isinstance(data["knowledge"], list) and len(data["knowledge"]) == 0:
                self.result.add_error(fn, "knowledge", "knowledge 不能为空")
            elif not isinstance(data["knowledge"], list):
                self.result.add_error(fn, "knowledge", "knowledge 必须是数组")

        # dialogue_examples
        if "dialogue_examples" in data and isinstance(data["dialogue_examples"], list):
            for i, de in enumerate(data["dialogue_examples"]):
                if not isinstance(de, dict):
                    self.result.add_error(fn, f"dialogue_examples[{i}]", "必须是字典")
                    continue
                self._check_required_fields(de, ["user", "response"], fn, f"dialogue_examples[{i}]")

        if self.verbose:
            print(f"  {green('✓')} {fn}")

    # ----- 事件校验 -----
    def validate_event(self, file_path: str) -> None:
        """校验事件配置"""
        data, error = load_yaml(file_path)
        if error:
            self.result.add_error(file_path, "root", error)
            return

        fn = Path(file_path).name
        subdir = Path(file_path).parent.name

        # 必填字段
        required = ["event_id", "name", "type", "trigger_conditions", "scenes"]
        self._check_required_fields(data, required, fn)

        # 事件类型
        valid_event_types = ["major", "minor", "daily"]
        self._check_enum(data, "type", valid_event_types, fn)

        event_type = data.get("type", "major")

        # trigger_conditions
        if "trigger_conditions" in data:
            tc = data["trigger_conditions"]
            if not isinstance(tc, list) or len(tc) == 0:
                self.result.add_error(fn, "trigger_conditions", "trigger_conditions 不能为空")
            else:
                valid_types = ["scene_enter", "flag_check", "attribute_check", "npc_affinity_check"]
                for i, cond in enumerate(tc):
                    if not isinstance(cond, dict):
                        self.result.add_error(fn, f"trigger_conditions[{i}]", "必须是字典")
                        continue
                    self._check_required_fields(cond, ["type"], fn, f"trigger_conditions[{i}]")
                    self._check_enum(cond, "type", valid_types, fn, f"trigger_conditions[{i}]")

        # scenes
        if "scenes" in data and isinstance(data["scenes"], dict):
            scene_ids = list(data["scenes"].keys())
            if len(scene_ids) == 0:
                self.result.add_error(fn, "scenes", "scenes 不能为空")

            for sid, scene in data["scenes"].items():
                if not isinstance(scene, dict):
                    self.result.add_error(fn, f"scenes.{sid}", "必须是字典")
                    continue
                self._check_required_fields(scene, ["scene_id", "name", "description"], fn, f"scenes.{sid}")

                # 校验 choices — 小事件可以有 free_input 而无 choices
                if "choices" in scene and isinstance(scene["choices"], list):
                    for j, choice in enumerate(scene["choices"]):
                        if not isinstance(choice, dict):
                            self.result.add_error(fn, f"scenes.{sid}.choices[{j}]", "必须是字典")
                            continue
                        self._check_required_fields(choice, ["id", "text", "next_scene"], fn, f"scenes.{sid}.choices[{j}]")

                        # 校验 next_scene 引用的场景是否存在
                        if "next_scene" in choice:
                            ns = choice["next_scene"]
                            if ns not in scene_ids:
                                self.result.add_warning(fn, f"scenes.{sid}.choices[{j}].next_scene", f"next_scene '{ns}' 不在此事件的 scenes 中")

        # 小事件特有字段检查
        if event_type == "minor":
            if "free_narrative_hints" not in data or not data["free_narrative_hints"]:
                self.result.add_warning(fn, "free_narrative_hints", "小事件建议配置 free_narrative_hints 以帮助 Agent 叙事")
            if "difficulty" not in data:
                self.result.add_warning(fn, "difficulty", "小事件建议配置 difficulty 帮助 Agent 判断难易度")

        if self.verbose:
            print(f"  {green('✓')} {fn}")

    # ----- 物品校验 -----
    def validate_item(self, file_path: str) -> None:
        """校验物品配置"""
        data, error = load_yaml(file_path)
        if error:
            self.result.add_error(file_path, "root", error)
            return

        fn = Path(file_path).name
        valid_types = ["consumable", "equipment", "material", "key_item", "currency", "skill_book"]
        valid_rarities = ["common", "uncommon", "rare", "epic", "legendary"]

        # 如果是物品列表文件（包含多个物品）
        if isinstance(data, list):
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    self.result.add_error(fn, f"[{i}]", "必须是字典")
                    continue
                self._check_required_fields(item, ["item_id", "name", "type", "description"], fn, f"[{i}]")
                self._check_enum(item, "type", valid_types, fn, f"[{i}]")
                if "rarity" in item:
                    self._check_enum(item, "rarity", valid_rarities, fn, f"[{i}]")
        elif isinstance(data, dict):
            self._check_required_fields(data, ["item_id", "name", "type", "description"], fn)
            self._check_enum(data, "type", valid_types, fn)
            if "rarity" in data:
                self._check_enum(data, "rarity", valid_rarities, fn)
        else:
            self.result.add_error(fn, "root", "YAML 根节点必须是字典或列表")

        if self.verbose:
            print(f"  {green('✓')} {fn}")

    # ----- 世界书校验 -----
    def validate_world_book(self, file_path: str) -> None:
        """校验世界书 JSON 配置"""
        fn = Path(file_path).name
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.result.add_error(fn, "root", f"JSON 语法错误: {e}")
            return
        except Exception as e:
            self.result.add_error(fn, "root", f"读取失败: {e}")
            return

        if not isinstance(data, dict):
            self.result.add_error(fn, "root", "世界书根节点必须是字典")
            return

        # 必填字段
        self._check_required_fields(data, ["book_id", "name", "entries"], fn)

        # book_id 格式
        if "book_id" in data and isinstance(data["book_id"], str):
            import re
            if not re.match(r'^[a-z][a-z0-9_]*$', data["book_id"]):
                self.result.add_error(fn, "book_id", "book_id 必须符合小写下划线命名规范")

        # entries 校验
        if "entries" in data and isinstance(data["entries"], list):
            entry_ids = set()
            for i, entry in enumerate(data["entries"]):
                prefix = f"entries[{i}]"
                if not isinstance(entry, dict):
                    self.result.add_error(fn, prefix, "必须是字典")
                    continue

                self._check_required_fields(entry, ["entry_id", "keys", "content"], fn, prefix)

                # entry_id 唯一性
                if "entry_id" in entry:
                    eid = entry["entry_id"]
                    if eid in entry_ids:
                        self.result.add_error(fn, f"{prefix}.entry_id", f"entry_id '{eid}' 重复")
                    entry_ids.add(eid)

                # keys 非空
                if "keys" in entry:
                    if not isinstance(entry["keys"], list):
                        self.result.add_error(fn, f"{prefix}.keys", "keys 必须是数组")
                    elif len(entry["keys"]) == 0:
                        self.result.add_error(fn, f"{prefix}.keys", "keys 不能为空")
                    else:
                        for j, k in enumerate(entry["keys"]):
                            if not isinstance(k, str) or not k.strip():
                                self.result.add_error(fn, f"{prefix}.keys[{j}]", "关键词不能为空字符串")

                # category
                valid_categories = ["world_lore", "npc_lore", "rule_knowledge", "event_effect", "location_info"]
                self._check_enum(entry, "category", valid_categories, fn, prefix)

                # weight 范围
                if "weight" in entry and isinstance(entry["weight"], int):
                    if entry["weight"] < 1 or entry["weight"] > 1000:
                        self.result.add_error(fn, f"{prefix}.weight", "weight 必须在 1-1000 之间")

                # probability 范围
                if "probability" in entry and isinstance(entry["probability"], (int, float)):
                    if entry["probability"] < 0 or entry["probability"] > 1:
                        self.result.add_error(fn, f"{prefix}.probability", "probability 必须在 0-1 之间")

                # max_tokens 范围
                if "max_tokens" in entry and isinstance(entry["max_tokens"], int):
                    if entry["max_tokens"] < 10 or entry["max_tokens"] > 2000:
                        self.result.add_error(fn, f"{prefix}.max_tokens", "max_tokens 必须在 10-2000 之间")

        if self.verbose:
            print(f"  {green('✓')} {fn}")

    # ----- NPC 池校验 -----
    def validate_npc_pool(self, file_path: str) -> None:
        """校验随机NPC成分池（npc_pool.yaml）"""
        fn = Path(file_path).name
        data, error = load_yaml(file_path)
        if error:
            self.result.add_error(fn, "root", error)
            return

        if not isinstance(data, dict):
            self.result.add_error(fn, "root", "NPC池文件根节点必须是字典")
            return

        # 收集所有性格标签key供后续交叉校验
        trait_keys = set()
        trait_names = set()
        trait_groups = {}
        if "personality_traits" in data and isinstance(data["personality_traits"], dict):
            trait_keys = set(data["personality_traits"].keys())
            for tk, tv in data["personality_traits"].items():
                if isinstance(tv, dict):
                    if "name" in tv:
                        trait_names.add(tv["name"])
                    if "group" in tv:
                        g = tv["group"]
                        if g not in trait_groups:
                            trait_groups[g] = []
                        trait_groups[g].append(tk)

        # 校验身份池
        if "identities" in data:
            self._validate_identities(data, fn, trait_names)
        else:
            self.result.add_error(fn, "identities", "缺少 'identities' 字段")

        # 校验性格标签池
        self._validate_personality_traits(data, fn)

        # 校验背景池
        if "backgrounds" in data:
            self._validate_backgrounds(data, fn, trait_names)
        else:
            self.result.add_error(fn, "backgrounds", "缺少 'backgrounds' 字段")

        # 校验姓名池
        if "name_pool" in data:
            self._validate_name_pool(data, fn)
        else:
            self.result.add_error(fn, "name_pool", "缺少 'name_pool' 字段")

        # 跨文件引用检查
        self._validate_npc_pool_cross_references(data, fn, trait_groups)

        if self.verbose:
            id_count = len(data.get("identities", []))
            bg_count = len(data.get("backgrounds", []))
            print(f"  {green('✓')} {fn} ({id_count} 身份, {len(trait_keys)} 性格标签, {bg_count} 背景)")

    def _validate_identities(self, pool_data: dict, fn: str, trait_keys: set) -> None:
        """校验身份池"""
        identities = pool_data["identities"]
        if not isinstance(identities, list):
            self.result.add_error(fn, "identities", "identities 必须是数组")
            return
        if len(identities) == 0:
            self.result.add_error(fn, "identities", "identities 不能为空")
            return

        valid_sects = ["xuanqing", "shenwu", "fulong", "hongchen", "neutral"]
        seen_ids = set()

        for i, id_ in enumerate(identities):
            prefix = f"identities[{i}]"
            if not isinstance(id_, dict):
                self.result.add_error(fn, prefix, "必须是字典")
                continue

            required = ["identity_id", "sect", "name", "realm_range", "personality_affinity"]
            self._check_required_fields(id_, required, fn, prefix)

            # identity_id 唯一性
            if "identity_id" in id_ and isinstance(id_["identity_id"], str):
                iid = id_["identity_id"]
                if iid in seen_ids:
                    self.result.add_error(fn, f"{prefix}.identity_id", f"identity_id '{iid}' 重复")
                seen_ids.add(iid)

            # sect enum
            self._check_enum(id_, "sect", valid_sects, fn, prefix)

            # realm_range
            if "realm_range" in id_ and isinstance(id_["realm_range"], dict):
                self._check_required_fields(id_["realm_range"], ["min", "max"], fn, f"{prefix}.realm_range")
                for f in ["min", "max"]:
                    if f in id_["realm_range"] and not isinstance(id_["realm_range"][f], str):
                        self.result.add_error(fn, f"{prefix}.realm_range.{f}", "必须是字符串")

            # personality_affinity 中的引用
            if "personality_affinity" in id_ and isinstance(id_["personality_affinity"], dict):
                pa = id_["personality_affinity"]
                for field in ["preferred", "excluded"]:
                    if field in pa and isinstance(pa[field], list):
                        for j, tag in enumerate(pa[field]):
                            if tag not in trait_keys:
                                self.result.add_warning(fn, f"{prefix}.personality_affinity.{field}[{j}]",
                                    f"性格标签 '{tag}' 在 personality_traits 中未定义")

    def _validate_personality_traits(self, pool_data: dict, fn: str) -> None:
        """校验性格标签池"""
        traits = pool_data.get("personality_traits", {})
        if not isinstance(traits, dict):
            self.result.add_error(fn, "personality_traits", "personality_traits 必须是字典")
            return
        if len(traits) == 0:
            self.result.add_error(fn, "personality_traits", "personality_traits 不能为空")
            return

        for tid, tdata in traits.items():
            prefix = f"personality_traits.{tid}"
            if not isinstance(tdata, dict):
                self.result.add_error(fn, prefix, "必须是字典")
                continue
            self._check_required_fields(tdata, ["name", "group"], fn, prefix)

            # conflict_groups 引用检查
            if "conflict_groups" in tdata and isinstance(tdata["conflict_groups"], list):
                for j, cg in enumerate(tdata["conflict_groups"]):
                    # 检查引用的组名是否在任意标签的 group 中存在（懒校验）
                    all_groups = set()
                    for t2 in traits.values():
                        if isinstance(t2, dict) and "group" in t2:
                            all_groups.add(t2["group"])
                    if cg not in all_groups:
                        self.result.add_warning(fn, f"{prefix}.conflict_groups[{j}]",
                            f"冲突组 '{cg}' 在已有性格组中未找到")

    def _validate_backgrounds(self, pool_data: dict, fn: str, trait_keys: set) -> None:
        """校验背景经历池"""
        backgrounds = pool_data["backgrounds"]
        if not isinstance(backgrounds, list):
            self.result.add_error(fn, "backgrounds", "backgrounds 必须是数组")
            return
        if len(backgrounds) == 0:
            self.result.add_error(fn, "backgrounds", "backgrounds 不能为空")
            return

        seen_ids = set()
        for i, bg in enumerate(backgrounds):
            prefix = f"backgrounds[{i}]"
            if not isinstance(bg, dict):
                self.result.add_error(fn, prefix, "必须是字典")
                continue

            required = ["bg_id", "story", "personality_affinity"]
            self._check_required_fields(bg, required, fn, prefix)

            # bg_id 唯一性
            if "bg_id" in bg and isinstance(bg["bg_id"], str):
                bid = bg["bg_id"]
                if bid in seen_ids:
                    self.result.add_error(fn, f"{prefix}.bg_id", f"bg_id '{bid}' 重复")
                seen_ids.add(bid)

            # personality_affinity 引用检查
            if "personality_affinity" in bg and isinstance(bg["personality_affinity"], list):
                for j, tag in enumerate(bg["personality_affinity"]):
                    if tag not in trait_keys:
                        self.result.add_warning(fn, f"{prefix}.personality_affinity[{j}]",
                            f"性格标签 '{tag}' 在 personality_traits 中未定义")

            # personality_conflict 引用检查
            if "personality_conflict" in bg and isinstance(bg["personality_conflict"], list):
                for j, tag in enumerate(bg["personality_conflict"]):
                    if tag not in trait_keys:
                        self.result.add_warning(fn, f"{prefix}.personality_conflict[{j}]",
                            f"性格标签 '{tag}' 在 personality_traits 中未定义")

            # knowledge 非空检查
            if "knowledge" in bg and isinstance(bg["knowledge"], list) and len(bg["knowledge"]) == 0:
                self.result.add_warning(fn, f"{prefix}.knowledge", "knowledge 建议非空")

            # secrets_weighted
            if "secrets_weighted" in bg and isinstance(bg["secrets_weighted"], list):
                for j, sec in enumerate(bg["secrets_weighted"]):
                    if not isinstance(sec, dict):
                        self.result.add_error(fn, f"{prefix}.secrets_weighted[{j}]", "必须是字典")
                        continue
                    self._check_required_fields(sec, ["secret", "weight"], fn, f"{prefix}.secrets_weighted[{j}]")
                    if "weight" in sec and isinstance(sec["weight"], (int, float)):
                        if sec["weight"] < 1 or sec["weight"] > 1000:
                            self.result.add_error(fn, f"{prefix}.secrets_weighted[{j}].weight",
                                "weight 必须在 1-1000 之间")

            # trigger_flags 和 forbidden_flags 互斥检查
            has_trigger = "trigger_flags" in bg and isinstance(bg["trigger_flags"], list) and len(bg["trigger_flags"]) > 0
            has_forbidden = "forbidden_flags" in bg and isinstance(bg["forbidden_flags"], list) and len(bg["forbidden_flags"]) > 0
            if has_trigger and has_forbidden:
                self.result.add_warning(fn, f"{prefix}",
                    "同时包含 trigger_flags 和 forbidden_flags，建议只使用一种")

    def _validate_name_pool(self, pool_data: dict, fn: str) -> None:
        """校验姓名池"""
        np_ = pool_data.get("name_pool", {})
        if not isinstance(np_, dict):
            self.result.add_error(fn, "name_pool", "name_pool 必须是字典")
            return

        # surnames
        if "surnames" in np_:
            if not isinstance(np_["surnames"], list) or len(np_["surnames"]) < 10:
                self.result.add_warning(fn, "name_pool.surnames", "建议至少 10 个姓氏")
        else:
            self.result.add_error(fn, "name_pool.surnames", "必须包含 surnames")

        # 至少有单名或双名
        has_given = "given_names" in np_ and isinstance(np_["given_names"], list) and len(np_["given_names"]) > 0
        has_two = "two_char_given_names" in np_ and isinstance(np_["two_char_given_names"], list) and len(np_["two_char_given_names"]) > 0
        if not has_given and not has_two:
            self.result.add_error(fn, "name_pool", "given_names 和 two_char_given_names 至少一个非空")

        # generation_chars
        if "generation_chars" in np_ and isinstance(np_["generation_chars"], dict):
            for sect in ["xuanqing", "shenwu", "fulong", "hongchen"]:
                if sect not in np_["generation_chars"]:
                    self.result.add_warning(fn, f"name_pool.generation_chars",
                        f"缺少 '{sect}' 的辈分字")
                elif not isinstance(np_["generation_chars"][sect], list) or len(np_["generation_chars"][sect]) == 0:
                    self.result.add_warning(fn, f"name_pool.generation_chars.{sect}",
                        "辈分字列表不能为空")

    def _validate_npc_pool_cross_references(self, pool_data: dict, fn: str, trait_groups: dict) -> None:
        """NPC池跨字段引用检查"""
        traits = pool_data.get("personality_traits", {})
        if not isinstance(traits, dict):
            return

        # 检查 personality_affinity.excluded 中的标签不与 preferred 在同一组
        identities = pool_data.get("identities", [])
        if not isinstance(identities, list):
            return

        # 构建 tag->group 映射
        tag_to_group = {}
        for tid, tdata in traits.items():
            if isinstance(tdata, dict) and "group" in tdata and "name" in tdata:
                tag_to_group[tdata["name"]] = tdata["group"]

        for i, id_ in enumerate(identities):
            if not isinstance(id_, dict):
                continue
            pa = id_.get("personality_affinity", {})
            if not isinstance(pa, dict):
                continue
            preferred = pa.get("preferred", [])
            excluded = pa.get("excluded", [])
            if not isinstance(preferred, list) or not isinstance(excluded, list):
                continue

            for p_tag in preferred:
                p_group = tag_to_group.get(p_tag)
                if p_group is None:
                    continue
                for e_tag in excluded:
                    e_group = tag_to_group.get(e_tag)
                    # 仅当 preferred 和 excluded 是同一个标签时才警告（矛盾较大）
                    if e_group is not None and p_group == e_group and p_tag == e_tag:
                        self.result.add_warning(fn,
                            f"identities[{i}].personality_affinity",
                            f"preferred 标签 '{p_tag}' 和 excluded 标签 '{e_tag}' 是同一个标签，逻辑矛盾")

    # ----- 运行全部校验 -----
    def validate_all(self) -> bool:
        """运行所有校验，返回是否通过"""
        print(bold("\n===== 内容配置校验 =====\n"))

        # 校验 NPC
        print(blue("[NPC 角色卡]"))
        npc_dir = self.content_dir / "npcs"
        if npc_dir.exists():
            for yaml_file in sorted(npc_dir.glob("*.yaml")) + sorted(npc_dir.glob("*.yml")):
                self.validate_npc(str(yaml_file))
        else:
            self.result.add_warning("content/npcs/", "目录", "npcs 目录不存在")

        # 校验事件
        print(blue("\n[事件配置]"))
        event_dir = self.content_dir / "events"
        if event_dir.exists():
            # 递归扫描子目录（major/、minor/）
            for yaml_file in sorted(event_dir.rglob("*.yaml")) + sorted(event_dir.rglob("*.yml")):
                self.validate_event(str(yaml_file))
        else:
            self.result.add_warning("content/events/", "目录", "events 目录不存在")

        # 校验物品
        print(blue("\n[物品配置]"))
        item_dir = self.content_dir / "items"
        if item_dir.exists():
            for yaml_file in sorted(item_dir.glob("*.yaml")) + sorted(item_dir.glob("*.yml")):
                self.validate_item(str(yaml_file))
        else:
            self.result.add_warning("content/items/", "目录", "items 目录不存在")

        # 校验世界书
        print(blue("\n[世界书配置]"))
        wb_dir = self.content_dir / "world_books"
        if wb_dir.exists():
            for json_file in sorted(wb_dir.glob("*.json")):
                self.validate_world_book(str(json_file))
        else:
            self.result.add_warning("content/world_books/", "目录", "world_books 目录不存在")

        # 校验NPC池
        print(blue("\n[随机NPC池]"))
        npc_pool_dir = self.content_dir / "npc_pool"
        if npc_pool_dir.exists():
            for yaml_file in sorted(npc_pool_dir.glob("*.yaml")) + sorted(npc_pool_dir.glob("*.yml")):
                self.validate_npc_pool(str(yaml_file))
        else:
            self.result.add_warning("content/npc_pool/", "目录", "npc_pool 目录不存在")

        # 打印结果
        print(bold("\n===== 校验结果 =====\n"))
        for err in self.result.errors:
            print(err)
        for warn in self.result.warnings:
            print(warn)

        print(f"\n{self.result.summary()}")
        return self.result.is_valid


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="内容配置校验脚本")
    parser.add_argument("--path", default=None, help="content 目录路径（默认脚本所在目录的上级）")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细校验过程")
    args = parser.parse_args()

    if args.path:
        content_dir = args.path
    else:
        # 默认: 脚本所在目录（content/tools/）的上级
        content_dir = Path(__file__).resolve().parent.parent

    if not os.path.isdir(content_dir):
        print(red(f"错误: 目录不存在: {content_dir}"))
        sys.exit(1)

    validator = ContentValidator(content_dir, verbose=args.verbose)
    success = validator.validate_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()