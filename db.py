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
if not uri:
    raise ValueError("MONGO_URI environment variable is not set. Please set it in your deployment environment.")
client = MongoClient(uri, serverSelectionTimeoutMS=5000)

# Access DB & collections
db = client["annapoorneshwari_tyre_works"]

visits_collection = db['visits']
services_collection = db['services']
ratings_collection = db['get_ratings']
prebookings_collection = db['prebookings']
admin_collection = db['admins']
otp_collection = db['otps']
painting_limits_collection = db['painting_limits']
payments_collection = db['payments']


# ================= UPDATED: CREATE INDEXES =================
def create_indexes():
    """Create database indexes with booking_id support"""
    try:
        # UPDATED: Drop old indexes that prevent proper rating functionality
        try:
            # Drop the old index that prevents multiple ratings per user-service
            ratings_collection.drop_index("service_name_1_user_name_1")
            print("✅ Dropped old user-service rating index")
        except Exception as e:
            print(f"Old user-service index drop note: {e}")

        try:
            # Drop the problematic single booking_id index that prevents multiple services per booking
            ratings_collection.drop_index("booking_id_1")
            print("✅ Dropped old single booking_id index")
        except Exception as e:
            print(f"Old booking_id index drop note: {e}")

        # Create new unique index on booking_id + service_name (allows multiple services per booking)
        try:
            ratings_collection.create_index(
                [("booking_id", 1), ("service_name", 1)],
                unique=True,
                name="booking_service_unique"
            )
            print("✅ Created booking-service rating index")
        except Exception as e:
            if "duplicate key" not in str(e).lower():
                print(f"Rating index note: {e}")

        # Performance indexes - Check existing indexes to avoid conflicts
        try:
            # Check existing indexes on ratings_collection
            existing_indexes = ratings_collection.index_information()

            # Create service_name + created_at index if not exists
            if not any('service_name' in str(idx.get('key', [])) and 'created_at' in str(idx.get('key', [])) for idx in existing_indexes.values()):
                ratings_collection.create_index([("service_name", 1), ("created_at", -1)])
                print("✅ Created service_name + created_at index")
            else:
                print("ℹ️  service_name + created_at index already exists")

            # Create user_email index if not exists
            if not any('user_email' in str(idx.get('key', [])) for idx in existing_indexes.values()):
                ratings_collection.create_index([("user_email", 1)])
                print("✅ Created user_email index")
            else:
                print("ℹ️  user_email index already exists")

            # Create booking_id index if not exists
            if not any('booking_id' in str(idx.get('key', [])) for idx in existing_indexes.values()):
                ratings_collection.create_index([("booking_id", 1)])
                print("✅ Created booking_id index")
            else:
                print("ℹ️  booking_id index already exists")

            # Prebookings indexes
            prebookings_existing = prebookings_collection.index_information()

            # email + status index
            if not any('email' in str(idx.get('key', [])) and 'status' in str(idx.get('key', [])) for idx in prebookings_existing.values()):
                prebookings_collection.create_index([("email", 1), ("status", 1)])
                print("✅ Created email + status index")
            else:
                print("ℹ️  email + status index already exists")

            # booking_id unique index
            if not any('booking_id' in str(idx.get('key', [])) for idx in prebookings_existing.values()):
                prebookings_collection.create_index([("booking_id", 1)], unique=True)
                print("✅ Created booking_id unique index")
            else:
                print("ℹ️  booking_id unique index already exists")

            # services + status index
            if not any('services' in str(idx.get('key', [])) and 'status' in str(idx.get('key', [])) for idx in prebookings_existing.values()):
                prebookings_collection.create_index([("services", 1), ("status", 1)])
                print("✅ Created services + status index")
            else:
                print("ℹ️  services + status index already exists")

        except Exception as e:
            print(f"Performance index note: {e}")

    except Exception as e:
        print(f"Index creation error: {e}")


# Call index creation
create_indexes()


# ==================== SERVICES ====================
def get_services():
    """Returns list of services without prices"""
    return list(services_collection.find({}, {"_id": 0, "name": 1, "description": 1}))


# ==================== USERS ====================
def insert_user(user_data):
    """Insert new user"""
    try:
        # Check if email already exists
        existing = db.users.find_one({"email": user_data.get("email").lower()})
        if existing:
            raise ValueError("Email already registered")

        user_data['email'] = user_data.get('email').lower()
        user_data['created_at'] = datetime.now()
        user_data['profile_photo'] = user_data.get('profile_photo', None)
        user_data['vehicle_details'] = user_data.get('vehicle_details', {})
        user_data['phone'] = user_data.get('phone', '')
        user_data['name'] = user_data.get('name', '')
        user_data['password_hash'] = user_data.get('password_hash', '')
        user_data['status'] = 'pending'
        user_data['role'] = 'customer'
        user_data['updated_at'] = datetime.now()

        result = db.users.insert_one(user_data)
        return result.inserted_id
    except Exception as e:
        print(f"Error inserting user: {e}")
        raise


def get_user_by_email(email):
    """Get user by email"""
    try:
        user = db.users.find_one({"email": email.lower()})
        return user
    except Exception as e:
        print(f"Error getting user: {e}")
        return None


def update_user_profile(email, update_data):
    """Update user profile by email"""
    try:
        update_data['updated_at'] = datetime.now()
        result = db.users.update_one({"email": email.lower()}, {"$set": update_data})
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating user: {e}")
        return False


def get_user_by_id(user_id):
    """Get user by ObjectId"""
    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
        return user
    except Exception as e:
        print(f"Error getting user by id: {e}")
        return None


def get_pending_users():
    """Get all pending users"""
    try:
        users = list(db.users.find({"status": "pending"}))
        return users
    except Exception as e:
        print(f"Error getting pending users: {e}")
        return []


def approve_user(user_id, role='customer'):
    """Approve a user and set their role"""
    try:
        result = db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"status": "approved", "role": role, "updated_at": datetime.now()}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error approving user: {e}")
        return False


def reject_user(user_id):
    """Reject a user"""
    try:
        result = db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"status": "rejected", "updated_at": datetime.now()}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error rejecting user: {e}")
        return False


# ================= UPDATED: NEW FUNCTION - Get service by name =================
def get_service_by_name(service_name):
    """
    FIXED: Get service with case-insensitive matching
    """
    try:
        service = services_collection.find_one(
            {"name": {"$regex": f"^{service_name}$", "$options": "i"}},
            {"_id": 0, "name": 1, "price": 1, "description": 1}
        )
        
        if not service:
            # Fallback: try exact match
            service = services_collection.find_one(
                {"name": service_name},
                {"_id": 0, "name": 1, "price": 1, "description": 1}
            )
        
        return service
    except Exception as e:
        print(f"Error getting service: {e}")
        return None


# ==================== RATINGS ====================
def calculate_average_ratings():
    """Calculate average ratings per service using canonical service names"""
    try:
        # Get all ratings
        ratings = list(ratings_collection.find())

        # Group by canonical service name
        service_ratings = {}
        for rating in ratings:
            service_name = rating.get("service_name", "")
            if service_name:
                # Get canonical service name
                canonical_service = get_service_by_name(service_name)
                if canonical_service:
                    canonical_name = canonical_service["name"]
                else:
                    canonical_name = service_name.capitalize()  # Fallback

                if canonical_name not in service_ratings:
                    service_ratings[canonical_name] = []
                service_ratings[canonical_name].append(rating["rating"])

        # Calculate averages
        avg_ratings = {}
        for service_name, ratings_list in service_ratings.items():
            if ratings_list:
                avg_ratings[service_name] = {
                    "average": round(float(sum(ratings_list) / len(ratings_list)), 1),
                    "count": len(ratings_list)
                }

        return avg_ratings

    except Exception as e:
        print(f"Error calculating ratings: {e}")
        return {}


# ================= UPDATED: INSERT RATING - Now with booking_id validation and service name normalization =================
def insert_rating(rating_data):
    """
    FIXED: Insert rating with flexible validation and service name normalization
    """
    try:
        # Validate required fields
        if "booking_id" not in rating_data or not rating_data["booking_id"]:
            raise ValueError("Booking ID is required")

        if "service_name" not in rating_data or not rating_data["service_name"]:
            raise ValueError("Service name is required")

        # NORMALIZE SERVICE NAME: Find the canonical service name from services collection
        original_service_name = rating_data["service_name"]
        canonical_service = get_service_by_name(original_service_name)

        if canonical_service:
            # Use the canonical service name from database
            rating_data["service_name"] = canonical_service["name"]
            print(f"🔄 Normalized service name: '{original_service_name}' → '{canonical_service['name']}'")
        else:
            print(f"⚠️  Warning: Service '{original_service_name}' not found in services collection")

        # FIXED: Use case-insensitive check for existing ratings
        existing = ratings_collection.find_one({
            "booking_id": rating_data["booking_id"],
            "service_name": {"$regex": f"^{rating_data['service_name']}$", "$options": "i"}
        })

        if existing:
            raise ValueError("Rating already exists for this booking and service")

        # Add timestamp if not present
        rating_data["created_at"] = rating_data.get("created_at", datetime.now())

        # Ensure photo_urls field exists
        rating_data["photo_urls"] = rating_data.get("photo_urls", [])

        # Insert rating
        result = ratings_collection.insert_one(rating_data)

        print(f"✅ Rating inserted successfully:")
        print(f"   Booking: {rating_data['booking_id']}")
        print(f"   Service: {rating_data['service_name']}")
        print(f"   Rating: {rating_data['rating']}/5")
        print(f"   Photos: {len(rating_data['photo_urls'])}")

        return str(result.inserted_id)

    except Exception as e:
        print(f"❌ Error inserting rating: {e}")
        raise


def get_ratings():
    """Get all ratings with formatted dates"""
    try:
        ratings = list(ratings_collection.find().sort("created_at", -1))
        
        for rating in ratings:
            rating['_id'] = str(rating['_id'])
            if 'created_at' in rating and rating['created_at']:
                rating['created_at_formatted'] = rating['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return ratings
        
    except Exception as e:
        print(f"Error getting ratings: {e}")
        return []


# ================= UPDATED: NEW FUNCTION - Get ratings by service =================
def get_ratings_by_service(service_name):
    """
    Get all ratings for a specific service (from all bookings)
    Returns ratings with photo URLs and booking info
    Uses case-insensitive matching with canonical service names
    """
    try:
        # First, get the canonical service name
        canonical_service = get_service_by_name(service_name)
        if canonical_service:
            search_name = canonical_service["name"]
        else:
            search_name = service_name

        # Use case-insensitive regex search to find all variations
        ratings = list(ratings_collection.find(
            {"service_name": {"$regex": f"^{search_name}$", "$options": "i"}}
        ).sort("created_at", -1))

        # Format data
        for rating in ratings:
            rating['_id'] = str(rating['_id'])
            if 'created_at' in rating and rating['created_at']:
                rating['created_at_formatted'] = rating['created_at'].strftime('%d %b %Y')

            # Ensure photo_urls exists
            if 'photo_urls' not in rating:
                rating['photo_urls'] = []

        return ratings

    except Exception as e:
        print(f"Error getting ratings by service: {e}")
        return []


# ================= UPDATED: NEW FUNCTION - Check rating exists for booking =================
def check_user_rating_exists_for_booking(booking_id, service_name):
    """
    FIXED: Check if a rating exists with case-insensitive service name matching
    """
    try:
        return ratings_collection.find_one({
            "booking_id": booking_id,
            "service_name": {"$regex": f"^{service_name}$", "$options": "i"}
        })
    except Exception as e:
        print(f"Error checking rating: {e}")
        return None


def delete_rating_by_id(rating_id):
    """Delete rating by ID"""
    try:
        result = ratings_collection.delete_one({"_id": ObjectId(rating_id)})
        return result.deleted_count
    except Exception as e:
        print(f"Error deleting rating: {e}")
        return 0


def get_user_completed_bookings(user_email, user_name):
    """Get all completed bookings for a user"""
    try:
        bookings = list(prebookings_collection.find({
            "email": user_email,
            "name": {"$regex": f"^{user_name}$", "$options": "i"},
            "status": "completed"
        }))
        return bookings
    except Exception as e:
        print(f"Error getting bookings: {e}")
        return []


def validate_user_can_rate_service(user_email, user_name, service_name):
    """Validate if user can rate a service"""
    try:
        # Find completed bookings for this user
        completed_bookings = list(prebookings_collection.find({
            "email": user_email,
            "name": {"$regex": f"^{user_name}$", "$options": "i"},
            "status": "completed"
        }))

        # Check if any booking contains the service
        for booking in completed_bookings:
            services = booking.get('services', [])
            if isinstance(services, list) and services:
                if isinstance(services[0], dict):
                    # New format: list of dicts
                    service_names = [s.get('name', '') for s in services]
                else:
                    # Old format: list of strings
                    service_names = services

                if service_name in service_names:
                    return True, "User can rate"

        return False, f"No completed booking for '{service_name}'"

    except Exception as e:
        print(f"Error validating: {e}")
        return False, "Validation error"


# ==================== PREBOOKINGS ====================
def insert_prebooking(prebooking_data):
    """Insert new prebooking"""
    try:
        booking_id = str(uuid.uuid4())[:8].upper()
        prebooking_data['booking_id'] = booking_id
        prebooking_data['created_at'] = datetime.now()
        prebooking_data['status'] = 'pending'

        if 'services' not in prebooking_data:
            prebooking_data['services'] = []

        # Ensure services are in correct format: list of dicts without amounts
        services = prebooking_data['services']
        if services and isinstance(services[0], str):
            # Migrate old format: list of strings to list of dicts without amounts
            prebooking_data['services'] = [
                {'name': service, 'amount': 0}
                for service in services
            ]

        # No amount calculation - amounts will be set by admin later
        prebooking_data['total_service_amount'] = 0
        prebooking_data['total_amount'] = 0

        result = prebookings_collection.insert_one(prebooking_data)
        return booking_id
    except Exception as e:
        print(f"Error inserting prebooking: {e}")
        raise


def get_prebookings(filter_criteria=None, search=None, status=None, service=None, start_date=None, end_date=None):
    """Get prebookings with optional filters"""
    try:
        query = {}

        # Apply existing filter_criteria if provided
        if filter_criteria:
            query.update(filter_criteria)

        # Text search across multiple fields
        if search:
            search_regex = {"$regex": search, "$options": "i"}
            query["$or"] = [
                {"name": search_regex},
                {"email": search_regex},
                {"contact": search_regex},
                {"booking_id": search_regex},
                {"vehicle_type": search_regex},
                {"vehicle_details": search_regex}
            ]

        # Status filter
        if status and status != "All":
            query["status"] = status.lower()

        # Service filter
        if service and service != "All":
            # Handle both old format (list of strings) and new format (list of dicts)
            query["$or"] = query.get("$or", []) + [
                {"services": {"$in": [service]}},  # Old format: direct string match
                {"services.name": service}  # New format: dict with name field
            ]

        # Date range filter (on created_at)
        if start_date or end_date:
            date_filter = {}
            if start_date:
                try:
                    date_filter["$gte"] = datetime.strptime(start_date, '%Y-%m-%d')
                except ValueError:
                    pass
            if end_date:
                try:
                    # Set end_date to end of day
                    end_datetime = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                    date_filter["$lt"] = end_datetime
                except ValueError:
                    pass
            if date_filter:
                query["created_at"] = date_filter

        return list(prebookings_collection.find(query).sort("created_at", -1))
    except Exception as e:
        print(f"Error getting prebookings: {e}")
        return []


def get_prebooking_by_id(identifier):
    """Get prebooking by booking_id (string) or _id (ObjectId)"""
    try:
        # Try to convert to ObjectId first (for _id lookup)
        try:
            obj_id = ObjectId(identifier)
            return prebookings_collection.find_one({"_id": obj_id})
        except:
            # If not a valid ObjectId, treat as booking_id string
            return prebookings_collection.find_one({"booking_id": identifier})
    except Exception as e:
        print(f"Error getting prebooking: {e}")
        return None


def update_prebooking_status(booking_id, status):
    """Update prebooking status"""
    try:
        return prebookings_collection.update_one(
            {"booking_id": booking_id},
            {"$set": {"status": status, "updated_at": datetime.now()}}
        )
    except Exception as e:
        print(f"Error updating status: {e}")
        return None


def delete_prebooking_by_id(prebooking_id):
    """Delete prebooking by ID"""
    try:
        result = prebookings_collection.delete_one({"_id": ObjectId(prebooking_id)})
        return result.deleted_count
    except Exception as e:
        print(f"Error deleting prebooking: {e}")
        return 0


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
        print(f"Error saving payment: {e}")
        raise


def save_manual_payment(manual_payment_data):
    """Save manual payment information"""
    try:
        # Validate required fields
        required_fields = ['booking_id', 'amount_paid', 'payment_mode']
        for field in required_fields:
            if field not in manual_payment_data or not manual_payment_data[field]:
                raise ValueError(f"{field} is required")

        manual_payment_data['payment_id'] = str(uuid.uuid4())[:8].upper()
        manual_payment_data['payment_type'] = 'manual'
        manual_payment_data['created_at'] = datetime.now()
        manual_payment_data['status'] = manual_payment_data.get('status', 'completed')

        # Update booking status if payment is completed
        if manual_payment_data['status'] == 'completed':
            prebookings_collection.update_one(
                {"booking_id": manual_payment_data['booking_id']},
                {"$set": {"payment_status": "paid", "updated_at": datetime.now()}}
            )

        result = payments_collection.insert_one(manual_payment_data)
        return result.inserted_id
    except Exception as e:
        print(f"Error saving manual payment: {e}")
        raise


def get_payments_by_booking(booking_id):
    """Get payment info by booking ID"""
    try:
        return payments_collection.find_one({"booking_id": booking_id})
    except Exception as e:
        print(f"Error getting payments: {e}")
        return None


def get_all_payments(filter_criteria=None, limit=100):
    """Get all payments with optional filters"""
    try:
        query = {}
        if filter_criteria:
            if 'payment_type' in filter_criteria:
                query['payment_type'] = filter_criteria['payment_type']
            if 'status' in filter_criteria:
                query['status'] = filter_criteria['status']
            if 'date_from' in filter_criteria and 'date_to' in filter_criteria:
                query['created_at'] = {
                    '$gte': datetime.strptime(filter_criteria['date_from'], '%Y-%m-%d'),
                    '$lte': datetime.strptime(filter_criteria['date_to'], '%Y-%m-%d')
                }

        payments = list(payments_collection.find(query).sort("created_at", -1).limit(limit))

        # Add booking details to payments
        for payment in payments:
            if 'booking_id' in payment:
                booking = prebookings_collection.find_one({"booking_id": payment['booking_id']})
                if booking:
                    payment['customer_name'] = booking.get('name', 'N/A')
                    payment['customer_email'] = booking.get('email', 'N/A')
                    payment['services'] = booking.get('services', [])

        return payments
    except Exception as e:
        print(f"Error getting payments: {e}")
        return []


def update_payment_status(payment_id, status):
    """Update payment status"""
    try:
        result = payments_collection.update_one(
            {"payment_id": payment_id},
            {"$set": {"status": status, "updated_at": datetime.now()}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating payment status: {e}")
        return False


def get_payment_stats():
    """Get payment statistics for dashboard"""
    try:
        # Total revenue from completed payments
        total_revenue_pipeline = [
            {"$match": {"status": "completed"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount_paid"}}}
        ]
        total_revenue_result = list(payments_collection.aggregate(total_revenue_pipeline))
        total_revenue = total_revenue_result[0]['total'] if total_revenue_result else 0

        # Revenue by payment type
        revenue_by_type_pipeline = [
            {"$match": {"status": "completed"}},
            {"$group": {"_id": "$payment_type", "total": {"$sum": "$amount_paid"}}}
        ]
        revenue_by_type = {item['_id'] or 'online': item['total'] for item in payments_collection.aggregate(revenue_by_type_pipeline)}

        # Pending payments count
        pending_payments = payments_collection.count_documents({"status": {"$ne": "completed"}})

        # Recent payments (last 10)
        recent_payments = list(payments_collection.find(
            {"status": "completed"}
        ).sort("created_at", -1).limit(10))

        # Add booking details to recent payments
        for payment in recent_payments:
            if 'booking_id' in payment:
                booking = prebookings_collection.find_one({"booking_id": payment['booking_id']})
                if booking:
                    payment['customer_name'] = booking.get('name', 'N/A')
                    payment['services'] = booking.get('services', [])

        return {
            "total_revenue": float(total_revenue),
            "revenue_by_type": revenue_by_type,
            "pending_payments": pending_payments,
            "recent_payments": recent_payments
        }
    except Exception as e:
        print(f"Error getting payment stats: {e}")
        return {
            "total_revenue": 0,
            "revenue_by_type": {},
            "pending_payments": 0,
            "recent_payments": []
        }


# ==================== ADMIN ====================
def get_admin_by_username(username):
    """Get admin by username"""
    try:
        return admin_collection.find_one({"username": username})
    except Exception as e:
        print(f"Error getting admin: {e}")
        return None


def update_booking_service_amount(booking_id, service_amount):
    """Update service amount for booking"""
    try:
        total_amount = float(service_amount) + 20

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
        print(f"Error updating amount: {e}")
        return False


def update_booking_service_amounts(booking_id, services_data):
    """Update individual service amounts for a booking"""
    try:
        # Calculate new totals
        total_service_amount = sum(service.get('amount', 0) for service in services_data)
        total_amount = total_service_amount  # Remove built-in booking fee

        result = prebookings_collection.update_one(
            {"_id": ObjectId(booking_id)},
            {
                "$set": {
                    "services": services_data,
                    "total_service_amount": total_service_amount,
                    "total_amount": total_amount,
                    "amount_updated_at": datetime.now()
                }
            }
        )

        success = result.modified_count > 0
        if success:
            return True, {
                'total_service_amount': total_service_amount,
                'total_amount': total_amount,
                'services': services_data
            }
        return False, None
    except Exception as e:
        print(f"Error updating service amounts: {e}")
        return False, None


def get_enhanced_payment_stats(date_from=None, date_to=None):
    """Get enhanced payment statistics with date filtering"""
    try:
        match_stage = {"status": "completed"}
        if date_from and date_to:
            match_stage["created_at"] = {
                "$gte": datetime.strptime(date_from, '%Y-%m-%d'),
                "$lte": datetime.strptime(date_to, '%Y-%m-%d')
            }

        # Total revenue
        total_revenue_pipeline = [
            {"$match": match_stage},
            {"$group": {"_id": None, "total": {"$sum": "$amount_paid"}}}
        ]
        total_revenue_result = list(payments_collection.aggregate(total_revenue_pipeline))
        total_revenue = total_revenue_result[0]['total'] if total_revenue_result else 0

        # Revenue by payment type
        revenue_by_type_pipeline = [
            {"$match": match_stage},
            {"$group": {"_id": "$payment_type", "total": {"$sum": "$amount_paid"}}}
        ]
        revenue_by_type = {item['_id'] or 'online': item['total'] for item in payments_collection.aggregate(revenue_by_type_pipeline)}

        # Revenue by service
        revenue_by_service = {}
        payments = list(payments_collection.find(match_stage))
        for payment in payments:
            booking = prebookings_collection.find_one({"booking_id": payment['booking_id']})
            if booking:
                services = booking.get('services', [])
                if isinstance(services, list) and services:
                    if isinstance(services[0], dict):
                        for service in services:
                            service_name = service.get('name', 'Unknown')
                            amount = service.get('amount', 0)
                            revenue_by_service[service_name] = revenue_by_service.get(service_name, 0) + amount
                    else:
                        # Old format: distribute amount equally
                        amount_per_service = payment.get('amount_paid', 0) / len(services)
                        for service_name in services:
                            revenue_by_service[service_name] = revenue_by_service.get(service_name, 0) + amount_per_service

        # Monthly revenue trend (last 12 months)
        monthly_revenue = []
        for i in range(11, -1, -1):
            month_start = (datetime.now().replace(day=1) - timedelta(days=i*30)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

            month_match = {"status": "completed", "created_at": {"$gte": month_start, "$lte": month_end}}
            month_result = list(payments_collection.aggregate([
                {"$match": month_match},
                {"$group": {"_id": None, "total": {"$sum": "$amount_paid"}}}
            ]))
            month_total = month_result[0]['total'] if month_result else 0
            monthly_revenue.append({
                "month": month_start.strftime('%b %Y'),
                "revenue": float(month_total)
            })

        return {
            "total_revenue": float(total_revenue),
            "revenue_by_type": revenue_by_type,
            "revenue_by_service": revenue_by_service,
            "monthly_revenue": monthly_revenue
        }
    except Exception as e:
        print(f"Error getting enhanced payment stats: {e}")
        return {
            "total_revenue": 0,
            "revenue_by_type": {},
            "revenue_by_service": {},
            "monthly_revenue": []
        }


def get_admin_dashboard_stats():
    """Get dashboard statistics"""
    try:
        total_bookings = prebookings_collection.count_documents({})
        total_ratings = ratings_collection.count_documents({})
        
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_bookings = prebookings_collection.count_documents({
            "created_at": {"$gte": today_start}
        })
        
        pending_bookings = prebookings_collection.count_documents({"status": "pending"})
        completed_bookings = prebookings_collection.count_documents({"status": "completed"})
        rejected_bookings = prebookings_collection.count_documents({"status": "rejected"})
        
        completed_bookings_data = list(prebookings_collection.find(
            {"status": "completed"},
            {"total_amount": 1, "service_amount": 1}
        ))
        
        total_service_amount = sum(
            booking.get('total_amount', booking.get('service_amount', 0) + 20) 
            for booking in completed_bookings_data
        )
        
        if total_service_amount == 0 and completed_bookings > 0:
            total_service_amount = completed_bookings * 20
        
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
            "rejected_bookings": rejected_bookings,
            "total_service_amount": total_service_amount,
            "average_rating": overall_avg
        }
    except Exception as e:
        print(f"Error getting stats: {e}")
        return {
            "total_bookings": 0, "total_ratings": 0, "today_bookings": 0,
            "pending_bookings": 0, "completed_bookings": 0,
            "total_service_amount": 0, "average_rating": 0
        }


def generate_receipt_pdf(booking_data, receipt_type="Booking Confirmation"):
    """Generate PDF booking confirmation"""
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                              rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=18)

        elements = []
        styles = getSampleStyleSheet()

        title_style = styles['Title']
        title_style.fontSize = 18
        title_style.textColor = colors.darkblue

        elements.append(Paragraph("Annapoorneshwari Tyre & Painting Works", title_style))
        elements.append(Paragraph(receipt_type, styles['Heading2']))
        elements.append(Spacer(1, 12))

        company_info = """
        <b>Address:</b> Hebri Santekatte, Karnataka<br/>
        <b>Contact:</b> 8861446025<br/>
        <b>Email:</b> kulaladarsh1@gmail.com<br/>
        """
        elements.append(Paragraph(company_info, styles['Normal']))
        elements.append(Spacer(1, 12))

        # Get services and calculate estimated cost
        services = booking_data.get('services', [])
        all_services = get_services()
        service_price_map = {service['name']: service.get('price', 0) for service in all_services}

        # Handle both old format (list of strings) and new format (list of dicts)
        service_names = []
        total_amount = 0

        if services:
            if isinstance(services[0], dict):
                # New format: list of dicts
                for service in services:
                    service_names.append(service.get('name', 'Unknown'))
                    total_amount += service.get('amount', 0)
            else:
                # Old format: list of strings
                service_names = services
                total_amount = sum(service_price_map.get(service, 0) for service in services)

        booking_data_table = [
            ['Booking Details', ''],
            ['Booking ID:', booking_data.get('booking_id', 'N/A')],
            ['Booking Date:', datetime.now().strftime('%Y-%m-%d %H:%M')],
            ['Status:', booking_data.get('status', 'pending').title()],
            ['', ''],
            ['Customer Details', ''],
            ['Name:', booking_data.get('name', 'N/A')],
            ['Contact:', booking_data.get('contact', 'N/A')],
            ['Email:', booking_data.get('email', 'N/A')],
            ['Area:', booking_data.get('area', 'N/A')],
            ['District:', booking_data.get('district', 'N/A')],
            ['Taluk:', booking_data.get('taluk', 'N/A')],
            ['', ''],
            ['Service Details', ''],
            ['Preferred Date:', booking_data.get('preferred_date', 'N/A')],
            ['Preferred Time:', booking_data.get('time', 'N/A')],
        ]

        if total_amount > 0:
            # Show service breakdown with amounts
            if isinstance(services, list) and services:
                if isinstance(services[0], dict):
                    # New format: show each service with amount
                    booking_data_table.append(['Service Breakdown:', ''])
                    for service in services:
                        service_name = service.get('name', 'Unknown')
                        service_amount = service.get('amount', 0)
                        booking_data_table.append([f'{service_name}:', f'Rs.{service_amount:.2f}'])
                else:
                    # Old format: list of strings, show with default prices
                    booking_data_table.append(['Services Requested:', ', '.join(service_names)])
                    for service_name in service_names:
                        service_amount = service_price_map.get(service_name, 0)
                        booking_data_table.append([f'{service_name}:', f'Rs.{service_amount:.2f}'])

            booking_data_table.extend([
                ['', ''],
                ['Total Amount:', f'Rs.{total_amount:.2f}'],
                ['', ''],
                ['Payment Note:', 'Payment will be collected on service day'],
            ])
        else:
            # No amounts set, show services without prices
            if service_names:
                booking_data_table.append(['Services Requested:', ', '.join(service_names)])

        table = Table(booking_data_table, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        elements.append(table)

        # Add footer note
        elements.append(Spacer(1, 24))
        footer_text = """
        <b>Important Notes:</b><br/>
        • This is a booking confirmation for service scheduling<br/>
        • Our team will contact you to confirm the appointment<br/>
        • Payment will be collected when services are performed<br/>
        • Please bring your vehicle on the scheduled date and time<br/>
        • For any changes, contact us at 8861446025
        """
        elements.append(Paragraph(footer_text, styles['Normal']))

        doc.build(elements)
        buffer.seek(0)
        return buffer

    except Exception as e:
        print(f"Error generating PDF: {e}")
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
        return '<i class="far fa-star text-warning"></i>' * 5


def export_bookings_to_excel():
    """Export bookings to Excel"""
    try:
        return list(prebookings_collection.find({}, {"_id": 0}))
    except Exception as e:
        print(f"Error exporting: {e}")
        return []


def cleanup_expired_otps():
    """Clean up expired OTPs"""
    try:
        result = otp_collection.delete_many({
            "expires_at": {"$lt": datetime.now()}
        })
        return result.deleted_count
    except Exception as e:
        print(f"Error cleaning OTPs: {e}")
        return 0


def initialize_services():
    """Initialize default services if they don't exist"""
    try:
        # Check if services already exist
        existing_count = services_collection.count_documents({})
        if existing_count > 0:
            print(f"Services already initialized ({existing_count} services found)")
            return

        # Default services to initialize
        default_services = [
            {
                "name": "Greasing",
                "price": 100,
                "description": "Professional greasing services for optimal vehicle performance"
            },
            {
                "name": "Puncturing",
                "price": 50,
                "description": "Quick and reliable puncture repair services"
            },
            {
                "name": "Tyre Issues",
                "price": 200,
                "description": "Complete tyre solutions including replacement and maintenance"
            },
            {
                "name": "Painting",
                "price": 500,
                "description": "Professional painting services for vehicles"
            }
        ]

        # Insert services
        result = services_collection.insert_many(default_services)
        print(f"✅ Initialized {len(result.inserted_ids)} services")

    except Exception as e:
        print(f"Error initializing services: {e}")


def initialize_admin():
    """Initialize default admin"""
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
            print("Admin created: admin/admin123")
    except Exception as e:
        print(f"Error initializing admin: {e}")


def increment_visit_count():
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        visits_collection.update_one(
            {"date": today},
            {"$inc": {"count": 1}},
            upsert=True
        )
    except Exception as e:
        print(f"Error incrementing visits: {e}")


def get_total_visits():
    """Get total visits"""
    try:
        total = visits_collection.aggregate([
            {"$group": {"_id": None, "total": {"$sum": "$count"}}}
        ])
        return next(total, {}).get("total", 0)
    except Exception as e:
        print(f"Error getting visits: {e}")
        return 0


# Initialize admin and services on import
initialize_admin()
initialize_services()
