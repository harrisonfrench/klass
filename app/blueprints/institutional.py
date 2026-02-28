"""Institutional Blueprint - Campus and institutional features."""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from app.services.lms_service import INSTITUTION_TIERS

institutional = Blueprint('institutional', __name__)


@institutional.route('/')
def landing():
    """Institutional landing page for campuses."""
    return render_template('institutional/landing.html', tiers=INSTITUTION_TIERS)


@institutional.route('/pricing')
def pricing():
    """Detailed pricing for institutions."""
    return render_template('institutional/pricing.html', tiers=INSTITUTION_TIERS)


@institutional.route('/demo', methods=['GET', 'POST'])
def request_demo():
    """Request a demo form."""
    if request.method == 'POST':
        # Collect form data
        data = {
            'name': request.form.get('name'),
            'email': request.form.get('email'),
            'institution': request.form.get('institution'),
            'role': request.form.get('role'),
            'students': request.form.get('students'),
            'lms': request.form.get('lms'),
            'message': request.form.get('message')
        }

        # In production, this would send an email or create a lead in CRM
        flash('Thank you! We\'ll be in touch within 24 hours to schedule your demo.', 'success')
        return redirect(url_for('institutional.landing'))

    return render_template('institutional/demo.html')


@institutional.route('/features')
def features():
    """Institutional features overview."""
    return render_template('institutional/features.html')


@institutional.route('/security')
def security():
    """Security and compliance documentation."""
    return render_template('institutional/security.html')


@institutional.route('/api/quote', methods=['POST'])
def get_quote():
    """Get a custom quote based on student count."""
    data = request.get_json()
    student_count = data.get('students', 0)

    if student_count <= 0:
        return jsonify({'error': 'Invalid student count'}), 400

    # Calculate pricing
    if student_count <= 500:
        tier = 'starter'
        price_per_user = INSTITUTION_TIERS['starter']['price_per_user_monthly']
    elif student_count <= 5000:
        tier = 'professional'
        price_per_user = INSTITUTION_TIERS['professional']['price_per_user_monthly']
    else:
        tier = 'enterprise'
        price_per_user = None  # Custom pricing

    if price_per_user:
        monthly_total = student_count * price_per_user
        annual_total = monthly_total * 12 * 0.8  # 20% annual discount
    else:
        monthly_total = None
        annual_total = None

    return jsonify({
        'success': True,
        'tier': tier,
        'tier_name': INSTITUTION_TIERS[tier]['name'],
        'student_count': student_count,
        'price_per_user': price_per_user,
        'monthly_total': round(monthly_total, 2) if monthly_total else None,
        'annual_total': round(annual_total, 2) if annual_total else None,
        'features': INSTITUTION_TIERS[tier]['features']
    })
