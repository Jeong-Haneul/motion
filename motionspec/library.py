"""Procedurally authored example poses/motions. These are hand-authored (not motion capture) and exist to
exercise the attribute extractor, the specs and the evaluation sheets."""
from __future__ import annotations

import numpy as np

from .skeleton import Pose, leg_to_fk, render_sequence, unit

V = np.array
CHAIR = dict(x=0.0, z=0.0, seat_h=0.46, w=0.46, d=0.42)


def dir_from(az, el):
    """az: degrees from +Z toward +X; el: degrees above horizontal."""
    a, e = np.radians(az), np.radians(el)
    return V([np.sin(a) * np.cos(e), np.sin(e), np.cos(a) * np.cos(e)])


def fwd(yaw):
    return V([np.sin(np.radians(yaw)), 0, np.cos(np.radians(yaw))])


# ------------------------------------------------------------------ sitting poses
def seated_base():
    p = Pose()
    p["pelvis"] = (0, 0.57, -0.08)
    p["pelvis_rot"] = (0, 0, 0)
    p["chest_rot"] = (0, 0, 0)
    p["head_rot"] = (0, 0, 0)
    p["aL_pole"] = (0.4, -1, -0.3)
    p["aR_pole"] = (-0.4, -1, -0.3)
    for s in "LR":
        p[f"{s}_frot"] = (0, 0, 0)
        p[f"{s}_pole"] = (0, 0, 1)
        p[f"{s}_ball"] = (0, 0, 0.4)
    return p


def sit(name, pose, modes=None, meta_extra=None, hold=0.5):
    meta = dict(chair=dict(CHAIR), kind="pose", **(meta_extra or {}))
    return render_sequence(name, [pose], [0.0], modes or {"L": "ik", "R": "ik"}, None, fps=30, meta=meta, hold_end=hold)


def ball_from_ankle(x, z, yaw=0):
    """Ball-of-foot target for a flat foot whose ankle is at (x, 0.08, z)."""
    f = fwd(yaw)
    return V([x + 0.17 * f[0], 0.0, z + 0.17 * f[2]])


def sit_closed_slanted():
    p = seated_base()
    p["pelvis_rot"] = (0, 2, 0)
    p["chest_rot"] = (4, 0, 0)
    p["head_rot"] = (10, -2, 7)
    p["L_ball"] = ball_from_ankle(0.20, 0.30, 18)
    p["R_ball"] = ball_from_ankle(0.12, 0.27, 18)
    p["L_frot"] = (18, 0, 0)
    p["R_frot"] = (18, 0, 0)
    p["L_pole"] = (0.15, 0, 1)
    p["R_pole"] = (0.25, 0, 1)
    p["aL_wrist"] = (0.05, 0.60, 0.14)
    p["aR_wrist"] = (0.12, 0.60, 0.15)
    return sit("Sitting: knees together, legs slanted, hands on lap", p)


def sit_wide():
    p = seated_base()
    p["pelvis"] = (0, 0.56, -0.05)
    p["pelvis_rot"] = (0, -12, 0)
    p["chest_rot"] = (0, -10, 0)
    p["head_rot"] = (0, 4, 0)
    p["L_ball"] = ball_from_ankle(0.34, 0.34, 12)
    p["R_ball"] = ball_from_ankle(-0.34, 0.34, -12)
    p["L_frot"] = (12, 0, 0)
    p["R_frot"] = (-12, 0, 0)
    p["L_pole"] = (0.55, 0, 1)
    p["R_pole"] = (-0.55, 0, 1)
    p["aL_wrist"] = (0.26, 0.58, 0.20)
    p["aR_wrist"] = (-0.26, 0.58, 0.20)
    return sit("Sitting: legs wide apart, reclined", p)


def sit_neutral():
    p = seated_base()
    p["L_ball"] = ball_from_ankle(0.16, 0.36, 0)
    p["R_ball"] = ball_from_ankle(-0.16, 0.36, 0)
    p["aL_wrist"] = (0.14, 0.60, 0.20)
    p["aR_wrist"] = (-0.14, 0.60, 0.20)
    return sit("Sitting: upright, knees hip-width, feet flat", p)


def sit_knee_over_knee():
    p = seated_base()
    p["chest_rot"] = (12, 0, 0)
    p["head_rot"] = (8, 0, 0)
    p["L_ball"] = ball_from_ankle(0.08, 0.30, 5)
    p["L_pole"] = (0, 0, 1)
    p["R_thigh"] = dir_from(34, 7)
    p["R_ant"] = (0.0, 0.8, -0.6)
    p["R_flex"] = 100
    p["R_frot"] = (30, 45, 0)
    p["aL_wrist"] = (0.10, 0.60, 0.20)
    p["aR_wrist"] = (0.12, 0.68, 0.30)
    return sit("Sitting: right knee over left knee", p, modes={"L": "ik", "R": "fk"})


# ------------------------------------------------------------------ kicks
STANCE_FRONT_BALL = V([0.17, 0.0, 0.40])   # support (left, front) foot ball position
STANCE_REAR_BALL = V([-0.26, 0.0, -0.22])


def kick_pose(t, pel_xz, pelvis_rot, chest_rot, head_rot, support_flex, sup_frot, thigh=None, ant=None, flex=None,
              frot=None, awL=(0.16, -0.12, 0.30), awR=(-0.10, -0.18, 0.22)):
    p = Pose()
    p["pelvis"] = (pel_xz[0], 0.9, pel_xz[1])
    p["pelvis_rot"], p["chest_rot"], p["head_rot"] = pelvis_rot, chest_rot, head_rot
    p["support_flex"] = support_flex
    p["arm_local"] = 1
    p["aL_wrist"], p["aR_wrist"] = awL, awR
    p["aL_pole"], p["aR_pole"] = (0.5, -1, -0.2), (-0.5, -1, -0.2)
    p["L_ball"] = STANCE_FRONT_BALL
    p["L_frot"] = sup_frot
    p["L_pole"] = fwd(sup_frot[0])
    if thigh is not None:
        p["R_thigh"] = dir_from(*thigh)
        p["R_ant"] = ant
        p["R_flex"] = flex
        p["R_frot"] = frot
    return p


def stance_key(yaw=-35):
    p = kick_pose(0, (0.0, 0.0), (yaw, 3, 0), (yaw + 15, 4, 0), (yaw + 35, 0, 0), 35, (-12, 0, 0))
    p["R_ball"] = STANCE_REAR_BALL
    p["R_frot"] = (-58, 0, 0)
    p["R_pole"] = fwd(-58)
    return p


def build_kick(name, rows, rear_ball_frot=(-58, 0, 0), fps=120, hold=0.1, meta_extra=None):
    """rows: list of dicts(t, **kick_pose kwargs). First row is the IK-authored stance."""
    modes = {"L": "ik", "R": "fk"}
    keys, times = [], []
    for k, r in enumerate(rows):
        r = dict(r)
        t = r.pop("t")
        if k == 0:
            p = stance_key(r.get("yaw", -35))
            keys.append(Pose(leg_to_fk(p.v, {"L": "ik", "R": "ik"}, "R", support="L")))
        else:
            keys.append(kick_pose(t, **r))
        times.append(t)
    m = render_sequence(name, keys, times, modes, "L", fps=fps, meta=dict(kind="motion", **(meta_extra or {})), hold_end=hold)
    return m


UP = V([-0.25, 1.0, 0.0])


def roundhouse(name="Roundhouse kick (dollyeo chagi), right leg"):
    rows = [
        dict(t=0.00),
        dict(t=0.20, pel_xz=(0.03, 0.08), pelvis_rot=(-12, 3, 0), chest_rot=(-2, 3, 0), head_rot=(2, 0, 0), support_flex=30,
             sup_frot=(0, 8, 0), thigh=(-14, -30), ant=V([-0.2, 1, 0.3]), flex=78, frot=(-20, 50, 0)),
        dict(t=0.32, pel_xz=(0.08, 0.20), pelvis_rot=(30, 0, 2), chest_rot=(15, 0, 4), head_rot=(2, 0, 3), support_flex=24,
             sup_frot=(52, 14, 0), thigh=(-24, 12), ant=UP, flex=118, frot=(-10, 62, -10),
             awL=(0.20, -0.10, 0.28), awR=(-0.14, -0.14, 0.26)),
        dict(t=0.40, pel_xz=(0.13, 0.30), pelvis_rot=(68, 0, 5), chest_rot=(48, 0, 12), head_rot=(4, 0, 6), support_flex=18,
             sup_frot=(98, 18, 0), thigh=(-4, 17), ant=UP, flex=62, frot=(4, 34, -85),
             awL=(0.30, -0.06, 0.12), awR=(-0.20, -0.10, 0.26)),
        dict(t=0.46, pel_xz=(0.16, 0.34), pelvis_rot=(100, 0, 8), chest_rot=(86, 0, 26), head_rot=(8, 0, 10), support_flex=14,
             sup_frot=(128, 20, 0), thigh=(12, 22), ant=UP, flex=7, frot=(12, 24, -92),
             awL=(0.34, -0.02, 0.02), awR=(-0.22, -0.14, 0.24)),
        dict(t=0.58, pel_xz=(0.15, 0.32), pelvis_rot=(70, 0, 6), chest_rot=(62, 0, 14), head_rot=(6, 0, 6), support_flex=20,
             sup_frot=(112, 18, 0), thigh=(-6, 8), ant=UP, flex=104, frot=(-6, 50, -40)),
        dict(t=0.74, pel_xz=(0.13, 0.30), pelvis_rot=(20, 3, 0), chest_rot=(14, 3, 0), head_rot=(4, 0, 0), support_flex=28,
             sup_frot=(96, 8, 0), thigh=(-8, -38), ant=V([-0.1, 1, 0.3]), flex=60, frot=(-8, 30, 0)),
    ]
    return build_kick(name, rows, meta_extra=dict(target_dir=(0, 0, 1)))


def front_kick(name="Front kick (ap chagi), right leg"):
    ANT = V([0.0, 1.0, 0.1])
    rows = [
        dict(t=0.00),
        dict(t=0.18, pel_xz=(0.02, 0.06), pelvis_rot=(-20, 3, 0), chest_rot=(-8, 3, 0), head_rot=(2, 0, 0), support_flex=30,
             sup_frot=(-10, 8, 0), thigh=(-6, -25), ant=ANT, flex=80, frot=(-8, 45, 0)),
        dict(t=0.30, pel_xz=(0.04, 0.12), pelvis_rot=(-10, 0, 0), chest_rot=(-2, 0, 0), head_rot=(2, 0, 0), support_flex=24,
             sup_frot=(-8, 14, 0), thigh=(-2, 52), ant=ANT, flex=112, frot=(0, 60, 0)),
        dict(t=0.38, pel_xz=(0.05, 0.16), pelvis_rot=(-6, -3, 0), chest_rot=(0, -7, 0), head_rot=(4, -4, 0), support_flex=18,
             sup_frot=(-8, 22, 0), thigh=(0, 42), ant=ANT, flex=8, frot=(2, -78, 0)),
        dict(t=0.52, pel_xz=(0.04, 0.12), pelvis_rot=(-12, 0, 0), chest_rot=(-4, 0, 0), head_rot=(2, 0, 0), support_flex=24,
             sup_frot=(-9, 14, 0), thigh=(-2, 46), ant=ANT, flex=108, frot=(0, 55, 0)),
        dict(t=0.70, pel_xz=(0.03, 0.08), pelvis_rot=(-22, 3, 0), chest_rot=(-8, 3, 0), head_rot=(2, 0, 0), support_flex=28,
             sup_frot=(-11, 6, 0), thigh=(-4, -30), ant=ANT, flex=62, frot=(-6, 30, 0)),
    ]
    return build_kick(name, rows, meta_extra=dict(target_dir=(0, 0, 1)))


def side_kick(name="Side kick (yeop chagi), right leg"):
    rows = [
        dict(t=0.00),
        dict(t=0.20, pel_xz=(0.04, 0.10), pelvis_rot=(5, 3, 0), chest_rot=(-5, 3, 0), head_rot=(2, 0, 0), support_flex=30,
             sup_frot=(20, 8, 0), thigh=(-20, -20), ant=UP, flex=85, frot=(-10, 50, 0)),
        dict(t=0.33, pel_xz=(0.10, 0.24), pelvis_rot=(62, 0, 6), chest_rot=(48, 0, 10), head_rot=(6, 0, 4), support_flex=22,
             sup_frot=(105, 14, 0), thigh=(-8, 50), ant=V([-0.1, 1.0, 0.2]), flex=128, frot=(80, 15, -10),
             awL=(0.28, -0.08, 0.20), awR=(-0.18, -0.12, 0.26)),
        dict(t=0.41, pel_xz=(0.15, 0.32), pelvis_rot=(98, 0, 8), chest_rot=(88, 0, 30), head_rot=(8, 0, 12), support_flex=16,
             sup_frot=(150, 18, 0), thigh=(6, 20), ant=UP, flex=34, frot=(90, 4, 0),
             awL=(0.34, -0.04, 0.06), awR=(-0.22, -0.12, 0.24)),
        dict(t=0.47, pel_xz=(0.17, 0.35), pelvis_rot=(104, 0, 9), chest_rot=(94, 0, 34), head_rot=(8, 0, 14), support_flex=12,
             sup_frot=(160, 20, 0), thigh=(8, 18), ant=UP, flex=6, frot=(90, 2, 0),
             awL=(0.36, -0.02, 0.0), awR=(-0.22, -0.14, 0.24)),
        dict(t=0.62, pel_xz=(0.14, 0.30), pelvis_rot=(80, 0, 6), chest_rot=(68, 0, 18), head_rot=(6, 0, 8), support_flex=20,
             sup_frot=(140, 16, 0), thigh=(-8, 40), ant=V([-0.1, 1.0, 0.2]), flex=120, frot=(75, 20, -10)),
        dict(t=0.78, pel_xz=(0.12, 0.28), pelvis_rot=(30, 3, 0), chest_rot=(20, 3, 0), head_rot=(4, 0, 0), support_flex=28,
             sup_frot=(120, 8, 0), thigh=(-8, -34), ant=V([-0.1, 1, 0.3]), flex=60, frot=(30, 30, 0)),
    ]
    return build_kick(name, rows, meta_extra=dict(target_dir=(0, 0, 1)))


def roundhouse_defective(name="Defective roundhouse: arm-of-leg swing, no hip turn"):
    """Leg swings sideways like a pendulum: no chamber, no pivot, little hip rotation, torso leans forward."""
    rows = [
        dict(t=0.00),
        dict(t=0.22, pel_xz=(0.02, 0.06), pelvis_rot=(-30, 6, 0), chest_rot=(-18, 8, 0), head_rot=(0, 4, 0), support_flex=33,
             sup_frot=(-12, 4, 0), thigh=(-52, -40), ant=V([0, 1, 0.1]), flex=22, frot=(-40, 15, 0)),
        dict(t=0.36, pel_xz=(0.03, 0.10), pelvis_rot=(-20, 10, 0), chest_rot=(-8, 12, 0), head_rot=(0, 6, 0), support_flex=30,
             sup_frot=(-12, 4, 0), thigh=(-18, 14), ant=V([0, 1, 0.1]), flex=14, frot=(-10, 25, -30)),
        dict(t=0.44, pel_xz=(0.04, 0.12), pelvis_rot=(-12, 10, 0), chest_rot=(0, 12, 0), head_rot=(2, 6, 0), support_flex=30,
             sup_frot=(-12, 4, 0), thigh=(18, 26), ant=V([0, 1, 0.1]), flex=10, frot=(15, 25, -45)),
        dict(t=0.60, pel_xz=(0.03, 0.08), pelvis_rot=(-24, 8, 0), chest_rot=(-12, 10, 0), head_rot=(0, 4, 0), support_flex=32,
             sup_frot=(-12, 4, 0), thigh=(-30, -10), ant=V([0, 1, 0.1]), flex=16, frot=(-20, 20, 0)),
        dict(t=0.76, pel_xz=(0.02, 0.06), pelvis_rot=(-32, 4, 0), chest_rot=(-18, 6, 0), head_rot=(0, 2, 0), support_flex=34,
             sup_frot=(-12, 2, 0), thigh=(-40, -45), ant=V([0, 1, 0.1]), flex=20, frot=(-30, 10, 0)),
    ]
    return build_kick(name, rows, meta_extra=dict(target_dir=(0, 0, 1), defective=True))


# ------------------------------------------------------------------ standing poses
def stand(name, pose, support_flex=8, hold=0.5):
    pose["support_flex"] = support_flex
    return render_sequence(name, [pose], [0.0], {"L": "ik", "R": "ik"}, "L", fps=30, meta=dict(kind="pose"), hold_end=hold)


def stand_base(gap=0.12):
    p = Pose()
    p["pelvis"] = (0, 0.95, 0)
    p["arm_local"] = 1
    p["aL_pole"], p["aR_pole"] = (0.4, -1, -0.3), (-0.4, -1, -0.3)
    for s, sg in (("L", 1), ("R", -1)):
        p[f"{s}_ball"] = ball_from_ankle(sg * gap, 0.0, 0)
        p[f"{s}_frot"] = (0, 0, 0)
        p[f"{s}_pole"] = (0, 0, 1)
    p["aL_wrist"], p["aR_wrist"] = (0.20, -0.45, 0.04), (-0.20, -0.45, 0.04)   # arms hanging
    return p


def stand_neutral():
    return stand("Standing: neutral, arms at sides", stand_base())


def stand_banzai():
    p = stand_base(0.12)
    p["head_rot"] = (0, -8, 0)
    p["chest_rot"] = (0, -4, 0)
    p["aL_wrist"], p["aR_wrist"] = (0.27, 0.50, 0.0), (-0.27, 0.50, 0.0)       # both arms up, slightly outward (V)
    p["aL_pole"], p["aR_pole"] = (0.5, 0, -1), (-0.5, 0, -1)
    return stand("Banzai: standing, both arms raised", p)
