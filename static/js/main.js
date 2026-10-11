(() => {
  'use strict';

  /* =========================================
     1. MOBILE MENU LOGIC (ROBUST FIX)
     ========================================= */
  const toggle = document.getElementById('menuToggle');
  const menu = document.getElementById('mobileMenu');
  const backdrop = document.getElementById('menuBackdrop');
  const closeButton = document.getElementById('menuClose');
  
  // 🚀 UPGRADE: matchMedia की शर्त हटा दी गई है ताकि बटन क्लिक करने पर मेनू 100% खुले।
  // CSS पहले से ही बटन को सिर्फ मोबाइल पर दिखाता है, इसलिए JS में इसकी जरूरत नहीं है।
  const mobileBreakpoint = window.matchMedia('(max-width: 1280px)');
  let lastFocused = null;

  function openMenu() {
    if (!menu || !toggle) return;
    lastFocused = document.activeElement;
    menu.classList.add('is-open');
    menu.removeAttribute('inert');
    menu.setAttribute('aria-hidden', 'false');
    toggle.setAttribute('aria-expanded', 'true');
    toggle.setAttribute('aria-label', 'Close navigation menu');
    if (backdrop) {
        backdrop.hidden = false;
        // Small delay to ensure the transition works perfectly
        setTimeout(() => backdrop.classList.add('is-open'), 10);
    }
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
    
    backdrop.classList.remove('is-open');
    setTimeout(() => {
        backdrop.hidden = true;
    }, 300); // Wait for transition to finish
    
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
  
  // ✅ Backdrop Click Close Feature (बाहर क्लिक करने पर बंद होना)
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

  // Responsive breakpoint handling (Close menu if resized to desktop)
  mobileBreakpoint.addEventListener?.('change', event => {
    if (!event.matches) closeMenu({ restoreFocus: false });
  });
  
  window.addEventListener('resize', () => {
    if (!mobileBreakpoint.matches && menu.classList.contains('is-open')) {
        closeMenu({ restoreFocus: false });
    }
  }, { passive: true });


  /* =========================================
     2. ACTIVE NAVIGATION STATE (SCROLL SPY)
     ========================================= */
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

  // Smooth removal of flash messages
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
     4. GALLERY AUTO-SLIDER
     ========================================= */
  const sliderTrack = document.getElementById('autoSlider');
  if (sliderTrack) {
    const slides = sliderTrack.querySelectorAll('.slide');
    let currentIndex = 0;
    let slideInterval;

    const startSlider = () => {
      if (slides.length <= 1) return; 
      slideInterval = setInterval(() => {
        currentIndex++;
        if (currentIndex >= slides.length) {
          currentIndex = 0; 
        }
        sliderTrack.style.transform = `translateX(-${currentIndex * 100}%)`;
      }, 3000); // 3 seconds
    };

    const stopSlider = () => {
      clearInterval(slideInterval);
    };

    // Start the slider
    startSlider();

    // Pause on hover, resume on mouse leave
    const sliderBox = sliderTrack.closest('.gallery-slider-box');
    if (sliderBox) {
      sliderBox.addEventListener('mouseenter', stopSlider);
      sliderBox.addEventListener('mouseleave', startSlider);
    }
  }

})();