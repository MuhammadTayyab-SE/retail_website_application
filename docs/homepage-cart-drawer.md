# Homepage floating basket drawer

Visual source: user's supplied empty-cart screenshot. Scope: shared floating
`.rtsb-cart-float-inner` trigger and drawer on Home, Shop, and product pages.
Header cart controls open the same drawer. No admin, model, or database changes.

The trigger opens a native modal dialog aligned to the right edge. The 348px
drawer is capped at viewport width and uses the viewport height. The design
includes the cart heading/count, Clear All, close control, empty-cart illustration,
Go Shopping link to the existing Shop route, coupon row and totals/actions footer.
The illustration was generated with built-in ImageGen from the supplied reference.

The trigger supports Enter/Space. Native dialog behavior provides modal focus
containment and Escape dismissal; backdrop clicks and the close control also
dismiss. Opening locks background scrolling; closing restores scrolling and focus.
Reduced-motion preferences disable the entrance animation.

Populated rows show the existing product photo, name, description, original price,
and discounted price when on sale. Descriptions are rendered as text, not HTML.
The shared homepage card template supplies unlocalized prices from Product.price
and the existing Product.sale_price property; discounts are not recomputed in JS.
Older cached card HTML without the new attributes falls back to the regular and
sale price labels already rendered on that card. A restart of the local server
loads updated cached templates. The per-product delete action uses the existing
Font Awesome trash icon with an accessible Delete label.
Preview totals sum integer minor units to avoid fractional-currency drift.
Items added through older events without pricing still display Not calculated.
Totals are previews, not authoritative checkout charges.

Increase/decrease controls update the quantity, counters, and preview total.
Quantities stay between one and the stock available when the product was added;
repeated Add to cart actions obey the same limit. Remove deletes an individual row,
and Clear All resets the basket. Removing the last item restores the empty state.
Focus remains in the drawer after row updates. Coupon, View cart and Checkout stay
disabled with a preview notice; no new routes or backend persistence are introduced.

The preview basket is saved to sessionStorage after each mutation and restored
when another storefront page loads in the same tab. Refreshing, navigating,
quantity changes, row deletion and Clear All share that state. Standard products
use the same live-product ID from every page, while variants retain distinct IDs.
Shop cards and product-page events carry descriptions, photos, prices and stock.
Malformed state is ignored; blocked storage leaves an in-memory page preview.
This is navigation persistence only: it does not guarantee recovery after closing
the tab or provide per-account carts. Database-backed account/guest carts require
separate user authorization for backend/schema changes.

Checks: JavaScript syntax; twelve Node event-handler checks using DOM stubs;
five focused Django template/regression tests without database setup; whitespace.
Browser interaction, layout, focus behavior in a real browser and screenshot
comparison have not been performed, per the user's visual-QA instruction.

Retest when requested: mouse/keyboard trigger; Escape/X/backdrop close; focus
restoration; scroll lock; empty and populated basket; Clear All; Go Shopping;
desktop/tablet/mobile layouts and short viewport scrolling; product descriptions,
regular/discounted prices, stock-limited quantity controls, row deletion and totals.
Also verify same-tab navigation and refresh between all three storefront pages.
Restart the development server to clear the older cached templates. For ongoing
editing, run Django's development server with its default autoreloader enabled.
