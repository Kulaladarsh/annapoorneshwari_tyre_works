
import os
from pymongo import MongoClient


from bson.objectid import ObjectId
from datetime import datetime, date, timedelta
import uuid
import random
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import io

# MongoDB connection
uri = os.environ.get("MONGO_URI")
client = MongoClient(uri)


# Access DB & collections
db = client['annapoorneshwari_tyre_works']
services_collection = db['services']
ratings_collection = db['get_ratings']
prebookings_collection = db['prebookings']
admin_collection = db['admins']
otp_collection = db['otps']
painting_limits_collection = db['painting_limits']
payments_collection = db['payments']

# Create indexes for better performance
def create_indexes():
    """Create database indexes if they don't exist"""
    try:
        # Check if ratings index exists
        existing_indexes = ratings_collection.list_indexes()
        rating_index_exists = any(
            idx.get('name') == 'service_name_1_user_name_1' 
            for idx in existing_indexes
        )
        
        if not rating_index_exists:
            ratings_collection.create_index([("service_name", 1), ("user_name", 1)], unique=True)
            print("Created ratings index")
        
        # Create other indexes if needed (non-unique, so less likely to conflict)
        prebookings_collection.create_index([("email", 1), ("preferred_date", 1)])
        otp_collection.create_index([("email", 1), ("expires_at", 1)])
        
    except Exception as e:
        # Silently handle index creation - not critical for functionality
        pass

# Call index creation
create_indexes()

# ==================== SERVICES ====================
def get_services():
    return list(services_collection.find({}, {"_id": 0}))

# ==================== RATINGS ====================
def check_user_rating_exists(user_name, service_name):
    """
    Check if user has already rated a specific service.
    Returns True if rating exists, False otherwise.
    """
    try:
        # Case-insensitive search for user name
        count = ratings_collection.count_documents({
            "user_name": {"$regex": f"^{user_name}$", "$options": "i"},
            "service_name": service_name
        })
        return count > 0
    except Exception as e:
        print(f"Error checking user rating exists: {e}")
        return False

def insert_rating(rating_data):
    """
    Insert a new rating with proper validation and duplicate prevention.
    """
    try:
        # Check for duplicate rating before inserting
        existing = ratings_collection.find_one({
            "user_name": {"$regex": f"^{rating_data['user_name']}$", "$options": "i"},
            "service_name": rating_data['service_name']
        })
        
        if existing:
            raise ValueError("User has already rated this service")
        
        # Set creation timestamp
        rating_data['created_at'] = datetime.now()
        
        # Insert the rating
        result = ratings_collection.insert_one(rating_data)
        return result.inserted_id
        
    except Exception as e:
        print(f"Error inserting rating: {e}")
        raise

def get_ratings():
    """
    Get all ratings from the database.
    Returns a list of all ratings with proper formatting.
    """
    try:
        ratings = list(ratings_collection.find().sort("created_at", -1))
        # Convert ObjectId to string for JSON serialization
        for rating in ratings:
            rating['_id'] = str(rating['_id'])
        return ratings
    except Exception as e:
        print(f"Error getting ratings: {e}")
        return []

def calculate_average_ratings():
    """
    Calculate average ratings for all services with proper error handling.
    """
    try:
        pipeline = [
            {
                "$group": {
                    "_id": "$service_name",
                    "average": {"$avg": "$rating"},
                    "count": {"$sum": 1}
                }
            }
        ]
        results = list(ratings_collection.aggregate(pipeline))
        
        avg_ratings = {}
        for item in results:
            service_name = item['_id']
            avg_ratings[service_name] = {
                'average': round(item['average'], 1),
                'count': item['count']
            }
        
        return avg_ratings
        
    except Exception as e:
        print(f"Error calculating average ratings: {e}")
        return {}

def delete_rating_by_id(rating_id):
    """Delete rating by ID"""
    try:
        result = ratings_collection.delete_one({"_id": ObjectId(rating_id)})
        return result.deleted_count
    except Exception as e:
        print(f"Error deleting rating: {e}")
        return 0

def get_user_completed_bookings(user_email, user_name):
    """
    Get all completed bookings for a specific user.
    Used to verify if user can rate services.
    """
    try:
        bookings = list(prebookings_collection.find({
            "email": user_email,
            "name": {"$regex": f"^{user_name}$", "$options": "i"},
            "status": "completed"
        }))
        return bookings
    except Exception as e:
        print(f"Error getting user completed bookings: {e}")
        return []

def get_user_rated_services(user_name):
    """
    Get list of services already rated by a user.
    """
    try:
        ratings = list(ratings_collection.find({
            "user_name": {"$regex": f"^{user_name}$", "$options": "i"}
        }, {"service_name": 1, "_id": 0}))
        
        return [rating['service_name'] for rating in ratings]
    except Exception as e:
        print(f"Error getting user rated services: {e}")
        return []

def validate_user_can_rate_service(user_email, user_name, service_name):
    """
    Comprehensive validation to check if a user can rate a specific service.
    Returns (can_rate: bool, reason: str)
    """
    try:
        # Check if user has completed booking for this service
        completed_booking = prebookings_collection.find_one({
            "email": user_email,
            "name": {"$regex": f"^{user_name}$", "$options": "i"},
            "services": service_name,
            "status": "completed"
        })
        
        if not completed_booking:
            return False, f"No completed booking found for '{service_name}'"
        
        # Check if user has already rated this service
        existing_rating = check_user_rating_exists(user_name, service_name)
        if existing_rating:
            return False, f"You have already rated '{service_name}'"
        
        return True, "User can rate this service"
        
    except Exception as e:
        print(f"Error validating user can rate service: {e}")
        return False, "Validation error occurred"

# ==================== PREBOOKINGS ====================
def insert_prebooking(prebooking_data):
    """Insert a new prebooking"""
    try:
        # Generate unique booking ID
        booking_id = str(uuid.uuid4())[:8].upper()
        prebooking_data['booking_id'] = booking_id
        prebooking_data['created_at'] = datetime.now()
        prebooking_data['status'] = 'pending'
        
        # Ensure services is a list
        if 'services' not in prebooking_data:
            prebooking_data['services'] = []
        
        result = prebookings_collection.insert_one(prebooking_data)
        return booking_id
    except Exception as e:
        print(f"Error inserting prebooking: {e}")
        raise

def get_prebookings(filter_criteria=None):
    """Get prebookings with optional filters"""
    try:
        if filter_criteria:
            return list(prebookings_collection.find(filter_criteria).sort("created_at", -1))
        return list(prebookings_collection.find().sort("created_at", -1))
    except Exception as e:
        print(f"Error getting prebookings: {e}")
        return []

def get_prebooking_by_id(booking_id):
    """Get prebooking by booking ID"""
    try:
        return prebookings_collection.find_one({"booking_id": booking_id})
    except Exception as e:
        print(f"Error getting prebooking by ID: {e}")
        return None

def update_prebooking_status(booking_id, status):
    """Update prebooking status"""
    try:
        return prebookings_collection.update_one(
            {"booking_id": booking_id},
            {"$set": {"status": status, "updated_at": datetime.now()}}
        )
    except Exception as e:
        print(f"Error updating prebooking status: {e}")
        return None

def delete_prebooking_by_id(prebooking_id):
    """Delete prebooking by ID"""
    try:
        result = prebookings_collection.delete_one({"_id": ObjectId(prebooking_id)})
        return result.deleted_count
    except Exception as e:
        print(f"Error deleting prebooking: {e}")
        return 0

# ==================== OTP ====================
def generate_otp(email):
    """Generate and store OTP for email verification"""
    try:
        # Delete any existing OTPs for this email
        otp_collection.delete_many({"email": email})
        
        # Generate new OTP
        otp = str(random.randint(100000, 999999))
        otp_data = {
            "email": email,
            "otp": otp,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(minutes=10)
        }
        otp_collection.insert_one(otp_data)
        return otp
    except Exception as e:
        print(f"Error generating OTP: {e}")
        raise

def verify_otp(email, otp):
    """Verify OTP for email"""
    try:
        print(f"🔍 Checking OTP: {otp} for email: {email}")  # ✅ Debug print

        record = otp_collection.find_one({
            "email": email,
            "otp": otp,
            "expires_at": {"$gt": datetime.now()}
        })
        if record:
            # Delete the used OTP
            otp_collection.delete_one({"_id": record["_id"]})
            return True
        return False
    except Exception as e:
        print(f"Error verifying OTP: {e}")
        return False

def increment_visit_count():
    visits = db.visits.find_one({})
    if not visits:
        db.visits.insert_one({"count": 1})
    else:
        db.visits.update_one({}, {"$inc": {"count": 1}})

def get_total_visits():
    visits = db.visits.find_one({})
    return visits.get("count", 0) if visits else 0

# ==================== PAYMENTS ====================
def save_payment_info(payment_data):
    """Save payment information"""
    try:
        payment_data['payment_id'] = str(uuid.uuid4())[:8].upper()
        payment_data['created_at'] = datetime.now()
        payment_data['status'] = payment_data.get('status', 'pending')
        result = payments_collection.insert_one(payment_data)
        return result.inserted_id
    except Exception as e:
        print(f"Error saving payment info: {e}")
        raise

def get_payments_by_booking(booking_id):
    """Get payment info by booking ID"""
    try:
        return payments_collection.find_one({"booking_id": booking_id})
    except Exception as e:
        print(f"Error getting payments by booking: {e}")
        return None

# ==================== ADMIN ====================
def get_admin_by_username(username):
    """Get admin by username"""
    try:
        return admin_collection.find_one({"username": username})
    except Exception as e:
        print(f"Error getting admin by username: {e}")
        return None

# Add these functions to your existing db.py file

def update_booking_service_amount(booking_id, service_amount):
    """
    Update the service amount for a booking.
    Total amount = service_amount + 20 (booking fee)
    """
    try:
        total_amount = float(service_amount) + 20  # Add ₹20 booking fee
        
        result = prebookings_collection.update_one(
            {"_id": ObjectId(booking_id)},
            {
                "$set": {
                    "service_amount": float(service_amount),
                    "total_amount": total_amount,
                    "amount_updated_at": datetime.now()
                }
            }
        )
        
        if result.modified_count > 0:
            # Update payment record if exists
            payments_collection.update_one(
                {"booking_id": prebookings_collection.find_one({"_id": ObjectId(booking_id)})["booking_id"]},
                {
                    "$set": {
                        "service_amount": float(service_amount),
                        "total_amount": total_amount,
                        "updated_at": datetime.now()
                    }
                }
            )
            return True
        return False
    except Exception as e:
        print(f"Error updating booking service amount: {e}")
        return False

def get_admin_dashboard_stats():
    """Enhanced dashboard stats with actual total amounts"""
    try:
        total_bookings = prebookings_collection.count_documents({})
        total_ratings = ratings_collection.count_documents({})
        
        # Get today's bookings
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_bookings = prebookings_collection.count_documents({
            "created_at": {"$gte": today_start}
        })
        
        # Get pending and completed bookings
        pending_bookings = prebookings_collection.count_documents({"status": "pending"})
        completed_bookings = prebookings_collection.count_documents({"status": "completed"})
        
        # Calculate total revenue from completed bookings with actual amounts
        completed_bookings_data = list(prebookings_collection.find(
            {"status": "completed"},
            {"total_amount": 1, "service_amount": 1}
        ))
        
        total_service_amount = sum(
            booking.get('total_amount', booking.get('service_amount', 0) + 20) 
            for booking in completed_bookings_data
        )
        
        # If no amounts set, use default ₹20 per booking
        if total_service_amount == 0 and completed_bookings > 0:
            total_service_amount = completed_bookings * 20
        
        # Calculate average rating
        avg_ratings = calculate_average_ratings()
        overall_avg = 0
        if avg_ratings:
            total_sum = sum(item['average'] for item in avg_ratings.values())
            overall_avg = round(total_sum / len(avg_ratings), 1)

        return {
            "total_bookings": total_bookings,
            "total_ratings": total_ratings,
            "today_bookings": today_bookings,
            "pending_bookings": pending_bookings,
            "completed_bookings": completed_bookings,
            "total_service_amount": total_service_amount,
            "average_rating": overall_avg
        }
    except Exception as e:
        print(f"Error getting dashboard stats: {e}")
        return {
            "total_bookings": 0,
            "total_ratings": 0,
            "today_bookings": 0,
            "pending_bookings": 0,
            "completed_bookings": 0,
            "total_service_amount": 0,
            "average_rating": 0
        }

def generate_receipt_pdf(booking_data, receipt_type="Service Receipt"):
    """Enhanced PDF receipt with service amounts"""
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, 
                              rightMargin=72, leftMargin=72, 
                              topMargin=72, bottomMargin=18)
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = styles['Title']
        title_style.fontSize = 18
        title_style.textColor = colors.darkblue
        
        elements.append(Paragraph("Annapoorneshwari Tyre & Painting Works", title_style))
        elements.append(Paragraph(receipt_type, styles['Heading2']))
        elements.append(Spacer(1, 12))
        
        # Company details
        company_info = """
        <b>Address:</b> Hebri Santekatte, Karnataka<br/>
        <b>Contact:</b> 8861446025<br/>
        <b>Email:</b> kulaladarsh1@gmail.com<br/>
        """
        elements.append(Paragraph(company_info, styles['Normal']))
        elements.append(Spacer(1, 12))
        
        # Get amounts
        service_amount = booking_data.get('service_amount', 0)
        booking_fee = 20
        total_amount = booking_data.get('total_amount', service_amount + booking_fee)
        
        # Receipt details
        receipt_data = [
            ['Receipt Details', ''],
            ['Booking ID:', booking_data.get('booking_id', 'N/A')],
            ['Date:', datetime.now().strftime('%Y-%m-%d %H:%M')],
            ['Status:', booking_data.get('status', 'pending').title()],
            ['', ''],
            ['Customer Details', ''],
            ['Name:', booking_data.get('name', 'N/A')],
            ['Contact:', booking_data.get('contact', 'N/A')],
            ['Email:', booking_data.get('email', 'N/A')],
            ['Area:', f"{booking_data.get('area', '')}, {booking_data.get('district', '')}, {booking_data.get('taluk', '')}"],
            ['', ''],
            ['Service Details', ''],
            ['Preferred Date:', booking_data.get('preferred_date', 'N/A')],
            ['Preferred Time:', booking_data.get('time', 'N/A')],
            ['Vehicle Type:', booking_data.get('vehicle_type', 'N/A')],
            ['Vehicle Details:', booking_data.get('vehicle_details', 'N/A')],
        ]
        
        # Add services
        services = booking_data.get('services', [])
        if services:
            receipt_data.append(['Services:', ', '.join(services)])
        
        # Enhanced Payment information with itemized amounts
        receipt_data.extend([
            ['', ''],
            ['Payment Details', ''],
            ['Service Charges:', f'₹{service_amount:.2f}'],
            ['Booking Fee:', f'₹{booking_fee:.2f}'],
            ['', ''],
            ['Total Amount:', f'₹{total_amount:.2f}'],
            ['Payment Status:', 'Completed' if booking_data.get('status') == 'completed' else 'Paid (Booking Fee)'],
            ['Payment Method:', 'UPI'],
        ])
        
        # Create table with styling
        table = Table(receipt_data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            # Highlight total amount row
            ('BACKGROUND', (0, -4), (-1, -4), colors.lightgrey),
            ('FONTNAME', (0, -4), (-1, -4), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -4), (-1, -4), 14),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 12))
        
        # Footer
        footer_text = """
        <b>Thank you for choosing Annapoorneshwari Tyre & Painting Works!</b><br/>
        For any queries, please contact us at 8861446025<br/>
        <i>This is a computer-generated receipt.</i>
        """
        elements.append(Paragraph(footer_text, styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        print(f"Error generating PDF receipt: {e}")
        raise

# ==================== UTILITY FUNCTIONS ====================
def render_stars(rating):
    """Render star rating HTML"""
    try:
        rating = float(rating) if rating else 0
        full_stars = int(rating)
        half_star = 1 if (rating - full_stars) >= 0.5 else 0
        empty_stars = 5 - full_stars - half_star

        stars_html = ''
        for _ in range(full_stars):
            stars_html += '<i class="fas fa-star text-warning"></i>'
        if half_star:
            stars_html += '<i class="fas fa-star-half-alt text-warning"></i>'
        for _ in range(empty_stars):
            stars_html += '<i class="far fa-star text-warning"></i>'

        return stars_html
    except Exception as e:
        print(f"Error rendering stars: {e}")
        return '<i class="far fa-star text-warning"></i>' * 5

def export_bookings_to_excel():
    """Export bookings to Excel format"""
    try:
        bookings = list(prebookings_collection.find({}, {"_id": 0}))
        return bookings
    except Exception as e:
        print(f"Error exporting bookings: {e}")
        return []

def cleanup_expired_otps():
    """Clean up expired OTPs (can be run as a background task)"""
    try:
        result = otp_collection.delete_many({
            "expires_at": {"$lt": datetime.now()}
        })
        return result.deleted_count
    except Exception as e:
        print(f"Error cleaning up expired OTPs: {e}")
        return 0

# Initialize admin user if not exists
def initialize_admin():
    """Initialize default admin user if not exists"""
    try:
        admin_exists = admin_collection.count_documents({})
        if admin_exists == 0:
            import hashlib
            default_admin = {
                "username": "admin",
                "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
                "created_at": datetime.now(),
                "role": "super_admin"
            }
            admin_collection.insert_one(default_admin)
            print("Default admin user created: username='admin', password='admin123'")
    except Exception as e:
        print(f"Error initializing admin: {e}")

# Enhanced visits tracking
visits_collection = db['visits']

def increment_visit_count():
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        visits_collection.update_one(
            {"date": today},
            {"$inc": {"count": 1}},
            upsert=True
        )
    except Exception as e:
        print("Error incrementing visits:", e)

def get_total_visits():
    try:
        total = visits_collection.aggregate([
            {"$group": {"_id": None, "total": {"$sum": "$count"}}}
        ])
        return next(total, {}).get("total", 0)
    except:
        return 0


initialize_admin()