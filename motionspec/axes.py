"""PoseAxes v0.2 - qualitative posture label axes (no thresholds).

An axis is a named contrast answered by looking at the pose. Each axis lists its verbal values, a default
(neutral) value, and how the axis behaves under the symmetry operations:
  LR  left-right flip     UD  up-down flip     FB  front-back flip
Behaviours: "same" (value unchanged), "swap" (values exchange according to a map), "manual" (not label-preserving,
needs re-annotation). Flipping twice returns the original label, so mirrored data can be labelled for free.
"""
from __future__ import annotations

import json
import math

AXES = {
    # ---------------- 범주 축
    "BASE": dict(group="범주", name="대분류", q="몸을 무엇이 어떻게 받치고 있나?",
                 values=["서기", "앉기", "눕기", "꿇기", "쪼그리기", "기대기", "짚기", "공중"],
                 anchors={"서기": "두 발로 선 차렷·대기 자세", "앉기": "의자나 바닥에 엉덩이로 앉음", "눕기": "등·배·옆으로 바닥에 누움",
                          "꿇기": "무릎으로 바닥을 짚음(정좌 포함)", "쪼그리기": "발로 딛고 깊이 웅크림", "기대기": "벽·물체에 몸을 맡김",
                          "짚기": "손으로 체중을 받침(엎드려뻗쳐·물구나무)", "공중": "어디에도 닿지 않음(점프)"},
                 ops=dict(LR="same", UD=("swap", {"서기": "짚기", "짚기": "서기"}), FB="same")),
    "SUP": dict(group="범주", name="체중 지지", q="체중이 받쳐지는 모양은?",
                values=["균등", "한쪽 치우침", "한 점", "없음"],
                anchors={"균등": "양발(또는 양쪽 엉덩이)에 고르게", "한쪽 치우침": "한쪽에 더 실림", "한 점": "한 발 또는 한 손으로만", "없음": "공중"},
                ops=dict(LR="same", UD="same", FB="same")),
    # ---------------- 비대칭 축 (뒤집으면 값이 바뀜)
    "LR": dict(group="비대칭", name="좌우", q="좌우가 같은가, 어느 쪽이 더 활동적·우세한가?",
               values=["대칭", "왼 우세", "오른 우세"], neutral="대칭",
               anchors={"대칭": "만세, 차렷", "왼 우세": "왼발을 앞/위로, 왼쪽으로 기울임", "오른 우세": "오른발로 차기, 오른쪽으로 기울임"},
               ops=dict(LR=("swap", {"왼 우세": "오른 우세", "오른 우세": "왼 우세"}), UD="same", FB="same")),
    "UD": dict(group="비대칭", name="상하", q="머리가 위인가 아래인가?",
               values=["정립", "수평", "도립"], neutral="정립",
               anchors={"정립": "서기·앉기", "수평": "눕기", "도립": "물구나무·거꾸로 매달림"},
               ops=dict(LR="same", UD=("swap", {"정립": "도립", "도립": "정립"}), FB="same")),
    "FB": dict(group="비대칭", name="전후 방향", q="몸이 기준 방향(상대·카메라·목표)에 대해 어느 쪽을 향하나?",
               values=["정면", "사선", "옆", "등"], neutral="정면",
               anchors={"정면": "기준을 마주함", "사선": "비스듬히", "옆": "옆구리를 향함", "등": "등을 돌림"},
               ops=dict(LR="same", UD="same", FB=("swap", {"정면": "등", "등": "정면"}))),
    "TW": dict(group="비대칭", name="상·하체 엇갈림", q="상체와 하체가 같은 쪽을 향하나, 엇갈렸나?",
               values=["일치", "엇갈림"], neutral="일치",
               anchors={"일치": "차렷", "엇갈림": "허리를 비튼 자세, 고관절을 돌려 차는 순간"},
               ops=dict(LR="same", UD="same", FB="same")),
    # ---------------- 형태 극성 축
    "OPN": dict(group="형태", name="열림–닫힘", q="몸이 모여 있나, 펼쳐져 있나?",
                values=["닫힘", "중립", "열림"], neutral="중립",
                anchors={"닫힘": "무릎·팔을 모은 단정한 앉기, 웅크림", "중립": "편하게 선 자세", "열림": "다리를 벌려 앉기, 만세"},
                ops=dict(LR="same", UD="same", FB="same")),
    "TRK": dict(group="형태", name="상체 모양", q="상체는 어떤 모양인가?",
                values=["곧음", "젖힘", "숙임", "말림", "옆굽힘"], neutral="곧음",
                anchors={"곧음": "단정히 앉음", "젖힘": "등받이에 기대 뒤로", "숙임": "허리를 앞으로", "말림": "등이 둥글게 굽음", "옆굽힘": "한쪽으로 기움"},
                ops=dict(LR="same", UD="same", FB=("swap", {"젖힘": "숙임", "숙임": "젖힘"}))),
    "LEG": dict(group="형태", name="다리 모양", q="무릎은 얼마나 접혀 있나?",
                values=["폄", "약간 굽힘", "직각 정도", "깊이 접음"], neutral="폄",
                anchors={"폄": "곧게 선 다리", "약간 굽힘": "겨루기 서기", "직각 정도": "의자에 앉은 무릎", "깊이 접음": "차기 직전 chamber, 쪼그림"},
                ops=dict(LR="same", UD="same", FB="same")),
    "LGP": dict(group="형태", name="다리 간격", q="두 다리(발·무릎)는 얼마나 떨어져 있나?",
                values=["붙임", "보통", "벌림"], neutral="보통",
                anchors={"붙임": "차렷, 무릎 모아 앉기", "보통": "어깨~골반 너비", "벌림": "다리를 쩍 벌림, 기마 서기"},
                ops=dict(LR="same", UD="same", FB="same")),
    "LGR": dict(group="형태", name="다리 관계", q="두 다리가 서로 어떤 관계인가?",
                values=["나란함", "교차·겹침", "한쪽 들림"], neutral="나란함", sided=True,
                anchors={"나란함": "두 발이 바닥", "교차·겹침": "발목 교차, 무릎 위에 무릎", "한쪽 들림": "한 발이 바닥에서 떨어짐(차기)"},
                ops=dict(LR="same", UD="same", FB="same")),
    "ARM": dict(group="형태", name="팔 모양", q="팔은 어디로 향하나?",
                values=["내림", "모음", "앞으로 뻗음", "옆으로 뻗음", "위로 뻗음", "뒤로", "굽혀 올림"], neutral="내림", sided=True,
                anchors={"내림": "차렷", "모음": "무릎 위·가슴 앞에 모음", "앞으로 뻗음": "앞으로 나란히", "옆으로 뻗음": "T자", "위로 뻗음": "만세", "뒤로": "팔짱·뒷짐", "굽혀 올림": "팔꿈치를 굽혀 손을 어깨~머리 높이로 올림(손 흔들기, 경례)"},
                ops=dict(LR="same", UD=("swap", {"위로 뻗음": "내림", "내림": "위로 뻗음"}), FB="same")),
    "HND": dict(group="얼굴·손", name="손 모양", q="손은 어떤 모양인가?",
                values=["자연", "펴짐", "주먹", "가리킴", "기호"], neutral="자연", sided=True,
                anchors={"자연": "힘 뺀 손", "펴짐": "손바닥을 펴 보임(인사, 멈춤)", "주먹": "꽉 쥠", "가리킴": "검지로 가리킴", "기호": "브이, OK 등"},
                ops=dict(LR="same", UD="same", FB="same")),
    "EYE": dict(group="얼굴·손", name="눈", q="눈은 어떤 상태인가?",
                values=["뜸", "감음", "한쪽 감음", "가늘게"], neutral="뜸", sided=True,
                anchors={"뜸": "자연스럽게 뜬 눈", "감음": "두 눈 감음", "한쪽 감음": "윙크", "가늘게": "찡그림·웃는 눈"},
                ops=dict(LR="same", UD="same", FB="same")),
    "MTH": dict(group="얼굴·손", name="입", q="입은 어떤 모양인가?",
                values=["다묾", "미소", "벌림", "오므림"], neutral="다묾",
                anchors={"다묾": "무표정", "미소": "입꼬리 올림", "벌림": "크게 웃음·놀람", "오므림": "휘파람·뽀뽀"},
                ops=dict(LR="same", UD="same", FB="same")),
    "HED": dict(group="형태", name="머리·시선", q="머리와 시선은 어디를 향하나?",
                values=["정면", "위", "아래", "옆", "기울임"], neutral="정면",
                anchors={"정면": "앞을 봄", "위": "하늘을 봄", "아래": "고개 숙임", "옆": "돌아봄", "기울임": "고개를 갸웃"},
                ops=dict(LR="same", UD=("swap", {"위": "아래", "아래": "위"}), FB="same")),
    # ---------------- 관계 축
    "CON": dict(group="관계", name="접촉", q="몸이 무엇과 닿아 있나?",
                values=["없음", "자기 접촉", "물체·바닥", "타인"], neutral="없음",
                anchors={"없음": "만세", "자기 접촉": "손을 무릎 위에, 팔짱", "물체·바닥": "손으로 짚음, 등받이", "타인": "포옹, 부축"},
                ops=dict(LR="same", UD="same", FB="same")),
    # ---------------- 스타일 축 (사람이 평가하는 지각 라벨)
    "GND": dict(group="스타일", name="남녀", q="이 자세·동작이 어느 쪽으로 읽히나? (인물의 성별이 아님)",
                values=["여성적", "약간 여성적", "중립", "약간 남성적", "남성적"], neutral="중립", rated=True,
                anchors={"여성적": "무릎을 모으고 다리를 기울여 앉기", "중립": "차렷", "남성적": "다리를 벌리고 젖혀 앉기"},
                ops=dict(LR="same", UD="same", FB="same")),
    "AGE": dict(group="스타일", name="노소", q="이 자세·동작이 몇 살쯤으로 읽히나? (실제 나이가 아님)",
                values=["아이", "젊음", "성인", "중년 이상", "노년"], neutral="성인", rated=True,
                anchors={"아이": "깡충거림, 몸 전체를 크게 씀", "성인": "중립", "노년": "천천히, 발 벌림, 몸을 아낌"},
                ops=dict(LR="same", UD="same", FB="same")),
    "TEN": dict(group="스타일", name="긴장–이완", q="몸에 힘이 들어가 있나?",
                values=["이완", "보통", "긴장"], neutral="보통", rated=True, optional=True,
                anchors={"이완": "축 처진 앉기", "긴장": "차렷, 겨루기 직전"},
                ops=dict(LR="same", UD="same", FB="same")),
}

TIERS = {
    "필수": ["BASE", "SUP", "LR", "UD", "FB", "OPN"],
    "표준": ["TW", "TRK", "LEG", "LGP", "LGR", "ARM", "HED", "CON"],
    "얼굴·손": ["HND", "EYE", "MTH"],
    "스타일": ["GND", "AGE"],
    "스타일+": ["TEN"],
}
OPS = ("LR", "UD", "FB")

# 전이 축: 자세에서 자세로 가는 방식. 반복되는 동작(손 흔들기)과 순간 동작(윙크)을 구분한다.
TRANS = {
    "REP": dict(name="반복", q="같은 변화가 되풀이되나?", values=["한 번", "반복", "지속"]),
    "OSC": dict(name="진동 방향", q="반복된다면 어느 방향으로 흔들리나?", values=["없음", "좌우", "상하", "앞뒤", "회전"]),
    "SPD": dict(name="속도", q="얼마나 빠른가?", values=["느림", "보통", "빠름", "폭발적"]),
    "DUR": dict(name="지속", q="그 상태가 얼마나 유지되나?", values=["순간", "짧음", "유지"]),
}


def bits(axes):
    return sum(math.log2(len(AXES[a]["values"])) for a in axes)


SIDES = {"왼": "오른", "오른": "왼", "양쪽": "양쪽"}


def split_side(v):
    """'굽혀 올림@오른' -> ('굽혀 올림', '오른'). Sided axes may name which side performs the value."""
    if isinstance(v, str) and "@" in v:
        base, side = v.split("@", 1)
        return base, side
    return v, None


def flip(label: dict, op: str) -> dict:
    """Apply a symmetry operation to a label. Axes marked 'manual' are returned as None for re-annotation.
    Side modifiers ('@왼', '@오른') swap under the left-right flip."""
    out = {}
    for k, v in label.items():
        if v in (None, "*"):
            out[k] = v
            continue
        v, side = split_side(v)
        if side is not None and op == "LR":
            side = SIDES[side]
        rule = AXES[k]["ops"][op]
        if side is not None:
            out[k] = None if rule == "manual" else ((v if rule == "same" else rule[1].get(v, v)) + "@" + side)
            continue
        if rule == "same":
            out[k] = v
        elif rule == "manual":
            out[k] = None
        else:
            out[k] = rule[1].get(v, v)
    return out


def validate(label: dict):
    for k, v in label.items():
        if k not in AXES:
            raise KeyError(k)
        base, side = split_side(v)
        if base not in AXES[k]["values"] and base != "*":
            raise ValueError(f"{k}={v!r} not in {AXES[k]['values']}")
        if side is not None and (not AXES[k].get("sided") or side not in SIDES):
            raise ValueError(f"{k} does not take side modifier {side!r}")


def code(label: dict, axes=None) -> str:
    axes = axes or [a for t in ("필수", "표준", "얼굴·손") for a in TIERS[t] if a in label or t != "얼굴·손"]
    return " / ".join(f"{AXES[a]['name']}:{label.get(a, '*')}" for a in axes)


def export(path):
    out = {"version": "0.2", "operations": {"LR": "좌우 반전", "UD": "상하 반전", "FB": "전후 반전"},
           "tiers": TIERS, "transitions": TRANS, "bits": {t: round(bits(a), 1) for t, a in TIERS.items()}, "axes": AXES}
    json.dump(out, open(path, "w"), ensure_ascii=False, indent=1)


# ----------------------------------------------------------------------------- examples
EXAMPLES = {
    "만세": dict(BASE="서기", SUP="균등", LR="대칭", UD="정립", FB="정면", TW="일치", OPN="열림", TRK="곧음", LEG="폄", LGP="보통",
               LGR="나란함", ARM="위로 뻗음", HED="위", CON="없음"),
    "단정하게 모아 앉기 (다리를 한쪽으로 기울임)": dict(BASE="앉기", SUP="균등", LR="왼 우세", UD="정립", FB="정면", TW="일치", OPN="닫힘", TRK="곧음",
                                       LEG="직각 정도", LGP="붙임", LGR="나란함", ARM="모음", HED="기울임", CON="자기 접촉", GND="여성적"),
    "다리 벌려 젖혀 앉기": dict(BASE="앉기", SUP="균등", LR="대칭", UD="정립", FB="정면", TW="일치", OPN="열림", TRK="젖힘",
                         LEG="직각 정도", LGP="벌림", LGR="나란함", ARM="내림", HED="정면", CON="자기 접촉", GND="남성적"),
    "다리 꼬고 앉기 (무릎 위에 무릎)": dict(BASE="앉기", SUP="균등", LR="오른 우세", UD="정립", FB="정면", TW="일치", OPN="닫힘", TRK="곧음",
                                  LEG="직각 정도", LGP="붙임", LGR="교차·겹침", ARM="모음", HED="정면", CON="자기 접촉"),
    "오른발 돌려차기, 충격 순간": dict(BASE="서기", SUP="한 점", LR="오른 우세", UD="정립", FB="옆", TW="엇갈림", OPN="열림", TRK="옆굽힘",
                             LEG="폄", LGP="벌림", LGR="한쪽 들림", ARM="옆으로 뻗음", HED="정면", CON="없음"),
    "오른발 돌려차기, 무릎 접은 순간": dict(BASE="서기", SUP="한 점", LR="오른 우세", UD="정립", FB="사선", TW="엇갈림", OPN="닫힘", TRK="곧음",
                              LEG="깊이 접음", LGP="보통", LGR="한쪽 들림", ARM="모음", HED="정면", CON="없음"),
}

EXAMPLES["손 흔들기 (오른손)"] = dict(BASE="서기", SUP="균등", LR="대칭", UD="정립", FB="정면", TW="일치", OPN="중립", TRK="곧음", LEG="폄", LGP="보통",
                                  LGR="나란함", ARM="굽혀 올림@오른", HED="정면", CON="없음", HND="펴짐@오른", EYE="뜸", MTH="미소")
EXAMPLES["윙크 (왼눈)"] = dict(BASE="서기", SUP="균등", LR="대칭", UD="정립", FB="정면", TW="일치", OPN="중립", TRK="곧음", LEG="폄", LGP="보통",
                            LGR="나란함", ARM="내림", HED="기울임", CON="없음", HND="자연", EYE="한쪽 감음@왼", MTH="미소")
EXAMPLES["오른손으로 흔들며 왼눈 윙크"] = dict(EXAMPLES["손 흔들기 (오른손)"], EYE="한쪽 감음@왼", HED="기울임")
EXAMPLE_TRANS = {
    "손 흔들기 (오른손)": dict(REP="반복", OSC="좌우", SPD="보통", DUR="유지"),
    "윙크 (왼눈)": dict(REP="한 번", OSC="없음", SPD="빠름", DUR="순간"),
    "오른손으로 흔들며 왼눈 윙크": dict(REP="반복", OSC="좌우", SPD="보통", DUR="유지"),
}


if __name__ == "__main__":
    for t, a in TIERS.items():
        print(f"{t:6s} {len(a):2d}축  {bits(a):5.1f} bit")
    bad = 0
    for name, L in EXAMPLES.items():
        validate(L)
        if name in EXAMPLE_TRANS:
            for k, v in EXAMPLE_TRANS[name].items():
                assert v in TRANS[k]["values"], (name, k, v)
        for op in OPS:
            f = flip(L, op)
            assert flip(f, op) == L, (name, op)          # flipping twice restores the label
        lr = flip(L, "LR")
        print(f"\n{name}\n  {code(L)}\n  좌우 반전 → 바뀐 축: " + (", ".join(f"{AXES[k]['name']} {L[k]}→{lr[k]}" for k in L if lr[k] != L[k]) or "없음 (대칭)"))
    print("\n상하 반전 예) 만세 →", {k: v for k, v in flip(EXAMPLES['만세'], 'UD').items() if v != EXAMPLES['만세'][k]})
