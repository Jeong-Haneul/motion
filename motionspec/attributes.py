"""Attribute extraction: turns a Motion (joint trajectories) into named, unit-bearing scalar attributes.

Every attribute here is a deterministic function of the joints, expressed in a body-relative or
target-relative frame so that a spec can be written once and applied to any body size and either handedness.
"""
from __future__ import annotations

import numpy as np

from .render import com as com_of
from .skeleton import HIP_W, I, SHOULDER_W, Motion, unit

UP = np.array([0.0, 1.0, 0.0])
DEG = 180.0 / np.pi


def _ang(a, b):
    a, b = unit(a), unit(b)
    return float(np.degrees(np.arccos(np.clip(a @ b, -1, 1))))


def _hfacing(L, R):
    """Horizontal forward direction of a left-right pair (hips or shoulders)."""
    lat = L - R
    f = np.cross(lat, UP)
    f[..., 1] = 0
    n = np.linalg.norm(f, axis=-1, keepdims=True)
    return f / np.maximum(n, 1e-9)


def _yaw(f):
    return np.degrees(np.unwrap(np.arctan2(f[:, 0], f[:, 2])))


def _flex(a, b, c):
    """Interior-angle-based flexion: 0 = straight, larger = more bent."""
    u, v = a - b, c - b
    cs = np.sum(u * v, -1) / (np.linalg.norm(u, axis=-1) * np.linalg.norm(v, axis=-1) + 1e-9)
    return 180.0 - np.degrees(np.arccos(np.clip(cs, -1, 1)))


def series(m: Motion) -> dict:
    """Per-frame feature series used by the extractor and by the sheet renderer."""
    j = m.j
    S = {}
    pf = _hfacing(j("l_hip"), j("r_hip"))
    cf = _hfacing(j("l_shoulder"), j("r_shoulder"))
    S["pelvis_fwd"], S["chest_fwd"] = pf, cf
    S["pelvis_yaw"], S["chest_yaw"] = _yaw(pf), _yaw(cf)
    S["torso_twist"] = S["chest_yaw"] - S["pelvis_yaw"]
    trunk = j("neck") - j("pelvis")
    left = np.cross(UP, pf)  # pelvis-left (horizontal)
    S["trunk_pitch"] = np.degrees(np.arctan2(np.sum(trunk * pf, -1), trunk[:, 1]))          # + forward
    S["trunk_lean_left"] = np.degrees(np.arctan2(np.sum(trunk * left, -1), trunk[:, 1]))    # + toward pelvis-left
    S["trunk_tilt"] = np.degrees(np.arccos(np.clip(trunk[:, 1] / np.linalg.norm(trunk, axis=-1), -1, 1)))
    for s, pre in (("L", "l_"), ("R", "r_")):
        S[f"knee_flex_{s}"] = _flex(j(pre + "hip"), j(pre + "knee"), j(pre + "ankle"))
        S[f"elbow_flex_{s}"] = _flex(j(pre + "shoulder"), j(pre + "elbow"), j(pre + "wrist"))
        th = j(pre + "knee") - j(pre + "hip")
        S[f"thigh_elev_{s}"] = np.degrees(np.arcsin(np.clip(th[:, 1] / np.linalg.norm(th, axis=-1), -1, 1)))
        S[f"ankle_y_{s}"] = j(pre + "ankle")[:, 1]
        S[f"ankle_speed_{s}"] = np.linalg.norm(np.gradient(j(pre + "ankle"), 1 / m.fps, axis=0), axis=1)
        fi = 0 if s == "L" else 1
        S[f"foot_yaw_{s}"] = np.degrees(np.unwrap(np.arctan2(m.foot_fd[:, fi, 0], m.foot_fd[:, fi, 2])))
    S["com"] = np.array([com_of(x) for x in m.X])
    return S


def _contacts(m, thr=0.025):
    low = {}
    for s, pre in (("L", "l_"), ("R", "r_")):
        low[s] = np.minimum(m.j(pre + "toe")[:, 1], m.j(pre + "heel")[:, 1]) < thr
    return low


def _seg_dist(p, a, b):
    ab = b - a
    t = np.clip(np.sum((p - a) * ab, -1) / (np.sum(ab * ab, -1) + 1e-9), 0, 1)
    return np.linalg.norm(p - (a + ab * t[..., None]), axis=-1)


def static_attrs(m: Motion, sl=None) -> dict:
    """Pose attributes averaged over the given frames (default: all)."""
    sl = slice(None) if sl is None else sl
    j = lambda n: m.j(n)[sl]
    S = series(m)
    A = {}
    thigh = np.linalg.norm(j("l_knee") - j("l_hip"), axis=-1).mean()
    legl = thigh + np.linalg.norm(j("l_knee") - j("l_ankle"), axis=-1).mean() + 0.08 * thigh / 0.44
    hipw = np.linalg.norm(j("l_hip") - j("r_hip"), axis=-1).mean()
    shw = np.linalg.norm(j("l_shoulder") - j("r_shoulder"), axis=-1).mean()
    A["scale.hip_width_m"] = float(hipw)
    A["pose.knee_gap_ratio"] = float((np.linalg.norm(j("l_knee") - j("r_knee"), axis=-1) / hipw).mean())
    A["pose.ankle_gap_ratio"] = float((np.linalg.norm(j("l_ankle") - j("r_ankle"), axis=-1) / hipw).mean())
    pf = S["pelvis_fwd"][sl].mean(0)
    pf = unit(pf)
    left = np.cross(UP, pf)
    hm = 0.5 * (j("l_hip") + j("r_hip")).mean(0)
    # signed lateral offsets (+ = toward the pelvis-left side)
    kmid = 0.5 * (j("l_knee") + j("r_knee")).mean(0)
    amid = 0.5 * (j("l_ankle") + j("r_ankle")).mean(0)
    A["pose.knees_lateral_shift_deg"] = float(np.degrees(np.arctan2((kmid - hm) @ left, max((kmid - hm) @ pf, 1e-3))))
    A["pose.ankles_lateral_offset_ratio"] = float(((amid - hm) @ left) / legl)
    A["pose.legs_slant_abs_ratio"] = abs(A["pose.ankles_lateral_offset_ratio"])
    A["pose.knee_flex_mean_deg"] = float(0.5 * (S["knee_flex_L"][sl] + S["knee_flex_R"][sl]).mean())
    A["pose.knee_flex_diff_deg"] = float(abs(S["knee_flex_L"][sl] - S["knee_flex_R"][sl]).mean())
    kl = (j("l_knee") - j("r_knee")).mean(0)
    al = (j("l_ankle") - j("r_ankle")).mean(0)
    hl = (j("l_hip") - j("r_hip")).mean(0)
    A["pose.knee_cross_depth_ratio"] = float(-(kl @ hl) / (hl @ hl) * 1.0)         # >0: knees have swapped sides
    A["pose.ankle_cross_depth_ratio"] = float(-(al @ hl) / (hl @ hl))
    A["pose.knee_height_diff_m"] = float(abs((j("l_knee") - j("r_knee"))[:, 1]).mean())
    A["pose.foot_lift_m"] = float(max(np.minimum(j("l_toe")[:, 1], j("l_heel")[:, 1]).mean(), np.minimum(j("r_toe")[:, 1], j("r_heel")[:, 1]).mean()))
    A["pose.trunk_pitch_deg"] = float(S["trunk_pitch"][sl].mean())
    A["pose.trunk_lean_lateral_deg"] = float(abs(S["trunk_lean_left"][sl]).mean())
    lum = (j("spine") - j("pelvis")).mean(0)
    tho = (j("chest") - j("spine")).mean(0)
    A["pose.lumbar_pitch_deg"] = float(np.degrees(np.arctan2(lum @ pf, lum[1])))
    A["pose.thoracic_pitch_deg"] = float(np.degrees(np.arctan2(tho @ pf, tho[1])))
    A["pose.spine_curl_deg"] = A["pose.thoracic_pitch_deg"] - A["pose.lumbar_pitch_deg"]
    head = (j("head") - j("neck")).mean(0)
    A["pose.head_pitch_deg"] = float(np.degrees(np.arctan2(head @ pf, head[1])))
    hroll = (j("head") - j("neck")).mean(0) @ left
    A["pose.head_roll_deg"] = float(abs(np.degrees(np.arctan2(hroll, head[1]))))
    # hands relative to thighs
    d = []
    for pre in ("l_", "r_"):
        for post in ("l_", "r_"):
            d.append(_seg_dist(j(pre + "wrist"), j(post + "hip"), j(post + "knee")))
    d = np.array(d).reshape(2, 2, -1).min(axis=1).mean(axis=1)  # per hand: min over both thighs
    A["pose.hand_thigh_dist_ratio"] = float(d.max() / thigh)
    wh = 0.5 * (j("l_wrist") + j("r_wrist")).mean(0)
    A["pose.hands_height_ratio"] = float(wh[1] / (j("head_top")[:, 1].mean() + 1e-9))
    pts = np.concatenate([j(n) for n in ("l_knee", "r_knee", "l_ankle", "r_ankle", "l_wrist", "r_wrist", "l_toe", "r_toe")])
    A["pose.lateral_extent_ratio"] = float(((pts @ left).max() - (pts @ left).min()) / shw)
    A["pose.hands_gap_ratio"] = float(np.linalg.norm(j("l_wrist") - j("r_wrist"), axis=-1).mean() / shw)
    A["pose.pelvis_height_ratio"] = float(j("pelvis")[:, 1].mean() / legl)
    # base of support margin (COM projected to the floor vs support polygon)
    A["pose.com_to_base_m"] = _com_base_dist(m, sl)
    return A


def _com_base_dist(m, sl=None):
    from .render import hull2d
    sl = slice(None) if sl is None else sl
    S = series(m)
    d = []
    idx = np.arange(m.T)[sl]
    for i in idx[:: max(1, len(idx) // 20)]:
        X = m.X[i]
        pts = [X[I[n]][[0, 2]] for n in ("l_toe", "l_heel", "r_toe", "r_heel") if X[I[n]][1] < 0.025]
        ch = m.meta.get("chair")
        if ch and X[I["pelvis"]][1] < ch["seat_h"] + 0.3:
            for sx in (-1, 1):
                for sz in (-1, 1):
                    pts.append(np.array([ch["x"] + sx * ch["w"] / 2, ch["z"] + sz * ch["d"] / 2]))
        c = S["com"][i][[0, 2]]
        if len(pts) == 0:
            d.append(9.9)
        else:
            d.append(_dist_to_hull(c, np.array(pts)))
    return float(np.max(d))


def _dist_to_hull(c, pts):
    from .render import hull2d
    h = hull2d(pts) if len(pts) >= 3 else pts
    if len(h) >= 3:
        inside = True
        for k in range(len(h)):
            a, b = h[k], h[(k + 1) % len(h)]
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < -1e-9:
                inside = False
                break
        if inside:
            return 0.0
    best = 9.9
    seg = list(zip(h, np.roll(h, -1, axis=0))) if len(h) >= 2 else [(h[0], h[0])]
    for a, b in seg:
        ab = b - a
        t = np.clip(((c - a) @ ab) / (ab @ ab + 1e-12), 0, 1)
        best = min(best, float(np.linalg.norm(c - (a + ab * t))))
    return best


def events(m: Motion, S=None):
    """Detect kick phases. Returns dict of frame indices or None when no kick-like lift is present."""
    S = S or series(m)
    peak = {s: S[f"ankle_y_{s}"].max() for s in "LR"}
    side = "L" if peak["L"] > peak["R"] else "R"
    y, v = S[f"ankle_y_{side}"], S[f"ankle_speed_{side}"]
    lift = np.where(y > 0.18)[0]
    if len(lift) == 0:
        return None
    s0 = int(lift[0])
    imp = int(s0 + np.argmax(v[s0:]))
    kf = S[f"knee_flex_{side}"]
    ch = int(s0 + np.argmax(kf[s0:imp + 1])) if imp > s0 else s0
    after = np.where(y[imp:] < 0.2)[0]
    end = int(imp + after[0]) if len(after) else m.T - 1
    return dict(side=side, lift=s0, chamber=ch, impact=imp, end=end)


def _kendall(order_times):
    """Kendall tau between the expected proximal->distal order (index) and observed peak-time order."""
    n = len(order_times)
    c = d = 0
    for a in range(n):
        for b in range(a + 1, n):
            dt = order_times[b] - order_times[a]
            if dt > 0:
                c += 1
            elif dt < 0:
                d += 1
    return (c - d) / (n * (n - 1) / 2)


def dynamic_attrs(m: Motion, E=None) -> dict:
    S = series(m)
    E = E or events(m, S)
    A = {}
    if E is None:
        A["kick.present"] = 0.0
        return A
    side, s0, ch, imp, end = E["side"], E["lift"], E["chamber"], E["impact"], E["end"]
    pre = "l_" if side == "L" else "r_"
    sup = "R" if side == "L" else "L"
    j = lambda n: m.j(n)
    tdir = np.array(m.meta.get("target_dir", (0, 0, 1)), float)
    thigh = np.linalg.norm(j(pre + "knee")[0] - j(pre + "hip")[0])
    A["kick.present"] = 1.0
    A["kick.side"] = side
    A["kick.duration_s"] = float((end - s0) / m.fps)
    A["kick.extension_duration_s"] = float((imp - ch) / m.fps)
    A["kick.peak_ankle_speed_ms"] = float(S[f"ankle_speed_{side}"].max())
    A["kick.peak_ankle_speed_norm"] = float(S[f"ankle_speed_{side}"].max() / (thigh / 0.44))
    A["chamber.knee_flex_deg"] = float(S[f"knee_flex_{side}"][ch])
    A["chamber.thigh_elev_deg"] = float(S[f"thigh_elev_{side}"][ch])
    A["impact.knee_flex_deg"] = float(S[f"knee_flex_{side}"][imp])
    A["impact.knee_flex_min_deg"] = float(S[f"knee_flex_{side}"][ch:end + 1].min())
    body_h = float(j("head_top")[0, 1])
    A["impact.ankle_height_ratio"] = float(j(pre + "ankle")[imp, 1] / body_h)
    hip, ank = j(pre + "hip")[imp], j(pre + "ankle")[imp]
    leg = ank - hip
    leg_h = leg * np.array([1, 0, 1])
    pf = S["pelvis_fwd"][imp]
    A["impact.leg_vs_pelvis_deg"] = _ang(leg_h, pf)
    vel = np.gradient(j(pre + "ankle"), 1 / m.fps, axis=0)[imp]
    A["impact.strike_vs_limb_deg"] = _ang(vel, leg)
    A["impact.strike_vs_target_deg"] = _ang(vel * np.array([1, 0, 1]), tdir)
    fd, sd = m.foot_fd[imp, 0 if side == "L" else 1], m.foot_sd[imp, 0 if side == "L" else 1]
    ld = np.cross(fd, sd)
    outer = ld if side == "L" else -ld
    cand = {"sole": sd, "instep": -sd, "outer_edge": outer, "inner_edge": -outer, "heel": -fd, "toe": fd}
    vu = unit(vel)
    sc = {k: float(vu @ unit(vv)) for k, vv in cand.items()}
    A["impact.leading_surface"] = max(sc, key=sc.get)
    for k, vv in sc.items():
        A[f"impact.lead_{k}_cos"] = vv
    trunk = (j("neck") - j("pelvis"))[imp]
    away = -tdir
    A["impact.trunk_lean_away_deg"] = float(np.degrees(np.arctan2(trunk @ away, trunk[1])))
    A["impact.trunk_tilt_deg"] = float(S["trunk_tilt"][imp])
    A["impact.pelvis_yaw_vs_target_deg"] = float(abs(_ang(pf * np.array([1, 0, 1]), tdir)))
    A["impact.pelvis_faces_target_cos"] = float(unit(pf) @ tdir)
    lo, hi = max(0, s0 - int(0.25 * m.fps)), end
    A["motion.pelvis_yaw_range_deg"] = float(np.ptp(S["pelvis_yaw"][lo:hi + 1]))
    A["motion.support_pivot_deg"] = float(np.ptp(S[f"foot_yaw_{sup}"][lo:hi + 1]))
    A["motion.torso_twist_max_deg"] = float(np.abs(S["torso_twist"][lo:hi + 1]).max())
    A["motion.support_knee_flex_mean_deg"] = float(S[f"knee_flex_{sup}"][s0:end + 1].mean())
    ext = j(pre + "ankle")[ch:imp + 1]
    seg = np.linalg.norm(np.diff(ext, axis=0), axis=1).sum()
    A["path.straightness"] = float(np.linalg.norm(ext[-1] - ext[0]) / max(seg, 1e-9))
    # proximal -> distal sequencing: pelvis yaw rate, thigh, shank, foot
    rng = slice(lo, end + 1)
    pr = np.abs(np.gradient(S["pelvis_yaw"], 1 / m.fps))
    th = np.linalg.norm(np.gradient(unit_rows(j(pre + "knee") - j(pre + "hip")), 1 / m.fps, axis=0), axis=1)
    sh = np.linalg.norm(np.gradient(unit_rows(j(pre + "ankle") - j(pre + "knee")), 1 / m.fps, axis=0), axis=1)
    ft = S[f"ankle_speed_{side}"]
    ts = [int(lo + np.argmax(x[rng])) for x in (pr, th, sh, ft)]
    A["motion.pd_order_tau"] = float(_kendall(ts))
    A["motion.pd_lag_pelvis_to_foot_s"] = float((ts[3] - ts[0]) / m.fps)
    retr = S[f"knee_flex_{side}"][imp:end + 1]
    A["retract.knee_flex_deg"] = float(retr.max()) if len(retr) else 0.0
    A["retract.recoil_deg"] = float(retr.max() - S[f"knee_flex_{side}"][imp]) if len(retr) else 0.0
    return A


def unit_rows(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)


def extract(m: Motion) -> dict:
    """All attributes for a motion or a held pose."""
    A = {}
    if m.meta.get("kind") == "motion":
        E = events(m)
        A.update(dynamic_attrs(m, E))
        if E:
            s = slice(0, 1)
            st = static_attrs(m, s)
            A.update({k.replace("pose.", "stance0."): v for k, v in st.items() if k.startswith("pose.")})
    else:
        A.update(static_attrs(m))
        A["kick.present"] = 0.0
    return A


def realism(m: Motion) -> dict:
    """Class-agnostic validity metrics (E0)."""
    R = {}
    allp = np.concatenate([m.X.reshape(-1, 3)])
    R["penetration_m"] = float(max(0.0, -allp[:, 1].min()))
    c = _contacts(m)
    hv = {}
    skate = []
    for s, pre in (("L", "l_"), ("R", "r_")):
        pts = np.stack([m.j(pre + "toe"), m.j(pre + "heel")], axis=1)
        low = pts[np.arange(m.T), np.argmin(pts[:, :, 1], axis=1)]
        sp = np.linalg.norm(np.gradient(low[:, [0, 2]], 1 / m.fps, axis=0), axis=1)
        mask = c[s]
        if mask.sum():
            skate.append(((sp > 0.10) & mask).sum() / mask.sum())
    R["foot_skating_ratio"] = float(max(skate) if skate else 0.0)
    ch = m.meta.get("chair")
    sup = c["L"] | c["R"]
    if ch:
        sup = sup | (m.j("pelvis")[:, 1] < ch["seat_h"] + 0.3)
    R["unsupported_frame_ratio"] = float(1.0 - sup.mean())
    S = series(m)
    R["knee_hyperext_deg"] = float(max(0.0, -min(S["knee_flex_L"].min(), S["knee_flex_R"].min())))
    R["knee_flex_max_deg"] = float(max(S["knee_flex_L"].max(), S["knee_flex_R"].max()))
    acc = np.linalg.norm(np.gradient(np.gradient(m.X, 1 / m.fps, axis=0), 1 / m.fps, axis=0), axis=2)
    R["max_joint_accel_ms2"] = float(acc.max())
    bone = lambda a, b: np.linalg.norm(m.j(a) - m.j(b), axis=1)
    R["bone_length_cv"] = float(np.mean([bone(a, b).std() / bone(a, b).mean() for a, b in (("l_hip", "l_knee"), ("l_knee", "l_ankle"), ("r_hip", "r_knee"), ("r_knee", "r_ankle"), ("l_shoulder", "l_elbow"), ("r_shoulder", "r_elbow"))]))
    R["com_to_base_max_m"] = _com_base_dist(m)
    return R
