from flask import Flask, render_template, request, redirect, url_for
from flask_mysqldb import MySQL
from dotenv import load_dotenv
import os
import random
import string
from math import ceil

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# MySQL configuration
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# Generate random referral code


def generate_referral_code():
    while True:
        code = ''.join(random.choices(
            string.ascii_uppercase + string.digits, k=6))
        cursor = mysql.connection.cursor()
        cursor.execute(
            "SELECT 1 FROM referrers WHERE referral_code = %s", (code,))
        if not cursor.fetchone():
            return code

# Home page


@app.route('/')
def index():
    return render_template('index.html')

# Add a referrer


@app.route('/add_referrer', methods=['POST'])
def add_referrer():
    name = request.form.get('name')
    contact = request.form.get('contact')
    referral_code = generate_referral_code()

    cursor = mysql.connection.cursor()
    cursor.execute(
        "INSERT INTO referrers (name, contact, referral_code, total_references) VALUES (%s, %s, %s, 0)",
        (name, contact, referral_code)
    )
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('index'))

# View all referrers


@app.route('/referrers')
def view_referrers():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    cursor = mysql.connection.cursor()
    # Fetch referrers with dynamically calculated total_references
    cursor.execute("""
        SELECT r.id, r.name, r.contact, r.referral_code, 
               (SELECT COUNT(*) FROM referees WHERE referees.referrer_id = r.id) AS total_references
        FROM referrers r
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    referrers = cursor.fetchall()

    # Fetch the total number of referrers for pagination
    cursor.execute("SELECT COUNT(*) AS total FROM referrers")
    total = cursor.fetchone()['total']
    total_pages = ceil(total / per_page)

    cursor.close()
    return render_template('referrers.html', referrers=referrers, page=page, total_pages=total_pages)

# Delete referrers


@app.route('/delete_referrer/<int:referrer_id>', methods=['POST'])
def delete_referrer(referrer_id):
    cursor = mysql.connection.cursor()

    # Delete all referees associated with the referrer
    cursor.execute(
        "DELETE FROM referees WHERE referrer_id = %s", (referrer_id,))

    # Delete the referrer
    cursor.execute("DELETE FROM referrers WHERE id = %s", (referrer_id,))

    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('view_referrers'))

# Search referral codes


@app.route('/search_referral', methods=['GET', 'POST'])
def search_referral():
    if request.method == 'POST':
        referral_code = request.form.get('referral_code').upper()
    else:
        referral_code = request.args.get('referral_code', '').upper()

    cursor = mysql.connection.cursor()

    # Fetch the referrer
    cursor.execute(
        "SELECT * FROM referrers WHERE referral_code = %s", (referral_code,))
    referrer = cursor.fetchone()

    if referrer:
        # Dynamically calculate the total references
        cursor.execute(
            "SELECT COUNT(*) AS total_references FROM referees WHERE referrer_id = %s", (referrer['id'],))
        total_references = cursor.fetchone()['total_references']
        referrer['total_references'] = total_references

        # Fetch referees for this referrer
        cursor.execute(
            "SELECT * FROM referees WHERE referrer_id = %s", (referrer['id'],))
        referees = cursor.fetchall()
        cursor.close()
        return render_template('search_result.html', referrer=referrer, referees=referees)
    else:
        cursor.close()
        return redirect('/')

# Add a referee


@app.route('/add_referee', methods=['POST'])
def add_referee():
    referral_code = request.form.get('referral_code').upper()
    name = request.form.get('name')
    purchase_count = int(request.form.get('purchase_count'))

    cursor = mysql.connection.cursor()
    cursor.execute(
        "SELECT * FROM referrers WHERE referral_code = %s", (referral_code,))
    referrer = cursor.fetchone()

    if referrer:
        referrer_id = referrer['id']

        cursor.execute(
            "SELECT * FROM referees WHERE referrer_id = %s AND name = %s", (
                referrer_id, name)
        )
        referee = cursor.fetchone()

        if referee:
            cursor.execute(
                "UPDATE referees SET purchase_count = %s WHERE id = %s", (
                    purchase_count, referee['id'])
            )
        else:
            cursor.execute(
                "INSERT INTO referees (referrer_id, name, purchase_count) VALUES (%s, %s, %s)",
                (referrer_id, name, purchase_count)
            )
        mysql.connection.commit()
    cursor.close()
    return redirect(url_for('search_referral', referral_code=referral_code))


# Delete a referee

@app.route('/delete_referee/<int:referee_id>', methods=['POST'])
def delete_referee(referee_id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM referees WHERE id = %s", (referee_id,))
    mysql.connection.commit()
    cursor.close()
    return redirect(request.referrer)


if __name__ == '__main__':
    app.run(debug=True)
