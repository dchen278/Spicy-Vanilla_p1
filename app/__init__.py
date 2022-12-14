# Spicy Vanilla: David Chen, Jing Feng, Jeremy Kwok, and Matthew Yee
# SoftDev

from flask import Flask, jsonify  # facilitate flask webserving
from flask import render_template  # facilitate jinja templating
from flask import request  # facilitate form submission
from flask import session
from flask import Response
import sqlite3
import requests
import os
import json
import datetime
from db import get_user_by_username, add_user, check_username, get_orders, get_order, get_users
import random

app = Flask(__name__)  # create Flask object
# Set the secret key to some random bytes. Keep this really secret!
app.secret_key = b'v9y$B&E)H+MbQeThWmZq4t7w!z%C*F-J'

dirname = os.path.dirname(__file__)
# qhqws47nyvgze2mq3qx4jadt
bestBuyKey = open(os.path.join(dirname, "keys/key_bestbuy.txt")).read()
radarKey = open(os.path.join(dirname, "keys/key_radar.txt")).read()
mailChimpKey = open(os.path.join(dirname, "keys/key_mailchimp.txt")).read()
mailgunKey = open(os.path.join(dirname, "keys/key_mailgun.txt")).read()

USER_DB_FILE = "users.db"
CART_DB_FILE = "cart.db"
# open if file exists, otherwise create
db = sqlite3.connect(USER_DB_FILE, check_same_thread=False)
c = db.cursor()

# custom render_template function that adds the username to the template


def render_template_with_username(template, **kwargs):
    username = session.get('username', None)
    print("username is " + str(username) + " in render_template_with_username")
    return render_template(template, username=username, **kwargs)


@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template_with_username('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return app.redirect("/")
    # both the database and the cursor need to be connected in the function it is used in because they must run in the same thread
    users_db = sqlite3.connect(USER_DB_FILE)
    users_c = users_db.cursor()

    error = ""
    username = ""
    users_c.execute("SELECT * FROM users")
    user_list = users_c.fetchall()
    print("valid accounts are :" + str(user_list))

    # the following code will only run if the user submits the form on the login page
    if request.method == "POST":
        # diagnostic prints
        print("inputted username is " + request.form['username'])
        print("inputted password is " + request.form['password'])

        # to catch an incomplete operation exception that occurs if the username field is
        try:
            username = request.form['username']
            # inserts username as a tuple containing one item because the ? substitution requires a tuple
            # looks in the database to see if the username entered exists in the users database
            print(
                "executing: SELECT * FROM users GROUP BY username HAVING username=?", (username,))
            users_c.execute(
                "SELECT * FROM users GROUP BY username HAVING username=?", (username,))
        except:
            # print error message if username is not found in database
            error = "username not found"
            print("user with username: " +
                  request.form['username'] + " was not found in database")
            return render_template('login.html', error_message=error)
        # if username is found, get the corresponding record from the database
        credentials = users_c.fetchall()
        print(f"Found the following record for user {username}: {credentials}")

        # since we got the record as a list of tuples, we can check the length of the list to see if the query had any matches
        # username is a primary key, so there will be at most one record
        if len(credentials) > 0:
            username = credentials[0][0]
            password = credentials[0][1]

            if request.form['password'] == password:
                # if password is correct, let the user login with that username
                session['username'] = username
                return app.redirect('/')
            else:
                error = "Incorrect password"
        else:
            error = "Username not found"

    return render_template('login.html', error_message=error)


@app.route('/logout', methods=["GET", "POST"])
def logout():
    # Checks if there is a username and password in session before popping to prevent a key error
    if 'username' in session:
        print("attempting to pop username")
        session.pop('username')  # removes the username from the session
    # Sends the user back to the login page
    return app.redirect(app.url_for('login'))


@app.route("/api/products/trending", methods=["GET"])
def trending():
    response = requests.get(
        f"https://api.bestbuy.com/v1/products/trendingViewed?apiKey={bestBuyKey}&format=json&show=sku,name,salePrice,image&pageSize=20"
    )
    data = response.json()
    return data


@app.route("/api/products/search", methods=["GET"])
def search():
    query = request.args.get("query")
    # handle pagination
    page = request.args.get("page")
    if page is None:
        page = 1
    else:
        page = int(page)
    response = requests.get(
        f"https://api.bestbuy.com/v1/products((search={query}))?apiKey={bestBuyKey}&format=json&show=sku,name,salePrice,image&pageSize=20&page={str(page)}"
    )
    data = response.json()
    return data


@app.route("/search", methods=["GET"])
def search_page():
    # dont error out if there is no username key in the session
    username = session.get('username', None)
    query = request.args.get("query")
    # handle pagination
    page = request.args.get("page")
    if query is None:
        return app.redirect("/")
    if page is None:
        page = 1
    else:
        page = int(page)
    response = requests.get(
        f"https://api.bestbuy.com/v1/products((longDescription={query}*))?apiKey={bestBuyKey}&format=json&show=sku,name,salePrice,image,customerReviewCount,customerReviewAverage&pageSize=20&page={str(page)}"
    )
    if response.status_code != 200:
        return app.redirect("/")
    data = response.json()["products"]
    return render_template_with_username("results.html", data=data, query=query, page=page)


@app.route('/register', methods=["GET", "POST"])
def register():
    if 'username' in session:
        return app.redirect("/")
    error = ''
    if request.method == 'POST':
        # check for an empty username
        if request.form['username'].strip() == '':
            error = 'No username submitted'
            return render_template('register.html', error_message=error)
        # check for an empty password
        if request.form['password'].strip() == '':
            error = 'No password submitted'
            return render_template('register.html', error_message=error)
        # prevent whitespaces to prevent usernames and passwords like "         e"
        if ' ' in request.form['username'] or ' ' in request.form['password']:
            error = 'Spaces are not permitted in the username or password'
            return render_template('register.html', error_message=error)

        users_db = sqlite3.connect(USER_DB_FILE)
        users_c = users_db.cursor()
        # get the record with the username entered
        username = request.form['username']
        users_c.execute(
            "SELECT * FROM users GROUP BY username HAVING username=?", (username,))
        user_list = users_c.fetchall()

        # if the record / username exists
        if len(user_list) > 0:
            error = 'Username already exists'
            return render_template('register.html', error_message=error)
        else:
            password = request.form['password']
            # add the user into the user database
            command = "INSERT INTO users values(?, ?);"
            users_c.execute(command, (username, password))
            users_db.commit()

            # add the user into the order_history table
            command = "INSERT INTO order_history values(?, ?, ?);"
            users_c.execute(command, (username, None, None))
            users_db.commit()

            # diagnostic print
            users_c.execute("SELECT * FROM users")
            user_list = users_c.fetchall()
            print(user_list)

            error = 'Account Created, Navigate to Login'
            return render_template('register.html', error_message=error)
            # confirmation message

    return render_template('register.html')


@app.route('/cart', methods=["GET", "POST"])
def cart_display():
    username = session.get('username', None)
    if username is None:
        return app.redirect('/login')
    users_db = sqlite3.connect(USER_DB_FILE)
    users_c = users_db.cursor()
    users_c.execute(
        "SELECT cart FROM order_history WHERE username=?", (username,))
    full_cart = users_c.fetchone()[0]

    if full_cart is None:
        full_cart = ""
        return render_template_with_username('cart.html', error='You have no items in your cart.', data=[])

    if 'username' in session:
        response = requests.get(
            f"https://api.bestbuy.com/v1/products(sku in ({full_cart}))?apiKey={bestBuyKey}&format=json"
        )
        if response.status_code != 200:
            return render_template_with_username('cart.html', error='You have no items in your cart.', data=[])
        data = response.json()["products"]
        error = 'You have no items in your cart.'
    else:
        error = 'Please log in to add items to your cart.'
    return render_template_with_username('cart.html', error=error, data=data)


@app.route('/searchbycategory/categoryID=<variable>', methods=['GET', 'POST'])
def searchbycategory(variable):
    response = requests.get(
        # pageSize=[number] allows you to change how many products you want in the json file returned
        f"https://api.bestbuy.com/v1/products(categoryPath.id={variable})?apiKey={bestBuyKey}&format=json&pageSize=40")
    data = response.json()["products"]
    # products = data["products"]
    # print(data)
    # print(products)

    return render_template_with_username("results.html", data=data)


@app.route('/searchbysale', methods=['GET', 'POST'])
def searchbysale():
    response = requests.get(
        f"https://api.bestbuy.com/v1/products(onSale=true)?apiKey={bestBuyKey}&format=json&pageSize=40"
    )
    data = response.json()["products"]
    return render_template_with_username("results.html", data=data)


@app.route('/randomitem/deal=<deal>', methods=['GET', 'POST'])
def randomitem(deal):
    if deal:
        response = requests.get(
            f"https://api.bestbuy.com/v1/products(onSale=true)?apiKey={bestBuyKey}&format=json&pageSize=100"
        )
    else:
        response = request.get(
            f"https://api.bestbuy.com/v1/products?apiKey={bestBuyKey}&format=json&pageSize=100"
        )

    randnum = random.randint(0, 99)
    product = response.json()["products"][randnum]
    return render_template_with_username("products.html", data=product)


@app.route('/searchbysku/<variable>', methods=['GET', 'POST'])
def searchbysku(variable):
    response = requests.get(
        f"https://api.bestbuy.com/v1/products(search={variable})?apiKey={bestBuyKey}&format=json&show=sku,name,salePrice,regularPrice,image,shortDescription,customerReviewCount,customerReviewAverage&pageSize=1"
    )
    print(response)
    # Searchs and takes first response
    product = response.json()["products"][0]
    print(product)
    return render_template_with_username("products.html", data=product, all=response.json())
    # return render_template("products.html", data=data)#, name=name)


def getip():
    # if the addr is 127.0.0.1 then request for the ip
    if request.remote_addr == "127.0.0.1":
        ip = requests.get("https://api.ipify.org").text
    else:
        ip = request.remote_addr
    return ip


def get_ip_data(ip):
    response = requests.get(f"http://ip-api.com/json/{ip}")
    data = response.json()
    print(data)
    return data


@app.route('/stores', methods=['GET', 'POST'])
def stores():
    ip_data = get_ip_data(getip())
    return render_template_with_username("stores.html", location=ip_data['zip'], stores=get_stores_helper())


def get_stores_helper():
    ip_data = get_ip_data(getip())
    response = requests.get(
        f"https://api.bestbuy.com/v1/stores(area({ip_data['lat']},{ip_data['lon']},10))?apiKey={bestBuyKey}&format=json&pageSize=10&show=storeId,storeType,name,city,distance,phone,region,postalCode,storeType,lat,lng,address,city,region,postalCode"
    )
    data = response.json()["stores"]
    print(data)
    print(response.json())
    return data


@app.route('/api/get_stores', methods=['GET'])
def get_stores():
    ip_data = get_ip_data(getip())
    response = requests.get(
        f"https://api.bestbuy.com/v1/stores(area({ip_data['lat']},{ip_data['lon']},10))?apiKey={bestBuyKey}&format=json&pageSize=10&show=storeId,storeType,name,city,distance,phone,region,postalCode,storeType,lat,lng"
    )
    data = response.json()["stores"]
    print(data)
    return jsonify(data)


@app.route('/add_cart', methods=["GET", "POST"])
def add_to_cart():
    if request.method == "POST" and 'username' in session:

        users_db = sqlite3.connect(USER_DB_FILE)
        users_c = users_db.cursor()

        username = ""
        username = session['username']
        print("Username is: " + username)

        users_c.execute(
            "SELECT cart FROM order_history WHERE username=?", (username,))
        full_cart = users_c.fetchone()[0]

        if (full_cart == None):
            full_cart = request.form['SKU']
        else:
            full_cart += "," + request.form['SKU']

        users_c.execute(
            "UPDATE order_history SET cart=? WHERE username=?", (full_cart, username,))
        users_db.commit()

    return app.redirect(app.url_for('cart_display'))


@app.route("/update_quantity", methods=["GET", "POST"])
def update_quantity():
    if request.method == "POST" and 'username' in session:

        users_db = sqlite3.connect(USER_DB_FILE)
        users_c = users_db.cursor()

        username = ""
        username = session['username']
        print("Username is: " + username)

        users_c.execute(
            "SELECT cart FROM order_history WHERE username=?", (username,))
        full_cart = users_c.fetchone()[0]

        if (full_cart == None):
            full_cart = ""
        else:
            full_cart = full_cart.replace(request.form['SKU'], "")

        for i in range(int(request.form['quantity'])):
            full_cart += "," + request.form['SKU']

        users_c.execute(
            "UPDATE order_history SET cart=? WHERE username=?", (full_cart, username,))
        users_db.commit()

    return app.redirect(app.url_for('cart_display'))


@app.route('/remove_cart', methods=["GET", "POST"])
def remove_from_cart():
    if request.method == "POST" and 'username' in session:

        users_db = sqlite3.connect(USER_DB_FILE)
        users_c = users_db.cursor()

        username = ""
        username = session['username']
        print("Username is: " + username)

        users_c.execute(
            "SELECT cart FROM order_history WHERE username=?", (username,))
        full_cart = users_c.fetchone()[0]

        if (full_cart == None):
            full_cart = ""
        else:
            full_cart = full_cart.replace(request.form['SKU'], "")

        users_c.execute(
            "UPDATE order_history SET cart=? WHERE username=?", (full_cart, username,))
        users_db.commit()
    # return Response(status=200)
    return app.redirect(app.url_for('cart_display'))


@app.route('/add_product_to_cart', methods=["GET", "POST"])
def add_product_to_cart(name, quantity, sku, price):
    username = session['username']
    date = datetime.datetime.now().strftime("%y-%m-%d")
    # going to temporarily add the cart items into user.db
    c.execute("insert into orders values(?, ?, ?, ?, ?, ?)",
              (username, name, date, quantity, sku, price))
    print("added to cart")
    return app.redirect(app.url_for('cart_display'))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if request.method == "POST" and 'username' in session:
        users_db = sqlite3.connect(USER_DB_FILE)
        users_c = users_db.cursor()

        username = session['username']
        # get the user's cart
        email = request.form['email']
        name = f"{request.form['firstName']} {request.form['lastName']}"
        print(name)
        date = datetime.datetime.now().strftime("%y-%m-%d")
        quantity = request.form.get('quantity', 1)
        sku = request.form['SKU']
        price = request.form['price']

        # handle checkout process and send email confirmation
        # get the user's cart
        req = requests.post(
            "https://api.mailgun.net/v3/mg.betterbuy.ml/messages",
            auth=("api", mailgunKey),
            data={"from": "BetterBuy <orders@betterbuy.ml>",
                  "to": f"{name} <{email}>",
                  "subject": f"Order Confirmation for {name}",
                  "text": f"Thank you for your order, {name}! Your order will be shipped to {email}."
                  })
        print(req.text)
        order_num = random.randint(1000000000, 9999999999)
        users_c.execute("insert into orders values(?, ?, ?, ?, ?, ?, ?)",
                        (username, name, date, quantity, sku, price, order_num))
        users_db.commit()

        users_c.execute(
            "UPDATE order_history SET cart='' WHERE username=?", (username,))
        users_db.commit()

        return app.redirect(app.url_for('show_orders') + f"?order_num={order_num}")
    else:
        username = session.get('username', None)
        if username is None:
            return app.redirect('/login')
        users_db = sqlite3.connect(USER_DB_FILE)
        users_c = users_db.cursor()
        users_c.execute(
            "SELECT cart FROM order_history WHERE username=?", (username,))
        full_cart = users_c.fetchone()[0]

        if full_cart is None:
            full_cart = ""
            return render_template_with_username('cart.html', error='You have no items in your cart.', data=[])

        if 'username' in session:
            response = requests.get(
                f"https://api.bestbuy.com/v1/products(sku in ({full_cart}))?apiKey={bestBuyKey}&format=json"
            )
            if response.status_code != 200:
                return render_template_with_username('cart.html', error='You have no items in your cart.', data=[])
            data = response.json()["products"]
            error = 'You have no items in your cart.'
        else:
            error = 'Please log in to add items to your cart.'
        # add  prodcut prices
        totalPrice = 0
        for product in data:
            totalPrice += product["salePrice"]
        print(data)
        return render_template_with_username('checkout.html', order=data, total=totalPrice, SKU=full_cart)


@app.route("/orders", methods=["GET", "POST"])
def show_orders():

    if 'username' in session:
        users_db = sqlite3.connect(USER_DB_FILE)
        users_c = users_db.cursor()

        username = ""
        username = session['username']

        users_c.execute(
            "SELECT orderID FROM orders WHERE username=?", (username,))
        order_list = users_c.fetchall()

        print(order_list)

        '''
        all_orders = [] #this is a nested list of all orders made by the current user, and the details for each
                        #currently not in use because nested list would be hard to feed to template

        for current in order_list:
            temp = current[0]
            users_c.execute("SELECT * FROM orders WHERE orderID=?", (temp,))
            search_dict = users_c.fetchall()
            #print(search_dict)
            all_orders.append(search_dict)
        
        print(all_orders)
        '''

        return render_template_with_username('orders.html', data=order_list)
    else:
        app.redirect(app.url_for('login'))
    return app.redirect(app.url_for('login'))


@app.route("/order/<variable>", methods=["GET", "POST"])
def order_details(variable):
    if 'username' in session:
        users_db = sqlite3.connect(USER_DB_FILE)
        users_c = users_db.cursor()

        username = ""
        username = session['username']

        users_c.execute(
            "SELECT * FROM orders WHERE orderID=?", (variable,))
        order_list = users_c.fetchall()[0]
        # fetch detials from bestbuy api
        print(order_list)
        response = requests.get(
            f"https://api.bestbuy.com/v1/products(sku in ({order_list[4]}))?apiKey={bestBuyKey}&format=json"
        )
        # print(response.json())

        return render_template_with_username('details.html', data=order_list, products=response.json()["products"])
    else:
        app.redirect(app.url_for('login'))
    return app.redirect(app.url_for('login'))


'''
@app.route('/search_order/<variable>', methods=['GET', 'POST'])
def search_order(variable):
    ID = variable
    users_db = sqlite3.connect(USER_DB_FILE)
    users_c = users_db.cursor()
    users_c.execute("SELECT * FROM orders WHERE orderID=?", (ID,))
    dump = users_c.fetchall()
    #name = users_c.fetchone()[1]
    date = dump[2]
    quantity = users_c.fetchone()[3]
    SKU = users_c.fetchone()[4]
    price = users_c.fetchone()[5]

    response = requests.get(
        f"https://api.bestbuy.com/v1/products(sku in ({SKU}))?apiKey={bestBuyKey}&format=json"
    )
    if response.status_code != 200:
        return render_template_with_username('cart.html', error='You have no items in your cart.', data=[])
    data = response.json()["products"]

    return render_template_with_username("order_search.html", ID=ID, name=name, date=date, data=data, price=price)
'''

if __name__ == "__main__":  # false if this file imported as module
    # enable debugging, auto-restarting of server when this file is modified
    app.debug = True
    app.run()
