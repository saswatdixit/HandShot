# 🎯 HANDSHOT

### Gesture-Controlled Aim Trainer for PC

**HANDSHOT** is a computer-vision-powered aim training game that lets you aim and shoot using your **hand in front of a webcam**.

Instead of a mouse, HANDSHOT uses real-time hand landmark tracking to control an on-screen crosshair. Players can aim with their index finger, shoot using a pinch gesture, and interact with the game using additional hand gestures.

> **Point. Pinch. Shoot. Improve.**

---

## ✨ Overview

HANDSHOT combines:

* 🖐️ Real-time hand tracking
* 🎯 Finger-controlled aiming
* 🤏 Pinch-to-shoot interaction
* ✋ Gesture-based game controls
* 🎮 Multiple gameplay modes
* 📊 Accuracy and performance tracking
* 🎨 Minimal, modern game UI
* ⚡ Adaptive low-latency aim filtering
* 🧠 Scale-invariant gesture detection
* 🐛 Developer/debug visualization

The project is designed around one central idea:

> **Turn a normal webcam into a natural, gesture-controlled game controller.**

---

## 🖼️ Gameplay

<!-- Replace these placeholders with actual screenshots/GIFs from the project -->

<p align="center">
  <img src="docs/images/gameplay.png" width="800" alt="HANDSHOT Gameplay">
</p>

<p align="center">
  <i>Aim using your index finger and pinch to shoot.</i>
</p>

### Gameplay loop

```text
             ┌───────────────────┐
             │   Webcam Input    │
             └─────────┬─────────┘
                       │
                       ▼
             ┌───────────────────┐
             │ Hand Detection    │
             │   MediaPipe       │
             └─────────┬─────────┘
                       │
                       ▼
             ┌───────────────────┐
             │ 21 Hand Landmarks │
             └─────────┬─────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
       ┌─────────────┐   ┌─────────────┐
       │ Aim Tracking│   │   Gestures  │
       └──────┬──────┘   └──────┬──────┘
              │                 │
              ▼                 ▼
       ┌─────────────────────────────┐
       │          Game Logic         │
       └──────────────┬──────────────┘
                      │
                      ▼
             ┌───────────────────┐
             │    Pygame UI      │
             └───────────────────┘
```

---

# 🎮 Controls

HANDSHOT is primarily designed around **gesture interaction**, while keyboard controls remain available for navigation and development.

## ✋ Hand Gestures

| Gesture            | Action           | Status      |
| ------------------ | ---------------- | ----------- |
| ☝️ Pointing finger | Aim              | ✅           |
| 🤏 Pinch           | Shoot            | ✅           |
| ✋ Closed palm      | Pause / Resume   | ✅           |
| ✌️ Two fingers     | Weapon switching | 🧩 Prepared |
| 👍 Thumbs up       | Reload           | 🧩 Prepared |

The gesture system is designed as a state-based system so that gestures do not continuously trigger actions while being held.

For example:

```text
OPEN HAND
    │
    ▼
POINTING
    │
    ├────── 🤏 PINCH ──────► SHOOT
    │
    └────── ✋ CLOSED ─────► PAUSE
```

---

## ⌨️ Keyboard Controls

| Key     | Action                                          |
| ------- | ----------------------------------------------- |
| `SPACE` | Keyboard shooting / interaction where supported |
| `ESC`   | Pause / resume                                  |
| `D`     | Toggle developer debug HUD                      |
| `M`     | Toggle audio                                    |
| `S`     | Open camera/setup screen where supported        |

> Keyboard controls are intentionally retained so the game remains testable without relying exclusively on gesture input.

---

# 🎯 Aim Tracking

The biggest challenge in HANDSHOT is not detecting a hand.

It is making the crosshair **feel like it is attached to the player's finger**.

Raw MediaPipe landmarks naturally contain small frame-to-frame fluctuations.

If raw coordinates are used directly:

```text
Finger position:

─────────╲╱╲╱╲╱╲╱─────────
          jitter
```

The crosshair becomes unstable.

HANDSHOT therefore uses an **adaptive velocity-based filtering system**.

---

## ⚡ Adaptive Aim Filtering

The current aim system uses a **1€-style adaptive filter**.

The basic principle is:

```text
Slow movement
      │
      ▼
More smoothing
      │
      ▼
Stable crosshair


Fast movement
      │
      ▼
Higher cutoff
      │
      ▼
Fast response
```

This allows the system to suppress small tracking noise while remaining responsive during intentional movement.

### Filter characteristics

* Minimum cutoff frequency
* Velocity-dependent cutoff
* Filtered derivative estimation
* Soft micro-jitter suppression
* Outlier rejection
* Pre-shot aim anchoring

The goal is not maximum smoothing.

The goal is:

> **Stable when still, responsive when moving.**

---

# 🎯 Pre-Shot Aim Anchoring

A subtle problem occurs when shooting with a pinch.

During the physical pinch motion, the fingertip can move slightly.

Without compensation:

```text
             Target
               ●

Finger ────────┘
             ↓
       tiny movement

Actual shot
       ×
```

HANDSHOT therefore maintains recent aim history and retrieves an **anchored position immediately before the pinch closure**.

Conceptually:

```text
Aim history

t-3   t-2   t-1    t0
 │     │     │      │
 ●─────●─────●──────●
             ↑
        shot anchor
```

This helps prevent the physical act of pinching from changing the intended impact point.

---

# 🤏 Pinch Detection

Pinch detection is designed to remain relatively independent of hand distance from the camera.

A fixed pixel threshold would behave poorly:

```text
Hand close to camera
        ↓
Large distances

Hand far from camera
        ↓
Small distances
```

HANDSHOT instead uses a **normalized hand-scale metric**.

The normalization considers multiple hand dimensions rather than relying on a single measurement.

---

## Hysteresis

The pinch detector uses separate close and release thresholds.

```text
             PINCHED
               ▲
               │
          Close threshold
               │
───────────────┼───────────────
               │
          Release threshold
               │
               ▼
             READY
```

This prevents the state from rapidly oscillating when the measured distance sits near the boundary.

### Behavior

```text
READY
  │
  │ distance <= close threshold
  ▼
PINCHED
  │
  │ distance >= release threshold
  ▼
READY
```

A held pinch produces **one shot**, rather than repeatedly firing because of tiny measurement fluctuations.

---

# 🖐️ Gesture Recognition

HANDSHOT is moving toward a broader gesture-control architecture.

The system distinguishes between gesture states rather than treating each frame as an independent command.

Conceptually:

```text
             ┌──────────────┐
             │   NO HAND    │
             └──────┬───────┘
                    │
                    ▼
             ┌──────────────┐
             │   POINTING   │
             └──┬─────┬─────┘
                │     │
           🤏   │     │   ✋
                ▼     ▼
            PINCH    PALM
              │       │
              ▼       ▼
            SHOOT    PAUSE

       ✌️ TWO FINGERS → future weapon switching

       👍 THUMBS UP   → future reload
```

Gesture transitions use confirmation/debouncing so that a noisy frame does not immediately trigger an action.

---

# ⏸️ Gesture-Based Pause

A closed palm can be used as a gameplay control.

```text
Playing
   │
   │ ✋ Closed Palm
   ▼
Paused
   │
   │ ✋ Open / Pointing
   ▼
Playing
```

The important distinction is between:

**gesture detection**

and

**gesture events**.

Holding a closed palm should not produce:

```text
PAUSE
RESUME
PAUSE
RESUME
PAUSE
...
```

Instead:

```text
CLOSED PALM DETECTED
        ↓
    PAUSE EVENT
        ↓
CLOSED PALM HELD
        ↓
    NO EVENT
        ↓
HAND OPENS
        ↓
   GESTURE RE-ARMED
```

---

# 🎮 Game Modes

HANDSHOT supports different gameplay modes designed around different pacing and difficulty.

### Relaxed

A more forgiving mode focused on smooth practice.

* Slower progression
* Gradual speed increases
* Less pressure
* Suitable for warming up

### Competitive

A faster-paced mode focused on reaction speed and accuracy.

* Faster progression
* More demanding target movement
* Higher pressure
* Designed for score chasing

---

# 🏆 Scoring

HANDSHOT tracks gameplay performance using several metrics.

Core statistics include:

* Score
* Hits
* Shots
* Accuracy
* Time
* Lives
* Combo / streak
* High score

Perfect shots can contribute to streak-based scoring bonuses.

The goal is to reward both:

```text
                 SPEED
                   +
                ACCURACY
                   +
              CONSISTENCY
                   ↓
                SCORE
```

---

# 🎨 UI / Design Philosophy

HANDSHOT deliberately avoids the typical "AI project" visual style.

No:

* ❌ excessive neon
* ❌ cyberpunk overload
* ❌ giant HUD elements
* ❌ unnecessary gradients
* ❌ excessive animations
* ❌ technical information everywhere

Instead, the interface follows:

> **Minimal. Clean. Calm. Functional.**

---

## Typography

The UI uses a centralized typography system with clear hierarchy.

Conceptual hierarchy:

```text
DISPLAY
Large titles / final score

H1
Major sections / countdown

H2
Mode titles / headings

BODY
Normal interface text

BODY SMALL
Descriptions / instructions

LABEL
Badges / status

CAPTION
Secondary information

DEBUG
Technical telemetry
```

The debug interface uses a separate monospaced style.

---

# 🖥️ UI Structure

## Main Menu / Mode Selection

```text
┌─────────────────────────────────────────────────────┐
│                                                     │
│                     HANDSHOT                        │
│                                                     │
│             Choose your experience                 │
│                                                     │
│       ┌────────────────┐  ┌────────────────┐       │
│       │    RELAXED     │  │  COMPETITIVE   │       │
│       │                │  │                │       │
│       │  Smooth pace   │  │  Test yourself │       │
│       └────────────────┘  └────────────────┘       │
│                                                     │
└─────────────────────────────────────────────────────┘
```

The actual interface uses the project's Pygame rendering system.

---

# ✋ Ready Screen

The ready screen provides a simple hand-acquisition experience.

```text
             READY

        Show your hand

       ───────────────
       Stabilizing...
       █████████░░░░░
       ───────────────

        Point to begin
```

The intention is to make the player understand what the system is waiting for without exposing technical computer-vision details.

---

# ⏱️ Countdown

The countdown focuses attention on the upcoming round.

```text
                 3

          Get ready to aim
```

followed by:

```text
                 2
```

```text
                 1
```

```text
                 GO
```

---

# 🎯 Gameplay HUD

The gameplay HUD is divided into isolated zones to avoid overlap.

```text
┌─────────────────────────────────────────────────────┐
│ HANDSHOT          RELAXED          SCORE            │
│                                      1240           │
│                                                     │
│                                                     │
│                         +                           │
│                                                     │
│                                                     │
│                                                     │
│                                  TIME   42          │
└─────────────────────────────────────────────────────┘
```

The center of the screen remains dedicated to gameplay.

---

# ⏸️ Pause Screen

The pause interface intentionally uses a subtle overlay rather than completely replacing the game scene.

```text
┌─────────────────────────────────────────────────────┐
│                                                     │
│                                                     │
│                    PAUSED                           │
│                                                     │
│                 Game is paused                      │
│                                                     │
│                 [ RESUME ]                          │
│                 [ RESTART ]                         │
│                 [ QUIT ]                            │
│                                                     │
│             Close palm or press ESC                │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

# 🏁 Results Screen

At the end of a round:

```text
                 RESULTS

                 1240
                SCORE

        Accuracy       94%
        Hits           47
        Shots          50
        Time           60s

              NEW HIGH SCORE

          [ PLAY AGAIN ]
          [ HOME ]
```

The results screen focuses on the player's performance rather than technical diagnostics.

---

# 🐛 Debug Mode

HANDSHOT includes a developer-focused diagnostic HUD.

It is **hidden by default**.

Press:

```text
D
```

to toggle it.

The debug panel can expose information such as:

```text
CAM       LOCAL / FPS
STATE     PLAYING
HAND      TRACKED
CONF      0.94

RAW/FILT  0.52,0.48 → 0.51,0.49

VEL/FC    0.04 / 3.2Hz

AIM       623,412

PINCH     0.38
PHASE     PINCHED

GESTURE   POINTING

SHOT      17

STATS     15/17  88%
```

This keeps technical information available during development without polluting normal gameplay.

---

# 🧠 Technology Stack

| Technology    | Purpose                             |
| ------------- | ----------------------------------- |
| **Python**    | Core application                    |
| **Pygame**    | Game engine and rendering           |
| **OpenCV**    | Webcam capture and image processing |
| **MediaPipe** | Hand landmark detection             |
| **NumPy**     | Numerical processing                |
| **unittest**  | Automated testing                   |

---

# 🏗️ Project Architecture

The project follows a modular structure separating camera input, tracking, gestures, aiming, game logic, and UI.

```text
HANDSHOT/
│
├── camera/
│   ├── camera_manager.py
│   └── ...
│
├── aim/
│   └── aim_controller.py
│
├── gestures/
│   ├── pinch_detector.py
│   └── gesture_detector.py
│
├── game/
│   ├── aim_screen.py
│   ├── ui_layout.py
│   ├── typography.py
│   └── ...
│
├── config/
│   └── settings.py
│
├── tests/
│   ├── test_aim_controller.py
│   ├── test_pinch_detector.py
│   ├── test_ui_layout.py
│   └── ...
│
├── main.py
├── requirements.txt
└── README.md
```

---

# 🔄 Data Flow

The complete runtime pipeline can be represented as:

```text
┌─────────────┐
│   Webcam    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Camera      │
│ Manager     │
└──────┬──────┘
       │
       │ Frame
       ▼
┌─────────────┐
│ MediaPipe   │
│ Hand        │
│ Tracking    │
└──────┬──────┘
       │
       │ 21 landmarks
       ▼
┌───────────────────────┐
│ Tracking / Processing │
└──────────┬────────────┘
           │
      ┌────┴────────────┐
      ▼                 ▼
┌─────────────┐   ┌──────────────┐
│ Aim         │   │ Gesture      │
│ Controller  │   │ Detection    │
└──────┬──────┘   └──────┬───────┘
       │                 │
       └────────┬────────┘
                ▼
        ┌──────────────┐
        │ Game Logic   │
        └──────┬───────┘
               │
               ▼
        ┌──────────────┐
        │ Pygame UI    │
        └──────────────┘
```

---

# 📦 Installation

## Requirements

Recommended environment:

* Windows / Linux / macOS
* Python 3.10+
* Functional webcam
* Good lighting
* A reasonably modern CPU

A dedicated GPU is not required for the basic game.

---

## Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/HANDSHOT.git
cd HANDSHOT
```

Replace `YOUR_USERNAME` with your GitHub username.

---

## Create a virtual environment

### Windows

```powershell
py -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## Install dependencies

```bash
pip install -r requirements.txt
```

---

# ▶️ Running HANDSHOT

Start the game:

```bash
py main.py
```

For development/debugging:

```bash
py main.py --debug-gestures
```

For camera/tracking diagnostics:

```bash
py main.py --check 30
```

For a tracking preview:

```bash
py main.py --preview
```

---

# 🧪 Testing

HANDSHOT includes automated tests for the core systems.

Run the complete test suite:

```bash
py -m unittest discover tests
```

Tracking diagnostics:

```bash
py main.py --check 30
```

Tracking preview:

```bash
py main.py --preview --duration 5.0
```

Debug gesture mode:

```bash
py main.py --debug-gestures --duration 5.0
```

Normal gameplay test:

```bash
py main.py --duration 10.0
```

---

# 🖥️ UI Preview

Individual UI states can be previewed without playing a complete game.

```bash
py main.py --ui-preview select --duration 1.0
py main.py --ui-preview ready --duration 1.0
py main.py --ui-preview countdown --duration 1.0
py main.py --ui-preview playing --duration 1.0
py main.py --ui-preview paused --duration 1.0
py main.py --ui-preview results --duration 1.0
```

This makes it easier to test UI layout independently from gameplay.

---

# 📊 Current Validation

The project has been tested across:

* Automated unit tests
* Camera pipeline diagnostics
* Hand tracking
* Aim filtering
* Pinch detection
* Gesture state handling
* Gameplay runtime
* UI preview states

Recent validation included:

```text
Unit tests
    ↓
Camera diagnostics
    ↓
Tracking laboratory
    ↓
Debug gesture mode
    ↓
Normal gameplay
    ↓
UI state previews
```

The exact test count may change as new functionality is added.

---

# 🛠️ Configuration

Important tuning parameters are centralized in:

```text
config/settings.py
```

This allows tracking and gesture behavior to be tuned without scattering constants throughout the codebase.

Examples include:

```text
Aim filtering
├── minimum cutoff
├── speed coefficient
└── derivative cutoff

Pinch detection
├── close threshold
└── release threshold

Gesture detection
├── confirmation frames
├── release frames
├── palm thresholds
└── confidence thresholds
```

---

# 💡 Design Principles

HANDSHOT is being developed around several principles.

### 1. Responsiveness over excessive smoothing

The cursor should feel connected to the hand.

### 2. Accuracy over flashy effects

Visual effects should communicate gameplay events rather than distract from them.

### 3. Gestures should behave like controls

A gesture should trigger an intentional event, not continuously fire actions.

### 4. Technical complexity should stay behind the interface

Computer vision is complicated.

The player shouldn't have to see that complexity.

### 5. Modular architecture

Weapons, gestures, scoring systems, and UI components should be independently extensible.

---

# 🚧 Roadmap

HANDSHOT is still under active development.

## ✅ Completed

* [x] Webcam input
* [x] MediaPipe hand tracking
* [x] 21-landmark hand processing
* [x] Finger-controlled aiming
* [x] Adaptive aim filtering
* [x] Outlier rejection
* [x] Pinch-to-shoot
* [x] Scale-invariant pinch detection
* [x] Pinch hysteresis
* [x] Pre-shot aim anchoring
* [x] Multiple game states
* [x] Relaxed mode
* [x] Competitive mode
* [x] Score tracking
* [x] Accuracy tracking
* [x] High scores
* [x] Minimal UI overhaul
* [x] Debug HUD
* [x] Gesture architecture
* [x] Closed-palm pause/resume

## 🔨 In Development

* [ ] Multiple weapon types
* [ ] Weapon-specific shooting behavior
* [ ] Weapon-specific crosshairs
* [ ] Weapon-specific audio
* [ ] Reload mechanics
* [ ] Weapon switching gestures
* [ ] More advanced gesture interactions
* [ ] Better visual hit feedback
* [ ] Expanded sound design

## 🔮 Future Ideas

* [ ] More weapons
* [ ] Advanced target patterns
* [ ] Difficulty customization
* [ ] Personal performance history
* [ ] Training challenges
* [ ] Leaderboards
* [ ] More gesture-controlled menus
* [ ] Additional game modes

---

# 🔫 Planned Weapon System

One of the next major expansions is weapon variety.

The goal is not simply to change the weapon's appearance.

Each weapon should have its own behavior.

```text
                 WEAPON
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
     FIRE        AIM         AUDIO
       │           │           │
   ┌───┴───┐       │       ┌───┴────┐
   ▼       ▼       ▼       ▼        ▼
 Damage  Rate   Crosshair Shot    Reload
                  │       Sound    Sound
                  ▼
                Recoil
```

Planned examples include:

### 🔫 Pistol

* Precise
* Moderate fire rate
* Small crosshair
* Single-shot behavior

### 🔥 Assault Rifle

* High fire rate
* Controlled recoil
* Larger crosshair
* Automatic fire behavior

### 💥 Shotgun

* Wide spread
* Multiple pellets
* Large spread-style crosshair
* Heavy firing sound

Future weapons may introduce completely different mechanics rather than simply higher damage.

---

# 🔊 Audio Direction

Audio will be designed around gameplay feedback.

Each weapon should eventually have:

* firing sound
* reload sound
* empty-magazine sound
* hit feedback
* weapon-switch sound

Different weapons should be recognizable **by sound as well as behavior**.

---

# 🎯 Crosshair System

Crosshairs will be weapon-specific.

Example concept:

```text
PISTOL

      +
```

```text
ASSAULT RIFLE

     ─┼─
      │
```

```text
SHOTGUN

    \ | /
   -- + --
    / | \
```

The crosshair should communicate the weapon's behavior visually.

A shotgun should feel wider.

A precise weapon should feel tighter.

---

# 🤝 Contributing

Contributions are welcome.

If you'd like to contribute:

1. Fork the repository.
2. Create a feature branch.

```bash
git checkout -b feature/your-feature
```

3. Make your changes.
4. Run the test suite.

```bash
py -m unittest discover tests
```

5. Commit your changes.

```bash
git add .
git commit -m "Add your feature"
```

6. Push the branch.

```bash
git push origin feature/your-feature
```

7. Open a Pull Request.

---

# 🐛 Reporting Issues

When reporting a bug, include:

* Operating system
* Python version
* Webcam model if relevant
* HANDSHOT version/commit
* Command used
* Expected behavior
* Actual behavior
* Relevant console output
* Screenshot/video if possible

For tracking problems, also mention:

* lighting conditions
* approximate distance from camera
* whether the issue occurs during slow or fast movement
* whether debug mode shows reduced hand confidence

---

# 📜 License

Add the project's chosen license here.

For example:

```text
MIT License
```

if the repository is intended to use the MIT License.

---

# 👨‍💻 Project

**HANDSHOT** is a personal computer-vision/game development project exploring how far a standard webcam can be pushed as a natural game controller.

The project sits at the intersection of:

```text
Computer Vision
       +
Human-Computer Interaction
       +
Game Development
       +
Real-Time Signal Processing
       +
UI / UX
```

---

## ⭐ If you like the project

Give the repository a ⭐ on GitHub.

Feedback, ideas, and contributions are welcome.

---

<p align="center">

### HANDSHOT

**Your hand is the controller.**

🎯 **Aim · 🤏 Pinch · ✋ Pause · Improve**

</p>
