# ONNELLAB Motion & Product Film Guide

## Purpose

This guide defines the motion language used by ONNELLAB marketing assets and
short product films. It does not change app runtime UI. App-side motion rules
live in `onnellab-flutter-template`.

The core principle is:

> Things do not appear. They become.

Motion should preserve continuity between a user's action, the product state,
and the result. It is not a decoration layer or a showreel.

## Product-film rules

1. **Real product first.** Use real ONNELLAB screens, components, icons, logos,
   recordings, and verified product states. Motion may frame or connect real
   states; it must not invent a screen, capability, success state, option, or
   performance claim.
2. **Continuity before cuts.** When two scenes share the same meaningful object,
   prefer a restrained morph, mask, page push, crop, or spatial hand-off over a
   generic fade. The viewer should understand what became what.
3. **Interaction drives change.** Clicks, taps, drags, scrubs, and selections
   should cause the visual transition. Avoid autonomous decoration that moves
   without a product reason.
4. **One focus per scene.** Camera pushes and scale changes are allowed only to
   clarify the current product action. Continuous zooming is not a brand style.
5. **Actual evidence stays legible.** Product recording remains uncropped where
   correctness would otherwise be ambiguous. Motion graphics must not cover the
   control, input, output, filename, status, or other evidence needed to verify
   the demonstrated workflow.
6. **2D and restrained.** Flat geometry, masks, shape morphs, short springs, and
   bounded accent fields are allowed. Avoid 3D flips, particle bursts, neon,
   lens flare, persistent glow, floating decoration, and effects whose main job
   is to look impressive.
7. **No template theatre.** Repeating the same bento, giant kinetic type,
   floating cards, or beat-on-every-frame treatment across unrelated apps is a
   failure. Each film should inherit the product's own task and visual anchor.
8. **Brand remains secondary to the product.** ONNELLAB wordmark and app icon
   may open or close the film, but the useful workflow is the hero.

## ONNELLAB color and type in motion

- White or authorized Ivory stays the default calm canvas.
- Lilac, Baby Blue, and Soft Peach may be used as bounded brand accents.
- Functional state should not require all three colors at once.
- A decorative multi-color field is allowed only when removing it would not
  remove meaning.
- Do not animate the palette merely because motion is available.
- ONNEL Sans may be used when the production path supports it reliably; until
  then use the current approved fallback and keep typography visually quiet.

## Preferred motion patterns

### State morph

A control can remain the same object while its role changes:

```text
Action -> Progress -> Result
```

Use this when the real product has the corresponding states. Do not create a
fake in-app morph just for the film.

### Shared-object hand-off

A thumbnail, cover, file card, waveform selection, or project tile can become
the next scene's focal object. Preserve recognisable geometry or content so the
viewer understands the relationship.

### Direct manipulation

During a demonstrated drag or scrub, the visual should follow the input. Spring
or settling motion belongs after release, not between the pointer and the value.

### Progress to result

Prefer one visual object resolving into the verified result over an unrelated
success slate. A closing slate may still follow after the result is established.

### Product-led scene construction

Build each scene from the app's actual objects rather than from generic motion
graphics. Marketing polish may reorganize space, but it must not alter what the
product does.

## Marketing-only allowances

Marketing films may be more expressive than app runtime UI:

- object-led transitions between scenes;
- short camera pushes;
- beat-aware cuts or morph timing;
- wordmark or icon transformations at the beginning/end;
- one bounded decorative color field.

These are not automatically authorized inside the app. Runtime UI follows the
Flutter template's motion guidance and accessibility fallbacks.

## Banned defaults

Do not use these as ONNELLAB brand defaults:

- motion-designer showreel density;
- "go all out" effect stacking;
- particle or sparkle bursts;
- repeated glow or neon;
- 3D card flips;
- liquid/glass treatment as a studio-wide identity;
- giant kinetic typography that competes with the product;
- constant camera movement;
- animation on every object;
- a beat event merely because a beat exists.

## Prompt Motion reference set

Prompt Motion is a research gallery, not a component library or a style to copy.
Videos/prompts remain credited to their original creators.

### PM-01 — UI state morph continuity

Source: https://www.prompt-motion.com/twoclipping-5cba86

Keep because:
- one object persists through multiple UI states;
- direct manipulation causes visible state change;
- only tiny overshoot is allowed;
- particles, glow, bouncy easing, and template-like treatment are explicitly
  rejected.

Do not copy:
- beat density;
- camera zoom on every state;
- exact state sequence;
- implementation stack.

Best use:
- conceptual reference for action -> progress -> result continuity.

### PM-02 — Continuous product-film construction

Source: https://www.prompt-motion.com/twoclipping-221cab

Keep because:
- each scene is made from the previous scene;
- shape, mask, push, and object hand-offs replace generic crossfades;
- product interaction drives the sequence.

Do not copy:
- Liquid Glass as ONNELLAB identity;
- effect density;
- exact typography, iris, lens, or wordmark choreography.

Best use:
- App Store/Google Play promo, ONNELLAB Shorts, launch films.

### PM-03 — Real-component product film

Source: https://www.prompt-motion.com/anthonyriera-9b1b2a

Keep because:
- the skill first learns the product design system;
- the film uses real components, logo, and product material;
- motion is derived from the product rather than an unrelated template.

Best use:
- future ONNELLAB product-film automation and renderer evolution.

### PM-04 — Cinetic code-rendered launch-film workflow

Source: https://www.prompt-motion.com/lexnlin-6161a6

Keep because:
- concept, brand, score, and render are treated as one reproducible production
  workflow;
- code-rendered motion can be deterministic and reviewable.

Best use:
- research for the content-engine rendering workflow, not a dependency mandate.

### PM-X — showreel anti-reference

Examples:
- https://www.prompt-motion.com/stephanlivera-df17a2
- https://www.prompt-motion.com/umangratani-57f86a

These are useful examples of what **not** to make the default ONNELLAB language:
dense "go all out" showreel motion demonstrates the creator more than the product.

## Reference interpretation rule

A reference proves only the decision named under "Keep because." It does not
authorize copying the source's full composition, brand, timing, effects, code,
assets, music, or product behavior.

If a reference conflicts with:
- verified app behavior;
- app/product SoT;
- store policy;
- accessibility;
- actual recording evidence;
- ONNELLAB brand constraints;

the reference loses.

## Relationship to the current Shorts runtime

The current Shorts renderer remains governed by `Short_Video_Pipeline.md`.
This guide is a design-direction contract and does not imply that every motion
pattern above is already implemented.

When the renderer is extended, prefer reusable continuity primitives over
one-off per-app effects, and keep deterministic video flows tied to real product
recordings.
