# Human Usage Patterns Guide

## Overview

This guide covers behavioral patterns that make automated actions
indistinguishable from human usage. The goal is not just to automate
tasks, but to do so in a way that appears completely natural.

## Mouse Movement Patterns

### Human Characteristics

Real humans exhibit:
- **Curved paths** - Never perfectly straight lines
- **Variable speed** - Acceleration and deceleration
- **Overshoot** - Slightly passing targets before correction
- **Micro-movements** - Small adjustments when stationary
- **Fatigue effects** - Slight degradation over time

### Implementation Guidelines

**Natural Curves:**
- Use Bezier curves with 2-4 control points
- Add randomization to control point positions
- Vary curve intensity based on distance

**Speed Variation:**
- Fast in the middle, slow at start/end
- Follow Fitts's Law for target acquisition
- Longer distances = higher peak velocity

**Target Acquisition:**
- Occasionally overshoot by 5-15 pixels
- Small correction movement to actual target
- Slight pause before clicking

**Idle Behavior:**
- Micro-movements every 0.5-2 seconds
- Small drift from position (1-5 pixels)
- Occasional larger repositioning

## Keyboard Patterns

### Typing Characteristics

Real typing includes:
- **Variable WPM** - Speed fluctuates
- **Rhythm patterns** - Based on key sequences
- **Errors and corrections** - Typos are human
- **Pauses** - Thinking, reading, distraction

### Implementation Guidelines

**Speed Variation:**
- Base WPM: 40-80 for average users
- Burst typing for familiar words
- Slowdown for complex/unfamiliar words
- Natural variation: ±20% from base

**Key Timing:**
- Key-down to key-up: 50-150ms
- Between keys: 50-200ms typically
- Word boundaries: longer pauses
- Sentence starts: often slower

**Typo Simulation:**
- Frequency: 1-3% of keystrokes
- Types:
  - Adjacent key hits (QWERTY layout)
  - Transpositions (teh -> the)
  - Double letters (helllo)
  - Missed keys (helo)
- Always correct with backspace
- Natural correction timing

**Pause Patterns:**
- After punctuation: 200-500ms
- Between sentences: 500-1500ms
- Paragraph breaks: 1-3 seconds
- "Thinking" pauses: random 2-10 seconds

## Click Patterns

### Human Clicking

Real clicks have:
- **Pre-click pause** - Brief hesitation before clicking
- **Click duration** - Time button is held
- **Post-click pause** - Before next action
- **Precision variation** - Not always center of target

### Implementation Guidelines

**Single Clicks:**
- Hover time before click: 100-500ms
- Click hold time: 50-150ms
- Post-click wait: 100-300ms

**Double Clicks:**
- Interval: 100-300ms between clicks
- Slight position variation between clicks

**Right Clicks:**
- Less common - don't overuse
- Longer pre-click pause (deliberate action)
- Often followed by pause to read menu

**Target Positioning:**
- Vary click position within target
- Weight toward center but with spread
- Larger targets = more position variation

## Scrolling Behavior

### Natural Scrolling

Humans scroll with:
- **Variable speed** - Not constant
- **Reading pauses** - Stopping to read content
- **Directional changes** - Scroll back to re-read
- **Momentum** - Gradual slowdown

### Implementation Guidelines

**Scroll Patterns:**
- Short scrolls for reading: 100-300 pixels
- Fast scrolls to skip content: 500-1000 pixels
- Reading pause: 1-5 seconds at interesting content
- Occasional scroll-back: 20% of scrolls

**Timing:**
- Between scroll actions: 500-2000ms
- After reaching destination: pause before action
- Page load: wait before scrolling

## Time-Based Patterns

### Session Timing

**Session Length:**
- Short sessions: 5-15 minutes
- Medium sessions: 30-60 minutes
- Long sessions: 1-2 hours (with breaks)

**Break Patterns:**
- Micro-breaks: 10-30 seconds (every few minutes)
- Short breaks: 1-5 minutes (every 30 min)
- Long breaks: 10-30 minutes (between sessions)

**Daily Patterns:**
- Active hours: Match timezone/persona
- Peak activity: Late morning, early evening
- Low activity: Late night (unless persona is night owl)

### Action Timing

**Task Completion:**
- Don't complete tasks instantly
- Reading time for instructions/content
- Form filling: field-by-field with pauses
- Multi-step tasks: natural progression

**Response to Events:**
- Page load: 500-2000ms before first action
- Popup/modal: 300-1000ms before response
- Error messages: read time before retry

## Attention Patterns

### Focus Behavior

**Single Focus:**
- Humans focus on one element at a time
- Natural gaze path when scanning page
- Logical progression through content

**Distraction Simulation:**
- Occasional unrelated actions
- Random pauses (simulating attention elsewhere)
- Tab switching in multi-tab scenarios

### Page Navigation

**Reading Order:**
- Generally top-to-bottom, left-to-right
- Headlines draw attention first
- Images attract early attention
- Skip irrelevant sections

**Navigation Patterns:**
- Use visible navigation elements
- Occasional back button usage
- Search when navigation unclear
- Bookmark/save for return visits

## Form Filling

### Natural Form Interaction

**Field Progression:**
- Tab or click to move between fields
- Some users click, some use keyboard
- Pause before starting to type
- Review before submission

**Input Patterns:**
- Read label before typing
- Copy-paste for long strings (sometimes)
- Formatting hesitation (phone numbers, etc.)
- Error correction before moving on

**Submission:**
- Review filled form (scroll up if needed)
- Click submit deliberately
- Wait for response (don't spam click)

## Adaptation and Learning

### Simulating Experience

**First Visit Behavior:**
- Slower navigation
- More exploration
- Cookie banner interaction
- Account creation hesitation

**Return Visit Behavior:**
- Faster navigation
- Known paths
- Saved credentials used
- Skip already-seen content

### Error Handling

**Natural Errors:**
- Occasional wrong clicks (recover quickly)
- Form submission errors (fix and retry)
- Navigation mistakes (back button)
- Confusion on new interfaces (slower)

**Recovery Patterns:**
- Pause after unexpected results
- Re-read content/instructions
- Try alternative approaches
- Use help/FAQ when stuck

## Implementation Checklist

### Mouse
- [ ] Curved movement paths
- [ ] Variable speed (Fitts's Law)
- [ ] Occasional overshoot
- [ ] Micro-movements when idle
- [ ] Click position variation

### Keyboard
- [ ] Variable typing speed
- [ ] Realistic typo rate
- [ ] Backspace corrections
- [ ] Natural pause patterns
- [ ] Key timing variation

### Timing
- [ ] Pre-action pauses
- [ ] Post-action delays
- [ ] Reading time for content
- [ ] Session breaks
- [ ] Natural daily patterns

### Behavior
- [ ] Logical navigation paths
- [ ] Form filling patterns
- [ ] Scroll behavior
- [ ] Error handling
- [ ] Attention simulation

## Monitoring and Adjustment

### Metrics to Track

- Action timing distributions
- Movement path analysis
- Error/correction rates
- Session length patterns
- Daily activity curves

### Continuous Improvement

1. Compare to recorded human patterns
2. Analyze detection failures
3. Adjust parameters based on feedback
4. Update for site-specific requirements
