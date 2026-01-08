    // Initialize Leaflet Map
    var map = L.map('map').setView([10.131965114373727, 124.83455240938477], 18);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Custom icon for terminal
    var terminalIcon = L.divIcon({
      html: '<i class="bi bi-geo-alt-fill" style="font-size: 2rem; color: #1a365d;"></i>',
      iconSize: [30, 30],
      className: 'terminal-marker'
    });

    L.marker([10.131965114373727, 124.83455240938477], {icon: terminalIcon})
      .addTo(map)
      .bindPopup('<b>Maasin City Integrated Terminal</b><br>Main Transportation Hub<br>📍 Southern Leyte, Philippines')
      .openPopup();

    // Add a circle for visual enhancement
    L.circle([10.131965114373727, 124.83455240938477], {
      color: '#1a365d',
      fillColor: '#1a365d',
      fillOpacity: 0.1,
      radius: 80
    }).addTo(map);

    // Scroll Animation Functionality (Stripe-like)
    document.addEventListener('DOMContentLoaded', function() {
      // Add animation classes to elements
      const animatedElements = document.querySelectorAll('.animate-on-scroll');
      
      // Function to check if element is in viewport
      function isElementInViewport(el) {
        const rect = el.getBoundingClientRect();
        return (
          rect.top <= (window.innerHeight || document.documentElement.clientHeight) * 0.85 &&
          rect.bottom >= 0
        );
      }

      // Function to handle scroll animations
      function handleScrollAnimations() {
        animatedElements.forEach(el => {
          if (isElementInViewport(el)) {
            el.classList.add('visible');
          }
        });
        
        // Facility cards stagger animation
        const facilityCards = document.querySelectorAll('.facility-card');
        facilityCards.forEach((card, index) => {
          if (isElementInViewport(card)) {
            setTimeout(() => {
              card.classList.add('visible');
            }, index * 150); // Stagger effect
          }
        });
      }

      // Initial check
      handleScrollAnimations();

      // Add scroll event listener with throttle
      let ticking = false;
      window.addEventListener('scroll', function() {
        if (!ticking) {
          window.requestAnimationFrame(function() {
            handleScrollAnimations();
            ticking = false;
          });
          ticking = true;
        }
      });

      // Image hover effects
      const announcementImage = document.querySelector('.announcement-image-content');
      if (announcementImage) {
        announcementImage.addEventListener('mouseenter', () => {
          announcementImage.style.transform = 'perspective(1000px) rotateY(0deg)';
        });
        
        announcementImage.addEventListener('mouseleave', () => {
          announcementImage.style.transform = 'perspective(1000px) rotateY(-10deg)';
        });
      }

      // Info card hover effects
      const infoCards = document.querySelectorAll('.info-card');
      infoCards.forEach(card => {
        card.addEventListener('mouseenter', () => {
          card.style.transform = 'translateY(-5px)';
        });
        
        card.addEventListener('mouseleave', () => {
          card.style.transform = 'translateY(0)';
        });
      });
    });

    // Mobile menu toggle (if included in header)
    document.addEventListener('DOMContentLoaded', function() {
      const toggle = document.querySelector('.menu-toggle');
      const menu = document.querySelector('.nav-menu');

      if (toggle && menu) {
        toggle.addEventListener('click', () => {
          menu.classList.toggle('active');
        });

        // Close menu when clicking outside
        document.addEventListener('click', e => {
          if (!menu.contains(e.target) && !toggle.contains(e.target)) {
            menu.classList.remove('active');
          }
        });
      }
    });