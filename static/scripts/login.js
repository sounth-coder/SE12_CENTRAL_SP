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
    const forgotPasswordSubmit = document.getElementById('forgotPasswordSubmit');
    const forgotPasswordMessage = document.getElementById('forgotPasswordMessage');
    const securityQuestionsFields = document.getElementById('securityQuestionsFields');
    const newPasswordFields = document.getElementById('newPasswordFields');
    const csrfToken = document.getElementById('forgotCsrfToken').value;
    let resetStep = 'questions';
    let loadedQuestions = [];

    function showForgotMessage(message, type) {
        forgotPasswordMessage.textContent = message;
        forgotPasswordMessage.className = `form-alert form-alert-${type}`;
        forgotPasswordMessage.style.display = 'block';
    }

    function clearForgotMessage() {
        forgotPasswordMessage.textContent = '';
        forgotPasswordMessage.style.display = 'none';
    }

    function resetForgotPasswordForm() {
        resetStep = 'questions';
        loadedQuestions = [];
        forgotPasswordForm.reset();
        securityQuestionsFields.innerHTML = '';
        securityQuestionsFields.style.display = 'none';
        newPasswordFields.style.display = 'none';
        document.getElementById('email').readOnly = false;
        forgotPasswordSubmit.textContent = 'Continue';
        clearForgotMessage();
    }
    
    // TOGGLE TO FORGET 
    forgotPasswordBtn.addEventListener('click', function() {
        loginForm.style.display = 'none';
        forgotPasswordForm.style.display = 'block';
        formTitle.textContent = 'Reset Password';
        formSubtitle.textContent = 'Use your security questions to reset your password';
    });
    
    // TOGGLE TO LOGIN
    cancelBtn.addEventListener('click', function() {
        resetForgotPasswordForm();
        forgotPasswordForm.style.display = 'none';
        loginForm.style.display = 'block';
        formTitle.textContent = 'Welcome Back';
        formSubtitle.textContent = 'Girra Student Portal';
    });
    
    forgotPasswordForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const email = document.getElementById('email').value;
        const payload = { email, action: resetStep };

        if (resetStep === 'reset') {
            payload.answers = {};
            loadedQuestions.forEach(function(question) {
                const answerInput = document.getElementById(`security_answer_${question.key}`);
                payload.answers[question.key] = answerInput ? answerInput.value : '';
            });
            payload.new_password = document.getElementById('newPassword').value;
            payload.confirm_password = document.getElementById('confirmNewPassword').value;
        }
        
        try {
            clearForgotMessage();
            forgotPasswordSubmit.disabled = true;
            const response = await fetch('/api/forgot-password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify(payload)
            });
            
            const data = await response.json();
            
            if (!response.ok || !data.success) {
                showForgotMessage(data.message || 'Password reset failed. Please try again.', 'error');
                return;
            }

            if (resetStep === 'questions') {
                loadedQuestions = data.questions || [];
                securityQuestionsFields.innerHTML = '';
                loadedQuestions.forEach(function(question) {
                    const group = document.createElement('div');
                    const label = document.createElement('label');
                    const input = document.createElement('input');

                    group.className = 'form-group';
                    label.setAttribute('for', `security_answer_${question.key}`);
                    label.textContent = question.text;
                    input.type = 'text';
                    input.id = `security_answer_${question.key}`;
                    input.className = 'form-input';
                    input.autocomplete = 'off';
                    input.required = true;

                    group.appendChild(label);
                    group.appendChild(input);
                    securityQuestionsFields.appendChild(group);
                });
                securityQuestionsFields.style.display = 'block';
                newPasswordFields.style.display = 'block';
                document.getElementById('email').readOnly = true;
                forgotPasswordSubmit.textContent = 'Reset Password';
                resetStep = 'reset';
                showForgotMessage('Answer your security questions and choose a new password.', 'info');
                return;
            }

            if (resetStep === 'reset') {
                alert(data.message);
                cancelBtn.click();
            }
        } catch (error) {
            console.error('Error:', error);
            showForgotMessage('An error occurred. Please try again.', 'error');
        } finally {
            forgotPasswordSubmit.disabled = false;
        }
    });
});
