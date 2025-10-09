# TODO: Enhance Booking Rejection with PDF Email

## Completed Tasks
- [x] Updated app.py reject_booking endpoint to generate PDF rejection notice
- [x] Enhanced email sending to include PDF attachment with rejection details
- [x] Reviewed admin_dashboard.html template for consistency
- [x] Refactored db.py to use lazy-loaded collection functions instead of direct db.collection access

## Pending Tasks
- [ ] Test reject booking functionality end-to-end
- [ ] Verify PDF generation and email sending
- [ ] Check error handling for PDF generation failures
- [ ] Test UI feedback and user experience

## Notes
- The reject booking button in admin dashboard calls the updated endpoint
- PDF includes booking ID, customer name, reason for rejection, and contact info
- Fallback to plain email if PDF generation fails
