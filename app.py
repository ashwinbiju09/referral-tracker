from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from dotenv import load_dotenv
import os
import random
import string
import bcrypt
from math import ceil
from datetime import datetime
from functools import wraps

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# MySQL configuration
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

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

# Function to generate Member ID


def generate_member_id():
    while True:
        member_id = 'NVO' + ''.join(random.choices(string.digits, k=6))
        cursor = mysql.connection.cursor()
        cursor.execute(
            "SELECT 1 FROM members WHERE member_id = %s", (member_id,))
        if not cursor.fetchone():
            return member_id

# Decorator to enforce login


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Login route


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == ADMIN_USERNAME and bcrypt.checkpw(password.encode('utf-8'), ADMIN_PASSWORD.encode('utf-8')):
            session['user'] = username
            flash('Login successful!', 'success')
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password", "danger")
    return render_template("login.html")

# Logout route


@app.route("/logout")
def logout():
    session.pop('user', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# Home page


@app.route('/home')
@login_required
def index():
    cursor = mysql.connection.cursor()

    # Fetch total number of referrers
    cursor.execute("SELECT COUNT(*) AS total FROM referrers")
    total_referrers = cursor.fetchone()['total']

    # Fetch total number of successful references (purchase_count = 2)
    cursor.execute("""
        SELECT COUNT(*) AS successful_references 
        FROM referees 
        WHERE purchase_count = 2
    """)
    successful_references = cursor.fetchone()['successful_references']

    # Fetch total references (counting unique referees)
    cursor.execute("""
        SELECT COUNT(*) AS total_references 
        FROM referees
    """)
    total_references = cursor.fetchone()['total_references'] or 0

    # Fetch total members count
    cursor.execute("""
        SELECT COUNT(*) AS total_members
        FROM members
    """)
    total_members = cursor.fetchone()['total_members'] or 0

    cursor.close()

    return render_template(
        'index.html',
        total_referrers=total_referrers,
        successful_references=successful_references,
        total_references=total_references,
        total_members=total_members  # Pass total_members to the template
    )


# Add a referrer


@app.route('/add_referrer', methods=['POST'])
@login_required
def add_referrer():
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    contact = request.form.get('contact')
    referral_code = generate_referral_code()

    cursor = mysql.connection.cursor()
    cursor.execute(
        "INSERT INTO referrers (first_name, last_name, contact, referral_code, total_references) VALUES (%s, %s, %s, %s, 0)",
        (first_name, last_name, contact, referral_code)
    )
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('index'))

# View all referrers


@app.route('/referrers')
@login_required
def view_referrers():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    cursor = mysql.connection.cursor()
    # Fetch referrers with dynamically calculated total_references
    cursor.execute("""
        SELECT r.id, r.first_name, r.last_name, r.contact, r.referral_code, 
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
@login_required
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
@login_required
def search_referral():
    if request.method == 'POST':
        referral_code = request.form.get('referral_code').upper()
    else:
        referral_code = request.args.get('referral_code', '').upper()

    cursor = mysql.connection.cursor()

    # Fetch the referrer
    cursor.execute(
        "SELECT * FROM referrers WHERE referral_code = %s", (referral_code,)
    )
    referrer = cursor.fetchone()

    if referrer:
        # Dynamically calculate the total references
        cursor.execute(
            "SELECT COUNT(*) AS total_references FROM referees WHERE referrer_id = %s", (
                referrer['id'],)
        )
        total_references = cursor.fetchone()['total_references']
        referrer['total_references'] = total_references

        # Calculate successful references (referees with 2 purchases)
        cursor.execute(
            "SELECT COUNT(*) AS successful_references FROM referees WHERE referrer_id = %s AND purchase_count = 2",
            (referrer['id'],)
        )
        successful_references = cursor.fetchone()['successful_references']
        referrer['successful_references'] = successful_references

        # Fetch referees for this referrer
        cursor.execute(
            "SELECT * FROM referees WHERE referrer_id = %s", (referrer['id'],)
        )
        referees = cursor.fetchall()

        cursor.close()
        return render_template('search_result.html', referrer=referrer, referees=referees)
    else:
        cursor.close()
        return redirect('/')


# Add a referee


@app.route('/add_referee', methods=['POST'])
@login_required
def add_referee():
    referral_code = request.form.get('referral_code').upper()
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    purchase_count = int(request.form.get('purchase_count'))
    date_of_purchase = datetime.now()

    cursor = mysql.connection.cursor()
    cursor.execute(
        "SELECT * FROM referrers WHERE referral_code = %s", (referral_code,)
    )
    referrer = cursor.fetchone()

    if referrer:
        referrer_id = referrer['id']

        # Check if the referee already exists
        cursor.execute(
            "SELECT * FROM referees WHERE referrer_id = %s AND first_name = %s AND last_name = %s",
            (referrer_id, first_name, last_name)
        )
        referee = cursor.fetchone()

        if referee:
            # Check if the purchase_count transitions to 3
            if purchase_count == 2 and referee['purchase_count'] < 2:
                cursor.execute(
                    "UPDATE referrers SET total_references = total_references + 1 WHERE id = %s",
                    (referrer_id,)
                )

            # Update referee purchase_count and date_of_purchase
            cursor.execute(
                """
                UPDATE referees 
                SET purchase_count = %s, date_of_purchase = %s 
                WHERE id = %s
                """,
                (purchase_count, date_of_purchase, referee['id'])
            )
        else:
            # Insert a new referee and check if purchase_count is already 3
            cursor.execute(
                """
                INSERT INTO referees (referrer_id, first_name, last_name, purchase_count, date_of_purchase) 
                VALUES (%s, %s, %s, %s, %s)
                """,
                (referrer_id, first_name, last_name,
                 purchase_count, date_of_purchase)
            )
            if purchase_count == 2:
                cursor.execute(
                    "UPDATE referrers SET total_references = total_references + 1 WHERE id = %s",
                    (referrer_id,)
                )
        mysql.connection.commit()
    else:
        print("Referrer not found.")
        cursor.close()
        return "Referrer not found. Please check the referral code.", 404

    cursor.close()
    return redirect(url_for('search_referral', referral_code=referral_code))

# Delete a referee


@app.route('/delete_referee/<int:referee_id>', methods=['POST'])
@login_required
def delete_referee(referee_id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM referees WHERE id = %s", (referee_id,))
    mysql.connection.commit()
    cursor.close()
    return redirect(request.referrer)


@app.route('/update_referee', methods=['POST'])
@login_required
def update_referee():
    referral_code = request.form.get('referral_code')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    purchase_count = int(request.form.get('purchase_count'))
    date_of_purchase = datetime.now()

    cursor = mysql.connection.cursor()

    # Fetch the referrer
    cursor.execute(
        "SELECT id FROM referrers WHERE referral_code = %s", (referral_code,))
    referrer = cursor.fetchone()

    if referrer:
        referrer_id = referrer['id']

        # Fetch the referee
        cursor.execute(
            "SELECT * FROM referees WHERE referrer_id = %s AND first_name = %s AND last_name = %s",
            (referrer_id, first_name, last_name)
        )
        referee = cursor.fetchone()

        if referee:
            # Increment total_references only if updating to 3
            if purchase_count == 3 and referee['purchase_count'] < 3:
                cursor.execute(
                    "UPDATE referrers SET total_references = total_references + 1 WHERE id = %s",
                    (referrer_id,)
                )

            # Update referee purchase_count and date_of_purchase
            cursor.execute(
                """
                UPDATE referees 
                SET purchase_count = %s, date_of_purchase = %s 
                WHERE id = %s
                """,
                (purchase_count, date_of_purchase, referee['id'])
            )
            mysql.connection.commit()

    cursor.close()
    return redirect(url_for('search_referral', referral_code=referral_code))

# Route to display members


@app.route('/members')
@login_required
def view_members():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM members LIMIT %s OFFSET %s",
                   (per_page, offset))
    members = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) AS total FROM members")
    total = cursor.fetchone()['total']
    total_pages = ceil(total / per_page)

    cursor.close()
    return render_template('members.html', members=members, page=page, total_pages=total_pages)


# Route to add a member
@app.route('/add_member', methods=['POST'])
@login_required
def add_member():
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    contact = request.form.get('contact')
    member_id = generate_member_id()

    cursor = mysql.connection.cursor()
    cursor.execute(
        "INSERT INTO members (member_id, first_name, last_name, contact, total_purchase_amount) VALUES (%s, %s, %s, %s, 0.00)",
        (member_id, first_name, last_name, contact)
    )
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('view_members'))


# Route to delete a member
@app.route('/delete_member/<int:member_id>', methods=['POST'])
@login_required
def delete_member(member_id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM members WHERE id = %s", (member_id,))
    mysql.connection.commit()
    cursor.close()
    return redirect(url_for('view_members'))


@app.route('/update_member/<int:member_id>', methods=['POST'])
@login_required
def update_member(member_id):
    purchase_amount = float(request.form.get('purchase_amount'))

    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE members
        SET total_purchase_amount = total_purchase_amount + %s
        WHERE id = %s
    """, (purchase_amount, member_id))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('view_members'))


if __name__ == '__main__':
    app.run(debug=True)
