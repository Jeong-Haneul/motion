"""Evaluation-sheet renderer: orthographic multi-view stick figures with contact, COM, support polygon,
trajectories, furniture and target markers. Labels are English because the bundled fonts lack Hangul."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle, Polygon

from .skeleton import I, Motion, unit

C_L, C_R, C_T = "#d9731a", "#1f66c9", "#3a3f47"
VIEWS = {
    "side": dict(eye=(-1, 0, 0), up=(0, 1, 0), title="SIDE (viewer at character's right, forward = right)"),
    "front": dict(eye=(0, 0, 1), up=(0, 1, 0), title="FRONT (viewer faces character)"),
    "top": dict(eye=(0, 1, 0), up=(0, 0, 1), title="TOP (forward = up)"),
    "oblique": dict(eye=(-0.62, 0.32, 0.72), up=(0, 1, 0), title="3/4 VIEW (front-right)"),
}
SEGS = [
    ("pelvis", "spine", C_T), ("spine", "chest", C_T), ("chest", "neck", C_T), ("neck", "head", C_T),
    ("l_shoulder", "r_shoulder", C_T), ("neck", "l_shoulder", C_T), ("neck", "r_shoulder", C_T),
    ("l_hip", "r_hip", C_T), ("pelvis", "l_hip", C_T), ("pelvis", "r_hip", C_T),
    ("l_shoulder", "l_elbow", C_L), ("l_elbow", "l_wrist", C_L), ("l_wrist", "l_hand", C_L),
    ("r_shoulder", "r_elbow", C_R), ("r_elbow", "r_wrist", C_R), ("r_wrist", "r_hand", C_R),
    ("l_hip", "l_knee", C_L), ("l_knee", "l_ankle", C_L), ("r_hip", "r_knee", C_R), ("r_knee", "r_ankle", C_R),
    ("l_ankle", "l_toe", C_L), ("l_ankle", "l_heel", C_L), ("l_heel", "l_toe", C_L),
    ("r_ankle", "r_toe", C_R), ("r_ankle", "r_heel", C_R), ("r_heel", "r_toe", C_R),
]
MASS = {  # segment mass fractions (approximate, Dempster-style), midpoint-based COM
    ("pelvis", "chest"): 0.34, ("chest", "neck"): 0.16, ("neck", "head"): 0.08,
    ("l_shoulder", "l_elbow"): 0.027, ("l_elbow", "l_wrist"): 0.016, ("l_wrist", "l_hand"): 0.006,
    ("r_shoulder", "r_elbow"): 0.027, ("r_elbow", "r_wrist"): 0.016, ("r_wrist", "r_hand"): 0.006,
    ("l_hip", "l_knee"): 0.10, ("l_knee", "l_ankle"): 0.0465, ("l_ankle", "l_toe"): 0.0145,
    ("r_hip", "r_knee"): 0.10, ("r_knee", "r_ankle"): 0.0465, ("r_ankle", "r_toe"): 0.0145,
}


def basis(view):
    v = VIEWS[view]
    eye, up = unit(np.array(v["eye"], float)), np.array(v["up"], float)
    f = -eye
    right = unit(np.cross(f, up))
    upv = np.cross(right, f)
    return right, upv, eye


def proj(P, view):
    right, upv, eye = basis(view)
    P = np.atleast_2d(P)
    return np.stack([P @ right, P @ upv], axis=1), P @ eye


def com(X):
    tot, acc = 0.0, np.zeros(3)
    for (a, b), m in MASS.items():
        acc += m * 0.5 * (X[I[a]] + X[I[b]])
        tot += m
    return acc / tot


def contact_points(X, thr=0.025):
    pts = []
    for n in ("l_toe", "l_heel", "r_toe", "r_heel"):
        if X[I[n]][1] < thr:
            pts.append(X[I[n]])
    return np.array(pts)


def hull2d(P):
    P = sorted(map(tuple, P))
    if len(P) < 3:
        return np.array(P)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lo, up = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return np.array(lo[:-1] + up[:-1])


def box_edges(c, size):
    cx, cy, cz = c
    sx, sy, sz = (s / 2 for s in size)
    v = np.array([[cx + dx, cy + dy, cz + dz] for dx in (-sx, sx) for dy in (-sy, sy) for dz in (-sz, sz)])
    e = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
    return v, e


def draw_env(ax, view, meta):
    segs = []
    if "chair" in meta:
        ch = meta["chair"]
        cx, cz, sh = ch["x"], ch["z"], ch["seat_h"]
        v, e = box_edges((cx, sh - 0.02, cz), (ch["w"], 0.04, ch["d"]))
        segs += [(v[a], v[b]) for a, b in e]
        for sx in (-1, 1):
            for sz in (-1, 1):
                segs.append((np.array([cx + sx * ch["w"] / 2.2, 0, cz + sz * ch["d"] / 2.2]),
                             np.array([cx + sx * ch["w"] / 2.2, sh - 0.04, cz + sz * ch["d"] / 2.2])))
        zb = cz - ch["d"] / 2
        for dx in (-1, 1):
            segs.append((np.array([cx + dx * ch["w"] / 2, sh, zb]), np.array([cx + dx * ch["w"] / 2, sh + 0.45, zb])))
        segs.append((np.array([cx - ch["w"] / 2, sh + 0.45, zb]), np.array([cx + ch["w"] / 2, sh + 0.45, zb])))
    for a, b in segs:
        pa, _ = proj(a, view)
        pb, _ = proj(b, view)
        ax.plot([pa[0][0], pb[0][0]], [pa[0][1], pb[0][1]], color="#9aa3ad", lw=1.3, zorder=1)
    if "target" in meta:
        pc, _ = proj(np.array(meta["target"]), view)
        ax.add_patch(Circle(pc[0], meta.get("target_r", 0.13), fc="#e8b4b4", ec="#b05050", lw=1.2, alpha=0.75, zorder=1))
        ax.text(pc[0][0], pc[0][1], "T", ha="center", va="center", fontsize=8, color="#7a2d2d", zorder=2)


def draw_floor(ax, view, ext):
    if view in ("side", "front", "oblique"):
        if view == "oblique":
            g = np.array([[x, 0, z] for x in (-1.5, 1.5) for z in (-1.5, 1.5)])
            for x in np.linspace(-1.5, 1.5, 7):
                a, _ = proj(np.array([x, 0, -1.5]), view)
                b, _ = proj(np.array([x, 0, 1.5]), view)
                ax.plot([a[0][0], b[0][0]], [a[0][1], b[0][1]], color="#dfe3e8", lw=0.8, zorder=0)
            for z in np.linspace(-1.5, 1.5, 7):
                a, _ = proj(np.array([-1.5, 0, z]), view)
                b, _ = proj(np.array([1.5, 0, z]), view)
                ax.plot([a[0][0], b[0][0]], [a[0][1], b[0][1]], color="#dfe3e8", lw=0.8, zorder=0)
        else:
            ax.axhline(0, color="#6b7480", lw=1.4, zorder=0)
            ax.axhspan(-0.2, 0, color="#eef0f3", zorder=0)
    else:
        for g in np.arange(np.floor(ext[0] * 2) / 2, ext[1] + 0.01, 0.5):
            ax.axvline(g, color="#e4e7eb", lw=0.8, zorder=0)
        for g in np.arange(np.floor(ext[2] * 2) / 2, ext[3] + 0.01, 0.5):
            ax.axhline(g, color="#e4e7eb", lw=0.8, zorder=0)


def draw_figure(ax, X, fd, sd, head_fd, view, alpha=1.0, lw=4.2, show_com=True, label_sides=False, zbase=3):
    P2, dep = proj(X, view)
    order = sorted(range(len(SEGS)), key=lambda k: (dep[I[SEGS[k][0]]] + dep[I[SEGS[k][1]]]))
    dmin, dmax = dep.min(), dep.max()
    top = view == "top"
    for z, k in enumerate(order):
        a, b, col = SEGS[k]
        d = 0.5 * (dep[I[a]] + dep[I[b]])
        t = 0.0 if dmax - dmin < 1e-6 else (d - dmin) / (dmax - dmin)
        pa, pb = P2[I[a]], P2[I[b]]
        is_arm = a[2:] in ("_shoulder", "_elbow", "_wrist") and b[2:] in ("_elbow", "_wrist", "_hand")
        is_leg_or_foot = a[2:] in ("_hip", "_knee", "_ankle", "_heel") and b[2:] in ("_knee", "_ankle", "_toe", "_heel")
        w = lw * (0.75 + 0.5 * t) * (0.62 if is_arm else 1.0)
        al = alpha * (0.55 + 0.45 * t)
        if top and not is_leg_or_foot:
            al *= 0.5
        ax.plot([pa[0], pb[0]], [pa[1], pb[1]], color=col, lw=w, alpha=al, solid_capstyle="round", zorder=zbase + z * 0.01,
                ls=(0, (3, 1.5)) if (top and is_arm) else "-")
    for n in ("pelvis", "spine", "chest", "l_elbow", "r_elbow", "l_knee", "r_knee", "l_ankle", "r_ankle"):
        ax.plot(*P2[I[n]], "o", ms=3.4, mfc="white", mec="#222", mew=0.8, alpha=alpha * (0.5 if top and n in ("pelvis", "spine", "chest") else 1), zorder=zbase + 1)
    for n in ("l_wrist", "r_wrist"):
        ax.plot(*P2[I[n]], "D", ms=3.6, mfc="#fff4d6", mec="#222", mew=0.8, alpha=alpha, zorder=zbase + 1)
    hc = P2[I["head"]]
    ax.add_patch(Circle(hc, 0.105, fc=(1, 1, 1, 0.55 if top else 1.0), ec="#555" if top else "#222", lw=1.2, alpha=alpha, zorder=zbase + 0.5))
    nose, _ = proj(X[I["head"]] + 0.105 * head_fd, view)
    ax.plot([hc[0], nose[0][0]], [hc[1], nose[0][1]], color="#c0392b", lw=2.0, alpha=alpha, zorder=zbase + 0.6)
    if top:
        for (ja, jb, c0, c1, lab, ln) in (("l_hip", "r_hip", "pelvis", None, "P", 0.34), ("l_shoulder", "r_shoulder", "neck", None, "S", 0.28)):
            lat = X[I[ja]] - X[I[jb]]
            f = np.cross(lat, [0, 1, 0])
            f[1] = 0
            f = unit(f)
            o = 0.5 * (X[I[ja]] + X[I[jb]])
            p0, _ = proj(o, "top")
            p1, _ = proj(o + ln * f, "top")
            ax.annotate("", xy=p1[0], xytext=p0[0], arrowprops=dict(arrowstyle="-|>", color="#111" if lab == "P" else "#7b8794", lw=1.6, mutation_scale=9), zorder=zbase + 3)
            ax.text(p1[0][0], p1[0][1], lab, fontsize=7, ha="center", va="bottom", color="#111" if lab == "P" else "#5b6672", zorder=zbase + 3)
    if show_com:
        c = com(X)
        pc, _ = proj(c, view)
        ax.plot(*pc[0], "P", ms=8, mfc="#2ca25f", mec="white", mew=0.8, zorder=zbase + 2, alpha=alpha)
        if view != "top":
            pg, _ = proj(np.array([c[0], 0, c[2]]), view)
            ax.plot([pc[0][0], pg[0][0]], [pc[0][1], pg[0][1]], ":", color="#2ca25f", lw=1.0, zorder=zbase)
    cp = contact_points(X)
    for q in cp:
        pq, _ = proj(q, view)
        ax.plot(*pq[0], "s", ms=4, color="#111", zorder=zbase + 2, alpha=alpha)
    if view == "top" and len(cp) >= 2:
        h = hull2d(cp[:, [0, 2]])
        # project hull (x,z) to the view's 2D coords
        hp, _ = proj(np.array([[p[0], 0, p[1]] for p in h]), "top")
        ax.add_patch(Polygon(hp, closed=True, fc="#2ca25f", ec="#2ca25f", alpha=0.16, lw=1.0, zorder=0.5))


def extent(motions_X, view, pad=0.18):
    allp = np.concatenate([proj(X.reshape(-1, 3), view)[0] for X in motions_X])
    lo, hi = allp.min(0), allp.max(0)
    return lo[0] - pad, hi[0] + pad, min(lo[1] - pad, -0.12) if view != "top" else lo[1] - pad, hi[1] + pad


def style_ax(ax, ext, view, title=None):
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#c8cdd3")
    if title:
        ax.set_title(title, fontsize=9.5, pad=3)


def draw_trace(ax, P3, view, colors=None, lw=1.6, alpha=0.9, mark=None):
    p2, _ = proj(P3, view)
    segs = np.stack([p2[:-1], p2[1:]], axis=1)
    lc = LineCollection(segs, colors=colors if colors is not None else "#7a3db8", linewidths=lw, alpha=alpha, zorder=2.5)
    ax.add_collection(lc)
    if mark is not None:
        for i, c in mark:
            ax.plot(*p2[i], "o", ms=3.2, color=c, zorder=2.6)


def keyframe_sheet(m: Motion, key_idx, key_labels, path, views=("side", "front", "top"), trace="r_ankle", note=None,
                   trace_color_by_speed=True, col_w=2.35):
    n = len(key_idx)
    fig, axs = plt.subplots(len(views), n, figsize=(col_w * n, 2.55 * len(views) + 0.8), squeeze=False)
    exts = {v: extent([m.X], v) for v in views}
    sp = np.linalg.norm(np.gradient(m.j(trace), 1 / m.fps, axis=0), axis=1)
    cols = plt.cm.plasma(np.clip(sp / max(sp.max(), 1e-6), 0, 1)) if trace_color_by_speed else None
    for r, v in enumerate(views):
        for c, (fi, lab) in enumerate(zip(key_idx, key_labels)):
            ax = axs[r][c]
            draw_floor(ax, v, exts[v])
            draw_env(ax, v, m.meta)
            if trace:
                draw_trace(ax, m.j(trace), v, colors=cols[:-1] if cols is not None else None, lw=1.4, alpha=0.8,
                           mark=[(fi, "#000")])
            draw_figure(ax, m.X[fi], m.foot_fd[fi], m.foot_sd[fi], m.head_fd[fi], v)
            style_ax(ax, exts[v], v, title=f"{lab}\nt={m.t[fi]:.2f}s" if r == 0 else None)
            if c == 0:
                ax.set_ylabel(VIEWS[v]["title"].split(" (")[0], fontsize=9)
    fig.suptitle(m.name + (f"   |   {note}" if note else ""), fontsize=12, y=0.995)
    fig.text(0.005, 0.003, "orange = character LEFT, blue = RIGHT | red tick = head facing | green + = COM (dotted drop line) | black squares = floor contact | "
             "green area (top view) = support polygon | top-view arrows: P = pelvis facing, S = shoulder-line facing | trail = ankle speed (dark slow, yellow fast) | T = target pad",
             fontsize=7.5, color="#555")
    fig.tight_layout(rect=(0, 0.015, 1, 0.97))
    fig.savefig(path, dpi=140, facecolor="white")
    plt.close(fig)


def pose_sheet(m: Motion, path, views=("front", "side", "top", "oblique"), table=None, note=None):
    fi = m.T // 2
    fig = plt.figure(figsize=(4 * 2.4 + (3.2 if table else 0), 3.6))
    ncol = len(views) + (1 if table else 0)
    gs = fig.add_gridspec(1, ncol, width_ratios=[1] * len(views) + ([1.25] if table else []))
    for c, v in enumerate(views):
        ax = fig.add_subplot(gs[0, c])
        ext = extent([m.X], v)
        draw_floor(ax, v, ext)
        draw_env(ax, v, m.meta)
        draw_figure(ax, m.X[fi], m.foot_fd[fi], m.foot_sd[fi], m.head_fd[fi], v)
        style_ax(ax, ext, v, title=VIEWS[v]["title"].split(" (")[0])
    if table:
        ax = fig.add_subplot(gs[0, -1])
        ax.axis("off")
        ax.text(0, 1, "\n".join(table), va="top", family="monospace", fontsize=7.4)
    fig.suptitle(m.name + (f"   |   {note}" if note else ""), fontsize=11, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=140, facecolor="white")
    plt.close(fig)
