# ShopSphere E-Commerce Platform — Product Requirements Document

ShopSphere is a web-based e-commerce platform where shoppers register an
account, browse and search a product catalog, manage a cart, check out with
multiple payment methods, and track and manage their orders. This document
defines the functional requirements, validation rules, business rules, and
error handling for the platform's 10 core modules: Login, Registration,
Dashboard, Product Search, Product Details, Add to Cart, Checkout, Payment,
Order History, and Account Settings. Each section below is the single
source of truth for that module's expected behavior and should be used to
derive positive, negative, and edge-case QA test cases.

## Module 1: Login

The Login module authenticates a returning user with an email and password.

Functional requirements:

- The Login page presents an Email field, a Password field (masked, with a
  show/hide toggle), a "Remember me" checkbox, a "Forgot password?" link, a
  Login button, and a "Sign up" link for new users.
- A registered, verified, non-disabled account with the correct email and
  password is redirected to the Dashboard on successful login.
- "Remember me" checked issues a persistent session valid for 30 days;
  unchecked issues a session that expires after 24 hours of inactivity or
  when the browser is closed.
- A successful login resets the account's failed-attempt counter and
  records an audit entry (timestamp, IP address, device) visible later
  under Account Settings > Security.
- Logging out invalidates the current session token immediately; any
  further request with that token is rejected as unauthenticated.

Validation and error handling:

- Email is required and must be a syntactically valid email address (max
  254 characters); an empty or malformed email is rejected with an inline
  error before the form submits.
- Password is required; an empty password is rejected with an inline error
  before the form submits.
- An unregistered email and an incorrect password both produce the exact
  same generic error, "Invalid email or password," so that the login
  screen never reveals whether a given email is registered.
- After 5 consecutive failed login attempts for the same account within 15
  minutes, the account is locked for 15 minutes and shows "Account
  temporarily locked. Try again in 15 minutes."; the lockout timer is not
  reset by further attempts while locked.
- Accounts that have been administratively disabled cannot log in and see
  "This account has been disabled. Contact support."
- Accounts that have not yet completed email verification cannot log in
  and see "Please verify your email address before logging in," along with
  a link to resend the verification email.
- More than 20 login attempts from a single IP address within 5 minutes
  triggers a CAPTCHA challenge on the next attempt from that IP.
- Any SQL, script, or HTML injection payload submitted in the email or
  password fields is treated as invalid input, never executed or reflected
  back, and logged as suspicious activity.
- The Login form is fully operable by keyboard alone, and inline
  validation errors are announced without a full page reload.

## Module 2: Registration

The Registration module lets a new shopper create an account.

Functional requirements:

- The Registration form collects Full Name, Email, Password, Confirm
  Password, an optional Phone Number, and requires acceptance of the Terms
  & Conditions and an 18-or-older confirmation before the Sign Up button is
  enabled.
- On successful submission, the account is created in an "unverified"
  state and a verification email with a link valid for 24 hours is sent;
  the user sees a confirmation screen: "Check your email to verify your
  account."
- The user is not automatically logged in after registering — only after
  the verification link is followed is the account activated, after which
  the user is redirected to Login with a "Email verified. Please log in."
  banner.
- A "Resend verification email" action is available and is rate-limited to
  one request per 60 seconds per account.

Validation and error handling:

- Full Name is required, must be 2-100 characters, and may contain only
  letters, spaces, hyphens, and apostrophes; digits or other special
  characters are rejected inline.
- Email is required, must be a valid email format, and must be unique
  across the system; registering with an email already on the platform
  shows "An account with this email already exists. Log in instead?" with
  a link to Login.
- Password is required, must be 8-64 characters, and must contain at least
  one uppercase letter, one lowercase letter, one digit, and one special
  character; passwords found on a common-password blocklist (e.g.,
  "password123") are rejected with "Please choose a stronger password."
- Confirm Password must exactly match Password; a mismatch is shown
  inline as "Passwords do not match" and blocks submission.
- Phone Number, if provided, must be 10-15 digits with an optional leading
  "+" and country code; an invalid format is rejected inline without
  blocking submission of the rest of the form (the field is optional).
- Submitting with the Terms & Conditions checkbox unchecked, or the
  18-or-older checkbox unchecked, is blocked both client-side and
  server-side with "You must accept the terms to continue."
- A verification link that has expired shows "This link has expired.
  Request a new verification email."; a link that has already been used
  once shows "This link has already been used."
- More than 10 registrations from a single IP address within 1 hour
  triggers a CAPTCHA challenge on the next signup attempt from that IP.
- All registration input is sanitized/escaped before storage to prevent
  stored cross-site scripting.

## Module 3: Dashboard

The Dashboard is the personalized landing page shown immediately after
login.

Functional requirements:

- The Dashboard shows a welcome banner with the user's first name, an
  order-summary widget (the 3 most recent orders with status badges:
  Processing, Shipped, Delivered, Cancelled), a personalized product
  recommendations carousel, quick links to Orders/Wishlist/Account
  Settings/Cart, and a notification bell showing an unread count.
- Clicking a row in the order-summary widget navigates to that order's
  detail view in Order History.
- The recommendations carousel shows up to 10 products based on the
  user's browsing/purchase history, falling back to a "Trending Products"
  carousel for users with no history yet.
- The notification bell's dropdown shows the 5 most recent notifications
  (order updates, wishlist price drops, promotions).
- The global search bar on the Dashboard accepts a query and, on Enter,
  navigates to Product Search results for that query.
- Currency and locale shown on the Dashboard reflect the user's saved
  preference in Account Settings.
- Users with an incomplete profile (missing phone number or address) see a
  dismissible banner prompting them to complete their profile.

Validation and error handling:

- A user with zero past orders sees an empty state in the order-summary
  widget: "You haven't placed any orders yet" with a "Start Shopping"
  button linking to Product Search.
- If the recommendations service fails to respond, the rest of the
  Dashboard still renders normally, with only the carousel section
  replaced by a retry message.
- Any Dashboard API call that returns a 401 (expired session) redirects to
  Login with "Your session has expired. Please log in again."
- The layout is responsive: a single column below 640px width, two columns
  on tablet widths, and three columns on desktop widths.
- While data is loading, a skeleton loader is shown instead of an empty or
  broken layout.

## Module 4: Product Search

Product Search lets shoppers find products by keyword and refine results
with filters and sorting.

Functional requirements:

- The search bar accepts free-text queries up to 200 characters, trims
  leading/trailing whitespace, and is case-insensitive.
- Results are paginated at 20 products per page and can be sorted by
  Relevance (default), Price: Low to High, Price: High to Low, Newest
  Arrivals, or Customer Rating.
- Available filters are Category, Price Range, Brand, Customer Rating (4
  stars & up, 3 stars & up, etc.), Availability (In Stock only), and
  Discount (on sale only); multiple selected values within one filter
  combine with OR logic, and different filters combine with AND logic.
- Each result card shows a thumbnail, product name, price (with a
  strikethrough original price when discounted), average rating and
  review count, and a quick "Add to Cart" action.
- Typeahead suggestions appear after 2 or more characters are typed,
  showing up to 8 matching product names or categories, debounced by 300
  milliseconds.
- Fuzzy/typo-tolerant matching is supported (e.g., "phon" returns "phone"
  results) with a "Showing results for 'phone'" hint shown when
  auto-corrected.
- Applied filters and the current sort order are reflected in the URL so
  results are shareable, bookmarkable, and preserved across refresh or
  back navigation.

Validation and error handling:

- Submitting an empty search query shows "Please enter a search term."
  and does not navigate to a results page.
- A query with no matches shows "No products found for '<query>'. Try
  adjusting your filters or search term." along with suggested related
  searches.
- Out-of-stock products remain visible in results (unless "In Stock only"
  is applied), are visually marked "Out of Stock," and have their Add to
  Cart button disabled.
- The Category filter only lists categories actually present in the
  current result set, so a filter selection never leads to a silent
  zero-result dead end.
- SQL, script, or HTML injection payloads typed into the search box are
  safely escaped and never cause a server error or execute as code.
- Search must return results for catalogs up to 100,000 products within
  1.5 seconds.

## Module 5: Product Details

Product Details shows full information for a single product and lets the
shopper choose a variant and quantity before adding it to the cart.

Functional requirements:

- The page shows an image gallery (main image plus up to 8 thumbnails,
  zoomable), product name, brand, price with a discount badge and percent
  off when on sale, average rating and review count, short and full
  descriptions, a specifications table, stock status, a quantity selector,
  Add to Cart and Buy Now buttons, and a wishlist icon.
- Variant selectors (size/color/etc.) update price, image, and stock
  status immediately without a full page reload when a different variant
  is chosen.
- The Specifications table lists only the attributes that exist for the
  product (size, color, material, weight, dimensions); attributes with no
  value are omitted rather than shown blank.
- A breadcrumb (Home > Category > Subcategory > Product Name) reflects the
  product's actual category path, and every segment is a working link.
- Customer Reviews are paginated at 10 per page and sortable by Most
  Recent, Highest Rating, Lowest Rating, or Most Helpful; only shoppers
  who purchased the product may post a review flagged "Verified Buyer."
- "Write a Review" requires the shopper to be logged in; a guest is
  prompted to log in first.
- A "Customers also bought" section shows up to 6 related products from
  the same category.
- Estimated delivery date/time is shown based on the shopper's saved
  address, or a default region if not logged in.

Validation and error handling:

- The quantity selector has a minimum of 1 and a maximum equal to the
  lower of available stock or 10; attempting to exceed the maximum shows
  "Only <N> left in stock." and decrementing below 1 is disabled.
- When stock is 0, Add to Cart and Buy Now are disabled and replaced by a
  "Notify Me When Available" action that captures an email address.
- Selecting a variant that is itself out of stock disables Add to Cart for
  that variant and shows "This variant is currently unavailable."
- If a shopper reaches Product Details for an item that went out of stock
  since the page was cached (e.g., via back navigation), the Add to Cart
  action is re-validated server-side and rejected with "This item just
  went out of stock" rather than silently succeeding.
- The price shown here must always match the price shown later in Cart
  and Checkout for the same variant at the same time.

## Module 6: Add to Cart

The Add to Cart / Cart module holds the shopper's selected items prior to
checkout.

Functional requirements:

- Clicking Add to Cart adds the chosen product, variant, and quantity to
  the cart, shows an "Added to cart" confirmation toast, and updates the
  header cart badge count immediately without a full page reload.
- Adding a product/variant combination that is already in the cart
  increases its quantity rather than creating a second line item, up to
  the maximum allowed.
- For logged-in users the cart is persisted server-side across sessions;
  for guests it is persisted in local storage; on login, a guest cart is
  merged into the account's cart, combining duplicate lines and capping
  quantities at the stock/quantity limit.
- The Cart page lists, per line item: thumbnail, name, selected variant,
  unit price, a quantity stepper, the line subtotal, and a Remove icon.
- The Cart shows a running Subtotal, a Discount line when a coupon is
  applied, and a Total, with tax and shipping shown as "calculated at
  checkout" until an address is available.
- The header cart icon count stays in sync in real time across open tabs
  for the same logged-in user.

Validation and error handling:

- Increasing a line item's quantity beyond available stock clamps it to
  the maximum available and shows "Only <N> left in stock. Quantity
  adjusted."
- Cart quantity is capped at 10 units per line item and 50 total items
  across the cart; exceeding either limit shows a "Maximum quantity
  reached" message and blocks the increment.
- Applying an invalid or expired coupon code shows "This coupon code is
  invalid or has expired." and leaves the cart unchanged; applying a valid
  code shows a success message and the discount applied.
- Only one coupon code may be active at a time; applying a second code
  prompts confirmation before it replaces the first.
- Removing the last item in the cart shows an empty-cart state: "Your
  cart is empty" with a "Continue Shopping" button.
- If an item in the cart becomes unavailable (out of stock or delisted)
  while sitting there, it is flagged "No longer available" and excluded
  from the Subtotal/Total until the shopper removes it.
- If a cart item's price changes between when it was added and when
  checkout is reached, the cart always displays the current price, not
  the price at time of adding.

## Module 7: Checkout

Checkout is the multi-step flow that turns a cart into a placed order:
Shipping Address, Delivery Method, Review Order, Payment, and Order
Confirmation.

Functional requirements:

- Guest checkout is allowed for orders under $500; orders of $500 or more
  require the shopper to be signed in ("Please sign in to complete orders
  over $500.").
- The Shipping Address step collects Full Name, Address Line 1 (Line 2
  optional), City, State/Province, ZIP/Postal Code, Country, and Phone
  Number; logged-in shoppers may pick a saved address, edit it inline, or
  add a new one, optionally saving it for future orders.
- The Delivery Method step offers Standard (5-7 days, free over $50 else
  $5.99), Express (2-3 days, $12.99), and Overnight ($24.99), filtered to
  only the methods actually available for the destination; unavailable
  methods are hidden rather than shown disabled.
- The Review Order step shows all cart line items read-only, the chosen
  address and delivery method, subtotal, discount, estimated tax, shipping
  cost, and grand total, with an "Edit Cart" link that returns to Cart
  without losing the entered address.
- Placing an order requires accepting the Terms of Sale / Return Policy
  checkbox on the Review step.
- On success, a unique Order ID in the format ORD-YYYYMMDD-NNNNN is
  generated, stock is decremented for each purchased item, the cart is
  cleared, and the shopper lands on an Order Confirmation page with the
  Order ID, estimated delivery date, and a link into Order History.
- A confirmation email with the Order ID, itemized list, total, and
  shipping address is sent within 1 minute of order placement.

Validation and error handling:

- If any cart item became unavailable or changed price since it was added,
  the Review step shows "Some items in your cart have changed. Please
  review before continuing." and requires acknowledgment before proceeding.
- The "Place Order" button is disabled while the request is in flight, and
  an idempotency key per checkout session prevents duplicate orders from
  double clicks or network retries.
- If payment fails, the shopper is returned to the Payment step with the
  cart and entered data intact and an error message shown; no order record
  is created for a failed payment.
- The checkout session (cart contents and entered address) times out after
  30 minutes of inactivity, returning the shopper to Cart with "Your
  checkout session expired. Please review your cart."
- Using the browser's back button during checkout never resubmits a form
  or creates a duplicate order.
- Missing or invalid required fields on the Shipping Address step (e.g.,
  a ZIP code that doesn't match the selected country's format) are
  rejected inline before the shopper can proceed to Delivery Method.

## Module 8: Payment

Payment captures and processes payment as part of Checkout.

Functional requirements:

- Supported payment methods are Credit/Debit Card (Visa, MasterCard,
  Amex), PayPal, and Cash on Delivery (COD) — COD only for orders under
  $200 and only in supported regions.
- The card form collects Cardholder Name, Card Number, Expiry Date
  (MM/YY), CVV, and Billing Address, defaulting to "same as shipping" with
  an editable override.
- Only a tokenized reference from the payment gateway plus the card's
  brand and last 4 digits (e.g., "Visa ending in 4242") are ever retained;
  full card numbers and CVV are never stored or logged in plaintext
  anywhere, including application logs and analytics.
- PayPal redirects to PayPal's hosted flow and returns to Order
  Confirmation on success, or back to Checkout with an error banner if the
  shopper cancels or the PayPal attempt fails.
- Cash on Delivery adds a $2.99 handling fee to the order total, shown
  before order placement, and is not offered when the cart exceeds $200 or
  contains an item marked "COD not eligible."
- A payment must be captured (or authorized then captured, per gateway
  configuration) before an order is marked "Confirmed"; a failed capture
  rolls the order back to a "Payment Failed" state visible in Order
  History.
- Refunds are issued to the original payment method and progress from
  "Refund Initiated" to "Refunded," with an expected 5-7 business day
  timeline shown to the shopper.

Validation and error handling:

- Card Number is validated client-side with the Luhn checksum and must
  match a recognized brand's prefix/length (Visa 13/16/19 digits starting
  with 4; MasterCard 16 digits starting 51-55 or 2221-2720; Amex 15 digits
  starting 34/37); an invalid number shows "Please enter a valid card
  number."
- Expiry Date must be a valid month (01-12) and not already in the past
  relative to the current month/year; an expired card shows "This card has
  expired."
- CVV must be exactly 3 digits (4 for Amex) and numeric only; any other
  length or non-numeric input blocks submission.
- A declined payment (insufficient funds, bank decline, expired card)
  shows the generic message "Your payment was declined. Please try a
  different payment method or contact your bank." without exposing raw
  gateway error codes.
- A gateway timeout with no response within 30 seconds shows "Payment
  could not be processed. Please try again." and never creates a partial
  or duplicate order.
- Cards that require 3D Secure/OTP step-up authentication are challenged
  before capture; failing or abandoning that step returns the shopper to
  Payment with the order not placed.
- The currency charged always matches the currency displayed throughout
  Checkout for the shopper's selected region.

## Module 9: Order History

Order History lets shoppers view, track, cancel, and return past and
current orders.

Functional requirements:

- Orders are listed most-recent-first, paginated at 10 per page, each row
  showing Order ID, order date, item count/thumbnail preview, total
  amount, and current status (Processing, Shipped, Out for Delivery,
  Delivered, Cancelled, Payment Failed, Refunded).
- Opening an order shows its detail view: itemized products (name,
  variant, quantity, price), the shipping address used, a masked payment
  method, the subtotal/discount/tax/shipping/total breakdown, and a
  shipment tracking timeline with a timestamp for each status change.
- Order History can be filtered by status (All, Processing, Shipped,
  Delivered, Cancelled, Refunded) and by date range (Last 30 days, Last 6
  months, Last year, Custom range), and searched by Order ID or product
  name within the shopper's own orders only.
- A "Download Invoice" action produces a PDF receipt for any completed
  order.
- A "Buy Again" action on a past order adds all still-available items from
  it back into the current cart, skips any discontinued/out-of-stock
  items, and shows a summary of what was and wasn't added.
- Once an order reaches "Shipped," a carrier name and tracking number
  appear on the detail view with a deep link to the carrier's tracking
  page.

Validation and error handling:

- An order can be cancelled by the shopper via "Cancel Order" only while
  it is in "Processing" status and within 1 hour of placement; a
  confirmation dialog must be accepted before cancellation proceeds.
- Once an order has moved to "Shipped" or later, Cancel Order is hidden,
  and a "Request Return" option becomes available for up to 30 days after
  delivery instead.
- Cancelling an eligible order immediately restores stock, sets status to
  "Cancelled," and triggers a refund per the Payment module's refund rules
  if payment had already been captured.
- A return request requires a reason chosen from Defective, Wrong Item, No
  Longer Needed, or Other; choosing Other requires a free-text explanation
  up to 500 characters.
- A shopper with no orders at all sees an empty state, "No orders yet,"
  with a "Start Shopping" link.

## Module 10: Account Settings

Account Settings lets shoppers manage their profile, addresses, security,
notification preferences, and saved payment methods, organized into
Profile, Addresses, Security, Notifications, and Payment Methods tabs.

Functional requirements:

- The Profile tab edits Full Name, Email, Phone Number, Date of Birth, and
  a profile photo (JPEG/PNG, max 5MB); changing Email requires
  re-verification via a confirmation link sent to the new address, with
  the old email remaining active until confirmed.
- The Addresses tab supports adding, editing, and deleting saved shipping
  addresses using the same validation rules as Checkout's Shipping Address
  step; exactly one address can be marked Default, and deleting the
  Default address prompts the shopper to choose a new one (or clears the
  default if none remain).
- The Security tab supports changing the password (requiring the current
  password plus a new one meeting Registration's complexity rules), shows
  the last 10 login events (date, IP/location, device), and offers "Log
  out of all devices," which invalidates every active session except the
  current one.
- Two-factor authentication (TOTP authenticator app) can be enabled or
  disabled from the Security tab; once enabled, login requires a 6-digit
  code in addition to the password, and disabling 2FA requires re-entering
  the current password.
- The Notifications tab lets the shopper independently toggle email/SMS
  preferences for Order Updates, Promotions, Price Drop Alerts, and
  Newsletter; Order Updates cannot be fully disabled (critical
  order-status emails always send), while Promotions and Newsletter can be
  fully opted out.
- The Payment Methods tab lists saved cards (masked) and any linked
  PayPal account, and supports adding a new card (validated the same way
  as the Payment module) or removing an existing one; removing a card used
  by a pending order does not affect that order's already-authorized
  payment.
- Any change on the Security tab (password change, 2FA toggle, device
  logout) sends a security-alert email to the account's registered
  address.

Validation and error handling:

- Attempting to change Email to an address already associated with another
  account shows "This email is already associated with another account."
- Deleting the account requires re-entering the password and typing
  "DELETE" to confirm; deletion is soft (the account can be reactivated by
  logging back in during a 30-day retention window) before being
  permanently purged.
- Every field on Account Settings validates inline using the same rules as
  its originating flow (e.g., email format, phone format, address format)
  and shows a "Changes saved" toast on success, or a specific inline error
  on failure without discarding the shopper's other unsaved edits.
