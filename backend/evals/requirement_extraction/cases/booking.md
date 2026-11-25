# Service Booking — Booking module (synthetic)

## Scheduling
A customer can search for available time slots by service and date.
Past dates must not be selectable in the date picker.
Bookings must be made at least 2 hours before the slot starts.
If no slots are available on the chosen date, the app suggests the next three dates that have availability.

## Confirmation
A booking is confirmed only after payment succeeds.
The customer receives a confirmation email within 1 minute of confirmation.

## Providers
A provider must accept or reject a pending booking within 24 hours; otherwise it is cancelled automatically and the customer is refunded.
Only the assigned provider can accept or reject a booking.
