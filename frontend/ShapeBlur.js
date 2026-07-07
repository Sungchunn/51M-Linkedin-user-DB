/**
 * ShapeBlur - WebGL Shader Effect using Three.js
 * Vanilla JavaScript implementation of animated shader effect for button hover
 */

const vertexShader = /* glsl */ `
varying vec2 v_texcoord;
void main() {
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    v_texcoord = uv;
}
`;

const fragmentShader = /* glsl */ `
varying vec2 v_texcoord;

uniform vec2 u_mouse;
uniform vec2 u_resolution;
uniform float u_pixelRatio;

uniform float u_shapeSize;
uniform float u_roundness;
uniform float u_borderSize;
uniform float u_circleSize;
uniform float u_circleEdge;

#ifndef PI
#define PI 3.1415926535897932384626433832795
#endif
#ifndef TWO_PI
#define TWO_PI 6.2831853071795864769252867665590
#endif

#ifndef VAR
#define VAR 0
#endif

#ifndef FNC_COORD
#define FNC_COORD
vec2 coord(in vec2 p) {
    p = p / u_resolution.xy;
    if (u_resolution.x > u_resolution.y) {
        p.x *= u_resolution.x / u_resolution.y;
        p.x += (u_resolution.y - u_resolution.x) / u_resolution.y / 2.0;
    } else {
        p.y *= u_resolution.y / u_resolution.x;
        p.y += (u_resolution.x - u_resolution.y) / u_resolution.x / 2.0;
    }
    p -= 0.5;
    p *= vec2(-1.0, 1.0);
    return p;
}
#endif

#define st0 coord(gl_FragCoord.xy)
#define mx coord(u_mouse * u_pixelRatio)

float sdRoundRect(vec2 p, vec2 b, float r) {
    vec2 d = abs(p - 0.5) * 4.2 - b + vec2(r);
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - r;
}
float sdCircle(in vec2 st, in vec2 center) {
    return length(st - center) * 2.0;
}

float aastep(float threshold, float value) {
    float afwidth = length(vec2(dFdx(value), dFdy(value))) * 0.70710678118654757;
    return smoothstep(threshold - afwidth, threshold + afwidth, value);
}
float fill(float x, float size, float edge) {
    return 1.0 - smoothstep(size - edge, size + edge, x);
}

float strokeAA(float x, float size, float w, float edge) {
    float afwidth = length(vec2(dFdx(x), dFdy(x))) * 0.70710678;
    float d = smoothstep(size - edge - afwidth, size + edge + afwidth, x + w * 0.5)
            - smoothstep(size - edge - afwidth, size + edge + afwidth, x - w * 0.5);
    return clamp(d, 0.0, 1.0);
}

void main() {
    vec2 st = st0 + 0.5;
    vec2 posMouse = mx * vec2(1., -1.) + 0.5;

    float size = u_shapeSize;
    float roundness = u_roundness;
    float borderSize = u_borderSize;
    float circleSize = u_circleSize;
    float circleEdge = u_circleEdge;

    float sdfCircle = fill(
        sdCircle(st, posMouse),
        circleSize,
        circleEdge
    );

    float sdf;
    if (VAR == 0) {
        sdf = sdRoundRect(st, vec2(size), roundness);
        sdf = strokeAA(sdf, 0.0, borderSize, sdfCircle) * 4.0;
    }

    vec3 color = vec3(1.0);
    float alpha = sdf;
    gl_FragColor = vec4(color.rgb, alpha);
}
`;

class ShapeBlur {
    constructor(container, options = {}) {
        this.container = container;
        this.variation = options.variation || 0;
        this.pixelRatioProp = options.pixelRatioProp || 2;
        this.shapeSize = options.shapeSize || 1.2;
        this.roundness = options.roundness || 0.4;
        this.borderSize = options.borderSize || 0.05;
        this.circleSize = options.circleSize || 0.3;
        this.circleEdge = options.circleEdge || 0.5;

        this.animationFrameId = null;
        this.time = 0;
        this.lastTime = 0;

        this.init();
    }

    init() {
        // Check if Three.js is loaded
        if (typeof THREE === 'undefined') {
            console.error('Three.js is required for ShapeBlur');
            return;
        }

        this.vMouse = new THREE.Vector2();
        this.vMouseDamp = new THREE.Vector2();
        this.vResolution = new THREE.Vector2();

        this.scene = new THREE.Scene();
        this.camera = new THREE.OrthographicCamera();
        this.camera.position.z = 1;

        this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
        this.renderer.setClearColor(0x000000, 0);
        this.container.appendChild(this.renderer.domElement);

        const geo = new THREE.PlaneGeometry(1, 1);
        this.material = new THREE.ShaderMaterial({
            vertexShader,
            fragmentShader,
            uniforms: {
                u_mouse: { value: this.vMouseDamp },
                u_resolution: { value: this.vResolution },
                u_pixelRatio: { value: this.pixelRatioProp },
                u_shapeSize: { value: this.shapeSize },
                u_roundness: { value: this.roundness },
                u_borderSize: { value: this.borderSize },
                u_circleSize: { value: this.circleSize },
                u_circleEdge: { value: this.circleEdge }
            },
            defines: { VAR: this.variation },
            transparent: true
        });

        this.quad = new THREE.Mesh(geo, this.material);
        this.scene.add(this.quad);

        this.onPointerMove = this.onPointerMove.bind(this);
        this.resize = this.resize.bind(this);
        this.update = this.update.bind(this);

        document.addEventListener('mousemove', this.onPointerMove);
        document.addEventListener('pointermove', this.onPointerMove);
        window.addEventListener('resize', this.resize);

        // ResizeObserver for container size changes
        this.ro = new ResizeObserver(() => this.resize());
        this.ro.observe(this.container);

        this.resize();
        this.update();
    }

    onPointerMove(e) {
        const rect = this.container.getBoundingClientRect();
        this.vMouse.set(e.clientX - rect.left, e.clientY - rect.top);
    }

    resize() {
        const w = this.container.clientWidth;
        const h = this.container.clientHeight;
        const dpr = Math.min(window.devicePixelRatio, 2);

        this.renderer.setSize(w, h);
        this.renderer.setPixelRatio(dpr);

        this.camera.left = -w / 2;
        this.camera.right = w / 2;
        this.camera.top = h / 2;
        this.camera.bottom = -h / 2;
        this.camera.updateProjectionMatrix();

        this.quad.scale.set(w, h, 1);
        this.vResolution.set(w, h).multiplyScalar(dpr);
        this.material.uniforms.u_pixelRatio.value = dpr;
    }

    update() {
        this.time = performance.now() * 0.001;
        const dt = this.time - this.lastTime;
        this.lastTime = this.time;

        // Smooth mouse movement
        ['x', 'y'].forEach(k => {
            this.vMouseDamp[k] = THREE.MathUtils.damp(
                this.vMouseDamp[k],
                this.vMouse[k],
                8,
                dt
            );
        });

        this.renderer.render(this.scene, this.camera);
        this.animationFrameId = requestAnimationFrame(this.update);
    }

    destroy() {
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
        }
        window.removeEventListener('resize', this.resize);
        document.removeEventListener('mousemove', this.onPointerMove);
        document.removeEventListener('pointermove', this.onPointerMove);
        if (this.ro) {
            this.ro.disconnect();
        }
        if (this.renderer && this.renderer.domElement && this.renderer.domElement.parentNode) {
            this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
        }
        if (this.renderer) {
            this.renderer.dispose();
        }
    }
}

export default ShapeBlur;
