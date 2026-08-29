"""Central configuration for HANDSHOT.

Phase 1 (camera), Phase 2 (hand tracking), and Phase 3 (aim) values live
here. Later phases should add their own clearly-marked section here instead of
scattering literals through the code (see main.md sections 49-50).
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# Camera (Phase 1)
# --------------------------------------------------------------------------

DEFAULT_CAMERA_INDEX = 0

# Requested capture resolution. The driver may negotiate something else, so
# always read the real values back from CameraManager after opening.
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30

# Mirroring the frame makes hand movement feel like looking into a mirror
# (main.md section 33). It is applied at capture time so every downstream
# consumer works in the same coordinate space.
MIRROR_CAMERA = True

# How many device indices to scan when listing available cameras.
CAMERA_PROBE_LIMIT = 6

# Frames discarded right after opening while auto-exposure/white-balance settle.
CAMERA_WARMUP_FRAMES = 5

# Consecutive failed reads tolerated before the camera is considered lost.
CAMERA_READ_RETRIES = 5

# Grab frames on a background thread. Without this the loop runs serially -
# block ~33ms for a frame, then ~22ms tracking it - which caps the pipeline at
# roughly 19 fps. Threaded capture overlaps the two so the cost is max(), not
# sum() (main.md section 44).
CAMERA_THREADED = True

# How long read() waits for a fresh frame before reporting a stall (seconds).
CAMERA_FRAME_TIMEOUT = 0.5


# --------------------------------------------------------------------------
# Hand tracking (Phase 2)
# --------------------------------------------------------------------------

HAND_MODEL_PATH = PROJECT_ROOT / "assets" / "models" / "hand_landmarker.task"
HAND_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)

# One hand keeps tracking fast and unambiguous (main.md section 45). If this is
# raised, HandTracker still picks a single primary hand for aiming.
MAX_HANDS = 1

# 0.35 confidence allows instant, robust palm acquisition and tracking across
# varied lighting, skin tones, hand distances, and natural hand orientations.
MIN_HAND_DETECTION_CONFIDENCE = 0.35
MIN_HAND_PRESENCE_CONFIDENCE = 0.35
MIN_TRACKING_CONFIDENCE = 0.35

# Width the frame is downscaled to before hand tracking.
TRACKING_INPUT_WIDTH = 640

# On a brief tracking dropout the last known hand is reused for this many
# frames so the aim point does not snap away (main.md section 45).
TRACKING_GRACE_FRAMES = 12


# --------------------------------------------------------------------------
# Phase 3: Pygame aim screen & crosshair
# --------------------------------------------------------------------------

GAME_WINDOW_NAME = "HANDSHOT"
GAME_WIDTH = 1280
GAME_HEIGHT = 720
GAME_FPS = 60

# Direct fingertip mapping: a comfortable central camera band covers
# the full playfield with minimal wrist travel.
AIM_INPUT_LEFT = 0.18
AIM_INPUT_TOP = 0.18
AIM_INPUT_RIGHT = 0.82
AIM_INPUT_BOTTOM = 0.82

# 1€ Adaptive Velocity Filter:
# Stationary cutoff (2.5 Hz) removes micro-jitter; dynamic scaling (beta=18.0)
# provides zero-lag instant tracking during fast motion.
AIM_MIN_CUTOFF_HZ = 2.5
AIM_SPEED_COEFF = 18.0
AIM_DERIVATIVE_CUTOFF_HZ = 15.0
AIM_DEADZONE = 0.0015
AIM_SMOOTHING_HZ = 24.0
AIM_MAX_TELEPORT_DISTANCE = 0.45

# Keep the crosshair from disappearing off the edge.
CROSSHAIR_MARGIN = 28
CROSSHAIR_RADIUS = 16
CROSSHAIR_MIN_SCALE = 0.80
CROSSHAIR_MAX_SCALE = 1.25

# Pre-shot aim anchor duration (seconds) to eliminate trigger squeeze jerk.
AIM_PRE_SHOT_ANCHOR_SECONDS = 0.045
CROSSHAIR_FIRE_PULSE_SECONDS = 0.09


# --------------------------------------------------------------------------
# Phase 4: pinch shooting vertical slice
# --------------------------------------------------------------------------

# Scale-normalized thumb/index distance in isotropic space.
# 0.45 close threshold allows effortless, natural finger contact to fire instantly.
# 0.62 release threshold allows fast, crisp re-arming with minimal separation.
PINCH_CLOSE_THRESHOLD = 0.45
PINCH_RELEASE_THRESHOLD = 0.62
PINCH_RELEASE_STABLE_FRAMES = 1
PINCH_COOLDOWN_SECONDS = 0.04
PINCH_DEBOUNCE_FRAMES = 1
PINCH_DISTANCE_FILTER_SAMPLES = 1

# --------------------------------------------------------------------------
# Spatial Reload Zone Settings
# --------------------------------------------------------------------------
# Hand/wrist position near bottom of screen triggers reliable reload
RELOAD_ZONE_TOP = 0.80
RELOAD_ZONE_EXIT = 0.70
RELOAD_DWELL_SECONDS = 0.30
RELOAD_COOLDOWN_SECONDS = 0.50

# Visual effects durations (clean and brief)
TRAINING_TARGET_RADIUS = 44
TARGET_HIT_EFFECT_SECONDS = 0.25
SHOT_EFFECT_SECONDS = 0.12


# --------------------------------------------------------------------------
# Phase 5 & 6: Blue-bubble game session & Core Game Loop
# --------------------------------------------------------------------------

BLUE_BUBBLE_SCORE = 10
INITIAL_LIVES = 3

# Combo multipliers:
# 0-2 consecutive hits -> 1x
# 3-4 consecutive hits -> 2x
# 5+ consecutive hits  -> 3x
COMBO_TIER_1_HITS = 3
COMBO_TIER_2_HITS = 5
COMBO_TIER_1_MULTIPLIER = 2
COMBO_TIER_2_MULTIPLIER = 3

# Difficulty Progression Scaling
# Score at which difficulty reaches maximum (gradual scaling from 0 to 600 points)
DIFFICULTY_MAX_SCORE = 600.0

# Bubble Speed Scaling (gradual increase from comfortable starting feel)
BUBBLE_SPEED_MIN_START = 75.0
BUBBLE_SPEED_MIN_END = 120.0
BUBBLE_SPEED_MAX_START = 130.0
BUBBLE_SPEED_MAX_END = 195.0

# Spawn Interval Scaling (seconds between spawns)
BUBBLE_SPAWN_INTERVAL_START = 1.50
BUBBLE_SPAWN_INTERVAL_END = 0.80

# Max Active Bubbles on Playfield (starts at 2 gentle targets)
BUBBLE_INITIAL_COUNT = 2
BUBBLE_MAX_ACTIVE_START = 3
BUBBLE_MAX_ACTIVE_END = 6

# Bubble Radii and Spawn Clearance
BUBBLE_RADIUS_MIN = 28
BUBBLE_RADIUS_MAX = 46
BUBBLE_SPAWN_ATTEMPTS = 30
BUBBLE_SPAWN_SEPARATION = 18

# Subtle shot forgiveness — not auto-aim, just a little leeway around bubbles.
HIT_FORGIVENESS_PADDING = 12


# --------------------------------------------------------------------------
# Phase 7: Game Flow, Ready Phase, Countdown & Pause System
# --------------------------------------------------------------------------

# Time a hand must be continuously detected to confirm readiness (seconds)
# 0.35s is fast, responsive confirmation with zero frustrating delay.
READY_HAND_STABLE_SECONDS = 0.35

# Countdown timings (seconds per step: 3 -> 2 -> 1 -> GO!)
COUNTDOWN_STEP_SECONDS = 0.75
COUNTDOWN_GO_SECONDS = 0.50

# High score persistence file path
STATS_SAVE_PATH = PROJECT_ROOT / "data" / "statistics.json"


# --------------------------------------------------------------------------
# Phase 8: Game Modes & Audio System
# --------------------------------------------------------------------------

# Timed Mode duration (seconds)
TIMED_MODE_DURATION = 60.0

# Chill Mode tuning (relaxed, slower, low pressure)
CHILL_BUBBLE_INITIAL_COUNT = 2
CHILL_BUBBLE_MAX_ACTIVE = 3
CHILL_BUBBLE_SPAWN_INTERVAL = 1.80
CHILL_BUBBLE_SPEED_MIN = 50.0
CHILL_BUBBLE_SPEED_MAX = 85.0

# Practice Mode tuning (calm training, predictable targets)
PRACTICE_BUBBLE_INITIAL_COUNT = 2
PRACTICE_BUBBLE_MAX_ACTIVE = 2
PRACTICE_BUBBLE_SPAWN_INTERVAL = 2.00
PRACTICE_BUBBLE_SPEED_MIN = 45.0
PRACTICE_BUBBLE_SPEED_MAX = 75.0

# Audio System Directories & Settings
AUDIO_DIR = PROJECT_ROOT / "assets" / "audio"
AUDIO_SFX_DIR = AUDIO_DIR / "sfx"
AUDIO_MUSIC_DIR = AUDIO_DIR / "music"
AUDIO_ENABLED = True
AUDIO_MASTER_VOLUME = 0.80
AUDIO_SFX_VOLUME = 0.90
AUDIO_MUSIC_VOLUME = 0.55

# --------------------------------------------------------------------------
# UI Layout Safe Zones & Dimensions
# --------------------------------------------------------------------------

HUD_MARGIN_X = 24
HUD_MARGIN_Y = 12
HUD_HEIGHT = 88
CONTROL_BAR_HEIGHT = 44

# Keep the entire bubble (not merely its centre) strictly outside HUD and
# control bar areas, and within the range reachable by the crosshair.
PLAYFIELD_LEFT = CROSSHAIR_MARGIN
PLAYFIELD_TOP = HUD_HEIGHT + 20
PLAYFIELD_RIGHT_INSET = CROSSHAIR_MARGIN
PLAYFIELD_BOTTOM_INSET = CONTROL_BAR_HEIGHT + 26


# --------------------------------------------------------------------------
# Phase 9: Target Variety, Visual Feedback, Particles & Audio Refinement
# --------------------------------------------------------------------------

# Target Type Base Scores
SCORE_NORMAL = 10
SCORE_SMALL = 20
SCORE_LARGE = 5
SCORE_GOLDEN = 50

# Target Radii Range per Type
RADIUS_NORMAL_MIN = 28.0
RADIUS_NORMAL_MAX = 38.0
RADIUS_SMALL_MIN = 18.0
RADIUS_SMALL_MAX = 24.0
RADIUS_LARGE_MIN = 42.0
RADIUS_LARGE_MAX = 52.0
RADIUS_GOLDEN_MIN = 32.0
RADIUS_GOLDEN_MAX = 40.0

# Target Speed Multipliers (relative to mode baseline speed range)
SPEED_MULT_NORMAL = 1.00
SPEED_MULT_SMALL = 1.35
SPEED_MULT_LARGE = 0.70
SPEED_MULT_GOLDEN = 1.05

# Spawn Probabilities per Mode: (Normal, Small, Large, Golden)
# Sum must equal 1.00
SPAWN_PROBS_CLASSIC = (0.65, 0.18, 0.14, 0.03)
SPAWN_PROBS_CHILL = (0.45, 0.05, 0.45, 0.05)
SPAWN_PROBS_TIMED = (0.55, 0.25, 0.12, 0.08)
SPAWN_PROBS_PRACTICE = (0.40, 0.00, 0.55, 0.05)

# Combo streak tier 3 (10+ hits)
COMBO_TIER_3_HITS = 10
COMBO_TIER_3_MULTIPLIER = 4

# Particle System Limits & Lifespans
MAX_ACTIVE_PARTICLES = 300
PARTICLE_LIFESPAN_NORMAL = 0.45
PARTICLE_LIFESPAN_GOLDEN = 0.70
PARTICLE_COUNT_NORMAL = 12
PARTICLE_COUNT_SMALL = 8
PARTICLE_COUNT_LARGE = 18
PARTICLE_COUNT_GOLDEN = 28


# --------------------------------------------------------------------------
# MediaPipe hand landmark indices
# --------------------------------------------------------------------------

WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

LANDMARK_COUNT = 21


# --------------------------------------------------------------------------
# Development preview window
# --------------------------------------------------------------------------

PREVIEW_WINDOW_NAME = "HANDSHOT - Phase 1+2 - camera & hand tracking"
SHOW_LANDMARKS = True
SHOW_HUD = True

# Exponential moving average factor for the on-screen FPS counter.
FPS_SMOOTHING = 0.9

# Toggle in-game control debug HUD with D or --debug-gestures.
SHOW_CONTROL_DEBUG = False
