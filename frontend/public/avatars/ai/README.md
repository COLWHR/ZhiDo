# AI portrait avatars

Original illustrations generated for ZhiDo with an image-generation model
(Seedream 5.0 Pro), not sourced from any third-party avatar library. No
attribution or external license is required for these files.

## What is here

Eight discipline pools, eight variants each (`<pool>-1.webp` … `<pool>-8.webp`),
512 × 512 WebP:

- `philosophy` — deep green / ivory, classical and knitwear, older and younger scholars
- `psychology` — dusty blue, knitwear and glasses, calm and attentive
- `technology` — dark teal, minimal shirts and jackets, focused
- `business` — ochre / camel, blazers, composed
- `arts` — muted purple, scarves and relaxed tailoring, expressive
- `humanities` — charcoal / taupe, tweed and trench coats, bookish
- `counseling` — counselling blue, cardigans and shawls, warm and reassuring
- `general` — neutral warm tones for ordinary user accounts

The discipline pools are **fictional people**: no real individual's likeness is
reproduced. The three named persona portraits below are stylized, AI-generated
editorial likenesses of the named public figures — not photographs and not
exact reproductions. All share the same visual language — soft flat illustration,
detailed faces, geometric colour blocks, low saturation, warm off-white
background `#EEF0EA`, head-and-shoulders framing, no text, no logo, no frame.

Three named personas have an explicit, persona-specific portrait so their
age and bearing read correctly instead of being picked by hash:

- `portrait-zhangquanling.webp` — 张泉灵
- `portrait-hejiong.webp` — 何炅
- `portrait-marx.webp` — 马克思

These are attached through the persona's `avatar` field (a `/avatars/…` path),
which `resolveIdentityAvatar` now honours before falling back to a pool.

## How it is assigned

`frontend/src/utils/avatar.ts` detects a persona's discipline from its title,
bio, stance and theories, then picks one of the eight variants with a stable
identity hash. Where the title or name makes gender explicit, the chosen
variant matches it, so a female architect never receives a male-coded portrait.
A counsellor always draws from `counseling`; a plain user account draws from
`general`. The same entity therefore gets the same portrait on every page, and
different identities spread across the variants.

Uploaded photos still take precedence; the academic badge remains the last-resort fallback if an image fails to load.
