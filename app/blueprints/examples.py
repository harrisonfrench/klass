from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.db_connect import get_db

examples = Blueprint('examples', __name__)

@examples.route('/', methods=['GET', 'POST'])
def show_examples():
    db = get_db()
    cursor = db.cursor()

    # Handle POST request to add a new example
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        date_of_birth = request.form['date_of_birth']

        # Insert the new example into the database
        cursor.execute('INSERT INTO sample_table (first_name, last_name, date_of_birth) VALUES (%s, %s, %s)',
                       (first_name, last_name, date_of_birth))
        db.commit()

        flash('New example added successfully!', 'success')
        return redirect(url_for('examples.show_examples'))

    # Handle GET request to display all examples
    cursor.execute('SELECT * FROM sample_table')
    all_examples = cursor.fetchall()
    return render_template('examples.html', all_examples=all_examples)

@examples.route('/update_example/<int:sample_id>', methods=['POST'])
def update_example(sample_id):
    db = get_db()
    cursor = db.cursor()

    # Update the example's details
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    date_of_birth = request.form['date_of_birth']

    cursor.execute('UPDATE sample_table SET first_name = %s, last_name = %s, date_of_birth = %s WHERE sample_table_id = %s',
                   (first_name, last_name, date_of_birth, sample_id))
    db.commit()

    flash('Example updated successfully!', 'success')
    return redirect(url_for('examples.show_examples'))

@examples.route('/delete_example/<int:sample_id>', methods=['POST'])
def delete_example(sample_id):
    db = get_db()
    cursor = db.cursor()

    # Delete the example
    cursor.execute('DELETE FROM sample_table WHERE sample_table_id = %s', (sample_id,))
    db.commit()

    flash('Example deleted successfully!', 'danger')
    return redirect(url_for('examples.show_examples'))

