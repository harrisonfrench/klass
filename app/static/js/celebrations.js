/**
 * Celebrations - Confetti and animation effects for milestones
 */

const Celebrations = {
    // Confetti particles array
    particles: [],
    canvas: null,
    ctx: null,
    animationId: null,

    // Initialize confetti canvas
    init: function() {
        if (this.canvas) return;

        this.canvas = document.createElement('canvas');
        this.canvas.id = 'confetti-canvas';
        this.canvas.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 9999;
        `;
        document.body.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        this.resize();
        window.addEventListener('resize', () => this.resize());
    },

    resize: function() {
        if (!this.canvas) return;
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    },

    // Create a single confetti particle
    createParticle: function(x, y, colors) {
        const colorList = colors || ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#ec4899'];
        return {
            x: x || Math.random() * this.canvas.width,
            y: y || -10,
            size: Math.random() * 8 + 4,
            color: colorList[Math.floor(Math.random() * colorList.length)],
            speedX: (Math.random() - 0.5) * 6,
            speedY: Math.random() * 4 + 2,
            rotation: Math.random() * 360,
            rotationSpeed: (Math.random() - 0.5) * 10,
            opacity: 1,
            shape: Math.random() > 0.5 ? 'rect' : 'circle'
        };
    },

    // Draw a single particle
    drawParticle: function(p) {
        this.ctx.save();
        this.ctx.translate(p.x, p.y);
        this.ctx.rotate(p.rotation * Math.PI / 180);
        this.ctx.globalAlpha = p.opacity;
        this.ctx.fillStyle = p.color;

        if (p.shape === 'rect') {
            this.ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size / 2);
        } else {
            this.ctx.beginPath();
            this.ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2);
            this.ctx.fill();
        }

        this.ctx.restore();
    },

    // Animate particles
    animate: function() {
        if (!this.ctx) return;

        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        this.particles = this.particles.filter(p => {
            p.x += p.speedX;
            p.y += p.speedY;
            p.speedY += 0.1; // gravity
            p.rotation += p.rotationSpeed;
            p.opacity -= 0.005;

            if (p.opacity > 0 && p.y < this.canvas.height + 50) {
                this.drawParticle(p);
                return true;
            }
            return false;
        });

        if (this.particles.length > 0) {
            this.animationId = requestAnimationFrame(() => this.animate());
        } else {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    },

    // Fire confetti burst
    confetti: function(options = {}) {
        this.init();

        const count = options.count || 100;
        const x = options.x || this.canvas.width / 2;
        const y = options.y || this.canvas.height / 3;
        const colors = options.colors;
        const spread = options.spread || 200;

        for (let i = 0; i < count; i++) {
            const particle = this.createParticle(
                x + (Math.random() - 0.5) * spread,
                y + (Math.random() - 0.5) * 50,
                colors
            );
            particle.speedX = (Math.random() - 0.5) * 15;
            particle.speedY = Math.random() * -10 - 5;
            this.particles.push(particle);
        }

        if (!this.animationId) {
            this.animate();
        }
    },

    // Streak celebration (fire emoji colors)
    streakCelebration: function(streakCount) {
        this.confetti({
            count: Math.min(50 + streakCount * 10, 200),
            colors: ['#f59e0b', '#ef4444', '#fbbf24', '#dc2626', '#fcd34d'],
            spread: 300
        });

        // Show streak toast
        this.showToast(`🔥 ${streakCount} Day Streak!`, 'streak');
    },

    // Achievement celebration
    achievementCelebration: function(title) {
        this.confetti({
            count: 150,
            colors: ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd'],
            spread: 400
        });

        this.showToast(`🏆 ${title}`, 'achievement');
    },

    // Milestone celebration (completing quizzes, decks, etc.)
    milestoneCelebration: function(title) {
        this.confetti({
            count: 80,
            colors: ['#10b981', '#34d399', '#6ee7b7', '#a7f3d0'],
            spread: 250
        });

        this.showToast(`✨ ${title}`, 'milestone');
    },

    // Show a celebratory toast notification
    showToast: function(message, type = 'default') {
        const toast = document.createElement('div');
        toast.className = `celebration-toast celebration-toast-${type}`;
        toast.innerHTML = `<span>${message}</span>`;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%) translateY(-100px);
            background: ${type === 'streak' ? 'linear-gradient(135deg, #f59e0b, #ef4444)' :
                        type === 'achievement' ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' :
                        'linear-gradient(135deg, #10b981, #059669)'};
            color: white;
            padding: 1rem 2rem;
            border-radius: 12px;
            font-weight: 600;
            font-size: 1.1rem;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            z-index: 10000;
            transition: transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
        `;

        document.body.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            toast.style.transform = 'translateX(-50%) translateY(0)';
        });

        // Animate out and remove
        setTimeout(() => {
            toast.style.transform = 'translateX(-50%) translateY(-100px)';
            setTimeout(() => toast.remove(), 500);
        }, 3000);
    },

    // Check for celebration triggers (called on page load)
    checkTriggers: function() {
        // Check URL params for celebration triggers
        const params = new URLSearchParams(window.location.search);

        if (params.get('celebration') === 'streak') {
            const streakCount = parseInt(params.get('count')) || 1;
            setTimeout(() => this.streakCelebration(streakCount), 500);
        }

        if (params.get('celebration') === 'achievement') {
            const title = params.get('title') || 'Achievement Unlocked!';
            setTimeout(() => this.achievementCelebration(title), 500);
        }

        if (params.get('celebration') === 'milestone') {
            const title = params.get('title') || 'Milestone Reached!';
            setTimeout(() => this.milestoneCelebration(title), 500);
        }

        // Check for new streak milestone in session storage
        const newStreak = sessionStorage.getItem('new_streak');
        if (newStreak) {
            sessionStorage.removeItem('new_streak');
            setTimeout(() => this.streakCelebration(parseInt(newStreak)), 500);
        }

        // Check for first-time user
        const isNewUser = sessionStorage.getItem('new_user');
        if (isNewUser) {
            sessionStorage.removeItem('new_user');
            setTimeout(() => {
                this.confetti({ count: 100 });
                this.showToast('Welcome to Klass! 🎉', 'milestone');
            }, 1000);
        }
    }
};

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    Celebrations.checkTriggers();
});

// Expose globally
window.Celebrations = Celebrations;
