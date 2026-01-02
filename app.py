from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
from datetime import timedelta

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

# SECRET KEY FOR SESSIONS
app.secret_key = 'girraween-student-portal-2026-secret-key'
app.permanent_session_lifetime = timedelta(hours=2)

@app.route('/')
def index():
    """Landing page"""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember')
        
        # FOR DEMO - ACCEPT ANY USERNAME/PASSWORD - WILL UPDATE IT LATER ONCE SQL IS COMPLETE. 
        if username and password:
            session.permanent = bool(remember)
            session['username'] = username
            session['logged_in'] = True
            return redirect(url_for('home'))
    
    return render_template('login.html')

@app.route('/home')
def home():
    """Home dashboard - requires login"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    username = session.get('username', 'Student')
    return render_template('home.html', username=username)

@app.route('/student-id')
def student_id():
    """Student ID page"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    username = session.get('username', 'Student')
    return render_template('student_id.html', username=username)

@app.route('/resources')
def resources():
    """Resources page"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('resources.html')

@app.route('/help')
def help_centre():
    """Help Centre page"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('help.html')

@app.route('/announcements')
def announcements():
    """Announcements page"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('announcements.html')

@app.route('/news')
def news():
    """Girra News page"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('news.html')

@app.route('/prefects')
def prefects():
    """Prefects page"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('prefects.html')

@app.route('/humans')
def humans():
    """Humans of Girra page"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('humans.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    """Handle forgot password request"""
    email = request.json.get('email')
    # Mock response
    return jsonify({'success': True, 'message': 'Password reset link sent to your school email!'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

#LOCAL FLASK OPERATION SCRIPT
#if __name__ == "__main__":
#    app.run(debug=True)


