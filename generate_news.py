import os
import re
import ssl
import html
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

# Bypass SSL verification for system-level python environments
ssl._create_default_https_context = ssl._create_unverified_context

# Target output files
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_HTML_PATH = os.path.join(WORKSPACE_DIR, "index.html")

import urllib.parse
import hashlib

# Curated dynamic mapping to Lorem Flickr for virtually unlimited unique category photos
def get_fallback_image(title, category):
    """Deterministically maps a title and category to a unique, dynamic Lorem Flickr image fallback."""
    category_tags = {
        "ai-news": "artificial,intelligence",
        "cybersecurity": "hacker,security",
        "space": "galaxy,space",
        "robotics": "robot,android",
        "startups": "startup,office",
        "technology": "technology,gadget",
        "business": "business,finance",
        "science": "science,laboratory",
        "world": "city,travel",
        "latest-news": "news,journalism"
    }
    tag = category_tags.get(category, "news")
    # Generate a deterministic integer lock index based on title hash
    h_idx = int(hashlib.md5(title.encode('utf-8')).hexdigest(), 16)
    lock_val = h_idx % 100000
    
    return f"https://loremflickr.com/800/450/{tag}?lock={lock_val}"

# Feeds Configuration
FEEDS = [
    {"source": "BBC News", "category": "world", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"source": "BBC News", "category": "technology", "url": "https://feeds.bbci.co.uk/news/technology/rss.xml"},
    {"source": "BBC News", "category": "science", "url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"},
    {"source": "BBC News", "category": "business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    {"source": "TechCrunch", "category": "startups", "url": "https://techcrunch.com/feed/"},
    {"source": "The Verge", "category": "technology", "url": "https://www.theverge.com/rss/index.xml"},
    {"source": "Wired", "category": "technology", "url": "https://www.wired.com/feed/rss"},
    {"source": "Ars Technica", "category": "technology", "url": "https://feeds.arstechnica.com/arstechnica/index"},
    {"source": "CNBC", "category": "business", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"},
    {"source": "NASA", "category": "space", "url": "https://www.nasa.gov/feed/"},
    {"source": "Nature", "category": "science", "url": "https://www.nature.com/nature.rss"}
]

def clean_html(raw_html):
    """Strips HTML tags and unescapes entities."""
    if not raw_html:
        return ""
    # Strip HTML tags
    cleanr = re.compile('<.*?>|&zwnj;|&nbsp;')
    cleantext = re.sub(cleanr, '', raw_html)
    # Unescape HTML entities
    cleantext = html.unescape(cleantext)
    # Remove excessive spaces/newlines
    cleantext = re.sub(r'\s+', ' ', cleantext).strip()
    return cleantext

def parse_pubdate(pubdate_str):
    """Converts a feed publication date string into a UTC datetime object."""
    if not pubdate_str:
        return datetime.now(timezone.utc)
    try:
        # Standard RFC 2822 format (e.g. "Fri, 03 Jul 2026 12:00:00 GMT")
        return parsedate_to_datetime(pubdate_str).astimezone(timezone.utc)
    except Exception:
        pass

    try:
        # ISO 8601 / W3C Atom format (e.g. "2026-07-03T12:00:00Z" or "2026-07-03T12:00:00+05:30")
        # Handle Zulu (Z) suffix
        if pubdate_str.endswith('Z'):
            pubdate_str = pubdate_str[:-1] + '+00:00'
        return datetime.fromisoformat(pubdate_str).astimezone(timezone.utc)
    except Exception:
        pass

    # Fallback to current time if unparseable
    return datetime.now(timezone.utc)

def is_tracker(url):
    """Checks if the image URL is likely a tracking pixel or social icon."""
    url_lower = url.lower()
    trackers = ['1x1', 'gravatar', 'doubleclick', 'pixel', 'analytics', 'spacer', 'feedburner', 'adsystem', 'facebook.com/tr', 'google-analytics', 'sharing', 'share_icon']
    return any(t in url_lower for t in trackers)

def clean_and_upgrade_url(url):
    """Upgrades low-res image URLs to higher resolution and cleans schema-less URLs."""
    if not url:
        return None
    url = url.strip()
    if url.startswith('//'):
        url = 'https:' + url
        
    # Upgrade BBC dimensions from standard low-res (240x135, 240, 320) to 800 for grids
    if 'ichef.bbci.co.uk' in url:
        url = url.replace('/standard/240/', '/standard/800/')
        url = url.replace('/standard/320/', '/standard/800/')
        url = url.replace('/240x135/', '/800x450/')
        
    return url

def extract_image_url(item_node, entry_description, encoded_content=None):
    """Tries to extract image URLs from enclosures, media namespaces, or img tags."""
    # 1. Search item XML tags (enclosures, media:content, etc.)
    for child in item_node:
        tag_lower = child.tag.lower()
        if 'enclosure' in tag_lower or 'content' in tag_lower or 'thumbnail' in tag_lower:
            url = child.attrib.get('url')
            if url and not is_tracker(url):
                ctype = child.attrib.get('type', '')
                if 'image' in ctype or any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    return clean_and_upgrade_url(url)

    # 2. Extract image from description HTML (e.g. <img src="...">)
    if entry_description:
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry_description)
        if match:
            url = match.group(1)
            if not is_tracker(url):
                return clean_and_upgrade_url(url)

    # 3. Extract image from content:encoded HTML
    if encoded_content:
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', encoded_content)
        if match:
            url = match.group(1)
            if not is_tracker(url):
                return clean_and_upgrade_url(url)

    return None

def classify_category(title, description, feed_default_cat):
    """Classifies articles dynamically based on keywords in title and description."""
    text = (title + " " + (description or "")).lower()
    # Normalize words by stripping punctuation and splitting
    words = set(re.sub(r'[^\w\s]', ' ', text).split())
    
    # 1. AI News
    ai_phrases = ["artificial intelligence", "machine learning", "neural network", "generative ai"]
    ai_words = ["ai", "llm", "chatgpt", "openai", "claude", "gemini", "midjourney", "deepmind", "copilot"]
    if any(p in text for p in ai_phrases) or any(w in words for w in ai_words):
        return "ai-news"

    # 2. Cybersecurity
    cyber_phrases = ["pegasus spyware", "zero day", "cyber attack"]
    cyber_words = ["cybersecurity", "cyber", "malware", "spyware", "hacked", "hacker", "ransomware", "phishing", "vulnerability", "ddos", "breach", "exploit"]
    if any(p in text for p in cyber_phrases) or any(w in words for w in cyber_words):
        return "cybersecurity"

    # 3. Space
    space_words = ["space", "nasa", "artemis", "spacex", "mars", "moon", "orbit", "rocket", "astronaut", "satellite", "galaxy", "telescope", "hubble", "jwst", "asteroid", "comet"]
    if "space telescope" in text or any(w in words for w in space_words):
        return "space"

    # 4. Robotics
    robot_words = ["robot", "robotics", "drone", "drones", "autonomous", "humanoid", "self-driving"]
    if "boston dynamics" in text or any(w in words for w in robot_words):
        return "robotics"

    # 5. Startups
    startup_phrases = ["venture capital", "seed round", "y combinator"]
    startup_words = ["startup", "startups", "funding", "yc", "ipo", "unicorn"]
    if any(p in text for p in startup_phrases) or any(w in words for w in startup_words):
        return "startups"

    # 6. Technology
    tech_phrases = ["smart home", "virtual reality", "augmented reality"]
    tech_words = ["tech", "technology", "software", "hardware", "apple", "google", "microsoft", "meta", "samsung", "nvidia", "intel", "amd", "gadget", "gadgets", "iphone", "android", "windows", "macos", "linux", "chip", "chips", "semiconductor", "device", "devices", "headphone", "headphones", "console", "playstation", "xbox", "nintendo"]
    if any(p in text for p in tech_phrases) or any(w in words for w in tech_words):
        return "technology"

    # 7. Business
    biz_phrases = ["stock market", "fiscal year", "interest rates"]
    biz_words = ["business", "market", "markets", "stock", "stocks", "economy", "finance", "earnings", "ceo", "ceos", "acquisition", "merger", "inflation", "revenue", "fiscal"]
    if any(p in text for p in biz_phrases) or any(w in words for w in biz_words):
        return "business"

    # 8. Science
    sci_phrases = ["climate change", "quantum computing", "solar panels"]
    sci_words = ["science", "scientific", "nature", "physics", "chemistry", "biology", "genetics", "fossil", "fossils", "archaeology", "quantum", "researchers", "study", "scientists", "photovoltaics", "perovskite"]
    if any(p in text for p in sci_phrases) or any(w in words for w in sci_words):
        return "science"

    # 9. World
    world_phrases = ["middle east", "united nations", "prime minister"]
    world_words = ["world", "global", "europe", "asia", "china", "ukraine", "russia", "president", "election", "politics", "government", "treaty", "nation", "international"]
    if any(p in text for p in world_phrases) or any(w in words for w in world_words):
        return "world"

    # Fallback to feed default category, or default "latest-news"
    return feed_default_cat or "latest-news"

def titles_are_similar(t1, t2):
    """Determines if two titles are semantically similar using Jaccard index of key terms."""
    w1 = set(w for w in re.sub(r'[^\w\s]', '', t1.lower()).split() if len(w) > 3)
    w2 = set(w for w in re.sub(r'[^\w\s]', '', t2.lower()).split() if len(w) > 3)
    if not w1 or not w2:
        return False
    intersection = w1.intersection(w2)
    union = w1.union(w2)
    return (len(intersection) / len(union)) > 0.6

def fetch_and_parse_feeds():
    """Fetches all RSS feeds and processes raw articles."""
    articles = []
    
    for feed in FEEDS:
        print(f"Fetching from {feed['source']} ({feed['category']})...")
        try:
            req = urllib.request.Request(
                feed['url'], 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                xml_data = response.read()
                root = ET.fromstring(xml_data)
                
                # Detect Atom vs RSS 2.0 vs RDF
                if "feed" in root.tag.lower():  # Atom Feed
                    # Atom namespaces
                    ns = {"atom": "http://www.w3.org/2005/Atom"}
                    for entry in root.findall("atom:entry", ns):
                        title_el = entry.find("atom:title", ns)
                        title = title_el.text if title_el is not None else ""
                        
                        link_el = entry.find("atom:link", ns)
                        link = link_el.attrib.get("href") if link_el is not None else ""
                        
                        desc_el = entry.find("atom:summary", ns)
                        if desc_el is None:
                            desc_el = entry.find("atom:content", ns)
                        raw_desc = desc_el.text if desc_el is not None else ""
                        description = clean_html(raw_desc)
                        
                        pub_el = entry.find("atom:published", ns)
                        if pub_el is None:
                            pub_el = entry.find("atom:updated", ns)
                        pubdate_str = pub_el.text if pub_el is not None else ""
                        
                        content_el = entry.find("{http://www.w3.org/2005/Atom}content", ns)
                        encoded_content = content_el.text if content_el is not None else ""
                        
                        image = extract_image_url(entry, raw_desc, encoded_content)
                        
                        parsed_date = parse_pubdate(pubdate_str)
                        category = classify_category(title, description, feed['category'])
                        
                        if title and link:
                            articles.append({
                                "title": title.strip(),
                                "link": link.strip(),
                                "description": description,
                                "pub_date": parsed_date,
                                "source": feed['source'],
                                "category": category,
                                "image": image
                            })
                            
                else:  # RSS 2.0 or RDF
                    channel = root.find("channel")
                    items = []
                    if channel is not None:
                        items = channel.findall("item")
                    else:
                        # RDF items are directly under root
                        # RDF/RSS 1.0 items are prefixed with namespace, search with localname
                        items = root.findall(".//{http://purl.org/rss/1.0/}item")
                        if not items:
                            items = root.findall("item") # Fallback
                            
                    for item in items:
                        title_el = item.find("title")
                        if title_el is None:
                            title_el = item.find("{http://purl.org/rss/1.0/}title")
                        title = title_el.text if title_el is not None else ""
                        
                        link_el = item.find("link")
                        if link_el is None:
                            link_el = item.find("{http://purl.org/rss/1.0/}link")
                        link = link_el.text if link_el is not None else ""
                        
                        desc_el = item.find("description")
                        if desc_el is None:
                            desc_el = item.find("{http://purl.org/rss/1.0/}description")
                        raw_desc = desc_el.text if desc_el is not None else ""
                        description = clean_html(raw_desc)
                        
                        pub_el = item.find("pubDate")
                        pubdate_str = pub_el.text if pub_el is not None else ""
                        
                        encoded_el = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")
                        if encoded_el is None:
                            for child in item:
                                if 'encoded' in child.tag.lower():
                                    encoded_el = child
                                    break
                        encoded_content = encoded_el.text if encoded_el is not None else ""
                        
                        image = extract_image_url(item, raw_desc, encoded_content)
                        
                        parsed_date = parse_pubdate(pubdate_str)
                        category = classify_category(title, description, feed['category'])
                        
                        if title and link:
                            articles.append({
                                "title": title.strip(),
                                "link": link.strip(),
                                "description": description,
                                "pub_date": parsed_date,
                                "source": feed['source'],
                                "category": category,
                                "image": image
                            })
        except Exception as e:
            print(f"Error parsing feed {feed['url']}: {e}")
            
    print(f"Total articles harvested: {len(articles)}")
    return articles

def process_articles(raw_articles):
    """Filters by freshness, removes duplicates, and sorts articles."""
    processed = []
    seen_urls = set()
    now_utc = datetime.now(timezone.utc)
    
    # 1. Filter by Freshness (maximum 72 hours old)
    max_age = timedelta(hours=72)
    fresh_articles = []
    for art in raw_articles:
        age = now_utc - art['pub_date']
        if age <= max_age:
            fresh_articles.append(art)
            
    print(f"Articles after freshness filter (<72h): {len(fresh_articles)}")
    
    # 2. Sort by date descending (so we evaluate duplicates keeping the newest one first)
    fresh_articles.sort(key=lambda x: x['pub_date'], reverse=True)
    
    # 3. Deduplicate
    for art in fresh_articles:
        # Check URL duplication
        if art['link'] in seen_urls:
            continue
            
        # Check Title similarity duplication
        duplicate = False
        for p_art in processed:
            if titles_are_similar(art['title'], p_art['title']):
                duplicate = True
                break
                
        if not duplicate:
            processed.append(art)
            seen_urls.add(art['link'])
            
    print(f"Articles after deduplication: {len(processed)}")
    return processed

def format_date_display(dt):
    """Formats datetime object to standard human readable display."""
    return dt.strftime("%b %d, %Y - %I:%M %p UTC")

def generate_html_card(article, card_type="grid"):
    """Generates the HTML string representation of an article card."""
    image_url = article['image']
    category = article['category']
    fallback_url = get_fallback_image(article['title'], category)
    if not image_url:
        image_url = fallback_url
        
    date_display = format_date_display(article['pub_date'])
    category_label = category.replace('-', ' ')
    
    if card_type == "featured":
        return f"""
        <article class="news-card featured-card fade-in-element" data-category="{category}">
            <div class="card-img-wrapper">
                <img src="{image_url}" alt="{html.escape(article['title'])}" class="card-img" loading="lazy" onerror="this.onerror=null; this.src='{fallback_url}';">
                <span class="card-badge" style="background: var(--cat-{category.split('-')[0]});">{html.escape(category_label)}</span>
            </div>
            <div class="card-content">
                <div class="card-meta">
                    <span class="meta-source">{html.escape(article['source'])}</span>
                    <span class="meta-dot"></span>
                    <span class="meta-date">{date_display}</span>
                </div>
                <a href="{article['link']}" target="_blank" class="card-title">{html.escape(article['title'])}</a>
                <p class="card-description">{html.escape(article['description'])}</p>
                <div class="card-footer">
                    <a href="{article['link']}" target="_blank" class="read-more-btn">
                        Read Full Article <i class="fas fa-arrow-right"></i>
                    </a>
                </div>
            </div>
        </article>
        """
    elif card_type == "sidebar":
        return f"""
        <div class="sidebar-item" data-category="{category}">
            <a href="{article['link']}" target="_blank" class="sidebar-item-title">{html.escape(article['title'])}</a>
            <div class="sidebar-item-meta">
                <span>{html.escape(article['source'])}</span>
                <span>•</span>
                <span>{date_display}</span>
            </div>
        </div>
        """
    else: # grid
        return f"""
        <article class="news-card fade-in-element" data-category="{category}">
            <div class="card-img-wrapper">
                <img src="{image_url}" alt="{html.escape(article['title'])}" class="card-img" loading="lazy" onerror="this.onerror=null; this.src='{fallback_url}';">
                <span class="card-badge" style="background: var(--cat-{category.split('-')[0]});">{html.escape(category_label)}</span>
            </div>
            <div class="card-content">
                <div class="card-meta">
                    <span class="meta-source">{html.escape(article['source'])}</span>
                    <span class="meta-dot"></span>
                    <span class="meta-date">{date_display}</span>
                </div>
                <a href="{article['link']}" target="_blank" class="card-title">{html.escape(article['title'])}</a>
                <p class="card-description">{html.escape(article['description'])}</p>
                <div class="card-footer">
                    <a href="{article['link']}" target="_blank" class="read-more-btn">
                        Read More <i class="fas fa-arrow-right"></i>
                    </a>
                </div>
            </div>
        </article>
        """

def compile_website(articles):
    """Generates the static index.html structure using processed articles."""
    total_count = len(articles)
    last_updated = format_date_display(datetime.now(timezone.utc))
    default_meta_img = "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=800&q=80"
    
    # Curated premium mock ads to fulfill page advertisement requirements
    ads_pool = [
        {
            "title": "Protect Your Digital Life",
            "desc": "Deploy CyberShield Pro firewall. Advanced threat detection & zero-logs VPN starting at just $4.99/mo.",
            "img": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?auto=format&fit=crop&w=400&q=80",
            "btn_text": "Secure Shield",
            "badge_color": "#06b6d4"
        },
        {
            "title": "Scale Your LLM Apps Instantly",
            "desc": "Run state-of-the-art models on high-performance server grids. Get 100,000 free tokens today with DevOS Cloud.",
            "img": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=400&q=80",
            "btn_text": "Deploy Free",
            "badge_color": "#8b5cf6"
        },
        {
            "title": "Commercial Space Flights Open",
            "desc": "Experience Earth orbit with AstroVenture Tours. Reservations now open for Q1 2027 expeditions.",
            "img": "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=400&q=80",
            "btn_text": "Book Orbit",
            "badge_color": "#f59e0b"
        }
    ]
    # Deterministic choice based on day of year to show rotating ads
    day_val = datetime.now(timezone.utc).timetuple().tm_yday
    ad = ads_pool[day_val % len(ads_pool)]
    
    sponsor_html = f"""
    <div class="sponsor-card" style="--sponsor-color: {ad['badge_color']};">
        <div class="sponsor-tag">Advertisement</div>
        <div class="sponsor-img-wrapper">
            <img src="{ad['img']}" alt="Sponsored Ad" class="sponsor-img">
        </div>
        <div class="sponsor-content">
            <h4 class="sponsor-title">{html.escape(ad['title'])}</h4>
            <p class="sponsor-description">{html.escape(ad['desc'])}</p>
            <a href="https://github.com" target="_blank" class="sponsor-btn">
                {html.escape(ad['btn_text'])} <i class="fas fa-external-link-alt"></i>
            </a>
        </div>
    </div>
    """
    
    # Partition layout: Hero (1), Sidebar (5), Grid (Rest)
    featured_html = ""
    sidebar_html = ""
    grid_html = ""
    
    if total_count > 0:
        featured_html = generate_html_card(articles[0], card_type="featured")
        
        sidebar_items = articles[1:6]
        sidebar_html = "".join(generate_html_card(art, card_type="sidebar") for art in sidebar_items)
        
        grid_items = articles[6:]
        grid_html = "".join(generate_html_card(art, card_type="grid") for art in grid_items)
    else:
        grid_html = "<p class='search-no-results' style='display:block;'>No news articles available. Please check back later.</p>"
        
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chronicle AI | Premium Autonomous News Portal</title>
    
    <!-- Google AdSense -->
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5643628392894798"
     crossorigin="anonymous"></script>
    
    <!-- SEO Optimization -->
    <meta name="description" content="Chronicle AI is an autonomous, AI-powered real-time news portal aggregating global updates from trusted sources including BBC, TechCrunch, Wired, NASA and Nature.">
    <meta name="keywords" content="autonomous news, AI news, technology, startups, world news, science, space, cybersecurity, robotics, real-time portal">
    <meta name="author" content="Chronicle AI Engine">
    
    <!-- Open Graph (Facebook / LinkedIn) -->
    <meta property="og:type" content="website">
    <meta property="og:title" content="Chronicle AI | Premium Autonomous News Portal">
    <meta property="og:description" content="Autonomous real-time news portal aggregating science, tech, space, and world updates from verified sources.">
    <meta property="og:image" content="{default_meta_img}">
    <meta property="og:url" content="./index.html">
    
    <!-- Twitter Cards -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Chronicle AI | Premium Autonomous News Portal">
    <meta name="twitter:description" content="Autonomous real-time news portal aggregating science, tech, space, and world updates.">
    <meta name="twitter:image" content="{default_meta_img}">
    
    <!-- Stylesheets & Fonts -->
    <link rel="stylesheet" href="styles.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>

    <!-- Background Glow Blobs -->
    <div class="blur-blobs">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
        <div class="blob blob-3"></div>
    </div>

    <!-- Navigation Header -->
    <header>
        <div class="nav-container">
            <a href="#" class="logo-link">
                <span class="logo-text">Chronicle.ai</span>
                <span class="logo-badge">Auto</span>
            </a>
            
            <nav>
                <ul class="nav-links">
                    <li class="nav-item active" data-category="all"><a href="#">Home</a></li>
                    <li class="nav-item" data-category="ai-news"><a href="#ai">AI News</a></li>
                    <li class="nav-item" data-category="technology"><a href="#tech">Technology</a></li>
                    <li class="nav-item" data-category="cybersecurity"><a href="#cyber">Cybersecurity</a></li>
                    <li class="nav-item" data-category="business"><a href="#business">Business</a></li>
                    <li class="nav-item" data-category="science"><a href="#science">Science</a></li>
                    <li class="nav-item" data-category="space"><a href="#space">Space</a></li>
                    <li class="nav-item" data-category="world"><a href="#world">World</a></li>
                    <li class="nav-item"><a href="#footer-section">About</a></li>
                </ul>
            </nav>
            
            <div class="nav-actions">
                <div class="search-container">
                    <i class="fas fa-search search-icon"></i>
                    <input type="text" class="search-input" placeholder="Search articles...">
                </div>
                <button class="menu-toggle" aria-label="Toggle Menu">
                    <i class="fas fa-bars"></i>
                </button>
            </div>
        </div>
    </header>

    <!-- Main Content Container -->
    <main>
    
        <!-- Hero Title -->
        <section class="hero-section">
            <div class="hero-title-section">
                <span class="hero-subtitle">Autonomous Research Engine</span>
                <h1 class="hero-title">Veracity. Depth. Speed.</h1>
            </div>
        </section>
        
        <!-- Featured Grid: Hero Article & Trending Sidebar -->
        <section class="featured-container" id="featured-news">
            {featured_html}
            
            <aside class="featured-sidebar">
                <h2 class="sidebar-title">
                    <i class="fas fa-bolt" style="color: #f59e0b;"></i> Trending Now
                </h2>
                <div class="sidebar-list">
                    {sidebar_html}
                </div>
                {sponsor_html}
            </aside>
        </section>
        
        <!-- Articles Feed Grid -->
        <section id="news-feed">
            <div class="section-header">
                <h2 class="section-title">Latest News Feed</h2>
            </div>
            
            <div class="articles-grid">
                {grid_html}
                
                <!-- No Results fallback -->
                <div class="search-no-results" id="search-no-results">
                    <i class="fas fa-search-minus"></i>
                    <h3>No matching stories found</h3>
                    <p>Try searching for other keywords or select a different category.</p>
                </div>
            </div>
        </section>
        
    </main>

    <!-- Back to Top Button -->
    <a href="#" class="back-to-top" aria-label="Back to Top">
        <i class="fas fa-chevron-up"></i>
    </a>

    <!-- Footer Area -->
    <footer id="footer-section">
        <div class="footer-container">
            <span class="footer-logo">Chronicle.ai</span>
            
            <div class="footer-meta">
                <span><i class="far fa-clock"></i> Last updated: {last_updated}</span>
                <span>•</span>
                <span id="total-articles-count"><i class="far fa-newspaper"></i> {total_count} articles harvested</span>
                <span>•</span>
                <span class="footer-tag">Auto-updated every 3 hours</span>
            </div>
            
            <p class="footer-copyright">
                &copy; {datetime.now(timezone.utc).year} Chronicle AI News Portal. Static, client-side, zero-infrastructure deployment.
            </p>
        </div>
    </footer>

    <!-- Client Script -->
    <script src="script.js"></script>
</body>
</html>
"""
    with open(OUTPUT_HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Generated index.html successfully at {OUTPUT_HTML_PATH}")

def main():
    print(f"=========================================")
    print(f"News Generator Started at {datetime.now(timezone.utc)}")
    print(f"=========================================")
    
    raw = fetch_and_parse_feeds()
    if not raw:
        print("No articles fetched. Skipping build to prevent overwriting with blank screen.")
        return
        
    processed = process_articles(raw)
    compile_website(processed)
    
    print(f"=========================================")
    print(f"News Generator Finished Successfully at {datetime.now(timezone.utc)}")
    print(f"=========================================")

if __name__ == '__main__':
    main()
