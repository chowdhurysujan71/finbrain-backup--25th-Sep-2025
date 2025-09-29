/**
 * Profile V2 - Google/Stripe Grade Interactive Features
 * Handles progressive enhancement, skeleton loading, and live data updates
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Profile V2 JS loaded');
    
    // Progressive enhancement - show live data sections
    const liveDataElements = document.querySelectorAll('.live-data');
    liveDataElements.forEach(element => {
        element.classList.add('show');
    });
    
    // Goal progress ring animation
    const progressRings = document.querySelectorAll('.progress-ring circle[stroke-dasharray]');
    progressRings.forEach(ring => {
        // Animate the stroke-dasharray for smooth progress loading
        const finalDashArray = ring.getAttribute('stroke-dasharray');
        ring.style.strokeDasharray = '0 314';
        
        setTimeout(() => {
            ring.style.transition = 'stroke-dasharray 1s ease-out';
            ring.style.strokeDasharray = finalDashArray;
        }, 300);
    });
    
    // Quick action hover effects and analytics
    const quickActions = document.querySelectorAll('.quick-action');
    quickActions.forEach(action => {
        action.addEventListener('click', function(e) {
            const actionType = this.getAttribute('data-action') || 'unknown';
            console.log(`Profile V2 action clicked: ${actionType}`);
            
            // Add click animation
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
        });
    });
    
    // Enhanced skeleton loading states
    const skeletonElements = document.querySelectorAll('.skeleton');
    if (skeletonElements.length > 0) {
        // Simulate data loading completion
        setTimeout(() => {
            skeletonElements.forEach(skeleton => {
                skeleton.style.opacity = '0';
                setTimeout(() => {
                    skeleton.style.display = 'none';
                }, 300);
            });
        }, 2000);
    }
    
    // Add intersection observer for smooth animations
    if ('IntersectionObserver' in window) {
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }
            });
        }, observerOptions);
        
        // Observe all cards for staggered animation
        const cards = document.querySelectorAll('.card, .quick-action');
        cards.forEach((card, index) => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            card.style.transition = `opacity 0.6s ease ${index * 0.1}s, transform 0.6s ease ${index * 0.1}s`;
            observer.observe(card);
        });
    }
});

// Export for potential use by other modules
window.ProfileV2 = {
    version: '2.0.0',
    initialized: true
};