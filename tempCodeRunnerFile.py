from flask import Flask, render_template, request, jsonify
import pandas as pd
import os
import json
import datetime
from flask import session
from flask import make_response

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.secret_key = '123'  # Cần để sử dụng session
import os
import pandas as pd
import ast

basedir = os.path.abspath(os.path.dirname(__file__))

df_info, df_comments, df_blog = None, None, None  # Khai báo biến toàn cục ban đầu

def load_data():
    import os, ast
    import pandas as pd

    basedir = os.path.abspath(os.path.dirname(__file__))

    info_path = os.path.join(basedir, 'product_info_ncds.csv')
    images_path = os.path.join(basedir, 'product_images.csv')
    comments_path = os.path.join(basedir, 'product_comments_ncds_20250520_143747.csv')
    blog_path = os.path.join(basedir, 'vnexpress_random_articles_20250521_195908.csv')

    df_info = pd.read_csv(info_path)
    df_images = pd.read_csv(images_path)
    df_comments = pd.read_csv(comments_path)
    df_blog = pd.read_csv(blog_path)

    # Đổi tên cột id nếu cần
    df_info.rename(columns=lambda x: 'product_id' if x.strip().lower() == 'id' else x, inplace=True)
    df_images.rename(columns=lambda x: 'product_id' if x.strip().lower() == 'id' else x, inplace=True)
    df_comments.rename(columns=lambda x: 'product_id' if x.strip().lower() == 'id' else x, inplace=True)

    if 'image_url' in df_images.columns:
        df_info = pd.merge(df_info, df_images[['product_id', 'image_url']], on='product_id', how='left')

    if 'images' in df_blog.columns:
        df_blog['images'] = df_blog['images'].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else [])

    return df_info, df_comments, df_blog

@app.route('/accept_cookies', methods=['POST'])
def accept_cookies():
    resp = make_response(jsonify({'message': 'Cookie đã được lưu!'}))
    resp.set_cookie('accepted_terms', 'yes', max_age=60*60*24*365)  # 1 năm
    return resp

@app.route('/chatbot', methods=['GET', 'POST'])
def chatbot():
    info_path = os.path.join(basedir, 'product_info_ncds.csv')
    image_path = os.path.join(basedir, 'product_images.csv')

    df_info = pd.read_csv(info_path)
    df_img = pd.read_csv(image_path)

    df_info.rename(columns={'id': 'product_id'}, inplace=True, errors='ignore')
    df_img.rename(columns={'id': 'product_id'}, inplace=True, errors='ignore')

    df_info['name_lower'] = df_info['name'].astype(str).str.lower()
    df_info['description_lower'] = df_info.get('description', pd.Series([''] * len(df_info))).astype(str).str.lower()

    df = pd.merge(df_info, df_img[['product_id', 'image_url']], on='product_id', how='left')

    # 🛑 ĐĂNG XUẤT: Không có user_id trong session thì xóa cookie
    if not session.get("id"):
        resp = make_response(render_template('_chatbot_widget.html', title='🤖 Chatbot hỗ trợ'))
        resp.set_cookie('accepted_terms', '', expires=0)
        return resp

    # 📥 POST: Người dùng gửi câu hỏi
    if request.method == 'POST':
        question = request.json.get('question', '').lower().strip()
        if not question:
            return jsonify({'answer': 'Vui lòng nhập câu hỏi.'})

        # 🍪 Nếu người dùng đã chấp nhận cookie và yêu cầu "gợi ý"
        if request.cookies.get('accepted_terms') == 'yes' and question == 'gợi ý':
            top = df.sort_values(by='rating_average', ascending=False).head(3)
            products = [{
                'id': int(row['product_id']),
                'name': row['name'],
                'image': row.get('image_url', ''),
                'price': int(row.get('price', 0))
            } for _, row in top.iterrows()]
            return jsonify({'answer': '🎯 Gợi ý sản phẩm dành cho bạn:', 'products': products})

        matched = df[df['name_lower'].str.contains(question) | df['description_lower'].str.contains(question)]
        if matched.empty:
            return jsonify({'answer': '❌ Không tìm thấy sản phẩm phù hợp.'})

        top3 = matched.head(3)
        products = [{
            'id': int(row['product_id']),
            'name': row['name'],
            'image': row.get('image_url', ''),
            'price': int(row.get('price', 0))
        } for _, row in top3.iterrows()]
        return jsonify({'answer': '✅ Tìm thấy sản phẩm:', 'products': products})

    # 🌐 GET: Truy cập lần đầu với keyword query
    keyword = request.args.get("keyword", "").lower().strip()
    auto_msg = ""
    products = []

    if keyword:
        matched = df[df['name_lower'].str.contains(keyword) | df['description_lower'].str.contains(keyword)]
        if not matched.empty:
            top3 = matched.head(3)
            auto_msg = "🔍 Có thể bạn đang tìm:"
            products = [{
                'id': int(row['product_id']),
                'name': row['name'],
                'image': row.get('image_url', ''),
                'price': int(row.get('price', 0))
            } for _, row in top3.iterrows()]

    # 🚀 Render chatbot view, truyền sẵn kết quả gợi ý nếu có
    return render_template(
        '_chatbot_widget.html',
        title='🤖 Chatbot hỗ trợ',
        auto_msg=auto_msg,
        auto_products=products
    )




@app.route('/shop')
def shop_grid():
    df_info, df_comments, df_blog = load_data()  # load dữ liệu

    # Lọc sản phẩm có đủ thông tin cần thiết
    products = (
        df_info.dropna(subset=['name', 'price', 'image_url'])
               .sort_values(by='name')
               .to_dict(orient='records')
    )

    # Lấy danh mục và thương hiệu (có thể dùng để filter nếu cần)
    categories = sorted(df_info['category'].dropna().unique())
    brands = sorted(df_info['brand'].dropna().unique())

    # Phân trang
    page = request.args.get('page', 1, type=int)
    per_page = 12
    total = len(products)
    start = (page - 1) * per_page
    end = start + per_page
    products_page = products[start:end]
    total_pages = (total + per_page - 1) // per_page

    return render_template(
        'shop-grid.html',
        title="🛍️ Sản phẩm",
        products=products_page,
        categories=categories,
        brands=brands,
        page=page,
        total_pages=total_pages,
        total_products=total
    )

@app.route('/contact')
def contact():


    return render_template(
        'contact.html',
    )

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    df_info, df_comments, df_blog = load_data()


    product_info = df_info[df_info['product_id'] == product_id].to_dict(orient='records')
    if not product_info:
        return "Product not found", 404

    product = product_info[0]

    # Lấy comment liên quan và sắp xếp
    comments = df_comments[df_comments['product_id'] == product_id].sort_values(by='created_at', ascending=False)
    product['comments'] = comments.to_dict(orient='records')

    return render_template('shop-details.html', product=product)


@app.route('/blog/<int:blog_id>')
def blog_detail(blog_id):
    df_info, df_comments, df_blog = load_data()

    blog_info = df_blog[df_blog['id'] == blog_id]
    if blog_info.empty:
        return "Blog post not found", 404
    blog_row = blog_info.iloc[0]

    blog_post = {
        "id": blog_row['id'],
        "title": blog_row.get('title', ''),
        "time": blog_row.get('time', ''),
        "content": blog_row.get('content', ''),
        "images": json.loads(blog_row['images']) if isinstance(blog_row['images'], str) else blog_row['images'],
        "url": blog_row.get('url', ''),
    }



    # --- Lấy các bài viết khác ngẫu nhiên ---
    available_df = df_blog.copy()

    sample_size = min(3, len(available_df))  # nếu ít hơn 3 thì lấy hết
    related_df = available_df.sample(n=sample_size, random_state=None)  # random_state=None để ngẫu nhiên thực sự

    related_posts = []
    for _, row in related_df.iterrows():
        related_posts.append({
            "id": row['id'],
            "title": row.get('title', ''),
            "time": row.get('time', ''),
            "content": row.get('content', ''),
            "images": json.loads(row['images']) if isinstance(row['images'], str) else row['images'],
            
        })

    return render_template('blog-details.html', blog_post=blog_post, related_posts=related_posts)



@app.route('/')
def home():
    df_info, df_comments, df_blog = load_data()  # unpack 3 dataframe

    featured_products = df_info.head(12).to_dict(orient='records')

    latest_products = (
        df_info.sort_values(by='discount', ascending=False)
               .dropna(subset=['name', 'price', 'image_url'])
               .head(6)
               .to_dict(orient='records')
    )

    top_rated_products = (
        df_info.sort_values(by='rating_average', ascending=False)
               .dropna(subset=['name', 'price', 'image_url'])
               .head(6)
               .to_dict(orient='records')
    )

    review_products = (
        df_info.sort_values(by='review_count', ascending=False)  # sửa cho đúng dữ liệu review
               .dropna(subset=['name', 'price', 'image_url'])
               .head(6)
               .to_dict(orient='records')
    )

    categories_df = (
        df_info.dropna(subset=['category', 'image_url'])
               .drop_duplicates(subset='category')
               [['category', 'image_url']]
               .head(5)
    )
    categories = categories_df.to_dict(orient='records')

    brands = sorted(df_info['brand'].dropna().unique())

    # Lấy 5 bài blog mới nhất (có thể tùy chỉnh theo cột 'time' nếu cần)
    blog_latest = df_blog.sort_values(by='time', ascending=False).head(5).to_dict(orient='records')

    return render_template('index.html',
                           title="🏠 Trang chủ",
                           products=latest_products,
                           top_rated_products=top_rated_products,
                           review_products=review_products,
                           categories=categories,
                           brands=brands,
                           blog_posts=blog_latest)
import re
import ast
def clean_datetime_str(s):
    if not isinstance(s, str):
        return s
    # Bỏ phần "Thứ hai," hoặc các thứ khác
    s = re.sub(r"^Thứ [a-z]+,\s*", "", s, flags=re.IGNORECASE)
    # Bỏ phần (GMT+7) hoặc tương tự
    s = re.sub(r"\s*\(GMT[+-]\d+\)", "", s, flags=re.IGNORECASE)
    return s.strip()
def load_blog_data():
    basedir = os.path.abspath(os.path.dirname(__file__))
    blog_path = os.path.join(basedir, 'vnexpress_random_articles_20250521_195908.csv')

    df_blog = pd.read_csv(blog_path)

    # Đảm bảo có cột 'id'
    if 'id' not in df_blog.columns:
        df_blog['id'] = df_blog.index

    # Parse images thành list
    if 'images' in df_blog.columns:
        df_blog['images'] = df_blog['images'].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else [])
    else:
        df_blog['images'] = [[]] * len(df_blog)

    # Làm sạch thời gian và định dạng
    df_blog['time'] = df_blog['time'].apply(clean_datetime_str)
    df_blog['time'] = pd.to_datetime(df_blog['time'], dayfirst=True, errors='coerce')
    df_blog['formatted_time'] = df_blog['time'].dt.strftime('%b %d, %Y')

    # Nếu không có summary, tạo từ content
    df_blog['summary'] = df_blog['content'].apply(lambda x: x[:150] + '...' if isinstance(x, str) else '')

    return df_blog
@app.route('/blog')
def blog():
    page = request.args.get('page', default=1, type=int)
    per_page = 5

    df_blog = load_blog_data()

    # Sắp xếp mới nhất trước
    df_blog = df_blog.sort_values(by='time', ascending=False)

    # Tính phân trang
    total_pages = (len(df_blog) + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page

    blog_posts = df_blog.iloc[start:end].to_dict(orient='records')

    return render_template(
        'blog.html',
        title="🏠 Blog",
        blog_posts=blog_posts,
        page=page,
        total_pages=total_pages
    )


@app.route('/best-selling')
def best_selling():
    df = load_data()
    top_products = df.sample(n=6) if len(df) >= 6 else df
    return render_template('best_selling.html', running_cakes=top_products.to_dict(orient='records'))

@app.route('/search', methods=['GET', 'POST'])
def search():
    results_html = ""
    if request.method == 'POST':
        query = request.form.get('search_query', '').strip().lower()
        df = load_data()
        df['name_lower'] = df['name'].astype(str).str.lower()
        results = df[df['name_lower'].str.contains(query)]
        
        if not results.empty:
            results_html = results.drop(columns=['name_lower']).to_html(classes='data', index=False)
        else:
            results_html = "<p>❌ Không tìm thấy sản phẩm phù hợp.</p>"

    return render_template('search.html', title="🔍 Tìm kiếm", table=results_html)

@app.route('/product_ids')
def show_product_ids():
    path = os.path.join(basedir, 'product_id_ncds.csv')
    df = pd.read_csv(path)
    return render_template('table.html', title="📦 Danh sách Product ID", table=df.to_html(classes='data', index=False))

@app.route('/comments')
def show_comments():
    path = os.path.join(basedir, 'product_comments_ncds.csv')
    df = pd.read_csv(path)
    return render_template('table.html', title="💬 Đánh giá sản phẩm", table=df.to_html(classes='data', index=False))

@app.route('/register', methods=['GET', 'POST'])
def register():
    user_file = os.path.join(basedir, 'users.csv')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not email or not password:
            return jsonify({'status': 'error', 'message': '❌ Vui lòng điền đầy đủ thông tin.'})

        # Kiểm tra file tồn tại và đọc dữ liệu cũ
        file_exists = os.path.exists(user_file)
        if file_exists and os.path.getsize(user_file) > 0:
            df_existing = pd.read_csv(user_file)

            # Kiểm tra trùng nội dung
            duplicate = df_existing[
                (df_existing['username'] == username) &
                (df_existing['email'] == email) &
                (df_existing['password'] == password)
            ]
            if not duplicate.empty:
                return jsonify({'status': 'error', 'message': '⚠️ Tài khoản đã tồn tại.'})

            # Lấy id cuối cùng
            last_id = df_existing['id'].max()
        else:
            df_existing = pd.DataFrame()
            last_id = 0

        new_id = last_id + 1

        # Ghi dòng mới
        df_new = pd.DataFrame([{
            'id': new_id,
            'username': username,
            'email': email,
            'password': password
        }])
        df_new.to_csv(user_file, mode='a', index=False, header=not file_exists or os.path.getsize(user_file) == 0)

        return jsonify({'status': 'success', 'message': '✅ Đăng ký thành công!'})

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.pop('id', None)
    return "Bạn đã đăng xuất."

user_file = os.path.join(basedir, 'users.csv')

user_file = os.path.join(os.path.dirname(__file__), 'users.csv')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    # Lấy dữ liệu từ form
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    # Kiểm tra dữ liệu đầu vào
    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Vui lòng nhập đầy đủ thông tin đăng nhập.'})

    # Kiểm tra tồn tại file người dùng
    if not os.path.exists(user_file):
        return jsonify({'status': 'error', 'message': 'Chưa có tài khoản đăng ký.'})

    try:
        # Đọc dữ liệu từ CSV
        df = pd.read_csv(user_file)
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Lỗi đọc dữ liệu người dùng: {str(e)}'})

    # Tìm người dùng theo username
    user_row = df[df['username'] == username]

    if user_row.empty:
        return jsonify({'status': 'error', 'message': 'Tên đăng nhập không tồn tại.'})

    # Lấy mật khẩu và so sánh
    stored_password = str(user_row.iloc[0]['password'])
    if password == stored_password:
        # Lưu thông tin vào session
        session['id'] = int(user_row.iloc[0]['id'])  # id phải là số
        session['username'] = user_row.iloc[0]['username']
        session['email'] = user_row.iloc[0]['email']

        return jsonify({'status': 'success', 'message': 'Đăng nhập thành công!'})
    else:
        return jsonify({'status': 'error', 'message': 'Mật khẩu không đúng.'})



@app.route('/header')
def header():
    user_file = os.path.join(basedir, 'users.csv')

    # Lấy id đúng key
    user_id = session.get('id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Chưa đăng nhập'}), 401

    if not os.path.exists(user_file):
        return jsonify({'status': 'error', 'message': 'Không tìm thấy dữ liệu người dùng'}), 500

    df_users = pd.read_csv(user_file)

    user_row = df_users[df_users['id'] == user_id]

    if user_row.empty:
        return jsonify({'status': 'error', 'message': 'Người dùng không tồn tại'}), 404

    user_data = user_row.iloc[0][['id', 'username', 'email']].to_dict()

    username = user_row.iloc[0]['username']

    return f"Xin chào {username}!"

@app.route('/test-session')
def test_session():
    user_id = session.get('id')
    return f"user_id trong session là: {user_id}"






@app.route('/save-product/<int:product_id>', methods=['POST'])
def save_product(product_id):
    user_id = session.get('id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Bạn cần đăng nhập để lưu sản phẩm.'}), 401

    save_file = os.path.join(basedir, 'saved_products.csv')

    if os.path.exists(save_file):
        df = pd.read_csv(save_file)
    else:
        df = pd.DataFrame(columns=['user_id', 'product_id'])

    # Kiểm tra đã lưu chưa
    if not ((df['user_id'] == user_id) & (df['product_id'] == product_id)).any():
        df = pd.concat([df, pd.DataFrame([{'user_id': user_id, 'product_id': product_id}])], ignore_index=True)
        df.to_csv(save_file, index=False)

    return jsonify({'status': 'success', 'message': '✅ Sản phẩm đã được lưu!'})
@app.route('/saved-products')
def view_saved_products():
    user_id = session.get('id')
    if not user_id:
        return "Bạn cần đăng nhập để xem sản phẩm đã lưu.", 401

    save_file = os.path.join(basedir, 'saved_products.csv')
    if not os.path.exists(save_file):
        return render_template('saved_products.html', products=[])

    df_saved = pd.read_csv(save_file)
    df_info, _, _ = load_data()

    saved_ids = df_saved[df_saved['user_id'] == user_id]['product_id'].tolist()

    products = df_info[df_info['product_id'].isin(saved_ids)].to_dict(orient='records')

    return render_template('shoping-cart.html', products=products, title="❤️ Sản phẩm đã lưu")



@app.route('/delete-saved-product/<int:product_id>', methods=['POST'])
def delete_saved_product(product_id):
    user_id = session.get('id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Bạn cần đăng nhập.'}), 401

    save_file = os.path.join(basedir, 'saved_products.csv')
    if not os.path.exists(save_file):
        return jsonify({'status': 'error', 'message': 'Không có dữ liệu lưu.'}), 404

    df = pd.read_csv(save_file)
    df = df[~((df['user_id'] == user_id) & (df['product_id'] == product_id))]

    df.to_csv(save_file, index=False)

    return jsonify({'status': 'success', 'message': '🗑️ Đã xóa sản phẩm khỏi danh sách lưu.'})













if __name__ == '__main__':
    app.run(debug=True)
