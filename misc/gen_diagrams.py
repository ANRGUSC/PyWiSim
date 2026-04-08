"""Generate mobility_architecture.png and encounter_architecture.png."""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── style matching architecture.png ──
BG     = '#1e293b'
CYAN   = '#22d3ee'
ORANGE = '#f97316'
GREEN  = '#4ade80'
FILL   = '#2a3a50'
TEXT   = '#e2e8f0'
LABEL  = '#94a3b8'
DASH_C = '#64748b'

def rounded_box(ax, cx, cy, w, h, color=CYAN, title='', sub=''):
    box = mpatches.FancyBboxPatch(
        (cx - w/2, cy - h/2), w, h,
        boxstyle="round,pad=0.12", facecolor=FILL, edgecolor=color, linewidth=2.5)
    ax.add_patch(box)
    if title and sub:
        ax.text(cx, cy + h*0.18, title, ha='center', va='center',
                fontsize=13, fontweight='bold', color=TEXT, family='sans-serif')
        ax.text(cx, cy - h*0.20, sub, ha='center', va='center',
                fontsize=8, color=LABEL, family='monospace', linespacing=1.5)
    elif title:
        ax.text(cx, cy, title, ha='center', va='center',
                fontsize=13, fontweight='bold', color=TEXT, family='sans-serif')

def varrow(ax, x, y1, y2, label=''):
    ax.annotate('', xy=(x, y2), xytext=(x, y1),
                arrowprops=dict(arrowstyle='->', color=LABEL, lw=1.5))
    if label:
        ax.text(x + 0.12, (y1+y2)/2, label, ha='left', va='center',
                fontsize=8.5, fontstyle='italic', color=LABEL)

def harrow(ax, x1, x2, y, label=''):
    ax.annotate('', xy=(x2, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle='->', color=LABEL, lw=1.5))
    if label:
        ax.text((x1+x2)/2, y + 0.15, label, ha='center', va='bottom',
                fontsize=7.5, fontstyle='italic', color=LABEL)

def dashed_box(ax, cx, cy, w, h):
    box = mpatches.FancyBboxPatch(
        (cx - w/2, cy - h/2), w, h,
        boxstyle="round,pad=0.15", facecolor='none', edgecolor=DASH_C,
        linewidth=1.5, linestyle='--')
    ax.add_patch(box)

def make_figure():
    fig, ax = plt.subplots(figsize=(9.5, 8), dpi=120, facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_xlim(-0.2, 9.5)
    ax.set_ylim(0.0, 8.5)
    ax.axis('off')
    return fig, ax


# ═══════════════════════════════════════════════
#  MOBILITY
# ═══════════════════════════════════════════════
def gen_mobility():
    fig, ax = make_figure()
    LX = 2.2   # left stack center
    RX = 7.5   # right module center

    # ── Your Protocol ──
    rounded_box(ax, LX, 7.8, 3.0, 0.75, CYAN, 'Your Protocol', '(user code)')
    varrow(ax, LX, 7.38, 7.05, 'subclass')

    # ── pywisim container ──
    dashed_box(ax, LX, 4.65, 3.7, 4.3)
    ax.text(LX, 6.75, 'pywisim.py \u2014 49 lines', ha='center', va='center',
            fontsize=10, fontweight='bold', color=TEXT)

    # Node
    rounded_box(ax, LX, 5.85, 2.9, 0.95, CYAN, 'Node',
                'on_receive(msg, sender)\nbroadcast(msg)\nunicast(dest, msg)')
    varrow(ax, LX, 5.33, 4.98, 'send / deliver')

    # WirelessNetwork
    rounded_box(ax, LX, 4.25, 2.9, 1.0, ORANGE, 'WirelessNetwork',
                'neighbors(nid)\ncollision avoidance\npacket loss')
    varrow(ax, LX, 3.70, 3.35, 'schedules events')

    # EventLoop
    rounded_box(ax, LX, 2.7, 2.9, 0.85, CYAN, 'EventLoop',
                'schedule(delay, fn)\nrun(until)')

    # ── mobility.py container ──
    dashed_box(ax, RX, 5.85, 2.5, 2.0)
    ax.text(RX, 6.80, 'mobility.py \u2014 33 lines', ha='center', va='center',
            fontsize=10, fontweight='bold', color=TEXT)

    # MobilityManager
    rounded_box(ax, RX, 5.65, 2.0, 1.3, GREEN, 'Mobility\nManager',
                'random waypoint\nrandom walk')

    # Arrow: MobilityManager → WirelessNetwork
    harrow(ax, RX - 1.25, LX + 1.50, 4.55, 'updates net.pos')

    fig.savefig('misc/mobility_architecture.png', bbox_inches='tight',
                pad_inches=0.3, facecolor=BG)
    plt.close()
    print('Saved misc/mobility_architecture.png')


# ═══════════════════════════════════════════════
#  ENCOUNTER
# ═══════════════════════════════════════════════
def gen_encounter():
    fig, ax = make_figure()
    LX = 2.2
    RX = 7.5

    # ── Your Protocol ──
    rounded_box(ax, LX, 7.8, 3.0, 0.75, CYAN, 'Your Protocol', '(user code)')
    varrow(ax, LX, 7.38, 7.05, 'subclass')

    # ── pywisim container ──
    dashed_box(ax, LX, 4.65, 3.7, 4.3)
    ax.text(LX, 6.75, 'pywisim.py \u2014 49 lines', ha='center', va='center',
            fontsize=10, fontweight='bold', color=TEXT)

    # Node
    rounded_box(ax, LX, 5.85, 2.9, 0.95, CYAN, 'Node',
                'on_receive(msg, sender)\nbroadcast(msg)\nunicast(dest, msg)')
    varrow(ax, LX, 5.33, 4.98, 'send / deliver')

    # WirelessNetwork
    rounded_box(ax, LX, 4.25, 2.9, 1.0, ORANGE, 'WirelessNetwork',
                'neighbors(nid)\ncollision avoidance\npacket loss')
    varrow(ax, LX, 3.70, 3.35, 'schedules events')

    # EventLoop
    rounded_box(ax, LX, 2.7, 2.9, 0.85, CYAN, 'EventLoop',
                'schedule(delay, fn)\nrun(until)')

    # ── encounter.py container ──
    dashed_box(ax, RX, 5.05, 2.5, 2.0)
    ax.text(RX, 6.0, 'encounter.py \u2014 42 lines', ha='center', va='center',
            fontsize=10, fontweight='bold', color=TEXT)

    # EncounterManager
    rounded_box(ax, RX, 4.85, 2.0, 1.3, GREEN, 'Encounter\nManager',
                'Poisson encounters\nco-locates pairs')

    # Arrow: EncounterManager → Node (ENCOUNTER)
    harrow(ax, RX - 1.25, LX + 1.50, 5.75, 'on_receive(ENCOUNTER)')

    # Arrow: EncounterManager → WirelessNetwork (manages pos)
    harrow(ax, RX - 1.25, LX + 1.50, 4.25, 'manages net.pos')

    fig.savefig('misc/encounter_architecture.png', bbox_inches='tight',
                pad_inches=0.3, facecolor=BG)
    plt.close()
    print('Saved misc/encounter_architecture.png')


if __name__ == '__main__':
    gen_mobility()
    gen_encounter()
