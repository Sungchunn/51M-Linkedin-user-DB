// PROSPECTIQ - Animated Squares Background
// Vanilla canvas implementation of the moving grid animation.
// Instantiated by components/SquaresBackground.js on document.body.

export class SquaresBackground {
    constructor(container, options = {}) {
        this.container = container;
        this.canvas = null;
        this.ctx = null;
        this.rafId = null;

        // borderColor / hoverFillColor options win when provided; otherwise the
        // colors come from the theme tokens (--canvas-*) and follow theme changes.
        this.options = {
            direction: options.direction || 'diagonal',
            speed: options.speed || 0.5,
            squareSize: options.squareSize || 40,
            ...options,
        };

        this.numSquaresX = 0;
        this.numSquaresY = 0;
        this.gridOffset = { x: 0, y: 0 };
        this.hoveredSquare = null;
        this.mouseX = 0;
        this.mouseY = 0;

        this.init();
    }

    init() {
        // Create canvas
        this.canvas = document.createElement('canvas');
        this.canvas.style.position = 'absolute';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.pointerEvents = 'none';
        this.canvas.style.zIndex = '0';

        this.ctx = this.canvas.getContext('2d');
        this.container.style.position = 'relative';
        this.container.insertBefore(this.canvas, this.container.firstChild);

        // Bind methods
        this.handleResize = this.handleResize.bind(this);
        this.handleMouseMove = this.handleMouseMove.bind(this);
        this.handleMouseLeave = this.handleMouseLeave.bind(this);
        this.handleThemeChange = this.handleThemeChange.bind(this);
        this.updateAnimation = this.updateAnimation.bind(this);

        // Setup
        this.readThemeColors();
        this.resizeCanvas();
        this.setupEventListeners();
        this.start();
    }

    readThemeColors() {
        const styles = getComputedStyle(document.documentElement);
        const line = styles.getPropertyValue('--canvas-line').trim();
        const hover = styles.getPropertyValue('--canvas-hover').trim();
        const vignette = styles.getPropertyValue('--canvas-vignette-rgb').trim();

        this.borderColor = this.options.borderColor || line || 'rgba(150, 150, 150, 0.08)';
        this.hoverFillColor = this.options.hoverFillColor || hover || 'rgba(100, 100, 100, 0.05)';
        this.vignetteRgb = vignette || '10, 10, 10';
    }

    handleThemeChange() {
        // drawGrid runs every animation frame, so the next frame picks these up.
        this.readThemeColors();
    }

    resizeCanvas() {
        this.canvas.width = this.container.offsetWidth;
        this.canvas.height = this.container.offsetHeight;
        this.numSquaresX = Math.ceil(this.canvas.width / this.options.squareSize) + 1;
        this.numSquaresY = Math.ceil(this.canvas.height / this.options.squareSize) + 1;
    }

    handleResize() {
        this.resizeCanvas();
    }

    handleMouseMove(event) {
        const rect = this.canvas.getBoundingClientRect();
        this.mouseX = event.clientX - rect.left;
        this.mouseY = event.clientY - rect.top;

        const startX = Math.floor(this.gridOffset.x / this.options.squareSize) * this.options.squareSize;
        const startY = Math.floor(this.gridOffset.y / this.options.squareSize) * this.options.squareSize;

        const hoveredSquareX = Math.floor((this.mouseX + this.gridOffset.x - startX) / this.options.squareSize);
        const hoveredSquareY = Math.floor((this.mouseY + this.gridOffset.y - startY) / this.options.squareSize);

        if (
            !this.hoveredSquare ||
            this.hoveredSquare.x !== hoveredSquareX ||
            this.hoveredSquare.y !== hoveredSquareY
        ) {
            this.hoveredSquare = { x: hoveredSquareX, y: hoveredSquareY };
        }
    }

    handleMouseLeave() {
        this.hoveredSquare = null;
    }

    setupEventListeners() {
        window.addEventListener('resize', this.handleResize);
        window.addEventListener('themechange', this.handleThemeChange);
        this.container.addEventListener('mousemove', this.handleMouseMove);
        this.container.addEventListener('mouseleave', this.handleMouseLeave);
    }

    drawGrid() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        const startX = Math.floor(this.gridOffset.x / this.options.squareSize) * this.options.squareSize;
        const startY = Math.floor(this.gridOffset.y / this.options.squareSize) * this.options.squareSize;

        // Draw squares
        for (let x = startX; x < this.canvas.width + this.options.squareSize; x += this.options.squareSize) {
            for (let y = startY; y < this.canvas.height + this.options.squareSize; y += this.options.squareSize) {
                const squareX = x - (this.gridOffset.x % this.options.squareSize);
                const squareY = y - (this.gridOffset.y % this.options.squareSize);

                // Check if this square is hovered
                if (
                    this.hoveredSquare &&
                    Math.floor((x - startX) / this.options.squareSize) === this.hoveredSquare.x &&
                    Math.floor((y - startY) / this.options.squareSize) === this.hoveredSquare.y
                ) {
                    this.ctx.fillStyle = this.hoverFillColor;
                    this.ctx.fillRect(squareX, squareY, this.options.squareSize, this.options.squareSize);
                }

                // Draw border
                this.ctx.strokeStyle = this.borderColor;
                this.ctx.lineWidth = 1;
                this.ctx.strokeRect(squareX, squareY, this.options.squareSize, this.options.squareSize);
            }
        }

        // Apply radial gradient fade
        const gradient = this.ctx.createRadialGradient(
            this.canvas.width / 2,
            this.canvas.height / 2,
            0,
            this.canvas.width / 2,
            this.canvas.height / 2,
            Math.sqrt(this.canvas.width ** 2 + this.canvas.height ** 2) / 2
        );
        gradient.addColorStop(0, `rgba(${this.vignetteRgb}, 0)`);
        gradient.addColorStop(1, `rgba(${this.vignetteRgb}, 0.8)`);

        this.ctx.fillStyle = gradient;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }

    updateAnimation() {
        const effectiveSpeed = Math.max(this.options.speed, 0.1);
        const size = this.options.squareSize;

        switch (this.options.direction) {
            case 'right':
                this.gridOffset.x = (this.gridOffset.x - effectiveSpeed + size) % size;
                break;
            case 'left':
                this.gridOffset.x = (this.gridOffset.x + effectiveSpeed + size) % size;
                break;
            case 'up':
                this.gridOffset.y = (this.gridOffset.y + effectiveSpeed + size) % size;
                break;
            case 'down':
                this.gridOffset.y = (this.gridOffset.y - effectiveSpeed + size) % size;
                break;
            case 'diagonal':
                this.gridOffset.x = (this.gridOffset.x - effectiveSpeed + size) % size;
                this.gridOffset.y = (this.gridOffset.y - effectiveSpeed + size) % size;
                break;
            default:
                break;
        }

        this.drawGrid();
        this.rafId = requestAnimationFrame(this.updateAnimation);
    }

    start() {
        if (!this.rafId) {
            this.rafId = requestAnimationFrame(this.updateAnimation);
        }
    }

    pause() {
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
            this.rafId = null;
        }
    }

    dispose() {
        this.pause();
        window.removeEventListener('resize', this.handleResize);
        window.removeEventListener('themechange', this.handleThemeChange);
        this.container.removeEventListener('mousemove', this.handleMouseMove);
        this.container.removeEventListener('mouseleave', this.handleMouseLeave);

        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }

        this.canvas = null;
        this.ctx = null;
    }
}
