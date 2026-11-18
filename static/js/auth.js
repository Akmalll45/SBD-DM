document.querySelectorAll('[data-password-toggle]').forEach((toggle) => {
  const inputId = toggle.getAttribute('aria-controls');
  const input = inputId ? document.getElementById(inputId) : null;

  if (!(input instanceof HTMLInputElement)) {
    console.error('Password visibility toggle is missing its input.');
    return;
  }

  toggle.addEventListener('click', () => {
    const isVisible = input.type === 'password';
    input.type = isVisible ? 'text' : 'password';
    toggle.setAttribute('aria-label', isVisible ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi');
    toggle.setAttribute('aria-pressed', String(isVisible));
  });
});
