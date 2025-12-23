document.addEventListener('DOMContentLoaded', () => {
  // --- Search filter (home) ---
  const filterInput = document.getElementById('event-filter');
  const eventCols = document.querySelectorAll('#event-list .event-col');

  if (filterInput && eventCols.length) {
    filterInput.addEventListener('input', () => {
      const q = filterInput.value.trim().toLowerCase();
      eventCols.forEach(col => {
        const title = (col.querySelector('.card-title')?.textContent || '').toLowerCase();
        col.style.display = title.includes(q) ? '' : 'none';
      });
    });
  }

  // --- Stats counters ---
  const counters = document.querySelectorAll('.stat-number[data-count]');
  const animateCounter = (el) => {
    const target = parseInt(el.dataset.count, 10) || 0;
    let current = 0;
    const step = Math.max(1, Math.floor(target / 60));
    const tick = () => {
      current += step;
      if (current >= target) { current = target; }
      el.textContent = current.toLocaleString();
      if (current < target) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };
  counters.forEach(animateCounter);

  // --- Navbar shadow on scroll ---
  const nav = document.querySelector('.fancy-nav');
  const onScroll = () => {
    if (!nav) return;
    if (window.scrollY > 8) nav.classList.add('scrolled');
    else nav.classList.remove('scrolled');
  };
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  // --- Improve hover dropdown for keyboard users ---
  document.querySelectorAll('.hover-open').forEach(li => {
    const link = li.querySelector('[data-bs-toggle="dropdown"]');
    const menu = li.querySelector('.dropdown-menu');
    if (!link || !menu) return;

    link.addEventListener('focus', () => menu.classList.add('show'));
    link.addEventListener('blur',  () => menu.classList.remove('show'));
    menu.addEventListener('mouseleave', () => menu.classList.remove('show'));
  });
});

document.addEventListener('DOMContentLoaded', function () {
    const filterInput = document.getElementById('event-filter');
    const eventCards = document.querySelectorAll('#event-list .card');

    if (filterInput) {
        filterInput.addEventListener('input', function () {
            const text = this.value.toLowerCase();
            eventCards.forEach(card => {
                const title = card.querySelector('.card-title').textContent.toLowerCase();
                card.parentElement.style.display = title.includes(text) ? '' : 'none';
            });
        });
    }
});
