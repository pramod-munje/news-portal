document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const header = document.querySelector('header');
    const menuToggle = document.querySelector('.menu-toggle');
    const nav = document.querySelector('nav');
    const searchInput = document.querySelector('.search-input');
    const articleCards = document.querySelectorAll('.articles-grid .news-card');
    const featuredCard = document.querySelector('.featured-card');
    const sidebarItems = document.querySelectorAll('.sidebar-item');
    const navItems = document.querySelectorAll('.nav-item');
    const sectionTitle = document.querySelector('.section-title');
    const noResults = document.getElementById('search-no-results');
    const backToTop = document.querySelector('.back-to-top');
    const totalArticlesEl = document.getElementById('total-articles-count');

    let currentCategory = 'all';
    let searchQuery = '';

    // Mobile Menu Toggle
    if (menuToggle && nav) {
        menuToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            nav.classList.toggle('open');
            // Toggle hamburger / close icon if text/icon is used
            const icon = menuToggle.querySelector('i');
            if (icon) {
                if (nav.classList.contains('open')) {
                    icon.className = 'fas fa-times';
                } else {
                    icon.className = 'fas fa-bars';
                }
            }
        });

        // Close mobile menu when clicking outside
        document.addEventListener('click', (e) => {
            if (nav.classList.contains('open') && !nav.contains(e.target) && !menuToggle.contains(e.target)) {
                nav.classList.remove('open');
                const icon = menuToggle.querySelector('i');
                if (icon) icon.className = 'fas fa-bars';
            }
        });
    }

    // Scroll Effects: Sticky Header shadow/glow & Back to Top button
    window.addEventListener('scroll', () => {
        if (window.scrollY > 30) {
            header.style.boxShadow = '0 10px 30px rgba(0, 0, 0, 0.5), 0 1px 0 rgba(255, 255, 255, 0.05)';
            header.style.background = 'rgba(11, 12, 16, 0.85)';
        } else {
            header.style.boxShadow = 'none';
            header.style.background = 'rgba(11, 12, 16, 0.7)';
        }

        if (window.scrollY > 400) {
            backToTop.classList.add('visible');
        } else {
            backToTop.classList.remove('visible');
        }
    });

    // Handle Category Filters via Navigation Items
    navItems.forEach(item => {
        const link = item.querySelector('a');
        if (!link) return;

        link.addEventListener('click', (e) => {
            const targetCategory = item.getAttribute('data-category');
            if (!targetCategory) return; // e.g., 'About' which might scroll to footer or be an external link

            e.preventDefault();

            // Close mobile menu if open
            if (nav.classList.contains('open')) {
                nav.classList.remove('open');
                const icon = menuToggle.querySelector('i');
                if (icon) icon.className = 'fas fa-bars';
            }

            // Scroll to the main articles section smoothly
            const mainSection = document.getElementById('news-feed');
            if (mainSection) {
                const headerOffset = header.offsetHeight + 20;
                const elementPosition = mainSection.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
            }

            // Update active state
            navItems.forEach(ni => ni.classList.remove('active'));
            item.classList.add('active');

            // Apply category filter
            currentCategory = targetCategory;
            filterArticles();
        });
    });

    // Handle Real-Time Search Input
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            searchQuery = e.target.value.toLowerCase().trim();
            filterArticles();
        });
    }

    // Core Filtering Logic (Category + Search Query)
    function filterArticles() {
        let visibleCount = 0;

        // 1. Process Grid Articles
        articleCards.forEach(card => {
            const title = card.querySelector('.card-title').textContent.toLowerCase();
            const description = card.querySelector('.card-description').textContent.toLowerCase();
            const category = card.getAttribute('data-category').toLowerCase();
            const source = card.querySelector('.meta-source').textContent.toLowerCase();
            
            const matchesCategory = (currentCategory === 'all' || category === currentCategory);
            const matchesSearch = !searchQuery || 
                                  title.includes(searchQuery) || 
                                  description.includes(searchQuery) || 
                                  category.includes(searchQuery) ||
                                  source.includes(searchQuery);

            if (matchesCategory && matchesSearch) {
                card.style.display = 'flex';
                // Add fade-in transition effect
                card.style.animation = 'fadeIn 0.4s ease-out forwards';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });

        // 2. Process Hero Featured Card (only show if category is 'all' and matches search, or matches specific category & search)
        if (featuredCard) {
            const fTitle = featuredCard.querySelector('.card-title').textContent.toLowerCase();
            const fDesc = featuredCard.querySelector('.card-description').textContent.toLowerCase();
            const fCategory = featuredCard.getAttribute('data-category').toLowerCase();
            const fSource = featuredCard.querySelector('.meta-source').textContent.toLowerCase();
            
            const fMatchesCategory = (currentCategory === 'all' || fCategory === currentCategory);
            const fMatchesSearch = !searchQuery || 
                                   fTitle.includes(searchQuery) || 
                                   fDesc.includes(searchQuery) || 
                                   fCategory.includes(searchQuery) ||
                                   fSource.includes(searchQuery);

            if (fMatchesCategory && fMatchesSearch) {
                featuredCard.style.display = 'flex';
                featuredCard.style.animation = 'fadeIn 0.4s ease-out forwards';
                visibleCount++;
            } else {
                featuredCard.style.display = 'none';
            }
        }

        // 3. Process Sidebar Items (filter them as well so page elements feel consistent)
        sidebarItems.forEach(item => {
            const title = item.querySelector('.sidebar-item-title').textContent.toLowerCase();
            const category = item.getAttribute('data-category').toLowerCase();
            const source = item.querySelector('.sidebar-item-meta').textContent.toLowerCase();

            const matchesCategory = (currentCategory === 'all' || category === currentCategory);
            const matchesSearch = !searchQuery || 
                                  title.includes(searchQuery) || 
                                  category.includes(searchQuery) ||
                                  source.includes(searchQuery);

            if (matchesCategory && matchesSearch) {
                item.style.display = 'flex';
                visibleCount++;
            } else {
                item.style.display = 'none';
            }
        });

        // 4. Update Header Titles based on selected filter
        if (sectionTitle) {
            if (currentCategory === 'all') {
                sectionTitle.textContent = searchQuery ? 'Search Results' : 'Latest News Feed';
            } else {
                // Capitalize category name
                const displayCatName = currentCategory.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
                sectionTitle.textContent = `${displayCatName} Feed`;
            }
        }

        // 5. Update Footer count dynamically for currently visible articles
        if (totalArticlesEl) {
            totalArticlesEl.textContent = `${visibleCount} articles visible`;
        }

        // 6. Handle "No Results" display
        if (noResults) {
            if (visibleCount === 0) {
                noResults.style.display = 'block';
            } else {
                noResults.style.display = 'none';
            }
        }
    }

    // Lazy Image Loading (Visual polish & Performance)
    const images = document.querySelectorAll('img[loading="lazy"]');
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const image = entry.target;
                    image.src = image.src; // Trigger load (fallback source is already in src, this ensures correct load order)
                    imageObserver.unobserve(image);
                }
            });
        });
        images.forEach(image => imageObserver.observe(image));
    }
});
