# Coupons and payment rules (synthetic)

| Rule | Detail |
| --- | --- |
| One coupon per order | A customer can apply at most one coupon to a booking. |
| Expiry | An expired coupon shows the message "This coupon has expired" and is not applied. |
| Minimum spend | Coupons apply only when the booking total is 20 USD or more. |

Payment methods are card and wallet. Wallet payments are rejected when the balance is lower than the total.
Card details are never stored by the platform; tokenisation is handled by the payment provider.
The checkout page must load in under 2 seconds on a 4G connection.
