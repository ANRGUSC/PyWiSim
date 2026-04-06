"""Generate architecture diagram for PyWiSim."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# --- Colors ---
BG        = "#1e293b"
SLATE_900 = "#0f172a"
SLATE_700 = "#334155"
CYAN      = "#22d3ee"
ORANGE    = "#f97316"
TEXT      = "#e2e8f0"
ARROW_CLR = "#94a3b8"
LABEL_CLR = "#cbd5e1"
WHITE     = "#ffffff"

# --- Figure setup (wider & taller to avoid cramming) ---
fig, ax = plt.subplots(figsize=(7, 8), dpi=150)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, 14)
ax.set_ylim(0, 16)
ax.set_aspect("equal")
ax.axis("off")


def draw_box(x, y, w, h, fill, edge, title, lines, title_size=12, line_size=8.5):
    """Draw a rounded rectangle with a title and detail lines."""
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.2",
        facecolor=fill, edgecolor=edge, linewidth=2,
    )
    ax.add_patch(box)
    # Title
    ax.text(
        x + w / 2, y + h - 0.40, title,
        ha="center", va="center", fontsize=title_size,
        fontweight="bold", color=TEXT, family="sans-serif",
    )
    # Separator line
    sep_y = y + h - 0.75
    ax.plot([x + 0.3, x + w - 0.3], [sep_y, sep_y], color=edge, lw=0.7, alpha=0.5)
    # Detail lines
    for i, line in enumerate(lines):
        ax.text(
            x + w / 2, sep_y - 0.40 - i * 0.38, line,
            ha="center", va="center", fontsize=line_size,
            color=LABEL_CLR, family="monospace",
        )
    return box


def draw_arrow(x1, y1, x2, y2, label, label_offset=(0, 0), bidirectional=False,
               color=ARROW_CLR):
    """Draw a styled arrow with a label."""
    arrowstyle = "<->" if bidirectional else "->"
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=arrowstyle,
        mutation_scale=14,
        lw=1.8,
        color=color,
        connectionstyle="arc3,rad=0",
    )
    ax.add_patch(arrow)
    mx = (x1 + x2) / 2 + label_offset[0]
    my = (y1 + y2) / 2 + label_offset[1]
    ax.text(
        mx, my, label,
        ha="center", va="center", fontsize=8.5,
        color=LABEL_CLR, family="sans-serif",
        fontstyle="italic",
    )


# ============================================================
# Box positions — generous spacing
# ============================================================

box_w = 6.0
cx = 7.0  # center x
left = cx - box_w / 2  # = 4.0

# "Your Protocol" box — outside the dashed bounding box
proto_h = 1.3
proto_y = 14.0
draw_box(left, proto_y, box_w, proto_h,
         SLATE_900, CYAN, "Your Protocol", ["(user code)"], title_size=13, line_size=9)

# --- Dashed bounding box for pywisim internals ---
dash_x, dash_y, dash_w, dash_h = 2.0, 0.8, 10.0, 11.0
dashed_rect = FancyBboxPatch(
    (dash_x, dash_y), dash_w, dash_h,
    boxstyle="round,pad=0.25",
    facecolor="none", edgecolor=WHITE,
    linewidth=1.5, linestyle=(0, (8, 4)),
)
ax.add_patch(dashed_rect)
# Label for the dashed box
ax.text(
    dash_x + dash_w / 2, dash_y + dash_h - 0.35,
    "pywisim.py \u2014 49 lines",
    ha="center", va="center", fontsize=10,
    color=WHITE, family="sans-serif", fontweight="bold",
    bbox=dict(facecolor=BG, edgecolor="none", pad=3),
)

# "Node" box
node_h = 2.5
node_y = 8.0
draw_box(left, node_y, box_w, node_h,
         SLATE_700, CYAN, "Node",
         ["on_receive(msg, sender)", "broadcast(msg)", "unicast(dest, msg)", "schedule(delay, fn)"])

# "WirelessNetwork" box
wn_h = 2.5
wn_y = 4.0
draw_box(left, wn_y, box_w, wn_h,
         SLATE_700, ORANGE, "WirelessNetwork",
         ["add_node(n, x, y)", "neighbors(nid)", "collision avoidance", "packet loss"])

# "EventLoop" box
el_h = 1.6
el_y = 1.2
draw_box(left, el_y, box_w, el_h,
         SLATE_700, CYAN, "EventLoop",
         ["schedule(delay, fn)", "run(until)"])

# ============================================================
# Arrows — labels offset to the right so they don't overlap
# ============================================================

mid_x = cx

# "Your Protocol" -> "Node"  (subclass)
draw_arrow(mid_x, proto_y - 0.05, mid_x, node_y + node_h + 0.05,
           "subclass", label_offset=(1.2, 0))

# "Node" <-> "WirelessNetwork"  (send / deliver)
draw_arrow(mid_x, node_y - 0.05, mid_x, wn_y + wn_h + 0.05,
           "send / deliver", label_offset=(1.3, 0), bidirectional=True)

# "WirelessNetwork" -> "EventLoop"  (schedules events)
draw_arrow(mid_x, wn_y - 0.05, mid_x, el_y + el_h + 0.05,
           "schedules events", label_offset=(1.4, 0))

# ============================================================
# Save
# ============================================================
fig.savefig("architecture.png", dpi=150, bbox_inches="tight",
            facecolor=fig.get_facecolor(), edgecolor="none")
plt.close(fig)
print("Saved architecture.png")
