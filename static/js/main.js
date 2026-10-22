(() => {
  'use strict';

  /* =========================================
     0. UTILITY HELPERS (NEW — do not affect existing logic)
     ========================================= */
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Debounce — prevents rapid-fire calls (used for resize)
  function debounce(fn, wait = 150) {
    let t;
    return function (...args) {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), wait);
    };
  }

  // Throttle — limits calls to once per interval (used for scroll-based work)
  function throttle(fn, wait = 100) {
    let last = 0, timer;
    return function (...args) {
      const now = Date.now();
      const remaining = wait - (now - last);
      if (remaining <= 0) {
        clearTimeout(timer);
        timer = null;
        last = now;
        fn.apply(this, args);
      } else if (!timer) {
        timer = setTimeout(() => {
          last = Date.now();
          timer = null;
          fn.apply(this, args);
        }, remaining);
      }
    };
  }

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
    /* === IMPROVED: prevent body scroll for a cleaner overlay === */
    document.documentElement.style.overflow = 'hidden';
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
    /* === IMPROVED: restore document scroll === */
    document.documentElement.style.overflow = '';
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
  
  /* === IMPROVED: debounce resize so it doesn't fire on every pixel === */
  window.addEventListener('resize', debounce(() => {
    if (!mobileBreakpoint.matches && menu?.classList.contains('is-open')) {
        closeMenu({ restoreFocus: false });
    }
  }, 150), { passive: true });


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

  /* === IMPROVED: auto-dismiss flash messages after 6s (optional UX boost) === */
  document.querySelectorAll('.flash').forEach(flash => {
    if (flash.dataset.autoDismiss === 'false') return;
    setTimeout(() => {
      if (!flash.isConnected) return;
      flash.style.opacity = '0';
      flash.style.transform = 'translateX(100%)';
      setTimeout(() => flash.remove(), 300);
    }, 6000);
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
      /* === IMPROVED: respect reduced-motion preference === */
      if (prefersReducedMotion) return;
      /* === IMPROVED: avoid stacking intervals if called twice === */
      clearInterval(slideInterval);
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

    /* === IMPROVED: helper to jump to a specific index (used by dots/swipe/keyboard) === */
    const goToSlide = (i) => {
      if (!slides.length) return;
      currentIndex = ((i % slides.length) + slides.length) % slides.length;
      sliderTrack.style.transform = `translateX(-${currentIndex * 100}%)`;
      /* === IMPROVED: keep dot indicators in sync if they exist === */
      const dots = document.querySelectorAll('.gallery-slider-dots button, .slider-dot');
      dots.forEach((d, idx) => {
        d.classList.toggle('active', idx === currentIndex);
        d.setAttribute('aria-selected', idx === currentIndex ? 'true' : 'false');
      });
    };

    // Start the slider
    startSlider();

    // Pause on hover, resume on mouse leave
    const sliderBox = sliderTrack.closest('.gallery-slider-box');
    if (sliderBox) {
      sliderBox.addEventListener('mouseenter', stopSlider);
      sliderBox.addEventListener('mouseleave', startSlider);
      /* === IMPROVED: pause on focus-within too (keyboard users) === */
      sliderBox.addEventListener('focusin', stopSlider);
      sliderBox.addEventListener('focusout', startSlider);
    }

    /* === IMPROVED: pause when the tab is hidden (saves CPU/battery) === */
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stopSlider();
      else startSlider();
    });

    /* === IMPROVED: pause when the slider is off-screen (scroll out of view) === */
    if ('IntersectionObserver' in window && sliderBox) {
      const sliderVisibilityObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) startSlider();
          else stopSlider();
        });
      }, { threshold: 0.1 });
      sliderVisibilityObserver.observe(sliderBox);
    }

    /* === IMPROVED: swipe support on touch devices === */
    let sx = 0, sy = 0, swiping = false;
    sliderTrack.addEventListener('touchstart', (e) => {
      if (!e.touches[0]) return;
      sx = e.touches[0].clientX;
      sy = e.touches[0].clientY;
      swiping = true;
      stopSlider();
    }, { passive: true });

    sliderTrack.addEventListener('touchend', (e) => {
      if (!swiping) return;
      swiping = false;
      const t = e.changedTouches[0];
      if (!t) { startSlider(); return; }
      const dx = t.clientX - sx;
      const dy = t.clientY - sy;
      /* Only treat as horizontal swipe if horizontal movement dominates */
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) {
        if (dx < 0) goToSlide(currentIndex + 1);   // swipe left  → next
        else        goToSlide(currentIndex - 1);   // swipe right → prev
      }
      startSlider();
    }, { passive: true });

    /* === IMPROVED: keyboard navigation (← → arrows) when slider has focus === */
    sliderTrack.setAttribute('tabindex', '0');
    sliderTrack.setAttribute('role', 'region');
    sliderTrack.setAttribute('aria-roledescription', 'carousel');
    sliderTrack.setAttribute('aria-label', 'Gallery slideshow — use arrow keys to navigate');
    sliderTrack.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft')  { e.preventDefault(); stopSlider(); goToSlide(currentIndex - 1); }
      if (e.key === 'ArrowRight') { e.preventDefault(); stopSlider(); goToSlide(currentIndex + 1); }
      if (e.key === 'Home')       { e.preventDefault(); goToSlide(0); }
      if (e.key === 'End')        { e.preventDefault(); goToSlide(slides.length - 1); }
    });

    /* === IMPROVED: dot navigation wiring (if dots exist) === */
    const dots = document.querySelectorAll('.gallery-slider-dots button, .slider-dot');
    dots.forEach((dot, idx) => {
      dot.addEventListener('click', () => {
        stopSlider();
        goToSlide(idx);
        startSlider();
      });
    });

    /* === IMPROVED: pause slider when user prefers reduced motion === */
    if (prefersReducedMotion) stopSlider();
  }

  /* === IMPROVED: smooth scroll for in-page anchor links (#hash) === */
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const href = this.getAttribute('href');
      if (!href || href === '#' || href.length < 2) return;
      const target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();
      const topBar = document.querySelector('.site-header');
      const offset = topBar ? topBar.offsetHeight + 12 : 12;
      const top = target.getBoundingClientRect().top + window.pageYOffset - offset;
      window.scrollTo({ top, behavior: prefersReducedMotion ? 'auto' : 'smooth' });
      /* Update URL without jumping */
      if (history.replaceState) history.replaceState(null, '', href);
    });
  });

})();

/* ============================================================
   USER PROFILE DROPDOWN — Click to pin, click-outside to close
   ============================================================ */
(function initUserDropdown() {
    const userProfile  = document.getElementById('userProfile');
    const userMenuBtn  = document.getElementById('userMenuBtn');
    const userDropdown = document.getElementById('userDropdown');

    if (!userProfile || !userMenuBtn || !userDropdown) return;

    function openMenu() {
        userProfile.classList.add('dropdown-open');
        userMenuBtn.setAttribute('aria-expanded', 'true');
    }

    function closeMenu() {
        userProfile.classList.remove('dropdown-open');
        userMenuBtn.setAttribute('aria-expanded', 'false');
    }

    function toggleMenu(e) {
        e.preventDefault();
        e.stopPropagation();
        if (userProfile.classList.contains('dropdown-open')) {
            closeMenu();
        } else {
            openMenu();
        }
    }

    // Click on button → toggle pin
    userMenuBtn.addEventListener('click', toggleMenu);

    // Click inside dropdown → don't close (link will navigate)
    userDropdown.addEventListener('click', function (e) {
        e.stopPropagation();
    });

    // Click anywhere outside → close
    document.addEventListener('click', function (e) {
        if (userProfile.classList.contains('dropdown-open') &&
            !userProfile.contains(e.target)) {
            closeMenu();
        }
    });

    // ESC key → close
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && userProfile.classList.contains('dropdown-open')) {
            closeMenu();
            userMenuBtn.focus();
        }
    });

    // Touch devices: tap outside to close
    document.addEventListener('touchstart', function (e) {
        if (userProfile.classList.contains('dropdown-open') &&
            !userProfile.contains(e.target)) {
            closeMenu();
        }
    }, { passive: true });

    /* === IMPROVED: keyboard navigation inside dropdown (↑ ↓ Home End) === */
    userDropdown.addEventListener('keydown', function (e) {
        const items = [...userDropdown.querySelectorAll('a[href], button:not([disabled])')];
        if (!items.length) return;
        const idx = items.indexOf(document.activeElement);
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            items[(idx + 1 + items.length) % items.length].focus();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            items[(idx - 1 + items.length) % items.length].focus();
        } else if (e.key === 'Home') {
            e.preventDefault();
            items[0].focus();
        } else if (e.key === 'End') {
            e.preventDefault();
            items[items.length - 1].focus();
        }
    });

    /* === IMPROVED: focus first item when dropdown opens via keyboard === */
    userMenuBtn.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
            e.preventDefault();
            if (!userProfile.classList.contains('dropdown-open')) openMenu();
            requestAnimationFrame(() => {
                const first = userDropdown.querySelector('a[href], button:not([disabled])');
                first?.focus();
            });
        }
    });

    /* === IMPROVED: close on any navigation link click inside dropdown === */
    userDropdown.querySelectorAll('a[href]').forEach(link => {
        link.addEventListener('click', () => closeMenu());
    });

    /* === IMPROVED: close on hash-link navigation for consistency === */
    userDropdown.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener('click', () => {
            setTimeout(closeMenu, 50);
        });
    });
})();