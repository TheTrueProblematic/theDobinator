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

// --- Grass Tuft 8x6 ---
const grassTuft = [
    [_,_,_,B,_,_,_,_],
    [_,_,B,B,B,_,_,_],
    [_,_,B,B,B,B,_,_],
    [_,B,B,B,B,B,B,_],
    [B,B,B,B,B,B,B,B],
    [B,B,B,B,B,B,B,B],
];


// -------------------------END MARKER----------------------------------------


// ---------------------------------------------------------------------------
// Sprite Rendering — draws pixel data arrays directly to canvas
// ---------------------------------------------------------------------------

let PIXEL_SIZE = 4;

/**
 * Render a sprite data array into an offscreen canvas.
 * @param {string[][]} data  — Pixel array ("0,0,0" = black, "0,0,0,0" = transparent)
 * @returns {HTMLCanvasElement}
 */
function renderSprite(data) {
    const rows = data.length;
    const cols = data[0] ? data[0].length : 0;
    const canvas = document.createElement('canvas');
    canvas.width = cols * PIXEL_SIZE;
    canvas.height = rows * PIXEL_SIZE;
    const ctx = canvas.getContext('2d');

    for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
            const val = data[r][c];
            if (val && val !== '0, 0, 0, 0') {
                // Parse RGB values — only draw non-transparent pixels
                const parts = val.split(',').map(s => parseInt(s.trim(), 10));
                if (parts.length >= 3 && !(parts.length === 4 && parts[3] === 0)) {
                    ctx.fillStyle = `rgb(${parts[0]},${parts[1]},${parts[2]})`;
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
    SPRITES = {
        catIdle: renderSprite(catIdle),
        catWalk1: renderSprite(catWalk1),
        catWalk2: renderSprite(catWalk2),
        dogIdle: renderSprite(dogIdle),
        dogWalk1: renderSprite(dogWalk1),
        dogWalk2: renderSprite(dogWalk2),
        tree: renderSprite(tree),
        bench: renderSprite(bench),
        sun: renderSprite(sun),
        moon: renderSprite(moon),
        cloud: renderSprite(cloud),
        grassTuft: renderSprite(grassTuft),
    };
}
buildSprites();

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const CONFIG = {
    sceneHeight: 180,          // Desktop scene height
    sceneHeightMobile: 140,    // Mobile scene height
    groundYRatio: 0.72,        // Ground line at 72% of scene height
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

    update(dt, groundY, sceneWidth) {
        this.stateTimer += dt;
        this.bouncePhase += dt * 0.004;
        this.frameTimer += dt;

        if (this.stateTimer >= this.nextStateTime) {
            this.stateTimer = 0;
            this.transitionState();
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

function getSunYRatio() {
    const hour = new Date().getHours() + new Date().getMinutes() / 60;
    if (hour < 6 || hour > 18) return 0.7;
    const t = (hour - 6) / 12;
    return 0.65 - 0.55 * Math.sin(t * Math.PI);
}

function buildScene() {
    entities = [];
    sceneWidth = sceneCanvas.width;
    sceneHeight = sceneCanvas.height;
    groundY = Math.floor(sceneHeight * CONFIG.groundYRatio);
    isNight = getTimeOfDayState();

    // --- Sun or Moon ---
    const sunY = Math.floor(sceneHeight * getSunYRatio());
    const skyBody = isNight ? SPRITES.moon : SPRITES.sun;
    if (skyBody) {
        entities.push(new StaticEntity(skyBody, Math.floor(sceneWidth * 0.75), sunY));
    }

    // --- Clouds ---
    if (SPRITES.cloud) {
        const cloudCount = Math.max(2, Math.floor(sceneWidth / 300));
        for (let i = 0; i < cloudCount; i++) {
            const cx = (sceneWidth / (cloudCount + 1)) * (i + 1) + (Math.random() * 60 - 30);
            const cy = 15 + Math.random() * (groundY * 0.25);
            const speed = (0.003 + Math.random() * 0.008) * (Math.random() < 0.5 ? 1 : -1);
            entities.push(new CloudEntity(SPRITES.cloud, cx, cy, speed));
        }
    }

    // --- Trees ---
    if (SPRITES.tree) {
        const treeCount = Math.max(2, Math.floor(sceneWidth / 250));
        for (let i = 0; i < treeCount; i++) {
            const tx = 30 + ((sceneWidth - 60) / (treeCount + 1)) * (i + 1) + (Math.random() * 40 - 20);
            entities.push(new StaticEntity(SPRITES.tree, tx, groundY - SPRITES.tree.height));
        }
    }

    // --- Bench ---
    if (SPRITES.bench) {
        const bx = Math.floor(sceneWidth * 0.45);
        entities.push(new StaticEntity(SPRITES.bench, bx, groundY - SPRITES.bench.height));
    }

    // --- Grass tufts ---
    if (SPRITES.grassTuft) {
        const tuftCount = Math.max(4, Math.floor(sceneWidth / 100));
        for (let i = 0; i < tuftCount; i++) {
            const gx = Math.random() * (sceneWidth - SPRITES.grassTuft.width);
            entities.push(new StaticEntity(SPRITES.grassTuft, gx, groundY - SPRITES.grassTuft.height));
        }
    }

    // --- Pets ---
    const petCount = Math.min(5, Math.max(3, Math.floor(sceneWidth / 400) + 1));
    for (let i = 0; i < petCount; i++) {
        const isCat = i % 2 === 0;
        const sprites = isCat
            ? { idle: SPRITES.catIdle, walk1: SPRITES.catWalk1, walk2: SPRITES.catWalk2 }
            : { idle: SPRITES.dogIdle, walk1: SPRITES.dogWalk1, walk2: SPRITES.dogWalk2 };

        if (sprites.idle) {
            const px = 40 + Math.random() * (sceneWidth - 80 - (sprites.idle.width || 64));
            const pet = new PetEntity(sprites, px, groundY - (sprites.idle.height || 64), isCat ? 'cat' : 'dog');
            if (i % 3 === 0) {
                pet.state = 'walking';
                pet.direction = Math.random() < 0.5 ? -1 : 1;
                pet.nextStateTime = pet.randomTime(CONFIG.wanderMinMs, CONFIG.wanderMaxMs);
            }
            entities.push(pet);
        }
    }
}

function drawGround(ctx) {
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, groundY, sceneWidth, 2);
    ctx.fillStyle = 'rgba(0, 0, 0, 0.03)';
    ctx.fillRect(0, groundY + 2, sceneWidth, sceneHeight - groundY - 2);
}

function gameLoop(timestamp) {
    if (!sceneCanvas || sceneCanvas.dataset.active !== 'true') {
        return;
    }

    const dt = lastTime ? (timestamp - lastTime) : 16;
    lastTime = timestamp;
    frameCounter++;

    if (frameCounter % 3600 === 0) {
        const wasNight = isNight;
        isNight = getTimeOfDayState();
        if (wasNight !== isNight) {
            buildScene();
        }
    }

    sceneCtx.clearRect(0, 0, sceneWidth, sceneHeight);
    drawGround(sceneCtx);

    for (const entity of entities) {
        if (entity instanceof CloudEntity) {
            entity.update(dt, sceneWidth);
        }
        if (entity instanceof PetEntity) {
            entity.update(dt, groundY, sceneWidth);
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
