(() => {
  'use strict';

  /* =========================================
     0. UTILITY HELPERS
     ========================================= */
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function debounce(fn, wait = 150) {
    let t;
    return function (...args) {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), wait);
    };
  }

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
     NEW UPGRADE: STICKY HEADER SCROLL EFFECT
     ========================================= */
  const siteHeader = document.querySelector('.site-header');
  if (siteHeader) {
    window.addEventListener('scroll', throttle(() => {
      if (window.scrollY > 50) {
        siteHeader.classList.add('scrolled');
      } else {
        siteHeader.classList.remove('scrolled');
      }
    }, 100), { passive: true });
  }

  /* =========================================
     1. MOBILE MENU LOGIC (Public Site)
     ========================================= */
  const toggle = document.getElementById('menuToggle');
  const menu = document.getElementById('mobileMenu');
  const backdrop = document.getElementById('menuBackdrop');
  const closeButton = document.getElementById('menuClose');
  
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
        setTimeout(() => backdrop.classList.add('is-open'), 10);
    }
    document.body.classList.add('menu-open');
    requestAnimationFrame(() => closeButton?.focus());
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
    }, 300); 
    
    document.body.classList.remove('menu-open');
    document.documentElement.style.overflow = '';
    if (restoreFocus && lastFocused instanceof HTMLElement) {
      lastFocused.focus({ preventScroll: true });
    }
  }

  toggle?.addEventListener('click', () => {
    toggle.getAttribute('aria-expanded') === 'true' ? closeMenu() : openMenu();
  });
  closeButton?.addEventListener('click', () => closeMenu());
  backdrop?.addEventListener('click', () => closeMenu());
  menu?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => closeMenu({ restoreFocus: false })));

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
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first.focus();
      }
    }
  });

  mobileBreakpoint.addEventListener?.('change', event => {
    if (!event.matches) closeMenu({ restoreFocus: false });
  });
  
  window.addEventListener('resize', debounce(() => {
    if (!mobileBreakpoint.matches && menu?.classList.contains('is-open')) {
        closeMenu({ restoreFocus: false });
    }
  }, 150), { passive: true });


  /* =========================================
     NEW UPGRADE: DASHBOARD SIDEBAR TOGGLE
     ========================================= */
  const dashSidebar = document.getElementById('dashSidebar');
  const dashToggle = document.getElementById('dashMenuToggle');
  const dashBackdrop = document.getElementById('dashBackdrop');

  if (dashSidebar && dashToggle) {
    function openDashSidebar() {
      dashSidebar.classList.add('open');
      if (dashBackdrop) {
        dashBackdrop.hidden = false;
        setTimeout(() => dashBackdrop.classList.add('show'), 10);
      }
      dashToggle.setAttribute('aria-expanded', 'true');
      document.body.classList.add('dash-sidebar-open');
    }

    function closeDashSidebar() {
      dashSidebar.classList.remove('open');
      if (dashBackdrop) {
        dashBackdrop.classList.remove('show');
        setTimeout(() => { dashBackdrop.hidden = true; }, 300);
      }
      dashToggle.setAttribute('aria-expanded', 'false');
      document.body.classList.remove('dash-sidebar-open');
    }

    dashToggle.addEventListener('click', () => {
      dashSidebar.classList.contains('open') ? closeDashSidebar() : openDashSidebar();
    });

    dashBackdrop?.addEventListener('click', closeDashSidebar);

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && dashSidebar.classList.contains('open')) closeDashSidebar();
    });

    dashSidebar.querySelectorAll('a[href^="#"]').forEach(link => {
      link.addEventListener('click', () => {
        if (window.innerWidth <= 1024) closeDashSidebar();
      });
    });

    window.addEventListener('resize', () => {
      if (window.innerWidth > 1024) closeDashSidebar();
    });
  }


  /* =========================================
     NEW UPGRADE: ADMIN SIDEBAR TOGGLE & COLLAPSE
     ========================================= */
  const adminSidebar = document.getElementById('adminSidebar');
  const adminMenuToggle = document.getElementById('adminMenuToggle');
  const adminBackdrop = document.getElementById('adminBackdrop');
  const collapseBtn = document.getElementById('sidebarCollapseBtn');

  // Mobile Toggle
  if (adminMenuToggle && adminSidebar) {
    function openAdminSidebar() {
      adminSidebar.classList.add('open');
      if (adminBackdrop) { adminBackdrop.hidden = false; adminBackdrop.classList.add('open'); }
      adminMenuToggle.setAttribute('aria-expanded', 'true');
      document.body.classList.add('menu-open');
    }
    function closeAdminSidebar() {
      adminSidebar.classList.remove('open');
      if (adminBackdrop) { adminBackdrop.classList.remove('open'); setTimeout(() => { adminBackdrop.hidden = true; }, 300); }
      adminMenuToggle.setAttribute('aria-expanded', 'false');
      document.body.classList.remove('menu-open');
    }
    adminMenuToggle.addEventListener('click', (e) => {
      e.preventDefault();
      adminSidebar.classList.contains('open') ? closeAdminSidebar() : openAdminSidebar();
    });
    adminBackdrop?.addEventListener('click', closeAdminSidebar);
  }

  // Desktop Collapse
  if (collapseBtn && adminSidebar) {
    if (window.innerWidth > 900 && localStorage.getItem('adminSidebarCollapsed') === 'true') {
      adminSidebar.classList.add('collapsed');
      document.body.classList.add('admin-sidebar-collapsed');
      const icon = collapseBtn.querySelector('i');
      if (icon) icon.className = 'fa-solid fa-angles-right';
    }
    collapseBtn.addEventListener('click', function () {
      adminSidebar.classList.toggle('collapsed');
      const isCollapsed = adminSidebar.classList.contains('collapsed');
      document.body.classList.toggle('admin-sidebar-collapsed', isCollapsed);
      localStorage.setItem('adminSidebarCollapsed', isCollapsed ? 'true' : 'false');
      const icon = this.querySelector('i');
      if (icon) icon.className = isCollapsed ? 'fa-solid fa-angles-right' : 'fa-solid fa-angles-left';
    });
  }

  // Sidebar Live Search Filter (Admin)
  const sidebarSearch = document.getElementById('sidebarSearch');
  if (sidebarSearch) {
    sidebarSearch.addEventListener('input', function () {
      const q = this.value.toLowerCase().trim();
      const links = document.querySelectorAll('.admin-nav-link');
      links.forEach(link => {
        const label = (link.getAttribute('data-label') || link.textContent).toLowerCase();
        link.style.display = (!q || label.includes(q)) ? '' : 'none';
      });
      document.querySelectorAll('.admin-nav-group-label').forEach(label => {
        let next = label.nextElementSibling;
        let hasVisible = false;
        while (next && !next.classList.contains('admin-nav-group-label')) {
          if (next.classList.contains('admin-nav-link') && next.style.display !== 'none') {
            hasVisible = true; break;
          }
          next = next.nextElementSibling;
        }
        label.style.display = (!q || hasVisible) ? '' : 'none';
      });
    });
  }


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
      if (prefersReducedMotion) return;
      clearInterval(slideInterval);
      slideInterval = setInterval(() => {
        currentIndex++;
        if (currentIndex >= slides.length) currentIndex = 0; 
        sliderTrack.style.transform = `translateX(-${currentIndex * 100}%)`;
      }, 3000);
    };

    const stopSlider = () => clearInterval(slideInterval);

    const goToSlide = (i) => {
      if (!slides.length) return;
      currentIndex = ((i % slides.length) + slides.length) % slides.length;
      sliderTrack.style.transform = `translateX(-${currentIndex * 100}%)`;
      const dots = document.querySelectorAll('.gallery-slider-dots button, .slider-dot');
      dots.forEach((d, idx) => {
        d.classList.toggle('active', idx === currentIndex);
        d.setAttribute('aria-selected', idx === currentIndex ? 'true' : 'false');
      });
    };

    startSlider();

    const sliderBox = sliderTrack.closest('.gallery-slider-box');
    if (sliderBox) {
      sliderBox.addEventListener('mouseenter', stopSlider);
      sliderBox.addEventListener('mouseleave', startSlider);
      sliderBox.addEventListener('focusin', stopSlider);
      sliderBox.addEventListener('focusout', startSlider);
    }

    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stopSlider();
      else startSlider();
    });

    if ('IntersectionObserver' in window && sliderBox) {
      const sliderVisibilityObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) startSlider();
          else stopSlider();
        });
      }, { threshold: 0.1 });
      sliderVisibilityObserver.observe(sliderBox);
    }

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
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) {
        if (dx < 0) goToSlide(currentIndex + 1);
        else        goToSlide(currentIndex - 1);
      }
      startSlider();
    }, { passive: true });

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

    const dots = document.querySelectorAll('.gallery-slider-dots button, .slider-dot');
    dots.forEach((dot, idx) => {
      dot.addEventListener('click', () => {
        stopSlider(); goToSlide(idx); startSlider();
      });
    });

    if (prefersReducedMotion) stopSlider();
  }

  /* =========================================
     5. SMOOTH SCROLL FOR IN-PAGE ANCHORS
     ========================================= */
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
      if (history.replaceState) history.replaceState(null, '', href);
    });
  });

})();

/* ============================================================
   DROPDOWNS: USER PROFILE & ADMIN NOTIFICATIONS
   ============================================================ */
(function initDropdowns() {
    // ---- User Profile Dropdown ----
    const userProfile  = document.getElementById('userProfile');
    const userMenuBtn  = document.getElementById('userMenuBtn');
    const userDropdown = document.getElementById('userDropdown');

    if (userProfile && userMenuBtn && userDropdown) {
        function openUserMenu() {
            userProfile.classList.add('dropdown-open');
            userMenuBtn.setAttribute('aria-expanded', 'true');
        }
        function closeUserMenu() {
            userProfile.classList.remove('dropdown-open');
            userMenuBtn.setAttribute('aria-expanded', 'false');
        }
        function toggleUserMenu(e) {
            e.preventDefault(); e.stopPropagation();
            userProfile.classList.contains('dropdown-open') ? closeUserMenu() : openUserMenu();
        }

        userMenuBtn.addEventListener('click', toggleUserMenu);
        userDropdown.addEventListener('click', e => e.stopPropagation());
        
        document.addEventListener('click', e => {
            if (userProfile.classList.contains('dropdown-open') && !userProfile.contains(e.target)) closeUserMenu();
        });
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape' && userProfile.classList.contains('dropdown-open')) {
                closeUserMenu(); userMenuBtn.focus();
            }
        });
        document.addEventListener('touchstart', e => {
            if (userProfile.classList.contains('dropdown-open') && !userProfile.contains(e.target)) closeUserMenu();
        }, { passive: true });

        userDropdown.addEventListener('keydown', function (e) {
            const items = [...userDropdown.querySelectorAll('a[href], button:not([disabled])')];
            if (!items.length) return;
            const idx = items.indexOf(document.activeElement);
            if (e.key === 'ArrowDown') { e.preventDefault(); items[(idx + 1 + items.length) % items.length].focus(); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); items[(idx - 1 + items.length) % items.length].focus(); }
            else if (e.key === 'Home') { e.preventDefault(); items[0].focus(); }
            else if (e.key === 'End') { e.preventDefault(); items[items.length - 1].focus(); }
        });

        userMenuBtn.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
                e.preventDefault();
                if (!userProfile.classList.contains('dropdown-open')) openUserMenu();
                requestAnimationFrame(() => {
                    const first = userDropdown.querySelector('a[href], button:not([disabled])');
                    first?.focus();
                });
            }
        });

        userDropdown.querySelectorAll('a[href]').forEach(link => link.addEventListener('click', closeUserMenu));
        userDropdown.querySelectorAll('a[href^="#"]').forEach(link => link.addEventListener('click', () => setTimeout(closeUserMenu, 50)));
    }

    // ---- Admin Notification Dropdown ----
    const notifWrapper = document.getElementById('adminNotifWrapper');
    const notifBtn = document.getElementById('adminNotifBtn');
    const notifDropdown = document.getElementById('adminNotifDropdown');

    if (notifWrapper && notifBtn && notifDropdown) {
        function openNotif() { notifWrapper.classList.add('dropdown-open'); notifBtn.setAttribute('aria-expanded', 'true'); }
        function closeNotif() { notifWrapper.classList.remove('dropdown-open'); notifBtn.setAttribute('aria-expanded', 'false'); }
        
        notifBtn.addEventListener('click', function (e) {
            e.preventDefault(); e.stopPropagation();
            const isOpen = notifWrapper.classList.contains('dropdown-open');
            // Close user menu if open
            if (userProfile && userProfile.classList.contains('dropdown-open')) {
                userProfile.classList.remove('dropdown-open');
            }
            if (!isOpen) openNotif(); else closeNotif();
        });

        notifDropdown.addEventListener('click', e => e.stopPropagation());
        document.addEventListener('click', e => {
            if (notifWrapper.classList.contains('dropdown-open') && !notifWrapper.contains(e.target)) closeNotif();
        });
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape' && notifWrapper.classList.contains('dropdown-open')) {
                closeNotif(); notifBtn.focus();
            }
        });
    }
})();