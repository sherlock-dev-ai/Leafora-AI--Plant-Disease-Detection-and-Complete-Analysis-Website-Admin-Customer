// landing.js - Interactions for the redesigned landing page

// --- Global Theme Definitions (Shared with UI) ---
window.curatedThemes = [
    // --- Group 1: Particles (Nature & Physics) ---
    { id: 'gen_0', type: 'particles', name: 'Golden Fireflies', opts: { count: 60, color: 'rgba(255, 215, 0, 0.8)', sizeVar: 3, speedX: 0.5, speedY: 0.5, wobble: true } },
    { id: 'gen_1', type: 'particles', name: 'Winter Snow', opts: { count: 100, color: 'rgba(255, 255, 255, 0.9)', fall: true, speedY: 2, speedX: 0.5, sizeVar: 2 } },
    { id: 'gen_2', type: 'particles', name: 'Heavy Rain', opts: { count: 300, color: 'rgba(174, 194, 224, 0.6)', fall: true, speedY: 15, speedX: 0, shape: 'rect', sizeVar: 0, minSize: 2 } },
    { id: 'gen_3', type: 'particles', name: 'Rising Bubbles', opts: { count: 40, color: 'rgba(255, 100, 200, 0.4)', speedY: -1, speedX: 0.2, wobble: true, sizeVar: 10, fill: true } },
    { id: 'gen_4', type: 'particles', name: 'Neural Network', opts: { count: 60, color: 'rgba(100, 200, 255, 0.8)', connect: true, connectDist: 120, speedX: 0.5, speedY: 0.5 } },
    { id: 'gen_5', type: 'particles', name: 'Rising Embers', opts: { count: 80, color: 'rgba(255, 80, 0, 0.8)', speedY: -2, speedX: 0.5, sizeVar: 3, fill: true } },
    { id: 'gen_6', type: 'particles', name: 'Deep Space Stars', opts: { count: 200, color: 'rgba(255, 255, 255, 1)', speedX: 0.05, speedY: 0.05, sizeVar: 1, minSize: 0.5 } },
    { id: 'gen_7', type: 'particles', name: 'Confetti Party', opts: { count: 100, color: 'hsl(random, 70%, 50%)', speedY: 3, speedX: 2, wobble: true, shape: 'square', fill: true } },

    // --- Group 2: Waves (Flow & Frequency) ---
    { id: 'gen_8', type: 'waves', name: 'Deep Ocean', opts: { count: 5, color: 'rgba(0, 100, 255, ALPHA)', speed: 0.02, amp: 40, freq: 0.01 } },
    { id: 'gen_9', type: 'waves', name: 'High Frequency', opts: { count: 3, color: 'rgba(0, 255, 100, ALPHA)', speed: 0.05, amp: 20, freq: 0.05 } },
    { id: 'gen_10', type: 'waves', name: 'Complex Interference', opts: { count: 6, color: 'rgba(180, 50, 255, ALPHA)', complex: true, speed: 0.01, amp: 60 } },
    { id: 'gen_11', type: 'waves', name: 'Neon Strings', opts: { count: 8, color: 'rgba(0, 255, 255, ALPHA)', lineWidth: 1, speed: 0.03, amp: 30 } },
    { id: 'gen_12', type: 'waves', name: 'Red Ribbon', opts: { count: 10, color: 'rgba(255, 0, 50, ALPHA)', lineWidth: 4, speed: 0.01, amp: 80, freq: 0.005 } },
    { id: 'gen_13', type: 'waves', name: 'Toxic Tide', opts: { count: 4, color: 'rgba(100, 255, 0, ALPHA)', speed: 0.04, amp: 50, complex: true } },
    { id: 'gen_14', type: 'waves', name: 'White Pulse', opts: { count: 3, color: 'rgba(255, 255, 255, ALPHA)', speed: 0.1, amp: 10, freq: 0.02 } },
    { id: 'gen_15', type: 'waves', name: 'Digital Sea', opts: { count: 20, color: 'rgba(0, 255, 200, ALPHA)', res: 20, speed: 0.02, amp: 20 } },

    // --- Group 3: Grid (Perspective & Geometry) ---
    { id: 'gen_16', type: 'grid', name: 'Retro Synthwave', opts: { color: '#ff00ff', perspective: true, speed: 2, size: 60 } },
    { id: 'gen_17', type: 'grid', name: 'Architect Blueprint', opts: { color: '#ffffff', size: 30, speed: 0 } },
    { id: 'gen_18', type: 'grid', name: 'Cyber Floor', opts: { color: '#00ff00', perspective: true, speed: 5, size: 40 } },
    { id: 'gen_19', type: 'grid', name: 'The Grid (Tron)', opts: { color: '#00ffff', perspective: true, speed: 1, size: 80 } },
    { id: 'gen_20', type: 'grid', name: 'Fine Graph', opts: { color: '#444', size: 10, speed: 0.5 } },
    { id: 'gen_21', type: 'grid', name: 'Danger Zone', opts: { color: '#ff0000', perspective: true, speed: 8, size: 50 } },
    { id: 'gen_22', type: 'grid', name: 'Warp Mesh', opts: { color: '#aaa', perspective: true, speed: 3, size: 20 } },
    { id: 'gen_23', type: 'grid', name: 'Golden Horizon', opts: { color: '#ffd700', perspective: true, speed: 0.5, size: 100 } },

    // --- Group 4: Spiral (Cosmic & Abstract) ---
    { id: 'gen_24', type: 'spiral', name: 'Purple Galaxy', opts: { color: '#a020f0', count: 200, speed: 0.01, expand: false, trail: 0.1 } },
    { id: 'gen_25', type: 'spiral', name: 'Hypnotic Wheel', opts: { color: '#ffffff', count: 300, speed: 0.05, expand: false, size: 1 } },
    { id: 'gen_26', type: 'spiral', name: 'Red Vortex', opts: { color: '#ff0000', count: 150, speed: 0.03, expand: true, trail: 0.2 } },
    { id: 'gen_27', type: 'spiral', name: 'Cosmic Flower', opts: { color: '#ff69b4', count: 100, speed: 0.02, expand: true } },
    { id: 'gen_28', type: 'spiral', name: 'Radar Sweep', opts: { color: '#00ff00', count: 50, speed: 0.1, size: 4 } },
    { id: 'gen_29', type: 'spiral', name: 'Nebula Cloud', opts: { color: '#00ffff', count: 200, speed: 0.005, trail: 0.05 } },
    { id: 'gen_30', type: 'spiral', name: 'Black Hole Event', opts: { color: '#ffffff', count: 300, speed: 0.04, expand: true, trail: 0.3 } },
    { id: 'gen_31', type: 'spiral', name: 'Solar Flare', opts: { color: '#ffaa00', count: 120, speed: 0.02, size: 3, expand: true } },

    // --- Group 5: Matrix (Digital Rain) ---
    { id: 'gen_32', type: 'matrix', name: 'Classic Matrix', opts: { color: '#00ff00', size: 20 } },
    { id: 'gen_33', type: 'matrix', name: 'Ice Code', opts: { color: '#00ffff', size: 16 } },
    { id: 'gen_34', type: 'matrix', name: 'System Failure', opts: { color: '#ff0000', size: 24 } },
    { id: 'gen_35', type: 'matrix', name: 'Golden Data', opts: { color: '#ffd700', size: 18 } },
    { id: 'gen_36', type: 'matrix', name: 'Ghost Protocol', opts: { color: 'rgba(255,255,255,0.5)', size: 14 } },
    { id: 'gen_37', type: 'matrix', name: 'Night Mode', opts: { color: '#00008b', size: 22 } },
    { id: 'gen_38', type: 'matrix', name: 'Purple Rain', opts: { color: '#800080', size: 20 } },
    { id: 'gen_39', type: 'matrix', name: 'Glitch Stream', opts: { color: '#cccccc', size: 12 } },

    // --- Group 6: Tunnel (3D Travel) ---
    { id: 'gen_40', type: 'tunnel', name: 'Warp Speed', opts: { color: '#ffffff', shape: 'circle', speed: 4, count: 20 } },
    { id: 'gen_41', type: 'tunnel', name: 'Wormhole', opts: { color: '#ff00ff', shape: 'circle', speed: 2, count: 15, space: 100 } },
    { id: 'gen_42', type: 'tunnel', name: 'Retro Passage', opts: { color: '#00ff00', shape: 'square', speed: 3, count: 10 } },
    { id: 'gen_43', type: 'tunnel', name: 'Blue Tube', opts: { color: '#0000ff', shape: 'circle', speed: 5, count: 30 } },
    { id: 'gen_44', type: 'tunnel', name: 'The Cave', opts: { color: '#8b4513', shape: 'square', speed: 1, count: 8 } },
    { id: 'gen_45', type: 'tunnel', name: 'Hyperloop', opts: { color: '#00ffff', shape: 'circle', speed: 8, count: 12 } },
    { id: 'gen_46', type: 'tunnel', name: 'Abyss', opts: { color: '#333333', shape: 'square', speed: 2, count: 20 } },
    { id: 'gen_47', type: 'tunnel', name: 'Time Vortex', opts: { color: '#ffa500', shape: 'circle', speed: 6, count: 25 } },

    // --- Specials ---
    { id: 'gen_48', type: 'particles', name: 'Chaos Theory', opts: { count: 150, color: 'hsl(random, 100%, 50%)', speedX: 3, speedY: 3, connect: true, connectDist: 50 } },
    { id: 'gen_49', type: 'waves', name: 'Rainbow Flow', opts: { count: 10, color: 'hsl(index, 70%, 50%, ALPHA)', speed: 0.03, amp: 40 } }
];

document.addEventListener('DOMContentLoaded', function() {
    initHeroCanvas();
    initScrollAnimations();
    initTypingEffect();
    initCounters();
    
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });
});

// --- Hero Canvas Animation System ---
function initHeroCanvas() {
    console.log("Initializing Hero Canvas...");
    // Look for landing-specific canvas first, then fallback to generic
    const canvas = document.getElementById('landingHeroCanvas') || document.getElementById('heroCanvas');
    
    if (!canvas) {
        console.error("Hero Canvas not found!");
        return;
    }
    
    // Cleanup previous instance
    if (window.heroAnimationId) cancelAnimationFrame(window.heroAnimationId);
    if (window.heroResizeHandler) window.removeEventListener('resize', window.heroResizeHandler);

    const ctx = canvas.getContext('2d');
    let width, height;
    let renderer = null;

    // --- Renderer Implementations ---
    
    const Renderers = {
        // 1. Standard Particles (Default, Leaf, Snow, etc.)
        particles: {
            particles: [],
            init: function(theme) {
                this.particles = [];
                this.theme = theme;
                
                // Configurable count via data-particle-count
                const attrCount = canvas.getAttribute('data-particle-count');
                const count = attrCount ? parseInt(attrCount) : (theme === 'dots' ? (window.innerWidth < 768 ? 100 : 200) : (window.innerWidth < 768 ? 40 : 70));
                
                for (let i = 0; i < count; i++) {
                    this.particles.push(new Particle(width, height, theme));
                }
            },
            animate: function() {
                ctx.clearRect(0, 0, width, height);
                
                // Draw connections if not disabled
                const drawLines = !canvas.hasAttribute('data-no-lines') && 
                                  ['default', 'leaf', 'net', 'constellation', 'polygons'].includes(this.theme || 'default');

                this.particles.forEach((p, index) => {
                    p.update(width, height);
                    p.draw(ctx);

                    if (drawLines) {
                        for (let j = index + 1; j < this.particles.length; j++) {
                            const p2 = this.particles[j];
                            const dx = p.x - p2.x;
                            const dy = p.y - p2.y;
                            const dist = Math.sqrt(dx*dx + dy*dy);
                            const maxDist = this.theme === 'leaf' ? 180 : 150;
                            
                            if (dist < maxDist) {
                                const opacity = (1 - dist/maxDist);
                                ctx.lineWidth = 1;

                                if (this.theme === 'default' || this.theme === 'leaf' || this.theme === 'customer') {
                                     // Randomly make some lines glow green
                                     const isGlow = (index + j) % 7 === 0; 
                                     if (isGlow) {
                                         ctx.strokeStyle = `rgba(34, 197, 94, ${0.7 * opacity})`;
                                         ctx.lineWidth = 1.5;
                                         // Optional: slight shadow for glow effect
                                         ctx.shadowBlur = 5;
                                         ctx.shadowColor = 'rgba(34, 197, 94, 0.5)';
                                     } else {
                                         ctx.strokeStyle = `rgba(255, 255, 255, ${0.2 * opacity})`;
                                         ctx.shadowBlur = 0;
                                     }
                                } else if (this.theme === 'net') {
                                     ctx.strokeStyle = `rgba(255, 255, 255, ${0.8 * opacity})`;
                                     ctx.lineWidth = 2;
                                } else {
                                     ctx.strokeStyle = `rgba(255, 255, 255, ${0.15 * opacity})`;
                                }
                                
                                ctx.beginPath();
                                if (this.theme === 'customer' && (index + j) % 15 === 0) {
                                    // Rare curved bending lines for customer page
                                    const midX = (p.x + p2.x) / 2 + Math.sin(Date.now() * 0.001 + index) * 30;
                                    const midY = (p.y + p2.y) / 2 + Math.cos(Date.now() * 0.001 + j) * 30;
                                    ctx.moveTo(p.x, p.y);
                                    ctx.quadraticCurveTo(midX, midY, p2.x, p2.y);
                                } else {
                                    ctx.moveTo(p.x, p.y);
                                    ctx.lineTo(p2.x, p2.y);
                                }
                                ctx.stroke();
                                ctx.shadowBlur = 0; // Reset for next lines/particles
                            }
                        }
                    }
                });
            }
        },

        // 2. Waves
        waves: {
            offset: 0,
            init: function() {},
            animate: function() {
                ctx.clearRect(0, 0, width, height);
                ctx.lineWidth = 2;
                this.offset += 0.05;
                
                for (let i = 0; i < 5; i++) {
                    ctx.beginPath();
                    ctx.strokeStyle = `rgba(255, 255, 255, ${0.1 + i * 0.1})`;
                    for (let x = 0; x < width; x += 5) {
                        const y = height/2 + Math.sin(x * 0.01 + this.offset + i) * (50 + i * 20) * Math.sin(this.offset * 0.5);
                        if (x === 0) ctx.moveTo(x, y);
                        else ctx.lineTo(x, y);
                    }
                    ctx.stroke();
                }
            }
        },

        // 3. Matrix (Digital Rain)
        matrix: {
            drops: [],
            init: function() {
                const columns = Math.floor(width / 20);
                this.drops = Array(columns).fill(1);
            },
            animate: function() {
                ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
                ctx.fillRect(0, 0, width, height);
                ctx.fillStyle = '#0F0';
                ctx.font = '15px monospace';
                
                for (let i = 0; i < this.drops.length; i++) {
                    const text = String.fromCharCode(0x30A0 + Math.random() * 96);
                    ctx.fillText(text, i * 20, this.drops[i] * 20);
                    if (this.drops[i] * 20 > height && Math.random() > 0.975) {
                        this.drops[i] = 0;
                    }
                    this.drops[i]++;
                }
            }
        },

        // 4. Circuit
        circuit: {
            nodes: [],
            pulses: [],
            init: function() {
                this.nodes = [];
                const cols = Math.floor(width / 100);
                const rows = Math.floor(height / 100);
                for(let i=0; i<cols; i++) {
                    for(let j=0; j<rows; j++) {
                        if(Math.random() > 0.5) {
                            this.nodes.push({x: i*100 + 50, y: j*100 + 50});
                        }
                    }
                }
            },
            animate: function() {
                ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
                ctx.fillRect(0, 0, width, height);
                
                ctx.strokeStyle = '#0ff';
                ctx.lineWidth = 2;
                
                // Draw grid connections
                this.nodes.forEach(node => {
                    if(Math.random() < 0.01) {
                        ctx.beginPath();
                        ctx.arc(node.x, node.y, 2, 0, Math.PI*2);
                        ctx.fillStyle = '#0ff';
                        ctx.fill();
                    }
                });

                // Random pulses
                if(Math.random() < 0.1) {
                    this.pulses.push({
                        x: Math.random() * width, 
                        y: Math.random() * height, 
                        life: 100,
                        dir: Math.floor(Math.random()*4)
                    });
                }
                
                this.pulses.forEach((p, i) => {
                    ctx.strokeStyle = `rgba(0, 255, 255, ${p.life/100})`;
                    ctx.beginPath();
                    ctx.moveTo(p.x, p.y);
                    
                    const speed = 5;
                    if(p.dir === 0) p.x += speed;
                    else if(p.dir === 1) p.x -= speed;
                    else if(p.dir === 2) p.y += speed;
                    else p.y -= speed;
                    
                    ctx.lineTo(p.x, p.y);
                    ctx.stroke();
                    p.life--;
                    
                    if(Math.random() < 0.05) p.dir = Math.floor(Math.random()*4);
                    if(p.life <= 0 || p.x < 0 || p.x > width || p.y < 0 || p.y > height) {
                        this.pulses.splice(i, 1);
                    }
                });
            }
        },

        // 5. Hexgrid
        hexgrid: {
            hexes: [],
            init: function() {
                this.hexes = [];
                const r = 30;
                const h = r * Math.sqrt(3);
                const cols = Math.ceil(width / (r * 3));
                const rows = Math.ceil(height / (h / 2));
                
                for(let col=0; col<cols; col++) {
                    for(let row=0; row<rows; row++) {
                         const x = col * r * 3 + (row % 2) * r * 1.5;
                         const y = row * (h / 2);
                         this.hexes.push({
                             x, y, r, 
                             active: 0
                         });
                    }
                }
            },
            animate: function() {
                ctx.clearRect(0, 0, width, height);
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
                ctx.lineWidth = 1;
                
                this.hexes.forEach(hex => {
                    if(Math.random() < 0.005) hex.active = 1;
                    if(hex.active > 0) hex.active -= 0.02;
                    
                    ctx.beginPath();
                    for (let i = 0; i < 6; i++) {
                        const angle = 2 * Math.PI / 6 * i;
                        const x_i = hex.x + hex.r * Math.cos(angle);
                        const y_i = hex.y + hex.r * Math.sin(angle);
                        if (i === 0) ctx.moveTo(x_i, y_i);
                        else ctx.lineTo(x_i, y_i);
                    }
                    ctx.closePath();
                    ctx.stroke();
                    
                    if(hex.active > 0) {
                        ctx.fillStyle = `rgba(255, 255, 255, ${hex.active * 0.3})`;
                        ctx.fill();
                    }
                });
            }
        },

        // 6. DNA
        dna: {
            t: 0,
            init: function() {},
            animate: function() {
                ctx.clearRect(0, 0, width, height);
                this.t += 0.02;
                const strands = 2;
                const points = 50;
                
                for(let i=0; i<points; i++) {
                    const x = (width / points) * i;
                    const yBase = height / 2;
                    const yOffset1 = Math.sin(i * 0.2 + this.t) * 100;
                    const yOffset2 = Math.sin(i * 0.2 + this.t + Math.PI) * 100;
                    
                    ctx.fillStyle = 'rgba(100, 200, 255, 0.8)';
                    ctx.beginPath();
                    ctx.arc(x, yBase + yOffset1, 3, 0, Math.PI*2);
                    ctx.fill();
                    
                    ctx.fillStyle = 'rgba(255, 100, 100, 0.8)';
                    ctx.beginPath();
                    ctx.arc(x, yBase + yOffset2, 3, 0, Math.PI*2);
                    ctx.fill();
                    
                    if(i % 3 === 0) {
                        ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
                        ctx.beginPath();
                        ctx.moveTo(x, yBase + yOffset1);
                        ctx.lineTo(x, yBase + yOffset2);
                        ctx.stroke();
                    }
                }
            }
        },

        // 7. Tunnel
        tunnel: {
            rings: [],
            init: function() {
                this.rings = [];
                for(let i=0; i<20; i++) {
                    this.rings.push({z: i * 50});
                }
            },
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.1)';
                ctx.fillRect(0,0,width,height);
                ctx.strokeStyle = '#0f0';
                ctx.lineWidth = 2;
                
                const cx = width/2;
                const cy = height/2;
                
                this.rings.forEach(r => {
                    r.z -= 2;
                    if(r.z <= 0) r.z = 1000;
                    
                    const scale = 500 / r.z;
                    const size = 100 * scale;
                    
                    ctx.strokeStyle = `rgba(0, 255, 100, ${Math.min(1, scale)})`;
                    ctx.beginPath();
                    ctx.rect(cx - size/2, cy - size/2, size, size);
                    ctx.stroke();
                });
            }
        },

        // 8. Solar
        solar: {
            planets: [],
            init: function() {
                this.planets = [];
                for(let i=1; i<=8; i++) {
                    this.planets.push({
                        r: i * 40 + 30,
                        angle: Math.random() * Math.PI * 2,
                        speed: 0.02 / Math.sqrt(i),
                        size: Math.random() * 5 + 2,
                        color: `hsl(${Math.random()*360}, 70%, 50%)`
                    });
                }
            },
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.1)';
                ctx.fillRect(0,0,width,height);
                
                const cx = width/2;
                const cy = height/2;
                
                // Sun
                ctx.shadowBlur = 20;
                ctx.shadowColor = 'yellow';
                ctx.fillStyle = 'yellow';
                ctx.beginPath();
                ctx.arc(cx, cy, 20, 0, Math.PI*2);
                ctx.fill();
                ctx.shadowBlur = 0;
                
                this.planets.forEach(p => {
                    p.angle += p.speed;
                    const x = cx + Math.cos(p.angle) * p.r;
                    const y = cy + Math.sin(p.angle) * p.r;
                    
                    ctx.strokeStyle = 'rgba(255,255,255,0.1)';
                    ctx.beginPath();
                    ctx.arc(cx, cy, p.r, 0, Math.PI*2);
                    ctx.stroke();
                    
                    ctx.fillStyle = p.color;
                    ctx.beginPath();
                    ctx.arc(x, y, p.size, 0, Math.PI*2);
                    ctx.fill();
                });
            }
        },

        // 9. Clouds
        clouds: {
            clouds: [],
            init: function() {
                this.clouds = [];
                for(let i=0; i<15; i++) {
                    this.clouds.push({
                        x: Math.random() * width,
                        y: Math.random() * height,
                        r: Math.random() * 100 + 50,
                        vx: (Math.random() - 0.5) * 0.5,
                        vy: (Math.random() - 0.5) * 0.5
                    });
                }
            },
            animate: function() {
                ctx.clearRect(0,0,width,height);
                
                this.clouds.forEach(c => {
                    c.x += c.vx;
                    c.y += c.vy;
                    if(c.x < -c.r) c.x = width + c.r;
                    if(c.x > width + c.r) c.x = -c.r;
                    if(c.y < -c.r) c.y = height + c.r;
                    if(c.y > height + c.r) c.y = -c.r;
                    
                    const g = ctx.createRadialGradient(c.x, c.y, 0, c.x, c.y, c.r);
                    g.addColorStop(0, 'rgba(255,255,255,0.1)');
                    g.addColorStop(1, 'rgba(255,255,255,0)');
                    ctx.fillStyle = g;
                    ctx.beginPath();
                    ctx.arc(c.x, c.y, c.r, 0, Math.PI*2);
                    ctx.fill();
                });
            }
        },

        // 10. Gradient (Flow)
        gradient: {
            t: 0,
            init: function() {},
            animate: function() {
                this.t += 0.01;
                const g = ctx.createLinearGradient(0, 0, width, height);
                g.addColorStop(0, `hsl(${this.t * 50}, 50%, 20%)`);
                g.addColorStop(1, `hsl(${this.t * 50 + 180}, 50%, 20%)`);
                ctx.fillStyle = g;
                ctx.fillRect(0,0,width,height);
            }
        },

        // 11. Stars (Warp)
        starswarp: {
            stars: [],
            init: function() {
                this.stars = [];
                for(let i=0; i<200; i++) {
                    this.stars.push({
                        x: Math.random() * width - width/2,
                        y: Math.random() * height - height/2,
                        z: Math.random() * width
                    });
                }
            },
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.4)';
                ctx.fillRect(0,0,width,height);
                ctx.fillStyle = '#fff';
                
                const cx = width/2;
                const cy = height/2;
                
                this.stars.forEach(s => {
                    s.z -= 10;
                    if(s.z <= 0) s.z = width;
                    
                    const x = cx + (s.x / s.z) * 100;
                    const y = cy + (s.y / s.z) * 100;
                    const size = (1 - s.z/width) * 3;
                    
                    if(x > 0 && x < width && y > 0 && y < height) {
                        ctx.beginPath();
                        ctx.arc(x, y, size, 0, Math.PI*2);
                        ctx.fill();
                    }
                });
            }
        },

        // 12. Glitch
        glitch: {
            init: function() {},
            animate: function() {
                if(Math.random() > 0.1) {
                    ctx.clearRect(0,0,width,height);
                }
                
                for(let i=0; i<10; i++) {
                    const x = Math.random() * width;
                    const y = Math.random() * height;
                    const w = Math.random() * 100;
                    const h = Math.random() * 50;
                    ctx.fillStyle = `rgba(${Math.random()*255}, ${Math.random()*255}, ${Math.random()*255}, 0.5)`;
                    ctx.fillRect(x, y, w, h);
                }
            }
        },

        // 13. Spiral (Galaxy)
        spiral: {
            stars: [],
            init: function() {
                this.stars = [];
                for(let i=0; i<300; i++) {
                    this.stars.push({
                        angle: Math.random() * Math.PI * 2,
                        radius: Math.random() * Math.min(width, height)/2,
                        speed: (Math.random() + 0.1) * 0.01,
                        size: Math.random() * 2
                    });
                }
            },
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.1)';
                ctx.fillRect(0,0,width,height);
                ctx.fillStyle = '#fff';
                const cx = width/2;
                const cy = height/2;
                
                this.stars.forEach(s => {
                    s.angle += s.speed;
                    const x = cx + Math.cos(s.angle) * s.radius;
                    const y = cy + Math.sin(s.angle) * s.radius;
                    ctx.beginPath();
                    ctx.arc(x, y, s.size, 0, Math.PI*2);
                    ctx.fill();
                });
            }
        },

        // 14. Neurons
        neurons: {
            nodes: [],
            pulses: [],
            init: function() {
                this.nodes = [];
                for(let i=0; i<50; i++) {
                    this.nodes.push({
                        x: Math.random() * width,
                        y: Math.random() * height,
                        connections: []
                    });
                }
                // Connect
                this.nodes.forEach((n, i) => {
                    this.nodes.forEach((n2, j) => {
                        if(i !== j && Math.random() < 0.1) {
                            n.connections.push(j);
                        }
                    });
                });
            },
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.1)';
                ctx.fillRect(0,0,width,height);
                
                this.nodes.forEach(n => {
                    ctx.beginPath();
                    ctx.arc(n.x, n.y, 3, 0, Math.PI*2);
                    ctx.fillStyle = '#4488ff';
                    ctx.fill();
                    
                    n.connections.forEach(targetIdx => {
                        const target = this.nodes[targetIdx];
                        ctx.beginPath();
                        ctx.moveTo(n.x, n.y);
                        ctx.lineTo(target.x, target.y);
                        ctx.strokeStyle = 'rgba(68, 136, 255, 0.2)';
                        ctx.stroke();
                        
                        // Fire pulse
                        if(Math.random() < 0.01) {
                            this.pulses.push({
                                sx: n.x, sy: n.y,
                                tx: target.x, ty: target.y,
                                progress: 0
                            });
                        }
                    });
                });
                
                this.pulses.forEach((p, i) => {
                    p.progress += 0.05;
                    const x = p.sx + (p.tx - p.sx) * p.progress;
                    const y = p.sy + (p.ty - p.sy) * p.progress;
                    
                    ctx.beginPath();
                    ctx.arc(x, y, 2, 0, Math.PI*2);
                    ctx.fillStyle = '#fff';
                    ctx.fill();
                    
                    if(p.progress >= 1) this.pulses.splice(i, 1);
                });
            }
        },

        // 15. Ripples
        ripples: {
            list: [],
            init: function() {},
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.1)';
                ctx.fillRect(0,0,width,height);
                
                if(Math.random() < 0.05) {
                    this.list.push({
                        x: Math.random() * width,
                        y: Math.random() * height,
                        r: 0,
                        alpha: 1
                    });
                }
                
                this.list.forEach((ripple, i) => {
                    ripple.r += 2;
                    ripple.alpha -= 0.01;
                    
                    ctx.beginPath();
                    ctx.arc(ripple.x, ripple.y, ripple.r, 0, Math.PI*2);
                    ctx.strokeStyle = `rgba(255, 255, 255, ${ripple.alpha})`;
                    ctx.stroke();
                    
                    if(ripple.alpha <= 0) this.list.splice(i, 1);
                });
            }
        },

        // 16. Globe (3D Sphere)
        globe: {
            angle: 0,
            init: function() {},
            animate: function() {
                ctx.clearRect(0,0,width,height);
                this.angle += 0.01;
                const cx = width/2;
                const cy = height/2;
                const r = 200;
                
                for(let i=0; i<200; i++) {
                    const lat = Math.acos(1 - 2 * (i + 0.5) / 200);
                    const lon = Math.PI * (1 + Math.sqrt(5)) * (i + 0.5);
                    
                    const x = r * Math.sin(lat) * Math.cos(lon + this.angle);
                    const y = r * Math.sin(lat) * Math.sin(lon + this.angle);
                    const z = r * Math.cos(lat);
                    
                    const scale = (z + r * 2) / (r * 3);
                    const alpha = (z + r) / (2 * r);
                    
                    ctx.beginPath();
                    ctx.arc(cx + x, cy + y, 2 * scale, 0, Math.PI*2);
                    ctx.fillStyle = `rgba(34, 197, 94, ${alpha})`;
                    ctx.fill();
                }
            }
        },

        // 17. Audio (Bars)
        audio: {
            bars: [],
            init: function() {
                this.bars = Array(50).fill(0);
            },
            animate: function() {
                ctx.clearRect(0,0,width,height);
                const barWidth = width / 50;
                
                this.bars.forEach((h, i) => {
                    // Update height randomly
                    this.bars[i] = Math.max(0, this.bars[i] - 5 + (Math.random() * 20 - 5));
                    if(this.bars[i] > height) this.bars[i] = height;
                    
                    const x = i * barWidth;
                    const y = height - this.bars[i];
                    
                    ctx.fillStyle = `hsl(${i * 5}, 50%, 50%)`;
                    ctx.fillRect(x, y, barWidth - 2, this.bars[i]);
                });
            }
        },

        // 18. Rain (Matrix Style)
        matrixrain: {
            drops: [],
            init: function() {
                 this.drops = Array(Math.floor(width/10)).fill(0);
            },
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.1)';
                ctx.fillRect(0,0,width,height);
                
                ctx.fillStyle = '#0f0';
                this.drops.forEach((y, i) => {
                    const text = String.fromCharCode(0x30A0 + Math.random()*96);
                    ctx.fillText(text, i*10, y);
                    
                    if(y > height && Math.random() > 0.975) {
                        this.drops[i] = 0;
                    } else {
                        this.drops[i] += 10;
                    }
                });
            }
        },

        // 19. Fire
        fire: {
            particles: [],
            init: function() { this.particles = []; },
            animate: function() {
                ctx.globalCompositeOperation = 'lighter';
                ctx.clearRect(0,0,width,height); // Can't clear with composite lighter easily, so reset
                ctx.globalCompositeOperation = 'source-over';
                ctx.fillStyle = 'rgba(0,0,0,0.2)';
                ctx.fillRect(0,0,width,height);
                ctx.globalCompositeOperation = 'lighter';
                
                for(let i=0; i<5; i++) {
                    this.particles.push({
                        x: width/2 + (Math.random() - 0.5) * 50,
                        y: height,
                        vx: (Math.random() - 0.5) * 2,
                        vy: Math.random() * -5 - 2,
                        life: 1,
                        size: Math.random() * 20 + 10
                    });
                }
                
                this.particles.forEach((p, i) => {
                    p.x += p.vx;
                    p.y += p.vy;
                    p.life -= 0.02;
                    p.size *= 0.95;
                    
                    if(p.life <= 0) {
                        this.particles.splice(i, 1);
                        return;
                    }
                    
                    const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size);
                    g.addColorStop(0, `rgba(255, 255, 0, ${p.life})`);
                    g.addColorStop(0.5, `rgba(255, 100, 0, ${p.life})`);
                    g.addColorStop(1, 'rgba(255, 0, 0, 0)');
                    
                    ctx.fillStyle = g;
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, p.size, 0, Math.PI*2);
                    ctx.fill();
                });
                ctx.globalCompositeOperation = 'source-over';
            }
        },

        // 20. Lightning
        lightning: {
            flashes: [],
            nextFlash: 0,
            init: function() { this.flashes = []; },
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.1)';
                ctx.fillRect(0,0,width,height);
                
                if(Date.now() > this.nextFlash) {
                    this.flashes.push({
                        x: Math.random() * width,
                        life: 10,
                        points: []
                    });
                    this.nextFlash = Date.now() + Math.random() * 2000 + 500;
                }
                
                this.flashes.forEach((f, i) => {
                    if(f.points.length === 0) {
                        let cx = f.x;
                        let cy = 0;
                        f.points.push({x: cx, y: cy});
                        while(cy < height) {
                            cx += (Math.random() - 0.5) * 50;
                            cy += Math.random() * 50 + 10;
                            f.points.push({x: cx, y: cy});
                        }
                    }
                    
                    ctx.strokeStyle = `rgba(255, 255, 255, ${f.life / 10})`;
                    ctx.lineWidth = 2;
                    ctx.beginPath();
                    ctx.moveTo(f.points[0].x, f.points[0].y);
                    for(let j=1; j<f.points.length; j++) {
                        ctx.lineTo(f.points[j].x, f.points[j].y);
                    }
                    ctx.stroke();
                    
                    // Flash screen
                    if(f.life > 8) {
                        ctx.fillStyle = `rgba(255,255,255,${(f.life-8)/20})`;
                        ctx.fillRect(0,0,width,height);
                    }
                    
                    f.life--;
                    if(f.life <= 0) this.flashes.splice(i, 1);
                });
            }
        },

        // 21. Fog
        fog: {
            particles: [],
            init: function() {
                this.particles = [];
                for(let i=0; i<50; i++) {
                    this.particles.push({
                        x: Math.random() * width,
                        y: Math.random() * height,
                        r: Math.random() * 100 + 50,
                        dx: (Math.random() - 0.5) * 0.2,
                        dy: (Math.random() - 0.5) * 0.2
                    });
                }
            },
            animate: function() {
                ctx.fillStyle = '#000';
                ctx.fillRect(0,0,width,height);
                
                this.particles.forEach(p => {
                    p.x += p.dx;
                    p.y += p.dy;
                    if(p.x < -p.r) p.x = width + p.r;
                    if(p.x > width + p.r) p.x = -p.r;
                    if(p.y < -p.r) p.y = height + p.r;
                    if(p.y > height + p.r) p.y = -p.r;
                    
                    const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r);
                    g.addColorStop(0, 'rgba(200,200,200,0.1)');
                    g.addColorStop(1, 'rgba(200,200,200,0)');
                    ctx.fillStyle = g;
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, p.r, 0, Math.PI*2);
                    ctx.fill();
                });
            }
        },

        // 22. Aurora
        aurora: {
            t: 0,
            init: function() {},
            animate: function() {
                ctx.fillStyle = 'rgba(0,10,20,0.2)';
                ctx.fillRect(0,0,width,height);
                this.t += 0.01;
                
                for(let i=0; i<3; i++) {
                    ctx.beginPath();
                    for(let x=0; x<=width; x+=10) {
                        const y = height/2 + Math.sin(x*0.01 + this.t + i) * 100 + Math.sin(x*0.02 + this.t*2) * 50;
                        if(x===0) ctx.moveTo(x,y);
                        else ctx.lineTo(x,y);
                    }
                    ctx.lineTo(width, height);
                    ctx.lineTo(0, height);
                    ctx.fillStyle = `hsla(${120 + i*40}, 70%, 50%, 0.1)`;
                    ctx.fill();
                }
            }
        },

        // 23. Sakura (Blossom)
        sakura: {
            petals: [],
            init: function() {
                this.petals = [];
                for(let i=0; i<50; i++) {
                    this.petals.push({
                        x: Math.random() * width,
                        y: Math.random() * height,
                        s: Math.random() * 5 + 2,
                        dx: Math.random() + 0.5,
                        dy: Math.random() + 0.5,
                        rot: Math.random() * Math.PI,
                        dRot: (Math.random() - 0.5) * 0.1
                    });
                }
            },
            animate: function() {
                ctx.clearRect(0,0,width,height);
                
                this.petals.forEach(p => {
                    p.x += p.dx;
                    p.y += p.dy;
                    p.rot += p.dRot;
                    
                    if(p.x > width) p.x = -10;
                    if(p.y > height) p.y = -10;
                    
                    ctx.save();
                    ctx.translate(p.x, p.y);
                    ctx.rotate(p.rot);
                    ctx.fillStyle = '#ffb7c5';
                    ctx.beginPath();
                    ctx.ellipse(0, 0, p.s, p.s/2, 0, 0, Math.PI*2);
                    ctx.fill();
                    ctx.restore();
                });
            }
        },

        // 24. Blackhole
        blackhole: {
            particles: [],
            init: function() {
                this.particles = [];
                for(let i=0; i<200; i++) {
                    this.particles.push({
                        angle: Math.random() * Math.PI * 2,
                        r: Math.random() * 200 + 50,
                        speed: Math.random() * 0.05 + 0.01
                    });
                }
            },
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.1)';
                ctx.fillRect(0,0,width,height);
                const cx = width/2;
                const cy = height/2;
                
                // Event Horizon
                ctx.beginPath();
                ctx.arc(cx, cy, 30, 0, Math.PI*2);
                ctx.fillStyle = '#000';
                ctx.fill();
                ctx.strokeStyle = 'rgba(100,100,255,0.5)';
                ctx.stroke();
                
                this.particles.forEach(p => {
                    p.angle += p.speed;
                    p.r -= 0.5;
                    if(p.r < 30) p.r = 250;
                    
                    const x = cx + Math.cos(p.angle) * p.r;
                    const y = cy + Math.sin(p.angle) * p.r * 0.4; // Disk perspective
                    
                    ctx.fillStyle = `hsl(${200 + p.r/2}, 70%, 60%)`;
                    ctx.beginPath();
                    ctx.arc(x, y, 2, 0, Math.PI*2);
                    ctx.fill();
                });
            }
        },

        // 25. Meteor
        meteor: {
            meteors: [],
            init: function() { this.meteors = []; },
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.2)';
                ctx.fillRect(0,0,width,height);
                
                if(Math.random() < 0.1) {
                    this.meteors.push({
                        x: Math.random() * width,
                        y: 0,
                        l: Math.random() * 50 + 20,
                        v: Math.random() * 10 + 10
                    });
                }
                
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 2;
                this.meteors.forEach((m, i) => {
                    m.x -= m.v;
                    m.y += m.v;
                    
                    ctx.beginPath();
                    ctx.moveTo(m.x, m.y);
                    ctx.lineTo(m.x + m.l, m.y - m.l);
                    ctx.stroke();
                    
                    if(m.y > height) this.meteors.splice(i, 1);
                });
            }
        },

        // 26. Nebula
        nebula: {
            clouds: [],
            init: function() {
                this.clouds = [];
                for(let i=0; i<20; i++) {
                    this.clouds.push({
                        x: Math.random() * width,
                        y: Math.random() * height,
                        r: Math.random() * 100 + 50,
                        c: Math.random() * 60 + 240 // Purple/Pink
                    });
                }
            },
            animate: function() {
                ctx.clearRect(0,0,width,height);
                ctx.globalCompositeOperation = 'screen';
                this.clouds.forEach(c => {
                    c.x += (Math.random() - 0.5);
                    c.y += (Math.random() - 0.5);
                    
                    const g = ctx.createRadialGradient(c.x, c.y, 0, c.x, c.y, c.r);
                    g.addColorStop(0, `hsla(${c.c}, 70%, 50%, 0.1)`);
                    g.addColorStop(1, 'transparent');
                    
                    ctx.fillStyle = g;
                    ctx.beginPath();
                    ctx.arc(c.x, c.y, c.r, 0, Math.PI*2);
                    ctx.fill();
                });
                ctx.globalCompositeOperation = 'source-over';
            }
        },

        // 27. Cube (Rotating 3D)
        cube: {
            angle: 0,
            init: function() {},
            animate: function() {
                ctx.clearRect(0,0,width,height);
                this.angle += 0.01;
                const cx = width/2;
                const cy = height/2;
                const size = 100;
                
                const vertices = [
                    [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
                    [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]
                ];
                
                const edges = [
                    [0,1], [1,2], [2,3], [3,0],
                    [4,5], [5,6], [6,7], [7,4],
                    [0,4], [1,5], [2,6], [3,7]
                ];
                
                const projected = [];
                
                vertices.forEach(v => {
                    // Rotate Y
                    let x = v[0] * Math.cos(this.angle) - v[2] * Math.sin(this.angle);
                    let z = v[0] * Math.sin(this.angle) + v[2] * Math.cos(this.angle);
                    let y = v[1];
                    
                    // Rotate X
                    let y2 = y * Math.cos(this.angle*0.5) - z * Math.sin(this.angle*0.5);
                    let z2 = y * Math.sin(this.angle*0.5) + z * Math.cos(this.angle*0.5);
                    
                    const scale = 400 / (400 - z2 * 100);
                    projected.push({
                        x: cx + x * size * scale,
                        y: cy + y2 * size * scale
                    });
                });
                
                ctx.strokeStyle = '#0ff';
                ctx.lineWidth = 2;
                ctx.beginPath();
                edges.forEach(e => {
                    ctx.moveTo(projected[e[0]].x, projected[e[0]].y);
                    ctx.lineTo(projected[e[1]].x, projected[e[1]].y);
                });
                ctx.stroke();
                
                // Dots
                ctx.fillStyle = '#fff';
                projected.forEach(p => {
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, 4, 0, Math.PI*2);
                    ctx.fill();
                });
            }
        },

        // 28. Pyramid
        pyramid: {
            angle: 0,
            init: function() {},
            animate: function() {
                ctx.clearRect(0,0,width,height);
                this.angle += 0.02;
                const cx = width/2;
                const cy = height/2;
                const size = 150;
                
                const vertices = [
                    [0, -1, 0],   // Top
                    [-1, 1, -1],  // Base FL
                    [1, 1, -1],   // Base FR
                    [1, 1, 1],    // Base BR
                    [-1, 1, 1]    // Base BL
                ];
                
                const edges = [
                    [0,1], [0,2], [0,3], [0,4],
                    [1,2], [2,3], [3,4], [4,1]
                ];
                
                const projected = [];
                vertices.forEach(v => {
                    // Rotate Y
                    let x = v[0] * Math.cos(this.angle) - v[2] * Math.sin(this.angle);
                    let z = v[0] * Math.sin(this.angle) + v[2] * Math.cos(this.angle);
                    let y = v[1];
                    
                    const scale = 500 / (500 + z * 100);
                    projected.push({
                        x: cx + x * size * scale,
                        y: cy + y * size * scale
                    });
                });
                
                ctx.strokeStyle = '#ff00ff';
                ctx.lineWidth = 2;
                ctx.beginPath();
                edges.forEach(e => {
                    ctx.moveTo(projected[e[0]].x, projected[e[0]].y);
                    ctx.lineTo(projected[e[1]].x, projected[e[1]].y);
                });
                ctx.stroke();
            }
        },

        // 29. Grid3D
        grid3d: {
            offset: 0,
            init: function() {},
            animate: function() {
                ctx.fillStyle = '#000';
                ctx.fillRect(0,0,width,height);
                this.offset += 2;
                if(this.offset > 100) this.offset = 0;
                
                ctx.strokeStyle = '#0f0';
                ctx.lineWidth = 1;
                
                const horizon = height/3;
                const cx = width/2;
                
                // Vertical lines (perspective)
                for(let i=-20; i<=20; i++) {
                    const x = cx + i * 100;
                    ctx.beginPath();
                    ctx.moveTo(cx, horizon);
                    ctx.lineTo(cx + (i * 500), height);
                    ctx.stroke();
                }
                
                // Horizontal lines (moving)
                for(let i=0; i<20; i++) {
                    const y = height - (i * 50 + this.offset) * (i/5 + 0.5);
                    if(y > horizon) {
                        ctx.beginPath();
                        ctx.moveTo(0, y);
                        ctx.lineTo(width, y);
                        ctx.stroke();
                    }
                }
            }
        },

        // 30. Mandala
        mandala: {
            t: 0,
            init: function() {},
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.1)';
                ctx.fillRect(0,0,width,height);
                this.t += 0.01;
                const cx = width/2;
                const cy = height/2;
                
                for(let i=0; i<12; i++) {
                    const angle = (Math.PI*2 / 12) * i + this.t;
                    const r = 100 + Math.sin(this.t * 5) * 20;
                    
                    const x = cx + Math.cos(angle) * r;
                    const y = cy + Math.sin(angle) * r;
                    
                    ctx.strokeStyle = `hsl(${i * 30 + this.t * 100}, 50%, 50%)`;
                    ctx.beginPath();
                    ctx.arc(x, y, 30, 0, Math.PI*2);
                    ctx.stroke();
                    
                    ctx.beginPath();
                    ctx.moveTo(cx, cy);
                    ctx.lineTo(x, y);
                    ctx.stroke();
                }
            }
        },

        // 31. Lissajous
        lissajous: {
            t: 0,
            init: function() {},
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.05)';
                ctx.fillRect(0,0,width,height);
                this.t += 0.05;
                const cx = width/2;
                const cy = height/2;
                
                const x = cx + Math.sin(this.t * 3) * 300;
                const y = cy + Math.cos(this.t * 4) * 200;
                
                ctx.fillStyle = '#fff';
                ctx.beginPath();
                ctx.arc(x, y, 5, 0, Math.PI*2);
                ctx.fill();
            }
        },

        // 32. Spirograph
        spirograph: {
            t: 0,
            init: function() {},
            animate: function() {
                // ctx.clearRect(0,0,width,height); // Keep trails
                if(this.t === 0) ctx.clearRect(0,0,width,height);
                
                this.t += 0.1;
                const cx = width/2;
                const cy = height/2;
                
                const R = 150;
                const r = 52;
                const d = 50;
                
                const x = cx + (R-r)*Math.cos(this.t) + d*Math.cos((R-r)/r*this.t);
                const y = cy + (R-r)*Math.sin(this.t) - d*Math.sin((R-r)/r*this.t);
                
                ctx.fillStyle = `hsl(${this.t}, 70%, 50%)`;
                ctx.beginPath();
                ctx.arc(x, y, 2, 0, Math.PI*2);
                ctx.fill();
                
                if(this.t > 1000) {
                     this.t = 0;
                     ctx.clearRect(0,0,width,height);
                }
            }
        },

        // 33. Kaleidoscope
        kaleidoscope: {
            t: 0,
            init: function() {},
            animate: function() {
                ctx.clearRect(0,0,width,height);
                this.t += 0.01;
                const cx = width/2;
                const cy = height/2;
                
                for(let i=0; i<8; i++) {
                    ctx.save();
                    ctx.translate(cx, cy);
                    ctx.rotate((Math.PI*2/8) * i + this.t);
                    
                    ctx.fillStyle = `hsla(${this.t * 50}, 70%, 50%, 0.5)`;
                    ctx.beginPath();
                    ctx.moveTo(0,0);
                    ctx.lineTo(100, 50);
                    ctx.lineTo(100, -50);
                    ctx.fill();
                    
                    ctx.fillStyle = `hsla(${this.t * 50 + 180}, 70%, 50%, 0.5)`;
                    ctx.beginPath();
                    ctx.arc(150, 0, 30, 0, Math.PI*2);
                    ctx.fill();
                    
                    ctx.restore();
                }
            }
        },

        // 34. Binary
        binary: {
            drops: [],
            init: function() {
                this.drops = Array(Math.floor(width/15)).fill(0);
            },
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.1)';
                ctx.fillRect(0,0,width,height);
                ctx.fillStyle = '#0f0';
                ctx.font = '12px monospace';
                
                this.drops.forEach((y, i) => {
                    const text = Math.random() > 0.5 ? '1' : '0';
                    ctx.fillText(text, i*15, y);
                    
                    if(y > height && Math.random() > 0.975) {
                        this.drops[i] = 0;
                    } else {
                        this.drops[i] += 15;
                    }
                });
            }
        },

        // 35. Barcode
        barcode: {
            x: 0,
            init: function() {},
            animate: function() {
                // No clear, build up
                if(this.x > width) {
                     this.x = 0;
                     ctx.clearRect(0,0,width,height);
                }
                
                ctx.fillStyle = '#000';
                ctx.fillRect(this.x, 0, 5, height); // scan line
                
                if(Math.random() > 0.5) {
                    ctx.fillStyle = '#fff';
                    ctx.fillRect(this.x, 0, Math.random()*10, height);
                }
                
                this.x += 5;
                
                // Red laser
                ctx.strokeStyle = 'red';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(0, height/2);
                ctx.lineTo(width, height/2);
                ctx.stroke();
            }
        },

        // 36. ASCII
        ascii: {
            init: function() {},
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.2)';
                ctx.fillRect(0,0,width,height);
                ctx.fillStyle = '#fff';
                ctx.font = '10px monospace';
                
                for(let i=0; i<50; i++) {
                    const x = Math.floor(Math.random() * (width/10)) * 10;
                    const y = Math.floor(Math.random() * (height/10)) * 10;
                    const char = String.fromCharCode(33 + Math.random()*90);
                    ctx.fillText(char, x, y);
                }
            }
        },

        // 37. Radar
        radar: {
            angle: 0,
            blips: [],
            init: function() {
                this.blips = [];
                for(let i=0; i<5; i++) {
                    this.blips.push({
                        angle: Math.random() * Math.PI * 2,
                        r: Math.random() * 200 + 50,
                        life: 0
                    });
                }
            },
            animate: function() {
                ctx.fillStyle = 'rgba(0,20,0,0.1)';
                ctx.fillRect(0,0,width,height);
                this.angle += 0.05;
                const cx = width/2;
                const cy = height/2;
                
                // Rings
                ctx.strokeStyle = '#0f0';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.arc(cx, cy, 100, 0, Math.PI*2);
                ctx.arc(cx, cy, 200, 0, Math.PI*2);
                ctx.arc(cx, cy, 300, 0, Math.PI*2);
                ctx.stroke();
                
                // Sweep
                ctx.beginPath();
                ctx.moveTo(cx, cy);
                ctx.arc(cx, cy, 350, this.angle, this.angle + 0.5);
                ctx.lineTo(cx, cy);
                ctx.fillStyle = 'rgba(0, 255, 0, 0.2)';
                ctx.fill();
                
                // Blips
                this.blips.forEach(b => {
                    // Check if sweep passed
                    const diff = (this.angle % (Math.PI*2)) - b.angle;
                    if(Math.abs(diff) < 0.1) b.life = 1;
                    
                    if(b.life > 0) {
                        const x = cx + Math.cos(b.angle) * b.r;
                        const y = cy + Math.sin(b.angle) * b.r;
                        ctx.fillStyle = `rgba(0, 255, 0, ${b.life})`;
                        ctx.beginPath();
                        ctx.arc(x, y, 5, 0, Math.PI*2);
                        ctx.fill();
                        b.life -= 0.02;
                    }
                });
            }
        },

        // 38. Gravity (Bouncing Balls)
        gravity: {
            balls: [],
            init: function() {
                this.balls = [];
                for(let i=0; i<20; i++) {
                    this.balls.push({
                        x: Math.random() * width,
                        y: Math.random() * height/2,
                        vx: (Math.random() - 0.5) * 5,
                        vy: 0,
                        r: Math.random() * 20 + 10,
                        color: `hsl(${Math.random()*360}, 70%, 50%)`
                    });
                }
            },
            animate: function() {
                ctx.clearRect(0,0,width,height);
                
                this.balls.forEach(b => {
                    b.vy += 0.5; // Gravity
                    b.x += b.vx;
                    b.y += b.vy;
                    
                    if(b.y + b.r > height) {
                        b.y = height - b.r;
                        b.vy *= -0.8; // Bounce
                    }
                    if(b.x + b.r > width || b.x - b.r < 0) {
                        b.vx *= -0.8;
                    }
                    
                    ctx.fillStyle = b.color;
                    ctx.beginPath();
                    ctx.arc(b.x, b.y, b.r, 0, Math.PI*2);
                    ctx.fill();
                });
            }
        },

        // 39. Fountain
        fountain: {
            particles: [],
            init: function() { this.particles = []; },
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.2)';
                ctx.fillRect(0,0,width,height);
                
                for(let i=0; i<5; i++) {
                    this.particles.push({
                        x: width/2,
                        y: height,
                        vx: (Math.random() - 0.5) * 10,
                        vy: Math.random() * -15 - 10,
                        life: 1
                    });
                }
                
                this.particles.forEach((p, i) => {
                    p.vy += 0.5;
                    p.x += p.vx;
                    p.y += p.vy;
                    p.life -= 0.01;
                    
                    ctx.fillStyle = `rgba(100, 200, 255, ${p.life})`;
                    ctx.fillRect(p.x, p.y, 4, 4);
                    
                    if(p.y > height || p.life <= 0) this.particles.splice(i, 1);
                });
            }
        },

        // 40. Hypnosis
        hypnosis: {
            t: 0,
            init: function() {},
            animate: function() {
                ctx.clearRect(0,0,width,height);
                this.t += 0.05;
                const cx = width/2;
                const cy = height/2;
                
                for(let i=0; i<20; i++) {
                    const r = (i * 20 + this.t * 10) % 400;
                    ctx.beginPath();
                    ctx.arc(cx, cy, r, 0, Math.PI*2);
                    ctx.strokeStyle = i % 2 === 0 ? '#fff' : '#000';
                    ctx.lineWidth = 10;
                    ctx.stroke();
                }
            }
        },

        // 41. Swirl
        swirl: {
            t: 0,
            init: function() {},
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.05)';
                ctx.fillRect(0,0,width,height);
                this.t += 0.1;
                const cx = width/2;
                const cy = height/2;
                
                for(let i=0; i<50; i++) {
                    const angle = this.t + i * 0.2;
                    const r = i * 5 + Math.sin(this.t) * 50;
                    const x = cx + Math.cos(angle) * r;
                    const y = cy + Math.sin(angle) * r;
                    
                    ctx.fillStyle = `hsl(${i * 10}, 70%, 50%)`;
                    ctx.beginPath();
                    ctx.arc(x, y, 5, 0, Math.PI*2);
                    ctx.fill();
                }
            }
        },

        
        // 52. Line Waves (Multiple Sine Waves)
        linewaves: {
            offset: 0,
            init: function() {},
            animate: function() {
                ctx.fillStyle = '#000';
                ctx.fillRect(0,0,width,height);
                this.offset += 0.02;
                
                for(let i=0; i<5; i++) {
                    ctx.beginPath();
                    ctx.lineWidth = 3; // Thicker
                    ctx.strokeStyle = `hsla(${i * 60 + this.offset * 10}, 70%, 50%, 0.8)`; // Brighter
                    
                    for(let x=0; x<width; x+=5) {
                        const y = height/2 + Math.sin(x * 0.01 + this.offset + i) * (100 + i * 20);
                        if(x===0) ctx.moveTo(x,y);
                        else ctx.lineTo(x,y);
                    }
                    ctx.stroke();
                }
            }
        },

        // 53. Galaxy (Spiral)
        galaxy: {
            stars: [],
            init: function() {
                this.stars = [];
                for(let i=0; i<500; i++) {
                    this.stars.push({
                        angle: Math.random() * Math.PI * 2,
                        radius: Math.random() * 400,
                        speed: (Math.random() * 0.02) + 0.005,
                        size: Math.random() * 2,
                        color: `hsl(${Math.random() * 60 + 200}, 80%, 70%)`
                    });
                }
            },
            animate: function() {
                ctx.fillStyle = 'rgba(10, 10, 30, 0.2)';
                ctx.fillRect(0,0,width,height);
                const cx = width/2;
                const cy = height/2;
                
                this.stars.forEach(s => {
                    s.angle += s.speed;
                    const x = cx + Math.cos(s.angle) * s.radius;
                    const y = cy + Math.sin(s.angle) * s.radius * 0.6; // Elliptical
                    
                    ctx.fillStyle = s.color;
                    ctx.beginPath();
                    ctx.arc(x, y, s.size, 0, Math.PI*2);
                    ctx.fill();
                });
            }
        },

        // 54. Vortex
        vortex: {
            particles: [],
            init: function() {
                this.particles = [];
                for(let i=0; i<300; i++) {
                    this.particles.push({
                        angle: Math.random() * Math.PI * 2,
                        radius: Math.random() * width,
                        speed: Math.random() * 0.05 + 0.02,
                        z: Math.random() * 100
                    });
                }
            },
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.1)';
                ctx.fillRect(0,0,width,height);
                const cx = width/2;
                const cy = height/2;
                
                this.particles.forEach(p => {
                    p.radius -= 2;
                    p.angle += p.speed;
                    if(p.radius < 10) p.radius = Math.max(width, height);
                    
                    const x = cx + Math.cos(p.angle) * p.radius;
                    const y = cy + Math.sin(p.angle) * p.radius;
                    
                    const colorVal = (p.radius / width) * 360;
                    ctx.fillStyle = `hsl(${colorVal}, 70%, 50%)`;
                    ctx.beginPath();
                    ctx.arc(x, y, 2, 0, Math.PI*2);
                    ctx.fill();
                });
            }
        },

        // 42. White Waves (Aesthetic)
        whitewaves: {
            offset: 0,
            init: function() {},
            animate: function() {
                ctx.fillStyle = '#000';
                ctx.fillRect(0,0,width,height);
                this.offset += 0.05;
                ctx.lineWidth = 4; // Thicker
                
                for(let i=0; i<8; i++) {
                    ctx.beginPath();
                    ctx.strokeStyle = `rgba(255, 255, 255, ${1.0 - i * 0.08})`; // Much Brighter
                    for(let x=0; x<width; x+=5) {
                        const y = height/2 + Math.sin(x*0.005 + this.offset + i*0.5) * (100 - i*5) * Math.sin(this.offset * 0.2);
                        if(x===0) ctx.moveTo(x,y);
                        else ctx.lineTo(x,y);
                    }
                    ctx.stroke();
                }
            }
        },

        // 43. Terrain (Wireframe)
        terrain: {
            offset: 0,
            init: function() {},
            animate: function() {
                ctx.fillStyle = '#050510';
                ctx.fillRect(0,0,width,height);
                this.offset -= 2; // Move forward
                
                ctx.strokeStyle = '#00ffaa';
                ctx.lineWidth = 1;
                
                const cx = width/2;
                const horizon = height/3;
                
                // Vertical lines
                for(let i=-20; i<=20; i++) {
                    const x = cx + i * 100;
                    ctx.beginPath();
                    ctx.moveTo(cx, horizon);
                    ctx.lineTo(cx + i * 800, height);
                    ctx.stroke();
                }
                
                // Horizontal lines with noise
                for(let i=0; i<20; i++) {
                    let z = i * 50 + (this.offset % 50);
                    if(z < 0) z += 1000;
                    const y = height - z * (i/10 + 0.2);
                    
                    if(y > horizon && y < height) {
                        ctx.beginPath();
                        ctx.moveTo(0, y);
                        
                        // Simple jagged line
                        for(let x=0; x<=width; x+=50) {
                            const dy = Math.sin(x * 0.01 + i) * 20;
                            ctx.lineTo(x, y + dy);
                        }
                        ctx.stroke();
                    }
                }
            }
        },

        // 44. Supernova
        supernova: {
            particles: [],
            init: function() {
                this.particles = [];
                for(let i=0; i<100; i++) {
                    this.particles.push({
                        angle: Math.random() * Math.PI * 2,
                        r: Math.random() * 10,
                        speed: Math.random() * 5 + 2,
                        color: `hsl(${Math.random()*60 + 10}, 100%, 50%)` // Orange/Yellow
                    });
                }
            },
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.1)';
                ctx.fillRect(0,0,width,height);
                const cx = width/2;
                const cy = height/2;
                
                this.particles.forEach(p => {
                    p.r += p.speed;
                    if(p.r > Math.max(width, height)) p.r = 0;
                    
                    const x = cx + Math.cos(p.angle) * p.r;
                    const y = cy + Math.sin(p.angle) * p.r;
                    
                    ctx.fillStyle = p.color;
                    ctx.beginPath();
                    ctx.arc(x, y, 2 + p.r/100, 0, Math.PI*2);
                    ctx.fill();
                });
            }
        },

        // 45. DNA 2 (3D Helix)
        dna2: {
            t: 0,
            init: function() {},
            animate: function() {
                ctx.clearRect(0,0,width,height);
                this.t += 0.02;
                const cx = width/2;
                
                for(let i=0; i<40; i++) {
                    const y = i * 20 + (height/2 - 400);
                    const angle = i * 0.2 + this.t;
                    const x1 = cx + Math.sin(angle) * 100;
                    const x2 = cx + Math.sin(angle + Math.PI) * 100;
                    
                    // Strand 1
                    ctx.fillStyle = '#f0f';
                    ctx.beginPath();
                    ctx.arc(x1, y, 5, 0, Math.PI*2);
                    ctx.fill();
                    
                    // Strand 2
                    ctx.fillStyle = '#0ff';
                    ctx.beginPath();
                    ctx.arc(x2, y, 5, 0, Math.PI*2);
                    ctx.fill();
                    
                    // Connector
                    if(i % 2 === 0) {
                        ctx.strokeStyle = 'rgba(255,255,255,0.3)';
                        ctx.beginPath();
                        ctx.moveTo(x1, y);
                        ctx.lineTo(x2, y);
                        ctx.stroke();
                    }
                }
            }
        },

        // 46. Fireworks
        fireworks: {
            rockets: [],
            sparks: [],
            init: function() { this.rockets = []; this.sparks = []; },
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.2)';
                ctx.fillRect(0,0,width,height);
                
                // Launch
                if(Math.random() < 0.05) {
                    this.rockets.push({
                        x: Math.random() * width,
                        y: height,
                        vy: Math.random() * -10 - 10,
                        color: `hsl(${Math.random()*360}, 100%, 50%)`
                    });
                }
                
                // Rockets
                this.rockets.forEach((r, i) => {
                    r.y += r.vy;
                    r.vy += 0.2;
                    ctx.fillStyle = r.color;
                    ctx.fillRect(r.x, r.y, 3, 3);
                    
                    if(r.vy >= 0) {
                        // Explode
                        this.rockets.splice(i, 1);
                        for(let j=0; j<50; j++) {
                            const angle = Math.random() * Math.PI * 2;
                            const speed = Math.random() * 5;
                            this.sparks.push({
                                x: r.x, y: r.y,
                                vx: Math.cos(angle) * speed,
                                vy: Math.sin(angle) * speed,
                                life: 1,
                                color: r.color
                            });
                        }
                    }
                });
                
                // Sparks
                this.sparks.forEach((s, i) => {
                    s.x += s.vx;
                    s.y += s.vy;
                    s.vy += 0.1; // gravity
                    s.life -= 0.02;
                    
                    ctx.fillStyle = s.color;
                    ctx.globalAlpha = s.life;
                    ctx.beginPath();
                    ctx.arc(s.x, s.y, 2, 0, Math.PI*2);
                    ctx.fill();
                    ctx.globalAlpha = 1;
                    
                    if(s.life <= 0) this.sparks.splice(i, 1);
                });
            }
        },

        // 47. Fractal (Tree)
        fractal: {
            t: 0,
            init: function() {},
            animate: function() {
                ctx.clearRect(0,0,width,height);
                this.t += 0.01;
                const angle = Math.PI/4 + Math.sin(this.t) * 0.2;
                
                const drawBranch = (x, y, len, a, w) => {
                    ctx.beginPath();
                    ctx.moveTo(x, y);
                    const x2 = x + Math.cos(a) * len;
                    const y2 = y + Math.sin(a) * len;
                    ctx.lineTo(x2, y2);
                    ctx.strokeStyle = '#fff';
                    ctx.lineWidth = w;
                    ctx.stroke();
                    
                    if(len > 10) {
                        drawBranch(x2, y2, len * 0.7, a - angle, w * 0.7);
                        drawBranch(x2, y2, len * 0.7, a + angle, w * 0.7);
                    }
                };
                
                drawBranch(width/2, height, 150, -Math.PI/2, 10);
            }
        },

        // 48. Boids (Flocking)
        boids: {
            boids: [],
            init: function() {
                this.boids = [];
                for(let i=0; i<50; i++) {
                    this.boids.push({
                        x: Math.random() * width,
                        y: Math.random() * height,
                        vx: Math.random() * 4 - 2,
                        vy: Math.random() * 4 - 2
                    });
                }
            },
            animate: function() {
                ctx.clearRect(0,0,width,height);
                
                this.boids.forEach(b => {
                    b.x += b.vx;
                    b.y += b.vy;
                    
                    if(b.x < 0) b.x = width;
                    if(b.x > width) b.x = 0;
                    if(b.y < 0) b.y = height;
                    if(b.y > height) b.y = 0;
                    
                    // Draw Triangle
                    const angle = Math.atan2(b.vy, b.vx);
                    ctx.save();
                    ctx.translate(b.x, b.y);
                    ctx.rotate(angle);
                    ctx.fillStyle = '#fff';
                    ctx.beginPath();
                    ctx.moveTo(10, 0);
                    ctx.lineTo(-5, 5);
                    ctx.lineTo(-5, -5);
                    ctx.fill();
                    ctx.restore();
                });
            }
        },

        // 49. Glitter
        glitter: {
            particles: [],
            init: function() {
                this.particles = [];
                for(let i=0; i<200; i++) {
                    this.particles.push({
                        x: Math.random() * width,
                        y: Math.random() * height,
                        size: Math.random() * 3,
                        alpha: Math.random(),
                        speed: Math.random() * 0.05
                    });
                }
            },
            animate: function() {
                ctx.fillStyle = '#000';
                ctx.fillRect(0,0,width,height);
                
                this.particles.forEach(p => {
                    p.alpha += p.speed;
                    if(p.alpha > 1 || p.alpha < 0) p.speed *= -1;
                    
                    ctx.fillStyle = `rgba(255, 255, 255, ${Math.abs(p.alpha)})`;
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, p.size, 0, Math.PI*2);
                    ctx.fill();
                    
                    // Sparkle
                    if(Math.random() < 0.001) {
                        ctx.strokeStyle = '#fff';
                        ctx.beginPath();
                        ctx.moveTo(p.x-5, p.y); ctx.lineTo(p.x+5, p.y);
                        ctx.moveTo(p.x, p.y-5); ctx.lineTo(p.x, p.y+5);
                        ctx.stroke();
                    }
                });
            }
        },

        // 50. Rings
        rings: {
            t: 0,
            init: function() {},
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.1)';
                ctx.fillRect(0,0,width,height);
                this.t += 0.02;
                const cx = width/2;
                const cy = height/2;
                
                for(let i=1; i<10; i++) {
                    ctx.strokeStyle = `hsl(${i * 36 + this.t * 50}, 70%, 50%)`;
                    ctx.lineWidth = 5;
                    ctx.beginPath();
                    ctx.arc(cx, cy, i * 30, this.t * (i%2===0?1:-1), this.t * (i%2===0?1:-1) + Math.PI);
                    ctx.stroke();
                }
            }
        },

        // 51. Laser
        laser: {
            beams: [],
            init: function() { this.beams = []; },
            animate: function() {
                ctx.fillStyle = 'rgba(0,0,0,0.2)';
                ctx.fillRect(0,0,width,height);
                
                if(Math.random() < 0.1) {
                    this.beams.push({
                        y: Math.random() * height,
                        speed: Math.random() * 20 + 20,
                        width: Math.random() * 5 + 1,
                        color: Math.random() > 0.5 ? '#f00' : '#0f0'
                    });
                }
                
                this.beams.forEach((b, i) => {
                    ctx.fillStyle = b.color;
                    ctx.fillRect(0, b.y, width, b.width);
                    
                    // Fade out
                    b.width *= 0.9;
                    if(b.width < 0.1) this.beams.splice(i, 1);
                });
            }
        },

        // 13. Net (Dots + Lines specific)
        net: {
            // Uses particles renderer with specific config
            init: function() { Renderers.particles.init.call(Renderers.particles, 'net'); },
            animate: function() { Renderers.particles.animate.call(Renderers.particles); }
        }
    };

    // Helper Class for Particles
    // --- Procedural Theme Generator ---
    const ThemeGen = {
        // 1. Advanced Particles (Float, Rain, Snow, Bubbles, Jitter)
        particles: (opts) => ({
            items: [],
            init: function() {
                this.items = [];
                const count = opts.count || 50;
                for(let i=0; i<count; i++) {
                    this.items.push({
                        x: Math.random() * width,
                        y: Math.random() * height,
                        vx: (Math.random() - 0.5) * (opts.speedX || 1),
                        vy: (Math.random() - 0.5) * (opts.speedY || 1),
                        size: Math.random() * (opts.sizeVar || 2) + (opts.minSize || 1),
                        phase: Math.random() * Math.PI * 2
                    });
                }
            },
            animate: function() {
                ctx.clearRect(0,0,width,height); // Clear only if not trailing
                if(opts.trail) {
                    ctx.fillStyle = `rgba(0,0,0,${opts.trail})`;
                    ctx.fillRect(0,0,width,height);
                } else {
                    ctx.clearRect(0,0,width,height);
                }

                if(!this.items.length) this.init();

                ctx.fillStyle = opts.color;
                ctx.strokeStyle = opts.color;
                
                this.items.forEach((p, i) => {
                    // Movement
                    p.x += p.vx;
                    p.y += p.vy;
                    
                    // Behavior: Bubble Wobble
                    if(opts.wobble) {
                        p.x += Math.sin(p.phase + Date.now()*0.002) * 0.5;
                    }

                    // Behavior: Rain/Fall
                    if(opts.fall) {
                        if(p.y > height) { p.y = -10; p.x = Math.random() * width; }
                    } else {
                        // Bounce or Wrap
                        if(p.x < 0 || p.x > width) p.vx *= -1;
                        if(p.y < 0 || p.y > height) p.vy *= -1;
                    }
                    
                    // Draw
                    ctx.beginPath();
                    if(opts.shape === 'square') ctx.rect(p.x, p.y, p.size, p.size);
                    else ctx.arc(p.x, p.y, p.size, 0, Math.PI*2);
                    
                    if(opts.fill) ctx.fill();
                    else ctx.stroke();
                    
                    // Connections
                    if(opts.connect) {
                        for(let j=i+1; j<this.items.length; j++) {
                            const p2 = this.items[j];
                            const dx = p.x - p2.x, dy = p.y - p2.y;
                            const dist = Math.sqrt(dx*dx + dy*dy);
                            if(dist < (opts.connectDist || 100)) {
                                ctx.globalAlpha = 1 - dist/(opts.connectDist || 100);
                                ctx.beginPath();
                                ctx.moveTo(p.x, p.y);
                                ctx.lineTo(p2.x, p2.y);
                                ctx.stroke();
                                ctx.globalAlpha = 1;
                            }
                        }
                    }
                });
            }
        }),

        // 2. Waves (Sine, Cosine, Interference)
        waves: (opts) => ({
            offset: 0,
            bgParticles: [],
            init: function() {
                // Initialize background particles if enabled
                if (opts.bgParticles) {
                    this.bgParticles = [];
                    const count = opts.bgParticles.count || 50;
                    for(let i=0; i<count; i++) {
                        this.bgParticles.push({
                            x: Math.random() * width,
                            y: Math.random() * height,
                            size: Math.random() * (opts.bgParticles.size || 2) + 1,
                            speedY: (Math.random() - 0.5) * (opts.bgParticles.speed || 0.5),
                            speedX: (Math.random() - 0.5) * (opts.bgParticles.speed || 0.5),
                            opacity: Math.random() * 0.5 + 0.1
                        });
                    }
                }
            },
            animate: function() {
                // 1. Background
                if (opts.bgColor === 'transparent') {
                    ctx.clearRect(0, 0, width, height);
                } else {
                    ctx.fillStyle = opts.bgColor || '#000';
                    ctx.fillRect(0, 0, width, height);
                }

                // 2. Render Background Particles
                if (this.bgParticles.length === 0 && opts.bgParticles) this.init();
                
                if (this.bgParticles.length > 0) {
                    ctx.fillStyle = opts.bgParticles.color || 'rgba(255,255,255,0.5)';
                    this.bgParticles.forEach(p => {
                        p.y += p.speedY;
                        p.x += p.speedX;
                        if(p.y < 0) p.y = height;
                        if(p.y > height) p.y = 0;
                        if(p.x < 0) p.x = width;
                        if(p.x > width) p.x = 0;
                        
                        ctx.globalAlpha = p.opacity;
                        ctx.beginPath();
                        ctx.arc(p.x, p.y, p.size, 0, Math.PI*2);
                        ctx.fill();
                    });
                    ctx.globalAlpha = 1;
                }

                // 3. Render Waves
                this.offset += opts.speed || 0.02;
                ctx.lineWidth = opts.lineWidth || 2;
                
                for(let i=0; i<(opts.count || 5); i++) {
                    ctx.beginPath();
                    ctx.strokeStyle = opts.color.replace('ALPHA', 1 - i/(opts.count||5));
                    
                    for(let x=0; x<width; x+=(opts.res || 10)) {
                        const y = height/2 + 
                                  Math.sin(x * (opts.freq || 0.01) + this.offset + i * (opts.shift || 0.5)) * (opts.amp || 50) +
                                  (opts.complex ? Math.cos(x * 0.02 - this.offset) * 30 : 0);
                        
                        if(x===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
                    }
                    ctx.stroke();
                }
            }
        }),

        // 3. Geometric Grid (Perspective, Flat, Moving)
        grid: (opts) => ({
            offset: 0,
            init: function() {},
            animate: function() {
                ctx.fillStyle = '#000';
                ctx.fillRect(0,0,width,height);
                this.offset += opts.speed || 1;
                ctx.strokeStyle = opts.color;
                ctx.lineWidth = 1;
                
                const s = opts.size || 40;
                
                // Vertical Lines
                for(let x=0; x<=width; x+=s) {
                    ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,height); ctx.stroke();
                }
                
                // Horizontal Lines (Moving)
                const off = this.offset % s;
                for(let y=off; y<=height; y+=s) {
                    ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(width,y); ctx.stroke();
                }
                
                // Perspective diagonals if enabled
                if(opts.perspective) {
                    const cx = width/2, cy = height/2;
                    ctx.globalAlpha = 0.3;
                    for(let i=0; i<4; i++) {
                         ctx.beginPath(); ctx.moveTo(cx, cy); 
                         ctx.lineTo(i<2?0:width, i%2===0?0:height); 
                         ctx.stroke();
                    }
                    ctx.globalAlpha = 1;
                }
            }
        }),

        // 4. Spiral / Vortex
        spiral: (opts) => ({
            particles: [],
            init: function() {
                this.particles = [];
                for(let i=0; i<(opts.count||100); i++) {
                    this.particles.push({
                        angle: Math.random() * Math.PI * 2,
                        radius: Math.random() * Math.min(width,height)/2,
                        speed: (Math.random() + 0.1) * (opts.speed || 0.02)
                    });
                }
            },
            animate: function() {
                if(!this.particles.length) this.init();
                ctx.fillStyle = opts.trail ? `rgba(0,0,0,${opts.trail})` : '#000';
                ctx.fillRect(0,0,width,height);
                
                const cx = width/2, cy = height/2;
                ctx.fillStyle = opts.color;
                
                this.particles.forEach(p => {
                    p.angle += p.speed;
                    if(opts.expand) p.radius += 0.5;
                    if(p.radius > Math.min(width,height)/2) p.radius = 0;
                    
                    const x = cx + Math.cos(p.angle) * p.radius;
                    const y = cy + Math.sin(p.angle) * p.radius;
                    
                    ctx.beginPath(); 
                    ctx.arc(x,y, opts.size || 2, 0, Math.PI*2); 
                    ctx.fill();
                });
            }
        }),
        
        // 5. Matrix / Digital Rain
        matrix: (opts) => ({
            drops: [],
            init: function() {
                const cols = Math.floor(width / (opts.size || 20));
                this.drops = Array(cols).fill(1);
            },
            animate: function() {
                if(!this.drops.length || this.drops.length !== Math.floor(width/(opts.size||20))) this.init();
                
                ctx.fillStyle = 'rgba(0,0,0,0.05)'; // Fixed trail for matrix
                ctx.fillRect(0,0,width,height);
                
                ctx.fillStyle = opts.color;
                ctx.font = `${opts.size || 20}px monospace`;
                
                this.drops.forEach((y, i) => {
                    const char = String.fromCharCode(0x30A0 + Math.random() * 96);
                    const x = i * (opts.size || 20);
                    ctx.fillText(char, x, y * (opts.size || 20));
                    
                    if(y * (opts.size || 20) > height && Math.random() > 0.975) {
                        this.drops[i] = 0;
                    }
                    this.drops[i]++;
                });
            }
        }),

        // 6. Tunnel
        tunnel: (opts) => ({
            shapes: [],
            frame: 0,
            init: function() {},
            animate: function() {
                ctx.fillStyle = '#000';
                ctx.fillRect(0,0,width,height);
                this.frame += opts.speed || 2;
                
                ctx.strokeStyle = opts.color;
                ctx.lineWidth = 2;
                const cx = width/2, cy = height/2;
                
                const max = opts.count || 10;
                const space = opts.space || 50;
                
                for(let i=0; i<max; i++) {
                    let z = (this.frame + i * space) % (max * space);
                    if(z < 1) z = 1;
                    const scale = (opts.fov || 300) / z;
                    const s = (opts.baseSize || 100) * scale;
                    
                    ctx.globalAlpha = Math.min(1, z/100);
                    ctx.beginPath();
                    if(opts.shape === 'circle') ctx.arc(cx, cy, s, 0, Math.PI*2);
                    else ctx.rect(cx - s, cy - s, s*2, s*2);
                    ctx.stroke();
                }
                ctx.globalAlpha = 1;
            }
        })
    };

    // --- Aesthetic & Blend Themes (User Requested) ---
    if (!window.curatedThemes) window.curatedThemes = [];
    window.curatedThemes.push(
        {
            id: 'aesthetic_wave_dots',
            name: 'Ethereal Wave',
            type: 'waves',
            opts: {
                color: 'rgba(255, 255, 255, ALPHA)',
                speed: 0.01,
                count: 3,
                amp: 40,
                shift: 0.2,
                bgColor: 'transparent',
                bgParticles: {
                    count: 60,
                    size: 1.5,
                    speed: 0.2,
                    color: 'rgba(255, 255, 255, 0.4)'
                }
            }
        },
        {
            id: 'aesthetic_blend_soft',
            name: 'Soft Blend',
            type: 'waves',
            opts: {
                color: 'rgba(100, 200, 255, ALPHA)',
                speed: 0.015,
                count: 4,
                amp: 30,
                bgColor: 'transparent', // Blends with website
                bgParticles: {
                    count: 30,
                    size: 2,
                    speed: 0.1,
                    color: 'rgba(100, 200, 255, 0.3)'
                }
            }
        },
        {
            id: 'aesthetic_midnight',
            name: 'Midnight Whisper',
            type: 'waves',
            opts: {
                color: 'rgba(147, 51, 234, ALPHA)', // Purple
                speed: 0.02,
                count: 5,
                amp: 50,
                bgColor: 'rgba(10, 10, 20, 0.95)', // Dark but not pitch black
                bgParticles: {
                    count: 80,
                    size: 1.5,
                    speed: 0.3,
                    color: 'rgba(168, 85, 247, 0.4)'
                }
            }
        }
    );

    // --- Register Curated Themes to Renderers ---
    if (window.curatedThemes) {
        window.curatedThemes.forEach((theme, index) => {
            // Dynamic color fallback handling
            if(theme.opts.color === 'hsl(random, 70%, 50%)' && theme.name === 'Confetti Party') {
                theme.opts.color = '#ff00ff'; // Fallback
            }
            if(theme.name === 'Rainbow Flow') {
                theme.opts.color = 'rgba(255, 255, 255, ALPHA)'; // Fallback
            }

            if(ThemeGen[theme.type]) {
                // Use theme.id (e.g., 'gen_0') as the key
                Renderers[theme.id] = ThemeGen[theme.type](theme.opts);
            }
        });
    }

    class Particle {
        constructor(w, h, theme) {
            this.theme = theme;
            this.reset(w, h);
        }
        
        reset(w, h) {
            this.x = Math.random() * w;
            this.y = Math.random() * h;
            
            // Configurable speed via data-particle-speed
            const speedMult = parseFloat(canvas.getAttribute('data-particle-speed')) || 1.0;
            
            this.vx = (Math.random() - 0.5) * 0.3 * speedMult; // Slower
            this.vy = (Math.random() - 0.5) * 0.3 * speedMult; // Slower
            this.size = Math.random() * 2 + 1;
            this.color = 'rgba(255,255,255,0.5)';
            
            if (this.theme === 'default' || this.theme === 'leaf' || this.theme === 'customer') {
                this.color = `rgba(255, 255, 255, ${Math.random() * 0.3 + 0.4})`; // Changed to White
                this.size = Math.random() * 3 + 2; 
                if(this.theme === 'leaf') {
                     this.vx = (Math.random() - 0.5) * 0.6 * speedMult; // Slower
                     this.vy = (Math.random() * 0.4 + 0.3) * speedMult; // Slower
                     this.rotation = Math.random() * Math.PI * 2;
                }
                if(this.theme === 'customer') {
                    this.vx = (Math.random() - 0.5) * 0.4 * speedMult;
                    this.vy = (Math.random() - 0.5) * 0.4 * speedMult;
                    this.size = Math.random() * 2 + 1.5; // Small circles
                }
            } else if (this.theme === 'snow') {
                this.vy = Math.random() * 2 + 1;
                this.color = 'rgba(255,255,255,0.8)';
            } else if (this.theme === 'net') {
                // Professional Net
                this.size = Math.random() * 3 + 2; // Bigger
                this.color = 'rgba(255, 255, 255, 0.9)'; // Brighter
            } else if (this.theme === 'rain') {
                this.vy = Math.random() * 15 + 10;
                this.vx = 0;
                this.color = 'rgba(174, 194, 224, 0.6)';
            } else if (this.theme === 'fireflies') {
                this.color = 'rgba(255, 215, 0, 0.8)';
                this.vx *= 2; this.vy *= 2;
            }
        }

        update(w, h) {
            this.x += this.vx;
            this.y += this.vy;
            
            if(this.theme === 'leaf') this.rotation += 0.02;

            // Wrap
            if (this.x < -20) this.x = w + 20;
            if (this.x > w + 20) this.x = -20;
            if (this.y < -20) this.y = h + 20;
            if (this.y > h + 20) this.y = -20;
        }

        draw(ctx) {
            ctx.fillStyle = this.color;
            if(this.theme === 'leaf') {
                ctx.save();
                ctx.translate(this.x, this.y);
                ctx.rotate(this.rotation || 0);
                ctx.beginPath();
                ctx.moveTo(0, -this.size);
                ctx.bezierCurveTo(this.size/2, -this.size/2, this.size, 0, 0, this.size);
                ctx.bezierCurveTo(-this.size, 0, -this.size/2, -this.size/2, 0, -this.size);
                ctx.fill();
                ctx.restore();
            } else if (this.theme === 'rain') {
                ctx.strokeStyle = this.color;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(this.x, this.y);
                ctx.lineTo(this.x, this.y + 10);
                ctx.stroke();
            } else {
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size, 0, Math.PI*2);
                ctx.fill();
            }
        }
    }

    // --- Core Logic ---

    function resize() {
        width = window.innerWidth;
        height = window.innerHeight;
        canvas.width = width;
        canvas.height = height;
        
        const theme = canvas.getAttribute('data-particle-theme') || 'default';
        console.log("Selected Theme:", theme);
        
        // Select Renderer
        if (['leaf', 'bubbles', 'snow', 'fireflies', 'rain', 'pollen', 'petals', 'embers', 'confetti', 'stars', 'net', 'customer', 'default'].includes(theme)) {
            renderer = Renderers.particles;
            renderer.init(theme);
        } else if (Renderers[theme]) {
            renderer = Renderers[theme];
            if(renderer.init) renderer.init();
        } else {
            renderer = Renderers.particles;
            renderer.init('default');
        }
    }

    let animationLogged = false;
    function animate() {
        if(!animationLogged && renderer) {
            console.log("Animation loop started with renderer:", renderer);
            animationLogged = true;
        }
        if(renderer && renderer.animate) {
            renderer.animate();
        }
        window.heroAnimationId = requestAnimationFrame(animate);
    }
    
    window.heroResizeHandler = resize;
    window.addEventListener('resize', resize);
    
    // Explicitly call resize and animate to ensure startup
    console.log("Starting animation loop...");
    resize();
    animate();
    
    // Safety check: Re-run resize after a short delay to handle potential race conditions
    setTimeout(resize, 100);
}

// Expose for demo
window.initHeroCanvas = initHeroCanvas;

// --- Scroll Animations (Intersection Observer) ---
function initScrollAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: "0px 0px -50px 0px"
    });
    
    document.querySelectorAll('.animate-on-scroll').forEach(el => {
        observer.observe(el);
    });
}

// --- Typing Effect for Hero Title ---
function initTypingEffect() {
    const element = document.getElementById('typing-text');
    if (!element) return;
    
    const words = ["Disease Detection", "Health Analysis", "Yield Protection"];
    let wordIndex = 0;
    let charIndex = 0;
    let isDeleting = false;
    let typeSpeed = 100;
    
    function type() {
        const currentWord = words[wordIndex];
        
        if (isDeleting) {
            element.textContent = currentWord.substring(0, charIndex - 1);
            charIndex--;
            typeSpeed = 50;
        } else {
            element.textContent = currentWord.substring(0, charIndex + 1);
            charIndex++;
            typeSpeed = 100;
        }
        
        if (!isDeleting && charIndex === currentWord.length) {
            isDeleting = true;
            typeSpeed = 2000;
        } else if (isDeleting && charIndex === 0) {
            isDeleting = false;
            wordIndex = (wordIndex + 1) % words.length;
            typeSpeed = 500;
        }
        
        setTimeout(type, typeSpeed);
    }
    
    type();
}

// --- Counters Animation ---
function initCounters() {
    const counters = document.querySelectorAll('.counter');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const target = +entry.target.getAttribute('data-target');
                const duration = 2000; // 2 seconds
                const increment = target / (duration / 16);
                
                let current = 0;
                const updateCounter = () => {
                    current += increment;
                    if (current < target) {
                        entry.target.textContent = Math.ceil(current);
                        requestAnimationFrame(updateCounter);
                    } else {
                        entry.target.textContent = target;
                    }
                };
                updateCounter();
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });
    
    counters.forEach(counter => observer.observe(counter));
}