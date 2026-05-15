// Home Dashboard JavaScript

document.addEventListener('DOMContentLoaded', function() {
 
    const currentPath = window.location.pathname;
    const navItems = document.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        const href = item.getAttribute('href');
        if (href === currentPath) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
 
    const sidebar = document.getElementById('sidebar');

    const composeToggles = document.querySelectorAll('[data-compose-toggle]');

    composeToggles.forEach(toggle => {
        const panel = document.getElementById(toggle.dataset.composeToggle);
        if (!panel) {
            return;
        }

        toggle.addEventListener('click', () => {
            const isOpening = panel.hasAttribute('hidden');
            panel.toggleAttribute('hidden', !isOpening);
            toggle.setAttribute('aria-expanded', String(isOpening));

            if (isOpening) {
                const firstInput = panel.querySelector('input:not([type="hidden"]), textarea, select');
                if (firstInput) {
                    firstInput.focus();
                }
            }
        });
    });

});
