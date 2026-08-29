# HANDSHOT — Master Game Specification

## 1. Project Overview

**HANDSHOT** is a webcam-controlled arcade aim game where the player controls the game using hand and finger movements instead of a mouse or controller.

The player's webcam tracks their hand in real time. The **index fingertip acts as the on-screen crosshair**, allowing the player to aim naturally by moving their finger. Specific hand gestures perform actions such as shooting, reloading, switching weapons, pausing, grabbing objects, and defensive movement.

The game should feel like a polished **FPS/aim-trainer-inspired arcade game**, while remaining simple, responsive, and fun.

The primary focus is:

> **Smooth hand-controlled aiming + responsive gesture recognition + satisfying target shooting.**

This is initially a **local desktop Python application**.

A web version and phone-as-webcam support may be developed later, but they are NOT part of the initial implementation.

---

# 2. Core Design Philosophy

The game should follow these principles:

### 2.1 Responsive

The crosshair must react quickly to finger movement.

Small finger movements should result in small crosshair movements.

Large movements should result in larger crosshair movements.

The player should feel that they have direct control over the crosshair.

### 2.2 Smooth

Raw webcam hand tracking can be noisy and jittery.

The game must apply appropriate smoothing/filtering so that the crosshair feels stable while still responding quickly.

Avoid excessive smoothing because it creates input lag.

### 2.3 Simple to Understand

The player should understand the game within seconds.

The primary interaction is:

> Point → Aim → Pinch → Shoot

Additional gestures should gradually introduce more advanced gameplay.

### 2.4 Arcade Feel

The game should be fast, satisfying, and visually responsive.

Actions should have:

* Hit effects
* Sound effects
* Animations
* Score popups
* Combo feedback
* Perfect-hit feedback
* Weapon effects

These effects should improve the experience without overwhelming the screen.

### 2.5 Clean Interface

The gameplay screen should remain uncluttered.

The bubbles and crosshair should be the main visual focus.

The HUD should contain only useful information.

---

# 3. Technology Stack

The initial local version should use:

### Programming Language

**Python**

### Computer Vision

**OpenCV**

Responsibilities:

* Access webcam
* Capture frames
* Process camera input
* Handle camera selection

### Hand Tracking

**MediaPipe**

Responsibilities:

* Detect hands
* Track hand landmarks
* Track index fingertip
* Detect finger positions
* Provide data for gesture recognition

MediaPipe provides the hand landmark coordinates required for aiming and gesture detection.

### Game Engine

**Pygame**

Responsibilities:

* Game window
* Rendering
* Game loop
* Sprites
* Collision detection
* Audio
* Input/game state
* UI
* Animations

### Numerical Processing

**NumPy**

Use where useful for:

* Coordinate calculations
* Distances
* Smoothing
* Vector calculations
* Gesture calculations

---

# 4. High-Level System Architecture

The application should follow this general pipeline:

```text
                WEBCAM
                   |
                   v
             OpenCV Capture
                   |
                   v
            MediaPipe Hands
                   |
                   v
          Hand Landmark Data
                   |
          +--------+---------+
          |                  |
          v                  v
    Aim Processing      Gesture Detection
          |                  |
          v                  v
   Crosshair Position    Game Actions
          |                  |
          +--------+---------+
                   |
                   v
              GAME ENGINE
                 Pygame
                   |
        +----------+----------+
        |          |          |
        v          v          v
     Targets    Weapons      HUD
        |          |          |
        +----------+----------+
                   |
                   v
              Game State
```

The camera/hand tracking layer should be separated from the game logic as much as reasonably possible.

---

# 5. Core Gameplay

The player controls an on-screen crosshair using their index finger.

Objects/bubbles appear and move around the game area.

The player aims at bubbles and performs a pinch gesture to shoot.

Different bubble colors have different effects.

The objective depends on the selected game mode.

Basic gameplay loop:

```text
Detect hand
    ↓
Track index finger
    ↓
Move crosshair
    ↓
Detect target
    ↓
Perform pinch
    ↓
Fire weapon
    ↓
Check collision
    ↓
Destroy / trigger target
    ↓
Update score
    ↓
Update combo
    ↓
Spawn new targets
```

---

# 6. Hand Tracking

MediaPipe should be used to detect and track the player's hand.

The system should primarily use the index fingertip as the aiming reference point.

Important landmarks include:

* Wrist
* Thumb tip
* Index fingertip
* Index joints
* Middle finger
* Ring finger
* Pinky

The system should support reliable detection even when the hand moves around the camera frame.

---

# 7. Crosshair / Aim System

The crosshair is one of the most important features of the game.

The player's index fingertip controls it.

## 7.1 Basic behavior

The system should convert the tracked index fingertip movement into game-screen movement.

Do NOT simply teleport the crosshair directly to the raw webcam coordinate.

Instead use a controlled input system:

```text
Index fingertip movement
        ↓
Coordinate processing
        ↓
Sensitivity
        ↓
Deadzone/filtering
        ↓
Smoothing
        ↓
Crosshair position
```

## 7.2 Relative movement

The crosshair should feel similar to an FPS mouse.

Small finger movement:

```text
Small movement → Small crosshair movement
```

Large finger movement:

```text
Large movement → Large crosshair movement
```

## 7.3 Sensitivity

Provide a sensitivity setting.

Example:

```text
Sensitivity
LOW ─────────●──── HIGH
```

Higher sensitivity means less physical hand movement is required to move the crosshair across the screen.

Lower sensitivity provides more precise control.

## 7.4 X/Y Sensitivity

Allow separate horizontal and vertical sensitivity settings.

```text
X Sensitivity
Y Sensitivity
```

This allows players to fine-tune their aim.

## 7.5 Smoothing

Provide a smoothing setting.

The goal is:

> Remove small tracking jitter without creating noticeable input delay.

Possible implementation can use interpolation, exponential smoothing, moving averages, or another appropriate filtering technique.

The exact algorithm can be selected during implementation based on testing.

## 7.6 Deadzone

Optional deadzone should prevent tiny tracking noise from moving the crosshair.

The deadzone should be configurable.

## 7.7 Screen boundaries

The crosshair must never leave the game window.

Clamp its position within the playable area.

---

# 8. Crosshair Design

The crosshair should be clearly visible but not distracting.

Settings should include:

* Crosshair style
* Size
* Thickness
* Opacity
* Color
* Center dot ON/OFF
* Hit marker ON/OFF

Possible crosshair styles:

* Circle
* Cross
* Dot
* Circle + dot
* Four-line FPS style

The exact visual design can be refined during implementation.

## Target interaction

When the crosshair is over a target, it may provide subtle visual feedback.

Example:

```text
Normal:
   ○

Hovering target:
   ⊙
```

Avoid excessive target highlighting because the player should still need to aim accurately.

---

# 9. Gesture System

The game uses gestures as its primary controls.

Initial gesture mapping:

| Gesture             | Action        |
| ------------------- | ------------- |
| Index finger        | Aim           |
| Thumb + index pinch | Shoot         |
| Open palm           | Pause         |
| Two fingers         | Switch weapon |
| Fist                | Reload        |
| Swipe               | Dash/deflect  |
| Pinch + movement    | Grab/interact |

Gesture detection must be designed to avoid accidental activation.

---

# 10. Gesture Detection Requirements

Gesture detection should not trigger from a single noisy frame.

Use appropriate:

* Distance thresholds
* Finger-state checks
* Frame history
* Gesture cooldowns
* State transitions
* Debouncing

For example, a pinch should be detected when the thumb and index fingertip distance falls below a threshold for a short number of frames.

Avoid repeatedly firing every frame while the fingers remain pinched.

A pinch should normally generate one shooting action, followed by a cooldown or release requirement depending on weapon behavior.

---

# 11. Shooting Gesture

### Pinch

The primary shooting gesture is:

> Thumb + index fingertip brought together.

The system detects the pinch.

The weapon fires toward the crosshair.

The shot should originate from the player's current crosshair position.

The exact firing behavior depends on the equipped weapon.

---

# 12. Pause Gesture

### Open Palm

An open palm should trigger the pause system.

When pause is activated:

* Gameplay stops
* Targets stop moving
* Timer stops
* Inputs related to gameplay are disabled
* Pause menu appears

The pause menu should allow:

* Resume
* Restart
* Settings
* Main Menu

Avoid triggering pause repeatedly while the palm remains open.

---

# 13. Weapon Switching Gesture

### Two Fingers

The player raises two fingers to switch weapons.

Weapon switching should cycle through unlocked/available weapons.

Example:

```text
Pistol
   ↓
Shotgun
   ↓
SMG
   ↓
Sniper
   ↓
Laser
```

A visual notification should briefly show the newly equipped weapon.

---

# 14. Reload Gesture

### Fist

A closed fist triggers reload.

Reload behavior depends on the equipped weapon.

If the magazine is already full, reload should not waste time unless intentionally designed otherwise.

A reload animation and sound should be used.

---

# 15. Swipe Gesture

A quick directional hand movement should be interpreted as a swipe.

Possible uses:

* Dash
* Deflect
* Avoid dangerous objects

For example:

```text
Swipe Left
    ↓
Dash/deflect left
```

Swipe detection must distinguish intentional swipes from normal aiming movement.

The swipe system should have:

* Minimum movement distance
* Time window
* Direction detection
* Cooldown

---

# 16. Grab / Interaction Gesture

Pinch + movement can be used for interactive objects.

This feature should initially be limited to special gameplay objects/power-ups.

Example:

```text
Pinch object
     ↓
Move hand
     ↓
Object follows interaction
     ↓
Release pinch
```

Do not allow this mechanic to interfere with normal shooting.

If necessary, use specific object states or interaction zones to distinguish grabbing from shooting.

---

# 17. Bubble / Target System

The primary targets are colorful bubbles.

The game should use simple, clean bubble visuals.

Different colors represent different gameplay effects.

The player should learn the meaning of colors through the tutorial/how-to-play screen.

---

# 18. Bubble Types

## 🔵 Cyan / Blue Bubble

### Normal target

Purpose:

* Main target
* Most common bubble
* Standard scoring

Effect:

> Destroy → gain normal points

Suggested base score:

**+10**

---

## ⚫ Black Bubble

### Dangerous bubble

Effect:

> Shooting it removes 1 heart.

The player should avoid shooting black bubbles.

Black bubbles should have clear visual differentiation.

---

## 🔴 Red Bubble

### Health bubble

Effect:

> Destroy → gain 1 heart.

There should be a maximum health limit.

Suggested maximum:

**5 hearts**

If the player is already at maximum health, the red bubble could either:

* Give bonus points, or
* Simply disappear without additional health.

Choose whichever produces better gameplay during testing.

---

## 🟡 Yellow Bubble

### Bonus bubble

Effect:

> Destroy → +5 bonus points.

It can also contribute to the normal combo system.

---

## 🟢 Green Bubble

### Slow-motion power-up

Effect:

> Temporarily slows bubble movement.

Suggested duration:

**3–5 seconds**

The exact duration should be configurable during balancing.

---

## 🟣 Purple Bubble

### Score multiplier

Effect:

> Temporarily increases the player's score multiplier.

Example:

```text
Normal: ×1
Purple activated: ×2
```

Duration should be limited.

---

## ⚪ White Bubble

### High-risk/high-reward target

Characteristics:

* Smaller
* Faster
* More difficult to hit
* Higher reward

The exact score should be balanced during testing.

---

# 19. Bubble Behavior

Bubbles should not all move identically.

Possible behaviors:

* Static
* Horizontal movement
* Vertical movement
* Diagonal movement
* Random movement
* Accelerating movement
* Short-lived bubbles
* Small fast bubbles
* Large slow bubbles

Difficulty should increase primarily through:

* Smaller targets
* Faster movement
* More simultaneous targets
* Shorter spawn intervals
* More complex movement patterns
* More dangerous targets

---

# 20. Perfect Hit

A perfect hit occurs when the player hits very close to the center of a bubble.

Example:

```text
Normal hit:
+10

Perfect:
+20
PERFECT!
```

Perfect hits should provide:

* Extra points
* Small visual effect
* Sound effect
* Optional combo bonus

The exact center tolerance should be configurable.

---

# 21. Combo System

Consecutive successful hits increase the player's combo.

Example:

```text
5 hits  → ×1.2
10 hits → ×1.5
20 hits → ×2
```

The exact values can be adjusted after testing.

The combo should reward accurate and consistent play.

Possible combo breakers:

* Shooting a black bubble
* Missing a required target
* Other major mistakes

Avoid making the system overly punishing.

---

# 22. Scoring

Scoring should be clear and immediately visible.

Suggested starting values:

```text
Blue bubble       +10
Yellow bubble     +15 total
Red bubble        +10
Green bubble      +10
Purple bubble     +10
White bubble      +25 or more
Black bubble      penalty
Perfect hit       additional bonus
```

These are starting values only and should be tuned through gameplay testing.

Score should be affected by combo multipliers where appropriate.

---

# 23. Health System

Health is represented using hearts.

HUD:

```text
❤️ ❤️ ❤️
```

Rules:

* Black bubble → -1 heart
* Red bubble → +1 heart
* Maximum health → 5 hearts

If health reaches zero in a mode where lives matter:

> Game Over

The game should provide clear feedback when health changes.

---

# 24. Weapons

The game should have multiple weapons.

Initial weapon set:

### 24.1 Pistol

Characteristics:

* Balanced
* Moderate fire rate
* Accurate
* Simple
* Large or infinite reserve ammo

Example HUD:

```text
PISTOL
7 / ∞
```

---

### 24.2 Shotgun

Characteristics:

* Slow fire rate
* Multiple pellets
* Large spread
* Powerful at close/medium target clusters

Example:

```text
SHOTGUN
5 / 30
```

---

### 24.3 SMG

Characteristics:

* Fast firing
* Smaller damage per shot
* Larger magazine
* More difficult to control

Example:

```text
SMG
30 / 120
```

---

### 24.4 Sniper

Characteristics:

* Slow
* Highly accurate
* High damage
* Small magazine

Example:

```text
SNIPER
5 / 25
```

---

### 24.5 Laser

Characteristics:

* Energy-based
* Fast/continuous attack
* Uses energy instead of conventional ammunition

Example:

```text
LASER
100 / 100
```

The exact mechanics can be adjusted during implementation.

---

# 25. Ammo System

The current weapon's ammo must always be visible.

Example:

```text
PISTOL

7 / ∞
```

For limited ammunition:

```text
SHOTGUN

5 / 30
```

The first number represents magazine/current ammo.

The second represents reserve ammunition.

Reload should be performed using the fist gesture.

Ammo should update immediately after firing/reloading.

---

# 26. Weapon HUD

The bottom-left area should display:

```text
┌────────────────────┐
│       PISTOL       │
│                    │
│       🔫           │
│                    │
│       7 / ∞        │
└────────────────────┘
```

The design should remain minimal.

When switching weapons, provide a short transition/notification.

---

# 27. Game Modes

The initial game should contain three primary game modes.

---

## 27.1 Chill Mode

Purpose:

> Relaxed gameplay and aim practice.

Characteristics:

* No strict time pressure
* Slow target movement
* Comfortable spawn rate
* Minimal punishment
* Relaxing gameplay
* Good mode for learning gestures and aiming

The player should be able to practice the mechanics without worrying about high scores.

---

## 27.2 Classic Mode

Purpose:

> Achieve the highest possible score within a fixed time.

Suggested duration:

**60 seconds**

Gameplay:

* Timer starts
* Targets continuously spawn
* Player shoots targets
* Score increases
* Difficulty gradually increases
* Timer reaches zero
* Game ends

The main goal is:

> **Highest Score**

The final results should show whether the player achieved a new high score.

---

## 27.3 Endless Mode

Purpose:

> Survive as long as possible.

Characteristics:

* Limited hearts/lives
* Continuous gameplay
* Difficulty continuously increases
* Dangerous bubbles become more important
* Targets become faster and smaller
* Survival time is tracked
* Score continues increasing

Game ends when:

```text
❤️ = 0
```

Primary statistics:

* Score
* Survival time
* Accuracy
* Best combo

---

# 28. Future Game Modes

Do not implement these initially unless development is ahead of schedule.

Possible future modes:

* Precision
* Time Attack
* Challenge
* Reaction Test
* Boss Mode
* Multiplayer
* Custom Training

These are ideas for future expansion.

---

# 29. Gameplay HUD

The gameplay HUD should be minimal.

Suggested layout:

```text
┌──────────────────────────────────────────────────────┐
│ ❤️ ❤️ ❤️       SCORE: 1,240       ×3       00:42    │
│                                                      │
│                                                      │
│              🔵                 🟡                  │
│                                                      │
│       🔵                         ⚫                 │
│                                                      │
│                         🎯                           │
│                                                      │
│              🔴                 🔵                  │
│                                                      │
│                                                      │
│  PISTOL                                               │
│  7 / ∞                                                │
└──────────────────────────────────────────────────────┘
```

The exact layout can be adjusted according to screen size.

---

# 30. Main Menu

The main menu should be clean and modern.

Suggested structure:

```text
                  HANDSHOT

          Gesture Controlled Aim Game

                    PLAY

                GAME MODES
                  SETTINGS
                   STATS
                HOW TO PLAY
```

Potential additional information:

```text
Camera: Connected
Hand: Detected
```

Do not overcrowd the menu.

---

# 31. Camera Setup

The initial version should support the computer's available webcam.

The game should:

1. Detect available camera devices.
2. Allow the user to select a camera.
3. Show a camera preview.
4. Confirm that a hand is detected.
5. Allow the player to continue into the game.

Display a useful message when no camera is available.

Example:

```text
No camera detected.

Please connect a webcam and try again.
```

---

# 32. Calibration

A calibration system should be included because hand tracking and different camera positions can affect aiming.

Possible calibration flow:

```text
CALIBRATION

Move your index finger to:

1. Top Left
2. Top Right
3. Bottom Right
4. Bottom Left

Calibration complete.
```

The system can use these positions to establish the usable hand-tracking area.

The calibration should help map physical hand movement to the game-screen movement.

---

# 33. Camera Mirroring

Provide an option:

```text
Mirror Camera: ON / OFF
```

Mirroring may make the player's movement feel more natural, similar to looking into a mirror.

The implementation should ensure that the crosshair movement remains intuitive.

---

# 34. Settings

The settings menu should contain multiple categories.

## Aim Settings

* Sensitivity
* X Sensitivity
* Y Sensitivity
* Smoothing
* Deadzone
* Aim Assist

## Crosshair Settings

* Style
* Size
* Thickness
* Opacity
* Color
* Center Dot
* Hit Marker

## Gesture Settings

* Gesture detection sensitivity
* Gesture bindings
* Gesture cooldown where applicable

## Gameplay Settings

* Difficulty
* Camera mirroring
* Screen shake
* Visual effects

## Audio

* Master volume
* Music volume
* SFX volume

Settings should be saved locally.

---

# 35. Aim Assist

Aim assist should be optional.

It should never completely aim for the player.

Possible behavior:

* Slightly attract the crosshair toward nearby targets.
* Reduce the effect when the player is far from the target.
* Allow the player to disable it.

Suggested setting:

```text
Aim Assist
OFF
LOW
MEDIUM
HIGH
```

Default should preferably be **OFF or LOW** for a competitive/aim-focused experience.

---

# 36. Visual Feedback

Every important interaction should provide feedback.

Examples:

### Successful hit

```text
+10
```

### Perfect hit

```text
PERFECT!
+20
```

### Combo

```text
COMBO ×5
```

### Health gained

```text
+❤️
```

### Health lost

```text
-❤️
```

### Weapon switch

```text
SHOTGUN EQUIPPED
```

### Reload

```text
RELOADING...
```

Effects should be short and unobtrusive.

---

# 37. Audio

The game should contain:

* Menu music
* Gameplay music
* Shooting sounds
* Reload sounds
* Hit sounds
* Perfect-hit sound
* Combo sound
* Health gain sound
* Damage sound
* Game-over sound
* Weapon-specific sounds

Audio should be configurable.

Avoid copyrighted assets unless properly licensed.

Use placeholder/free assets during development if necessary.

---

# 38. Animations

Recommended animations:

* Bubble spawn
* Bubble destruction
* Bubble movement
* Score popup
* Perfect-hit effect
* Combo increase
* Weapon switching
* Reload
* Health change
* Game-over transition
* Menu transitions

Animations should prioritize performance and responsiveness.

---

# 39. Difficulty Scaling

Difficulty should increase gradually.

Difficulty can be controlled through:

* Target speed
* Target size
* Spawn frequency
* Number of targets
* Movement patterns
* Special target frequency
* Dangerous target frequency

The player should have enough time to understand each mechanic before the game becomes difficult.

---

# 40. Game States

The application should use clear game states.

Suggested states:

```text
MAIN_MENU
CAMERA_SETUP
CALIBRATION
MODE_SELECT
PLAYING
PAUSED
GAME_OVER
RESULTS
SETTINGS
HOW_TO_PLAY
STATS
```

The implementation should avoid putting all logic into a single Python file/function.

---

# 41. Statistics

The game should track useful statistics locally.

Possible statistics:

* Highest score
* Highest classic score
* Highest endless score
* Longest survival
* Total targets destroyed
* Total shots
* Total hits
* Accuracy
* Highest combo
* Total perfect hits
* Favorite weapon

A statistics screen can display these values.

---

# 42. High Score

High scores should be saved locally.

At minimum:

* Classic high score
* Endless high score
* Endless survival record

After a game:

```text
NEW HIGH SCORE!
```

should appear when applicable.

---

# 43. How To Play

The game should include a simple tutorial.

Example:

```text
☝️ POINT
Move your index finger to aim.

🤏 PINCH
Pinch thumb + index finger to shoot.

✊ FIST
Reload weapon.

✌️ TWO FINGERS
Switch weapon.

✋ OPEN PALM
Pause.

👉 SWIPE
Dash / Deflect.
```

Also explain bubble colors.

The tutorial should be short and visual.

---

# 44. Performance Requirements

The game should prioritize responsiveness.

Goals:

* Smooth hand tracking
* Stable crosshair
* Low perceived input latency
* Consistent game rendering
* No unnecessary camera processing
* Avoid freezing the game while processing frames

Camera processing and game rendering should be designed carefully so that hand tracking does not block the game loop unnecessarily.

If appropriate, use separate processing or efficient frame handling.

---

# 45. Error Handling

The game should gracefully handle:

### Camera unavailable

Display a useful error.

### Hand not detected

Display:

```text
Hand not detected
Please move your hand into view.
```

Do not crash.

### Multiple hands

Initially, the game should preferably use the primary/closest detected hand.

Future versions may support multiple hands.

### Tracking temporarily lost

The crosshair should not teleport unpredictably.

Maintain a reasonable last-known state and smoothly recover when tracking returns.

---

# 46. Project Structure

Use a clean modular structure.

A possible structure:

```text
HANDSHOT/
│
├── main.py
│
├── config/
│   └── settings.py
│
├── camera/
│   ├── camera_manager.py
│   └── hand_tracker.py
│
├── gestures/
│   ├── gesture_detector.py
│   └── gesture_types.py
│
├── aim/
│   ├── aim_controller.py
│   └── smoothing.py
│
├── game/
│   ├── game.py
│   ├── game_state.py
│   ├── player.py
│   ├── target_manager.py
│   ├── bubble.py
│   ├── weapons.py
│   ├── scoring.py
│   └── modes.py
│
├── ui/
│   ├── menu.py
│   ├── hud.py
│   ├── settings_menu.py
│   ├── results_screen.py
│   └── tutorial.py
│
├── audio/
│   └── audio_manager.py
│
├── assets/
│   ├── images/
│   ├── sounds/
│   ├── fonts/
│   └── music/
│
├── data/
│   ├── settings.json
│   └── statistics.json
│
├── requirements.txt
│
└── README.md
```

The exact structure may be adjusted if there is a better architecture, but the project should remain modular.

---

# 47. Development Strategy

IMPORTANT:

**Do NOT attempt to implement the entire project in one step.**

Development must happen incrementally.

Each phase should be tested before moving to the next.

---

## Phase 1 — Camera

Implement:

* OpenCV camera access
* Camera selection
* Camera preview
* Basic error handling

Test:

* Camera opens
* Camera closes correctly
* Frames are received consistently

---

## Phase 2 — Hand Tracking

Implement:

* MediaPipe
* Hand detection
* Hand landmarks
* Index fingertip tracking

Display the hand landmarks during development.

Test:

* Hand detection
* Tracking stability
* Different hand positions
* Temporary tracking loss

---

## Phase 3 — Crosshair

Implement:

* Index fingertip → crosshair
* Coordinate mapping
* Sensitivity
* Smoothing
* Deadzone
* Screen boundaries

This phase is extremely important.

Spend significant time tuning the feeling of the crosshair.

Do not continue until aiming feels responsive and stable.

---

## Phase 4 — Pinch Shooting

Implement:

* Pinch detection
* Shooting event
* Gesture cooldown
* Simple projectile/shot
* Basic target

Test:

```text
Aim → pinch → shot
```

---

## Phase 5 — Basic Bubble Game

Implement:

* Blue bubbles
* Bubble spawning
* Bubble movement
* Collision detection
* Score
* Basic HUD
* Bubble destruction

At this point there should already be a playable prototype.

---

## Phase 6 — Health and Special Bubbles

Add:

* Black bubble
* Red bubble
* Yellow bubble
* Green bubble
* Purple bubble
* White bubble
* Health
* Effects

Test each bubble individually.

---

## Phase 7 — Combo and Perfect Hits

Add:

* Combo
* Multipliers
* Perfect hits
* Score popups
* Hit effects
* Accuracy tracking

---

## Phase 8 — Weapons

Add weapons one at a time.

Recommended order:

1. Pistol
2. Shotgun
3. SMG
4. Sniper
5. Laser

Implement:

* Ammo
* Reserve ammo
* Reload
* Fire rate
* Weapon switching
* Weapon-specific behavior

---

## Phase 9 — Remaining Gestures

Add:

* Open palm → pause
* Two fingers → weapon switch
* Fist → reload
* Swipe → dash/deflect
* Grab/interact

Test each independently.

---

## Phase 10 — Game Modes

Implement:

1. Chill
2. Classic
3. Endless

Each mode should have clearly separated rules.

---

## Phase 11 — Menus and Settings

Implement:

* Main menu
* Mode selection
* Settings
* How to play
* Stats
* Pause menu
* Results screen

---

## Phase 12 — Polish

Improve:

* Animations
* Audio
* Visual effects
* Transitions
* Crosshair
* Bubble designs
* UI
* Performance
* Error handling

---

# 48. Testing Philosophy

After each feature:

1. Implement it.
2. Run the game.
3. Test manually.
4. Identify problems.
5. Fix problems.
6. Only then continue.

Do not accumulate many untested features.

If a feature causes another feature to break, fix the regression before continuing.

---

# 49. Code Quality Requirements

The code should be:

* Modular
* Readable
* Well organized
* Commented where necessary
* Easy to modify
* Avoid unnecessary complexity

Avoid:

* One giant Python file
* Giant functions
* Hardcoded values everywhere
* Duplicate logic
* Unnecessary dependencies

Important values should be configurable.

---

# 50. Configuration

Game constants should not be scattered throughout the code.

Examples:

```text
DEFAULT_SENSITIVITY
SMOOTHING_AMOUNT
PINCH_THRESHOLD
MAX_HEALTH
BUBBLE_SPAWN_RATE
BUBBLE_SPEED
COMBO_THRESHOLDS
WEAPON_STATS
```

Keep these in an appropriate configuration system.

---

# 51. Future Phone Camera Support

This is NOT part of the initial version.

Later, the game may provide:

```text
Camera Source

○ Laptop Webcam
○ USB Webcam
○ Phone Camera
```

Phone camera support could use:

```text
Phone Camera
     ↓
Local Wi-Fi
     ↓
Video Stream
     ↓
Laptop Game
     ↓
OpenCV
     ↓
MediaPipe
```

A future implementation may provide QR-code pairing so the user can easily connect their phone.

Do not implement this until the local webcam version is stable.

---

# 52. Future Web Version

The initial Python version should be considered the prototype.

A future web version may use:

* TypeScript/JavaScript
* Browser camera APIs
* MediaPipe web/Tasks Vision
* HTML Canvas or another web rendering system
* Vercel for deployment

The Python implementation should therefore keep the game mechanics reasonably separated from the computer-vision layer.

The web version will likely require rewriting parts of the implementation rather than directly converting Python code.

---

# 53. Important Implementation Rule

Do not assume that every proposed mechanic must be implemented exactly as described if testing proves that it produces poor gameplay.

The priority order is:

```text
1. Responsiveness
2. Reliability
3. Fun gameplay
4. Clear UI
5. Visual polish
6. Additional features
```

A smaller number of polished mechanics is better than a large number of unreliable mechanics.

---

# 54. Initial MVP

Before implementing the complete game, the minimum playable version should contain only:

```text
Webcam
   ↓
Hand tracking
   ↓
Index finger aiming
   ↓
Smooth crosshair
   ↓
Pinch shooting
   ↓
Blue bubbles
   ↓
Score
```

The MVP should feel good before adding complexity.

---

# 55. Definition of Success

The project should eventually feel like a real game, not a technical demonstration.

A successful player experience should be:

> “I can move my finger naturally, the crosshair follows smoothly, I pinch to shoot, and the game responds instantly.”

The player should not constantly think:

> “Why did the camera not detect my hand?”

or:

> “Why did the crosshair jump?”

or:

> “Why did my pinch fire three times?”

Reliability and responsiveness are therefore critical.

---

# 56. Final Vision

HANDSHOT should combine:

```text
Computer Vision
       +
Hand Tracking
       +
Gesture Recognition
       +
FPS-style Aiming
       +
Arcade Target Shooting
       +
Multiple Weapons
       +
Game Modes
       +
Progression/Statistics
       +
Polished UI
```

The defining feature is:

> **Your hand is the controller.**

The index finger is the crosshair.

The player's gestures become the controls.

The webcam becomes the input device.

The goal is to make this interaction feel natural enough that the player forgets they are controlling the game through a webcam.

---

# 57. Instructions for AI Development Agent

When working on this project:

1. Read this entire `main.md` before modifying the project.
2. Understand the complete architecture and game vision.
3. Do not implement every feature at once.
4. Follow the development phases.
5. Start with the MVP.
6. Test every major feature before proceeding.
7. Preserve existing functionality when adding new features.
8. Do not rewrite working systems unnecessarily.
9. If a design decision is ambiguous, choose the simplest reliable implementation.
10. Prioritize responsiveness and stability.
11. Keep the code modular.
12. Keep important constants configurable.
13. Do not add unnecessary libraries.
14. Do not create unnecessary files.
15. Do not replace working implementations simply for stylistic reasons.
16. When an error occurs, investigate the actual cause before changing unrelated code.
17. After implementing a feature, run/test the relevant part of the application.
18. Clearly report what was implemented and what remains.
19. Never claim a feature works without testing it.
20. If a planned feature cannot be implemented reliably, explain the limitation and propose the simplest alternative.

---

# 58. First Task

Do NOT build the entire game yet.

Begin with **Phase 1 and Phase 2 only**:

### Phase 1

Create a working webcam system using OpenCV.

### Phase 2

Integrate MediaPipe hand tracking.

The first milestone should display:

* Webcam feed
* Detected hand
* Hand landmarks
* Index fingertip position

After this is confirmed to work reliably, proceed to the crosshair implementation.

Do not implement weapons, game modes, bubbles, menus, or advanced gestures during the first milestone.
