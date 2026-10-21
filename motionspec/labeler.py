"""Posture labeling: joint coordinates -> a short code made of small, orthogonal label axes.

Axes are grouped in tiers (CORE, STANDARD, STYLE). Computable axes are derived from joints with explicit
thresholds; STYLE axes are human-rated and only get a geometric pre-label proposal. Every axis can be '*'
(unspecified), so a label is a partial constraint and a posture set can be described at any resolution.
"""
from __future__ import annotations

import numpy as np

from .skeleton import I, Motion, unit

UP = np.array([0.0, 1.0, 0.0])

# ----------------------------------------------------------------------------- schema
AXES = {
    # id: (tier, name, levels, short description)
    "BASE": ("CORE", "대분류 (지지 방식)", ["ST", "SI", "KN", "SQ", "LY", "SU", "AI"],
             "ST 서기 / SI 앉기 / KN 무릎꿇기 / SQ 쪼그려 / LY 눕기 / SU 손발 짚기 / AI 공중"),
    "SUP": ("CORE", "하체 하중 지지", ["EV", "BI", "ONE", "NO"],
            "EV 양발 균등 / BI 양발 편중 / ONE 한 발 / NO 없음(발이 바닥에서 떠 있음)"),
    "SPR": ("CORE", "좌우 벌어짐", ["1", "2", "3", "4", "5"],
            "1 붙임 / 2 좁음 / 3 보통 / 4 넓음 / 5 매우 넓음 (고관절 폭 대비, 서기=발목 · 그 외=무릎)"),
    "FLA": ("CORE", "무릎 굽힘 (더 굽힌 다리)", ["EXT", "SLI", "RGT", "DEP"], "EXT <25° / SLI 25–60 / RGT 60–115 / DEP >115"),
    "REL": ("CORE", "다리 관계", ["PL", "AX", "KK", "F4", "RL", "RM", "RH"],
            "PL 두 발 바닥 / AX 발목 교차 / KK 무릎 겹침 / F4 발을 반대 무릎 위 / RL·RM·RH 한 발 들림 낮음·중간·높음"),
    "TRK": ("CORE", "상체 앞뒤 기울기", ["RC", "UP", "LS", "LN", "FD"], "RC 뒤로 젖힘 <-8° / UP / LS 약간 숙임 12–30 / LN 30–60 / FD >60"),
    "ARH": ("CORE", "손 높이", ["LO", "MI", "HI", "OV"], "LO 골반 아래 / MI 허리–가슴 / HI 어깨–머리 / OV 머리 위 (골반~정수리 정규화)"),
    "ARR": ("CORE", "팔 뻗음", ["TU", "MD", "EX"], "TU 몸통 가까이 / MD 중간 / EX 몸통에서 멀리 뻗음 (몸통 선분(골반–목)에서 손목까지 거리 / 팔 길이)"),
    "FAC": ("CORE", "기준 방향 대비 몸 방향", ["FR", "OB", "SD", "BK"], "FR 정면 <30° / OB 사선 30–70 / SD 측면 70–110 / BK 뒤 >110"),
    "STG": ("STANDARD", "발 위치 비대칭", ["AL", "FB", "SL"], "AL 나란함 / FB 앞뒤 어긋남 / SL 다리가 한쪽으로 기움"),
    "FLB": ("STANDARD", "무릎 굽힘 (덜 굽힌 다리)", ["EXT", "SLI", "RGT", "DEP"], "FLA와 같은 구간"),
    "CHI": ("STANDARD", "좌우 편향 (활동·기울어진 쪽)", ["L", "R", "S"], "L 왼쪽 / R 오른쪽 / S 대칭. 다른 축은 좌우 무관(역할 기준)이라 이 축 하나가 거울상을 구분"),
    "SPN": ("STANDARD", "척추 곡률", ["ST", "AR", "CU"], "ST 곧음 / AR 젖혀짐 / CU 말림"),
    "TWB": ("STANDARD", "상체 비틀림·옆굽힘", ["N", "T", "B", "TB"], "N 없음 / T 비틀림 ≥20° / B 옆굽힘 ≥15° / TB 둘 다"),
    "HED": ("STANDARD", "머리", ["NE", "TL", "BW", "RS", "TN"], "NE 중립 / TL 기울임 / BW 숙임 / RS 들음 / TN 돌림"),
    "HCT": ("STANDARD", "손 접촉", ["NO", "PA", "BD", "SP"], "NO 없음 / PA 두 손 맞닿음 / BD 자기 몸 접촉(허벅지·허리·가슴) / SP 바닥·물체 짚음"),
    "GND": ("STYLE", "남녀 (여성적–남성적 인상)", ["-2", "-1", "0", "+1", "+2"],
            "사람이 평가하는 지각 라벨. -2 여성적으로 읽힘 … +2 남성적으로 읽힘. 연기자의 성별이 아님. 문화권 태그 필수"),
    "AGE": ("STYLE", "노소 (어린–노년 인상)", ["-2", "-1", "0", "+1", "+2"],
            "사람이 평가하는 지각 라벨. -2 아동·매우 어림 / -1 젊고 활기참 / 0 성인 중립 / +1 중년 이상 / +2 고령으로 읽힘. 실제 나이가 아님"),
    "OPN": ("STYLE", "개방–폐쇄", ["-2", "-1", "0", "+1", "+2"], "기하 지표(좌우 확장 비율)로 사전 제안하고 사람이 확정. -2 매우 닫힘 … +2 매우 열림"),
    "TEN": ("STYLE+", "긴장–이완", ["-2", "-1", "0", "+1", "+2"], "확장 팩. 사람이 평가. -2 매우 이완 … +2 매우 긴장"),
    "FRM": ("STYLE+", "격식", ["-2", "-1", "0", "+1", "+2"], "확장 팩. 사람이 평가. -2 매우 편함 … +2 매우 격식"),
}
SEG_AXES = ["BASE", "SUP", "REL", "FAC", "FLA"]   # axes whose change defines a new key posture in a sequence
CORE = [k for k, v in AXES.items() if v[0] == "CORE"]
STANDARD = [k for k, v in AXES.items() if v[0] == "STANDARD"]
STYLE = [k for k, v in AXES.items() if v[0] == "STYLE"]
STYLE_EXT = [k for k, v in AXES.items() if v[0] == "STYLE+"]


def bits(axes):
    return float(sum(np.log2(len(AXES[a][2])) for a in axes))


# ----------------------------------------------------------------------------- helpers
def _bin(x, edges, names):
    for e, n in zip(edges, names):
        if x < e:
            return n
    return names[-1]


def _flex(a, b, c):
    u, v = a - b, c - b
    cs = u @ v / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-9)
    return 180.0 - float(np.degrees(np.arccos(np.clip(cs, -1, 1))))


def _hface(Lj, Rj):
    f = np.cross(Lj - Rj, UP)
    f[1] = 0
    return unit(f)


def _seg_dist(p, a, b):
    ab = b - a
    t = np.clip((p - a) @ ab / (ab @ ab + 1e-9), 0, 1)
    return float(np.linalg.norm(p - (a + ab * t)))


def label_frame(m: Motion, i: int, ref=(0.0, 0.0, 1.0)) -> dict:
    X, fd = m.X[i], m.foot_fd[i]
    j = lambda n: X[I[n]]
    chair = m.meta.get("chair")
    hipw = np.linalg.norm(j("l_hip") - j("r_hip"))
    thigh = np.linalg.norm(j("l_knee") - j("l_hip"))
    shank = np.linalg.norm(j("l_ankle") - j("l_knee"))
    legl = thigh + shank + 0.08 * thigh / 0.44
    arm_len = np.linalg.norm(j("l_elbow") - j("l_shoulder")) + np.linalg.norm(j("l_wrist") - j("l_elbow"))
    foot_low = {s: min(j(p + "toe")[1], j(p + "heel")[1]) for s, p in (("L", "l_"), ("R", "r_"))}
    contact = {s: foot_low[s] < 0.03 for s in "LR"}
    pf, cf = _hface(j("l_hip"), j("r_hip")), _hface(j("l_shoulder"), j("r_shoulder"))
    left = np.cross(UP, pf)
    com_xz = None
    pel = j("pelvis")
    seat = bool(chair) and pel[1] < chair["seat_h"] + 0.2 and abs(pel[0] - chair["x"]) < chair["w"] / 2 + 0.1 and abs(pel[2] - chair["z"]) < chair["d"] / 2 + 0.1
    kfl = {"L": _flex(j("l_hip"), j("l_knee"), j("l_ankle")), "R": _flex(j("r_hip"), j("r_knee"), j("r_ankle"))}
    L = {}
    # ---- BASE
    wrist_low = min(j("l_wrist")[1], j("r_wrist")[1])
    knee_low = min(j("l_knee")[1], j("r_knee")[1])
    trunk = j("neck") - pel
    tilt = float(np.degrees(np.arccos(np.clip(trunk[1] / np.linalg.norm(trunk), -1, 1))))
    if seat:
        L["BASE"] = "SI"
    elif not (contact["L"] or contact["R"]):
        L["BASE"] = "AI"
    elif pel[1] / legl >= 0.7:
        L["BASE"] = "ST"
    elif tilt > 60 and pel[1] < 0.3:
        L["BASE"] = "LY"
    elif wrist_low < 0.1 and pel[1] / legl < 0.7:
        L["BASE"] = "SU"
    elif knee_low < 0.15:
        L["BASE"] = "KN"
    else:
        L["BASE"] = "SQ"
    # ---- SUP (lower-limb load)
    nct = sum(contact.values())
    if nct == 0:
        L["SUP"] = "NO"
    elif nct == 1:
        L["SUP"] = "ONE"
    else:
        from .render import com
        c = com(X)
        a = 0.5 * (j("l_toe") + j("l_heel"))[[0, 2]]
        b = 0.5 * (j("r_toe") + j("r_heel"))[[0, 2]]
        ab = a - b
        f = float((c[[0, 2]] - b) @ ab / (ab @ ab + 1e-9))
        L["SUP"] = "EV" if (0.3 <= f <= 0.7 or L["BASE"] == "SI") else "BI"
    # ---- SPR
    if L["BASE"] in ("ST", "AI"):
        gap = abs((j("l_ankle") - j("r_ankle")) @ left)
    else:
        gap = abs((j("l_knee") - j("r_knee")) @ left)
    L["SPR"] = _bin(gap / hipw, [0.9, 1.4, 2.2, 3.2], ["1", "2", "3", "4", "5"])
    # ---- flexion
    hi, lo = max(kfl.values()), min(kfl.values())
    nm = ["EXT", "SLI", "RGT", "DEP"]
    L["FLA"] = _bin(hi, [25, 60, 115], nm)
    L["FLB"] = _bin(lo, [25, 60, 115], nm)
    # ---- REL
    lifted = [s for s in "LR" if foot_low[s] > 0.06]
    kk = (-(j("l_knee") - j("r_knee")) @ (j("l_hip") - j("r_hip")) / (hipw ** 2))
    ak = (-(j("l_ankle") - j("r_ankle")) @ (j("l_hip") - j("r_hip")) / (hipw ** 2))
    kh = abs(j("l_knee")[1] - j("r_knee")[1])
    if kk > 0.15 and kh > 0.04:
        L["REL"] = "KK"
    elif len(lifted) == 1 and _seg_dist(j(("l_" if lifted[0] == "L" else "r_") + "ankle"),
                                        j(("r_" if lifted[0] == "L" else "l_") + "hip"), j(("r_" if lifted[0] == "L" else "l_") + "knee")) < 0.12:
        L["REL"] = "F4"
    elif not lifted and ak > 0.3:
        L["REL"] = "AX"
    elif not lifted:
        L["REL"] = "PL"
    else:
        s = lifted[0]
        pre = "l_" if s == "L" else "r_"
        r = j(pre + "ankle")[1] / max(j(pre + "hip")[1], 1e-6)
        L["REL"] = "RL" if r < 0.5 else ("RM" if r < 1.0 else "RH")
    # ---- trunk
    pitch = float(np.degrees(np.arctan2(trunk @ pf, trunk[1])))
    lean = float(np.degrees(np.arctan2(trunk @ left, trunk[1])))
    L["TRK"] = _bin(pitch, [-8, 12, 30, 60], ["RC", "UP", "LS", "LN", "FD"])
    lum, tho = j("spine") - pel, j("chest") - j("spine")
    curl = float(np.degrees(np.arctan2(tho @ pf, tho[1])) - np.degrees(np.arctan2(lum @ pf, lum[1])))
    L["SPN"] = "CU" if curl > 12 else ("AR" if curl < -8 else "ST")
    ang = lambda v: np.degrees(np.arctan2(v[0], v[2]))
    twist = abs((ang(cf) - ang(pf) + 180) % 360 - 180)
    t, b = twist >= 20, abs(lean) >= 15
    L["TWB"] = "TB" if (t and b) else ("T" if t else ("B" if b else "N"))
    # ---- head (facing vector + roll)
    hf = m.head_fd[i]
    hpitch = float(np.degrees(np.arcsin(np.clip(hf[1], -1, 1))))
    hyaw = abs((ang(hf) - ang(pf) + 180) % 360 - 180)
    hv = j("head") - j("neck")
    hroll = abs(float(np.degrees(np.arctan2(hv @ left, hv[1]))))
    score = {"BW": max(0, -hpitch - 12) / 12, "RS": max(0, hpitch - 15) / 15, "TN": max(0, hyaw - 30) / 30, "TL": max(0, hroll - 10) / 10}
    best = max(score, key=score.get)
    L["HED"] = best if score[best] > 0 else "NE"
    # ---- arms
    top = j("head_top")[1]
    hh = max(j("l_wrist")[1], j("r_wrist")[1])
    z = (hh - pel[1]) / (top - pel[1])
    L["ARH"] = _bin(z, [0.25, 0.65, 1.0], ["LO", "MI", "HI", "OV"])
    reach = [_seg_dist(j(p + "wrist"), pel, j("neck")) / arm_len for p in ("l_", "r_")]   # distance to the trunk segment
    L["ARR"] = _bin(max(reach), [0.45, 0.8], ["TU", "MD", "EX"])
    dh = np.linalg.norm(j("l_wrist") - j("r_wrist"))
    thigh_d = min(_seg_dist(j(a + "wrist"), j(b + "hip"), j(b + "knee")) for a in ("l_", "r_") for b in ("l_", "r_"))
    torso_d = min(_seg_dist(j(a + "wrist"), j("pelvis"), j("neck")) for a in ("l_", "r_"))
    if dh < 0.10:
        L["HCT"] = "PA"
    elif wrist_low < 0.1 or (chair and wrist_low < chair["seat_h"] - 0.05):
        L["HCT"] = "SP"
    elif thigh_d < 0.12 or torso_d < 0.15:
        L["HCT"] = "BD"
    else:
        L["HCT"] = "NO"
    # ---- orientation vs reference
    r = unit(np.array(ref, float))
    fa = abs((ang(pf) - ang(r) + 180) % 360 - 180)
    L["FAC"] = _bin(fa, [30, 70, 110], ["FR", "OB", "SD", "BK"])
    # ---- stagger
    fb = abs((j("l_ankle") - j("r_ankle")) @ pf) / legl
    mid_h = 0.5 * (j("l_hip") + j("r_hip"))
    sl = abs(((0.5 * (j("l_ankle") + j("r_ankle")) - mid_h) @ left) / legl)
    L["STG"] = "FB" if fb >= 0.12 else ("SL" if sl >= 0.1 else "AL")
    if L["REL"] == "KK":
        L["CHI"] = "L" if j("l_knee")[1] > j("r_knee")[1] else "R"
    elif lifted:
        L["CHI"] = lifted[0]
    elif L["STG"] == "SL":
        L["CHI"] = "L" if ((0.5 * (j("l_ankle") + j("r_ankle")) - mid_h) @ left) > 0 else "R"
    elif L["STG"] == "FB":
        L["CHI"] = "L" if (j("l_ankle") - j("r_ankle")) @ pf > 0 else "R"
    else:
        L["CHI"] = "S"
    # ---- style proposal from geometry (human rater confirms)
    pts = np.array([j(n) for n in ("l_knee", "r_knee", "l_ankle", "r_ankle", "l_wrist", "r_wrist", "l_toe", "r_toe")])
    ext = float(((pts @ left).max() - (pts @ left).min()) / np.linalg.norm(j("l_shoulder") - j("r_shoulder")))
    L["OPN"] = _bin(ext, [0.5, 0.75, 1.3, 1.8], ["-2", "-1", "0", "+1", "+2"])
    return L


# ----------------------------------------------------------------------------- code strings
def code(L: dict, axes=None, unspecified="*") -> str:
    axes = axes or (CORE + STANDARD)
    return "|".join(f"{a}:{L.get(a, unspecified)}" for a in axes)


def label_pose(m: Motion, ref=(0, 0, 1)) -> dict:
    """Label a held pose: majority over frames per axis."""
    ls = [label_frame(m, i, ref) for i in range(0, m.T, max(1, m.T // 8))]
    return {a: max(set(x[a] for x in ls), key=[x[a] for x in ls].count) for a in ls[0]}


def label_sequence(m: Motion, ref=(0, 0, 1), axes=None, seg_axes=None, step_hz=60, min_run_s=0.05, win=1):
    """Posture sequence. Segment on the stable CORE axes (mode-filtered), then fill every other axis with the
    per-segment mode. Runs shorter than min_run_s are absorbed by the previous run."""
    axes = axes or (CORE + STANDARD)
    seg_axes = seg_axes or SEG_AXES
    stride = max(1, int(round(m.fps / step_hz)))
    idx = list(range(0, m.T, stride))
    labs = [label_frame(m, i, ref) for i in idx]
    sm = []
    for k in range(len(labs)):
        w = labs[max(0, k - win):k + win + 1]
        sm.append({a: max(set(x[a] for x in w), key=[x[a] for x in w].count) for a in labs[0]})
    runs = []
    for k, L in enumerate(sm):
        c = code(L, seg_axes)
        if runs and runs[-1]["seg"] == c:
            runs[-1]["k1"] = k
        else:
            runs.append(dict(seg=c, k0=k, k1=k))
    dt = 1.0 / step_hz
    merged = []
    for r in runs:
        if merged and (r["k1"] - r["k0"] + 1) * dt < min_run_s:
            merged[-1]["k1"] = r["k1"]
        else:
            merged.append(r)
    out = []
    for r in merged:
        seg = sm[r["k0"]:r["k1"] + 1]
        L = {a: max(set(x[a] for x in seg), key=[x[a] for x in seg].count) for a in seg[0]}
        out.append([code(L, axes), idx[r["k0"]] / m.fps, idx[r["k1"]] / m.fps, L])
    return out


# ----------------------------------------------------------------------------- domain pack: strike (transition axes)
STRIKE_AXES = {
    "PTH": ("PACK:STRIKE", "타격 경로", ["LN", "MX", "AR"], "LN 직선(타격 속도 ∥ 다리 축 <35°) / MX / AR 호(≥55°)"),
    "LED": ("PACK:STRIKE", "타격면", ["SO", "IN", "BL", "IE", "HE", "TO"], "SO 발바닥·앞축 / IN 발등 / BL 발날(바깥) / IE 안쪽 / HE 뒤꿈치 / TO 발끝"),
}


def strike_pack(m: Motion) -> dict:
    from .attributes import dynamic_attrs
    A = dynamic_attrs(m)
    if not A.get("kick.present"):
        return {}
    d = A["impact.strike_vs_limb_deg"]
    pth = "LN" if d < 35 else ("AR" if d >= 55 else "MX")
    led = {"sole": "SO", "instep": "IN", "outer_edge": "BL", "inner_edge": "IE", "heel": "HE", "toe": "TO"}[A["impact.leading_surface"]]
    return {"PTH": pth, "LED": led, "_strike_vs_limb_deg": d}


def export_schema(path):
    import json
    out = {"version": "0.1", "note": "축은 모두 '*'(미지정) 허용. 좌우는 역할 기준(CHI 하나로만 구분). STYLE 층은 사람이 평가하는 지각 라벨.",
           "tiers": {"CORE": CORE, "STANDARD": STANDARD, "STYLE": STYLE, "STYLE+": STYLE_EXT, "PACK:STRIKE": list(STRIKE_AXES)},
           "bits": {"CORE": round(bits(CORE), 1), "STANDARD": round(bits(STANDARD), 1), "STYLE": round(bits(STYLE), 1)},
           "seg_axes": SEG_AXES,
           "axes": {k: {"tier": v[0], "name": v[1], "levels": v[2], "desc": v[3]} for k, v in {**AXES, **STRIKE_AXES}.items()}}
    json.dump(out, open(path, "w"), ensure_ascii=False, indent=1)
    return out
