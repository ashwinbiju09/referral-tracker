from flask import Flask, render_template, request, redirect
from flask_mysqldb import MySQL
from datetime import datetime
import random
import string
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# MySQL configuration using environment variables
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# Function to generate a random referral code


def generate_referral_code():
    while True:
        code = ''.join(random.choices(
            string.ascii_uppercase + string.digits, k=6))
        cursor = mysql.connection.cursor()
        cursor.execute(
            "SELECT 1 FROM referrers WHERE referral_code = %s", (code,))
        if not cursor.fetchone():
            return code

# Routes


@app.route('/')
def index():
    cursor = mysql.connection.cursor()  # No need to specify dictionary=True
    cursor.execute("SELECT * FROM referrers")
    referrers = cursor.fetchall()

    for referrer in referrers:
        # Fetch referees for each referrer
        cursor.execute(
            "SELECT name, purchase_count FROM referees WHERE referrer_id = %s", (referrer['id'],))
        referrer['referees'] = cursor.fetchall()

    cursor.close()
    return render_template('index.html', referrers=referrers)


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
    return redirect('/')


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
        # Fetch the referees for this referrer
        cursor.execute(
            "SELECT * FROM referees WHERE referrer_id = %s", (referrer['id'],))
        referees = cursor.fetchall()  # Get the list of referees
        cursor.close()
        # Pass both referrer and referees to the template
        return render_template('search_result.html', referrer=referrer, referees=referees)
    else:
        cursor.close()
        return redirect('/')


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

        # Check if the referee already exists
        cursor.execute(
            "SELECT * FROM referees WHERE referrer_id = %s AND name = %s", (referrer_id, name))
        referee = cursor.fetchone()

        if referee:
            # Update purchase count for existing referee
            cursor.execute(
                "UPDATE referees SET purchase_count = %s WHERE id = %s",
                (purchase_count, referee['id'])
            )
            if purchase_count == 3 and not referee['incremented']:
                cursor.execute(
                    "UPDATE referrers SET total_references = total_references + 1 WHERE id = %s",
                    (referrer_id,)
                )
                cursor.execute(
                    "UPDATE referees SET incremented = TRUE WHERE id = %s", (referee['id'],))
        else:
            # Insert new referee
            cursor.execute(
                "INSERT INTO referees (referrer_id, name, purchase_count, date_of_purchase, incremented) "
                "VALUES (%s, %s, %s, %s, %s)",
                (referrer_id, name, purchase_count,
                 datetime.now(), purchase_count == 3)
            )
            if purchase_count == 3:
                cursor.execute(
                    "UPDATE referrers SET total_references = total_references + 1 WHERE id = %s",
                    (referrer_id,)
                )
        mysql.connection.commit()
    cursor.close()
    return redirect(f'/search_referral?referral_code={referral_code}')


@app.route('/update_referee', methods=['POST'])
def update_referee():
    referral_code = request.form.get('referral_code').upper()
    name = request.form.get('name')
    purchase_count = int(request.form.get('purchase_count'))

    cursor = mysql.connection.cursor()
    cursor.execute(
        "SELECT * FROM referrers WHERE referral_code = %s", (referral_code,))
    referrer = cursor.fetchone()

    if referrer:
        referrer_id = referrer['id']

        # Update purchase count for existing referee
        cursor.execute(
            "SELECT * FROM referees WHERE referrer_id = %s AND name = %s", (referrer_id, name))
        referee = cursor.fetchone()

        if referee:
            cursor.execute(
                "UPDATE referees SET purchase_count = %s WHERE id = %s",
                (purchase_count, referee['id'])
            )
            if purchase_count == 3 and not referee['incremented']:
                cursor.execute(
                    "UPDATE referrers SET total_references = total_references + 1 WHERE id = %s",
                    (referrer_id,)
                )
                cursor.execute(
                    "UPDATE referees SET incremented = TRUE WHERE id = %s", (referee['id'],))
        mysql.connection.commit()
    cursor.close()
    return redirect(f'/search_referral?referral_code={referral_code}')


if __name__ == '__main__':
    app.run(debug=True)
