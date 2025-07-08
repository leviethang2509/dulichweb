import requests
import pandas as pd
import time
import random
import sqlite3
from datetime import datetime
from bs4 import BeautifulSoup
# --- Kết nối SQLite để lưu ID sản phẩm ---
conn = sqlite3.connect('products_traicay.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS id (
        id INTEGER PRIMARY KEY
    )
''')

# --- Header và API endpoint ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
}
API_PRODUCT_LIST = 'https://tiki.vn/api/personalish/v1/blocks/listings'
API_PRODUCT_DETAIL = 'https://tiki.vn/api/v2/products/{}'
API_PRODUCT_REVIEWS = 'https://tiki.vn/api/v2/reviews'

# --- Cấu hình category trái cây ---
CATEGORY_ID = '2601'
URL_KEY = 'trai-cay'

# --- Hàm crawl ID sản phẩm ---
def crawl_product_ids(pages=5):
    print("🔍 Đang thu thập ID sản phẩm trái cây...")
    product_ids = []
    for i in range(1, pages + 1):
        params = {
            'limit': '48',
            'include': 'category',
            'aggregations': '1',
            'trackity_id': 'crawler_traicay',
            'category': CATEGORY_ID,
            'page': str(i),
            'src': f'c{CATEGORY_ID}',
            'urlKey': URL_KEY,
        }
        try:
            response = requests.get(API_PRODUCT_LIST, headers=HEADERS, params=params)
            print(f"[DEBUG] Trang {i} - Status code: {response.status_code}")
            print(f"[DEBUG] Trang {i} - Response snippet: {response.text[:300]}")  # In 300 ký tự đầu

            response.raise_for_status()
            data = response.json().get('data', [])
            for item in data:
                pid = item.get('id')
                if pid:
                    product_ids.append(pid)
                    cursor.execute('INSERT OR IGNORE INTO id (id) VALUES (?)', (pid,))
            print(f"✅ Đã lấy ID trang {i} - Tổng ID hiện có: {len(product_ids)}")
        except Exception as e:
            print(f"❌ Lỗi khi crawl trang {i}: {e}")
        time.sleep(random.uniform(1.5, 3))
    conn.commit()
    return product_ids

# --- Hàm crawl chi tiết sản phẩm ---
def crawl_product_details(product_ids):
    print("📦 Đang crawl thông tin chi tiết sản phẩm...")
    details = []
    for pid in product_ids:
        try:
            url = API_PRODUCT_DETAIL.format(pid)
            res = requests.get(url, headers=HEADERS)
            print(f"[DEBUG] Product {pid} - Status code: {res.status_code}")
            print(f"[DEBUG] Product {pid} - Response snippet: {res.text[:300]}")

            res.raise_for_status()
            data = res.json()
            item = {
                'id': data.get('id'),
                'name': data.get('name'),
                'brand': data.get('brand', {}).get('name'),
                'price': data.get('price'),
                'rating': data.get('rating_average'),
                'review_count': data.get('review_count'),
                'short_description': data.get('short_description'),
                'category': data.get('categories', [{}])[-1].get('name'),
                'image_url': data.get('thumbnail_url'),
                'url': f"https://tiki.vn/p-{data.get('id')}"
            }
            details.append(item)
        except Exception as e:
            print(f"⚠️ Lỗi crawl sản phẩm {pid}: {e}")
        time.sleep(random.uniform(1, 2))
    return pd.DataFrame(details)

# --- Hàm crawl đánh giá sản phẩm ---
def crawl_product_reviews(product_ids, max_reviews=10):
    print("📝 Đang crawl đánh giá sản phẩm...")
    all_reviews = []
    for pid in product_ids:
        try:
            for page in range(1, 3):
                params = {
                    'product_id': pid,
                    'limit': max_reviews,
                    'page': page,
                }
                res = requests.get(API_PRODUCT_REVIEWS, headers=HEADERS, params=params)
                print(f"[DEBUG] Reviews product {pid} page {page} - Status code: {res.status_code}")
                print(f"[DEBUG] Reviews product {pid} page {page} - Response snippet: {res.text[:300]}")

                res.raise_for_status()
                reviews = res.json().get('data', [])
                for r in reviews:
                    all_reviews.append({
                        'product_id': pid,
                        'rating': r.get('rating'),
                        'comment': r.get('content'),
                        'created_at': r.get('created_at'),
                        'thank_count': r.get('thank_count')
                    })
                time.sleep(random.uniform(1, 2))
        except Exception as e:
            print(f"⚠️ Lỗi đánh giá sản phẩm {pid}: {e}")
    return pd.DataFrame(all_reviews)

# --- Hàm lưu dataframe ra CSV ---
def export_to_csv(df, prefix='traicay'):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.csv"
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"📁 Đã lưu file: {filename}")
# --- Hàm crawl dữ liệu sách từ OpenLibrary ---
def crawl_article_vnexpress(url):
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        res.raise_for_status()
        soup = BeautifulSoup(res.content, 'html.parser')

        title = soup.find('h1', class_='title-detail').get_text(strip=True)
        time_posted = soup.find('span', class_='date').get_text(strip=True)
        article_body = soup.find('article', class_='fck_detail')
        content = "\n".join([p.get_text(strip=True) for p in article_body.find_all('p')])

        return {
            'title': title,
            'time': time_posted,
            'content': content
        }
    except Exception as e:
        print(f"❌ Lỗi khi lấy bài viết: {e}")
        return None
def get_article_id_from_url(url):
    # Lấy phần cuối URL trước ".html"
    try:
        base = url.split('/')[-1]  # lấy phần cuối, ví dụ: co-gai-my-noi-tieng-v...-4887283.html
        id_part = base.split('-')[-1]  # lấy đoạn cuối sau dấu "-", ví dụ: "4887283.html"
        article_id = id_part.split('.')[0]  # lấy số trước ".html"
        return article_id
    except Exception:
        return None

from urllib.parse import urljoin
import csv
import time

def crawl_articles_with_images(url_list, max_articles=20):
    results = []
    for url in url_list:
        article = crawl_article_vnexpress(url)
        if article:
            results.append(article)
            print(f"✅ Đã lấy: {article['title']}")
        else:
            print(f"⚠️ Bỏ qua: {url}")

        if len(results) >= max_articles:
            break

        time.sleep(1)  # Tránh bị chặn

    return results

def save_articles_to_csv(articles, filename='articles.csv'):
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'title', 'time', 'content', 'images', 'url'])
        writer.writeheader()
        for article in articles:
            writer.writerow({
                'id': article['id'],
                'title': article['title'],
                'time': article['time'],
                'content': article['content'],
                'images': ', '.join(article['images']),
                'url': article['url']
            })
    print(f"📁 Đã xuất {len(articles)} bài viết ra file: {filename}")

def crawl_article_vnexpress(url):
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        title = soup.find('h1', class_='title-detail')
        time_post = soup.find('span', class_='date')
        content_div = soup.find('article', class_='fck_detail')

        if not all([title, time_post, content_div]):
            return None

        paragraphs = content_div.find_all('p')
        content = "\n".join([p.get_text(strip=True) for p in paragraphs])

        # Chỉ lấy ảnh hiển thị được (URL bắt đầu bằng http/https)
        images = []
        for img_tag in content_div.find_all('img'):
            img_url = img_tag.get('src')
            full_url = urljoin(url, img_url)
            if full_url.startswith('http'):
                images.append(full_url)

        # Nếu không có ảnh hợp lệ thì bỏ qua bài viết
        if not images:
            return None

        article_id = get_article_id_from_url(url)

        return {
            'id': article_id,
            'title': title.text.strip(),
            'time': time_post.text.strip(),
            'content': content.strip(),
            'images': images,
            'url': url
        }
    except Exception as e:
        print(f"❌ Lỗi crawl bài viết: {e}")
        return None


def crawl_articles_random_from_vnexpress(pages=3, max_articles=10):
    base_url = "https://vnexpress.net/doi-song-p{page}"
    article_links = set()

    print(f"📥 Đang lấy ngẫu nhiên bài viết từ chuyên mục Đời sống (tối đa {max_articles})...")

    for page in range(1, pages + 1):
        url = base_url.format(page=page)
        print(f"🔍 Đang duyệt trang {page}: {url}")
        try:
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')

            # Lấy các link bài viết
            links = soup.select('h3.title-news a[href]')
            for link in links:
                href = link['href']
                if href.startswith('https://vnexpress.net/') and '/video/' not in href:
                    article_links.add(href)

            time.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            print(f"❌ Lỗi khi đọc trang {page}: {e}")

    print(f"🔗 Tổng số link bài viết tìm thấy: {len(article_links)}")

    # Lấy ngẫu nhiên max_articles bài
    selected_links = random.sample(list(article_links), min(max_articles, len(article_links)))

    articles = []
    for url in selected_links:
        article = crawl_article_vnexpress(url)
        if article:
            articles.append(article)
            print(f"✅ Đã lấy: {article['title']}")
        else:
            print(f"⚠️ Bỏ qua (không lấy được): {url}")
        time.sleep(random.uniform(0.5, 1.0))

    if articles:
        df = pd.DataFrame(articles)
        filename = f"vnexpress_random_articles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"\n📁 Đã lưu {len(df)} bài viết vào file: {filename}")
    else:
        print("⚠️ Không lấy được bài viết nào.")

    return articles
# --- Main menu ---
if __name__ == "__main__":
    while True:
        print("\n====== MENU CRAWL DỮ LIỆU ======")
        print("1. Crawl ID sản phẩm trái cây")
        print("2. Crawl chi tiết sản phẩm trái cây")
        print("3. Crawl đánh giá sản phẩm trái cây")
        print("4. Thoát")
        print("5. Crawl bài viết VNExpress có ảnh (mẹo đồ gia dụng)")

        choice = input("👉 Chọn chức năng (1-5): ")

        if choice == '1':
            product_ids = crawl_product_ids(pages=5)
            print(f"🔢 Tổng số ID đã lấy: {len(product_ids)}")

        elif choice == '2':
            cursor.execute("SELECT id FROM id")
            ids = [row[0] for row in cursor.fetchall()]
            if not ids:
                print("⚠️ Chưa có ID sản phẩm. Vui lòng crawl ID trước.")
                continue
            df_details = crawl_product_details(ids)
            export_to_csv(df_details, prefix="product_details_traicay")

        elif choice == '3':
            cursor.execute("SELECT id FROM id")
            ids = [row[0] for row in cursor.fetchall()]
            if not ids:
                print("⚠️ Chưa có ID sản phẩm. Vui lòng crawl ID trước.")
                continue
            df_reviews = crawl_product_reviews(ids)
            export_to_csv(df_reviews, prefix="product_reviews_traicay")

        elif choice == '4':
            print("👋 Thoát chương trình.")
            break

        elif choice == '5':
            # Ví dụ: dùng hàm crawl ngẫu nhiên từ VNExpress Đời sống
            print("📥 Bắt đầu crawl bài viết VNExpress có ảnh...")
            articles = crawl_articles_random_from_vnexpress(pages=5, max_articles=20)
            # Lưu file CSV (hàm crawl_articles_random_from_vnexpress đã tự lưu rồi, nếu muốn gọi riêng thì bỏ dòng lưu trong hàm đó)
            # save_articles_to_csv(articles, 'meo-do-gia-dung.csv')

        else:
            print("⚠️ Lựa chọn không hợp lệ, vui lòng chọn lại.")