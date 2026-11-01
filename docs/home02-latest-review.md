# Home 02 review update

## Current behavior

- Best Selling uses five visible catalog products with real prices, ordered photos
  and product links. Until sales history exists, selection uses name/ID ordering;
  it is not a ranking based on completed sales.
- Featured cards have dedicated image, price, title, stock and action rows, scoped
  separately from captured card classes to prevent inherited image offsets.
- Homepage product cards share green split Add to Cart / wishlist controls.
  Out-of-stock cart actions are disabled. Stock labels omit the measuring unit.
- Best Selling and Top Rated photos have no themed grey padding/background.
- The middle hero uses up to three live product photos in a six-second Swiper
  carousel. The two smaller panels are photo-only links to live catalog products.
- Banner links use URL-encoded category names and open Shop with matching products
  and descendants. Category-name matching is case-insensitive; numeric bookmarks
  remain supported. Selected child-category filters persist in the filter form.
- Desktop Top Categories uses six category rows, prioritizing populated categories.
  Images are round and the original single-panel presentation is retained.
- At 1024px and below, Shop by Department uses active parent categories below the
  banners and above the offer ticker. It has larger round photos, centered names,
  hidden product counts, swipe/arrow navigation and six-second automatic scrolling.
  Autoplay respects reduced motion, visibility, focus and pointer interaction.
- At the same breakpoint, the two smaller hero photos are hidden and only the
  main slider occupies the banner area.

## Verification and review limits

Nonvisual checks for this update: Django system check, migration-drift check,
affected Python lint/format, JavaScript syntax and staged whitespace checks.
The Featured template also rendered with synthetic context and separate photo,
price and action sections without a browser or database write.

Visual QA, browser interaction checks and screenshots remain on the user's hold.
The latest layout is not visually verified. Updated Home 02 and Shop regression
tests are included, but the suite was not rerun for this PR update. An earlier
Home 02 test run encountered an existing sale fixture with no required discount;
that broader test limitation is not a passing result for the current candidate.

Basket and wishlist remain in-memory previews. Checkout and persisted carts are
not connected. No admin interface, shared model or schema changes are included in
this update; earlier product-page migration 0011 remains part of the overall PR.
No merge or production deployment is performed.
