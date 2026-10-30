#!/usr/bin/env python3
"""Genera las imágenes de assets/ con la identidad visual de joelsuarez.dev.

GitHub sirve los SVG de un repositorio con la cabecera CSP
`default-src 'none'; style-src 'unsafe-inline'`: un SVG puede animarse con CSS,
pero no puede cargar fuentes ni imágenes. Por eso todo el texto se convierte en
trazos con las fuentes de la web (Anton y Montserrat), y la vitrina con capturas
de Delicius se arma como WebP con Pillow.

Uso: python3 scripts/build.py
Las fuentes, los íconos y las capturas salen de la carpeta public/ del portafolio
(variable de entorno PORTFOLIO_PUBLIC).
"""
import os
from html import escape
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont

PUBLIC = Path(os.environ.get("PORTFOLIO_PUBLIC", "/home/joel/astro-projects/joel-suarez-portfolio/public"))
OUT = Path(__file__).resolve().parent.parent / "assets"

# Paleta de la web (src/styles/global.css).
INK = "#050c17"
INK2 = "#0b1626"
LINE = "#1c2a40"
EDGE = "#2a3b57"
NAVY = "#0c3a62"
LEMON = "#f2e96d"
WHITE = "#ffffff"
SOFT = "#c8cfdb"
MUTED = "#8f9bb0"
MINT = "#3ddc97"
CORAL = "#ff7a59"
SKY = "#7cc4ff"

WHATSAPP = "https://wa.me/573227632472"


# --- Texto como trazos -------------------------------------------------------

def num(value):
    return f"{value:.1f}".rstrip("0").rstrip(".")


def kerning(font):
    """Pares de interletraje de la función `kern` (GPOS, tipo 2 en sus dos formatos)."""
    pairs, classes = {}, []
    if "GPOS" not in font:
        return pairs, classes
    table = font["GPOS"].table
    indices = sorted({i for record in table.FeatureList.FeatureRecord
                      if record.FeatureTag == "kern" for i in record.Feature.LookupListIndex})
    for index in indices:
        lookup = table.LookupList.Lookup[index]
        for sub in lookup.SubTable:
            kind = lookup.LookupType
            if kind == 9:
                kind, sub = sub.ExtensionLookupType, sub.ExtSubTable
            if kind != 2:
                continue
            if sub.Format == 1:
                for first, pairset in zip(sub.Coverage.glyphs, sub.PairSet):
                    for record in pairset.PairValueRecord:
                        value = getattr(record.Value1, "XAdvance", 0) or 0
                        pairs.setdefault((first, record.SecondGlyph), value)
            elif sub.Format == 2:
                classes.append((set(sub.Coverage.glyphs), sub.ClassDef1.classDefs,
                                sub.ClassDef2.classDefs, sub.Class1Record))
    return pairs, classes


class Font:
    """Una fuente lista para convertir texto en trazos SVG."""

    def __init__(self, file, weight=None):
        font = TTFont(PUBLIC / "fonts" / file)
        if weight is not None:
            font = instancer.instantiateVariableFont(font, {"wght": weight})
        self.upm = font["head"].unitsPerEm
        self.cap = font["OS/2"].sCapHeight / self.upm
        self.cmap = font.getBestCmap()
        self.glyphs = font.getGlyphSet()
        self.hmtx = font["hmtx"]
        self.pairs, self.classes = kerning(font)

    def kern(self, left, right):
        if (left, right) in self.pairs:
            return self.pairs[left, right]
        for covered, first, second, records in self.classes:
            if left in covered:
                value = records[first.get(left, 0)].Class2Record[second.get(right, 0)].Value1
                return getattr(value, "XAdvance", 0) or 0
        return 0

    def steps(self, text, size, track):
        scale = size / self.upm
        names = [self.cmap.get(ord(ch), ".notdef") for ch in text]
        for i, name in enumerate(names):
            last = i + 1 == len(names)
            advance = self.hmtx[name][0] + (0 if last else self.kern(name, names[i + 1]))
            yield name, advance * scale + (0 if last else track)

    def width(self, text, size, track=0):
        return sum(step for _, step in self.steps(text, size, track))

    def path(self, text, x, y, size, track=0):
        scale = size / self.upm
        parts = []
        for name, step in self.steps(text, size, track):
            pen = SVGPathPen(self.glyphs, ntos=num)
            self.glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, y)))
            parts.append(pen.getCommands())
            x += step
        return "".join(parts)


ANTON = Font("anton-latin.woff")
M500 = Font("montserrat-latin.woff", 500)
M600 = Font("montserrat-latin.woff", 600)
M700 = Font("montserrat-latin.woff", 700)
M800 = Font("montserrat-latin.woff", 800)


def text(font, value, x, y, size, fill, track=0, anchor="start", attrs=""):
    """Un texto convertido en un único <path>; devuelve el SVG y su ancho."""
    width = font.width(value, size, track)
    if anchor == "middle":
        x -= width / 2
    elif anchor == "end":
        x -= width
    return f'<path d="{font.path(value, x, y, size, track)}" fill="{fill}"{attrs}/>', width


def wrap(font, value, size, width):
    lines, line = [], ""
    for word in value.split():
        candidate = f"{line} {word}".strip()
        if line and font.width(candidate, size) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    return lines + [line]


# --- Piezas comunes ----------------------------------------------------------

def document(name, width, height, title, body, style=""):
    css = f"<style>{style}</style>" if style else ""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">'
           f"<title>{escape(title)}</title>{css}{''.join(body)}</svg>\n")
    (OUT / name).write_text(svg, encoding="utf-8")
    return len(svg)


def backdrop(width, height, glow=("88%", "8%"), radius=28):
    """Fondo de tinta con la cuadrícula de plano y un resplandor azul, como la web."""
    gx, gy = glow
    return (
        "<defs>"
        f'<clipPath id="card"><rect width="{width}" height="{height}" rx="{radius}"/></clipPath>'
        '<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">'
        '<path d="M40 0H0V40" fill="none" stroke="#132641"/></pattern>'
        f'<radialGradient id="glow" cx="{gx}" cy="{gy}" r="75%">'
        f'<stop offset="0" stop-color="{NAVY}" stop-opacity=".85"/>'
        f'<stop offset="1" stop-color="{NAVY}" stop-opacity="0"/></radialGradient>'
        "</defs>"
        f'<g clip-path="url(#card)"><rect width="{width}" height="{height}" fill="{INK}"/>'
        f'<rect width="{width}" height="{height}" fill="url(#grid)" opacity=".55"/>'
        f'<rect width="{width}" height="{height}" fill="url(#glow)"/></g>'
    )


def logo(x, y, height, fill=LEMON):
    """Los dos bloques cortados del logo de la web (viewBox 165x312)."""
    scale = height / 312
    shapes = ([(0, 0), (165, 0), (165, 75), (0, 156)], [(165, 103), (165, 238), (18, 312), (18, 178)])
    polygons = "".join(
        f'<polygon points="{" ".join(f"{num(x + px * scale)},{num(y + py * scale)}" for px, py in shape)}" fill="{fill}"/>'
        for shape in shapes)
    return polygons, 165 * scale


def icon(slug, x, y, size, fill):
    source = (PUBLIC / "icons" / f"{slug}.svg").read_text()
    paths = "".join(f'<path d="{d}"/>' for d in __import__("re").findall(r'\sd="([^"]+)"', source))
    return f'<g transform="translate({num(x)} {num(y)}) scale({num(size / 24)})" fill="{fill}">{paths}</g>'


def keyframes(name, frames):
    return f"@keyframes {name}{{{''.join(f'{num(at)}%{{{rule}}}' for at, rule in frames)}}}"


# --- Portada -----------------------------------------------------------------

VERBS = ["RESPONDE", "COBRA", "FACTURA", "VENDE", "TRABAJA"]
STEPS = [
    ("Tu cliente escribe", "Por WhatsApp, como siempre."),
    ("La IA lo entiende", "Clasifica, asigna y crea el pedido."),
    ("Cobras en línea", "Link de pago, reintentos y conciliación."),
    ("Se factura solo", "Conectado a tu ERP y a tu inventario."),
    ("Lo mides todo", "GA4, Pixel de Meta y Search Console."),
]


def hero():
    W, H = 1200, 540
    X = 64
    body = [backdrop(W, H)]

    mark, mark_w = logo(X, 50, 58)
    body.append(mark)
    name, _ = text(M800, "JOEL SUÁREZ", X + mark_w + 18, 79, 27, WHITE, track=2.2)
    role, _ = text(M700, "ARQUITECTO DE SOFTWARE", X + mark_w + 18, 104, 13.5, MUTED, track=4)
    body += [name, role]

    # Titular de la web: «SOFTWARE QUE [VERBO] POR TI»; el verbo rota como en joelsuarez.dev.
    size, top, gap = 92, 236, 104
    line1, _ = text(ANTON, "SOFTWARE QUE", X, top, size, WHITE)
    body.append(line1)
    base = top + gap
    pad = 14
    widths = [ANTON.width(verb, size) for verb in VERBS]
    rest = widths[-1]
    cap = ANTON.cap * size
    box_w = rest + 2 * pad
    body.append(f'<rect class="box" x="{X - pad}" y="{num(base - cap - pad)}" width="{num(box_w)}" '
                f'height="{num(cap + 2 * pad)}" rx="4" fill="{LEMON}"/>')
    for i, verb in enumerate(VERBS):
        path, _ = text(ANTON, verb, X, base, size, INK)
        visible = "1" if i == len(VERBS) - 1 else "0"
        body.append(f'<g class="v v{i}" opacity="{visible}">{path}</g>')
    por, _ = text(ANTON, "POR TI", X + rest + pad + 24, base, size, WHITE)
    body.append(f'<g class="por">{por}</g>')

    for i, line in enumerate(("Agentes de IA para WhatsApp, pagos en línea", "e integraciones con tu ERP.")):
        sub, _ = text(M500, line, X, 408 + i * 30, 21, SOFT)
        body.append(sub)
    meta, _ = text(M700, "MÉRIDA, VENEZUELA · 100 % REMOTO · DESDE 2017", X, 486, 14, LEMON, track=3)
    body.append(meta)

    # Flujo de la derecha: lo que hace el software de punta a punta.
    PX, first, step = 812, 168, 74
    label, _ = text(M800, "DE PUNTA A PUNTA", PX - 12, 112, 13.5, LEMON, track=3.5)
    body.append(label)
    last = first + step * (len(STEPS) - 1)
    body.append(f'<line x1="{PX}" y1="{first}" x2="{PX}" y2="{last}" stroke="{EDGE}" stroke-width="2"/>')
    body.append(f'<line class="prog" x1="{PX}" y1="{first}" x2="{PX}" y2="{last}" stroke="{LEMON}" stroke-width="2"/>')
    for i, (title, detail) in enumerate(STEPS):
        y = first + i * step
        body.append(f'<circle class="node n{i}" cx="{PX}" cy="{y}" r="9" fill="{LEMON}" stroke="{LEMON}" stroke-width="2"/>')
        heading, _ = text(M700, title, PX + 28, y + 7, 21, WHITE)
        note, _ = text(M500, detail, PX + 28, y + 33, 16.5, MUTED)
        body += [heading, note]
    body.append(f'<circle class="dot" cx="{PX}" cy="{first}" r="5" fill="{WHITE}" opacity="0"/>')

    # Animaciones: el verbo rota cada 2,5 s y un pedido recorre el flujo cada 7 s.
    n, seg, fade = len(VERBS), 100 / len(VERBS), 2.4
    css = []
    for i in range(n):
        a, b = i * seg, (i + 1) * seg
        frames = [(0, "opacity:0;transform:translateY(26px)")] if a > 0 else []
        frames += [(a, "opacity:0;transform:translateY(26px)"), (a + fade, "opacity:1;transform:translateY(0)"),
                   (b - fade, "opacity:1;transform:translateY(0)"), (b, "opacity:0;transform:translateY(-26px)")]
        if b < 100:
            frames.append((100, "opacity:0;transform:translateY(-26px)"))
        css.append(keyframes(f"v{i}", frames))
    box_frames, por_frames = [(0, f"transform:scaleX({num(1)})")], [(0, "transform:translateX(0)")]
    for i, width in enumerate(widths):
        a, b = i * seg + fade, (i + 1) * seg - fade
        k = (width + 2 * pad) / box_w
        box_frames += [(a, f"transform:scaleX({k:.4f})"), (b, f"transform:scaleX({k:.4f})")]
        por_frames += [(a, f"transform:translateX({num(width - rest)}px)"), (b, f"transform:translateX({num(width - rest)}px)")]
    box_frames.append((100, "transform:scaleX(1)"))
    por_frames.append((100, "transform:translateX(0)"))
    css += [keyframes("box", box_frames), keyframes("por", por_frames)]

    travel = last - first
    css.append(keyframes("prog", [(0, "transform:scaleY(0);opacity:1"), (72, "transform:scaleY(1);opacity:1"),
                                  (90, "transform:scaleY(1);opacity:1"), (100, "transform:scaleY(1);opacity:0")]))
    css.append(keyframes("dot", [(0, "transform:translateY(0);opacity:0"), (4, "transform:translateY(0);opacity:1"),
                                 (72, f"transform:translateY({travel}px);opacity:1"),
                                 (90, f"transform:translateY({travel}px);opacity:1"),
                                 (96, f"transform:translateY({travel}px);opacity:0"),
                                 (100, f"transform:translateY({travel}px);opacity:0")]))
    off, on = f"fill:{INK2};stroke:{EDGE}", f"fill:{LEMON};stroke:{LEMON}"
    for i in range(len(STEPS)):
        at = 4 + 68 * i / (len(STEPS) - 1)
        css.append(keyframes(f"n{i}", [(0, off), (max(at - 1, 0.5), off), (at + 0.5, on), (90, on), (100, off)]))

    motion = (
        "".join(f".v{i}{{animation:v{i} 12.5s infinite}}" for i in range(n))
        + ".box{transform-box:fill-box;transform-origin:0 50%;animation:box 12.5s infinite}"
        + ".por{animation:por 12.5s infinite}"
        + ".prog{transform-box:fill-box;transform-origin:50% 0;animation:prog 7s infinite}"
        + ".dot{animation:dot 7s infinite}"
        + "".join(f".n{i}{{animation:n{i} 7s infinite}}" for i in range(len(STEPS)))
    )
    style = "".join(css) + "@media (prefers-reduced-motion:no-preference){" + motion + "}"
    title = ("Joel Suárez, arquitecto de software. Software que responde, cobra, factura, vende y trabaja por ti: "
             "agentes de IA para WhatsApp, pagos en línea e integraciones con ERP.")
    return document("hero.svg", W, H, title, body, style)


# --- Cifras -------------------------------------------------------------------

METRICS = [
    # (signo, moneda, cifra, unidad, texto): la moneda y la unidad van más pequeñas, como en la web.
    ("", "", "9+", "", "años con software en producción"),
    ("+", "US$", "1,5", "M", "vendidos en el primer año a través del sistema que diseñé"),
    ("+", "US$", "30", "mil", "al mes en ventas de empresas que llegaron por WhatsApp y la web"),
    ("", "", "250+", "", "clases de test en el sistema de Delicius"),
]


def metricas():
    W = 1200
    cell = W / len(METRICS)
    big, small, gap = 72, 40, 8
    labels = [wrap(M600, label, 18, 220) for *_, label in METRICS]
    H = 140 + 24 * (max(map(len, labels)) - 1) + 44
    body = [backdrop(W, H, glow=("50%", "-40%"), radius=24)]
    for i, ((sign, currency, value, unit, _), lines) in enumerate(zip(METRICS, labels)):
        cx = cell * i + cell / 2
        if i:
            body.append(f'<line x1="{num(cell * i)}" y1="44" x2="{num(cell * i)}" y2="{H - 44}" stroke="{LINE}" stroke-width="2"/>')
        pieces = [(sign, big, 0), (currency, small, 0), (value, big, 0), (unit, small, gap)]
        pieces = [(t, size, before) for t, size, before in pieces if t]
        total = sum(ANTON.width(t, size) + before for t, size, before in pieces)
        x = cx - total / 2
        for t, size, before in pieces:
            x += before
            path, width = text(ANTON, t, x, 104, size, LEMON)
            body.append(path)
            x += width
        for n, line in enumerate(lines):
            body.append(text(M600, line, cx, 140 + 24 * n, 18, SOFT, anchor="middle")[0])
    title = " · ".join(f"{sign}{currency}{value}{' ' + unit if unit else ''} {label}"
                       for sign, currency, value, unit, label in METRICS)
    return document("metricas.svg", W, H, title, body)


# --- Botones de contacto -----------------------------------------------------

def boton(name, label, glyph, primary=False):
    H, size, track = 52, 16.5, 2.2
    label_w = M800.width(label, size, track)
    W = round(24 + 24 + 12 + label_w + 26)
    fill, ink, stroke = (LEMON, INK, LEMON) if primary else (INK, WHITE, LEMON)
    body = [f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="{(H - 2) / 2}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>']
    body.append(glyph(24, 14, 24, INK if primary else LEMON))
    word, _ = text(M800, label, 24 + 24 + 12, 32.5, size, ink, track=track)
    body.append(word)
    return document(name, W, H, label, body)


def glifo_web(x, y, size, fill):
    mark, _ = logo(x + 5, y, size, fill)
    return mark


def glifo_linkedin(x, y, size, fill):
    letters, _ = text(M800, "in", x + size / 2, y + size - 6, 14, INK, anchor="middle")
    return f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="5" fill="{fill}"/>{letters}'


def botones():
    boton("btn-web.svg", "JOELSUAREZ.DEV", glifo_web, primary=True)
    boton("btn-linkedin.svg", "LINKEDIN", glifo_linkedin)
    boton("btn-correo.svg", "CORREO", lambda x, y, s, f: icon("gmail", x, y, s, f))
    boton("btn-whatsapp.svg", "WHATSAPP", lambda x, y, s, f: icon("whatsapp", x, y, s, f))


# --- Tarjetas de proyectos ---------------------------------------------------

PROJECTS = [
    ("proyecto-ddd.svg", "IA · MCP · ARQUITECTURA", "DDD DIAGRAM EDITOR", LEMON,
     "Dibuja la arquitectura anillo por anillo y archivo por archivo antes de programar. Tu agente de IA la lee por MCP y la respeta.",
     ["PHP", "Laravel", "React", "MCP"]),
    ("proyecto-atomic.svg", "SAAS · IA", "ATOMIC HABITS", MINT,
     "Hábitos con el método de James Clear y un coach de IA que lee y escribe tus datos. Planes de pago y arquitectura DDD.",
     ["Laravel 12", "Vue 3", "Tailwind", "IA"]),
    ("proyecto-verbo.svg", "IA · EDUCACIÓN", "VERBO", SKY,
     "Gramática inglesa con 115 unidades y unos 3.100 ejercicios. Una IA corrige cada respuesta y la comenta en español.",
     ["Laravel 13", "Livewire 4", "DeepSeek", "DDD"]),
    ("proyecto-web.svg", "WEB · SEO", "JOELSUAREZ.DEV", CORAL,
     "Mi sitio: casos reales, servicios y contacto. Rápido, con SEO técnico y despliegue continuo.",
     ["Astro", "Tailwind", "GitHub Actions"]),
]


def tarjeta(name, eyebrow, title, accent, description, tags):
    W, H, X = 600, 340, 38
    body = [
        "<defs><clipPath id=\"card\"><rect width=\"600\" height=\"340\" rx=\"22\"/></clipPath>"
        f'<linearGradient id="bar" x1="0" x2="1"><stop offset="0" stop-color="{accent}"/>'
        f'<stop offset="1" stop-color="{accent}" stop-opacity="0"/></linearGradient></defs>',
        f'<g clip-path="url(#card)"><rect width="{W}" height="{H}" fill="{INK2}"/>'
        f'<rect width="{W}" height="6" fill="url(#bar)"/></g>',
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="21" fill="none" stroke="{LINE}" stroke-width="2"/>',
    ]
    small, _ = text(M800, eyebrow, X, 58, 13.5, accent, track=3.2)
    big, _ = text(ANTON, title, X, 114, 46, WHITE)
    body += [small, big]
    for i, line in enumerate(wrap(M500, description, 19.5, W - 2 * X)):
        row, _ = text(M500, line, X, 158 + i * 29, 19.5, SOFT)
        body.append(row)
    x = X
    for tag in tags:
        word_w = M600.width(tag, 15)
        body.append(f'<rect x="{num(x)}" y="252" width="{num(word_w + 26)}" height="34" rx="17" fill="none" stroke="{EDGE}" stroke-width="1.5"/>')
        word, _ = text(M600, tag, x + 13, 274, 15, SOFT)
        body.append(word)
        x += word_w + 26 + 8
    cta, _ = text(M800, "VER REPO →", W - X, 316, 13.5, accent, track=2.5, anchor="end")
    body.append(cta)
    return document(name, W, H, f"{title.title()}: {description}", body)


# --- Cómo trabajo ------------------------------------------------------------

PROCESS = [
    ("Diagnóstico", "Entiendo tu operación: qué se hace a mano y qué conviene automatizar primero."),
    ("Diseño", "Dibujo la arquitectura por capas antes de escribir código. Tú ves el plano y lo apruebas."),
    ("Construcción", "Avances pequeños y visibles, con pruebas automáticas que cuidan lo que ya funciona."),
    ("Lanzamiento", "Despliegue en la nube, monitoreo y métricas para decidir con datos."),
]


def proceso():
    W, H = 1200, 300
    cell = W / len(PROCESS)
    body = [backdrop(W, H, glow=("10%", "0%"), radius=24)]
    for i, (title, detail) in enumerate(PROCESS):
        x = cell * i + 40
        number, _ = text(ANTON, f"0{i + 1}", x, 104, 64, "none",
                         attrs=f' stroke="{LEMON}" stroke-width="1.6"')
        heading, _ = text(M800, title, x, 150, 22, WHITE)
        body += [number, heading]
        for j, line in enumerate(wrap(M500, detail, 16.5, cell - 70)):
            row, _ = text(M500, line, x, 184 + j * 25, 16.5, SOFT)
            body.append(row)
        if i + 1 < len(PROCESS):
            ax = cell * (i + 1) - 14
            body.append(f'<path d="M{num(ax - 8)} 70l10 10-10 10" fill="none" stroke="{LEMON}" stroke-width="2.4" '
                        'stroke-linecap="round" stroke-linejoin="round"/>')
    title = "Cómo trabajo: " + " ".join(f"{i + 1}. {t}: {d}" for i, (t, d) in enumerate(PROCESS))
    return document("proceso.svg", W, H, title, body)


# --- Stack -------------------------------------------------------------------

BRAND = {
    "laravel": "#ff2d20", "php": "#8f93d6", "nodedotjs": "#5fa04e", "mysql": "#5d9cd6", "postgresql": "#5b84f0",
    "redis": "#ff4438", "mongodb": "#47a248", "react": "#61dafb", "vuedotjs": "#4fc08d", "typescript": "#4b8fe0",
    "astro": "#bc52ee", "tailwindcss": "#06b6d4", "livewire": "#fb70a9", "filament": "#fdae4b",
    "claude": "#d97757", "anthropic": "#f0eee6", "deepseek": "#6d87ff", "ollama": "#ffffff", "whatsapp": "#25d366",
    "docker": "#2496ed", "githubactions": "#4b9dff", "serverless": "#fd5750", "vitest": "#8cc63f",
    "stripe": "#8a84ff", "binance": "#f0b90b", "googleanalytics": "#f9ab00", "googletagmanager": "#5c9bff",
    "meta": "#2d8cff",
}

STACK = [
    ("BACKEND", [("laravel", "Laravel"), ("php", "PHP 8.4"), ("nodedotjs", "Node.js"), (None, "Python y FastAPI")]),
    ("DATOS", [(None, "MySQL"), ("postgresql", "PostgreSQL"), ("redis", "Redis"), ("mongodb", "MongoDB")]),
    ("FRONTEND", [("react", "React"), ("vuedotjs", "Vue"), ("typescript", "TypeScript"), ("astro", "Astro"),
                  ("tailwindcss", "Tailwind"), ("livewire", "Livewire"), (None, "Filament")]),
    ("IA Y AGENTES", [("claude", "Claude"), ("anthropic", "Anthropic API"), ("deepseek", "DeepSeek"),
                      ("ollama", "Ollama"), (None, "MCP"), ("whatsapp", "WhatsApp API")]),
    ("NUBE Y CALIDAD", [(None, "AWS"), ("docker", "Docker"), ("githubactions", "GitHub Actions"),
                        ("serverless", "Serverless"), ("vitest", "Vitest"), (None, "PHPUnit"), (None, "Playwright")]),
    ("PAGOS Y MEDICIÓN", [("stripe", "Stripe"), (None, "Klap"), ("binance", "Binance Pay"), (None, "Defontana"),
                          ("googleanalytics", "GA4"), ("googletagmanager", "Tag Manager"), ("meta", "Pixel de Meta")]),
]


def stack():
    """Una fila de fichas por grupo, con el nombre del grupo encima para usar todo el ancho."""
    W, LEFT, RIGHT, CHIP, GAP, LABEL, ICON = 1200, 40, 1160, 48, 10, 18.5, 22
    rows, y = [], 40
    for group, items in STACK:
        x, line_y, chips = LEFT, y + 26, []
        for slug, label in items:
            label_w = M600.width(label, LABEL)
            chip_w = 14 + ICON + 10 + label_w + 18
            if x + chip_w > RIGHT:
                x, line_y = LEFT, line_y + CHIP + GAP
            chips.append((slug, label, x, line_y, chip_w))
            x += chip_w + GAP
        rows.append((group, y, chips))
        y = line_y + CHIP + 30
    H = y + 6
    body = [backdrop(W, H, glow=("95%", "100%"), radius=24)]
    for group, top, chips in rows:
        heading, _ = text(M800, group, LEFT + 4, top + 12, 13.5, LEMON, track=3)
        body.append(heading)
        for slug, label, x, cy, chip_w in chips:
            body.append(f'<rect x="{num(x)}" y="{cy}" width="{num(chip_w)}" height="{CHIP}" rx="{CHIP / 2}" '
                        f'fill="{INK2}" stroke="{LINE}" stroke-width="1.5"/>')
            if slug:
                body.append(icon(slug, x + 14, cy + (CHIP - ICON) / 2, ICON, BRAND[slug]))
            else:
                body.append(f'<circle cx="{num(x + 14 + ICON / 2)}" cy="{CHIP / 2 + cy}" r="5" fill="{LEMON}"/>')
            word, _ = text(M600, label, x + 14 + ICON + 10, cy + CHIP / 2 + 6.5, LABEL, WHITE)
            body.append(word)
    title = "Stack: " + "; ".join(f"{g.capitalize()}: " + ", ".join(label for _, label in items) for g, items in STACK)
    return document("stack.svg", W, H, title, body)


# --- Cierre ------------------------------------------------------------------

def cierre():
    W, H = 1200, 260
    body = [backdrop(W, H, glow=("0%", "50%"), radius=28)]
    mark, mark_w = logo(64, 62, 136)
    body.append(mark)
    X = 64 + mark_w + 40
    l1, _ = text(ANTON, "¿TIENES UN PROCESO QUE", X, 112, 56, WHITE)
    body.append(l1)
    l2a, w2 = text(ANTON, "TODAVÍA SE HACE ", X, 182, 56, WHITE)
    word_w = ANTON.width("A MANO?", 56)
    cap = ANTON.cap * 56
    body += [l2a, f'<rect x="{num(X + w2 - 8)}" y="{num(182 - cap - 10)}" width="{num(word_w + 16)}" height="{num(cap + 20)}" rx="4" fill="{LEMON}"/>']
    l2b, _ = text(ANTON, "A MANO?", X + w2, 182, 56, INK)
    note, _ = text(M600, "Escríbeme por WhatsApp y lo conversamos.", X, 222, 17, MUTED)
    body += [l2b, note]
    label = "CONVERSEMOS →"
    label_w = M800.width(label, 18, 2.4)
    bw = label_w + 60
    bx, by = W - 64 - bw, 104
    body.append(f'<g class="cta"><rect x="{num(bx)}" y="{by}" width="{num(bw)}" height="60" rx="30" fill="{LEMON}"/>')
    word, _ = text(M800, label, bx + 30, by + 37, 18, INK, track=2.4)
    body.append(word + "</g>")
    style = ("@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.045)}}"
             "@media (prefers-reduced-motion:no-preference){.cta{transform-box:fill-box;transform-origin:50% 50%;"
             "animation:pulse 2.4s ease-in-out infinite}}")
    return document("cierre.svg", W, H, "¿Tienes un proceso que todavía se hace a mano? Conversemos por WhatsApp.", body, style)


# --- Vitrina de Delicius (WebP) ----------------------------------------------

def rgb(color, alpha=255):
    return ImageColor.getrgb(color) + (alpha,)


def montserrat(size, weight):
    font = ImageFont.truetype(str(PUBLIC / "fonts" / "montserrat-latin.woff"), size)
    font.set_variation_by_axes([weight])
    return font


def tracked(draw, x, y, value, font, fill, track):
    for ch in value:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + track
    return x


def tracked_width(draw, value, font, track):
    return sum(draw.textlength(ch, font=font) for ch in value) + track * (len(value) - 1)


def capture(file, width):
    shot = Image.open(PUBLIC / "images" / "cases" / file).convert("RGB")
    return shot.resize((width, round(width * shot.height / shot.width)), Image.LANCZOS)


def rounded(image, radius):
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, image.width - 1, image.height - 1], radius, fill=255)
    out = Image.new("RGBA", image.size, (0, 0, 0, 0))
    out.paste(image, (0, 0), mask)
    return out


def browser(file, width, address):
    shot = capture(file, width)
    bar = 44
    window = Image.new("RGBA", (width, shot.height + bar), rgb(INK2))
    window.paste(shot, (0, bar))
    draw = ImageDraw.Draw(window)
    for i, color in enumerate((CORAL, LEMON, MINT)):
        draw.ellipse([20 + i * 22, 16, 32 + i * 22, 28], fill=rgb(color))
    font = montserrat(16, 600)
    text_w = draw.textlength(address, font=font)
    pill_w = text_w + 40
    px = (width - pill_w) / 2
    draw.rounded_rectangle([px, 9, px + pill_w, 35], 13, fill=rgb(INK))
    draw.text((px + 20, 13), address, font=font, fill=rgb(MUTED))
    window = rounded(window, 16)
    ImageDraw.Draw(window).rounded_rectangle([0, 0, window.width - 1, window.height - 1], 16, outline=rgb(EDGE), width=2)
    return window


def phone(file, width):
    shot = rounded(capture(file, width), 30)
    bezel = 12
    body = Image.new("RGBA", (width + 2 * bezel, shot.height + 2 * bezel), (0, 0, 0, 0))
    draw = ImageDraw.Draw(body)
    draw.rounded_rectangle([0, 0, body.width - 1, body.height - 1], 42, fill=rgb(INK2), outline=rgb(EDGE), width=2)
    body.alpha_composite(shot, (bezel, bezel))
    return body


def place(canvas, piece, x, y, radius=18):
    blur, pad = 26, 80
    shade = Image.new("RGBA", (piece.width + 2 * pad, piece.height + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(shade).rounded_rectangle([pad, pad, pad + piece.width, pad + piece.height], radius, fill=(0, 0, 0, 175))
    canvas.alpha_composite(shade.filter(ImageFilter.GaussianBlur(blur)), (x - pad, y - pad + 24))
    canvas.alpha_composite(piece, (x, y))


def tag(canvas, x, y, label):
    draw = ImageDraw.Draw(canvas)
    font = montserrat(17, 800)
    width = tracked_width(draw, label, font, 2.2)
    draw.rounded_rectangle([x, y, x + width + 32, y + 40], 20, fill=rgb(LEMON))
    tracked(draw, x + 16, y + 9, label, font, rgb(INK), 2.2)


def vitrina():
    W, H = 1600, 900
    canvas = Image.new("RGBA", (W, H), rgb(INK))
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(grid)
    for x in range(0, W, 40):
        draw.line([(x, 0), (x, H)], fill=rgb("#132641", 140))
    for y in range(0, H, 40):
        draw.line([(0, y), (W, y)], fill=rgb("#132641", 140))
    canvas.alpha_composite(grid)
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse([W - 820, -560, W + 420, 520], fill=rgb(NAVY, 210))
    canvas.alpha_composite(halo.filter(ImageFilter.GaussianBlur(170)))

    place(canvas, browser("delicius-bo-conversaciones.webp", 930, "Backoffice · Delicius Food"), 70, 70)
    place(canvas, browser("delicius-desktop.webp", 780, "deliciusfoodchile.cl"), 590, 316)
    place(canvas, phone("delicius-b2b-movil.webp", 214), 1320, 96, radius=42)

    tag(canvas, 48, 40, "BACKOFFICE Y CRM")
    tag(canvas, 566, 286, "TIENDA B2C Y WEB")
    tag(canvas, 1296, 66, "TIENDA B2B")
    # Esquinas redondeadas como los paneles SVG (rx 28 a 1200 de ancho = 37 a 1600).
    path = OUT / "delicius.webp"
    rounded(canvas, 37).save(path, quality=88, method=6)
    return path.stat().st_size


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    sizes = {
        "hero.svg": hero(),
        "metricas.svg": metricas(),
        "proceso.svg": proceso(),
        "stack.svg": stack(),
        "cierre.svg": cierre(),
        "delicius.webp": vitrina(),
    }
    botones()
    for project in PROJECTS:
        sizes[project[0]] = tarjeta(*project)
    for name, size in sizes.items():
        print(f"{name:22s} {size / 1024:7.1f} KB")
