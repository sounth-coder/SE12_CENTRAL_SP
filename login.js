// LOGIN PAGE JAVA - A WORK IN PROGRESS

document.addEventListener('DOMContentLoaded', function() {
    var images = [
        'https://media.istockphoto.com/id/944812540/photo/mountain-landscape-ponta-delgada-island-azores.jpg?s=612x612&w=0&k=20&c=mbS8X4gtJki3gGDjfC0sG3rsz7D0nls53a0b4OPXLnE=',
        'https://media.gettyimages.com/id/2240394251/video/blue-quantum-technology-abstract-backgrounds-4k-resolution.jpg?s=640x640&k=20&c=H_233aCrOwoWpafgyq_cYJWZvnXTUVBJE_B4ppQ26_0=',
        'https://t4.ftcdn.net/jpg/08/31/13/63/360_F_831136313_Rf5tZbaz6vPpWsa4EOXkP7FB8vsalocf.jpg',
        'https://deih43ym53wif.cloudfront.net/kuta-bali-beach-indonesia-shutterstock_297303287.jpg_9b516347e5.jpg',
        'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS-Jh-j2bRc6EjlZzs-EUNvVpLD_8FBKsnLBg&s',
        'https://image.slidesdocs.com/responsive-images/background/airplane-depicted-during-its-takeoff-or-landing-on-the-runway-in-a-3d-rendering-at-the-airport-powerpoint-background_6890e63763__960_540.jpg',
        'https://thumbs.dreamstime.com/b/airplane-flying-above-clouds-sunrise-transportation-air-travel-plane-decoration-wallpaper-desktop-poster-booklet-cover-357264759.jpg',
        'https://thumbs.dreamstime.com/b/night-landscape-colorful-milky-way-yellow-light-mountains-starry-sky-hills-summer-beautiful-universe-space-72956059.jpg'
    ];

    var randomIndex = Math.floor(Math.random() * images.length);

    const bg = document.querySelector('.background-image');
    bg.style.backgroundImage = `url(${images[randomIndex]})`;

    const loginForm = document.getElementById('loginForm');
    const forgotPasswordForm = document.getElementById('forgotPasswordForm');
    const forgotPasswordBtn = document.getElementById('forgotPasswordBtn');
    const cancelBtn = document.getElementById('cancelBtn');
    const formTitle = document.getElementById('formTitle');
    const formSubtitle = document.getElementById('formSubtitle');
    
    // TOGGLE TO FORGET 
    forgotPasswordBtn.addEventListener('click', function() {
        loginForm.style.display = 'none';
        forgotPasswordForm.style.display = 'block';
        formTitle.textContent = 'Reset Password';
        formSubtitle.textContent = 'Enter your email to receive reset instructions';
    });
    
    // TOGGLE TO LOGIN
    cancelBtn.addEventListener('click', function() {
        forgotPasswordForm.style.display = 'none';
        loginForm.style.display = 'block';
        formTitle.textContent = 'Welcome Back';
        formSubtitle.textContent = 'Girra Student Portal';
    });
    
    // STILL NEEDS WORK - FORGOT PASSWORD SUBMISSION
    forgotPasswordForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const email = document.getElementById('email').value;
        
        try {
            const response = await fetch('/api/forgot-password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email })
            });
            
            const data = await response.json();
            
            if (data.success) {
                alert(data.message);
                // SWITCH TO LOGIN
                cancelBtn.click();
            }
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred. Please try again.');
        }
    });
});