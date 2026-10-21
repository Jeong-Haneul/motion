"""PoseAxes v0.3 - 10 qualitative posture label axes (no thresholds).

An axis is a named contrast answered by looking at the pose. Each axis lists its verbal values, a neutral value, and
how it behaves under the two symmetry operations the label system is built around:
  LR  left-right flip     UD  up-down flip
Behaviours: "same" (value unchanged) or ("swap", map) (values exchange). Flipping twice returns the original label,
so mirrored data can be labelled for free.

Limb axes (ARM, LEG) are *sided*: one value means both sides; "굽힘@왼/폄@오른" gives each side its own value.
Single-sided values ("윙크@왼") exist on FACE and the extension axes. The LR flip swaps every 왼/오른.
"""
from __future__ import annotations

import json
import math

SW_SIDE = {"왼": "오른", "오른": "왼"}
SIDES = ("왼", "오른")
_NEUTRAL_SIDE_ORDER = {"왼": 0, "오른": 1}

AXES = {
    # ---------------- 1. 범주
    "BASE": dict(group="범주", name="대분류", q="몸을 무엇이 어떻게 받치고 있나?",
                 values=["서기", "앉기", "눕기", "꿇기", "쪼그리기", "기대기", "짚기", "공중"], neutral="서기",
                 anchors={"서기": "두 발로 선 차렷·대기 자세", "앉기": "의자나 바닥에 엉덩이로 앉음", "눕기": "등·배·옆으로 바닥에 누움",
                          "꿇기": "무릎으로 바닥을 짚음(정좌 포함)", "쪼그리기": "발로 딛고 깊이 웅크림", "기대기": "벽·물체에 몸을 맡김",
                          "짚기": "손으로 체중을 받침(엎드려뻗쳐·물구나무)", "공중": "어디에도 닿지 않음(점프)"},
                 ops=dict(LR="same", UD=("swap", {"서기": "짚기", "짚기": "서기"}))),
    # ---------------- 2~3. 비대칭 (뒤집으면 값이 바뀜)
    "LR": dict(group="비대칭", name="좌우", q="좌우가 같은가? 아니면 몸이 어느 쪽으로 쏠리거나 어느 쪽이 주도하나?",
               values=["대칭", "왼 우세", "오른 우세"], neutral="대칭",
               anchors={"대칭": "만세, 차렷", "왼 우세": "왼발이 앞/위, 다리를 왼쪽으로 비껴 앉음", "오른 우세": "오른발로 차기, 오른손 흔들기"},
               ops=dict(LR=("swap", {"왼 우세": "오른 우세", "오른 우세": "왼 우세"}), UD="same")),
    "UD": dict(group="비대칭", name="상하", q="머리가 위인가 아래인가?",
               values=["정립", "수평", "도립"], neutral="정립",
               anchors={"정립": "서기·앉기", "수평": "눕기", "도립": "물구나무·거꾸로 매달림"},
               ops=dict(LR="same", UD=("swap", {"정립": "도립", "도립": "정립"}))),
    # ---------------- 4~8. 몸의 부위 모양
    "TRK": dict(group="형태", name="몸통", q="몸통은 어떤 모양인가?",
                values=["곧음", "젖힘", "숙임", "말림", "옆굽힘", "비틂"], neutral="곧음",
                anchors={"곧음": "단정히 앉음", "젖힘": "등받이에 기대 뒤로", "숙임": "허리를 앞으로", "말림": "등이 둥글게 굽음",
                         "옆굽힘": "한쪽 옆구리를 접음", "비틂": "상체와 하체가 다른 쪽을 향함(허리를 돌림)"},
                ops=dict(LR="same", UD="same")),
    "ARM": dict(group="형태", name="팔", q="팔은 어디로 향하나? (세계 기준: 위=하늘. 왼팔·오른팔 따로 가능)",
                values=["내림", "모음", "앞으로 뻗음", "옆으로 뻗음", "위로 뻗음", "뒤로", "굽혀 올림", "얼굴에 댐"], neutral="내림", sided=True,
                anchors={"내림": "차렷", "모음": "몸 앞·무릎 위·허리에 붙임, 팔짱", "앞으로 뻗음": "앞으로 나란히", "옆으로 뻗음": "T자",
                         "위로 뻗음": "만세", "뒤로": "뒷짐", "굽혀 올림": "팔꿈치를 굽혀 손을 어깨~머리 높이로(손 흔들기, 경례)",
                         "얼굴에 댐": "턱 괴기, 얼굴 가리기, 머리 만지기"},
                ops=dict(LR="same", UD=("swap", {"위로 뻗음": "내림", "내림": "위로 뻗음"}))),
    "LEG": dict(group="형태", name="다리", q="다리는 어떤 모양인가? (왼다리·오른다리 따로 가능)",
                values=["폄", "벌려 폄", "굽힘", "벌려 굽힘", "깊이 접음", "교차·겹침", "들어 폄", "들어 접음"], neutral="폄", sided=True,
                anchors={"폄": "곧게 선 다리, 모아 편 다리", "벌려 폄": "다리를 옆으로 벌려 폄", "굽힘": "무릎이 약간~직각(겨루기 서기, 의자에 앉은 무릎)",
                         "벌려 굽힘": "무릎을 굽히고 벌림(기마 서기, 다리 벌려 앉기)", "깊이 접음": "쪼그림, 꿇음", "교차·겹침": "발목 교차, 무릎 위에 무릎",
                         "들어 폄": "다리를 들어 폄(차기 충격)", "들어 접음": "무릎을 들어 접음(차기 준비, 무릎 올리기)"},
                ops=dict(LR="same", UD="same")),
    "HED": dict(group="형태", name="머리·시선", q="머리와 시선은 어디를 향하나?",
                values=["정면", "위", "아래", "옆", "기울임"], neutral="정면",
                anchors={"정면": "앞을 봄", "위": "하늘을 봄", "아래": "고개 숙임", "옆": "돌아봄", "기울임": "고개를 갸웃"},
                ops=dict(LR="same", UD=("swap", {"위": "아래", "아래": "위"}))),
    "FACE": dict(group="형태", name="표정", q="얼굴은 어떤 표정인가?",
                 values=["무표정", "미소", "웃음", "화남", "슬픔", "놀람", "윙크", "눈 감음"], neutral="무표정", sided=True,
                 anchors={"무표정": "힘 뺀 얼굴", "미소": "입꼬리만 올림", "웃음": "입을 벌려 웃음", "화남": "눈썹을 모으고 노려봄",
                          "슬픔": "눈꼬리·입꼬리를 내림", "놀람": "눈과 입을 크게", "윙크": "한쪽 눈만 감음(@로 어느 쪽인지)", "눈 감음": "두 눈 감음"},
                 ops=dict(LR="same", UD="same")),
    # ---------------- 9~10. 스타일 (사람이 평가하는 지각 라벨)
    "GND": dict(group="스타일", name="남녀", q="이 자세·동작이 어느 쪽으로 읽히나? (인물의 성별이 아님)",
                values=["여성적", "중립", "남성적"], neutral="중립", rated=True,
                anchors={"여성적": "무릎을 모으고 다리를 기울여 앉기", "중립": "차렷", "남성적": "다리를 벌리고 젖혀 앉기"},
                ops=dict(LR="same", UD="same")),
    "AGE": dict(group="스타일", name="노소", q="이 자세·동작이 몇 살쯤으로 읽히나? (실제 나이가 아님)",
                values=["아이", "청년", "중년", "노년"], neutral="청년", rated=True,
                anchors={"아이": "깡충거림, 몸 전체를 크게 씀", "청년": "중립", "중년": "무게 있게 서고 앉음", "노년": "천천히, 발 벌림, 몸을 아낌"},
                ops=dict(LR="same", UD="same")),
}
CORE = list(AXES)

# 10축 밖의 확장 축. 필요할 때만 붙인다 (손 모양은 주먹/펴짐을 가르는 태권도 등에서, 접촉·긴장은 장면 맥락에서).
EXT = {
    "HND": dict(group="확장", name="손 모양", q="손은 어떤 모양인가?",
                values=["자연", "펴짐", "주먹", "가리킴", "기호"], neutral="자연", sided=True,
                anchors={"자연": "힘 뺀 손", "펴짐": "손바닥을 펴 보임", "주먹": "꽉 쥠", "가리킴": "검지로 가리킴", "기호": "브이, OK 등"},
                ops=dict(LR="same", UD="same")),
    "CON": dict(group="확장", name="접촉", q="몸이 무엇과 닿아 있나? (자기 접촉은 팔 축으로 표현)",
                values=["없음", "물체·바닥", "타인"], neutral="없음",
                anchors={"없음": "만세", "물체·바닥": "의자·벽·바닥에 닿음", "타인": "포옹, 부축"},
                ops=dict(LR="same", UD="same")),
    "TEN": dict(group="확장", name="긴장–이완", q="몸에 힘이 들어가 있나?",
                values=["이완", "보통", "긴장"], neutral="보통", rated=True,
                anchors={"이완": "축 처진 앉기", "긴장": "차렷, 겨루기 직전"},
                ops=dict(LR="same", UD="same")),
}
ALL = {**AXES, **EXT}
OPS = ("LR", "UD")

# 전이 축: 자세에서 자세로 가는 방식 (동작 = 자세의 시퀀스 + 이 축). 10축에는 포함하지 않는다.
TRANS = {
    "REP": dict(name="반복", q="같은 변화가 되풀이되나?", values=["한 번", "반복", "지속"]),
    "OSC": dict(name="진동 방향", q="반복된다면 어느 방향으로 흔들리나?", values=["없음", "좌우", "상하", "앞뒤", "회전"]),
    "SPD": dict(name="속도", q="얼마나 빠른가?", values=["느림", "보통", "빠름", "폭발적"]),
    "DUR": dict(name="지속", q="그 상태가 얼마나 유지되나?", values=["순간", "짧음", "유지"]),
}

# 스타일 축이 말하지 않은 몸 축을 채우는 사전값. 문헌(열림/닫힘 앉기, 어깨·엉덩이 흔들림, 노화 보행)에서 가져온 가설이며
# 몸 축에 값이 명시되어 있으면 항상 그쪽이 이긴다. 라벨링이 아니라 자세를 만들 때만 쓴다.
PRIORS = {
    ("GND", "여성적"): dict(TRK="곧음", ARM="모음", HED="기울임", LEG={"앉기": "굽힘", "꿇기": "깊이 접음", "*": "폄"}),
    ("GND", "남성적"): dict(TRK={"앉기": "젖힘", "*": "곧음"}, ARM="내림", LEG={"앉기": "벌려 굽힘", "서기": "벌려 폄", "*": "폄"}),
    ("AGE", "아이"): dict(ARM="옆으로 뻗음", LEG={"서기": "벌려 폄", "*": "굽힘"}),
    ("AGE", "노년"): dict(TRK="말림", HED="아래", LEG={"서기": "굽힘", "*": "굽힘"}),
}


def bits(axes):
    return sum(math.log2(len(ALL[a]["values"])) for a in axes)


# ----------------------------------------------------------------------------- sided values
def parse(v):
    """'굽힘@왼/폄@오른' -> [('굽힘','왼'), ('폄','오른')];  '굽힘' -> [('굽힘', None)] (both sides)."""
    out = []
    for part in str(v).split("/"):
        base, _, side = part.partition("@")
        out.append((base, side or None))
    return out


def fmt(parts):
    """Canonical text: 왼 before 오른, so flipping twice returns the identical string."""
    parts = sorted(parts, key=lambda p: _NEUTRAL_SIDE_ORDER.get(p[1], -1))
    return "/".join(b if s is None else f"{b}@{s}" for b, s in parts)


def flip(label: dict, op: str) -> dict:
    """Apply a symmetry operation. LR swaps every 왼/오른; UD swaps the values each axis lists for it."""
    out = {}
    for k, v in label.items():
        if v in (None, "*"):
            out[k] = v
            continue
        rule = ALL[k]["ops"][op]
        parts = []
        for base, side in parse(v):
            if op == "LR" and side is not None:
                side = SW_SIDE[side]
            if rule != "same":
                base = rule[1].get(base, base)
            parts.append((base, side))
        out[k] = fmt(parts)
    return out


def validate(label: dict):
    for k, v in label.items():
        if k not in ALL:
            raise KeyError(k)
        if v == "*":
            continue
        parts = parse(v)
        for base, side in parts:
            if base not in ALL[k]["values"]:
                raise ValueError(f"{k}={v!r}: {base!r} not in {ALL[k]['values']}")
            if side is not None and (not ALL[k].get("sided") or side not in SIDES):
                raise ValueError(f"{k} does not take side modifier {side!r}")
        if len(parts) > 2 or (len(parts) == 2 and (not ALL[k].get("sided") or {s for _, s in parts} != set(SIDES))):
            raise ValueError(f"{k}={v!r}: a pair needs one 왼 and one 오른 part on a sided axis")
        if k not in ("FACE",) and fmt(parts) != v:
            raise ValueError(f"{k}={v!r}: write pairs in canonical order {fmt(parts)!r}")


def check(label: dict):
    """Soft consistency warnings between axes (the label is still usable)."""
    w = []
    sided = any(s for k, v in label.items() if v not in (None, "*") for _, s in parse(v))
    if sided and label.get("LR") == "대칭":
        w.append("한쪽만 지정한 값(@왼/@오른)이 있는데 좌우가 '대칭'")
    if label.get("BASE") == "눕기" and label.get("UD") not in (None, "*", "수평"):
        w.append("눕기인데 상하가 '수평'이 아님")
    if label.get("UD") == "도립" and label.get("BASE") not in (None, "*", "짚기", "공중"):
        w.append("도립인데 대분류가 짚기·공중이 아님")
    return w


def fill(label: dict) -> dict:
    """Complete a label for pose generation: explicit body axes win, then style priors, then neutral values."""
    out = dict(label)
    base = out.get("BASE", "서기")
    for style in ("GND", "AGE"):
        for k, v in PRIORS.get((style, label.get(style)), {}).items():
            if out.get(k) in (None, "*"):
                out[k] = v.get(base, v["*"]) if isinstance(v, dict) else v
    for k, a in AXES.items():
        if out.get(k) in (None, "*") and not a.get("rated"):
            out[k] = a["neutral"]
    return out


def code(label: dict, axes=None) -> str:
    axes = axes or CORE
    return " / ".join(f"{ALL[a]['name']}:{label.get(a, '*')}" for a in axes)


def export(path):
    out = {"version": "0.3", "operations": {"LR": "좌우 반전", "UD": "상하 반전"}, "core": CORE, "extensions": list(EXT),
           "transitions": TRANS, "priors": {f"{k[0]}={k[1]}": v for k, v in PRIORS.items()},
           "bits": {"core": round(bits(CORE), 1), "core+ext": round(bits(list(ALL)), 1)}, "axes": ALL}
    json.dump(out, open(path, "w"), ensure_ascii=False, indent=1)


# ----------------------------------------------------------------------------- examples
EXAMPLES = {
    "만세": dict(BASE="서기", LR="대칭", UD="정립", TRK="곧음", ARM="위로 뻗음", LEG="폄", HED="위", FACE="웃음", GND="*", AGE="*"),
    "단정하게 모아 앉기 (다리를 왼쪽으로 비껴)": dict(BASE="앉기", LR="왼 우세", UD="정립", TRK="곧음", ARM="모음", LEG="굽힘", HED="기울임", FACE="미소",
                                      GND="여성적", AGE="*"),
    "다리 벌려 젖혀 앉기": dict(BASE="앉기", LR="대칭", UD="정립", TRK="젖힘", ARM="내림", LEG="벌려 굽힘", HED="정면", FACE="무표정", GND="남성적", AGE="*"),
    "다리 꼬고 앉기 (오른다리가 위)": dict(BASE="앉기", LR="오른 우세", UD="정립", TRK="곧음", ARM="모음", LEG="굽힘@왼/교차·겹침@오른", HED="정면", FACE="무표정",
                                 GND="*", AGE="*"),
    "한쪽 무릎 세워 앉기 (오른 무릎)": dict(BASE="앉기", LR="오른 우세", UD="정립", TRK="말림", ARM="모음", LEG="깊이 접음@왼/굽힘@오른", HED="아래", FACE="무표정",
                                  GND="*", AGE="*"),
    "오른발 돌려차기, 충격 순간": dict(BASE="서기", LR="오른 우세", UD="정립", TRK="옆굽힘", ARM="옆으로 뻗음", LEG="폄@왼/들어 폄@오른", HED="정면", FACE="화남",
                             GND="*", AGE="*"),
    "오른발 돌려차기, 무릎 접은 순간": dict(BASE="서기", LR="오른 우세", UD="정립", TRK="비틂", ARM="모음", LEG="폄@왼/들어 접음@오른", HED="정면", FACE="화남",
                              GND="*", AGE="*"),
    "앞서기 아래막기 (왼발 앞)": dict(BASE="서기", LR="왼 우세", UD="정립", TRK="곧음", ARM="앞으로 뻗음@왼/모음@오른", LEG="굽힘@왼/폄@오른", HED="정면",
                           FACE="무표정", GND="*", AGE="*", HND="주먹"),
    "손 흔들기 (오른손)": dict(BASE="서기", LR="오른 우세", UD="정립", TRK="곧음", ARM="굽혀 올림@오른", LEG="폄", HED="정면", FACE="미소", GND="*", AGE="*",
                         HND="펴짐@오른"),
    "윙크 (왼눈)": dict(BASE="서기", LR="왼 우세", UD="정립", TRK="곧음", ARM="내림", LEG="폄", HED="기울임", FACE="윙크@왼", GND="*", AGE="*"),
    "물구나무서기": dict(BASE="짚기", LR="대칭", UD="도립", TRK="곧음", ARM="내림", LEG="폄", HED="아래", FACE="무표정", GND="*", AGE="*"),
}
EXAMPLES["오른손으로 흔들며 왼눈 윙크"] = dict(EXAMPLES["손 흔들기 (오른손)"], FACE="윙크@왼", HED="기울임")
EXAMPLE_TRANS = {
    "손 흔들기 (오른손)": dict(REP="반복", OSC="좌우", SPD="보통", DUR="유지"),
    "윙크 (왼눈)": dict(REP="한 번", OSC="없음", SPD="빠름", DUR="순간"),
    "오른손으로 흔들며 왼눈 윙크": dict(REP="반복", OSC="좌우", SPD="보통", DUR="유지"),
}


if __name__ == "__main__":
    print(f"핵심 {len(CORE)}축 {bits(CORE):.1f} bit (대칭일 때), 확장 포함 {bits(list(ALL)):.1f} bit")
    seen = {}
    for name, L in EXAMPLES.items():
        validate(L)
        assert not check(L), (name, check(L))
        if name in EXAMPLE_TRANS:
            for k, v in EXAMPLE_TRANS[name].items():
                assert v in TRANS[k]["values"], (name, k, v)
        for op in OPS:
            assert flip(flip(L, op), op) == L, (name, op)          # flipping twice restores the label
        assert flip(flip(L, "LR"), "UD") == flip(flip(L, "UD"), "LR"), name   # the two operations commute
        key = tuple(sorted(L.items()))
        assert key not in seen, (name, seen.get(key))                 # every example is distinguishable
        seen[key] = name
        lr = flip(L, "LR")
        print(f"\n{name}\n  {code(L)}\n  좌우 반전 → " + (", ".join(f"{ALL[k]['name']} {L[k]}→{lr[k]}" for k in L if lr[k] != L[k]) or "없음 (대칭)"))
    ud = flip(EXAMPLES["만세"], "UD")
    print("\n상하 반전 예) 만세 →", {k: v for k, v in ud.items() if v != EXAMPLES["만세"][k]})
    print("\n채우기 예) 여성적 앉기 →", code(fill(dict(BASE="앉기", GND="여성적"))))
    print("채우기 예) 남성적 앉기 →", code(fill(dict(BASE="앉기", GND="남성적"))))
