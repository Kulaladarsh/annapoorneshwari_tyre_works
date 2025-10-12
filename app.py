import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, url_for, session, jsonify, abort, flash, make_response, redirect, Response
from werkzeug.utils import secure_filename
import uuid
from PIL import Image
import io
import hashlib
from datetime import timedelta
import logging
from logging.handlers import RotatingFileHandler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Validate required environment variables
REQUIRED_ENV_VARS = ['SECRET_KEY', 'EMAIL_USER', 'EMAIL_PASS']
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]
if missing_vars:
    print(f"⚠️  WARNING: Missing environment variables: {', '.join(missing_vars)}")
    print("Please set these in your .env file or deployment environment")
    # Only raise in production if critical vars missing
    if os.environ.get('RENDER') and missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Create app and set secret key
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or "fallback-secret"

# Configure session for persistent login
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS

# Configure upload folder - UPDATED: More specific path
UPLOAD_FOLDER = 'static/uploads/ratings'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def compress_image(image_file, max_size=(1920, 1080), quality=85):
    """
    Compress and resize image to reduce file size while maintaining quality
    """
    try:
        # Open image
        img = Image.open(image_file)

        # Convert to RGB if necessary (for PNG with transparency)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize if larger than max_size
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Save to BytesIO with compression
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)

        return output
    except Exception as e:
        print(f"Error compressing image: {e}")
        return None

# Import database functions
from bson.objectid import ObjectId
from db import (
    update_booking_service_amount,
    update_booking_service_amounts,
    prebookings_collection,
    get_services,
    increment_visit_count,
    calculate_average_ratings,
    insert_rating,
    insert_prebooking,
    get_ratings,
    get_prebookings,
    check_user_rating_exists_for_booking,  # UPDATED: New function
    get_user_completed_bookings,
    validate_user_can_rate_service,
    delete_prebooking_by_id,
    create_indexes,
    save_payment_info,
    render_stars,
    get_admin_by_username,
    get_prebooking_by_id,
    get_payments_by_booking,
    get_total_visits,
    update_prebooking_status,
    export_bookings_to_excel,
    cleanup_expired_otps,
    get_admin_dashboard_stats,
    get_enhanced_payment_stats,
    generate_receipt_pdf,
    initialize_admin,
    get_ratings_by_service,
    get_service_by_name,
    insert_user,
    get_user_by_email,
    update_user_profile,
    get_user_by_id,
    save_manual_payment,
    get_all_payments,
    get_payment_stats,
    update_payment_status
)

import bcrypt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import io
from datetime import datetime
import time, random, re

# Initialize admin after app and db are ready
initialize_admin()


def ensure_user_session(user_id):
    """
    Ensure user session variables are properly set.
    If missing, retrieve from database and set them.
    """
    try:
        if not user_id:
            logger.warning("ensure_user_session called with empty user_id")
            return False

        # Check if session variables are already set
        if session.get('user_email') and session.get('user_name'):
            return True

        # Retrieve user data from database
        user = get_user_by_id(ObjectId(user_id))
        if not user:
            logger.error(f"User not found in database for user_id: {user_id}")
            return False

        # Set session variables
        session['user_email'] = user['email']
        session['user_name'] = user['name']
        logger.info(f"Restored session variables for user: {user['email']}")
        return True

    except Exception as e:
        logger.error(f"Error in ensure_user_session: {e}")
        return False


@app.route('/')
def home():
    increment_visit_count()
    avg_ratings = calculate_average_ratings()
    total_visits = get_total_visits()
    return render_template('index.html', avg_ratings=avg_ratings, total_visits=total_visits)


# ================= USER AUTHENTICATION ROUTES =================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')
    try:
        data = request.form
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        phone = data.get('phone', '').strip()
        password = data.get('password', '')
        confirm_password = data.get('confirm_password', '')

        if not all([name, email, phone, password, confirm_password]):
            flash('Please fill all required fields', 'danger')
            return redirect(url_for('signup'))

        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('signup'))

        # Hash password with bcrypt
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        # Handle profile photo upload
        profile_photo = None
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"user_{uuid.uuid4().hex[:8]}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                profile_photo = f"/static/uploads/ratings/{unique_filename}"

        user_data = {
            'name': name,
            'email': email,
            'phone': phone,
            'password_hash': password_hash,
            'profile_photo': profile_photo
        }

        insert_user(user_data)
        flash('Signup successful! Please login.', 'success')
        return redirect(url_for('login'))

    except Exception as e:
        flash(f"Error during signup: {str(e)}", 'danger')
        return redirect(url_for('signup'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        # User already logged in, redirect to dashboard
        return redirect(url_for('user_dashboard'))
    if request.method == 'GET':
        return render_template('login.html')
    try:
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please enter email and password', 'danger')
            return redirect(url_for('login'))

        user = get_user_by_email(email)
        if not user:
            flash('Invalid email or password', 'danger')
            return redirect(url_for('login'))

        # Verify password with bcrypt
        stored_hash = user.get('password_hash')
        if not stored_hash or not bcrypt.checkpw(password.encode(), stored_hash.encode()):
            flash('Invalid email or password', 'danger')
            return redirect(url_for('login'))

        # Generate OTP and send to user's email
        otp = str(random.randint(100000, 999999))
        session['login_otp'] = otp
        session['login_otp_time'] = time.time()
        session['login_user_id'] = str(user['_id'])
        session['login_user_email'] = user['email']
        session['login_user_name'] = user['name']

        subject = "Your OTP for Login"
        body = f"Your OTP for login is: {otp}. It will expire in 5 minutes."

        print(f"OTP for {user['email']}: {otp}")  # TEMP: Print OTP for testing
        if not send_email(user['email'], subject, body):
            flash('Failed to send OTP. Please try again.', 'danger')
            return redirect(url_for('login'))

        flash('OTP sent to your registered email. Please verify to complete login.', 'info')
        return redirect(url_for('login_otp'))

    except Exception as e:
        flash(f"Error during login: {str(e)}", 'danger')
        return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('home'))


@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))

    if request.method == 'GET':
        return render_template('change_password.html')

    try:
        user_id = session['user_id']
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not all([current_password, new_password, confirm_password]):
            flash('Please fill all fields', 'danger')
            return redirect(url_for('change_password'))

        if new_password != confirm_password:
            flash('New passwords do not match', 'danger')
            return redirect(url_for('change_password'))

        user = get_user_by_id(ObjectId(user_id))
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('login'))

        stored_hash = user.get('password_hash')
        if not stored_hash or not bcrypt.checkpw(current_password.encode(), stored_hash.encode()):
            flash('Current password is incorrect', 'danger')
            return redirect(url_for('change_password'))

        new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        update_user_profile(user['email'], {'password_hash': new_hash})

        flash('Password changed successfully', 'success')
        return redirect(url_for('user_dashboard'))

    except Exception as e:
        flash(f"Error changing password: {str(e)}", 'danger')
        return redirect(url_for('change_password'))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = get_user_by_id(ObjectId(user_id))
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('login'))

    if request.method == 'GET':
        return render_template('profile.html', user=user)

    try:
        data = request.form
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        phone = data.get('phone', '').strip()
        district = data.get('district', '').strip()
        taluk = data.get('taluk', '').strip()
        area = data.get('area', '').strip()

        # Check if email is already taken by another user
        if email != user['email']:
            existing_user = get_user_by_email(email)
            if existing_user:
                flash('Email address is already in use', 'danger')
                return redirect(url_for('profile'))

        profile_photo = user.get('profile_photo', None)
        if 'profile_photo' in request.files:
            file = request.files['profile_photo']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"user_{uuid.uuid4().hex[:8]}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                profile_photo = f"/static/uploads/ratings/{unique_filename}"

        update_data = {
            'name': name,
            'email': email,
            'phone': phone,
            'district': district,
            'taluk': taluk,
            'area': area,
            'profile_photo': profile_photo,
            'updated_at': datetime.now()
        }

        # Update session if email changed
        if email != user['email']:
            session['user_email'] = email

        update_user_profile(user['email'], update_data)
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile'))

    except Exception as e:
        flash(f"Error updating profile: {str(e)}", 'danger')
        return redirect(url_for('profile'))


@app.route('/user/dashboard')
def user_dashboard():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Ensure user session variables are properly set
    if not ensure_user_session(user_id):
        flash('Session expired. Please login again.', 'warning')
        return redirect(url_for('login'))

    user_email = session.get('user_email')
    user_name = session.get('user_name')

    # Fetch user document to get profile photo
    user = get_user_by_email(user_email)
    user_photo = user.get('profile_photo') if user else None

    # Fetch bookings linked to this user email and name with pagination
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))

        # Get filter parameters
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '').strip()
        service_filter = request.args.get('service', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        # Use the new paginated function
        from db import get_user_bookings_paginated
        bookings_result = get_user_bookings_paginated(
            user_email=user_email,
            user_name=user_name,
            page=page,
            per_page=per_page,
            search=search,
            status=status_filter,
            service=service_filter,
            start_date=start_date,
            end_date=end_date
        )

        bookings = bookings_result['bookings']

        # Add unrated_services field to completed bookings (but don't filter them out)
        for booking in bookings:
            if booking.get('status') == 'completed':
                services = booking.get('services', [])
                unrated_services = []
                if services:
                    for service in services:
                        service_name = service if isinstance(service, str) else service.get('name', '')
                        if service_name and not check_user_rating_exists_for_booking(booking.get('booking_id'), service_name):
                            unrated_services.append(service_name)
                booking['unrated_services'] = unrated_services

        # Use the original pagination from the database query
        pagination_info = {
            'total_count': bookings_result['total_count'],
            'total_pages': bookings_result['total_pages'],
            'current_page': bookings_result['current_page'],
            'per_page': bookings_result['per_page'],
            'has_next': bookings_result['has_next'],
            'has_prev': bookings_result['has_prev']
        }

    except Exception as e:
        logger.error(f"Error fetching bookings: {e}")
        bookings = []
        pagination_info = {
            'total_count': 0,
            'total_pages': 0,
            'current_page': 1,
            'per_page': 10,
            'has_next': False,
            'has_prev': False
        }

    # Check if this is an AJAX request for real-time updates
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            # Get pagination parameters
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 10))

            # Get filter parameters
            search = request.args.get('search', '').strip()
            status_filter = request.args.get('status', '').strip()
            service_filter = request.args.get('service', '').strip()
            start_date = request.args.get('start_date', '').strip()
            end_date = request.args.get('end_date', '').strip()

            # Use the new paginated function for AJAX requests too
            from db import get_user_bookings_paginated
            bookings_result = get_user_bookings_paginated(
                user_email=user_email,
                user_name=user_name,
                page=page,
                per_page=per_page,
                search=search,
                status=status_filter,
                service=service_filter,
                start_date=start_date,
                end_date=end_date
            )

            bookings_data = bookings_result['bookings']
            pagination_info = {
                'total_count': bookings_result['total_count'],
                'total_pages': bookings_result['total_pages'],
                'current_page': bookings_result['current_page'],
                'per_page': bookings_result['per_page'],
                'has_next': bookings_result['has_next'],
                'has_prev': bookings_result['has_prev']
            }

            # FIXED: Convert ObjectIds and datetime objects to strings for JSON serialization
            serialized_bookings = []
            for booking in bookings_data:
                serialized_booking = {}
                for key, value in booking.items():
                    if isinstance(value, ObjectId):
                        serialized_booking[key] = str(value)
                    elif isinstance(value, datetime):
                        serialized_booking[key] = value.isoformat()
                    elif isinstance(value, list):
                        # Handle services array (could be strings or dicts)
                        serialized_booking[key] = value
                    else:
                        serialized_booking[key] = value

                # Add unrated services for completed bookings
                if booking.get('status') == 'completed':
                    services = booking.get('services', [])
                    unrated_services = []
                    if services:
                        for service in services:
                            service_name = service if isinstance(service, str) else service.get('name', '')
                            if service_name and not check_user_rating_exists_for_booking(booking.get('booking_id'), service_name):
                                unrated_services.append(service_name)
                    serialized_booking['unrated_services'] = unrated_services
                else:
                    serialized_booking['unrated_services'] = []

                serialized_bookings.append(serialized_booking)

            return jsonify({
                'success': True,
                'total_bookings': len(serialized_bookings),
                'completed_bookings': len([b for b in serialized_bookings if b.get('status') == 'completed']),
                'pending_bookings': len([b for b in serialized_bookings if b.get('status') == 'pending']),
                'rejected_bookings': len([b for b in serialized_bookings if b.get('status') == 'rejected']),
                'bookings': serialized_bookings,
                'pagination': pagination_info
            })
        except Exception as e:
            logger.error(f"Error serializing bookings for AJAX: {e}")
            return jsonify({
                'success': False,
                'error': 'Failed to fetch bookings',
                'bookings': []
            }), 500

    return render_template('user_dashboard.html', bookings=bookings, user_name=user_name, user_photo=user_photo)


@app.route('/user/cancel-booking/<booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Ensure user session variables are properly set
    if not ensure_user_session(user_id):
        flash('Session expired. Please login again.', 'warning')
        return redirect(url_for('login'))

    user_email = session.get('user_email')
    user_name = session.get('user_name')

    # Find the booking and verify ownership
    booking = prebookings_collection.find_one({
        "booking_id": booking_id,
        "email": user_email,
        "name": {"$regex": f"^{user_name}$", "$options": "i"}
    })

    if not booking:
        flash('Booking not found', 'danger')
        return redirect(url_for('user_dashboard'))

    if booking.get('status') != 'pending':
        flash('Only pending bookings can be cancelled', 'warning')
        return redirect(url_for('user_dashboard'))

    # Update booking status to cancelled
    prebookings_collection.update_one(
        {"booking_id": booking_id},
        {"$set": {"status": "cancelled", "updated_at": datetime.now()}}
    )

    flash('Booking cancelled successfully', 'success')
    return redirect(url_for('user_dashboard'))


@app.route('/user/reschedule-booking/<booking_id>', methods=['GET', 'POST'])
def reschedule_booking(booking_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Ensure user session variables are properly set
    if not ensure_user_session(user_id):
        flash('Session expired. Please login again.', 'warning')
        return redirect(url_for('login'))

    user_email = session.get('user_email')
    user_name = session.get('user_name')

    # Find the booking and verify ownership
    booking = prebookings_collection.find_one({
        "booking_id": booking_id,
        "email": user_email,
        "name": {"$regex": f"^{user_name}$", "$options": "i"}
    })

    if not booking:
        flash('Booking not found', 'danger')
        return redirect(url_for('user_dashboard'))

    if booking.get('status') != 'pending':
        flash('Only pending bookings can be rescheduled', 'warning')
        return redirect(url_for('user_dashboard'))

    if request.method == 'GET':
        return render_template('reschedule_booking.html', booking=booking)

    try:
        new_date = request.form.get('preferred_date')
        new_time = request.form.get('time')

        if not new_date or not new_time:
            flash('Please provide both date and time', 'danger')
            return redirect(url_for('reschedule_booking', booking_id=booking_id))

        # Validate date
        try:
            date_obj = datetime.strptime(new_date, '%Y-%m-%d')
            if date_obj.date() < datetime.now().date():
                flash('Date cannot be in the past', 'danger')
                return redirect(url_for('reschedule_booking', booking_id=booking_id))
        except ValueError:
            flash('Invalid date format', 'danger')
            return redirect(url_for('reschedule_booking', booking_id=booking_id))

        # Update booking
        prebookings_collection.update_one(
            {"booking_id": booking_id},
            {"$set": {
                "preferred_date": new_date,
                "time": new_time,
                "updated_at": datetime.now()
            }}
        )

        flash('Booking rescheduled successfully', 'success')
        return redirect(url_for('user_dashboard'))

    except Exception as e:
        flash(f"Error rescheduling booking: {str(e)}", 'danger')
        return redirect(url_for('reschedule_booking', booking_id=booking_id))


# ================= EMAIL SENDER =================
def send_email(to_email, subject, body, attachment=None, attachment_name=None):
    sender_email = os.environ.get("EMAIL_USER")
    sender_password = os.environ.get("EMAIL_PASS")
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    if attachment and attachment_name:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename= {attachment_name}')
        msg.attach(part)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


# ================= OTP ROUTES =================
@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({"success": False, "error": "Email is required"}), 400

    otp = str(random.randint(100000, 999999))
    session['otp'] = otp
    session['otp_time'] = time.time()
    session['otp_verified'] = False

    subject = "Your OTP for Pre-booking"
    body = f"Your OTP is: {otp}. It will expire in 5 minutes."

    if not send_email(email, subject, body):
        return jsonify({"success": False, "error": "Failed to send OTP email"}), 500

    return jsonify({"success": True})


@app.route('/verify-otp', methods=['POST'])
def verify_otp_route():
    email = request.json.get('email')
    otp_entered = request.json.get('otp')

    if 'otp' not in session:
        return jsonify(success=False, error="OTP not sent")

    if time.time() - session['otp_time'] > 300:
        return jsonify(success=False, error="Expired OTP")

    if otp_entered == session['otp']:
        session['otp_verified'] = True
        session['user_email'] = email
        return jsonify(success=True)

    return jsonify(success=False, error="Invalid OTP")


# ================= PREBOOK ROUTE =================
@app.route('/prebook', methods=['GET', 'POST'])
def prebook():
    if request.method == 'GET':
        # Check if user is logged in
        if 'user_id' not in session:
            flash('Please login to make a booking', 'warning')
            return redirect(url_for('login'))

        # Get user data for auto-fill
        user = get_user_by_id(ObjectId(session['user_id']))
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('login'))

        return render_template('prebooking.html', user=user)

    try:
        # Check if user is logged in
        if 'user_id' not in session:
            return jsonify({"success": False, "error": "Please login to make a booking"}), 401

        if not request.is_json:
            return jsonify({"success": False, "error": "Content-Type must be application/json"}), 400

        data = request.get_json()

        # Validation
        required_fields = {
            'name': 'Full name', 'contact': 'Contact number', 'email': 'Email address',
            'area': 'Area', 'district': 'District', 'taluk': 'Taluk',
            'preferred_date': 'Preferred date', 'time': 'Preferred time',
            'services': 'Service selection'
        }
        missing_fields = [label for field, label in required_fields.items() if not data.get(field)]
        if missing_fields:
            return jsonify({"success": False, "error": f"Missing: {', '.join(missing_fields)}"}), 400

        email = data.get('email').strip()
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            return jsonify({"success": False, "error": "Invalid email"}), 400

        contact = str(data.get('contact')).strip()
        if not contact.isdigit() or not (10 <= len(contact) <= 15):
            return jsonify({"success": False, "error": "Invalid contact"}), 400

        preferred_date = data.get('preferred_date')
        try:
            date_obj = datetime.strptime(preferred_date, '%Y-%m-%d')
            if date_obj.date() < datetime.now().date():
                return jsonify({"success": False, "error": "Date cannot be in past"}), 400
        except ValueError:
            return jsonify({"success": False, "error": "Invalid date"}), 400

        services = data.get('services', [])
        if isinstance(services, str):
            services = [services]
        if not services:
            return jsonify({"success": False, "error": "Select at least one service"}), 400

        # Attach user_id to booking
        data['user_id'] = session['user_id']

        # Ensure user email and name are attached to booking
        if 'user_id' in session:
            user = get_user_by_id(ObjectId(session['user_id']))
            if user:
                data['email'] = user.get('email')
                data['name'] = user.get('name')
        else:
            data['email'] = session.get('user_email')
            data['name'] = session.get('user_name')

        session['user_name'] = data.get('name').strip()
        session['user_email'] = email

        # Amounts will be set to 0 initially and updated by admin later

        # Save booking
        booking_id = insert_prebooking(data)

        # Send confirmation email
        booking_data = get_prebooking_by_id(booking_id)
        if booking_data:
            try:
                pdf_buffer = generate_receipt_pdf(booking_data, "Booking Confirmed")
                subject = f"Booking Confirmation - {booking_id}"
                total_amount = booking_data.get('total_amount', 0)
                completed_at = booking_data.get('completed_at')
                body = f"""Dear {data.get('name')},

Your booking confirmed!

Booking ID: {booking_id}
Vehicle Number: {booking_data.get('vehicle_number', 'N/A')}
Services: {', '.join(services)}
Date: {preferred_date}
Total Amount: ₹{total_amount if total_amount > 0 else 'To be determined'}
Completed Time: {completed_at.strftime('%d-%m-%Y %H:%M') if completed_at else 'To be determined'}

Amount will be determined and communicated by our team.

Thank you!"""
                send_email(email, subject, body, pdf_buffer.getvalue(), f"receipt_{booking_id}.pdf")
            except Exception as e:
                print(f"Email error: {e}")

        return jsonify({"success": True, "booking_id": booking_id})

    except Exception as e:
        print(f"Error in prebook: {e}")
        return jsonify({"success": False, "error": "Server error"}), 500


# ================= ADMIN ROUTES =================
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'admin_logged_in' in session:
        # Admin already logged in, redirect to dashboard
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = get_admin_by_username(username)
        if admin and admin.get('password_hash') == hashlib.sha256(password.encode()).hexdigest():
            session['admin_logged_in'] = True
            # Set session as permanent for persistent login
            session.permanent = True
            return redirect(url_for('admin_dashboard'))
        flash("Invalid credentials", "danger")
        return redirect(url_for('admin'))
    return render_template('admin_login.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))

    # Check if this is an AJAX request for filtered bookings
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Get query parameters for filtering
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '').strip()
        service_filter = request.args.get('service', '').strip()
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()

        # Get filtered prebookings using the updated get_prebookings function
        prebookings = get_prebookings(
            search=search,
            status=status_filter,
            service=service_filter,
            start_date=date_from,
            end_date=date_to
        )

        # Convert ObjectIds to strings for JSON serialization
        for booking in prebookings:
            booking['_id'] = str(booking['_id'])

        return jsonify({
            'success': True,
            'prebookings': prebookings
        })

    # Regular page load
    ratings = get_ratings()
    prebookings = get_prebookings()
    stats = get_admin_dashboard_stats()
    payment_stats = get_enhanced_payment_stats()  # New enhanced payment stats

    return render_template('admin_dashboard.html',
                         ratings=ratings,
                         prebookings=prebookings,
                         total_bookings=stats['total_bookings'],
                         total_ratings=stats['total_ratings'],
                         average_rating=stats['average_rating'],
                         daily_prebookings=stats['today_bookings'],
                         total_service_amount=stats.get('total_service_amount', 0),
                         completed_bookings=stats.get('completed_bookings', 0),
                         pending_bookings=stats.get('pending_bookings', 0),
                         rejected_bookings=stats.get('rejected_bookings', 0),
                         payment_stats=payment_stats)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin'))


@app.route('/api/rating/<id>', methods=['DELETE'])
def delete_rating(id):
    if not session.get('admin_logged_in'):
        abort(401)
    from db import delete_rating_by_id
    deleted_count = delete_rating_by_id(id)
    if deleted_count == 0:
        return jsonify({"error": "Rating not found"}), 404
    return jsonify({"success": True})


@app.route('/api/prebook/<id>', methods=['GET', 'DELETE'])
def get_or_delete_prebook(id):
    if not session.get('admin_logged_in'):
        abort(401)

    if request.method == 'GET':
        booking = get_prebooking_by_id(id)
        if not booking:
            return jsonify({"error": "Prebooking not found"}), 404
        # Convert ObjectId to string for JSON serialization
        booking['_id'] = str(booking['_id'])
        return jsonify(booking)
    elif request.method == 'DELETE':
        deleted_count = delete_prebooking_by_id(id)
        if deleted_count == 0:
            return jsonify({"error": "Prebooking not found"}), 404
        return jsonify({"success": True})


@app.route('/receipt/<booking_id>')
def show_receipt(booking_id):
    booking = get_prebooking_by_id(booking_id)
    if not booking:
        return "Booking not found", 404
    payment = get_payments_by_booking(booking_id)
    return render_template("receipt.html", booking=booking, payment=payment)


@app.route('/developer')
def developer():
    # Get real stats from database
    stats = get_admin_dashboard_stats()
    avg_ratings = calculate_average_ratings()
    total_visits = get_total_visits()

    # Get recent testimonials (ratings with comments)
    recent_ratings = get_ratings()[:5]  # Get last 5 ratings

    return render_template('developer.html',
                         stats=stats,
                         avg_ratings=avg_ratings,
                         total_visits=total_visits,
                         recent_ratings=recent_ratings)

@app.route('/api/developer/contact', methods=['POST'])
def developer_contact():
    """Handle contact form submissions from developer page"""
    try:
        data = request.get_json()

        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        subject = data.get('subject', '').strip()
        message = data.get('message', '').strip()

        if not all([name, email, subject, message]):
            return jsonify({"success": False, "error": "All fields are required"}), 400

        # Send email to developer
        developer_email = "adarshkulal091@gmail.com"
        email_subject = f"Portfolio Contact: {subject}"
        email_body = f"""
New contact from portfolio website:

Name: {name}
Email: {email}
Subject: {subject}

Message:
{message}

---
Sent from portfolio contact form
"""

        if send_email(developer_email, email_subject, email_body):
            return jsonify({"success": True, "message": "Message sent successfully!"})
        else:
            return jsonify({"success": False, "error": "Failed to send message"}), 500

    except Exception as e:
        print(f"Contact form error: {e}")
        return jsonify({"success": False, "error": "Server error"}), 500

@app.route('/api/developer/stats')
def developer_stats_api():
    """API endpoint for real-time stats"""
    try:
        stats = get_admin_dashboard_stats()
        avg_ratings = calculate_average_ratings()
        total_visits = get_total_visits()

        return jsonify({
            "total_bookings": stats['total_bookings'],
            "total_ratings": stats['total_ratings'],
            "average_rating": stats['average_rating'],
            "total_visits": total_visits,
            "services": len(avg_ratings)
        })
    except Exception as e:
        return jsonify({"error": "Failed to fetch stats"}), 500


@app.route('/api/payment-stats')
def api_payment_stats():
    """API endpoint for payment statistics with date filtering"""
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "error": "Admin access required"}), 403

    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        stats = get_enhanced_payment_stats(date_from=date_from, date_to=date_to)

        return jsonify({
            "success": True,
            "stats": stats
        })

    except Exception as e:
        print(f"Error getting payment stats: {e}")
        return jsonify({"success": False, "error": "Server error"}), 500


# Also update the /api/check-booking route
@app.route('/api/check-booking')
def check_booking():
    """FIXED: Check if user has completed bookings and return booking IDs"""
    if 'user_id' not in session:
        return jsonify({'booked': False, 'bookings': []})

    user_id = session['user_id']

    # Ensure user session variables are properly set
    if not ensure_user_session(user_id):
        return jsonify({'booked': False, 'bookings': []})

    user_email = session.get('user_email')
    user_name = session.get('user_name')

    if not user_email or not user_name:
        return jsonify({'booked': False, 'bookings': []})

    # Get all completed bookings for this user
    bookings = list(prebookings_collection.find({
        "email": user_email,
        "status": "completed"
    }, {"booking_id": 1, "services": 1, "_id": 0}))

    # Format bookings with service names, filtering out already rated services
    formatted_bookings = []
    for booking in bookings:
        services = booking.get('services', [])
        service_names = []

        if services:
            if isinstance(services[0], dict):
                service_names = [s.get('name', '') for s in services]
            else:
                service_names = services

        # Filter out services that have already been rated for this booking
        filtered_services = []
        for service_name in service_names:
            if not check_user_rating_exists_for_booking(booking.get('booking_id'), service_name):
                filtered_services.append(service_name)

        # Only include booking if it has services that haven't been rated yet
        if filtered_services:
            formatted_bookings.append({
                'booking_id': booking.get('booking_id'),
                'services': filtered_services
            })

    return jsonify({
        'booked': len(formatted_bookings) > 0,
        'bookings': formatted_bookings
    })


# ================= FIXED: RATING WITH IMAGES - Enhanced validation and booking verification =================
@app.route('/api/rate-with-images', methods=['POST'])
def rate_service_with_images():
    """
    FIXED: Enhanced rating system with comprehensive validation and booking verification
    """
    try:
        if 'user_id' not in session:
            return jsonify({"success": False, "error": "Please log in first"}), 401

        user_id = session['user_id']

        # Ensure user session variables are properly set
        if not ensure_user_session(user_id):
            return jsonify({"success": False, "error": "Session expired. Please login again."}), 401

        session_email = session.get('user_email')
        session_name = session.get('user_name')

        if not session_email or not session_name:
            return jsonify({"success": False, "error": "Please log in first"}), 401

        # Get form data
        user_name = request.form.get('user_name', '').strip()
        service_name = request.form.get('service_name', '').strip()
        booking_id = request.form.get('booking_id', '').strip()
        rating = request.form.get('rating')
        comment = request.form.get('comment', '').strip()

        # Basic validation
        if not all([user_name, service_name, booking_id, rating]):
            return jsonify({"success": False, "error": "All required fields must be filled"}), 400

        # Validate rating value
        try:
            rating = int(rating)
            if not (1 <= rating <= 5):
                return jsonify({"success": False, "error": "Rating must be between 1 and 5"}), 400
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid rating value"}), 400

        # Verify user session matches
        if user_name.lower().strip() != session_name.lower().strip():
            return jsonify({"success": False, "error": "User session mismatch"}), 403

        # FIXED: Comprehensive booking verification
        # First, check if booking exists and belongs to user
        user_booking = prebookings_collection.find_one({
            "booking_id": booking_id,
            "email": session_email,
            "status": "completed"
        })

        if not user_booking:
            return jsonify({
                "success": False,
                "error": "No completed booking found with this ID"
            }), 403

        # FIXED: Verify the service was actually part of this booking
        booking_services = user_booking.get('services', [])
        service_found = False

        if isinstance(booking_services, list):
            for service in booking_services:
                if isinstance(service, dict):
                    # New format: services as dicts with 'name' field
                    if service.get('name') == service_name:
                        service_found = True
                        break
                elif isinstance(service, str):
                    # Old format: services as strings
                    if service == service_name:
                        service_found = True
                        break

        if not service_found:
            return jsonify({
                "success": False,
                "error": f"Service '{service_name}' was not part of booking {booking_id}"
            }), 403

        # FIXED: Check if user already rated this specific booking-service combination
        existing_rating = check_user_rating_exists_for_booking(booking_id, service_name)
        if existing_rating:
            return jsonify({
                "success": False,
                "error": "You have already rated this service for this booking"
            }), 400

        # FIXED: Enhanced image upload handling
        photo_urls = []
        if 'photos' in request.files:
            files = request.files.getlist('photos')

            # Limit number of images
            if len(files) > 5:
                return jsonify({"success": False, "error": "Maximum 5 images allowed"}), 400

            for file in files:
                if file and file.filename:
                    if not allowed_file(file.filename):
                        return jsonify({"success": False, "error": f"Invalid file type: {file.filename}"}), 400

                    # Generate secure unique filename
                    filename = secure_filename(file.filename)
                    unique_filename = f"{booking_id}_{service_name.replace(' ', '_')}_{uuid.uuid4().hex[:8]}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

                    try:
                        # Compress image before saving
                        compressed_image = compress_image(file)
                        if compressed_image:
                            with open(file_path, 'wb') as f:
                                f.write(compressed_image.getvalue())
                        else:
                            # Fallback to direct save if compression fails
                            file.save(file_path)

                        photo_urls.append(f"/static/uploads/ratings/{unique_filename}")

                    except Exception as img_error:
                        print(f"Image processing error: {img_error}")
                        return jsonify({"success": False, "error": "Failed to process image"}), 500

        # FIXED: Insert rating with comprehensive data
        rating_data = {
            'user_name': user_name,
            'service_name': service_name,
            'booking_id': booking_id,
            'rating': rating,
            'comment': comment if comment else None,
            'user_email': session_email,
            'photo_urls': photo_urls,
            'created_at': datetime.now(),
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')
        }

        rating_id = insert_rating(rating_data)

        # Calculate updated averages
        updated_averages = calculate_average_ratings()
        service_avg = updated_averages.get(service_name, {"average": 0, "count": 0})

        return jsonify({
            "success": True,
            "message": "Thank you for your rating!",
            "rating_id": str(rating_id),
            "updated_average": round(service_avg["average"], 1),
            "total_reviews": service_avg["count"],
            "uploaded_photos": len(photo_urls)
        })

    except Exception as e:
        print(f"Error in rate_service_with_images: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


# ================= UPDATED: SERVICE DETAIL ROUTE - Fixed "service not found" =================
@app.route('/service/<service_name>')
def service_detail(service_name):
    """
    UPDATED: Properly fetches service and displays all ratings with images
    Also checks if current user can rate (has completed booking)
    """
    try:
        # Get service details
        service = get_service_by_name(service_name)

        if not service:
            return render_template('error.html',
                                 message=f"Service '{service_name}' not found",
                                 back_url=url_for('home')), 404

        # Get all ratings for this service
        ratings = get_ratings_by_service(service_name)

        # Calculate average
        avg_ratings = calculate_average_ratings()
        service_avg = avg_ratings.get(service_name.lower().capitalize(), {"average": 0, "count": 0})

        # Check if current user can rate this service (has completed booking)
        can_rate = False
        bookings = []
        specific_booking_id = request.args.get('booking_id')

        # Only check rating capability if user is logged in
        if 'user_id' in session:
            user_id = session['user_id']

            # Ensure user session variables are properly set
            if not ensure_user_session(user_id):
                # Session expired, clear session and continue without rating capability
                session.clear()
            else:
                user_email = session.get('user_email')
                user_name = session.get('user_name')

                if user_email and user_name:
                    if specific_booking_id:
                        # Check if this specific booking has the service and is completed and unrated
                        booking = prebookings_collection.find_one({
                            "booking_id": specific_booking_id,
                            "email": user_email,
                            "name": user_name,
                            "status": "completed"
                        })
                        if booking:
                            services = booking.get('services', [])
                            service_found = False
                            if isinstance(services, list):
                                for service in services:
                                    if isinstance(service, dict):
                                        if service.get('name') == service_name:
                                            service_found = True
                                            break
                                    elif isinstance(service, str):
                                        if service == service_name:
                                            service_found = True
                                            break
                            if service_found and not check_user_rating_exists_for_booking(specific_booking_id, service_name):
                                can_rate = True
                                bookings = [booking]  # Only this booking
                    else:
                        # General check for any completed booking with this service
                        bookings = list(prebookings_collection.find({
                            "email": user_email,
                            "name": user_name,
                            "status": "completed",
                            "$or": [
                                {"services": service_name},  # old format: direct string match
                                {"services.name": service_name}  # new format: dict with name field
                            ]
                        }))
                        can_rate = len(bookings) > 0

        return render_template('service_detail.html',
                             service=service,
                             service_name=service_name,
                             ratings=ratings,
                             average_rating=service_avg['average'],
                             total_reviews=service_avg['count'],
                             can_rate=can_rate,
                             bookings=bookings)

    except Exception as e:
        print(f"Error in service_detail: {e}")
        return render_template('error.html',
                             message="Error loading service details",
                             back_url=url_for('home')), 500


# ================= OTHER API ROUTES =================
@app.route('/health')
def health_check():
    """Health check endpoint for deployment monitoring"""
    try:
        # Check database connectivity
        db_status = "connected"
        try:
            # Simple ping to check MongoDB connection
            prebookings_collection.find_one({}, {"_id": 1})
        except Exception as e:
            db_status = f"error: {str(e)}"

        return jsonify({
            "status": "healthy" if db_status == "connected" else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "database": db_status,
            "version": "1.0.0"
        }), 200 if db_status == "connected" else 503

    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }), 503


@app.route('/api/services')
def api_services():
    try:
        services = get_services()
        return jsonify({'services': services})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'services': []}), 500

@app.route('/api/average-ratings')
def average_ratings_api():
    try:
        avg_ratings = calculate_average_ratings()
        return jsonify(avg_ratings)
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({}), 500


@app.route('/api/total-visits')
def total_visits_api():
    try:
        total_visits = get_total_visits()
        return jsonify({"total_visits": total_visits})
    except Exception as e:
        return jsonify({"total_visits": 0}), 500


@app.route('/admin/update-service-amount/<booking_id>', methods=['POST'])
def update_service_amount(booking_id):
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "error": "Admin access required"}), 403

    try:
        data = request.get_json()
        service_amount = float(data.get('service_amount', 0))

        if service_amount < 0:
            return jsonify({"success": False, "error": "Amount cannot be negative"}), 400

        success = update_booking_service_amount(booking_id, service_amount)

        if success:
            total_amount = service_amount
            return jsonify({
                "success": True,
                "service_amount": service_amount,
                "total_amount": total_amount
            })
        return jsonify({"success": False, "error": "Update failed"}), 500

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "error": "Server error"}), 500


@app.route('/admin/update-individual-service-amounts/<booking_id>', methods=['POST'])
def update_individual_service_amounts(booking_id):
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "error": "Admin access required"}), 403

    try:
        data = request.get_json()
        services_data = data.get('services_data', [])

        if not services_data:
            return jsonify({"success": False, "error": "services_data is required"}), 400

        # Validate services_data format
        for service in services_data:
            if not isinstance(service, dict) or 'name' not in service or 'amount' not in service:
                return jsonify({"success": False, "error": "Each service must have 'name' and 'amount' fields"}), 400
            try:
                float(service['amount'])
            except (ValueError, TypeError):
                return jsonify({"success": False, "error": f"Invalid amount for service '{service['name']}'"}), 400

        success, result = update_booking_service_amounts(booking_id, services_data)

        if success:
            return jsonify({
                "success": True,
                "total_service_amount": result.get('total_service_amount', 0),
                "total_amount": result.get('total_amount', 0),
                "services": result.get('services', [])
            })
        return jsonify({"success": False, "error": "Update failed"}), 500

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "error": "Server error"}), 500


@app.route('/admin/complete-booking/<booking_id>', methods=['POST'])
def complete_booking(booking_id):
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "error": "Admin access required"}), 403

    try:
        booking_oid = ObjectId(booking_id)
        booking = prebookings_collection.find_one({"_id": booking_oid})

        if not booking:
            return jsonify({"success": False, "error": "Booking not found"}), 404

        # Use existing total_amount that was set by the set amount button
        total_amount = booking.get('total_amount', 0)
        completion_time = datetime.now()

        result = prebookings_collection.update_one(
            {"_id": booking_oid},
            {"$set": {
                "status": "completed",
                "completed_at": completion_time,
                "updated_at": completion_time
            }}
        )

        if result.matched_count == 0:
            return jsonify({"success": False, "error": "Booking not found"}), 404

        # Send completion email with existing amounts
        booking['status'] = "completed"
        booking['completed_at'] = completion_time

        try:
            pdf_buffer = generate_receipt_pdf(booking, "Service Completed")
            subject = f"Service Complete - {booking.get('booking_id')}"
            body = f"""Dear {booking.get('name')},

Service completed!

Booking ID: {booking.get('booking_id')}
Total: ₹{total_amount}
Completed on: {completion_time.strftime('%d-%m-%Y %H:%M')}

You can now rate our services!

Thank you!"""

            send_email(booking.get('email'), subject, body,
                      pdf_buffer.getvalue(), f"invoice_{booking.get('booking_id')}.pdf")
        except Exception as e:
            print(f"Email error: {e}")

        return jsonify({"success": True, "message": f"Completed. Total: ₹{total_amount}"})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "error": "Server error"}), 500


@app.route('/api/prebook/<booking_id>/reject', methods=['POST'])
def reject_booking(booking_id):
    if not session.get('admin_logged_in'):
        abort(401)

    booking = get_prebooking_by_id(booking_id)
    if not booking:
        return jsonify({"success": False, "error": "Booking not found"}), 404

    result = update_prebooking_status(booking_id, "rejected")
    if not result or result.modified_count == 0:
        print(f"Failed to update booking status to rejected for booking_id: {booking_id}")
        return jsonify({"success": False, "error": "Failed to update booking status"}), 500

    email = booking.get("email")
    name = booking.get("name", "Customer")
    reason = request.json.get("reason", "Booking rejected")

    subject = f"Booking Rejected - {booking_id}"
    body = f"""Dear {name},

Your booking ({booking_id}) has been rejected.

Reason: {reason}

Contact us for assistance.

Regards,
Annapoorneshwari Works"""

    # Send rejection email with PDF attachment summarizing rejection details
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        import io

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, height - 72, "Booking Rejection Notice")

        c.setFont("Helvetica", 12)
        c.drawString(72, height - 108, f"Booking ID: {booking_id}")
        c.drawString(72, height - 130, f"Customer Name: {name}")
        c.drawString(72, height - 152, f"Reason for Rejection:")
        text = c.beginText(72, height - 174)
        text.setFont("Helvetica", 12)
        for line in reason.splitlines():
            text.textLine(line)
        c.drawText(text)

        c.drawString(72, height - 220, "Please contact us for further assistance.")
        c.drawString(72, height - 250, "Regards,")
        c.drawString(72, height - 270, "Annapoorneshwari Tyre & Painting Works")

        c.showPage()
        c.save()
        buffer.seek(0)

        send_email(email, subject, body, buffer.getvalue(), f"rejection_{booking_id}.pdf")
    except Exception as e:
        print(f"Error generating or sending rejection PDF: {e}")
        send_email(email, subject, body)

    return jsonify({"success": True})


@app.route('/admin/manual-payment', methods=['POST'])
def add_manual_payment():
    """Add manual payment for a booking"""
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "error": "Admin access required"}), 403

    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['booking_id', 'amount_paid', 'payment_mode']
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return jsonify({"success": False, "error": f"Missing fields: {', '.join(missing_fields)}"}), 400

        # Verify booking exists
        booking = get_prebooking_by_id(data['booking_id'])
        if not booking:
            return jsonify({"success": False, "error": "Booking not found"}), 404

        # Add manual payment
        payment_data = {
            'booking_id': data['booking_id'],
            'amount_paid': float(data['amount_paid']),
            'payment_mode': data['payment_mode'],
            'transaction_id': data.get('transaction_id', ''),
            'payment_date': data.get('payment_date', datetime.now().strftime('%Y-%m-%d')),
            'notes': data.get('notes', '')
        }

        payment_id = save_manual_payment(payment_data)

        return jsonify({
            "success": True,
            "message": "Manual payment added successfully",
            "payment_id": payment_id
        })

    except Exception as e:
        print(f"Error adding manual payment: {e}")
        return jsonify({"success": False, "error": "Server error"}), 500


@app.route('/admin/payments', methods=['GET'])
def get_payments():
    """Get all payments with filters"""
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "error": "Admin access required"}), 403

    try:
        # Get query parameters
        payment_type = request.args.get('type')
        status = request.args.get('status')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        limit = int(request.args.get('limit', 100))

        filter_criteria = {}
        if payment_type:
            filter_criteria['payment_type'] = payment_type
        if status:
            filter_criteria['status'] = status
        if date_from and date_to:
            filter_criteria['date_from'] = date_from
            filter_criteria['date_to'] = date_to

        payments = get_all_payments(filter_criteria, limit)

        return jsonify({
            "success": True,
            "payments": payments
        })

    except Exception as e:
        print(f"Error getting payments: {e}")
        return jsonify({"success": False, "error": "Server error"}), 500


@app.route('/admin/payment-stats', methods=['GET'])
def get_payment_stats_route():
    """Get payment statistics for dashboard"""
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "error": "Admin access required"}), 403

    try:
        stats = get_payment_stats()
        return jsonify({
            "success": True,
            "stats": stats
        })

    except Exception as e:
        print(f"Error getting payment stats: {e}")
        return jsonify({"success": False, "error": "Server error"}), 500


@app.route('/admin/payment/<payment_id>/status', methods=['PUT'])
def update_payment_status_route(payment_id):
    """Update payment status"""
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "error": "Admin access required"}), 403

    try:
        data = request.get_json()
        new_status = data.get('status')

        if not new_status:
            return jsonify({"success": False, "error": "Status is required"}), 400

        success = update_payment_status(payment_id, new_status)

        if success:
            return jsonify({"success": True, "message": "Payment status updated"})
        else:
            return jsonify({"success": False, "error": "Payment not found"}), 404

    except Exception as e:
        print(f"Error updating payment status: {e}")
        return jsonify({"success": False, "error": "Server error"}), 500


@app.route('/admin/export-payments', methods=['GET'])
def export_payments():
    """Export payments data to Excel/CSV"""
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "error": "Admin access required"}), 403

    try:
        format_type = request.args.get('format', 'excel')
        payments = get_all_payments({}, 1000)  # Get up to 1000 records

        if format_type == 'csv':
            # Create CSV response
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow(['Payment ID', 'Booking ID', 'Customer Name', 'Customer Email',
                           'Amount Paid', 'Payment Mode', 'Payment Type', 'Status', 'Created At'])

            # Write data
            for payment in payments:
                writer.writerow([
                    payment.get('payment_id', ''),
                    payment.get('booking_id', ''),
                    payment.get('customer_name', ''),
                    payment.get('customer_email', ''),
                    payment.get('amount_paid', 0),
                    payment.get('payment_mode', ''),
                    payment.get('payment_type', 'online'),
                    payment.get('status', ''),
                    payment.get('created_at', '').strftime('%Y-%m-%d %H:%M:%S') if payment.get('created_at') else ''
                ])

            output.seek(0)
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment; filename=payments.csv'}
            )

        else:
            # Default to JSON for now (can be enhanced to Excel later)
            return jsonify({
                "success": True,
                "data": payments,
                "message": "Use format=csv for CSV export"
            })

    except Exception as e:
        print(f"Error exporting payments: {e}")
        return jsonify({"success": False, "error": "Server error"}), 500


@app.route('/login-otp', methods=['GET', 'POST'])
def login_otp():
    if request.method == 'GET':
        return render_template('login_otp.html')

    try:
        otp_entered = request.form.get('otp', '').strip()

        if 'login_otp' not in session or 'login_otp_time' not in session:
            flash('OTP session expired. Please login again.', 'danger')
            return redirect(url_for('login'))

        if time.time() - session['login_otp_time'] > 300:
            flash('OTP expired. Please login again.', 'danger')
            return redirect(url_for('login'))

        if otp_entered == session['login_otp']:
            # OTP verified, finalize login
            session['user_id'] = session.pop('login_user_id')
            session['user_email'] = session.pop('login_user_email')
            session['user_name'] = session.pop('login_user_name')
            session.pop('login_otp')
            session.pop('login_otp_time')

            # Set session as permanent for persistent login
            session.permanent = True

            flash('Login successful!', 'success')
            return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid OTP. Please try again.', 'danger')
            return redirect(url_for('login_otp'))

    except Exception as e:
        flash(f"Error during OTP verification: {str(e)}", 'danger')
        return redirect(url_for('login_otp'))

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
