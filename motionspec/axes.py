"""PoseAxes v0.4 - whole-body axes + one common rule applied to every body part (qualitative, no thresholds).

Nominal axes: 6 whole-body axes + 4 part axes = 10. Every part (몸통, 머리, 왼/오른 팔, 왼/오른 손, 왼/오른 다리)
answers the same 4 part questions, so the slots actually used are 6 + 8 x 4, but a label only writes what differs
from the defaults (대분류 template, then style priors).

Directions are in the body (pelvis) frame: 위 = toward the head, 앞 = belly side, 왼쪽/오른쪽 = the body's own sides.
How the body sits in the world is the 상하 axis, so the up-down flip only touches 상하/대분류.
Limb values may say 바깥/안쪽 (relative to that limb's side); they are stored as absolute 왼쪽/오른쪽.
Face expressions are a separate system and are not part of these labels.
"""
from __future__ import annotations

import json
import math
from itertools import combinations

# ----------------------------------------------------------------------------- whole-body axes
GLOBAL = {
    "대분류": dict(q="몸을 무엇이 어떻게 받치고 있나?",
                values=["서기", "앉기", "눕기", "꿇기", "쪼그리기", "기대기", "짚기", "공중"], neutral="서기",
                anchors={"서기": "두 발로 선 차렷·대기 자세", "앉기": "의자나 바닥에 엉덩이로 앉음", "눕기": "바닥에 누움",
                         "꿇기": "무릎으로 바닥을 짚음(정좌 포함)", "쪼그리기": "발로 딛고 깊이 웅크림", "기대기": "벽·물체에 몸을 맡김",
                         "짚기": "손으로 체중을 받침(엎드려뻗쳐·물구나무)", "공중": "어디에도 닿지 않음(점프)"},
                ops=dict(LR="same", UD=("swap", {"서기": "짚기", "짚기": "서기"}))),
    "좌우": dict(q="좌우가 같은가? 아니면 몸이 어느 쪽으로 쏠리거나 어느 쪽이 주도하나?",
               values=["대칭", "왼 우세", "오른 우세"], neutral="대칭",
               anchors={"대칭": "만세, 차렷", "왼 우세": "왼발 앞 서기, 다리를 왼쪽으로 비껴 앉음", "오른 우세": "오른발 차기, 오른손 흔들기"},
               ops=dict(LR=("swap", {"왼 우세": "오른 우세", "오른 우세": "왼 우세"}), UD="same")),
    "상하": dict(q="몸이 세상에 대해 어떻게 놓였나? (어느 쪽이 위/아래인가)",
               values=["정립", "도립", "등 아래", "배 아래", "왼옆 아래", "오른옆 아래"], neutral="정립",
               anchors={"정립": "머리가 위(서기·앉기)", "도립": "머리가 아래(물구나무)", "등 아래": "반듯이 누움",
                        "배 아래": "엎드림, 엎드려뻗쳐", "왼옆 아래": "왼쪽으로 모로 누움", "오른옆 아래": "오른쪽으로 모로 누움"},
               ops=dict(LR=("swap", {"왼옆 아래": "오른옆 아래", "오른옆 아래": "왼옆 아래"}),
                        UD=("swap", {"정립": "도립", "도립": "정립", "등 아래": "배 아래", "배 아래": "등 아래",
                                     "왼옆 아래": "오른옆 아래", "오른옆 아래": "왼옆 아래"}))),
    "열림": dict(q="몸 전체가 모여 있나, 펼쳐져 있나?",
               values=["닫힘", "중립", "열림"], neutral="중립",
               anchors={"닫힘": "무릎·팔을 모은 단정한 앉기, 웅크림", "중립": "편하게 선 자세", "열림": "다리를 벌려 앉기, 만세"},
               ops=dict(LR="same", UD="same")),
    "남녀": dict(q="이 자세가 어느 쪽으로 읽히나? (인물의 성별이 아님)", values=["여성적", "중립", "남성적"], neutral="중립", rated=True,
               anchors={"여성적": "무릎을 모으고 다리를 기울여 앉기", "중립": "차렷", "남성적": "다리를 벌리고 젖혀 앉기"},
               ops=dict(LR="same", UD="same")),
    "노소": dict(q="이 자세가 몇 살쯤으로 읽히나? (실제 나이가 아님)", values=["아이", "청년", "중년", "노년"], neutral="청년", rated=True,
               anchors={"아이": "몸 전체를 크게 씀", "청년": "중립", "중년": "무게 있게 서고 앉음", "노년": "등이 굽고 무릎을 약간 굽힘"},
               ops=dict(LR="same", UD="same")),
}

# ----------------------------------------------------------------------------- part axes (one rule for every part)
PART_AXES = {
    "향함": dict(q="부위의 뿌리에서 끝을 보면 어느 쪽인가? (어깨→손, 고관절→발, 골반→목, 손목→손끝, 머리는 얼굴이 보는 쪽)",
               values=["위", "아래", "앞", "뒤", "왼쪽", "오른쪽"], combo=3, relative=True),
    "굽힘": dict(q="부위 가운데 마디가 얼마나 접혔나? (팔꿈치, 무릎, 등, 손가락)", values=["폄", "굽힘", "접음"], neutral="폄"),
    "비틂": dict(q="부위가 길이 방향으로 돌았나? (몸통 비틂, 머리 갸웃, 팔·다리 안/바깥 돌림)", values=["없음", "왼쪽", "오른쪽"],
               neutral="없음", relative=True),
    "닿음": dict(q="부위가 무엇에 닿아 있나?", values=["없음", "머리", "몸통", "팔", "손", "다리", "바닥", "물체", "타인"], combo=2,
               neutral="없음"),
}
OPPOSITE = {"위": "아래", "아래": "위", "앞": "뒤", "뒤": "앞", "왼쪽": "오른쪽", "오른쪽": "왼쪽"}

PARTS = {
    "몸통": dict(side=None, meaning={"향함": "위=곧음, 위+앞=숙임, 위+뒤=젖힘, 위+왼쪽=왼 옆굽힘", "굽힘": "등이 둥글게 말림",
                                   "비틂": "가슴이 돌아간 쪽"}),
    "머리": dict(side=None, skip=["굽힘"], meaning={"향함": "얼굴·시선이 향하는 쪽", "비틂": "고개를 갸웃한 쪽"}),
    "왼팔": dict(side="왼"), "오른팔": dict(side="오른"),
    "왼손": dict(side="왼", extra={"굽힘": ["가리킴", "기호"]}, meaning={"굽힘": "폄=펴짐, 굽힘=반쯤 쥠, 접음=주먹"}),
    "오른손": dict(side="오른", extra={"굽힘": ["가리킴", "기호"]}, meaning={"굽힘": "폄=펴짐, 굽힘=반쯤 쥠, 접음=주먹"}),
    "왼다리": dict(side="왼"), "오른다리": dict(side="오른"),
}
GROUPS = {"팔": ("왼팔", "오른팔"), "손": ("왼손", "오른손"), "다리": ("왼다리", "오른다리")}
MIRROR = {"왼팔": "오른팔", "오른팔": "왼팔", "왼손": "오른손", "오른손": "왼손", "왼다리": "오른다리", "오른다리": "왼다리"}
OPS = ("LR", "UD")

# 동작 = 자세 라벨의 시퀀스 + 전이 축. 자세 축 수에는 넣지 않는다.
TRANS = {
    "반복": ["한 번", "반복", "지속"],
    "진동 방향": ["없음", "좌우", "상하", "앞뒤", "회전"],
    "속도": ["느림", "보통", "빠름", "폭발적"],
    "지속": ["순간", "짧음", "유지"],
}

# ----------------------------------------------------------------------------- defaults for pose generation
# 대분류마다의 기본 모양. 라벨에 없는 칸은 (명시값 > 스타일 사전값 > 이 기본 모양 > 중립값) 순서로 채운다.
TEMPLATES = {
    "서기": {"몸통": {"향함": "위"}, "머리": {"향함": "앞"}, "팔": {"향함": "아래"}, "손": {"향함": "아래"},
           "다리": {"향함": "아래", "닿음": "바닥"}},
    "앉기": {"몸통": {"향함": "위"}, "머리": {"향함": "앞"}, "팔": {"향함": "앞+아래", "굽힘": "굽힘", "닿음": "다리"},
           "손": {"향함": "앞"}, "다리": {"향함": "앞+아래", "굽힘": "굽힘", "닿음": "바닥"}},
    "눕기": {"몸통": {"향함": "위", "닿음": "바닥"}, "머리": {"향함": "앞"}, "팔": {"향함": "아래"}, "손": {"향함": "아래"},
           "다리": {"향함": "아래"}},
    "꿇기": {"몸통": {"향함": "위"}, "머리": {"향함": "앞"}, "팔": {"향함": "앞+아래", "굽힘": "굽힘", "닿음": "다리"},
           "손": {"향함": "앞"}, "다리": {"향함": "아래+뒤", "굽힘": "접음", "닿음": "바닥"}},
    "쪼그리기": {"몸통": {"향함": "위+앞", "굽힘": "굽힘"}, "머리": {"향함": "앞"}, "팔": {"향함": "앞+아래", "닿음": "다리"},
             "손": {"향함": "아래"}, "다리": {"향함": "아래", "굽힘": "접음", "닿음": "바닥"}},
    "기대기": {"몸통": {"향함": "위", "닿음": "물체"}, "머리": {"향함": "앞"}, "팔": {"향함": "아래"}, "손": {"향함": "아래"},
            "다리": {"향함": "아래+앞", "닿음": "바닥"}},
    "짚기": {"몸통": {"향함": "위"}, "머리": {"향함": "앞"}, "팔": {"향함": "앞", "닿음": "바닥"}, "손": {"향함": "위"},
           "다리": {"향함": "아래", "닿음": "바닥"}},
    "공중": {"몸통": {"향함": "위"}, "머리": {"향함": "앞"}, "팔": {"향함": "아래"}, "손": {"향함": "아래"},
           "다리": {"향함": "아래", "굽힘": "굽힘"}},
}
# 전체 느낌 축이 비어 있는 칸에 주는 사전값 (문헌 기반 가설, 검증 안 함). "+바깥"은 기본 모양의 향함에 바깥을 더한다는 뜻.
PRIORS = {
    ("열림", "열림"): {"팔": {"향함": "+바깥"}, "다리": {"향함": "+바깥"}},
    ("열림", "닫힘"): {"팔": {"닿음": "몸통"}, "다리": {"닿음": "다리"}},
    ("남녀", "여성적"): {"다리": {"닿음": "다리"}, "몸통": {"향함": "위"}},
    ("남녀", "남성적"): {"다리": {"향함": "+바깥"}, "몸통": {"향함": {"앉기": "위+뒤"}}},
    ("노소", "아이"): {"다리": {"향함": {"서기": "+바깥"}}},
    ("노소", "노년"): {"몸통": {"향함": "위+앞", "굽힘": "굽힘"}, "머리": {"향함": "앞+아래"}, "다리": {"굽힘": {"서기": "굽힘"}}},
}


# ----------------------------------------------------------------------------- values
def _part_values(part, axis):
    return PART_AXES[axis]["values"] + PARTS[part].get("extra", {}).get(axis, [])


def _resolve(part, axis, raw):
    """'앞+아래+바깥' on 왼다리 -> '아래+앞+왼쪽' (aliases resolved, combo checked, canonical order)."""
    spec, side = PART_AXES[axis], PARTS[part]["side"]
    comps = []
    for c in str(raw).split("+"):
        if c in ("바깥", "안쪽"):
            if not (spec.get("relative") and side):
                raise ValueError(f"{part}.{axis}: '{c}' is only for left/right parts")
            c = (side if c == "바깥" else {"왼": "오른", "오른": "왼"}[side]) + "쪽"
        if c not in _part_values(part, axis):
            raise ValueError(f"{part}.{axis}: {c!r} not in {_part_values(part, axis)}")
        if c not in comps:
            comps.append(c)
    if len(comps) > spec.get("combo", 1):
        raise ValueError(f"{part}.{axis}={raw!r}: at most {spec.get('combo', 1)} values")
    if len(comps) > 1 and ("없음" in comps or any(OPPOSITE.get(c) in comps for c in comps)):
        raise ValueError(f"{part}.{axis}={raw!r}: contradictory combination")
    order = _part_values(part, axis)
    return "+".join(sorted(comps, key=order.index))


def expand(label: dict) -> dict:
    """Short label -> canonical form: whole-body values + {part: {axis: value}}. Groups (팔/손/다리) fill both sides,
    a named side overrides the group per axis."""
    out = {k: v for k, v in label.items() if k in GLOBAL}
    for k, v in out.items():
        if v != "*" and v not in GLOBAL[k]["values"]:
            raise ValueError(f"{k}={v!r} not in {GLOBAL[k]['values']}")
    parts = {}
    for key in [k for k in label if k in GROUPS] + [k for k in label if k in PARTS]:
        for part in GROUPS.get(key, (key,)):
            for axis, raw in label[key].items():
                if axis not in PART_AXES or axis in PARTS[part].get("skip", []):
                    raise ValueError(f"{part} has no axis {axis!r}")
                parts.setdefault(part, {})[axis] = _resolve(part, axis, raw)
    unknown = set(label) - set(GLOBAL) - set(GROUPS) - set(PARTS)
    if unknown:
        raise KeyError(unknown)
    out["부위"] = {p: parts[p] for p in PARTS if p in parts}
    return out


def validate(label: dict):
    expand(label)


def _swap_lr(value):
    return "+".join({"왼쪽": "오른쪽", "오른쪽": "왼쪽"}.get(c, c) for c in value.split("+"))


def flip(label: dict, op: str) -> dict:
    """Symmetry operation on a label (returns canonical form). LR swaps left/right parts and every 왼쪽/오른쪽 value;
    UD only changes how the body sits in the world (상하, 대분류), because part directions are in the body frame."""
    e = expand(label) if "부위" not in label else label
    out = {}
    for k, v in e.items():
        if k == "부위":
            continue
        rule = GLOBAL[k]["ops"][op]
        out[k] = v if rule == "same" or v == "*" else rule[1].get(v, v)
    parts = {}
    for p, axes in e["부위"].items():
        q = MIRROR.get(p, p) if op == "LR" else p
        parts[q] = {a: (_resolve(q, a, _swap_lr(v)) if op == "LR" else v) for a, v in axes.items()}
    out["부위"] = {p: parts[p] for p in PARTS if p in parts}
    return out


def symmetric(label: dict) -> bool:
    """Is the pose its own mirror image? (the 좌우 value itself is ignored)"""
    e = expand(label) if "부위" not in label else label
    f = flip(e, "LR")
    return {k: v for k, v in f.items() if k != "좌우"} == {k: v for k, v in e.items() if k != "좌우"}


def check(label: dict):
    """Soft consistency warnings between axes (the label is still usable)."""
    e = expand(label) if "부위" not in label else label
    w = []
    if e.get("좌우") == "대칭" and not symmetric(e):
        w.append("부위 값이 좌우로 다른데 좌우가 '대칭'")
    if e.get("좌우") in ("왼 우세", "오른 우세") and symmetric(e) and e["부위"]:
        w.append("부위 값이 좌우로 같은데 좌우가 우세로 적힘 (쏠림만 있는 자세면 무시)")
    lying = ("등 아래", "배 아래", "왼옆 아래", "오른옆 아래")
    if e.get("대분류") == "눕기" and e.get("상하") not in (None, "*") + lying:
        w.append("눕기인데 상하가 누운 방향이 아님")
    if e.get("상하") == "도립" and e.get("대분류") not in (None, "*", "짚기", "공중"):
        w.append("도립인데 대분류가 짚기·공중이 아님")
    return w


def fill(label: dict) -> dict:
    """Complete every slot for pose generation: explicit > whole-body priors > 대분류 template > neutral."""
    e = expand(label)
    base = e.get("대분류", "서기")
    if base == "*":
        base = "서기"
    filled = {p: dict(a) for p, a in e["부위"].items()}

    def put(key, axis, val, from_prior):
        for part in GROUPS.get(key, (key,)):
            if axis in PARTS[part].get("skip", []) or axis in filled.get(part, {}):
                continue
            if isinstance(val, dict):
                val2 = val.get(base)
                if val2 is None:
                    continue
            else:
                val2 = val
            if val2.startswith("+"):
                t = TEMPLATES[base].get(key, {}).get(axis) or TEMPLATES[base].get(_group_of(part), {}).get(axis)
                val2 = (t + val2) if t else val2[1:]
            try:
                filled.setdefault(part, {})[axis] = _resolve(part, axis, val2)
            except ValueError:
                if not from_prior:
                    raise

    for gk in ("열림", "남녀", "노소"):
        for key, axes in PRIORS.get((gk, e.get(gk)), {}).items():
            for axis, val in axes.items():
                put(key, axis, val, True)
    for key, axes in TEMPLATES[base].items():
        for axis, val in axes.items():
            put(key, axis, val, False)
    for part in PARTS:
        for axis, spec in PART_AXES.items():
            if "neutral" in spec and axis not in PARTS[part].get("skip", []):
                filled.setdefault(part, {}).setdefault(axis, spec["neutral"])
    out = {k: e.get(k, GLOBAL[k]["neutral"] if not GLOBAL[k].get("rated") else "*") for k in GLOBAL}
    out["부위"] = {p: {a: filled[p][a] for a in PART_AXES if a in filled[p]} for p in PARTS if p in filled}
    return out


def _group_of(part):
    return next((g for g, ps in GROUPS.items() if part in ps), part)


def code(label: dict) -> str:
    e = expand(label) if "부위" not in label else label
    head = " / ".join(f"{k}:{e.get(k, '*')}" for k in GLOBAL)
    body = "; ".join(f"{p} " + ", ".join(f"{a} {v}" for a, v in ax.items()) for p, ax in e["부위"].items())
    return head + ("\n    " + body if body else "")


def bits():
    def n(axis):
        spec = PART_AXES[axis]
        vals = [v for v in spec["values"] if v != "없음"]
        k = spec.get("combo", 1)
        good = [c for r in range(1, k + 1) for c in combinations(vals, r) if not any(OPPOSITE.get(x) in c for x in c)]
        return len(good) + (1 if "없음" in spec["values"] else 0)
    g = sum(math.log2(len(a["values"])) for a in GLOBAL.values())
    per_part = {a: math.log2(n(a)) for a in PART_AXES}
    parts = sum(sum(v for a, v in per_part.items() if a not in PARTS[p].get("skip", [])) for p in PARTS)
    return dict(whole_body=g, per_part_axis=per_part, all_parts=parts, total=g + parts)


def export(path):
    b = bits()
    out = {"version": "0.4", "operations": {"LR": "좌우 반전", "UD": "상하 반전"},
           "nominal_axes": {"전체": list(GLOBAL), "부위 공통": list(PART_AXES)}, "parts": PARTS, "groups": GROUPS,
           "whole_body": GLOBAL, "part_axes": PART_AXES, "templates": TEMPLATES,
           "priors": {f"{k[0]}={k[1]}": v for k, v in PRIORS.items()}, "transitions": TRANS,
           "bits": {"whole_body": round(b["whole_body"], 1), "all_parts": round(b["all_parts"], 1)}}
    json.dump(out, open(path, "w"), ensure_ascii=False, indent=1)


# ----------------------------------------------------------------------------- examples (short form)
EXAMPLES = {
    "만세": {"대분류": "서기", "좌우": "대칭", "상하": "정립", "열림": "열림",
           "팔": {"향함": "위", "굽힘": "폄"}, "머리": {"향함": "위+앞"}},
    "단정하게 비껴 앉기 (다리를 왼쪽으로)": {"대분류": "앉기", "좌우": "왼 우세", "상하": "정립", "열림": "닫힘", "남녀": "여성적",
                                "다리": {"향함": "아래+앞+왼쪽", "굽힘": "굽힘", "닿음": "다리"},
                                "팔": {"향함": "아래+앞", "굽힘": "굽힘", "닿음": "다리"}, "머리": {"비틂": "왼쪽"}},
    "다리 벌려 젖혀 앉기": {"대분류": "앉기", "좌우": "대칭", "상하": "정립", "열림": "열림", "남녀": "남성적",
                     "몸통": {"향함": "위+뒤", "닿음": "물체"}, "다리": {"향함": "아래+앞+바깥", "굽힘": "굽힘", "닿음": "바닥"},
                     "팔": {"향함": "아래", "닿음": "다리"}},
    "다리 꼬고 앉기 (오른다리가 위)": {"대분류": "앉기", "좌우": "오른 우세", "상하": "정립", "열림": "닫힘",
                             "다리": {"향함": "아래+앞", "굽힘": "굽힘"}, "왼다리": {"닿음": "바닥"},
                             "오른다리": {"향함": "앞+안쪽", "닿음": "다리"},
                             "팔": {"향함": "아래+앞", "굽힘": "굽힘", "닿음": "다리"}},
    "바닥에 한쪽 무릎 세워 앉기 (오른 무릎)": {"대분류": "앉기", "좌우": "오른 우세", "상하": "정립", "열림": "닫힘",
                                  "몸통": {"굽힘": "굽힘"}, "머리": {"향함": "앞+아래"},
                                  "왼다리": {"향함": "앞+안쪽", "굽힘": "접음", "닿음": "바닥"},
                                  "오른다리": {"향함": "앞+아래", "굽힘": "접음", "닿음": "바닥"},
                                  "오른팔": {"향함": "앞+아래", "닿음": "다리"}},
    "오른발 돌려차기, 무릎 접은 순간": {"대분류": "서기", "좌우": "오른 우세", "상하": "정립", "열림": "닫힘",
                              "몸통": {"비틂": "왼쪽"}, "팔": {"향함": "앞+아래", "굽힘": "접음"}, "손": {"굽힘": "접음"},
                              "왼다리": {"향함": "아래", "닿음": "바닥"}, "오른다리": {"향함": "앞+바깥", "굽힘": "접음"}},
    "오른발 돌려차기, 충격 순간": {"대분류": "서기", "좌우": "오른 우세", "상하": "정립", "열림": "열림",
                            "몸통": {"향함": "위+왼쪽", "비틂": "왼쪽"}, "팔": {"향함": "아래+바깥"}, "손": {"굽힘": "접음"},
                            "왼다리": {"향함": "아래", "닿음": "바닥"}, "오른다리": {"향함": "바깥", "굽힘": "폄"}},
    "앞서기 아래막기 (왼발 앞)": {"대분류": "서기", "좌우": "왼 우세", "상하": "정립",
                           "왼다리": {"향함": "아래+앞", "굽힘": "굽힘", "닿음": "바닥"},
                           "오른다리": {"향함": "아래+뒤", "굽힘": "폄", "닿음": "바닥"},
                           "왼팔": {"향함": "아래+앞", "굽힘": "폄"}, "오른팔": {"향함": "아래", "굽힘": "접음", "닿음": "몸통"},
                           "손": {"굽힘": "접음"}},
    "손 흔들기 (오른손)": {"대분류": "서기", "좌우": "오른 우세", "상하": "정립",
                     "오른팔": {"향함": "위+바깥", "굽힘": "접음"}, "오른손": {"향함": "위", "굽힘": "폄"}},
    "물구나무서기": {"대분류": "짚기", "좌우": "대칭", "상하": "도립",
               "팔": {"향함": "위", "굽힘": "폄", "닿음": "바닥"}, "다리": {"향함": "아래", "굽힘": "폄", "닿음": "없음"}},
    "반듯이 누워 쉬기": {"대분류": "눕기", "좌우": "대칭", "상하": "등 아래", "열림": "중립",
                  "몸통": {"닿음": "바닥"}, "팔": {"향함": "아래+바깥", "닿음": "바닥"}},
    "오른쪽으로 모로 누워 다리 접기": {"대분류": "눕기", "좌우": "오른 우세", "상하": "오른옆 아래", "열림": "닫힘",
                           "몸통": {"굽힘": "굽힘", "닿음": "바닥"}, "다리": {"향함": "아래+앞", "굽힘": "굽힘", "닿음": "다리"},
                           "팔": {"향함": "앞", "굽힘": "굽힘"}},
}
EXAMPLE_TRANS = {"손 흔들기 (오른손)": {"반복": "반복", "진동 방향": "좌우", "속도": "보통", "지속": "유지"}}


if __name__ == "__main__":
    b = bits()
    print(f"명목 축: 전체 {len(GLOBAL)} + 부위 공통 {len(PART_AXES)} = {len(GLOBAL) + len(PART_AXES)}  |  "
          f"실사용 칸: {len(GLOBAL)} + {sum(len(PART_AXES) - len(p.get('skip', [])) for p in PARTS.values())}")
    print(f"비트: 전체 {b['whole_body']:.1f} + 부위 {b['all_parts']:.1f} = {b['total']:.1f}  "
          f"(부위 1개당 " + ", ".join(f"{a} {v:.1f}" for a, v in b["per_part_axis"].items()) + ")")
    seen = {}
    for name, L in EXAMPLES.items():
        e = expand(L)
        assert not check(e), (name, check(e))
        for op in OPS:
            assert flip(flip(e, op), op) == e, (name, op)                      # flipping twice restores the label
        assert flip(flip(e, "LR"), "UD") == flip(flip(e, "UD"), "LR"), name    # the two flips commute
        key = json.dumps(e, ensure_ascii=False, sort_keys=True)
        assert key not in seen, (name, seen.get(key))                          # examples are distinguishable
        seen[key] = name
        f = fill(L)
        assert flip(flip(f, "LR"), "LR") == f, name
        print(f"\n{name}\n  {code(e)}")
        if not symmetric(e):
            print(f"  좌우 반전 → {code(flip(e, 'LR'))}")
    for name in EXAMPLE_TRANS:
        for k, v in EXAMPLE_TRANS[name].items():
            assert v in TRANS[k], (name, k, v)
    print("\n상하 반전 예) 만세 →", code(flip(EXAMPLES["만세"], "UD")))
    print("\n채우기 예) 앉기 + 여성적 →", code(fill({"대분류": "앉기", "남녀": "여성적"})))
    print("채우기 예) 앉기 + 남성적 →", code(fill({"대분류": "앉기", "남녀": "남성적"})))
    print("채우기 예) 서기 + 노년 →", code(fill({"대분류": "서기", "노소": "노년"})))
