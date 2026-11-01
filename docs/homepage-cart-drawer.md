# Homepage floating basket drawer

Visual source: user's supplied empty-cart screenshot. Scope: homepage floating
`.rtsb-cart-float-inner` trigger, drawer, and existing in-memory basket. No Shop,
product-page, admin, model, or database changes.

The trigger opens a native modal dialog aligned to the right edge. The 348px
drawer is capped at viewport width and uses the viewport height. The design
includes the cart heading/count, Clear All, close control, empty-cart illustration,
Go Shopping link to the existing Shop route, coupon row and totals/actions footer.
The illustration was generated with built-in ImageGen from the supplied reference.

The trigger supports Enter/Space. Native dialog behavior provides modal focus
containment and Escape dismissal; backdrop clicks and the close control also
dismiss. Opening locks background scrolling; closing restores scrolling and focus.
Reduced-motion preferences disable the entrance animation.

Existing preview items are shown as a list and Clear All resets the basket/counts.
Empty totals use PKR 0.00. Populated totals say Not calculated because the existing
preview has no authoritative total. Coupon, View cart and Checkout remain disabled
with a preview notice; no new checkout routes or persistence are introduced.

Checks: JavaScript syntax; three Node event-handler checks using DOM stubs;
three focused Django template/regression tests without database setup; whitespace.
Browser interaction, layout, focus behavior in a real browser and screenshot
comparison have not been performed, per the user's visual-QA instruction.

Retest when requested: mouse/keyboard trigger; Escape/X/backdrop close; focus
restoration; scroll lock; empty and populated basket; Clear All; Go Shopping;
desktop/tablet/mobile layouts and short viewport scrolling.
