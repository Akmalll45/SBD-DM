document.addEventListener('error', (event) => {
  const image = event.target;
  if (!(image instanceof HTMLImageElement)) return;

  const defaultFallback = document.documentElement.dataset.imageFallback;
  if (!defaultFallback || image.dataset.imageFallback === 'default') return;

  const preferredFallback = image.dataset.fallbackSrc;
  if (
    image.dataset.imageFallback !== 'preferred'
    && preferredFallback
    && new URL(preferredFallback, document.baseURI).href !== image.src
  ) {
    image.dataset.imageFallback = 'preferred';
    image.src = preferredFallback;
    return;
  }

  image.dataset.imageFallback = 'default';
  image.src = defaultFallback;
}, true);
