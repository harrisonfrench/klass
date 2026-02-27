"""Billing Blueprint - Stripe integration for subscriptions."""

import os
import stripe
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
from app.db_connect import get_db
from app.blueprints.auth import login_required

billing = Blueprint('billing', __name__)

# Initialize Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Pricing configuration
PRICING = {
    'pro_monthly': {
        'name': 'Pro Monthly',
        'price': 799,  # $7.99 in cents
        'interval': 'month',
        'features': [
            'Unlimited AI calls',
            'Unlimited flashcards',
            'Unlimited quizzes',
            'Priority support',
            'Advanced analytics',
        ]
    },
    'pro_yearly': {
        'name': 'Pro Yearly',
        'price': 4999,  # $49.99 in cents (save ~48%)
        'interval': 'year',
        'features': [
            'Everything in Pro Monthly',
            'Save 48% vs monthly',
            'Early access to new features',
        ]
    }
}


def get_user_subscription(user_id):
    """Get the current subscription for a user."""
    db = get_db()
    cursor = db.execute('''
        SELECT * FROM subscriptions WHERE user_id = %s
    ''', (user_id,))
    sub = cursor.fetchone()

    if not sub:
        # Create free subscription record
        db.execute('''
            INSERT INTO subscriptions (user_id, plan, status)
            VALUES (%s, 'free', 'active')
        ''', (user_id,))
        db.commit()
        return {'plan': 'free', 'status': 'active'}

    return sub


def is_pro_user(user_id):
    """Check if user has an active pro subscription."""
    sub = get_user_subscription(user_id)
    return sub['plan'] in ('pro_monthly', 'pro_yearly') and sub['status'] == 'active'


def get_or_create_stripe_customer(user_id):
    """Get or create a Stripe customer for the user."""
    db = get_db()

    # Get user info
    cursor = db.execute('SELECT email, username FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()

    # Get subscription
    cursor = db.execute('SELECT stripe_customer_id FROM subscriptions WHERE user_id = %s', (user_id,))
    sub = cursor.fetchone()

    if sub and sub.get('stripe_customer_id'):
        return sub['stripe_customer_id']

    # Create Stripe customer
    customer = stripe.Customer.create(
        email=user['email'],
        name=user['username'],
        metadata={'user_id': str(user_id)}
    )

    # Save customer ID
    if sub:
        db.execute('''
            UPDATE subscriptions SET stripe_customer_id = %s WHERE user_id = %s
        ''', (customer.id, user_id))
    else:
        db.execute('''
            INSERT INTO subscriptions (user_id, stripe_customer_id, plan, status)
            VALUES (%s, %s, 'free', 'active')
        ''', (user_id, customer.id))
    db.commit()

    return customer.id


@billing.route('/')
@login_required
def pricing_page():
    """Display pricing page."""
    user_id = session['user_id']
    subscription = get_user_subscription(user_id)

    return render_template('billing/pricing.html',
        pricing=PRICING,
        subscription=subscription,
        is_pro=is_pro_user(user_id)
    )


@billing.route('/checkout/<plan>')
@login_required
def checkout(plan):
    """Create Stripe checkout session."""
    if plan not in PRICING:
        flash('Invalid plan selected.', 'error')
        return redirect(url_for('billing.pricing_page'))

    user_id = session['user_id']

    # Check if already subscribed
    if is_pro_user(user_id):
        flash('You already have an active Pro subscription.', 'info')
        return redirect(url_for('billing.manage'))

    try:
        customer_id = get_or_create_stripe_customer(user_id)

        # Get or create the price in Stripe
        price_data = PRICING[plan]

        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Klass {price_data["name"]}',
                        'description': 'AI-powered study assistant',
                    },
                    'unit_amount': price_data['price'],
                    'recurring': {
                        'interval': price_data['interval'],
                    },
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('billing.success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('billing.pricing_page', _external=True),
            metadata={
                'user_id': str(user_id),
                'plan': plan,
            }
        )

        return redirect(checkout_session.url)

    except stripe.error.StripeError as e:
        flash(f'Payment error: {str(e)}', 'error')
        return redirect(url_for('billing.pricing_page'))


@billing.route('/success')
@login_required
def success():
    """Handle successful checkout."""
    session_id = request.args.get('session_id')

    if session_id:
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)

            if checkout_session.payment_status == 'paid':
                # Update subscription in database
                user_id = session['user_id']
                plan = checkout_session.metadata.get('plan', 'pro_monthly')

                db = get_db()
                db.execute('''
                    UPDATE subscriptions
                    SET plan = %s,
                        status = 'active',
                        stripe_subscription_id = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                ''', (plan, checkout_session.subscription, user_id))
                db.commit()

                flash('Welcome to Klass Pro! Your subscription is now active.', 'success')
        except stripe.error.StripeError:
            pass

    return redirect(url_for('billing.manage'))


@billing.route('/manage')
@login_required
def manage():
    """Manage subscription page."""
    user_id = session['user_id']
    subscription = get_user_subscription(user_id)

    # Get payment history
    db = get_db()
    cursor = db.execute('''
        SELECT * FROM payments
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 10
    ''', (user_id,))
    payments = cursor.fetchall()

    return render_template('billing/manage.html',
        subscription=subscription,
        payments=payments,
        pricing=PRICING,
        is_pro=is_pro_user(user_id)
    )


@billing.route('/portal')
@login_required
def customer_portal():
    """Redirect to Stripe Customer Portal for subscription management."""
    user_id = session['user_id']

    try:
        customer_id = get_or_create_stripe_customer(user_id)

        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=url_for('billing.manage', _external=True),
        )

        return redirect(portal_session.url)

    except stripe.error.StripeError as e:
        flash(f'Error accessing billing portal: {str(e)}', 'error')
        return redirect(url_for('billing.manage'))


@billing.route('/webhook', methods=['POST'])
def webhook():
    """Handle Stripe webhooks."""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({'error': 'Invalid signature'}), 400

    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session_data = event['data']['object']
        handle_checkout_completed(session_data)

    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        handle_subscription_updated(subscription)

    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        handle_subscription_deleted(subscription)

    elif event['type'] == 'invoice.paid':
        invoice = event['data']['object']
        handle_invoice_paid(invoice)

    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        handle_payment_failed(invoice)

    return jsonify({'status': 'success'})


def handle_checkout_completed(session_data):
    """Handle successful checkout."""
    user_id = session_data.get('metadata', {}).get('user_id')
    if not user_id:
        return

    db = get_db()
    plan = session_data.get('metadata', {}).get('plan', 'pro_monthly')

    db.execute('''
        UPDATE subscriptions
        SET plan = %s,
            status = 'active',
            stripe_subscription_id = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = %s
    ''', (plan, session_data.get('subscription'), user_id))
    db.commit()


def handle_subscription_updated(subscription):
    """Handle subscription update (upgrade, downgrade, renewal)."""
    db = get_db()

    # Find user by stripe subscription ID
    cursor = db.execute('''
        SELECT user_id FROM subscriptions WHERE stripe_subscription_id = %s
    ''', (subscription['id'],))
    row = cursor.fetchone()

    if not row:
        return

    status = subscription['status']
    cancel_at_period_end = subscription.get('cancel_at_period_end', False)

    db.execute('''
        UPDATE subscriptions
        SET status = %s,
            cancel_at_period_end = %s,
            current_period_start = FROM_UNIXTIME(%s),
            current_period_end = FROM_UNIXTIME(%s),
            updated_at = CURRENT_TIMESTAMP
        WHERE stripe_subscription_id = %s
    ''', (
        status,
        1 if cancel_at_period_end else 0,
        subscription['current_period_start'],
        subscription['current_period_end'],
        subscription['id']
    ))
    db.commit()


def handle_subscription_deleted(subscription):
    """Handle subscription cancellation."""
    db = get_db()

    db.execute('''
        UPDATE subscriptions
        SET plan = 'free',
            status = 'canceled',
            stripe_subscription_id = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE stripe_subscription_id = %s
    ''', (subscription['id'],))
    db.commit()


def handle_invoice_paid(invoice):
    """Handle successful payment."""
    db = get_db()

    # Find user by customer ID
    cursor = db.execute('''
        SELECT user_id FROM subscriptions WHERE stripe_customer_id = %s
    ''', (invoice['customer'],))
    row = cursor.fetchone()

    if not row:
        return

    # Record payment
    db.execute('''
        INSERT INTO payments (user_id, stripe_payment_intent_id, amount, currency, status, description)
        VALUES (%s, %s, %s, %s, 'succeeded', %s)
    ''', (
        row['user_id'],
        invoice.get('payment_intent'),
        invoice['amount_paid'],
        invoice['currency'],
        f"Subscription payment - {invoice.get('billing_reason', 'renewal')}"
    ))
    db.commit()


def handle_payment_failed(invoice):
    """Handle failed payment."""
    db = get_db()

    # Find user by customer ID
    cursor = db.execute('''
        SELECT user_id FROM subscriptions WHERE stripe_customer_id = %s
    ''', (invoice['customer'],))
    row = cursor.fetchone()

    if not row:
        return

    # Record failed payment
    db.execute('''
        INSERT INTO payments (user_id, stripe_payment_intent_id, amount, currency, status, description)
        VALUES (%s, %s, %s, %s, 'failed', %s)
    ''', (
        row['user_id'],
        invoice.get('payment_intent'),
        invoice['amount_due'],
        invoice['currency'],
        'Payment failed'
    ))

    # Update subscription status
    db.execute('''
        UPDATE subscriptions
        SET status = 'past_due',
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = %s
    ''', (row['user_id'],))
    db.commit()
