"""PoseAxes v0.5 - base form (5 axes) + optional detail controls.

Base form:   카테1 / 카테2 (depends on 카테1) / 남녀 / 노소 / 에너지
Detail:      side of a sided 카테2 (@왼/@오른) and per-part overrides (팔·다리 = 방향·뻗음, 몸통, 머리, 손)

Every 카테2 has a base posture written in part values. Part values sit on top of IK prototypes:
a direction (unit vector, body frame) and a reach ratio (tip distance / limb length). Degree is not labelled per part;
남녀·노소·에너지 apply it to the whole body when the pose is generated.
Sided 카테2 base postures are written for @오른; @왼 is the mirror image. Face expressions are a separate system.
"""
from __future__ import annotations

import json

# ----------------------------------------------------------------------------- base form
CAT1 = ["서기", "앉기", "눕기", "꿇기", "쪼그리기", "기대기", "짚기", "공중"]

# 카테2: {이름: dict(side=쪽 표기의 뜻 or None, put=몸이 놓인 방향, parts=기본 자세)}. 쪽 있는 값은 @오른 기준으로 적는다.
# 빠진 부위는 DEFAULT_PARTS를 쓴다.
_ = None
CAT2 = {
    "서기": {
        "바로 서기": dict(side=_, parts={}),
        "짝다리": dict(side="체중을 실은 다리", parts={"왼다리": "아래·굽힘"}),
        "다리 벌려 서기": dict(side=_, parts={"다리": "바깥아래·폄"}),
        "한 발 서기": dict(side="든 다리", parts={"오른다리": "앞아래·접음"}),
        "앞서기": dict(side="앞 다리", parts={"오른다리": "앞아래·굽힘", "왼다리": "뒤아래·폄"}),
        "기마 서기": dict(side=_, parts={"다리": "바깥아래·굽힘"}),
        "겨루기 서기": dict(side="앞 다리", parts={"오른다리": "앞아래·굽힘", "왼다리": "뒤아래·굽힘", "팔": "앞아래·접음", "손": "주먹"}),
        "반쯤 앉은 서기": dict(side=_, parts={"다리": "앞아래·굽힘", "몸통": "숙임"}),
        "숙여 서기": dict(side=_, parts={"몸통": "숙임", "머리": "아래"}),
    },
    "앉기": {
        "바로 앉기": dict(side=_, parts={"다리": "앞아래·굽힘", "팔": "앞아래·굽힘"}),
        "기대 앉기": dict(side=_, parts={"다리": "앞아래·굽힘", "몸통": "젖힘"}),
        "다리 꼬기": dict(side="위에 얹은 다리", parts={"왼다리": "앞아래·굽힘", "오른다리": "가로질러·굽힘", "팔": "앞아래·굽힘"}),
        "비껴 앉기": dict(side="다리가 가는 쪽", parts={"오른다리": "앞바깥·굽힘", "왼다리": "가로질러·굽힘", "팔": "앞아래·굽힘"}),
        "벌려 젖혀 앉기": dict(side=_, parts={"다리": "앞바깥·굽힘", "몸통": "젖힘"}),
        "양반다리": dict(side=_, parts={"다리": "가로질러·접음", "팔": "앞아래·굽힘"}),
        "무릎 세워 앉기": dict(side="세운 무릎", parts={"오른다리": "앞·접음", "왼다리": "가로질러·접음", "오른팔": "앞·굽힘"}),
        "다리 뻗고 앉기": dict(side=_, parts={"다리": "앞·폄", "팔": "뒤아래·폄"}),
        "무릎 껴안고 앉기": dict(side=_, parts={"다리": "앞·접음", "팔": "앞·굽힘", "몸통": "말림"}),
    },
    "눕기": {
        "반듯이": dict(side=_, put="등 아래", parts={}),
        "엎드려": dict(side=_, put="배 아래", parts={}),
        "모로": dict(side="바닥에 닿은 쪽", put="옆 아래", parts={"다리": "앞아래·굽힘"}),
        "웅크려 모로": dict(side="바닥에 닿은 쪽", put="옆 아래", parts={"다리": "앞아래·접음", "팔": "앞·굽힘", "몸통": "말림"}),
        "팔베개": dict(side=_, put="등 아래", parts={"팔": "위·접음"}),
    },
    "꿇기": {
        "정좌": dict(side=_, parts={"다리": "뒤아래·접음", "팔": "앞아래·굽힘"}),
        "무릎 서기": dict(side=_, parts={"다리": "뒤아래·굽힘"}),
        "한 무릎 꿇기": dict(side="세운 무릎", parts={"오른다리": "앞아래·굽힘", "왼다리": "뒤아래·굽힘"}),
    },
    "쪼그리기": {
        "쪼그려 앉기": dict(side=_, parts={"다리": "아래·접음", "팔": "앞아래·굽힘", "몸통": "숙임"}),
        "벌려 쪼그리기": dict(side=_, parts={"다리": "바깥아래·접음", "팔": "앞아래·굽힘"}),
    },
    "기대기": {
        "등 기대기": dict(side=_, parts={"다리": "앞아래·폄"}),
        "어깨 기대기": dict(side="벽 쪽", parts={"몸통": "옆굽힘@오른", "왼다리": "가로질러·폄"}),
        "팔 걸치기": dict(side=_, parts={"몸통": "숙임", "팔": "앞·굽힘"}),
    },
    "짚기": {
        "엎드려뻗쳐": dict(side=_, put="배 아래", parts={"팔": "앞·폄"}),
        "네발": dict(side=_, put="배 아래", parts={"팔": "앞·폄", "다리": "앞·접음"}),
        "옆으로 짚기": dict(side="짚은 팔", put="옆 아래", parts={"오른팔": "바깥·폄", "왼팔": "바깥·폄"}),
        "물구나무": dict(side=_, put="도립", parts={"팔": "위·폄"}),
    },
    "공중": {
        "곧게 뛰기": dict(side=_, parts={}),
        "벌려 뛰기": dict(side=_, parts={"팔": "바깥위·폄", "다리": "바깥아래·폄"}),
        "웅크려 뛰기": dict(side=_, parts={"다리": "앞·접음", "팔": "앞·굽힘"}),
        "앞뒤 도약": dict(side="앞 다리", parts={"오른다리": "앞·폄", "왼다리": "뒤아래·굽힘", "팔": "바깥·폄"}),
    },
}
STYLE = {
    "남녀": dict(values=["여성적", "중립", "남성적"], neutral="중립",
               effect="열림–닫힘(무릎·팔 모음/벌림), 골반 쓰임(여성적) vs 어깨 쓰임(남성적)"),
    "노소": dict(values=["아이", "청년", "중년", "노년"], neutral="청년",
               effect="척추 굽음, 무릎 굽힘, 몸통 숙임, 보폭(노년으로 갈수록 커지거나 줄어듦)"),
    "에너지": dict(values=["처짐", "편안", "보통", "힘참", "폭발적"], neutral="보통",
                effect="뻗음률(처짐은 덜 뻗고 폭발적은 끝까지), 척추 펴짐, 자세 폭, 동작이면 속도"),
}
BASE_AXES = ["카테1", "카테2", "남녀", "노소", "에너지"]

# ----------------------------------------------------------------------------- detail controls (parts)
PARTS = ["몸통", "머리", "왼팔", "오른팔", "왼손", "오른손", "왼다리", "오른다리"]
GROUPS = {"팔": ("왼팔", "오른팔"), "손": ("왼손", "오른손"), "다리": ("왼다리", "오른다리")}
MIRROR = {"왼팔": "오른팔", "오른팔": "왼팔", "왼손": "오른손", "오른손": "왼손", "왼다리": "오른다리", "오른다리": "왼다리"}
SW = {"왼": "오른", "오른": "왼"}

# 팔·다리 방향 (뿌리에서 끝을 본 쪽, 몸 기준). 벡터는 (바깥, 위, 앞) - 왼쪽 부위는 바깥이 몸의 왼쪽.
DIRS = {"위": (0, 1, 0), "아래": (0, -1, 0), "앞": (0, 0, 1), "뒤": (0, 0, -1), "바깥": (1, 0, 0), "가로질러": (-1, 0, 0.6),
        "앞위": (0, 1, 1), "앞아래": (0, -1, 1), "바깥위": (1, 1, 0), "바깥아래": (1, -1, 0), "앞바깥": (1, 0, 1), "뒤아래": (0, -1, -1)}
REACH = {"폄": 1.0, "굽힘": 0.7, "접음": 0.35}      # 끝까지 거리 / 팔(다리) 길이 - 라벨이 아니라 대표값
TORSO = ["곧음", "숙임", "젖힘", "말림", "옆굽힘@왼", "옆굽힘@오른", "비틂@왼", "비틂@오른"]
HEAD = ["앞", "위", "아래", "옆@왼", "옆@오른", "갸웃@왼", "갸웃@오른"]
HAND = ["자연", "펴짐", "주먹", "가리킴", "브이"]
DEFAULT_PARTS = {"몸통": "곧음", "머리": "앞", "팔": "아래·폄", "손": "자연", "다리": "아래·폄"}

PUT_DEFAULT = "정립"
OPS = ("LR", "UD")
# 상하 반전은 카테2 사이의 대응으로만 정의한다 (나머지는 다시 라벨링).
UD_MAP = {("서기", "바로 서기"): ("짚기", "물구나무"), ("눕기", "반듯이"): ("눕기", "엎드려")}
UD_MAP.update({v: k for k, v in list(UD_MAP.items())})

TRANS = {"반복": ["한 번", "반복", "지속"], "진동 방향": ["없음", "좌우", "상하", "앞뒤", "회전"],
         "속도": ["느림", "보통", "빠름", "폭발적"], "지속": ["순간", "짧음", "유지"]}


def _part_kind(part):
    return "팔" if part.endswith("팔") else "다리" if part.endswith("다리") else "손" if part.endswith("손") else part


def _check_part_value(part, v):
    kind = _part_kind(part)
    if kind in ("팔", "다리"):
        d, _, r = v.partition("·")
        if d not in DIRS or r not in REACH:
            raise ValueError(f"{part}={v!r}: write 방향·뻗음, 방향 in {list(DIRS)}, 뻗음 in {list(REACH)}")
    elif v not in {"몸통": TORSO, "머리": HEAD, "손": HAND}[kind]:
        raise ValueError(f"{part}={v!r} not in {({'몸통': TORSO, '머리': HEAD, '손': HAND})[kind]}")


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


def split_cat2(v):
    name, _, side = v.partition("@")
    return name, side or None


# ----------------------------------------------------------------------------- label operations
def validate(label: dict):
    for k in label:
        if k not in BASE_AXES + ["부위"]:
            raise KeyError(k)
    c1 = label.get("카테1")
    if c1 not in CAT1:
        raise ValueError(f"카테1={c1!r} not in {CAT1}")
    name, side = split_cat2(label.get("카테2", ""))
    if name not in CAT2[c1]:
        raise ValueError(f"카테2={name!r} is not under 카테1={c1!r}: {list(CAT2[c1])}")
    if (CAT2[c1][name]["side"] is None) != (side is None):
        raise ValueError(f"카테2={label['카테2']!r}: " + (f"needs @왼/@오른 ({CAT2[c1][name]['side']})"
                                                         if side is None else "takes no side"))
    if side is not None and side not in SW:
        raise ValueError(f"side {side!r}")
    for k, a in STYLE.items():
        if k in label and label[k] not in a["values"]:
            raise ValueError(f"{k}={label[k]!r} not in {a['values']}")
    for p, v in _expand_parts(label.get("부위", {})).items():
        _check_part_value(p, v)


def resolve(label: dict) -> dict:
    """Everything needed to build the pose: style values, how the body is placed, and one value per part
    (defaults < 카테2 base posture (mirrored for @왼) < detail overrides)."""
    validate(label)
    c1 = label["카테1"]
    name, side = split_cat2(label["카테2"])
    spec = CAT2[c1][name]
    base = _expand_parts(spec["parts"])
    if side == "왼":
        base = _mirror_parts(base)
    parts = _expand_parts(DEFAULT_PARTS)
    parts.update(base)
    parts.update(_expand_parts(label.get("부위", {})))
    put = spec.get("put", PUT_DEFAULT)
    if put == "옆 아래":
        put = f"{side}옆 아래"
    return dict(카테1=c1, 카테2=label["카테2"], 놓임=put, **{k: label.get(k, a["neutral"]) for k, a in STYLE.items()},
                부위={p: parts[p] for p in PARTS})


def flip(label: dict, op: str):
    """LR: swap the 카테2 side and left/right detail parts. UD: only defined between 카테2 pairs in UD_MAP (else None)."""
    out = dict(label)
    if op == "LR":
        name, side = split_cat2(label["카테2"])
        if side:
            out["카테2"] = f"{name}@{SW[side]}"
        if "부위" in label:
            out["부위"] = _mirror_parts(label["부위"])       # group keys (팔/손/다리) stay, named sides swap
        return out
    key = (label["카테1"], split_cat2(label["카테2"])[0])
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
    s = " / ".join(str(label.get(k, "-")) for k in BASE_AXES)
    if label.get("부위"):
        s += "  + " + ", ".join(f"{p} {v}" for p, v in label["부위"].items())
    return s


def count():
    n2 = sum(len(v) for v in CAT2.values())
    sided = sum(1 for v in CAT2.values() for s in v.values() if s["side"])
    return dict(카테2=n2, 쪽_있는_카테2=sided, 기본형_조합=(n2 + sided) * 3 * 4 * 5)


def export(path):
    out = {"version": "0.5", "base_axes": BASE_AXES, "카테1": CAT1, "카테2": CAT2, "style": STYLE,
           "detail": {"parts": PARTS, "groups": GROUPS, "arm_leg": {"방향": DIRS, "뻗음": REACH}, "몸통": TORSO, "머리": HEAD,
                      "손": HAND, "default": DEFAULT_PARTS},
           "flip": {"LR": "카테2 쪽과 좌우 부위를 맞바꿈", "UD": {f"{a[0]}.{a[1]}": f"{b[0]}.{b[1]}" for a, b in UD_MAP.items()}},
           "transitions": TRANS, "count": count()}
    json.dump(out, open(path, "w"), ensure_ascii=False, indent=1)


# ----------------------------------------------------------------------------- examples
EXAMPLES = {
    "차렷": dict(카테1="서기", 카테2="바로 서기", 에너지="힘참"),
    "편히 서 있기": dict(카테1="서기", 카테2="바로 서기", 에너지="편안"),
    "만세": dict(카테1="서기", 카테2="바로 서기", 에너지="힘참", 부위={"팔": "위·폄", "머리": "위"}),
    "여성스럽게 비껴 앉기": dict(카테1="앉기", 카테2="비껴 앉기@왼", 남녀="여성적", 에너지="편안", 부위={"머리": "갸웃@왼"}),
    "다리 벌려 젖혀 앉기": dict(카테1="앉기", 카테2="벌려 젖혀 앉기", 남녀="남성적", 에너지="편안"),
    "다리 꼬고 앉기": dict(카테1="앉기", 카테2="다리 꼬기@오른"),
    "앞서기 아래막기": dict(카테1="서기", 카테2="앞서기@왼", 에너지="힘참",
                     부위={"왼팔": "앞아래·폄", "오른팔": "아래·접음", "손": "주먹"}),
    "돌려차기 충격": dict(카테1="서기", 카테2="한 발 서기@오른", 에너지="폭발적",
                    부위={"오른다리": "바깥·폄", "몸통": "옆굽힘@왼", "손": "주먹"}),
    "손 흔들기": dict(카테1="서기", 카테2="바로 서기", 에너지="보통", 부위={"오른팔": "바깥위·접음", "오른손": "펴짐"}),
    "노인이 서 있기": dict(카테1="서기", 카테2="바로 서기", 노소="노년", 에너지="처짐"),
    "아이가 쪼그려 앉기": dict(카테1="쪼그리기", 카테2="쪼그려 앉기", 노소="아이"),
    "물구나무": dict(카테1="짚기", 카테2="물구나무", 에너지="힘참"),
    "모로 누워 웅크리기": dict(카테1="눕기", 카테2="웅크려 모로@오른", 에너지="처짐"),
}
EXAMPLE_TRANS = {"손 흔들기": {"반복": "반복", "진동 방향": "좌우", "속도": "보통", "지속": "유지"}}


if __name__ == "__main__":
    # every base posture is valid, and its @왼 version is the mirror of @오른
    for c1, items in CAT2.items():
        for name, spec in items.items():
            for p, v in _expand_parts(spec["parts"]).items():
                _check_part_value(p, v)
            if spec["side"]:
                r = resolve(dict(카테1=c1, 카테2=f"{name}@오른"))["부위"]
                l = resolve(dict(카테1=c1, 카테2=f"{name}@왼"))["부위"]
                assert _mirror_parts(r) == l, (c1, name)
    c = count()
    print(f"기본형 5축: 카테1 {len(CAT1)} / 카테2 {c['카테2']} (쪽 있는 것 {c['쪽_있는_카테2']}) / 남녀 3 / 노소 4 / 에너지 5"
          f"  -> 기본형 조합 {c['기본형_조합']:,}")
    print(f"추가 제어: 팔·다리 {len(DIRS)}방향 x {len(REACH)}뻗음, 몸통 {len(TORSO)}, 머리 {len(HEAD)}, 손 {len(HAND)}")
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
        print(f"\n{name}\n  {code(L)}\n  -> 놓임 {r['놓임']}; " + ", ".join(f"{p} {v}" for p, v in r["부위"].items()))
        if ud is not None:
            print(f"  상하 반전 -> {code(ud)}")
    for name, t in EXAMPLE_TRANS.items():
        for k, v in t.items():
            assert v in TRANS[k], (name, k, v)
    print("\nIK 대표값 예) 손 흔들기 오른팔 바깥위·접음 ->", ik_target("오른팔", "바깥위·접음"))
