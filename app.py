import re
import sqlite3
import json
import random
from functools import wraps
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from openai import OpenAI


# ---------------- APP CONFIG ----------------
app = Flask(__name__)
app.secret_key = "price_system_secret"

DATABASE = "database.db"

# ---------------- OPENAI ----------------
OPENAI_API_KEY = "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"
AI_MODEL_NAME = "gpt-4o-mini"

client = OpenAI(
    api_key=OPENAI_API_KEY
)

# ---------------- DATABASE ----------------
def db_connection():

    conn = sqlite3.connect(
        DATABASE,
        timeout=30,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn

def init_db():

    conn = db_connection()

    # users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'user'
        )
    """)

    # products table
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        search_name TEXT,
        product_name TEXT,
        brand TEXT,
        website TEXT,
        price REAL,
        warranty TEXT,
        rating REAL,
        sales INTEGER,
        discount INTEGER,
        offer TEXT,
        image_url TEXT,
        product_url TEXT
    )
""")

    # offers table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        search_text TEXT
    )
""")

    # create admin account
    admin = conn.execute(
        "SELECT * FROM users WHERE username=?",
        ("admin",)
    ).fetchone()

    if not admin:

        conn.execute(
            """
            INSERT INTO users
            (username, password, role)
            VALUES (?, ?, ?)
            """,
            (
                "admin",
                generate_password_hash("Admin1234"),
                "admin"
            )
        )

    conn.commit()
    conn.close()
# ---------------- LOGIN REQUIRED ----------------
def login_required(page):

    @wraps(page)
    def wrapper(*args, **kwargs):

        if "username" not in session:

            flash("Please login first.", "error")

            return redirect(url_for("login"))

        return page(*args, **kwargs)

    return wrapper

# ---------------- AI WEB SCRAPER ----------------
def ai_web_scraper(search_text):

    import random

    print("AI SEARCH:", search_text)

    prompt = f"""
You are a professional AI shopping assistant.

TASK:
Return EXACTLY 5 REAL products related ONLY to:
{search_text}

STRICT RULES:
- Products MUST match the search exactly
- Do NOT return unrelated items
- Do NOT explain anything
- Return ONLY valid JSON
- No markdown
- No ```json

Each product must contain:
- brand
- product_name
- price
- website
- product_url
- image_url

IMPORTANT:
Use short valid image URLs.
Do NOT generate extremely long URLs.
If no image URL is known, use:
"image_url": ""
Example format:

[
  {{
    "brand": "Dell",
    "product_name": "Dell XPS 15",
    "price": 1399,
    "website": "Dell",
    "product_url": "https://www.dell.com",
    "image_url": "https://..."
  }}
]
"""

    try:

        response = client.chat.completions.create(

            model=AI_MODEL_NAME,

            messages=[

                {
                    "role": "system",
                    "content": """
You are a JSON API.

Return ONLY valid JSON array.

No markdown.
No explanations.
No extra text.
"""
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ],

            temperature=0.3
        )

        answer = response.choices[0].message.content.strip()

        print("AI RAW:", answer)

        answer = answer.replace("```json", "")
        answer = answer.replace("```", "")
        answer = answer.strip()

        start = answer.find("[")
        end = answer.rfind("]")

        if start != -1 and end != -1:
            answer = answer[start:end + 1]

        try:
            products_data = json.loads(answer)

            print("JSON PARSED SUCCESSFULLY")
            print("PRODUCT COUNT:", len(products_data))

        except json.JSONDecodeError as e:

            print("\n========== INVALID JSON ==========")
            print(answer)
            print("==================================")
            print(e)

            return []

        products = []

        for item in products_data:

            usd_price = float(item.get("price", 0))
            omr_price = round(usd_price * 0.38, 2)

            sales_value = random.randint(50, 1000)

            if omr_price > 400:
                sales_value = random.randint(20, 150)

            elif omr_price < 100:
                sales_value = random.randint(300, 2000)

            has_offer = random.random() < 0.4

            discount = 0
            offer = ""

            if has_offer:

                discount = random.choice([5, 10, 15, 20, 25])

                offer = random.choice([
                    "Summer Sale",
                    "Weekend Deal",
                    "Back To School",
                    "Special Promotion",
                    "Limited Time Offer"
                ])

            products.append({

                "brand": item.get("brand", "Unknown"),
                "product_name": item.get("product_name", "Unknown Product"),
                "price": omr_price,
                "website": item.get("website", "Unknown"),

                "warranty": random.choice([
                    "No Warranty",
                    "6 Months",
                    "1 Year",
                    "2 Years",
                    "3 Years",
                    "5 Years"
                ]),

                "rating": round(
                    random.uniform(3.5, 5.0),
                    1
                ),

                "sales": sales_value,
                "discount": discount,
                "offer": offer,

                "image_url": item.get("image_url", ""),
                "product_url": item.get("product_url", "")
            })

        print("REAL PRODUCTS:", products)

        for p in products:
            print(
                p["product_name"],
                "Discount:", p["discount"],
                "Offer:", p["offer"]
            )

        return products

    except Exception as e:

        print("AI SCRAPER ERROR:")
        print(e)

        return []
# ---------------- AI RECOMMENDATION ----------------
def ai_choose_best_product(products, user_prompt):

    if not products:
        return None

    product_text = "\n".join([

        f"{i+1}. "
        f"{p['product_name']} | "
        f"Brand: {p['brand']} | "
        f"Price: ${p['price']} | "
        f"Warranty: {p['warranty']} year | "
        f"Rating: {p['rating']}/5"

        for i, p in enumerate(products)
    ])

    prompt = f"""
You are an AI shopping assistant.

User Request:
{user_prompt}

Products:
{product_text}

Choose the BEST product.

Explain WHY briefly.

Return format exactly like this:

Product Number: 1
Reason: Good price and quality
"""

    try:

        response = client.chat.completions.create(

            model=AI_MODEL_NAME,

          messages=[

    {
        "role": "system",
        "content": "You are a product search AI. Only return products related EXACTLY to the user search."
    },

    {
        "role": "user",
        "content": prompt
    }

],

            temperature=0.3
        )

        answer = response.choices[0].message.content.strip()

        print("AI ANSWER:", answer)

        match = re.search(r"\d+", answer)

        if match:

            index = int(match.group()) - 1

            if 0 <= index < len(products):

                best_product = products[index]

                best_product["ai_reason"] = answer

                return best_product

    except Exception as e:

        print("OPENAI ERROR:")
        print(e)

        return {
            "product_name": "AI Error",
            "brand": "System",
            "price": 0,
            "website": "OpenAI",
            "warranty": 0,
            "rating": 0,
            "sales": 0,
            "image_url": "",
            "product_url": "",
            "ai_reason": str(e)
        }

    return products[0]

# ---------------- SAVE PRODUCTS ----------------
def save_products(search_text):

    products = ai_web_scraper(search_text)

    conn = None

    try:
        conn = db_connection()
        cursor = conn.cursor()

        # Clear ONLY products for this search term
        cursor.execute(
            "DELETE FROM products WHERE search_name = ?", (search_text,)
        )

        # Insert new products
        for p in products:
            cursor.execute("""
                INSERT INTO products (
                    search_name,
                    product_name,
                    brand,
                    website,
                    price,
                    warranty,
                    rating,
                    sales,
                    discount,
                    offer,
                    image_url,
                    product_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                search_text,
                p["product_name"],
                p["brand"],
                p["website"],
                p["price"],
                p["warranty"],
                p["rating"],
                p["sales"],
                p["discount"],
                p["offer"],
                p["image_url"],
                p["product_url"]
            ))

        conn.commit()
        print(f"PRODUCTS SAVED for '{search_text}'")
        return True  # Return True on success
        
    except Exception as e:
        print("DATABASE ERROR:")
        print(e)
        return False  # Return False on error
        
    finally:
        if conn:
            conn.close()

# ---------------- GET PRODUCTS ----------------

def get_products(search_text=None):
    conn = db_connection()
    
    if search_text:
        # Only get products for the current search
        products = conn.execute(
            "SELECT * FROM products WHERE search_name = ? ORDER BY price ASC",
            (search_text,)
        ).fetchall()
    else:
        
        products = conn.execute(
            "SELECT * FROM products ORDER BY price ASC"
        ).fetchall()
    
    print("GET PRODUCTS FOR:", search_text)
    conn.close()
    return products
# ---------------- GET BRAND SALES ----------------

def get_brand_sales():
    """Get sales data grouped by brand"""
    conn = db_connection()
    sales = conn.execute("""
        SELECT 
            brand,
            SUM(sales) AS total_sales,
            COUNT(*) AS product_count
        FROM products
        WHERE brand IS NOT NULL AND brand != ''
        GROUP BY brand
        ORDER BY total_sales DESC
    """).fetchall()
    conn.close()
    return sales

# ---------------- HOME ----------------
@app.route("/")
def index():

    if "username" in session:
        return redirect(url_for("home"))

    return redirect(url_for("login"))

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        conn = db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()
        conn.close()
        
        if user and check_password_hash(user["password"], password):
            session["username"] = username
            session["role"] = user["role"]
            session["user_id"] = user["id"]
            
            # Redirect based on role
            if user["role"] == "seller":
                return redirect(url_for("seller"))  # Go to seller dashboard
            else:
                return redirect(url_for("home"))
        
        flash("Invalid credentials", "error")
    
    return render_template("login.html")

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        # Check if user exists
        conn = db_connection()
        existing_user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        
        if existing_user:
            flash("Username already exists", "error")
            conn.close()
            return redirect(url_for("register"))
        
        # Create new user
        hashed_password = generate_password_hash(password)
        conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, hashed_password, "user")
        )
        conn.commit()
        conn.close()
        
        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))
    
    return render_template("register.html")

# ---------------- HOME PAGE ----------------
@app.route("/home", methods=["GET", "POST"])
@login_required
def home():
    # Redirect sellers to their dashboard
    if session.get("role") == "seller":
        flash("Sellers use the Seller Dashboard, not the search page.", "info")
        return redirect(url_for("seller"))
    
    # Get popular categories for display
    popular_categories = get_popular_categories(6)
    
    if request.method == "POST":
        search_text = request.form.get('search', '').strip()
        
        
        if search_text:
           session['last_search'] = search_text  
           save_products(search_text)
           products = [dict(p) for p in get_products(search_text)]
           
        conn = db_connection()
        try:
                conn.execute(
                    "INSERT INTO searches (username, search_text) VALUES (?, ?)",
                    (session.get("username"), search_text)
                )
                conn.commit()
        except Exception as e:
                print(f"Error logging search: {e}")
        finally:
                conn.close()
            
        save_products(search_text)
        return redirect(url_for("comparison", search=search_text))
    
    return render_template("home.html", 
                         username=session.get("username"), 
                         role=session.get("role"),
                         popular_categories=popular_categories)

# ---------------- GET POPULAR CATEGORIES ----------------
def get_popular_categories(limit=6):
    """Get popular search categories from user searches"""
    conn = db_connection()
    conn.row_factory = sqlite3.Row
    categories = conn.execute("""
        SELECT 
            search_text,
            COUNT(*) AS search_count,
            COUNT(DISTINCT username) AS unique_users
        FROM searches
        WHERE search_text IS NOT NULL AND search_text != ''
        GROUP BY search_text
        ORDER BY search_count DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    
    # Convert to list of dictionaries
    result = []
    for row in categories:
        result.append({
            'name': row['search_text'],
            'count': row['search_count'],
            'users': row['unique_users']
        })
    return result

# ---------------- COMPARISON ----------------
@app.route("/comparison")
@login_required
def comparison():

    search_context = session.get('last_search', '')
    
    # Get products for the search context
    products_raw = get_products(search_context)
    products = [dict(p) for p in products_raw] if products_raw else []

    # If no products found in search, show message instead of all products
    if not products:
        return render_template(
            "comparison.html",
            products=[],
            search_text=search_context,
            notifications=[f"⚠️ No products found for '{search_context}'. Please search for '{search_context}' on the Home page first."]
        )

    notifications = []

    for p in products:
        if p.get("discount") and p.get("discount") > 0:
            notifications.append(
                f"🔥 {p['product_name']} now has {p['discount']}% OFF - {p['offer']}"
            )

    return render_template(
        "comparison.html",
        products=products,
        search_text=search_context,
        notifications=notifications
    )
# ---------------- AI RECOMMEND ----------------
@app.route("/recommend", methods=["GET", "POST"])
@login_required
def recommend():

    recommendation = None
    search_context = session.get('last_search', '')
    products = [dict(p) for p in get_products(search_context)]
    if request.method == "POST":

        age = request.form.get("age")
        job = request.form.get("job")
        budget = request.form.get("budget")
        quality = request.form.get("quality")
        warranty = request.form.get("warranty")
        usage = request.form.get("usage")

        user_prompt = f"""
        Age: {age}
        Job: {job}
        Budget: {budget}
        Quality Importance: {quality}
        Warranty Importance: {warranty}
        Usage Type: {usage}
        """

        recommendation = ai_choose_best_product(
            products,
            user_prompt
        )

    return render_template(
        "recommend.html",
        recommendation=recommendation,
        products=products
    )

# ---------------- ADMIN ----------------
@app.route("/admin")
@login_required
def admin():

    if session.get("role") != "admin":

        flash("Access denied")

        return redirect(url_for("home"))

    conn = db_connection()

    users = conn.execute(
        "SELECT * FROM users"
    ).fetchall()

    products = conn.execute(
        "SELECT * FROM products ORDER BY id DESC"
    ).fetchall()

    searches = conn.execute("""
        SELECT *
        FROM searches
        ORDER BY id DESC
        LIMIT 20
    """).fetchall()

    total_users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    total_products = conn.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0]

    total_searches = conn.execute(
        "SELECT COUNT(*) FROM searches"
    ).fetchone()[0]

    top_searches = conn.execute("""
        SELECT search_text,
               COUNT(*) AS total
        FROM searches
        GROUP BY search_text
        ORDER BY total DESC
        LIMIT 5
    """).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        users=users,
        products=products,
        searches=searches,
        total_users=total_users,
        total_products=total_products,
        total_searches=total_searches,
        top_searches=top_searches
    )

# ---------------- SELLER DASHBOARD ----------------
@app.route("/seller")
@login_required
def seller():
    if session.get("role") != "seller":
        flash("Access denied - Seller only")
        return redirect(url_for("home"))
    
    conn = db_connection()
    conn.row_factory = sqlite3.Row
    
    # Get top searches
    top_searches = conn.execute("""
        SELECT 
            search_text,
            COUNT(*) AS total,
            COUNT(DISTINCT username) AS unique_users
        FROM searches
        WHERE search_text IS NOT NULL AND search_text != ''
        GROUP BY search_text
        ORDER BY total DESC
        LIMIT 10
    """).fetchall()
    
    # Get recent searches
    recent_searches = conn.execute("""
        SELECT username, search_text, searched_at
        FROM searches
        WHERE search_text IS NOT NULL
        ORDER BY searched_at DESC
        LIMIT 10
    """).fetchall()
    
    # Get sales by brand 
    brand_sales = conn.execute("""
        SELECT 
            brand,
            SUM(sales) AS total_sales
        FROM products
        WHERE brand IS NOT NULL 
        AND brand != ''
        AND sales IS NOT NULL
        GROUP BY brand
        ORDER BY total_sales DESC
        LIMIT 20
    """).fetchall()
    
    # Get counts
    total = conn.execute("SELECT COUNT(*) as count FROM searches").fetchone()
    today = conn.execute("""
        SELECT COUNT(*) as count 
        FROM searches 
        WHERE DATE(searched_at) = DATE('now')
    """).fetchone()
    
    conn.close()
    
    # Convert to dictionaries for template
    top_list = []
    for t in top_searches:
        top_list.append({
            'search_text': t['search_text'],
            'total': t['total'],
            'unique_users': t['unique_users']
        })
    
    recent_list = []
    for r in recent_searches:
        recent_list.append({
            'username': r['username'],
            'search_text': r['search_text'],
            'searched_at': r['searched_at']
        })
    
    # Convert brand sales to dictionaries
    sales_list = []
    for s in brand_sales:
        sales_list.append({
            'brand': s['brand'],
            'total_sales': s['total_sales']
        })
    
    # Debug print
    print(f"Sales list count: {len(sales_list)}")
    if sales_list:
        print(f"Top brand: {sales_list[0]['brand']} with {sales_list[0]['total_sales']} sales")
    
    return render_template(
        "seller.html",
        top_searches=top_list,
        recent_searches=recent_list,
        brand_sales=sales_list,
        total_searches=total['count'] if total else 0,
        today_searches=today['count'] if today else 0
    )
# ---------------- DEMAND PREDICTION ----------------
@app.route("/predict", methods=["GET", "POST"])
@login_required
def predict():
    if session.get("role") != "seller":
        flash("Access denied - Seller only")
        return redirect(url_for("home"))
    
    result = None
    
    if request.method == "POST":
        product = request.form["product"]
        
        conn = db_connection()
        
        # Get search count
        row = conn.execute("""
            SELECT COUNT(*) AS total,
                   COUNT(DISTINCT DATE(searched_at)) as days_with_searches
            FROM searches
            WHERE LOWER(search_text) LIKE ?
        """, ("%" + product.lower() + "%",)).fetchone()
        
        # Get product data for more accurate prediction
        product_data = conn.execute("""
            SELECT AVG(rating) as avg_rating,
                   AVG(sales) as avg_sales,
                   COUNT(*) as product_count
            FROM products
            WHERE LOWER(search_name) LIKE ?
        """, ("%" + product.lower() + "%",)).fetchone()
        
        conn.close()
        
        searches = row["total"] or 0
        
        # Calculate dynamic score
        score = 0
        if searches > 0:
            # Base score from searches (max 50 points)
            score += min(50, searches * 2)
            
            # Add rating points (max 30 points)
            if product_data["avg_rating"]:
                score += product_data["avg_rating"] * 6
            
            # Add sales points (max 20 points)
            if product_data["avg_sales"]:
                score += min(20, product_data["avg_sales"] / 10)
        
        score = min(100, int(score))
        
        # Determine demand level
        if score >= 70:
            level = "HIGH"
            recommendation = "Strong demand detected. Excellent opportunity to stock!"
            color = "green"
        elif score >= 40:
            level = "MEDIUM"
            recommendation = "Moderate demand. Consider testing with small inventory."
            color = "orange"
        else:
            level = "LOW"
            recommendation = "Limited demand. Monitor trends before stocking."
            color = "red"
        
        result = {
            "product": product,
            "searches": searches,
            "score": score,
            "level": level,
            "recommendation": recommendation,
            "color": color,
            "avg_rating": round(product_data["avg_rating"] or 0, 1),
            "products_found": product_data["product_count"] or 0,
            "avg_sales": int(product_data["avg_sales"] or 0)
        }
    
    return render_template("predict.html", result=result)

# ---------------- SELLER ANALYTICS  ----------------
@app.route("/seller/analytics")
@login_required
def seller_analytics():
    if session.get("role") != "seller":
        flash("Access denied")
        return redirect(url_for("home"))
    
    conn = db_connection()
    
    # Get daily search trends
    daily_trends = conn.execute("""
        SELECT DATE(searched_at) as date,
               COUNT(*) as searches
        FROM searches
        WHERE searched_at >= DATE('now', '-7 days')
        GROUP BY DATE(searched_at)
        ORDER BY date DESC
    """).fetchall()
    
    # Get top products by opportunity score
    opportunities = conn.execute("""
        SELECT p.search_name,
               COUNT(s.id) as searches,
               AVG(p.rating) as avg_rating,
               AVG(p.sales) as avg_sales
        FROM products p
        LEFT JOIN searches s ON LOWER(s.search_text) LIKE '%' || LOWER(p.search_name) || '%'
        GROUP BY p.search_name
        ORDER BY (COUNT(s.id) * AVG(p.rating)) DESC
        LIMIT 10
    """).fetchall()
    
    conn.close()
    
    return render_template("seller_analytics.html", 
                         daily_trends=daily_trends,
                         opportunities=opportunities)

# ---------------- ADD PRODUCT ----------------
@app.route("/add_product", methods=["POST"])
@login_required
def add_product():

    if session.get("role") != "admin":
        return redirect(url_for("home"))

    product_name = request.form["product_name"]
    brand = request.form["brand"]
    price = request.form["price"]

    conn = db_connection()

    conn.execute("""
        INSERT INTO products (
            search_name,
            product_name,
            brand,
            website,
            price,
            warranty,
            rating,
            sales,
            discount,
            offer,
            image_url,
            product_url
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "admin",
        product_name,
        brand,
        brand,
        price,
        "1 Year",
        5.0,
        0,
        0,
        "",
        "",
        ""
    ))

    conn.commit()
    conn.close()

    flash("Product Added Successfully")

    return redirect(url_for("admin"))

# ---------------- DELETE USER ----------------
@app.route("/delete_user/<int:user_id>")
@login_required
def delete_user(user_id):

    if session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = db_connection()

    conn.execute(
        "DELETE FROM users WHERE id=?",
        (user_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("admin"))

# ---------------- DELETE PRODUCT ----------------
@app.route("/delete_product/<int:product_id>")
@login_required
def delete_product(product_id):

    if session.get("role") != "admin":
        return redirect(url_for("home"))

    conn = db_connection()

    conn.execute(
        "DELETE FROM products WHERE id=?",
        (product_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("admin"))

# ---------------- SALES PAGE FUNCTIONS ----------------
def get_brand_sales():
    """Get sales data grouped by brand from the products table"""
    conn = db_connection()
    conn.row_factory = sqlite3.Row
    sales = conn.execute("""
        SELECT 
            brand,
            SUM(COALESCE(sales, 0)) AS total_sales,
            COUNT(*) AS product_count
        FROM products
        WHERE brand IS NOT NULL 
        AND brand != ''
        AND sales IS NOT NULL
        GROUP BY brand
        ORDER BY total_sales DESC
        LIMIT 20
    """).fetchall()
    conn.close()
    
    # Convert to list of dictionaries
    result = []
    for row in sales:
        if row['total_sales'] > 0:  # to show Only brands with sales
            result.append({
                'brand': row['brand'],
                'total_sales': row['total_sales']
            })
    return result

def get_search_trends(limit=10):
    """Get top search trends"""
    conn = db_connection()
    conn.row_factory = sqlite3.Row
    trends = conn.execute("""
        SELECT 
            search_text,
            COUNT(*) AS total,
            COUNT(DISTINCT username) AS unique_users
        FROM searches
        WHERE search_text IS NOT NULL 
        AND search_text != ''
        GROUP BY search_text
        ORDER BY total DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    
    # Convert to list of dictionaries
    result = []
    for row in trends:
        result.append({
            'search_text': row['search_text'],
            'total': row['total'],
            'unique_users': row['unique_users']
        })
    return result

def get_recent_searches(limit=10):
    """Get recent searches"""
    conn = db_connection()
    recent = conn.execute("""
        SELECT username, search_text, searched_at
        FROM searches
        ORDER BY searched_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return recent

def get_trending_products():
    """Identify trending products (searches in last 24 hours)"""
    conn = db_connection()
    trending = conn.execute("""
        SELECT DISTINCT search_text
        FROM searches
        WHERE searched_at >= datetime('now', '-1 day')
        GROUP BY search_text
        HAVING COUNT(*) > 1
    """).fetchall()
    conn.close()
    return [item[0] for item in trending]

def get_search_sales_correlation():
    """Show correlation between searches and sales"""
    conn = db_connection()
    correlation = conn.execute("""
        SELECT 
            p.search_name,
            COUNT(DISTINCT s.id) AS searches,
            SUM(p.sales) AS sales
        FROM products p
        LEFT JOIN searches s ON LOWER(s.search_text) LIKE '%' || LOWER(p.search_name) || '%'
        WHERE p.search_name IS NOT NULL
        GROUP BY p.search_name
        ORDER BY searches DESC
        LIMIT 10
    """).fetchall()
    conn.close()
    return correlation

# ---------------- SEARCH TRENDS (for sales page) ----------------
def get_search_trends(limit=10):
    """Get top search trends"""
    conn = db_connection()
    trends = conn.execute("""
        SELECT 
            search_text,
            COUNT(*) AS total,
            COUNT(DISTINCT username) AS unique_users,
            MAX(searched_at) AS last_searched
        FROM searches
        WHERE search_text IS NOT NULL AND search_text != ''
        GROUP BY search_text
        ORDER BY total DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return trends

def get_recent_searches(limit=10):
    """Get recent searches"""
    conn = db_connection()
    recent = conn.execute("""
        SELECT username, search_text, searched_at
        FROM searches
        WHERE search_text IS NOT NULL AND search_text != ''
        ORDER BY searched_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return recent

def get_trending_products():
    """Identify trending products (searches increased in last 24 hours)"""
    conn = db_connection()
    trending = conn.execute("""
        SELECT DISTINCT search_text
        FROM searches
        WHERE searched_at >= datetime('now', '-1 day')
        GROUP BY search_text
        HAVING COUNT(*) > 1
    """).fetchall()
    conn.close()
    return [item[0] for item in trending]

def get_search_sales_correlation():
    """Show correlation between searches and sales"""
    conn = db_connection()
    correlation = conn.execute("""
        SELECT 
            p.search_name,
            COUNT(DISTINCT s.id) AS searches,
            SUM(p.sales) AS sales
        FROM products p
        LEFT JOIN searches s ON LOWER(s.search_text) LIKE '%' || LOWER(p.search_name) || '%'
        WHERE p.search_name IS NOT NULL
        GROUP BY p.search_name
        ORDER BY searches DESC
        LIMIT 10
    """).fetchall()
    conn.close()
    return correlation

# ---------------- SALES PAGE ----------------
@app.route("/sales")
@login_required
def sales():

    role = session.get("role")

    brand_sales_data = []

    # USER -> only brands from last comparison
    if role == "user":

        search_context = session.get("last_search", "")

        if search_context:

            products = [dict(p) for p in get_products(search_context)]

            brand_sales = {}

            for p in products:

                brand = p["brand"]

                brand_sales[brand] = (
                    brand_sales.get(brand, 0)
                    + p["sales"]
                )

            brand_sales_data = [
                {
                    "brand": brand,
                    "total_sales": sales
                }
                for brand, sales in brand_sales.items()
            ]

            brand_sales_data.sort(
                key=lambda x: x["total_sales"],
                reverse=True
            )

    # SELLER / ADMIN -> all brands in database
    else:

        conn = db_connection()

        brand_sales_data = conn.execute("""
            SELECT
                brand,
                SUM(sales) AS total_sales
            FROM products
            GROUP BY brand
            ORDER BY total_sales DESC
        """).fetchall()

        conn.close()

    search_trends_data = get_search_trends()

    recent_searches_data = []
    correlation_data = []

    if role in ["seller", "admin"]:
        recent_searches_data = get_recent_searches()
        correlation_data = get_search_sales_correlation()

    return render_template(
        "sales.html",
        brand_sales=brand_sales_data,
        search_trends=search_trends_data,
        recent_searches=recent_searches_data,
        correlation_data=correlation_data
    )
# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))

# ---------------- RUN ----------------
if __name__ == "__main__":

    init_db()

    app.run(
        debug=True,
        use_reloader=False
    )
