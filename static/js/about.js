(() => {
  const initializeReveals = () => {
    const elements = document.querySelectorAll('[data-reveal]');
    if (
      !elements.length
      || window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      return;
    }

    elements.forEach((element, index) => {
      element.classList.add('about-reveal');
      element.style.setProperty('--about-reveal-delay', `${(index % 5) * 70}ms`);
    });

    const pending = new Set(elements);
    let frameScheduled = false;

    const revealVisibleElements = () => {
      frameScheduled = false;
      const viewportHeight = window.innerHeight;

      pending.forEach((element) => {
        const bounds = element.getBoundingClientRect();
        if (bounds.top < viewportHeight * 0.92 && bounds.bottom > viewportHeight * 0.08) {
          element.classList.add('is-visible');
          pending.delete(element);
        }
      });

      if (!pending.size) {
        window.removeEventListener('scroll', scheduleReveal);
        window.removeEventListener('resize', scheduleReveal);
      }
    };

    const scheduleReveal = () => {
      if (!frameScheduled) {
        frameScheduled = true;
        window.requestAnimationFrame(revealVisibleElements);
      }
    };

    window.addEventListener('scroll', scheduleReveal, { passive: true });
    window.addEventListener('resize', scheduleReveal);
    scheduleReveal();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeReveals, { once: true });
  } else {
    initializeReveals();
  }
})();
