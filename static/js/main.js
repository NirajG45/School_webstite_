(() => {
  'use strict';

  /* =========================================
     1. MOBILE MENU LOGIC (UPGRADED)
     ========================================= */
  const toggle = document.getElementById('menuToggle');
  const menu = document.getElementById('mobileMenu');
  const backdrop = document.getElementById('menuBackdrop');
  const closeButton = document.getElementById('menuClose');
  
  // 🚀 UPGRADE: Breakpoint को 1280px किया गया ताकि यह CSS के साथ परफेक्टली मैच करे
  const mobileBreakpoint = window.matchMedia('(max-width: 1280px)');
  let lastFocused = null;

  function openMenu() {
    if (!mobileBreakpoint.matches || !menu || !toggle) return;
    lastFocused = document.activeElement;
    menu.classList.add('is-open');
    menu.removeAttribute('inert');
    menu.setAttribute('aria-hidden', 'false');
    toggle.setAttribute('aria-expanded', 'true');
    toggle.setAttribute('aria-label', 'Close navigation menu');
    if (backdrop) backdrop.hidden = false;
    document.body.classList.add('menu-open');
    requestAnimationFrame(() => closeButton?.focus());
  }

  function closeMenu({ restoreFocus = true } = {}) {
    if (!menu || !toggle || !backdrop) return;
    menu.classList.remove('is-open');
    menu.setAttribute('aria-hidden', 'true');
    menu.setAttribute('inert', '');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'Open navigation menu');
    backdrop.hidden = true;
    document.body.classList.remove('menu-open');
    if (restoreFocus && lastFocused instanceof HTMLElement) {
      lastFocused.focus({ preventScroll: true });
    }
  }

  // Event Listeners
  toggle?.addEventListener('click', () => {
    toggle.getAttribute('aria-expanded') === 'true' ? closeMenu() : openMenu();
  });
  
  closeButton?.addEventListener('click', () => closeMenu());
  backdrop?.addEventListener('click', () => closeMenu());
  menu?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => closeMenu({ restoreFocus: false })));

  // Keyboard Accessibility (Esc key & Tab trapping)
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && toggle?.getAttribute('aria-expanded') === 'true') {
      closeMenu();
    }
    if (event.key === 'Tab' && toggle?.getAttribute('aria-expanded') === 'true') {
      const focusable = [...menu.querySelectorAll('a[href], button:not([disabled])')];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });

  // Responsive breakpoint handling
  mobileBreakpoint.addEventListener?.('change', event => {
    if (!event.matches) closeMenu({ restoreFocus: false });
  });
  
  window.addEventListener('resize', () => {
    if (!mobileBreakpoint.matches) closeMenu({ restoreFocus: false });
  }, { passive: true });

  /* =========================================
     2. ACTIVE NAVIGATION STATE (SCROLL SPY)
     ========================================= */
  // 🚀 UPGRADE: अब यह डेस्कटॉप और मोबाइल दोनों नेविगेशन को ट्रैक करेगा
  const navLinks = [...document.querySelectorAll('.desktop-nav .nav-link, .mobile-nav a')];
  const sections = ['about', 'academics', 'facilities', 'gallery', 'notices', 'contact']
    .map(id => document.getElementById(id)).filter(Boolean);

  if ('IntersectionObserver' in window && sections.length) {
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      
      const href = `#${visible.target.id}`;
      navLinks.forEach(link => {
        const isActive = link.getAttribute('href') === href;
        link.classList.toggle('active', isActive);
        if (isActive) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      });
    }, { rootMargin: '-22% 0px -62% 0px', threshold: [0, .15, .35, .6] });
    
    sections.forEach(section => observer.observe(section));
  }

  /* =========================================
     3. FOOTER YEAR & FLASH MESSAGES
     ========================================= */
  const yearEl = document.getElementById('year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // 🚀 UPGRADE: फ्लैश मैसेज को स्मूथ तरीके से रिमूव करने के लिए एनिमेशन जोड़ा गया
  document.querySelectorAll('.flash-close').forEach(button => {
    button.addEventListener('click', () => {
      const flash = button.closest('.flash');
      if (flash) {
        flash.style.opacity = '0';
        flash.style.transform = 'translateX(100%)';
        setTimeout(() => flash.remove(), 300);
      }
    });
  });

  /* =========================================
     4. GALLERY AUTO-SLIDER (NEW FEATURE)
     ========================================= */
  // 🚀 UPGRADE: यह आपके बैकग्राउंड इमेज स्लाइडर को ऑटोमैटिकली चलाएगा
  const sliderTrack = document.getElementById('autoSlider');
  if (sliderTrack) {
    const slides = sliderTrack.querySelectorAll('.slide');
    let currentIndex = 0;
    let slideInterval;

    const startSlider = () => {
      if (slides.length <= 1) return; // अगर सिर्फ 1 इमेज है तो स्लाइड नहीं होगा
      slideInterval = setInterval(() => {
        currentIndex++;
        if (currentIndex >= slides.length) {
          currentIndex = 0; // आखिरी इमेज के बाद वापस पहली पर
        }
        sliderTrack.style.transform = `translateX(-${currentIndex * 100}%)`;
      }, 3000); // 3000ms = 3 सेकंड (स्पीड बदलने के लिए इसे बदलें)
    };

    const stopSlider = () => {
      clearInterval(slideInterval);
    };

    // स्लाइडर को शुरू करें
    startSlider();

    // 🚀 UPGRADE: जब यूज़र माउस लाए (Hover) तो स्लाइडर रुक जाए, और हटाने पर चालू हो जाए
    const sliderBox = sliderTrack.closest('.gallery-slider-box');
    if (sliderBox) {
      sliderBox.addEventListener('mouseenter', stopSlider);
      sliderBox.addEventListener('mouseleave', startSlider);
    }
  }

})();
