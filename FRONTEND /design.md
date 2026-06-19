---
name: openclaw-design-v4
description: Builds premium dark-mode websites for local businesses (gyms, clinics, real estate, restaurants) using a Brutalist, 3D Glassmorphism, and Vibe Code design system. Includes fluid typography, CSS 3D effects, Three.js backgrounds, glassmorphism surfaces, scroll animations, magnetic CTAs, and niche-specific presets. Deploy-ready with Tailwind CDN and Vercel.
---

# SKILL: OpenClaw Premium Design System V4
### Built for AI Automation Agencies — by Hemant Kadam × OpenClaw Ecosystem 2026

---

## 🧠 Design Philosophy

> "Every site we deploy is a weapon. It converts. It intimidates. It sells."

OpenClaw V4 merges three aesthetic pillars into one unified system:

| Pillar | Vibe | When to Use |
|---|---|---|
| **Brutalist Dark** | Raw power, editorial weight | Gyms, agencies, studios, legal |
| **3D Glassmorphism** | Depth, premium feel, spatial UI | SaaS, clinics, beauty, fintech |
| **Vibe Code / Acid** | Trendy, generative, hyper-modern | Restaurants, fashion, creators |

Every deployment MUST pick ONE primary pillar and use the others as accents only.

---

## 🎨 Core Color System

### Primary Palette (Universal)
```css
:root {
  /* Foundation */
  --clr-void:     #000000;   /* Pure black — main bg */
  --clr-carbon:   #050505;   /* Near black — card bg */
  --clr-graphite: #0D0D0D;   /* Section bg */
  --clr-smoke:    #1A1A1A;   /* Border, divider */

  /* Acid Accent Stack (Brutalist) */
  --clr-acid:     #DFFF00;   /* Primary CTA — Acid Yellow */
  --clr-lime:     #CCFF00;   /* Hover state */
  --clr-volt:     #AAFF00;   /* Active / pressed */

  /* Neon Accent Stack (3D / Vibe) */
  --clr-cyan:     #00FFFF;   /* 3D highlight */
  --clr-ice:      #E0F7FA;   /* Glass surface text */
  --clr-plasma:   #BF5AF2;   /* Purple glow accent */
  --clr-ember:    #FF6B35;   /* Warm contrast CTA */

  /* Typography */
  --clr-text-primary:   #FFFFFF;
  --clr-text-secondary: #888888;
  --clr-text-muted:     #444444;
}
```

### Trending 2026 Color Combos
```
Combo 1 — "Acid Agency":    #000000 + #DFFF00 + #FFFFFF
Combo 2 — "Glacier SaaS":   #050505 + #00FFFF + #BF5AF2
Combo 3 — "Ember Studio":   #0D0D0D + #FF6B35 + #DFFF00
Combo 4 — "Void Minimal":   #000000 + #FFFFFF + #1A1A1A (text only)
Combo 5 — "Chrome Vibe":    #0A0A0A + #C0C0C0 (silver) + #FF3366
```

---

## 🔤 Typography System

### Font Stack by Pillar

| Role | Brutalist | 3D / Glass | Vibe Code |
|---|---|---|---|
| **Hero / Display** | Syncopate | Space Grotesk | Cabinet Grotesk |
| **Body / UI** | Outfit | DM Sans | Satoshi |
| **Serif Accent** | Playfair Display | Cormorant Garamond | EB Garamond |
| **Mono / Code** | JetBrains Mono | Fira Code | Geist Mono |

### Google Fonts CDN Import (Pick one set per site)
```html
<!-- BRUTALIST SET -->
<link href="https://fonts.googleapis.com/css2?family=Syncopate:wght@400;700&family=Outfit:wght@300;400;500;700&family=Playfair+Display:ital,wght@0,700;1,400&display=swap" rel="stylesheet">

<!-- 3D GLASS SET -->
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;700&family=DM+Sans:ital,wght@0,400;0,500;1,300&family=Cormorant+Garamond:ital,wght@1,300&display=swap" rel="stylesheet">

<!-- VIBE CODE SET -->
<link href="https://fonts.googleapis.com/css2?family=Cabinet+Grotesk:wght@300;400;700;800&family=Satoshi:wght@400;500;700&family=Geist+Mono:wght@400&display=swap" rel="stylesheet">
```

### Fluid Typography (Clamp Scale)
```css
:root {
  --fs-hero:    clamp(3.5rem, 10vw, 9rem);     /* Main headline */
  --fs-title:   clamp(2rem, 5vw, 4.5rem);      /* Section titles */
  --fs-heading: clamp(1.5rem, 3vw, 2.5rem);    /* Card headings */
  --fs-lead:    clamp(1.1rem, 2vw, 1.4rem);    /* Lead paragraph */
  --fs-body:    clamp(0.9rem, 1.5vw, 1.1rem);  /* Body text */
  --fs-caption: clamp(0.7rem, 1vw, 0.85rem);   /* Labels, captions */
  --fs-mono:    clamp(0.75rem, 1vw, 0.9rem);   /* Code, tags */
}
```

---

## 🧊 3D Design System (NEW in V4)

### CSS 3D Card Effect
```css
.card-3d {
  transform-style: preserve-3d;
  perspective: 1000px;
  transition: transform 0.4s cubic-bezier(0.23, 1, 0.32, 1);
}

.card-3d:hover {
  transform: rotateY(-8deg) rotateX(4deg) translateZ(20px);
}

.card-3d::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.08), transparent 60%);
  border-radius: inherit;
  pointer-events: none;
}
```

### Glassmorphism Surface
```css
.glass {
  background: rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  box-shadow:
    0 8px 32px rgba(0,0,0,0.4),
    inset 0 1px 0 rgba(255,255,255,0.1);
}

.glass-acid {
  border-color: rgba(223, 255, 0, 0.2);
  box-shadow:
    0 8px 32px rgba(223, 255, 0, 0.08),
    inset 0 1px 0 rgba(223, 255, 0, 0.1);
}

.glass-cyan {
  border-color: rgba(0, 255, 255, 0.2);
  box-shadow:
    0 0 40px rgba(0,255,255,0.08),
    inset 0 1px 0 rgba(0,255,255,0.12);
}
```

### 3D Floating Orbs (Background Atmosphere)
```css
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.15;
  pointer-events: none;
  animation: orb-drift 8s ease-in-out infinite alternate;
}

.orb-1 {
  width: 600px; height: 600px;
  background: radial-gradient(circle, #DFFF00, transparent 70%);
  top: -200px; left: -100px;
  animation-delay: 0s;
}

.orb-2 {
  width: 400px; height: 400px;
  background: radial-gradient(circle, #BF5AF2, transparent 70%);
  bottom: -100px; right: -50px;
  animation-delay: -4s;
}

.orb-3 {
  width: 300px; height: 300px;
  background: radial-gradient(circle, #00FFFF, transparent 70%);
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  animation-delay: -2s;
}

@keyframes orb-drift {
  0%   { transform: translate(0, 0) scale(1); }
  100% { transform: translate(40px, -30px) scale(1.1); }
}
```

### Three.js Floating Geometry (Loader Snippet)
```html
<!-- Drop inside <body> for 3D background mesh -->
<canvas id="bg-canvas" style="position:fixed;inset:0;z-index:-1;opacity:0.3;"></canvas>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(75, innerWidth/innerHeight, 0.1, 1000);
  const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('bg-canvas'), alpha: true });
  renderer.setSize(innerWidth, innerHeight);
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  cam.position.z = 5;

  const geo = new THREE.IcosahedronGeometry(1.5, 1);
  const mat = new THREE.MeshBasicMaterial({ color: 0xDFFF00, wireframe: true });
  const mesh = new THREE.Mesh(geo, mat);
  scene.add(mesh);

  (function animate() {
    requestAnimationFrame(animate);
    mesh.rotation.x += 0.002;
    mesh.rotation.y += 0.003;
    renderer.render(scene, cam);
  })();

  window.addEventListener('resize', () => {
    cam.aspect = innerWidth/innerHeight;
    cam.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
  });
</script>
```

### CSS-Only 3D Text Effect
```css
.text-3d {
  color: var(--clr-acid);
  text-shadow:
    1px 1px 0px #aacc00,
    2px 2px 0px #88aa00,
    3px 3px 0px #667700,
    4px 4px 0px #445500,
    5px 5px 15px rgba(223,255,0,0.3);
  letter-spacing: -0.02em;
}

.text-chrome {
  background: linear-gradient(180deg, #fff 0%, #888 50%, #fff 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
```

---

## ✨ Motion & Animation System

### Bézier Curves (Apple-Grade)
```css
:root {
  --ease-smooth:   cubic-bezier(0.23, 1, 0.32, 1);       /* Default UI */
  --ease-spring:   cubic-bezier(0.34, 1.56, 0.64, 1);    /* Bounce-in */
  --ease-sharp:    cubic-bezier(0.4, 0, 0.2, 1);          /* Material */
  --ease-expo:     cubic-bezier(0.16, 1, 0.3, 1);         /* Expo out */
  --ease-brutal:   cubic-bezier(0.77, 0, 0.175, 1);       /* Aggressive */
}
```

### Entrance Animations (Scroll-Triggered)
```css
/* Base state — hidden */
.reveal {
  opacity: 0;
  transform: translateY(40px);
  transition: opacity 0.7s var(--ease-smooth), transform 0.7s var(--ease-smooth);
}

/* Active state — triggered by IntersectionObserver */
.reveal.in-view {
  opacity: 1;
  transform: translateY(0);
}

/* Stagger children */
.stagger > * { transition-delay: calc(var(--i) * 80ms); }
```

```js
// Scroll reveal — add to every deployment
const observer = new IntersectionObserver(
  (entries) => entries.forEach(e => e.isIntersecting && e.target.classList.add('in-view')),
  { threshold: 0.15 }
);
document.querySelectorAll('.reveal').forEach((el, i) => {
  el.style.setProperty('--i', i);
  observer.observe(el);
});
```

### Magnetic Button Effect (Vibe CTA)
```js
document.querySelectorAll('.btn-magnetic').forEach(btn => {
  btn.addEventListener('mousemove', (e) => {
    const rect = btn.getBoundingClientRect();
    const x = (e.clientX - rect.left - rect.width / 2) * 0.3;
    const y = (e.clientY - rect.top - rect.height / 2) * 0.3;
    btn.style.transform = `translate(${x}px, ${y}px)`;
  });
  btn.addEventListener('mouseleave', () => {
    btn.style.transform = 'translate(0, 0)';
    btn.style.transition = 'transform 0.5s var(--ease-spring)';
  });
});
```

### Text Scramble Effect (Hero Titles)
```js
class TextScramble {
  constructor(el) {
    this.el = el;
    this.chars = '!<>-_\\/[]{}—=+*^?#________';
    this.update = this.update.bind(this);
  }
  setText(newText) {
    const len = Math.max(this.el.innerText.length, newText.length);
    return new Promise(resolve => {
      let frame = 0;
      const queue = [...newText].map((to, i) => ({
        from: this.el.innerText[i] || '',
        to, start: Math.floor(Math.random() * 10),
        end: Math.floor(Math.random() * 10) + 10, char: ''
      }));
      const tick = () => {
        let output = '', complete = 0;
        queue.forEach(item => {
          if (frame >= item.end) { complete++; output += item.to; }
          else if (frame >= item.start) {
            item.char = this.chars[Math.floor(Math.random() * this.chars.length)];
            output += `<span style="opacity:0.4">${item.char}</span>`;
          } else output += item.from;
        });
        this.el.innerHTML = output;
        if (complete < queue.length) { requestAnimationFrame(tick); frame++; } else resolve();
      };
      requestAnimationFrame(tick);
    });
  }
}
// Usage: new TextScramble(document.querySelector('h1')).setText('Your Agency Name');
```

---

## 🏗️ Layout System

### Section Templates

```css
/* Full-bleed hero */
.hero {
  min-height: 100svh;
  display: grid;
  place-items: center;
  padding: clamp(2rem, 8vw, 8rem) clamp(1rem, 5vw, 6rem);
  position: relative;
  overflow: hidden;
}

/* Content section */
.section {
  padding: clamp(4rem, 10vw, 10rem) clamp(1rem, 5vw, 6rem);
  max-width: 1400px;
  margin: 0 auto;
}

/* Brutalist grid */
.grid-brutal {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1px;          /* 1px gap = outline effect on dark bg */
  background: var(--clr-smoke);
}

.grid-brutal > * {
  background: var(--clr-carbon);
  padding: 2.5rem;
}

/* Asymmetric hero split */
.hero-split {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 4rem;
  align-items: center;
}

@media (max-width: 768px) {
  .hero-split { grid-template-columns: 1fr; }
}
```

### Brutalist CTA Button
```css
.btn-acid {
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
  background: var(--clr-acid);
  color: #000;
  font-family: var(--font-hero);
  font-size: var(--fs-body);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 1.1rem 2.5rem;
  border: none;
  cursor: pointer;
  position: relative;
  transition: transform 0.2s var(--ease-brutal), box-shadow 0.2s;
  clip-path: polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 0 100%);
}

.btn-acid:hover {
  transform: translate(-3px, -3px);
  box-shadow: 6px 6px 0 rgba(223, 255, 0, 0.4);
}

.btn-acid:active {
  transform: translate(0, 0);
  box-shadow: none;
}

/* Ghost variant */
.btn-ghost {
  background: transparent;
  border: 1px solid rgba(255,255,255,0.2);
  color: var(--clr-text-primary);
  transition: border-color 0.3s, background 0.3s;
}
.btn-ghost:hover {
  border-color: var(--clr-acid);
  background: rgba(223,255,0,0.05);
  color: var(--clr-acid);
}
```

---

## 🌊 Texture & Surface System

### Grain Noise Overlay (Premium Finish)
```css
/* grain.svg — embed as data URI */
.noise {
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: none;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
  opacity: 0.04;
  mix-blend-mode: overlay;
}
```

### Scanline Effect
```css
.scanlines::after {
  content: '';
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0,0,0,0.03) 2px,
    rgba(0,0,0,0.03) 4px
  );
  pointer-events: none;
}
```

### Grid / Dot Background
```css
.bg-grid {
  background-image:
    linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
  background-size: 48px 48px;
}

.bg-dots {
  background-image: radial-gradient(rgba(255,255,255,0.08) 1px, transparent 1px);
  background-size: 28px 28px;
}
```

---

## 📐 Component Library

### Stat Card (Social Proof)
```html
<div class="stat-card glass">
  <span class="stat-number" data-target="847">0</span>
  <span class="stat-suffix">+</span>
  <p class="stat-label">Sites Deployed</p>
</div>
```
```css
.stat-card {
  padding: 2rem 2.5rem;
  text-align: center;
}
.stat-number {
  font-family: var(--font-hero);
  font-size: clamp(3rem, 6vw, 5rem);
  font-weight: 700;
  color: var(--clr-acid);
  line-height: 1;
  display: block;
}
.stat-label {
  font-size: var(--fs-caption);
  text-transform: uppercase;
  letter-spacing: 0.15em;
  color: var(--clr-text-secondary);
  margin-top: 0.5rem;
}
```

### Marquee / Ticker (Logo Strip)
```html
<div class="ticker" aria-hidden="true">
  <div class="ticker-track">
    <span>GYMS</span><span>★</span><span>CLINICS</span><span>★</span>
    <span>REAL ESTATE</span><span>★</span><span>RESTAURANTS</span><span>★</span>
    <!-- duplicate for seamless loop -->
  </div>
</div>
```
```css
.ticker { overflow: hidden; border-top: 1px solid var(--clr-smoke); border-bottom: 1px solid var(--clr-smoke); padding: 0.75rem 0; }
.ticker-track { display: flex; gap: 3rem; width: max-content; animation: ticker 20s linear infinite; font-family: var(--font-hero); font-size: var(--fs-caption); text-transform: uppercase; letter-spacing: 0.2em; color: var(--clr-text-secondary); }
@keyframes ticker { from { transform: translateX(0); } to { transform: translateX(-50%); } }
```

### FOMO Badge
```css
.fomo-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(223,255,0,0.08);
  border: 1px solid rgba(223,255,0,0.25);
  border-radius: 100px;
  padding: 0.4rem 1rem;
  font-size: var(--fs-caption);
  font-weight: 500;
  color: var(--clr-acid);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}
.fomo-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--clr-acid);
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.5;transform:scale(1.5)} }
```

---

## 🚀 Deployment Instructions

### Zero-Build Stack (Standard)
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{BUSINESS_NAME}}</title>
  <!-- Tailwind CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Animate.css -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css">
  <!-- Fonts (pick one set from Typography section above) -->
  <!-- Your design tokens go here as <style> -->
</head>
<body class="bg-black text-white">
  <div class="noise" aria-hidden="true"></div>
  <!-- Content -->
  <script>
    /* Scroll reveal, magnetic buttons, counter animations */
  </script>
</body>
</html>
```

### Tailwind Config (Custom Tokens)
```html
<script>
  tailwind.config = {
    theme: {
      extend: {
        colors: {
          acid: '#DFFF00',
          void: '#000000',
          carbon: '#050505',
          smoke: '#1A1A1A',
          cyan: '#00FFFF',
          plasma: '#BF5AF2',
          ember: '#FF6B35',
        },
        fontFamily: {
          hero: ['Syncopate', 'sans-serif'],
          body: ['Outfit', 'sans-serif'],
          serif: ['Playfair Display', 'serif'],
          mono: ['JetBrains Mono', 'monospace'],
        }
      }
    }
  }
</script>
```

### Vercel Deploy Command
```bash
npx vercel --prod --yes --public
```

---

## 🏆 Niche Presets

### Gym / Fitness
- Pillar: **Brutalist**
- Hero font: Syncopate 700
- Accent: `#DFFF00` (Acid)
- 3D: Wireframe icosahedron background
- Tone: Aggressive, raw, powerful
- Key sections: Hero + Stats + Transformation gallery + Pricing + FOMO CTA

### Medical / Clinic
- Pillar: **3D Glassmorphism**
- Hero font: Space Grotesk 300
- Accent: `#00FFFF` (Cyan) or `#FFFFFF`
- 3D: Subtle orbs (reduced opacity 0.06)
- Tone: Clean, trustworthy, premium
- Key sections: Hero + Services + Credentials + Testimonials + Booking

### Real Estate
- Pillar: **Brutalist + Serif accent**
- Hero font: Syncopate / Playfair combo
- Accent: `#C0A060` (Gold) replacing Acid
- 3D: Parallax image layers
- Tone: Luxury, architectural
- Key sections: Hero + Properties + Agent profile + Contact

### Restaurant / Café
- Pillar: **Vibe Code / Acid**
- Hero font: Cabinet Grotesk 800
- Accent: `#FF6B35` (Ember)
- 3D: Floating fruit/food CSS shapes
- Tone: Playful, warm, inviting
- Key sections: Hero + Menu preview + Story + Gallery + Reservation

---

## ✅ Pre-Deploy QA Checklist

```
[ ] Grainy noise overlay applied (opacity 0.04)
[ ] All font sizes use clamp() fluid scaling
[ ] 3D element present (orbs / wireframe / glass card)
[ ] Scroll reveal on at least 3 sections
[ ] Magnetic CTA button active
[ ] FOMO badge visible above hero CTA
[ ] Counter animation on stats (if present)
[ ] Mobile breakpoints tested at 375px
[ ] Vercel deployment URL captured for email
[ ] Meta title, description set to business name/niche
[ ] Favicon generated (use business initial on acid bg)
[ ] Page speed: LCP < 2.5s (no unoptimized images)
```

---

*OpenClaw Design System V4 — Hemant Kadam × OpenClaw Ecosystem 2026*
*"We don't build websites. We build conversion machines."*
