# TODO: Add Vehicle Number Field

## Tasks
- [ ] Add vehicle_number input field to prebooking.html form
- [ ] Update admin_dashboard.html to display vehicle_number in the Vehicle column
- [ ] Update receipt.html to show vehicle_number in the Vehicle section
- [ ] Test the form submission and verify data is saved and displayed correctly

## Files to Edit
- templates/prebooking.html: Add input field for vehicle number
- templates/admin_dashboard.html: Update table display
- templates/receipt.html: Update receipt display

## Notes
- Vehicle number should be optional field
- Display format: Vehicle Type, Vehicle Number, Vehicle Details
- Ensure database automatically handles the new field (no changes needed in db.py or app.py)
