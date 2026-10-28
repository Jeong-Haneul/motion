"""PoseAxes v0.7 - base label = 카테1 > 카테2 (shape) + 남녀 / 노소 / 에너지, with optional detail controls.

카테1·카테2 classify the whole-body shape (catalog.py). 명카테1 > 명카테2 (field > known pose) is an independent,
optional knowledge tag; its main job is an auxiliary search index that checks the shape list has no holes.
남녀·노소·에너지 carry the degree for the whole body and are applied conceptually when a pose is made.

Detail controls override parts (팔·다리 = 방향·뻗음 with IK prototypes, 몸통, 머리, 손, 발끝).
Shapes that differ only by a left-right flip are kept once, in their right-side form; a label marks the left-side
form with 좌우반전=True (the mirror image). Part values (갸웃@왼) still name sides. Face expressions are separate.
"""
from __future__ import annotations

import json

from .catalog import CAT1, CAT2, NAMED

# 카테2 기본 자세 중 부위 값으로 적어 둔 것 (오른쪽 기준). 적지 않은 카테2는 이름과 남녀·노소·에너지로 관념적으로 만든다.
BASE_PARTS = {
    ("서기", "바로 서기"): {},
    ("서기", "발 모아 서기"): {"다리": "가로아래·폄"},
    ("서기", "다리 벌려 서기"): {"다리": "바깥아래·폄"},
    ("서기", "짝다리"): {"왼다리": "아래·굽힘"},
    ("서기", "한 발 앞 내딛기"): {"오른다리": "앞아래·폄", "왼다리": "뒤아래·폄"},
    ("서기", "런지"): {"오른다리": "앞아래·굽힘", "왼다리": "뒤아래·폄"},
    ("서기", "기마 서기"): {"다리": "바깥아래·굽힘"},
    ("서기", "무릎 굽혀 서기"): {"다리": "앞아래·굽힘"},
    ("서기", "한 발 서기(무릎 올림)"): {"오른다리": "앞아래·접음"},
    ("서기", "한 발 서기(다리 앞으로)"): {"오른다리": "앞·폄"},
    ("서기", "한 발 서기(다리 옆으로)"): {"오른다리": "바깥·폄"},
    ("서기", "한 발 서기(다리 뒤로)"): {"오른다리": "뒤·폄"},
    ("서기", "한 발 서기(발바닥을 다른 다리에)"): {"오른다리": "아래·접음"},
    ("서기", "숙여 서기"): {"몸통": "숙임", "머리": "아래"},
    ("서기", "만세"): {"팔": "위·폄", "머리": "위"},
    ("서기", "한 손 굽혀 올리기"): {"오른팔": "바깥위·접음"},
    ("서기", "팔짱"): {"팔": "가로질러·접음"},
    ("서기", "뒷짐"): {"팔": "뒤아래·굽힘"},
    ("서기", "양손 허리"): {"팔": "바깥아래·접음"},
    ("서기", "한 팔 앞으로 뻗고 다른 팔 허리에"): {"오른팔": "앞·폄", "왼팔": "아래·접음"},
    ("서기", "두 손 얼굴 앞에 모으기"): {"팔": "앞위·접음"},
    ("앉기", "바로 앉기"): {"다리": "앞아래·굽힘", "팔": "앞아래·굽힘"},
    ("앉기", "기대 앉기"): {"다리": "앞아래·굽힘", "몸통": "젖힘"},
    ("앉기", "다리 꼬기"): {"왼다리": "앞아래·굽힘", "오른다리": "가로질러·굽힘", "팔": "앞아래·굽힘"},
    ("앉기", "비껴 앉기"): {"오른다리": "앞바깥·굽힘", "왼다리": "가로질러·굽힘", "팔": "앞아래·굽힘"},
    ("앉기", "양반다리"): {"다리": "가로질러·접음", "팔": "앞아래·굽힘"},
    ("앉기", "한쪽 무릎 세워 앉기"): {"오른다리": "앞·접음", "왼다리": "가로질러·접음", "오른팔": "앞·굽힘"},
    ("앉기", "다리 뻗고 앉기"): {"다리": "앞·폄"},
    ("앉기", "다리 뻗고 손 뒤로 짚기"): {"다리": "앞·폄", "팔": "뒤아래·폄"},
    ("앉기", "무릎 껴안고 앉기"): {"다리": "앞·접음", "팔": "앞·굽힘", "몸통": "말림"},
    ("앉기", "턱 괴고 앉기"): {"다리": "앞아래·굽힘", "오른팔": "앞위·접음", "몸통": "숙임", "머리": "갸웃@오른"},
    ("눕기", "팔베개"): {"팔": "위·접음"},
    ("눕기", "모로 눕기"): {"다리": "앞아래·굽힘"},
    ("눕기", "모로 웅크려 눕기"): {"다리": "앞아래·접음", "팔": "앞·굽힘", "몸통": "말림"},
    ("꿇기", "정좌"): {"다리": "뒤아래·접음", "팔": "앞아래·굽힘"},
    ("꿇기", "무릎 서기"): {"다리": "뒤아래·굽힘"},
    ("꿇기", "한 무릎 꿇기"): {"오른다리": "앞아래·굽힘", "왼다리": "뒤아래·굽힘"},
    ("쪼그리기", "쪼그려 앉기"): {"다리": "아래·접음", "팔": "앞아래·굽힘", "몸통": "숙임"},
    ("쪼그리기", "벌려 쪼그리기"): {"다리": "바깥아래·접음", "팔": "앞아래·굽힘"},
    ("기대기", "벽에 등 기대기"): {"다리": "앞아래·폄"},
    ("기대기", "벽에 어깨 기대기"): {"몸통": "옆굽힘@오른", "왼다리": "가로질러·폄"},
    ("짚기", "엎드려뻗쳐"): {"팔": "앞·폄"},
    ("짚기", "네발"): {"팔": "앞·폄", "다리": "앞·접음"},
    ("짚기", "옆으로 짚기"): {"오른팔": "바깥·폄", "왼팔": "바깥·폄"},
    ("짚기", "물구나무"): {"팔": "위·폄"},
    ("공중", "만세 뛰기"): {"팔": "위·폄"},
    ("공중", "벌려 뛰기"): {"팔": "바깥위·폄", "다리": "바깥아래·폄"},
    ("공중", "웅크려 뛰기"): {"다리": "앞·접음", "팔": "앞·굽힘"},
    ("공중", "다리 앞뒤로 벌려 뛰기"): {"오른다리": "앞·폄", "왼다리": "뒤아래·굽힘", "팔": "바깥·폄"},
}
STYLE = {
    "남녀": dict(values=["여성적", "중립", "남성적"], neutral="중립",
               q="이성이 매력적으로, 또는 동성이 동경하는 모습으로 보는 여성다움·남성다움이 드러나나? (인물의 성별이 아님)",
               effect="여성적: 골반 기울인 S자 곡선, 허리선, 다리를 길어 보이게(교차·발끝), 고개 기울임, 손을 얼굴·머리 가까이 / "
                      "남성적: 넓은 어깨, 편 가슴, 넓은 스탠스, 턱 들기, 팔 근육이 드러나는 팔짱·허리 손"),
    "노소": dict(values=["아이", "청년", "중년", "노년"], neutral="청년",
               effect="척추 굽음, 무릎 굽힘, 몸통 숙임, 보폭(노년으로 갈수록 커지거나 줄어듦)"),
    "에너지": dict(values=["처짐", "편안", "보통", "힘참", "폭발적"], neutral="보통",
                effect="뻗음률(처짐은 덜 뻗고 폭발적은 끝까지), 척추 펴짐, 자세 폭, 동작이면 속도"),
}
BASE_AXES = ["카테1", "카테2", "남녀", "노소", "에너지"]
NAMED_AXES = ["명카테1", "명카테2"]
LABEL_KEYS = BASE_AXES + ["좌우반전"] + NAMED_AXES + ["부위"]

# ----------------------------------------------------------------------------- detail controls (parts)
PARTS = ["몸통", "머리", "왼팔", "오른팔", "왼손", "오른손", "왼다리", "오른다리", "왼발끝", "오른발끝"]
GROUPS = {"팔": ("왼팔", "오른팔"), "손": ("왼손", "오른손"), "다리": ("왼다리", "오른다리"), "발끝": ("왼발끝", "오른발끝")}
MIRROR = {"왼팔": "오른팔", "오른팔": "왼팔", "왼손": "오른손", "오른손": "왼손", "왼다리": "오른다리", "오른다리": "왼다리",
          "왼발끝": "오른발끝", "오른발끝": "왼발끝"}
SW = {"왼": "오른", "오른": "왼"}

# 팔·다리 방향 (뿌리에서 끝을 본 쪽, 몸 기준). 벡터는 (바깥, 위, 앞) - 왼쪽 부위는 바깥이 몸의 왼쪽.
DIRS = {"위": (0, 1, 0), "아래": (0, -1, 0), "앞": (0, 0, 1), "뒤": (0, 0, -1), "바깥": (1, 0, 0), "가로질러": (-1, 0, 0.6),
        "앞위": (0, 1, 1), "앞아래": (0, -1, 1), "바깥위": (1, 1, 0), "바깥아래": (1, -1, 0), "앞바깥": (1, 0, 1), "뒤아래": (0, -1, -1),
        "가로아래": (-0.4, -1, 0)}
REACH = {"폄": 1.0, "굽힘": 0.7, "접음": 0.35}      # 끝까지 거리 / 팔(다리) 길이 - 라벨이 아니라 대표값
TORSO = ["곧음", "숙임", "젖힘", "말림", "옆굽힘@왼", "옆굽힘@오른", "비틂@왼", "비틂@오른"]
HEAD = ["앞", "위", "아래", "옆@왼", "옆@오른", "갸웃@왼", "갸웃@오른"]
HAND = ["자연", "펴짐", "주먹", "가리킴", "브이"]
FOOT = ["앞", "바깥", "안쪽"]                          # 발끝이 향하는 쪽 (바깥 = 턴아웃, 팔자)
DEFAULT_PARTS = {"몸통": "곧음", "머리": "앞", "팔": "아래·폄", "손": "자연", "다리": "아래·폄", "발끝": "앞"}

PUT_DEFAULT = "정립"
OPS = ("LR", "UD")
# 상하 반전은 카테2 사이의 대응으로만 정의한다 (나머지는 다시 라벨링).
UD_MAP = {("서기", "바로 서기"): ("짚기", "물구나무"), ("눕기", "반듯이 눕기"): ("눕기", "엎드려 눕기")}
UD_MAP.update({v: k for k, v in list(UD_MAP.items())})

TRANS = {"반복": ["한 번", "반복", "지속"], "진동 방향": ["없음", "좌우", "상하", "앞뒤", "회전"],
         "속도": ["느림", "보통", "빠름", "폭발적"], "지속": ["순간", "짧음", "유지"]}


def _part_kind(part):
    for kind in ("발끝", "다리", "팔", "손"):
        if part.endswith(kind):
            return kind
    return part


def _check_part_value(part, v):
    kind = _part_kind(part)
    if kind in ("팔", "다리"):
        d, _, r = v.partition("·")
        if d not in DIRS or r not in REACH:
            raise ValueError(f"{part}={v!r}: write 방향·뻗음, 방향 in {list(DIRS)}, 뻗음 in {list(REACH)}")
        return
    allowed = {"몸통": TORSO, "머리": HEAD, "손": HAND, "발끝": FOOT}[kind]
    if v not in allowed:
        raise ValueError(f"{part}={v!r} not in {allowed}")


def _expand_parts(d):
    """{'다리': x, '오른다리': y} -> per-part dict; a named side overrides its group."""
    out = {}
    for key in [k for k in d if k in GROUPS] + [k for k in d if k in PARTS]:
        for p in GROUPS.get(key, (key,)):
            out[p] = d[key]
    unknown = set(d) - set(GROUPS) - set(PARTS)
    if unknown:
        raise KeyError(unknown)
    return out


def _mirror_parts(parts):
    return {MIRROR.get(p, p): (v.replace("@왼", "@#").replace("@오른", "@왼").replace("@#", "@오른") if "@" in v else v)
            for p, v in parts.items()}


def _no_side(what, value):
    if "@" in str(value):
        raise ValueError(f"{what}={value!r}: 카테2·명카테2는 오른쪽 기준 하나뿐이다. 왼쪽이면 좌우반전=True로 적는다")
    return value


def _named(label):
    """Spec of the 명카테2 in the label, or None."""
    n1, n2 = label.get("명카테1"), label.get("명카테2")
    return None if n2 is None else NAMED[n1][n2]


def _cat(label):
    """(카테1, 카테2) - written in the label; if blank, the shape the named pose points at (used to build the pose)."""
    if "카테1" in label:
        return label["카테1"], label.get("카테2")
    spec = _named(label)
    return (None, None) if spec is None else spec["shape"]


# ----------------------------------------------------------------------------- label operations
def validate(label: dict):
    for k in label:
        if k not in LABEL_KEYS:
            raise KeyError(k)
    if label.get("좌우반전") not in (None, True):
        raise ValueError("좌우반전은 True이거나 없어야 한다 (오른쪽 기준이면 적지 않음)")
    n1, n2 = label.get("명카테1"), label.get("명카테2")
    if n2 is not None and n1 is None:
        raise ValueError("명카테2 needs 명카테1")
    if n1 is not None:
        if n1 not in NAMED:
            raise ValueError(f"명카테1={n1!r} not in {list(NAMED)}")
        if n2 is not None and _no_side("명카테2", n2) not in NAMED[n1]:
            raise ValueError(f"명카테2={n2!r} is not under 명카테1={n1!r}: {list(NAMED[n1])}")
    if "카테2" in label and "카테1" not in label:
        raise ValueError("카테2 needs 카테1")
    c1, c2 = _cat(label)
    if c1 is None:
        raise ValueError("카테1 is blank and there is no named pose to take the shape from")
    if c1 not in CAT1:
        raise ValueError(f"카테1={c1!r} not in {CAT1}")
    if c2 is None or _no_side("카테2", c2) not in CAT2[c1]:
        raise ValueError(f"카테2={c2!r} is not under 카테1={c1!r}: {list(CAT2[c1])}")
    for k, a in STYLE.items():
        if k in label and label[k] not in a["values"]:
            raise ValueError(f"{k}={label[k]!r} not in {a['values']}")
    for spec in (_named(label) or {}).get("parts", {}), label.get("부위", {}):
        for p, v in _expand_parts(spec).items():
            _check_part_value(p, v)


def resolve(label: dict) -> dict:
    """Everything needed to build the pose: style values, how the body is placed, and one value per part.
    The right-side form is built from defaults < 카테2 base posture < 명자세 detail; 좌우반전 mirrors it;
    부위 (written as the pose actually is) goes on last."""
    validate(label)
    c1, c2 = _cat(label)
    spec = CAT2[c1][c2]
    parts = _expand_parts(DEFAULT_PARTS)
    parts.update(_expand_parts(BASE_PARTS.get((c1, c2), {})))
    nspec = _named(label)
    if nspec is not None:
        parts.update(_expand_parts(nspec["parts"]))
    put = spec.get("put") or PUT_DEFAULT
    if put == "옆 아래":
        put = "오른옆 아래"
    if label.get("좌우반전"):
        parts = _mirror_parts(parts)
        put = {"오른옆 아래": "왼옆 아래"}.get(put, put)
    parts.update(_expand_parts(label.get("부위", {})))
    return dict(카테1=c1, 카테2=c2, 좌우반전=bool(label.get("좌우반전")), 명카테1=label.get("명카테1"),
                명카테2=label.get("명카테2"), 놓임=put, **{k: label.get(k, a["neutral"]) for k, a in STYLE.items()},
                부위={p: parts[p] for p in PARTS})


def flip(label: dict, op: str):
    """LR: toggle 좌우반전 and swap left/right detail parts. UD: only between 카테2 pairs in UD_MAP (else None)."""
    out = dict(label)
    if op == "LR":
        if label.get("좌우반전"):
            del out["좌우반전"]
        else:
            out["좌우반전"] = True
        if "부위" in label:
            out["부위"] = _mirror_parts(label["부위"])       # group keys (팔/손/다리) stay, named sides swap
        return out
    if "카테1" not in label:
        return None
    key = (label["카테1"], label["카테2"])
    if key not in UD_MAP:
        return None
    out["카테1"], out["카테2"] = UD_MAP[key]
    return out


def ik_target(part, value):
    """Part value -> (unit direction in the body frame (x 오른쪽, y 위, z 앞), reach ratio). Arms and legs only."""
    d, _, r = value.partition("·")
    x, y, z = DIRS[d]
    if part.startswith("왼"):
        x = -x
    n = (x * x + y * y + z * z) ** 0.5
    return (x / n, y / n, z / n), REACH[r]


def code(label: dict) -> str:
    s = " / ".join(str(label.get(k, "·")) for k in BASE_AXES) + (" [좌우반전]" if label.get("좌우반전") else "")
    if label.get("명카테1"):
        s += f"  | {label['명카테1']}" + (f" > {label['명카테2']}" if label.get("명카테2") else "")
    if label.get("부위"):
        s += "  + " + ", ".join(f"{p} {v}" for p, v in label["부위"].items())
    return s


def count():
    n2 = sum(len(v) for v in CAT2.values())
    sided = sum(1 for v in CAT2.values() for s in v.values() if s["side"])
    named = {k: len(v) for k, v in NAMED.items()}
    return dict(카테2=n2, 좌우가_다른_카테2=sided, 카테2_카테1별={k: len(v) for k, v in CAT2.items()},
                기본형_조합=n2 * 3 * 4 * 5, 명자세=named)


def coverage():
    """명자세 -> 카테2 대조: which 카테2 each field's known poses land on, per 카테1, and any pose with no shape."""
    hit, missing = {}, []
    for field, items in NAMED.items():
        for name, spec in items.items():
            c1, c2 = spec["shape"]
            if c1 not in CAT2 or c2 not in CAT2[c1]:
                missing.append((field, name, c1, c2))
                continue
            hit.setdefault((c1, c2), []).append(f"{field}>{name}")
    per = {c1: (sum(1 for c2 in CAT2[c1] if (c1, c2) in hit), len(CAT2[c1])) for c1 in CAT1}
    probes = {c1: sum(len(v) for (a, _), v in hit.items() if a == c1) for c1 in CAT1}
    return dict(hit=hit, missing=missing, per_cat1=per, probes_per_cat1=probes)


def export(path):
    out = {"version": "0.7", "base_axes": BASE_AXES, "named_axes": NAMED_AXES, "카테1": CAT1, "카테2": CAT2, "style": STYLE,
           "named": {f: {n: dict(v, shape=" > ".join(v["shape"])) for n, v in items.items()} for f, items in NAMED.items()},
           "base_parts": {f"{a} > {b}": v for (a, b), v in BASE_PARTS.items()},
           "detail": {"parts": PARTS, "groups": GROUPS, "arm_leg": {"방향": DIRS, "뻗음": REACH}, "몸통": TORSO, "머리": HEAD,
                      "손": HAND, "발끝": FOOT, "default": DEFAULT_PARTS},
           "priority": "기본값 < 카테2 기본 자세 < 명자세 추가 제어 < 부위",
           "flip": {"LR": "좌우반전 표시를 켜고 끔, 좌우 부위를 맞바꿈 (카테2·명카테2는 오른쪽 기준 하나뿐)",
                    "UD": {f"{a[0]}.{a[1]}": f"{b[0]}.{b[1]}" for a, b in UD_MAP.items()}},
           "transitions": TRANS, "count": count()}
    json.dump(out, open(path, "w"), ensure_ascii=False, indent=1)


# ----------------------------------------------------------------------------- examples
EXAMPLES = {
    "차렷": dict(카테1="서기", 카테2="바로 서기", 에너지="힘참"),
    "편히 서 있기": dict(카테1="서기", 카테2="바로 서기", 에너지="편안"),
    "노인이 서 있기": dict(카테1="서기", 카테2="바로 서기", 노소="노년", 에너지="처짐"),
    "만세": dict(카테1="서기", 카테2="만세", 에너지="힘참", 명카테1="일상", 명카테2="만세"),
    "앉아서 만세": dict(카테1="앉기", 카테2="바로 앉기", 부위={"팔": "위·폄", "머리": "위"}),
    "여성스럽게 비껴 앉기": dict(카테1="앉기", 카테2="비껴 앉기", 좌우반전=True, 남녀="여성적", 에너지="편안", 부위={"머리": "갸웃@왼"}),
    "다리 벌려 젖혀 앉기": dict(카테1="앉기", 카테2="기대 앉기", 남녀="남성적", 에너지="편안"),
    "다리 꼬고 턱 괴기": dict(카테1="앉기", 카테2="다리 꼬기", 명카테1="일상", 명카테2="턱 괴기"),
    "손 흔들기": dict(카테1="서기", 카테2="한 손 굽혀 올리기", 명카테1="일상", 명카테2="손 흔들기(중간)"),
    "아래막기 (카테 공란)": dict(에너지="힘참", 명카테1="태권도", 명카테2="아래막기(임팩트)", 좌우반전=True),
    "돌려차기 (카테 공란)": dict(에너지="폭발적", 명카테1="태권도", 명카테2="돌려차기(임팩트)"),
    "돌려차기 무릎 접은 순간 (카테 공란)": dict(에너지="폭발적", 명카테1="태권도", 명카테2="돌려차기(중간)"),
    "왼발 옆차기 (카테 공란)": dict(에너지="폭발적", 명카테1="태권도", 명카테2="옆차기(임팩트)", 좌우반전=True),
    "옆차기 (카테 공란)": dict(에너지="폭발적", 명카테1="태권도", 명카테2="옆차기(임팩트)"),
    "아라베스크": dict(카테1="서기", 카테2="한 발 서기(다리 뒤로)", 에너지="힘참", 명카테1="발레", 명카테2="아라베스크"),
    "발레 1번 포지션 (카테 공란)": dict(명카테1="발레", 명카테2="1번 포지션"),
    "다운독": dict(카테1="짚기", 카테2="엉덩이 들어 손발 짚기", 명카테1="요가", 명카테2="다운독"),
    "아이가 쪼그려 앉기": dict(카테1="쪼그리기", 카테2="쪼그려 앉기", 노소="아이"),
    "물구나무": dict(카테1="짚기", 카테2="물구나무", 에너지="힘참"),
    "모로 누워 웅크리기": dict(카테1="눕기", 카테2="모로 웅크려 눕기", 에너지="처짐"),
    "턱걸이 끝": dict(카테1="매달리기", 카테2="매달려 팔 굽혀 턱 올리기", 에너지="힘참"),
}
EXAMPLE_TRANS = {"손 흔들기": {"반복": "반복", "진동 방향": "좌우", "속도": "보통", "지속": "유지"}}

if __name__ == "__main__":
    # base postures are valid; every 카테2 and 명자세 resolves, and 좌우반전 gives the mirror image
    for (c1, c2), parts in BASE_PARTS.items():
        assert c2 in CAT2[c1], (c1, c2)
        for p, v in _expand_parts(parts).items():
            _check_part_value(p, v)
    for c1, items in CAT2.items():
        for name in items:
            r, l = resolve(dict(카테1=c1, 카테2=name)), resolve(dict(카테1=c1, 카테2=name, 좌우반전=True))
            assert _mirror_parts(r["부위"]) == l["부위"], (c1, name)
    for n1, items in NAMED.items():
        for name, spec in items.items():
            for p, v in _expand_parts(spec["parts"]).items():
                _check_part_value(p, v)
            c1, c2 = spec["shape"]
            assert c2 in CAT2.get(c1, {}), ("명자세가 가리키는 카테2가 없음", n1, name, c1, c2)
            r, l = resolve(dict(명카테1=n1, 명카테2=name)), resolve(dict(명카테1=n1, 명카테2=name, 좌우반전=True))
            assert _mirror_parts(r["부위"]) == l["부위"], (n1, name)
    try:
        validate(dict(카테1="앉기", 카테2="다리 꼬기@왼"))
        raise AssertionError("@ must be refused")
    except ValueError:
        pass
    c = count()
    print(f"기본형: 카테1 {len(CAT1)} / 카테2 {c['카테2']} (좌우가 다른 것 {c['좌우가_다른_카테2']}, 오른쪽 기준만) / 남녀 3 / 노소 4 / 에너지 5")
    print("  카테2: " + ", ".join(f"{k} {v}" for k, v in c["카테2_카테1별"].items()))
    print("명자세(보조 탐색 지표): " + ", ".join(f"{k} {v}" for k, v in c["명자세"].items()) + f"  = {sum(c['명자세'].values())}")
    acts = {}
    for field, items in NAMED.items():
        for name, spec in items.items():
            if spec["phase"]:
                acts.setdefault((field, spec["action"]), []).append(spec["phase"])
    print(f"  동작 이름 {len(acts)}개, 순간별 자세 {sum(len(v) for v in acts.values())}개: "
          + ", ".join(f"{a}({'·'.join(v)})" for (_, a), v in acts.items()))
    cov = coverage()
    assert not cov["missing"], cov["missing"]
    print("대조: 명자세가 닿은 카테2 / 카테2 수 (명자세 수)")
    for c1, (h, n) in cov["per_cat1"].items():
        print(f"  {c1:5s} {h:3d} / {n:3d}  ({cov['probes_per_cat1'][c1]})")
    seen = {}
    for name, L in EXAMPLES.items():
        r = resolve(L)
        key = json.dumps(r, ensure_ascii=False, sort_keys=True)
        assert key not in seen, (name, seen.get(key))                    # examples resolve to different poses
        seen[key] = name
        lr = flip(L, "LR")
        assert flip(lr, "LR") == L, name                                  # flipping twice restores the label
        assert resolve(lr)["부위"] == _mirror_parts(r["부위"]), name       # LR flip of the label = mirror of the pose
        ud = flip(L, "UD")
        if ud is not None:
            assert flip(ud, "UD") == L, name
    for name, t in EXAMPLE_TRANS.items():
        for k, v in t.items():
            assert v in TRANS[k], (name, k, v)
    print(f"\n예시 {len(EXAMPLES)}개 점검 통과")
    for name in ("아래막기 (카테 공란)", "아라베스크"):
        r = resolve(EXAMPLES[name])
        print(f"  {name}: {r['카테1']} > {r['카테2']} | 놓임 {r['놓임']}; " + ", ".join(f"{p} {v}" for p, v in r["부위"].items()))
