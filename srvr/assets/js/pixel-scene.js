// ============================================================
// The Dobinator — Pixel Art Scene Engine
// Renders a black-and-white pixel art scene at the bottom of
// the viewport while the app is running.
//
// Sprites are defined as arrays of color strings ("0,0,0" = black,
// "0,0,0,0" = transparent) and rendered directly to canvas.
// ============================================================

// ---------------------------------------------------------------------------
// Sprite Data — all black (#000) or transparent
// ---------------------------------------------------------------------------

const B = "0, 0, 0";           // Black pixel
const _ = "0, 0, 0, 0";       // Transparent


// -------------------------START MARKER----------------------------------------



// --- Cat Idle (sitting) 16x16 ---
const catIdle = [
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,B,_,_,_,B,_,_],
    [_,_,_,_,_,_,_,_,_,B,B,B,B,B,_,_],
    [_,_,_,_,_,_,_,_,_,B,B,B,B,B,_,_],
    [_,_,_,_,_,_,_,_,_,_,B,B,B,_,_,_],
    [_,_,_,_,_,_,_,_,B,B,B,B,B,_,_,_],
    [_,_,_,_,_,_,_,B,B,B,B,B,B,_,_,_],
    [_,_,_,_,_,_,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,_,_,_,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,_,_,_,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,_,_,_,B,B,B,B,B,B,B,_,_,_],
    [_,_,B,B,_,_,B,B,_,B,B,_,B,B,_,_],
    [_,B,B,B,B,_,B,B,_,B,B,_,B,B,_,_],
    [_,_,_,B,B,B,B,B,B,B,B,B,B,B,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
];

// --- Cat Walk Frame 1 16x16 ---
const catWalk1 = [
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,B,_,_,_,B,_],
    [_,_,_,_,_,_,_,_,_,_,B,B,B,B,B,_],
    [_,_,_,_,_,_,_,_,_,_,B,B,B,B,B,_],
    [_,B,_,_,_,_,_,_,_,_,_,B,B,B,_,_],
    [_,B,B,_,_,B,B,B,B,B,B,B,B,_,_,_],
    [_,_,B,B,B,B,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,B,B,B,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,B,B,B,B,B,B,B,B,B,_,_,_,_],
    [_,_,_,B,B,_,_,_,_,_,B,B,_,_,_,_],
    [_,_,B,B,_,_,_,_,_,_,_,B,B,_,_,_],
    [_,B,B,_,_,_,_,_,_,_,_,_,B,B,_,_],
    [_,B,B,B,_,_,_,_,_,_,_,_,B,B,B,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
];

// --- Cat Walk Frame 2 16x16 ---
const catWalk2 = [
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,B,_,_,_,B,_],
    [_,_,_,_,_,_,_,_,_,_,B,B,B,B,B,_],
    [_,_,_,_,_,_,_,_,_,_,B,B,B,B,B,_],
    [_,B,_,_,_,_,_,_,_,_,_,B,B,B,_,_],
    [_,B,B,_,_,B,B,B,B,B,B,B,B,_,_,_],
    [_,_,B,B,B,B,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,B,B,B,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,B,B,B,B,B,B,B,B,B,_,_,_,_],
    [_,_,_,_,B,B,_,_,_,B,B,_,_,_,_,_],
    [_,_,_,_,B,B,_,_,_,B,B,_,_,_,_,_],
    [_,_,_,_,B,B,_,_,_,B,B,_,_,_,_,_],
    [_,_,_,B,B,B,_,_,B,B,B,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
];

// --- Dog Idle (sitting) 16x18 ---
const dogIdle = [
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,B,B,B,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,B,B,B,B,B,B,_,_],
    [_,_,_,_,_,_,_,B,B,B,B,B,B,B,_,_],
    [_,_,_,_,_,_,_,B,B,B,B,B,B,_,_,_],
    [_,_,_,_,_,_,_,B,B,B,B,B,_,_,_,_],
    [_,_,_,_,_,_,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,_,_,_,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,_,_,B,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,_,_,B,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,_,_,B,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,_,B,B,B,B,B,B,B,B,B,_,_,_],
    [_,_,B,B,B,B,B,_,B,B,_,B,B,_,_,_],
    [_,B,B,B,B,B,B,_,B,B,_,B,B,_,_,_],
    [_,B,B,_,B,B,B,_,B,B,_,B,B,_,_,_],
    [_,_,B,B,B,B,B,B,B,B,B,B,B,B,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
];

// --- Dog Walk Frame 1 16x18 ---
const dogWalk1 = [
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,B,B,B,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,B,B,B,B,B],
    [_,_,_,_,_,_,_,_,_,_,B,B,B,B,B,B],
    [_,_,_,_,_,_,_,_,_,_,B,B,B,B,B,_],
    [_,_,_,_,_,_,B,B,B,B,B,B,B,B,_,_],
    [_,_,_,B,B,B,B,B,B,B,B,B,B,B,_,_],
    [_,B,B,B,B,B,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,B,B,B,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,B,B,B,B,B,B,B,B,B,_,_,_,_],
    [_,_,_,B,B,B,B,B,B,B,B,B,_,_,_,_],
    [_,_,_,B,B,_,_,_,_,_,B,B,_,_,_,_],
    [_,_,_,B,B,_,_,_,_,_,B,B,_,_,_,_],
    [_,_,B,B,_,_,_,_,_,_,_,B,B,_,_,_],
    [_,B,B,_,_,_,_,_,_,_,_,_,B,B,_,_],
    [_,B,B,B,_,_,_,_,_,_,_,_,B,B,B,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
];

// --- Dog Walk Frame 2 16x18 ---
const dogWalk2 = [
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,B,B,B,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,B,B,B,B,B],
    [_,_,_,_,_,_,_,_,_,_,B,B,B,B,B,B],
    [_,_,_,_,_,_,_,_,_,_,B,B,B,B,B,_],
    [_,_,_,_,_,_,B,B,B,B,B,B,B,B,_,_],
    [_,_,_,B,B,B,B,B,B,B,B,B,B,B,_,_],
    [_,B,B,B,B,B,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,B,B,B,B,B,B,B,B,B,B,_,_,_],
    [_,_,_,B,B,B,B,B,B,B,B,B,_,_,_,_],
    [_,_,_,B,B,B,B,B,B,B,B,B,_,_,_,_],
    [_,_,_,_,B,B,_,_,_,B,B,_,_,_,_,_],
    [_,_,_,_,B,B,_,_,_,B,B,_,_,_,_,_],
    [_,_,_,_,B,B,_,_,_,B,B,_,_,_,_,_],
    [_,_,_,B,B,B,_,_,B,B,B,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
];

// --- Tree (deciduous) 12x20 ---
const tree = [
    [_,_,_,_,B,B,B,_,_,_,_,_],
    [_,_,_,B,B,B,B,B,_,_,_,_],
    [_,_,B,B,B,B,B,B,B,_,_,_],
    [_,_,B,B,B,B,B,B,B,_,_,_],
    [_,B,B,B,B,B,B,B,B,B,_,_],
    [_,B,B,B,B,B,B,B,B,B,_,_],
    [B,B,B,B,B,B,B,B,B,B,B,_],
    [B,B,B,B,B,B,B,B,B,B,B,_],
    [B,B,B,B,B,B,B,B,B,B,B,_],
    [B,B,B,B,B,B,B,B,B,B,B,_],
    [B,B,B,B,B,B,B,B,B,B,B,_],
    [B,B,B,B,B,B,B,B,B,B,B,_],
    [_,_,_,B,B,B,B,B,_,_,_,_],
    [_,_,_,B,B,B,B,B,_,_,_,_],
    [_,_,_,B,B,B,B,B,_,_,_,_],
    [_,_,_,B,B,B,B,B,_,_,_,_],
    [_,_,_,B,B,B,B,B,_,_,_,_],
    [_,_,_,B,B,B,B,B,_,_,_,_],
    [_,_,_,B,B,B,B,B,_,_,_,_],
    [_,_,_,B,B,B,B,B,_,_,_,_],
];

// --- Bench 20x10 ---
const bench = [
    [_,_,_,_,B,B,B,B,B,B,B,B,B,B,B,B,_,_,_,_],
    [_,_,_,_,B,B,B,B,B,B,B,B,B,B,B,B,_,_,_,_],
    [_,_,_,_,B,B,B,B,B,B,B,B,B,B,B,B,_,_,_,_],
    [_,_,_,_,B,_,_,B,_,_,B,_,_,B,_,_,B,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,B,B,B,B,B,B,B,B,B,B,B,B,_,_,_,_],
    [_,_,_,_,B,B,B,B,B,B,B,B,B,B,B,B,_,_,_,_],
    [_,_,_,_,B,_,_,B,_,_,B,_,_,B,_,_,B,_,_,_],
    [_,_,_,_,B,_,_,B,_,_,B,_,_,B,_,_,B,_,_,_],
    [_,_,_,_,B,_,_,B,_,_,B,_,_,B,_,_,B,_,_,_],
];

// --- Sun 16x16 ---
const sun = [
    [_,_,_,_,_,_,_,B,B,_,_,_,_,_,_,_],
    [_,_,B,_,_,_,_,B,B,_,_,_,_,B,_,_],
    [_,_,_,B,_,_,_,_,_,_,_,_,B,_,_,_],
    [_,_,_,_,_,_,B,B,B,B,_,_,_,_,_,_],
    [_,_,_,_,_,B,B,B,B,B,B,_,_,_,_,_],
    [_,_,_,_,B,B,B,B,B,B,B,B,_,_,_,_],
    [_,_,_,_,B,B,B,B,B,B,B,B,_,_,_,_],
    [B,B,_,_,B,B,B,B,B,B,B,B,_,_,B,B],
    [B,B,_,_,B,B,B,B,B,B,B,B,_,_,B,B],
    [_,_,_,_,B,B,B,B,B,B,B,B,_,_,_,_],
    [_,_,_,_,B,B,B,B,B,B,B,B,_,_,_,_],
    [_,_,_,_,_,B,B,B,B,B,B,_,_,_,_,_],
    [_,_,_,_,_,_,B,B,B,B,_,_,_,_,_,_],
    [_,_,_,B,_,_,_,_,_,_,_,_,B,_,_,_],
    [_,_,B,_,_,_,_,B,B,_,_,_,_,B,_,_],
    [_,_,_,_,_,_,_,B,B,_,_,_,_,_,_,_],
];

// --- Moon 16x16 ---
const moon = [
    [_,_,_,_,_,_,B,B,B,B,_,_,_,_,_,_],
    [_,_,_,_,B,B,B,B,B,B,B,_,_,_,_,_],
    [_,_,_,B,B,B,B,B,_,_,_,_,_,_,_,_],
    [_,_,B,B,B,B,_,_,_,_,_,_,_,_,_,_],
    [_,_,B,B,B,_,_,_,_,_,_,_,_,_,_,_],
    [_,B,B,B,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,B,B,B,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,B,B,B,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,B,B,B,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,B,B,B,_,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,B,B,B,_,_,_,_,_,_,_,_,_,_,_],
    [_,_,B,B,B,B,_,_,_,_,_,_,_,_,_,_],
    [_,_,_,B,B,B,B,B,_,_,_,_,_,_,_,_],
    [_,_,_,_,B,B,B,B,B,B,B,_,_,_,_,_],
    [_,_,_,_,_,_,B,B,B,B,_,_,_,_,_,_],
    [_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_],
];

// --- Cloud 20x8 ---
const cloud = [
    [_,_,_,_,_,B,B,B,B,B,B,_,_,_,_,_,_,_,_,_],
    [_,_,_,_,B,B,B,B,B,B,B,B,_,_,_,_,_,_,_,_],
    [_,_,_,B,B,B,B,B,B,B,B,B,B,_,_,_,_,_,_,_],
    [_,_,B,B,B,B,B,B,B,B,B,B,B,B,_,_,_,_,_,_],
    [_,B,B,B,B,B,B,B,B,B,B,B,B,B,B,_,_,_,_,_],
    [_,B,B,B,B,B,B,B,B,B,B,B,B,B,B,_,_,_,_,_],
    [_,_,B,B,B,B,B,B,B,B,B,B,B,B,_,_,_,_,_,_],
    [_,_,_,B,B,B,B,B,B,B,B,B,B,_,_,_,_,_,_,_],
];

// --- Bush 14x7 (rounded, two-humped shrub) ---
const bush = [
    [_,_,_,B,B,_,_,_,_,B,B,_,_,_],
    [_,_,B,B,B,B,_,_,B,B,B,B,_,_],
    [_,B,B,B,B,B,B,B,B,B,B,B,B,_],
    [B,B,B,B,B,B,B,B,B,B,B,B,B,B],
    [B,B,B,B,B,B,B,B,B,B,B,B,B,B],
    [B,B,B,B,B,B,B,B,B,B,B,B,B,B],
    [_,B,B,B,B,B,B,B,B,B,B,B,B,_],
];


// -------------------------END MARKER----------------------------------------


// ---------------------------------------------------------------------------
// Sprite Rendering — draws pixel data arrays directly to canvas
// ---------------------------------------------------------------------------

let PIXEL_SIZE = 4;

// Active sprite color. Defaults to black; flips to white when the page
// background is dark (e.g. the Dark Reader extension darkened it), so the
// scene stays visible instead of rendering black-on-black.
let spriteColorRGB = '0, 0, 0';

function relativeLuminance(r, g, b) {
    return 0.299 * r + 0.587 * g + 0.114 * b;
}

/**
 * Inspect the page's effective background color and decide what color the
 * sprites should be drawn in. Dark background -> white sprites; light -> black.
 * This is what lets the scene survive dark-mode browser extensions, which
 * recolor the CSS background but cannot touch our canvas bitmap.
 */
function detectSpriteColor() {
    try {
        let bg = getComputedStyle(document.body).backgroundColor || '';
        let m = bg.match(/rgba?\(([^)]+)\)/);
        if (m) {
            const p = m[1].split(',').map(s => parseFloat(s));
            const a = p.length >= 4 ? p[3] : 1;
            // A transparent body shows the <html> background instead.
            if (a === 0) {
                bg = getComputedStyle(document.documentElement).backgroundColor || '';
                m = bg.match(/rgba?\(([^)]+)\)/);
                if (!m) return '0, 0, 0';
                const hp = m[1].split(',').map(s => parseFloat(s));
                return relativeLuminance(hp[0], hp[1], hp[2]) < 128 ? '255, 255, 255' : '0, 0, 0';
            }
            return relativeLuminance(p[0], p[1], p[2]) < 128 ? '255, 255, 255' : '0, 0, 0';
        }
    } catch (e) { /* ignore and fall through */ }
    return '0, 0, 0';
}

/**
 * Re-detect the background color. If the needed sprite color changed, rebuild
 * every sprite and the scene so entities reference the recolored canvases.
 * Returns true if a rebuild happened.
 */
function refreshSpriteColor() {
    const c = detectSpriteColor();
    if (c !== spriteColorRGB) {
        spriteColorRGB = c;
        buildSprites();
        if (sceneCanvas) buildScene();
        return true;
    }
    return false;
}

/**
 * Render a sprite data array into an offscreen canvas. The data is treated as
 * a 1-bit mask: any non-transparent cell is painted in `color` (an "r, g, b"
 * string), regardless of the cell's original value.
 * @param {string[][]} data  — Pixel array (opaque = drawn, "0,0,0,0" = transparent)
 * @param {string} color     — "r, g, b" fill applied to every opaque cell
 * @returns {HTMLCanvasElement}
 */
function renderSprite(data, color) {
    const rows = data.length;
    const cols = data[0] ? data[0].length : 0;
    const canvas = document.createElement('canvas');
    canvas.width = cols * PIXEL_SIZE;
    canvas.height = rows * PIXEL_SIZE;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = `rgb(${color})`;

    for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
            const val = data[r][c];
            if (val && val !== '0, 0, 0, 0') {
                const parts = val.split(',').map(s => parseInt(s.trim(), 10));
                const isTransparent = parts.length === 4 && parts[3] === 0;
                if (!isTransparent) {
                    ctx.fillRect(c * PIXEL_SIZE, r * PIXEL_SIZE, PIXEL_SIZE, PIXEL_SIZE);
                }
            }
        }
    }
    return canvas;
}

// Pre-render all sprites — re-runs when PIXEL_SIZE changes (mobile/desktop crossover)
let SPRITES = {};
function buildSprites() {
    const col = spriteColorRGB;
    SPRITES = {
        catIdle: renderSprite(catIdle, col),
        catWalk1: renderSprite(catWalk1, col),
        catWalk2: renderSprite(catWalk2, col),
        dogIdle: renderSprite(dogIdle, col),
        dogWalk1: renderSprite(dogWalk1, col),
        dogWalk2: renderSprite(dogWalk2, col),
        tree: renderSprite(tree, col),
        bench: renderSprite(bench, col),
        sun: renderSprite(sun, col),
        moon: renderSprite(moon, col),
        cloud: renderSprite(cloud, col),
        bush: renderSprite(bush, col),
    };
}
buildSprites();

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const CONFIG = {
    sceneHeight: 180,          // Desktop scene height
    sceneHeightMobile: 140,    // Mobile scene height
    groundYRatio: 0.90,        // Ground line at 90% of scene height (moved lower)
    petSpeed: 0.025,           // pixels per ms
    idleMinMs: 2000,
    idleMaxMs: 6000,
    wanderMinMs: 3000,
    wanderMaxMs: 8000,
    cloudDriftSpeed: 0.03,     // px per ms
};

// ---------------------------------------------------------------------------
// Entity classes
// ---------------------------------------------------------------------------

class StaticEntity {
    constructor(canvas, x, y) {
        this.canvas = canvas;
        this.x = x;
        this.y = y;
    }
    draw(ctx) {
        ctx.drawImage(this.canvas, this.x, this.y);
    }
}

class CloudEntity {
    constructor(canvas, x, y, speed) {
        this.canvas = canvas;
        this.x = x;
        this.y = y;
        this.speed = speed;
    }
    update(dt, sceneWidth) {
        this.x += this.speed * dt;
        if (this.x > sceneWidth) {
            this.x = -this.canvas.width;
        }
        if (this.x < -this.canvas.width) {
            this.x = sceneWidth;
        }
    }
    draw(ctx) {
        ctx.drawImage(this.canvas, this.x, this.y);
    }
}

class PetEntity {
    constructor(sprites, x, y, type) {
        this.sprites = sprites;  // { idle, walk1, walk2 } — each is a canvas
        this.x = x;
        this.y = y;
        this.type = type;        // 'cat' or 'dog'
        this.state = 'idle';     // 'idle' | 'walking'
        this.direction = 1;      // 1 = right, -1 = left
        this.frameIndex = 0;
        this.stateTimer = 0;
        this.nextStateTime = this.randomTime(CONFIG.idleMinMs, CONFIG.idleMaxMs);
        this.bouncePhase = Math.random() * Math.PI * 2;
        this.frameTimer = 0;
    }

    randomTime(min, max) {
        return min + Math.random() * (max - min);
    }

    isSafeToStop(x, idlePets, staticObjects) {
        const petW = this.sprites.idle.width;
        // Check overlap with static ground objects
        for (const obj of staticObjects) {
            if (!(x + petW <= obj.x || obj.x + obj.width <= x)) {
                return false;
            }
        }
        // Check overlap with other idle pets
        for (const other of idlePets) {
            if (other === this) continue;
            const otherW = other.sprites.idle.width;
            if (!(x + petW <= other.x || other.x + otherW <= x)) {
                return false;
            }
        }
        return true;
    }

    update(dt, groundY, sceneWidth, idlePets = [], staticObjects = []) {
        this.stateTimer += dt;
        this.bouncePhase += dt * 0.004;
        this.frameTimer += dt;

        if (this.stateTimer >= this.nextStateTime) {
            if (this.state === 'walking') {
                if (this.isSafeToStop(this.x, idlePets, staticObjects)) {
                    this.stateTimer = 0;
                    this.transitionState();
                } else {
                    // Extend stateTimer to stay in walking state and check again next frame
                    this.stateTimer = this.nextStateTime;
                }
            } else {
                this.stateTimer = 0;
                this.transitionState();
            }
        }

        if (this.state === 'walking') {
            this.x += this.direction * CONFIG.petSpeed * dt;
            this.y = groundY - this.sprites.idle.height + Math.abs(Math.sin(this.bouncePhase)) * 3;

            const margin = 20;
            if (this.x < margin) {
                this.x = margin;
                this.direction = 1;
            }
            if (this.x + this.sprites.idle.width > sceneWidth - margin) {
                this.x = sceneWidth - this.sprites.idle.width - margin;
                this.direction = -1;
            }
        } else {
            this.y = groundY - this.sprites.idle.height + Math.abs(Math.sin(this.bouncePhase)) * 1.5;
        }
    }

    transitionState() {
        if (this.state === 'idle') {
            if (Math.random() < 0.5) {
                this.state = 'walking';
                this.direction = Math.random() < 0.5 ? -1 : 1;
                this.nextStateTime = this.randomTime(CONFIG.wanderMinMs, CONFIG.wanderMaxMs);
            } else {
                this.nextStateTime = this.randomTime(CONFIG.idleMinMs, CONFIG.idleMaxMs);
            }
        } else {
            this.state = 'idle';
            this.nextStateTime = this.randomTime(CONFIG.idleMinMs, CONFIG.idleMaxMs);
        }
    }

    draw(ctx) {
        let sprite;
        if (this.state === 'idle') {
            sprite = this.sprites.idle;
        } else {
            // Alternate walk frames every ~250ms — sprite picked from frameIndex parity
            // so each pose holds for the full interval (previous code only flashed walk2
            // for one render frame at the swap boundary).
            sprite = (this.frameIndex % 2 === 0) ? this.sprites.walk1 : this.sprites.walk2;
            if (this.frameTimer > 250) {
                this.frameTimer = 0;
                this.frameIndex++;
            }
        }

        ctx.save();
        if (this.direction === -1) {
            ctx.translate(this.x + sprite.width, this.y);
            ctx.scale(-1, 1);
            ctx.drawImage(sprite, 0, 0);
        } else {
            ctx.drawImage(sprite, this.x, this.y);
        }
        ctx.restore();
    }
}

// ---------------------------------------------------------------------------
// Scene Manager
// ---------------------------------------------------------------------------

let sceneCanvas = null;
let sceneCtx = null;
let animationId = null;
let lastTime = 0;
let entities = [];
let sceneWidth = 0;
let sceneHeight = 0;
let groundY = 0;
let isNight = false;
let frameCounter = 0;

function getSceneHeight() {
    return window.innerWidth <= 720 ? CONFIG.sceneHeightMobile : CONFIG.sceneHeight;
}

function getTimeOfDayState() {
    const hour = new Date().getHours() + new Date().getMinutes() / 60;
    return hour >= 21 || hour < 6;
}

function getSkyBodyYRatio() {
    const hour = new Date().getHours() + new Date().getMinutes() / 60;
    // Night: park the moon high in the sky (the old code dropped it onto the
    // horizon, where it looked broken). Day: a gentle arc that stays well
    // above the ground — the sun used to sit too low at dawn/dusk.
    if (hour < 6 || hour > 18) return 0.18;
    const t = (hour - 6) / 12;
    return 0.32 - 0.20 * Math.sin(t * Math.PI);
}

function buildScene() {
    entities = [];
    sceneWidth = sceneCanvas.width;
    sceneHeight = sceneCanvas.height;
    groundY = Math.floor(sceneHeight * CONFIG.groundYRatio);
    isNight = getTimeOfDayState();

    const edge = Math.max(16, Math.floor(sceneWidth * 0.03));
    const usable = sceneWidth - edge * 2;

    // --- Sun or Moon ---
    // Positioned higher in the sky so the bottom has a small gap before the max height of the tallest trees
    const skyBody = isNight ? SPRITES.moon : SPRITES.sun;
    if (skyBody) {
        const treeHeight = SPRITES.tree ? SPRITES.tree.height : 20 * PIXEL_SIZE;
        const gap = 2 * PIXEL_SIZE;
        const skyY = groundY - treeHeight - skyBody.height - gap;
        entities.push(new StaticEntity(skyBody, Math.floor(sceneWidth * 0.78), skyY));
    }

    // --- Clouds (sparse, kept in the upper sky) ---
    if (SPRITES.cloud) {
        const cloudCount = Math.min(4, Math.max(1, Math.round(sceneWidth / 480)));
        for (let i = 0; i < cloudCount; i++) {
            const cx = (sceneWidth / (cloudCount + 1)) * (i + 1) + (Math.random() * 50 - 25);
            const cy = 12 + Math.random() * (groundY * 0.18);
            const speed = (0.003 + Math.random() * 0.007) * (Math.random() < 0.5 ? 1 : -1);
            entities.push(new CloudEntity(SPRITES.cloud, cx, cy, speed));
        }
    }

    // --- Static Objects Random Layout (Benches, Trees, Bushes) with Overlap Prevention ---
    const staticObjectsToPlace = [];
    if (SPRITES.bench) {
        staticObjectsToPlace.push({ sprite: SPRITES.bench, type: 'bench' });
    }
    const treeCount = Math.min(4, Math.max(1, Math.round(sceneWidth / 440)));
    if (SPRITES.tree) {
        for (let i = 0; i < treeCount; i++) {
            staticObjectsToPlace.push({ sprite: SPRITES.tree, type: 'tree' });
        }
    }
    const bushCount = Math.min(5, Math.max(1, Math.round(sceneWidth / 360)));
    if (SPRITES.bush) {
        for (let i = 0; i < bushCount; i++) {
            staticObjectsToPlace.push({ sprite: SPRITES.bush, type: 'bush' });
        }
    }

    // Place largest objects first to make non-overlapping layout easier
    staticObjectsToPlace.sort((a, b) => b.sprite.width - a.sprite.width);

    const placedStaticObjects = [];
    const minGap = 4 * PIXEL_SIZE; // Spacer between objects

    for (const obj of staticObjectsToPlace) {
        let placed = false;
        let bestX = 0;

        // Try placement with spacing gap
        for (let attempt = 0; attempt < 100; attempt++) {
            const maxX = sceneWidth - edge - obj.sprite.width;
            const x = Math.round(edge + Math.random() * (maxX - edge));
            let overlap = false;
            for (const other of placedStaticObjects) {
                if (!(x + obj.sprite.width + minGap <= other.x || other.x + other.width + minGap <= x)) {
                    overlap = true;
                    break;
                }
            }
            if (!overlap) {
                bestX = x;
                placed = true;
                break;
            }
        }

        // Fallback 1: Try without gap if tight on space
        if (!placed) {
            for (let attempt = 0; attempt < 50; attempt++) {
                const maxX = sceneWidth - edge - obj.sprite.width;
                const x = Math.round(edge + Math.random() * (maxX - edge));
                let overlap = false;
                for (const other of placedStaticObjects) {
                    if (!(x + obj.sprite.width <= other.x || other.x + other.width <= x)) {
                        overlap = true;
                        break;
                    }
                }
                if (!overlap) {
                    bestX = x;
                    placed = true;
                    break;
                }
            }
        }

        // Fallback 2: Direct random placement if completely full
        if (!placed) {
            const maxX = sceneWidth - edge - obj.sprite.width;
            bestX = Math.round(edge + Math.random() * (maxX - edge));
        }

        const y = groundY - obj.sprite.height;
        placedStaticObjects.push({
            x: bestX,
            y: y,
            width: obj.sprite.width,
            height: obj.sprite.height,
            type: obj.type
        });
        entities.push(new StaticEntity(obj.sprite, bestX, y));
    }

    // --- Pets (spread out initially without overlapping static objects or other pets) ---
    const petCount = Math.min(5, Math.max(2, Math.round(sceneWidth / 480)));
    const placedPets = [];
    for (let i = 0; i < petCount; i++) {
        const isCat = i % 2 === 0;
        const sprites = isCat
            ? { idle: SPRITES.catIdle, walk1: SPRITES.catWalk1, walk2: SPRITES.catWalk2 }
            : { idle: SPRITES.dogIdle, walk1: SPRITES.dogWalk1, walk2: SPRITES.dogWalk2 };

        if (sprites.idle) {
            let px = 0;
            let found = false;
            for (let attempt = 0; attempt < 100; attempt++) {
                const base = edge + (usable / (petCount + 1)) * (i + 1);
                px = Math.round(base - sprites.idle.width / 2 + (Math.random() * 40 - 20));

                if (px < edge) px = edge;
                if (px + sprites.idle.width > sceneWidth - edge) px = sceneWidth - edge - sprites.idle.width;

                let overlap = false;
                for (const obj of placedStaticObjects) {
                    if (!(px + sprites.idle.width <= obj.x || obj.x + obj.width <= px)) {
                        overlap = true;
                        break;
                    }
                }
                if (!overlap) {
                    for (const other of placedPets) {
                        const otherW = other.sprites.idle.width;
                        if (!(px + sprites.idle.width <= other.x || other.x + otherW <= px)) {
                            overlap = true;
                            break;
                        }
                    }
                }
                if (!overlap) {
                    found = true;
                    break;
                }
            }
            if (!found) {
                const maxX = sceneWidth - edge - sprites.idle.width;
                px = Math.round(edge + Math.random() * (maxX - edge));
            }

            const pet = new PetEntity(sprites, px, groundY - sprites.idle.height, isCat ? 'cat' : 'dog');
            if (i % 3 === 0) {
                pet.state = 'walking';
                pet.direction = Math.random() < 0.5 ? -1 : 1;
                pet.nextStateTime = pet.randomTime(CONFIG.wanderMinMs, CONFIG.wanderMaxMs);
            }
            entities.push(pet);
            placedPets.push(pet);
        }
    }
}

function drawGround(ctx) {
    const isWhite = spriteColorRGB.trim().startsWith('255');
    ctx.fillStyle = `rgb(${spriteColorRGB})`;
    ctx.fillRect(0, groundY, sceneWidth, 2);
    ctx.fillStyle = isWhite ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)';
    ctx.fillRect(0, groundY + 2, sceneWidth, sceneHeight - groundY - 2);
}

function gameLoop(timestamp) {
    if (!sceneCanvas || sceneCanvas.dataset.active !== 'true') {
        return;
    }

    const dt = lastTime ? (timestamp - lastTime) : 16;
    lastTime = timestamp;
    frameCounter++;

    // Re-check the page background a couple of times a second so the scene
    // adapts when a dark-mode extension turns on/off after load.
    if (frameCounter % 30 === 0) {
        refreshSpriteColor();
    }

    if (frameCounter % 3600 === 0) {
        const wasNight = isNight;
        isNight = getTimeOfDayState();
        if (wasNight !== isNight) {
            buildScene();
        }
    }

    sceneCtx.clearRect(0, 0, sceneWidth, sceneHeight);
    drawGround(sceneCtx);

    const staticObjectsForCollision = entities
        .filter(e => e instanceof StaticEntity && e.canvas !== SPRITES.sun && e.canvas !== SPRITES.moon)
        .map(e => ({ x: e.x, width: e.canvas.width }));

    const idlePets = entities.filter(e => e instanceof PetEntity && e.state === 'idle');

    for (const entity of entities) {
        if (entity instanceof CloudEntity) {
            entity.update(dt, sceneWidth);
        }
        if (entity instanceof PetEntity) {
            entity.update(dt, groundY, sceneWidth, idlePets, staticObjectsForCollision);
        }
        entity.draw(sceneCtx);
    }

    animationId = requestAnimationFrame(gameLoop);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function initScene() {
    if (sceneCanvas && sceneCanvas.dataset.active === 'true') {
        return;
    }

    let container = document.getElementById('pixel-scene-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'pixel-scene-container';
        document.body.appendChild(container);
    }

    sceneCanvas = document.createElement('canvas');
    sceneCanvas.id = 'pixel-scene-canvas';
    sceneCanvas.dataset.active = 'true';
    container.appendChild(sceneCanvas);
    sceneCtx = sceneCanvas.getContext('2d');

    // Pick the sprite color for the current background (handles Dark Reader)
    // before the first paint, then build sprites in that color.
    spriteColorRGB = detectSpriteColor();
    buildSprites();

    resizeScene();
    buildScene();
    lastTime = 0;
    animationId = requestAnimationFrame(gameLoop);

    window.addEventListener('resize', onResize);
}

export function destroyScene() {
    if (animationId) {
        cancelAnimationFrame(animationId);
        animationId = null;
    }

    window.removeEventListener('resize', onResize);

    const container = document.getElementById('pixel-scene-container');
    if (container) {
        container.remove();
    }

    sceneCanvas = null;
    sceneCtx = null;
    entities = [];
}

function resizeScene() {
    if (!sceneCanvas) return;

    const newPixelSize = window.innerWidth <= 720 ? 3 : 4;
    if (newPixelSize !== PIXEL_SIZE) {
        PIXEL_SIZE = newPixelSize;
        buildSprites();
    }

    sceneHeight = getSceneHeight();
    sceneWidth = window.innerWidth;
    sceneCanvas.width = sceneWidth;
    sceneCanvas.height = sceneHeight;
    groundY = Math.floor(sceneHeight * CONFIG.groundYRatio);

    if (Object.keys(SPRITES).length > 0) {
        buildScene();
    }
}

let resizeTimeout = null;
function onResize() {
    if (resizeTimeout) clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(resizeScene, 150);
}
