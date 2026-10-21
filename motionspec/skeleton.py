"""Procedural humanoid skeleton: pose building (IK/FK), keyframe interpolation, mirroring.

World frame: +Y up, +Z = the direction the character initially faces, +X = character's left.
Angles are degrees. Yaw > 0 turns toward +X (character's left). Pitch > 0 leans forward.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

import numpy as np
from scipy.interpolate import PchipInterpolator

NAMES = [
    "pelvis", "spine", "chest", "neck", "head", "head_top",
    "l_shoulder", "l_elbow", "l_wrist", "l_hand",
    "r_shoulder", "r_elbow", "r_wrist", "r_hand",
    "l_hip", "l_knee", "l_ankle", "l_toe", "l_heel",
    "r_hip", "r_knee", "r_ankle", "r_toe", "r_heel",
]
I = {n: i for i, n in enumerate(NAMES)}
MIRROR = {}
for _n in NAMES:
    if _n.startswith("l_"):
        MIRROR[_n] = "r_" + _n[2:]
    elif _n.startswith("r_"):
        MIRROR[_n] = "l_" + _n[2:]
    else:
        MIRROR[_n] = _n
MIRROR_IDX = [I[MIRROR[n]] for n in NAMES]

L = dict(pelvis_spine=0.15, spine_chest=0.17, chest_neck=0.20, neck_head=0.12, head_top=0.12,
         shoulder_half=0.19, hip_half=0.10, hip_drop=0.03, thigh=0.44, shank=0.43,
         ankle_h=0.08, foot_fwd=0.17, heel_back=0.07, upper_arm=0.29, fore=0.26, hand=0.18)
LEG_LEN = L["thigh"] + L["shank"] + L["ankle_h"]
BODY_H = 1.74
HIP_W = 2 * L["hip_half"]
SHOULDER_W = 2 * L["shoulder_half"]


def Ry(d):
    c, s = np.cos(np.radians(d)), np.sin(np.radians(d))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rx(d):
    c, s = np.cos(np.radians(d)), np.sin(np.radians(d))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Rz(d):
    c, s = np.cos(np.radians(d)), np.sin(np.radians(d))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler(yaw, pitch, lean_left):
    """yaw about Y, then pitch (forward lean), then lean toward the character's left."""
    return Ry(yaw) @ Rx(pitch) @ Rz(-lean_left)


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def two_bone(root, tgt, l1, l2, pole):
    v = tgt - root
    dist = np.linalg.norm(v)
    a = unit(v)
    d = float(np.clip(dist, 1e-6, l1 + l2 - 1e-6))
    c = np.clip((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1, 1)
    s = np.sqrt(1 - c * c)
    pp = pole - (pole @ a) * a
    if np.linalg.norm(pp) < 1e-6:
        pp = np.cross(a, [1.0, 0, 0])
    pp = unit(pp)
    return root + a * (l1 * c) + pp * (l1 * s), root + a * d


def foot_axes(frot):
    """frot = (yaw, plantarflexion, roll). Returns (forward, sole-direction) unit vectors."""
    R = Ry(frot[0]) @ Rx(frot[1]) @ Rz(frot[2])
    return R @ np.array([0, 0, 1.0]), R @ np.array([0, -1.0, 0])


def foot_points(ankle, fd, sd):
    toe = ankle + L["foot_fwd"] * fd + L["ankle_h"] * sd
    heel = ankle - L["heel_back"] * fd + L["ankle_h"] * sd
    return toe, heel


@dataclass
class Frame:
    X: np.ndarray            # (24, 3)
    foot_fd: np.ndarray      # (2, 3) left,right
    foot_sd: np.ndarray      # (2, 3)
    head_fd: np.ndarray      # (3,)
    warn: list = field(default_factory=list)


# ---- parameter layout: every pose is a flat vector so keyframes can be interpolated ----
LAYOUT = [
    ("pelvis", 3), ("pelvis_rot", 3), ("chest_rot", 3), ("head_rot", 3), ("support_flex", 1), ("arm_local", 1),
    ("aL_wrist", 3), ("aL_pole", 3), ("aR_wrist", 3), ("aR_pole", 3),
    ("L_ball", 3), ("L_pole", 3), ("L_thigh", 3), ("L_ant", 3), ("L_flex", 1), ("L_frot", 3),
    ("R_ball", 3), ("R_pole", 3), ("R_thigh", 3), ("R_ant", 3), ("R_flex", 1), ("R_frot", 3),
]
SIZES = dict(LAYOUT)
OFFS = {}
_o = 0
for _k, _s in LAYOUT:
    OFFS[_k] = (_o, _o + _s)
    _o += _s
DIM = _o


class Pose:
    """Convenience wrapper over a flat parameter vector with named access."""

    def __init__(self, v=None):
        self.v = np.zeros(DIM) if v is None else np.array(v, float)

    def __getitem__(self, k):
        a, b = OFFS[k]
        return self.v[a:b] if b - a > 1 else self.v[a]

    def __setitem__(self, k, val):
        a, b = OFFS[k]
        self.v[a:b] = np.atleast_1d(np.asarray(val, float))

    def copy(self, **kw):
        q = Pose(self.v.copy())
        for k, val in kw.items():
            q[k] = val
        return q


def build_frame(pv, modes, support=None):
    """Build joint positions. modes = {'L': 'ik'|'fk', 'R': ...}. support = 'L'/'R' to auto-solve pelvis height."""
    p = Pose(pv)
    warn = []
    Rp, Rc, Rh = euler(*p["pelvis_rot"]), euler(*p["chest_rot"]), euler(*p["head_rot"])
    Rm = euler(*(0.5 * (p["pelvis_rot"] + p["chest_rot"])))
    pel = p["pelvis"].copy()
    legs = {}
    for side, sgn in (("L", +1), ("R", -1)):
        fd, sd = foot_axes(p[f"{side}_frot"])
        legs[side] = dict(fd=fd, sd=sd, off=Rp @ np.array([sgn * L["hip_half"], -L["hip_drop"], 0.0]))
        if modes[side] == "ik":
            ball = p[f"{side}_ball"]
            legs[side]["ankle"] = ball - L["foot_fwd"] * fd - L["ankle_h"] * sd
    if support:
        a = legs[support]["ankle"]
        off = legs[support]["off"]
        flex = np.radians(p["support_flex"])
        d2 = L["thigh"] ** 2 + L["shank"] ** 2 + 2 * L["thigh"] * L["shank"] * np.cos(flex)
        horiz2 = (pel[0] + off[0] - a[0]) ** 2 + (pel[2] + off[2] - a[2]) ** 2
        if horiz2 > d2:
            warn.append("support leg reach clamped")
            dy = 0.0
        else:
            dy = np.sqrt(d2 - horiz2)
        pel[1] = a[1] + dy - off[1]
    spine = pel + Rp @ np.array([0, L["pelvis_spine"], 0])
    chest = spine + Rm @ np.array([0, L["spine_chest"], 0])
    neck = chest + Rc @ np.array([0, L["chest_neck"], 0])
    head = neck + Rh @ np.array([0, L["neck_head"], 0])
    top = head + Rh @ np.array([0, L["head_top"], 0])
    X = np.zeros((len(NAMES), 3))
    X[I["pelvis"]], X[I["spine"]], X[I["chest"]], X[I["neck"]], X[I["head"]], X[I["head_top"]] = pel, spine, chest, neck, head, top
    for side, sgn, pre in (("L", +1, "l_"), ("R", -1, "r_")):
        sh = neck + Rc @ np.array([sgn * L["shoulder_half"], -0.03, 0])
        wtgt = neck + Rc @ p[f"a{side}_wrist"] if p["arm_local"] > 0.5 else p[f"a{side}_wrist"]
        pole = Rc @ p[f"a{side}_pole"] if p["arm_local"] > 0.5 else p[f"a{side}_pole"]
        elbow, wrist = two_bone(sh, wtgt, L["upper_arm"], L["fore"], pole)
        if np.linalg.norm(wtgt - sh) > L["upper_arm"] + L["fore"]:
            warn.append(f"arm {side} reach clamped")
        hand = wrist + L["hand"] * unit(wrist - elbow)
        X[I[pre + "shoulder"]], X[I[pre + "elbow"]], X[I[pre + "wrist"]], X[I[pre + "hand"]] = sh, elbow, wrist, hand
        hip = pel + legs[side]["off"]
        fd, sd = legs[side]["fd"], legs[side]["sd"]
        if modes[side] == "ik":
            knee, ankle = two_bone(hip, legs[side]["ankle"], L["thigh"], L["shank"], p[f"{side}_pole"])
            if np.linalg.norm(legs[side]["ankle"] - hip) > L["thigh"] + L["shank"]:
                warn.append(f"leg {side} reach clamped")
        else:
            t = unit(p[f"{side}_thigh"])
            ant = p[f"{side}_ant"]
            ant = unit(ant - (ant @ t) * t)
            flex = np.radians(p[f"{side}_flex"])
            knee = hip + L["thigh"] * t
            ankle = knee + L["shank"] * (t * np.cos(flex) - ant * np.sin(flex))
        toe, heel = foot_points(ankle, fd, sd)
        X[I[pre + "hip"]], X[I[pre + "knee"]], X[I[pre + "ankle"]], X[I[pre + "toe"]], X[I[pre + "heel"]] = hip, knee, ankle, toe, heel
    return Frame(X, np.array([legs["L"]["fd"], legs["R"]["fd"]]), np.array([legs["L"]["sd"], legs["R"]["sd"]]), Rh @ np.array([0, 0, 1.0]), warn)


def leg_to_fk(pv, modes, side, support=None):
    """Convert an IK-authored leg keyframe into FK parameters (thigh direction, anterior axis, flex)."""
    fr = build_frame(pv, {**modes, side: "ik"}, support)
    pre = "l_" if side == "L" else "r_"
    hip, knee, ankle = fr.X[I[pre + "hip"]], fr.X[I[pre + "knee"]], fr.X[I[pre + "ankle"]]
    t = unit(knee - hip)
    s = unit(ankle - knee)
    cosf = np.clip(t @ s, -1, 1)
    flex = np.degrees(np.arccos(cosf))
    # anterior axis: direction opposite to the shank deviation from the thigh line
    a = unit(t * cosf - s) if flex > 1e-3 else np.array([0, 0, 1.0])
    p = Pose(pv)
    p[f"{side}_thigh"], p[f"{side}_ant"], p[f"{side}_flex"] = t, a, flex
    return p.v


@dataclass
class Motion:
    name: str
    fps: float
    X: np.ndarray            # (T, 24, 3)
    foot_fd: np.ndarray      # (T, 2, 3)
    foot_sd: np.ndarray      # (T, 2, 3)
    head_fd: np.ndarray      # (T, 3)
    meta: dict = field(default_factory=dict)

    @property
    def T(self):
        return self.X.shape[0]

    @property
    def t(self):
        return np.arange(self.T) / self.fps

    def j(self, name):
        return self.X[:, I[name]]


def render_sequence(name, keys, times, modes, support, fps=120, meta=None, hold_end=0.0):
    """keys: list of Pose; times: keyframe times. PCHIP interpolation per dimension."""
    V = np.array([k.v for k in keys])
    times = np.asarray(times, float)
    ts = np.arange(0, times[-1] + hold_end + 1e-9, 1.0 / fps)
    tt = np.minimum(ts, times[-1])
    if len(keys) == 1:
        Vs = np.repeat(V, len(ts), axis=0)
    else:
        Vs = PchipInterpolator(times, V, axis=0)(tt)
    frames = [build_frame(v, modes, support) for v in Vs]
    m = Motion(name, fps, np.array([f.X for f in frames]), np.array([f.foot_fd for f in frames]),
               np.array([f.foot_sd for f in frames]), np.array([f.head_fd for f in frames]), dict(meta or {}))
    m.meta["warnings"] = sorted({w for f in frames for w in f.warn})
    return m


def mirrored(m: Motion, name=None):
    X = m.X[:, MIRROR_IDX].copy()
    X[:, :, 0] *= -1
    fd = m.foot_fd[:, ::-1].copy()
    sd = m.foot_sd[:, ::-1].copy()
    fd[:, :, 0] *= -1
    sd[:, :, 0] *= -1
    hf = m.head_fd.copy()
    hf[:, 0] *= -1
    meta = copy.deepcopy(m.meta)
    meta["mirrored"] = not meta.get("mirrored", False)
    return Motion(name or m.name, m.fps, X, fd, sd, hf, meta)


def scaled(m: Motion, s):
    """Uniform body scale about the floor origin (keeps feet on the floor)."""
    meta = copy.deepcopy(m.meta)
    meta["body_scale"] = meta.get("body_scale", 1.0) * s
    return Motion(m.name, m.fps, m.X * s, m.foot_fd, m.foot_sd, m.head_fd, meta)
