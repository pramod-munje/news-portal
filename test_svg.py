import urllib.parse

def get_fallback_image(title, category):
    category_colors = {
        "ai-news": ("#1e1b4b", "#065f46"),
        "cybersecurity": ("#0f172a", "#831843"),
        "space": ("#000000", "#1e1b4b"),
        "robotics": ("#171717", "#0f766e"),
        "startups": ("#422006", "#86198f"),
        "technology": ("#020617", "#1d4ed8"),
        "business": ("#064e3b", "#0f172a"),
        "science": ("#2e1065", "#0f172a"),
        "world": ("#000000", "#000000"),
        "latest-news": ("#171717", "#171717")
    }
    c1, c2 = category_colors.get(category, ("#0f172a", "#1e1b4b"))
    
    label = category.replace('-', ' ').title()
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="0 0 800 450">
<defs>
<linearGradient id="grad-{category}" x1="0%" y1="0%" x2="100%" y2="100%">
<stop offset="0%" stop-color="{c1}" />
<stop offset="100%" stop-color="{c2}" />
</linearGradient>
</defs>
<rect width="800" height="450" fill="url(#grad-{category})" />
<text x="400" y="225" font-family="system-ui, sans-serif" font-size="48" font-weight="bold" fill="#ffffff" text-anchor="middle" dominant-baseline="middle" opacity="0.8">
{label}
</text>
</svg>'''
    encoded = urllib.parse.quote(svg)
    return f"data:image/svg+xml;charset=utf-8,{encoded}"

print(get_fallback_image("test", "ai-news"))
