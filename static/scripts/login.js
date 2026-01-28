// LOGIN PAGE JAVA - A WORK IN PROGRESS

document.addEventListener('DOMContentLoaded', function() {
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