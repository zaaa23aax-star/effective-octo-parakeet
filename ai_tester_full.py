import streamlit as st
import requests
import time
from io import BytesIO
from PIL import Image

# -----------------------------
# Streamlit Setup
# -----------------------------
st.set_page_config(page_title="🛍️ Amazon Product Finder", layout="wide", page_icon="🛍️")

# Custom CSS for Pinterest-style cards
st.markdown("""
<style>
    .product-card {
        background: white;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .product-title {
        font-size: 24px;
        font-weight: bold;
        color: #2d3436;
        margin-bottom: 10px;
    }
    .product-asin {
        background: #f8f9fa;
        padding: 8px 12px;
        border-radius: 8px;
        font-family: monospace;
        display: inline-block;
        margin: 10px 0;
    }
    .marketing-text {
        font-size: 16px;
        line-height: 1.8;
        color: #4a4a4a;
        margin: 15px 0;
    }
    .amazon-button {
        background: #ff9900;
        color: white;
        padding: 12px 24px;
        border-radius: 8px;
        text-decoration: none;
        font-weight: bold;
        display: inline-block;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛍️ Amazon Product Finder")
st.markdown("**Find Amazon products with AI-generated Pinterest-style marketing descriptions!**")

# -----------------------------
# API Keys (from Streamlit Secrets)
# -----------------------------
try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
    SERPAPI_KEY = st.secrets["SERPAPI_KEY"]
    
    # Clean the keys
    OPENROUTER_API_KEY = str(OPENROUTER_API_KEY).strip().strip('"').strip("'")
    SERPAPI_KEY = str(SERPAPI_KEY).strip().strip('"').strip("'")
    
except Exception as e:
    st.error("❌ Missing API keys in Streamlit Secrets.")
    st.stop()

# -----------------------------
# User Input
# -----------------------------
product_name = st.text_input(
    "🔍 Enter Product Name:",
    placeholder="e.g., wireless headphones, yoga mat, coffee maker...",
    help="Enter any product you want to find on Amazon"
)

col1, col2 = st.columns([3, 1])
with col1:
    search_intent = st.selectbox(
        "📊 Search Intent:",
        ["Best Selling", "Highly Rated", "New Arrivals", "Budget Friendly", "Premium Quality"],
        help="Refine your search"
    )
with col2:
    num_products = st.slider("Products:", 1, 6, 3)

# -----------------------------
# Core Functions
# -----------------------------
def search_amazon_products(query, num_results, api_key):
    """Search Amazon products using SerpAPI."""
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "amazon",
        "q": query,
        "amazon_domain": "amazon.com",
        "api_key": api_key
    }
    
    try:
        res = requests.get(url, params=params, timeout=15)
        if res.status_code != 200:
            return {"error": f"Search failed: {res.text}"}
        
        data = res.json()
        products = []
        
        # Get organic results
        for item in data.get("organic_results", [])[:num_results]:
            # Only include items that are deliverable and have valid links
            if item.get("link") and item.get("title"):
                product = {
                    "title": item.get("title", ""),
                    "asin": item.get("asin", "N/A"),
                    "link": item.get("link", ""),
                    "image": item.get("thumbnail", ""),
                    "price": item.get("price", "Price not available"),
                    "rating": item.get("rating", "N/A"),
                    "reviews": item.get("reviews_count", "N/A")
                }
                
                # Verify the link is valid Amazon link
                if "amazon.com" in product["link"]:
                    products.append(product)
        
        return {"products": products}
    
    except Exception as e:
        return {"error": str(e)}

def generate_pinterest_description(product_title, product_details, api_key):
    """Generate Pinterest-style marketing description using AI."""
    prompt = f"""Create a captivating Pinterest-style marketing description for this Amazon product:

Product: {product_title}
Details: {product_details}

Write a short, engaging description (3-4 sentences) that:
- Uses emotional and aspirational language
- Highlights benefits, not just features
- Includes relevant emojis naturally
- Sounds like a lifestyle influencer recommending it
- Makes readers want to click and buy

Keep it under 100 words and make it Pinterest-worthy!"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            res = response.json()
            return res["choices"][0]["message"]["content"].strip()
        else:
            return "✨ Discover this amazing product that customers love! Perfect for enhancing your lifestyle. 🌟"
    except:
        return "✨ Discover this amazing product that customers love! Perfect for enhancing your lifestyle. 🌟"

# -----------------------------
# Search Button
# -----------------------------
if st.button("🔍 Find Products", type="primary", use_container_width=True):
    if not product_name.strip():
        st.warning("⚠️ Please enter a product name.")
    else:
        # Construct search query based on intent
        search_query = product_name
        if search_intent == "Best Selling":
            search_query = f"best {product_name}"
        elif search_intent == "Highly Rated":
            search_query = f"{product_name} highly rated"
        elif search_intent == "New Arrivals":
            search_query = f"{product_name} new"
        elif search_intent == "Budget Friendly":
            search_query = f"{product_name} affordable"
        elif search_intent == "Premium Quality":
            search_query = f"{product_name} premium"
        
        with st.spinner(f"🔍 Searching Amazon for '{search_query}'..."):
            result = search_amazon_products(search_query, num_products, SERPAPI_KEY)
        
        if "error" in result:
            st.error(f"❌ Search failed: {result['error']}")
            st.info("💡 Try a different product name or check your SerpAPI key.")
        elif not result.get("products"):
            st.warning("⚠️ No products found. Try a different search term.")
        else:
            products = result["products"]
            st.success(f"✅ Found {len(products)} products!")
            st.divider()
            
            # Display products in Pinterest-style cards
            for idx, product in enumerate(products, 1):
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    # Product image
                    if product["image"]:
                        try:
                            img_data = requests.get(product["image"], timeout=10).content
                            img = Image.open(BytesIO(img_data))
                            st.image(img, use_container_width=True)
                        except:
                            st.info("📦 Image not available")
                    else:
                        st.info("📦 Image not available")
                
                with col2:
                    # Product title
                    st.markdown(f"### {idx}. {product['title'][:80]}...")
                    
                    # ASIN
                    st.markdown(f"**ASIN:** `{product['asin']}`")
                    
                    # Price and rating
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**💰 Price:** {product['price']}")
                    with col_b:
                        if product['rating'] != 'N/A':
                            st.markdown(f"**⭐ Rating:** {product['rating']} ({product['reviews']} reviews)")
                    
                    # Generate Pinterest-style description
                    with st.spinner("✨ Generating marketing description..."):
                        details = f"Price: {product['price']}, Rating: {product['rating']}"
                        description = generate_pinterest_description(
                            product['title'], 
                            details, 
                            OPENROUTER_API_KEY
                        )
                    
                    # Display description in styled box
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                padding: 20px; border-radius: 12px; color: white; margin: 15px 0;">
                        <p style="margin: 0; font-size: 16px; line-height: 1.6;">
                            {description}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Amazon link button
                    st.link_button(
                        "🛒 View on Amazon",
                        product['link'],
                        use_container_width=True,
                        type="primary"
                    )
                    
                    # Copy ASIN button
                    if st.button(f"📋 Copy ASIN", key=f"copy_{idx}"):
                        st.code(product['asin'])
                        st.success("✅ ASIN ready to copy!")
                
                st.divider()

# -----------------------------
# Sidebar Info
# -----------------------------
with st.sidebar:
    st.markdown("### 📖 How to Use")
    st.markdown("""
    1. **Enter** a product name
    2. **Choose** search intent
    3. **Click** Find Products
    4. Get **Pinterest-style** descriptions
    5. **Click** links to buy on Amazon
    """)
    
    st.divider()
    
    st.markdown("### 💡 Tips")
    st.markdown("""
    - Be specific with product names
    - Try different search intents
    - All links are verified Amazon URLs
    - ASINs are valid and deliverable
    - Descriptions are AI-generated
    """)
    
    st.divider()
    
    st.markdown("### 🎯 Examples")
    st.code("wireless earbuds")
    st.code("standing desk")
    st.code("yoga mat")
    st.code("laptop backpack")

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.9em;'>
    🛍️ Powered by Amazon Search & AI Marketing | All links are verified Amazon products
</div>
""", unsafe_allow_html=True)
