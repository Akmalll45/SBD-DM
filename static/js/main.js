/**
 * Hendra Sport - Vanilla JavaScript Storefront Controller
 */

document.addEventListener('DOMContentLoaded', () => {
  // Initialize Lucide Icons if available
  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Mobile Menu Toggle
  const menuToggle = document.getElementById('menu-toggle');
  const navMenu = document.getElementById('nav-menu');
  if (menuToggle && navMenu) {
    menuToggle.addEventListener('click', () => {
      navMenu.classList.toggle('open');
      document.body.classList.toggle('menu-open', navMenu.classList.contains('open'));
    });
  }

  // Accessible click/touch behavior for navigation dropdowns
  const dropdownToggles = document.querySelectorAll('.dropdown > .nav-dropdown-toggle');
  dropdownToggles.forEach((toggle) => {
    toggle.addEventListener('click', () => {
      const dropdown = toggle.parentElement;
      const isOpen = dropdown.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(isOpen));
    });
  });

  document.addEventListener('click', (event) => {
    document.querySelectorAll('.dropdown.open').forEach((dropdown) => {
      if (!dropdown.contains(event.target)) {
        dropdown.classList.remove('open');
        const toggle = dropdown.querySelector('.nav-dropdown-toggle');
        if (toggle) toggle.setAttribute('aria-expanded', 'false');
      }
    });
  });

  document.querySelectorAll('[data-copy-value]').forEach((button) => {
    button.addEventListener('click', () => {
      navigator.clipboard.writeText(button.dataset.copyValue)
        .then(() => { button.textContent = 'Tersalin'; })
        .catch(() => { button.textContent = 'Gagal menyalin'; });
    });
  });

  // Search Panel Toggle
  const searchToggle = document.getElementById('search-toggle');
  const searchPanel = document.getElementById('search-panel');
  if (searchToggle && searchPanel) {
    searchToggle.addEventListener('click', () => {
      searchPanel.classList.toggle('open');
      if (searchPanel.classList.contains('open')) {
        const input = searchPanel.querySelector('input');
        if (input) input.focus();
      }
    });
  }

  // Sliding Cart Drawer Elements
  const cartToggleBtn = document.getElementById('cart-toggle-btn');
  const cartDrawer = document.getElementById('cart-drawer');
  const cartOverlay = document.getElementById('cart-drawer-overlay');
  const cartCloseBtn = document.getElementById('cart-drawer-close');

  function openCartDrawer() {
    if (cartDrawer && cartOverlay) {
      cartDrawer.classList.add('open');
      cartOverlay.classList.add('open');
      document.body.classList.add('drawer-open');
    }
  }

  function closeCartDrawer() {
    if (cartDrawer && cartOverlay) {
      cartDrawer.classList.remove('open');
      cartOverlay.classList.remove('open');
      document.body.classList.remove('drawer-open');
    }
  }

  if (cartToggleBtn) {
    cartToggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      openCartDrawer();
    });
  }

  if (cartCloseBtn) cartCloseBtn.addEventListener('click', closeCartDrawer);
  if (cartOverlay) cartOverlay.addEventListener('click', closeCartDrawer);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeCartDrawer();
  });

  // Expose global drawer helper
  window.openCartDrawer = openCartDrawer;
  window.closeCartDrawer = closeCartDrawer;

  // Global Toast Notification Helper
  window.showToast = function (message, type = 'info') {
    let container = document.getElementById('toast-root');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-root';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  };

  // ---------------------------------------------------------------------------
  // Hero Stadium Energy Sparks & Embers Particles
  // ---------------------------------------------------------------------------
  const canvas = document.getElementById('hero-particles');
  if (canvas && canvas.parentElement) {
    const ctx = canvas.getContext('2d');
    let width = (canvas.width = canvas.parentElement.offsetWidth);
    let height = (canvas.height = canvas.parentElement.offsetHeight);

    window.addEventListener('resize', () => {
      if (canvas && canvas.parentElement) {
        width = canvas.width = canvas.parentElement.offsetWidth;
        height = canvas.height = canvas.parentElement.offsetHeight;
      }
    });

    const particles = [];
    const count = Math.min(45, Math.floor(width / 28));
    const colors = [
      'rgba(255, 85, 0, ',
      'rgba(255, 140, 0, ',
      'rgba(255, 215, 60, ',
      'rgba(255, 255, 255, '
    ];

    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        radius: Math.random() * 2.2 + 0.8,
        color: colors[Math.floor(Math.random() * colors.length)],
        alpha: Math.random() * 0.7 + 0.3,
        speedY: -(Math.random() * 0.9 + 0.35),
        speedX: (Math.random() - 0.5) * 0.7,
        pulse: Math.random() * Math.PI,
      });
    }

    let mouseX = -1000;
    let mouseY = -1000;
    const heroSection = canvas.closest('.hero');
    if (heroSection) {
      heroSection.addEventListener('mousemove', (e) => {
        const rect = heroSection.getBoundingClientRect();
        mouseX = e.clientX - rect.left;
        mouseY = e.clientY - rect.top;
      });
      heroSection.addEventListener('mouseleave', () => {
        mouseX = -1000;
        mouseY = -1000;
      });
    }

    function renderParticles() {
      ctx.clearRect(0, 0, width, height);
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.pulse += 0.04;
        const currentAlpha = Math.max(0.12, p.alpha + Math.sin(p.pulse) * 0.25);

        // Cursor interactive repulsion
        const dx = p.x - mouseX;
        const dy = p.y - mouseY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          const force = (120 - dist) / 120;
          p.x += (dx / dist) * force * 1.8;
          p.y += (dy / dist) * force * 1.8;
        }

        p.x += p.speedX;
        p.y += p.speedY;

        if (p.y < -10) {
          p.y = height + 10;
          p.x = Math.random() * width;
        }
        if (p.x < -10) p.x = width + 10;
        if (p.x > width + 10) p.x = -10;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = p.color + currentAlpha + ')';
        ctx.shadowBlur = 10;
        ctx.shadowColor = '#ff5500';
        ctx.fill();
      }
      requestAnimationFrame(renderParticles);
    }
    requestAnimationFrame(renderParticles);
  }
});

