import os
from dotenv import load_dotenv
from flask import Flask
from flask import Flask, render_template, request, url_for, session, jsonify, abort, flash, make_response, redirect

# Load environment variables
load_dotenv()

# Create app and set secret key
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or "fallback-secret"

# Now import everything else
from bson.objectid import ObjectId
from db import (
    prebookings_collection,
    get_services,
    increment_visit_count,
    calculate_average_ratings,
    insert_rating,
    insert_prebooking,
    get_ratings,
    get_prebookings,
    check_user_rating_exists,
    get_user_completed_bookings,
    get_user_rated_services,
    validate_user_can_rate_service,
    delete_prebooking_by_id,
    create_indexes,
    save_payment_info,
    render_stars,
    generate_otp,
    verify_otp,
    save_payment_info,
    get_admin_by_username,
    check_user_rating_exists,
    get_prebooking_by_id,
    get_payments_by_booking,
    get_total_visits,
    update_prebooking_status,
    export_bookings_to_excel,
    cleanup_expired_otps,
    get_admin_dashboard_stats,
    generate_receipt_pdf,
    initialize_admin
)

import hashlib
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


@app.route('/')
def home():
    increment_visit_count()
    avg_ratings = calculate_average_ratings()
    total_visits = get_total_visits()
    return render_template('index.html', avg_ratings=avg_ratings, total_visits=total_visits)

# =================== Email Sender ===================
from flask import Flask, request, jsonify, session, render_template
import time, random, re
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

# ================= EMAIL SENDER =================
def send_email(to_email, subject, body, attachment=None, attachment_name=None):
    sender_email = os.environ.get("EMAIL_USER")
    sender_password = os.environ.get("EMAIL_PASS")
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # Add attachment if provided
    if attachment and attachment_name:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment)
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename= {attachment_name}'
        )
        msg.attach(part)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully")
        return True
    except Exception as e:
        print("Error sending email:", e)
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

    print(f"✅ OTP generated for {email}: {otp}")
    return jsonify({"success": True})

@app.route('/verify-otp', methods=['POST'])
def verify_otp_route():
    email = request.json.get('email')
    otp_entered = request.json.get('otp')

    if 'otp' not in session:
        return jsonify(success=False, error="OTP not sent")

    if time.time() - session['otp_time'] > 300:  # 5 minutes expiry
        return jsonify(success=False, error="Expired OTP")

    if otp_entered == session['otp']:
        session['otp_verified'] = True
        # Set user session for rating eligibility
        session['user_email'] = email
        return jsonify(success=True)

    return jsonify(success=False, error="Invalid OTP")

# ================= PREBOOK ROUTE =================
@app.route('/prebook', methods=['GET', 'POST'])
def prebook():
    if request.method == 'GET':
        return render_template('prebooking.html')

    try:
        if not session.get('otp_verified'):
            return jsonify({"success": False, "error": "Invalid or expired OTP. Please request a new OTP."}), 400

        if not request.is_json:
            return jsonify({"success": False, "error": "Content-Type must be application/json"}), 400

        data = request.get_json()

        # Required field validation
        required_fields = {
            'name': 'Full name',
            'contact': 'Contact number',
            'email': 'Email address',
            'area': 'Area',
            'district': 'District',
            'taluk': 'Taluk',
            'preferred_date': 'Preferred date',
            'time': 'Preferred time',
            'services': 'Service selection',
            'vehicle_type': 'Vehicle type',
            'vehicle_details': 'Vehicle details',
            'upi_number': 'UPI number',
            'upi_ref': 'UPI reference ID'
        }
        missing_fields = [label for field, label in required_fields.items() if not data.get(field)]
        if missing_fields:
            return jsonify({"success": False, "error": f"Please fill in all required fields: {', '.join(missing_fields)}"}), 400

        # Email validation
        email = data.get('email').strip()
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            return jsonify({"success": False, "error": "Invalid email address"}), 400

        # Contact validation
        contact = str(data.get('contact')).strip()
        if not contact.isdigit() or not (10 <= len(contact) <= 15):
            return jsonify({"success": False, "error": "Invalid contact number"}), 400

        # Date validation
        preferred_date = data.get('preferred_date')
        try:
            date_obj = datetime.strptime(preferred_date, '%Y-%m-%d')
            if date_obj.date() < datetime.now().date():
                return jsonify({"success": False, "error": "Preferred date cannot be in the past"}), 400
        except ValueError:
            return jsonify({"success": False, "error": "Invalid date format"}), 400

        # Time validation
        try:
            datetime.strptime(data.get('time'), '%H:%M')
        except ValueError:
            return jsonify({"success": False, "error": "Invalid time format"}), 400

        # UPI format check
        upi_number = data.get("upi_number", "").strip()
        if not re.match(r'^[\w.-]+@[\w.-]+$', upi_number):
            return jsonify({"success": False, "error": "Invalid UPI ID"}), 400

        # UPI reference check
        upi_ref = data.get("upi_ref", "").strip()
        if not (8 <= len(upi_ref) <= 30):
            return jsonify({"success": False, "error": "UPI reference ID must be 8-30 characters"}), 400

        # Services validation
        services = data.get('services', [])
        if isinstance(services, str):
            services = [services]
        if not services:
            return jsonify({"success": False, "error": "Please select at least one service"}), 400

        # Payment validation
        payment_info = data.get("payment_info", {})
        if int(payment_info.get("amount", 0)) != 20:
            return jsonify({"success": False, "error": "₹20 UPI payment is required"}), 400
        if payment_info.get("ref") != upi_ref:
            return jsonify({"success": False, "error": "UPI reference ID mismatch"}), 400

        # Set user session data for ratings
        session['user_name'] = data.get('name').strip()
        session['user_email'] = email

        # ====== DB Save Logic (Your existing functions) ======
        booking_id = insert_prebooking(data)
        save_payment_info({
            "booking_id": booking_id,
            "amount": payment_info.get("amount", 0),
            "ref": upi_ref,
            "upi_number": upi_number,
            "status": "completed"
        })

        # Generate and send initial booking confirmation receipt
        booking_data = get_prebooking_by_id(booking_id)
        if booking_data:
            try:
                pdf_buffer = generate_receipt_pdf(booking_data, "Booking Confirmed")
                subject = f"Booking Confirmation - {booking_id}"
                body = f"""Dear {data.get('name')},

Your booking has been confirmed successfully!

Booking Details:
- Booking ID: {booking_id}
- Services: {', '.join(services)}
- Date: {preferred_date}
- Time: {data.get('time')}
- Amount Paid: ₹{payment_info.get('amount', 20)}

Your service will be completed soon and you'll receive a final receipt via email.

Thank you for choosing Annapoorneshwari Tyre & Painting Works!

Best regards,
Annapoorneshwari Team"""
                
                send_email(email, subject, body, pdf_buffer.getvalue(), f"booking_receipt_{booking_id}.pdf")
            except Exception as e:
                print(f"Error sending booking confirmation email: {e}")

        return jsonify({"success": True, "booking_id": booking_id, "message": "Pre-booking confirmed successfully!"})

    except Exception as e:
        print(f"❌ Error in prebook: {e}")
        return jsonify({"success": False, "error": "Unexpected error"}), 500

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        print("Admin login POST request received")  # Debug print
        username = request.form.get('username')
        password = request.form.get('password')
        print(f"Username: {username}, Password: {'*' * len(password) if password else None}")  # Debug print
        admin = get_admin_by_username(username)
        if admin and admin.get('password_hash') == hashlib.sha256(password.encode()).hexdigest():
            print("Admin authenticated successfully")  # Debug print
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            print("Admin authentication failed")  # Debug print
            flash("Invalid credentials", "danger")
            return redirect(url_for('admin'))
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    ratings = get_ratings()
    prebookings = get_prebookings()
    
    # Get dashboard statistics including total service amount
    stats = get_admin_dashboard_stats()
    
    return render_template('admin_dashboard.html', 
                         ratings=ratings, 
                         prebookings=prebookings,
                         total_bookings=stats['total_bookings'],
                         average_rating=stats['average_rating'],
                         daily_prebookings=stats['today_bookings'],
                         total_service_amount=stats.get('total_service_amount', 0),
                         completed_bookings=stats.get('completed_bookings', 0),
                         pending_bookings=stats.get('pending_bookings', 0))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin'))

@app.route('/api/rating/<id>', methods=['DELETE'])
def delete_rating(id):
    if not session.get('admin_logged_in'):
        abort(401)
    from db import delete_rating_by_id  # Import the function we'll add to db.py
    deleted_count = delete_rating_by_id(id)
    if deleted_count == 0:
        return jsonify({"error": "Rating not found"}), 404
    return jsonify({"success": True})

@app.route('/api/prebook/<id>', methods=['DELETE'])
def delete_prebook(id):
    if not session.get('admin_logged_in'):
        abort(401)
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
    return render_template('developer.html')

# ================= FIXED RATING ROUTES =================

@app.route('/api/check-booking')
def check_booking():
    """
    Check if user has any completed bookings.
    Returns { booked: true } only if at least one booking exists with status "completed".
    """
    user_email = session.get('user_email')
    user_name = session.get('user_name')
    
    if not user_email or not user_name:
        return jsonify({'booked': False})

    # Check for at least one completed booking
    booking_exists = prebookings_collection.find_one({
        "email": user_email,
        "name": user_name,
        "status": "completed"
    })

    return jsonify({'booked': bool(booking_exists)})

@app.route('/api/rate', methods=['POST'])
def rate_service():
    """
    Fixed rating logic:
    1. User must be logged in via session
    2. Must have a completed booking for the specific service
    3. Can only rate once per service (even if multiple bookings exist)
    4. Validates all input data
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        # Get form data with proper null handling
        user_name = (data.get('user_name') or '').strip()
        service_name = (data.get('service_name') or '').strip()
        rating = data.get('rating')
        comment = (data.get('comment') or '').strip()

        # Validate required fields
        if not user_name or not service_name or not rating:
            return jsonify({"success": False, "error": "Please fill all required fields"}), 400

        # Validate rating value
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                return jsonify({"success": False, "error": "Rating must be between 1 and 5"}), 400
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Invalid rating value"}), 400

        # Check if user is logged in via session
        session_email = session.get('user_email')
        session_name = session.get('user_name')
        
        if not session_email or not session_name:
            return jsonify({"success": False, "error": "Please log in by completing a booking first"}), 401

        # Verify that the submitted name matches session name (security check)
        if user_name.lower().strip() != session_name.lower().strip():
            return jsonify({"success": False, "error": "Name mismatch. Please use your registered name"}), 403

        # Check if user has a completed booking for this specific service
        completed_booking = prebookings_collection.find_one({
            "email": session_email,
            "name": {"$regex": f"^{user_name}$", "$options": "i"},  # Case insensitive
            "services": service_name,
            "status": "completed"
        })

        if not completed_booking:
            return jsonify({
                "success": False, 
                "error": f"You must have a completed booking for '{service_name}' to rate this service"
            }), 403

        # Check if user has already rated this service (prevent duplicate ratings)
        existing_rating = check_user_rating_exists(user_name, service_name)
        if existing_rating:
            return jsonify({
                "success": False, 
                "error": f"You have already rated '{service_name}'. Only one rating per service is allowed"
            }), 400

        # Insert the rating
        rating_data = {
            'user_name': user_name,
            'service_name': service_name,
            'rating': rating,
            'comment': comment if comment else None,
            'user_email': session_email,  # Store for reference
            'booking_id': completed_booking.get('booking_id'),  # Link to booking
            'created_at': datetime.now()
        }

        rating_id = insert_rating(rating_data)
        
        print(f"✅ Rating submitted successfully: {rating_id}")
        return jsonify({
            "success": True, 
            "message": f"Thank you for rating '{service_name}'!",
            "rating_id": str(rating_id)
        })

    except Exception as e:
        print(f"❌ Error in rate_service: {str(e)}")
        return jsonify({
            "success": False, 
            "error": "Internal server error. Please try again later."
        }), 500

@app.route('/admin/complete-booking/<booking_id>', methods=['POST'])
def complete_booking(booking_id):
    """
    Admin route to mark a booking as completed.
    Updates the booking status to "completed" and sends final receipt.
    """
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "error": "Admin access required"}), 403

    try:
        booking_oid = ObjectId(booking_id)
    except Exception:
        return jsonify({"success": False, "error": "Invalid booking ID"}), 400

    try:
        # Get booking details before updating
        booking = prebookings_collection.find_one({"_id": booking_oid})
        if not booking:
            return jsonify({"success": False, "error": "Booking not found"}), 404

        # Update booking status
        result = prebookings_collection.update_one(
            {"_id": booking_oid},
            {"$set": {
                "status": "completed",
                "updated_at": datetime.now()
            }}
        )

        if result.matched_count == 0:
            return jsonify({"success": False, "error": "Booking not found"}), 404

        if result.modified_count == 0:
            return jsonify({"success": False, "error": "Booking status already completed"}), 200

        # Generate and send final service completion receipt
        try:
            pdf_buffer = generate_receipt_pdf(booking, "Service Completed")
            subject = f"Service Completion Receipt - {booking.get('booking_id')}"
            body = f"""Dear {booking.get('name')},

Your service has been completed successfully!

Service Details:
- Booking ID: {booking.get('booking_id')}
- Services: {', '.join(booking.get('services', []))}
- Date: {booking.get('preferred_date')}
- Status: Completed

Thank you for choosing Annapoorneshwari Tyre & Painting Works!
You can now rate our services on our website.

Best regards,
Annapoorneshwari Team"""
            
            send_email(
                booking.get('email'), 
                subject, 
                body, 
                pdf_buffer.getvalue(), 
                f"service_completion_{booking.get('booking_id')}.pdf"
            )
            print(f"✅ Service completion receipt sent to {booking.get('email')}")
        except Exception as e:
            print(f"Error sending service completion email: {e}")

        return jsonify({
            "success": True,
            "message": "Booking marked as completed successfully"
        })

    except Exception as e:
        print(f"❌ Error completing booking: {e}")
        return jsonify({"success": False, "error": "Failed to update booking status"}), 500

# ================= RECEIPT DOWNLOAD ROUTE =================
@app.route('/download-receipt/<booking_id>')
def download_receipt(booking_id):
    """Download receipt as PDF"""
    booking = get_prebooking_by_id(booking_id)
    if not booking:
        return "Booking not found", 404
    
    try:
        pdf_buffer = generate_receipt_pdf(booking, "Service Receipt")
        response = make_response(pdf_buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=receipt_{booking_id}.pdf'
        return response
    except Exception as e:
        print(f"Error generating PDF receipt: {e}")
        return "Error generating receipt", 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)